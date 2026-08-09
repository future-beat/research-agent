"""
The eval runner.

Runs the golden dataset through the real compiled graph and grades what comes
back. Two modes:

    offline   a scripted client stands in for the API. Free, deterministic,
              CI-safe. Grades the pipeline -- routing, guardrails, honesty --
              and the graders themselves. The scripted output is authored in
              the dataset, so nothing about the current model's quality can be
              read from it; `replay_case` grades the answers a real run once
              gave (committed fixtures), which is a claim about what the
              pipeline said then, not what it would say now.

    live      real API, real web search, plus judge graders on a stronger
              model. This is the one that measures quality; it costs money
              and its results move between runs.

Both modes drive the same `graph.app`, so an eval failure is a real
failure of the shipped graph rather than of a parallel reimplementation.
"""

from __future__ import annotations

import contextlib
import os
import time
from dataclasses import dataclass, field

from evals import graders as G
from evals.dataset import APPROVED, Case, Followup
from research_agent import graph
from research_agent.graph import followup_state, initial_state
from research_agent.memory import InMemoryStore

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
    # The turn's final AgentState, kept only when recording (see
    # `run_case(capture_state=True)`). Deliberately absent from `as_dict`:
    # states are tens of KB each and the report is read by humans and CI, so
    # a recorded state's home is its fixture file, not the report.
    state: dict | None = None

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
    capture_state: bool = False,
) -> CaseResult:
    """Run one golden case end to end and grade every turn.

    Each case gets its own memory store: recall across cases would make
    results depend on dataset ordering, which is the kind of flakiness that
    trains people to ignore a failing suite.

    `capture_state` keeps each turn's final state instead of discarding it,
    which is all a recorder needs. It is a seam here rather than a separate
    recording pipeline because everything else a recorder wants -- budget
    scoping, per-case memory, follow-up chaining, error isolation -- is
    already correct in this function, and a parallel driver would drift from
    the shipped graph in exactly the way this harness exists to prevent.
    Off, which is every caller but the recorder, nothing changes.
    """
    result = CaseResult(case_id=case.id, why=case.why)
    previous_client = graph._client
    previous_memory = graph._memory

    try:
        graph._client = client_factory(case)
        graph.set_memory(memory_factory())

        with _budget(case.budget_usd):
            started = time.perf_counter()
            state = graph.app.invoke(initial_state(case.task))
            elapsed = (time.perf_counter() - started) * 1000

            result.turns.append(
                TurnResult(
                    label="research",
                    grades=_grade_research(case, state, judge),
                    cost_usd=state["usage"]["cost_usd"],
                    duration_ms=elapsed,
                    # Copied at append time so a later turn cannot alias an
                    # earlier one's record.
                    state=dict(state) if capture_state else None,
                )
            )

            for fu in case.followups:
                started = time.perf_counter()
                state = graph.app.invoke(followup_state(state, fu.question))
                elapsed = (time.perf_counter() - started) * 1000
                result.turns.append(
                    TurnResult(
                        label=fu.question,
                        grades=_grade_followup(case, fu, state, judge),
                        cost_usd=state["usage"]["cost_usd"],
                        duration_ms=elapsed,
                        state=dict(state) if capture_state else None,
                    )
                )

    except Exception as exc:  # noqa: BLE001 - one bad case shouldn't end the suite
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        graph._client = previous_client
        graph.set_memory(previous_memory)

    return result


# --------------------------------------------------------------------------
# Replaying one recorded case
#
# A fixture is a run that already happened. Replay grades it with exactly the
# vocabulary a live run is graded with -- the same deterministic graders over
# the same state dicts -- plus the two things only a recording can be asked:
# is it still current, and do the verdicts it was recorded with still hold.
# No client, no memory, no network, no key, no spend.
# --------------------------------------------------------------------------


def grade_fixture_current(fixture: dict) -> G.Grade:
    """The recording must have been made on the model this tree runs.

    This is the deterministic staleness gate, and the only one there is: age
    prints in the caveat but never grades, because a grader that fails on the
    calendar makes the same commit pass in August and fail in October.
    `models.pipeline` against `graph.MODEL` fires exactly when a code change
    invalidates the recordings, and never otherwise.

    Cannot catch: a change to any model this map does not compare. It reads
    `models["pipeline"]` against `graph.MODEL` -- the writer/researcher model --
    and nothing else. Phase 16 makes the CRITIC's model configurable
    INDEPENDENTLY of `graph.MODEL` (ROADMAP, Phase 16 SC-1), so a critic-model
    change will NOT fire this gate: the recordings would stay green with only
    the printed recording date hinting that they describe an older pipeline.
    Closing that needs three things together -- a per-node entry in the
    fixture's `models` map, this gate extended to compare it, and the fixtures
    re-recorded. The map exists precisely so that extension is additive rather
    than a schema bump.

    It lives here rather than in graders.py so that graders.py never imports
    the graph: the quality rubrics are pure functions of a recorded state, and
    a gate that reads the running code is a different kind of check.
    """
    name = "fixture_current"
    recorded = fixture.get("models", {}).get("pipeline")
    if recorded == graph.MODEL:
        return G.Grade(name, True, f"recorded on {recorded}, which is what this tree runs")
    return G.Grade(
        name,
        False,
        f"recorded on {recorded!r} but this tree runs {graph.MODEL!r} -- "
        "the recording describes a pipeline that no longer exists; re-record",
    )


def _recorded_judge_grades(turn: dict) -> list[G.Grade]:
    """The judge verdicts this turn was recorded with, replayed as gates.

    They are fixed data now, so `judged` is False: nothing was asked of a
    model to produce these. The recorder refuses to write a fixture whose own
    grades failed, so a red here means a hand-edited file or a `--force`d
    recording -- both worth a red, and both worth a non-zero exit.
    """
    grades = []
    for entry in turn["judge"]:
        detail = entry.get("detail") or entry.get("reason") or ""
        grades.append(
            G.Grade(f"recorded_{entry['grader']}", bool(entry["passed"]), detail, judged=False)
        )
    return grades


def replay_case(case: Case, fixture: dict) -> CaseResult:
    """Grade a recorded run: the behavioural graders, the quality graders, the
    staleness gate, and the recorded judge verdicts.

    The case ids are suffixed `@recorded` so the printout and the report can
    never confuse the replay leg with the behavioural one -- they grade the
    same case for different reasons and can disagree.

    Malformed input is isolated the way `run_case` isolates a crashing case:
    into `result.error`, loud and red, rather than ending the run. A recorded
    state missing a key some grader reads is exactly the shape of the bug that
    would otherwise grade vacuously green.
    """
    result = CaseResult(case_id=f"{case.id}@recorded", why=case.why)

    turns = fixture.get("turns", [])
    expected = 1 + len(case.followups)
    if len(turns) != expected:
        result.error = (
            f"fixture records {len(turns)} turn(s) but case {case.id!r} has {expected} "
            f"(research + {len(case.followups)} follow-up(s)) -- the dataset moved "
            "under the recording; re-record"
        )
        return result

    try:
        model_gate = grade_fixture_current(fixture)
        for index, turn in enumerate(turns):
            state = turn["state"]
            if index == 0:
                grades = [grader(case, state) for grader in G.DETERMINISTIC_GRADERS]
                grades += [grader(case, state) for grader in G.RECORDED_GRADERS]
                grades.append(model_gate)
            else:
                fu = case.followups[index - 1]
                grades = [grader(case, fu, state) for grader in G.FOLLOWUP_GRADERS]
                grades += [grader(case, fu, state) for grader in G.RECORDED_FOLLOWUP_GRADERS]
            grades += _recorded_judge_grades(turn)
            result.turns.append(TurnResult(label=turn["label"], grades=grades))
    except Exception as exc:  # noqa: BLE001 - one bad fixture shouldn't end the suite
        result.error = f"{type(exc).__name__}: {exc}"

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
        "model": graph.MODEL,
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
