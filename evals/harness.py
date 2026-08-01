"""
The eval runner.

Runs the golden dataset through the real compiled graph and grades what comes
back. Two modes:

    offline   a scripted client stands in for the API. Free, deterministic,
              CI-safe. Grades the pipeline -- routing, guardrails, honesty --
              and the graders themselves. It cannot grade model quality,
              because the model output is authored in the dataset.

    live      real API, real web search, plus judge graders on a stronger
              model. This is the one that measures quality; it costs money
              and its results move between runs.

Both modes drive the same `research_agent.app`, so an eval failure is a real
failure of the shipped graph rather than of a parallel reimplementation.
"""

from __future__ import annotations

import contextlib
import os
import time
from dataclasses import dataclass, field

import research_agent
from evals import graders as G
from evals.dataset import APPROVED, Case, Followup
from research_agent import followup_state, initial_state
from vector_memory import InMemoryStore


# --------------------------------------------------------------------------
# Offline scripting
# --------------------------------------------------------------------------


class _Block:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _ServerToolUse:
    def __init__(self, web_search_requests: int):
        self.web_search_requests = web_search_requests
        self.web_fetch_requests = 0


class _Usage:
    def __init__(self, web_search_requests: int = 0):
        self.input_tokens = 2000
        self.output_tokens = 400
        self.cache_read_input_tokens = None
        self.cache_creation_input_tokens = None
        self.server_tool_use = _ServerToolUse(web_search_requests)


class _Response:
    def __init__(self, text: str, web_search_requests: int = 0):
        self.content = [_Block(text)]
        self.usage = _Usage(web_search_requests)


class HashEmbedder:
    """A deterministic stand-in for Voyage, used offline.

    Without it, "offline" would still reach the network on every note the
    researcher stores -- and an eval suite that needs an API key to run for
    free is not a CI suite. Bag-of-words hashing gives stable vectors where
    shared vocabulary means similarity, which is all the recall path needs
    to be exercised.
    """

    DIMENSIONS = 64

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.DIMENSIONS
        for word in text.lower().split():
            vec[hash(word) % self.DIMENSIONS] += 1.0
        if not any(vec):
            vec[0] = 1e-6
        return vec

    def embed_documents(self, texts):
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        return self._vector(text)


class ScriptedClient:
    """Replays a case's authored output, dispatching on which node is calling.

    Nodes are identified by their prompt rather than by an argument, so the
    scripting stays honest: if a node's prompt is rewritten such that it no
    longer looks like itself, the eval notices instead of silently passing.
    """

    def __init__(self, case: Case):
        self.case = case
        self.verdicts = list(case.critic_verdicts)
        self.answers = [fu.answer for fu in case.followups]
        self.calls: list[str] = []
        self.messages = self

    def create(self, **kwargs) -> _Response:
        prompt = kwargs["messages"][0]["content"]

        if "Respond with exactly one word" in prompt:
            node, text, searches = "classifier", self.case.topic_label, 0
        elif "Search the web" in prompt:
            node, text, searches = "researcher", self.case.notes, 2
        elif "follow-up question" in prompt:
            node = "responder"
            text = self.answers.pop(0) if self.answers else "(no scripted answer)"
            searches = 0
        elif "Does the" in prompt:
            node = "critic"
            text = self.verdicts.pop(0) if self.verdicts else APPROVED
            searches = 0
        else:
            node, text, searches = "writer", self.case.report, 0

        self.calls.append(node)
        return _Response(text, searches)


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass
class TurnResult:
    label: str  # "research", or the follow-up question
    grades: list[G.Grade] = field(default_factory=list)
    cost_usd: float = 0.0
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.grades)

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "passed": self.passed,
            "cost_usd": round(self.cost_usd, 6),
            "duration_ms": round(self.duration_ms, 1),
            "grades": [g.as_dict() for g in self.grades],
        }


@dataclass
class CaseResult:
    case_id: str
    why: str
    turns: list[TurnResult] = field(default_factory=list)
    error: str = ""

    @property
    def passed(self) -> bool:
        return not self.error and all(t.passed for t in self.turns)

    @property
    def cost_usd(self) -> float:
        return sum(t.cost_usd for t in self.turns)

    @property
    def failures(self) -> list[G.Grade]:
        return [g for turn in self.turns for g in turn.grades if not g.passed]

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "why": self.why,
            "passed": self.passed,
            "error": self.error,
            "cost_usd": round(self.cost_usd, 6),
            "turns": [t.as_dict() for t in self.turns],
        }


# --------------------------------------------------------------------------
# Running one case
# --------------------------------------------------------------------------


def _grade_research(case: Case, state: dict, judge: G.Judge | None) -> list[G.Grade]:
    grades = [grader(case, state) for grader in G.DETERMINISTIC_GRADERS]
    if judge is not None:
        grades += [grader(judge, case, state) for grader in G.JUDGE_GRADERS]
    return grades


def _grade_followup(
    case: Case, fu: Followup, state: dict, judge: G.Judge | None
) -> list[G.Grade]:
    grades = [grader(case, fu, state) for grader in G.FOLLOWUP_GRADERS]
    if judge is not None:
        grades.append(G.judge_followup_honesty(judge, case, fu, state))
    return grades


@contextlib.contextmanager
def _budget(limit: float | None):
    """Temporarily override the spend cap for a case that exercises it.

    The guardrail cases need a budget small enough to trip; every other case
    needs the real one, so this is scoped rather than global.
    """
    if limit is None:
        yield
        return
    key = "AGENT_MAX_RUN_COST_USD"
    previous = os.environ.get(key)
    os.environ[key] = repr(limit)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def run_case(
    case: Case,
    *,
    client_factory,
    memory_factory,
    judge: G.Judge | None = None,
) -> CaseResult:
    """Run one golden case end to end and grade every turn.

    Each case gets its own memory store: recall across cases would make
    results depend on dataset ordering, which is the kind of flakiness that
    trains people to ignore a failing suite.
    """
    result = CaseResult(case_id=case.id, why=case.why)
    previous_client = research_agent._client
    previous_memory = research_agent._memory

    try:
        research_agent._client = client_factory(case)
        research_agent.set_memory(memory_factory())

        with _budget(case.budget_usd):
            started = time.perf_counter()
            state = research_agent.app.invoke(initial_state(case.task))
            elapsed = (time.perf_counter() - started) * 1000

            result.turns.append(
                TurnResult(
                    label="research",
                    grades=_grade_research(case, state, judge),
                    cost_usd=state["usage"]["cost_usd"],
                    duration_ms=elapsed,
                )
            )

            for fu in case.followups:
                started = time.perf_counter()
                state = research_agent.app.invoke(followup_state(state, fu.question))
                elapsed = (time.perf_counter() - started) * 1000
                result.turns.append(
                    TurnResult(
                        label=fu.question,
                        grades=_grade_followup(case, fu, state, judge),
                        cost_usd=state["usage"]["cost_usd"],
                        duration_ms=elapsed,
                    )
                )

    except Exception as exc:  # noqa: BLE001 - one bad case shouldn't end the suite
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        research_agent._client = previous_client
        research_agent.set_memory(previous_memory)

    return result


# --------------------------------------------------------------------------
# Running the suite
# --------------------------------------------------------------------------


def summarise(results: list[CaseResult], min_pass_rate: float) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = round(passed / total, 4) if total else None

    by_grader: dict[str, dict[str, int]] = {}
    for result in results:
        for turn in result.turns:
            for grade in turn.grades:
                bucket = by_grader.setdefault(grade.grader, {"passed": 0, "failed": 0})
                bucket["passed" if grade.passed else "failed"] += 1

    return {
        "cases": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": pass_rate,
        "errored": sum(1 for r in results if r.error),
        "by_grader": by_grader,
        "cost_usd": round(sum(r.cost_usd for r in results), 6),
        "duration_ms": round(
            sum(t.duration_ms for r in results for t in r.turns), 1
        ),
        # A suite with zero cases must not report success -- an empty run is a
        # broken selector, not a green build.
        "ok": bool(total) and pass_rate is not None and pass_rate >= min_pass_rate,
        "min_pass_rate": min_pass_rate,
    }


def run_suite(
    cases,
    *,
    client_factory,
    memory_factory,
    judge: G.Judge | None = None,
    mode: str = "offline",
    min_pass_rate: float = 0.9,
    on_result=None,
) -> dict:
    results: list[CaseResult] = []
    for case in cases:
        result = run_case(
            case, client_factory=client_factory, memory_factory=memory_factory, judge=judge
        )
        results.append(result)
        if on_result:
            on_result(result)

    return {
        "mode": mode,
        "model": research_agent.MODEL,
        "judge_model": judge.model if judge else None,
        "judge_calls": judge.calls if judge else 0,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cases": [r.as_dict() for r in results],
        "summary": summarise(results, min_pass_rate),
    }


def offline_client_factory(case: Case) -> ScriptedClient:
    return ScriptedClient(case)


def offline_memory_factory() -> InMemoryStore:
    return InMemoryStore(embedder=HashEmbedder())


def live_memory_factory() -> InMemoryStore:
    """Real embeddings, but a store per case.

    Deliberately not the persistent store: cross-case recall would make
    results depend on dataset ordering, and a suite whose verdict changes
    when you reorder it teaches people to ignore it.
    """
    return InMemoryStore()
