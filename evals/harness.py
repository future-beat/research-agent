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
import pathlib
import sys
import time
from dataclasses import dataclass, field

from evals import fixtures as F
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
        # Bound rather than passed straight through, because a case may want
        # to put something in its store before the graph reads it.
        store = memory_factory()
        graph.set_memory(store)
        for note in case.seeded_notes:
            # Owner "" is the identity this harness runs as, so a seeded note
            # is recallable by this run and by nothing else -- the store is
            # built per case, so there is no other run to leak into. See the
            # heavy-overlap authoring rule on `Case.seeded_notes`: a note that
            # shares little vocabulary with the task may not clear the recall
            # floor, and a seed that is never recalled tests nothing.
            store.add(note, owner="")

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
    """The recording must have been made on the models this tree runs.

    This is the deterministic staleness gate, and the only one there is: age
    prints in the caveat but never grades, because a grader that fails on the
    calendar makes the same commit pass in August and fail in October. It
    compares TWO roles: `models.pipeline` against `graph.MODEL`, and
    `models.critic` against `graph.critic_model()`. Either moving fires it,
    and nothing else does.

    The critic comparison BACKFILLS -- `models.get("critic") or pipeline`.
    That is a fact about pre-Phase-16 recordings, not a guess: at record time
    the code had no critic seam at all, so the critic ran on `graph.MODEL` by
    construction, verifiable from this git history. A falsy value (key absent,
    null, or the empty string) is read as absent for the same reason
    `critic_model()` reads a blank `CRITIC_MODEL` as unset: a blank names no
    model, so the pre-16 reading is the only honest one available. From this
    phase on `record_case_to_fixture` always writes the key, so absence keeps
    meaning pre-16 -- and the pre-16 population is exactly one file
    (`technical-figures.json`), which the deferred full record run replaces.

    Consequence of the deployed configuration, stated rather than discovered:
    production sets `CRITIC_MODEL=claude-opus-5` (Phase 16's cutover), and the
    committed fixture predates the Opus critic. A suite run in an environment
    that sets `CRITIC_MODEL` therefore grades it STALE -- the designed
    staleness, not a bug, and the verdict is the thing that tells the story
    until the deferred record run re-records under the new critic. CI and
    keyless contexts never set the variable, so `critic_model() == graph.MODEL`
    there and the fixture stays green.

    Cannot catch: a change to any model this map does not compare. The JUDGE's
    is recorded and deliberately not checked -- its verdicts are fixed data in
    the fixture, replayed as `recorded_*` grades, so pointing `JUDGE_MODEL`
    somewhere new does not invalidate a word of what the old judge already
    said; it changes only what a fresh recording would claim. Nor can it catch
    a model this map never carried at all: the gate is only ever as wide as
    the roles the recorder writes.

    It lives here rather than in graders.py so that graders.py never imports
    the graph: the quality rubrics are pure functions of a recorded state, and
    a gate that reads the running code is a different kind of check.
    """
    name = "fixture_current"
    models = fixture.get("models", {})
    recorded = models.get("pipeline")
    # Falsy means absent means pre-16 -- see the docstring's backfill paragraph.
    recorded_critic = models.get("critic") or recorded
    current_critic = graph.critic_model()

    if recorded != graph.MODEL:
        return G.Grade(
            name,
            False,
            f"recorded on {recorded!r} but this tree runs {graph.MODEL!r} -- "
            "the recording describes a pipeline that no longer exists; re-record",
        )
    if recorded_critic != current_critic:
        # Name the role and both models: the operator's first question about a
        # stale recording is which model moved, and "pipeline" and "critic" now
        # move independently.
        return G.Grade(
            name,
            False,
            f"the CRITIC was recorded on {recorded_critic!r} but this tree runs it on "
            f"{current_critic!r} (CRITIC_MODEL) -- the recording describes a pipeline "
            "that no longer exists; re-record",
        )
    return G.Grade(
        name,
        True,
        f"recorded on {recorded} with the critic on {recorded_critic}, "
        "which is what this tree runs",
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
# Recording: the one leg that spends money
#
# A recording is `run_case` with the state kept, graded by a real judge, and
# written through the writer that refuses anything the graders failed. There is
# no second driver: the recorder is the same function the live suite runs, with
# `capture_state=True`, because a parallel loop would drift from the shipped
# graph in exactly the way this harness exists to prevent.
# --------------------------------------------------------------------------


@dataclass
class RecordOutcome:
    """What became of one case's recording: a file, or a stated refusal."""

    case_id: str
    result: CaseResult
    path: pathlib.Path | None = None
    refusal: str = ""

    @property
    def written(self) -> bool:
        return self.path is not None

    @property
    def cost_usd(self) -> float:
        return self.result.cost_usd

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "written": self.written,
            "path": str(self.path) if self.path else None,
            "refusal": self.refusal,
            "cost_usd": round(self.cost_usd, 6),
        }


def record_case_to_fixture(
    case: Case,
    *,
    client_factory,
    memory_factory,
    judge: G.Judge | None,
    force: bool = False,
    directory: pathlib.Path | None = None,
) -> RecordOutcome:
    """Run one case for real, keep its states, and write the fixture.

    The judge is MANDATORY, and this is the only place that can enforce it: its
    verdicts are the fixture's metadata *and* the refusal gate, so a judgeless
    recording would commit answers that nothing ever graded and then replay
    them forever as evidence of quality. A missing judge is a programming
    error, not a case-level failure, so it raises rather than becoming an
    outcome -- there is nothing here worth continuing a paid loop for.

    A refusal is NOT an exception: `write_fixture` declining a recording whose
    own grades failed is the system working, one case among forty, and the
    remaining thirty-nine are still worth their money.
    """
    if judge is None:
        raise ValueError(
            "record mode requires a judge -- a fixture's recorded verdicts are both "
            "its metadata and the gate that lets replay assert anything about "
            "quality; there is no judgeless recording"
        )

    result = run_case(
        case,
        client_factory=client_factory,
        memory_factory=memory_factory,
        judge=judge,
        capture_state=True,
    )
    outcome = RecordOutcome(case_id=case.id, result=result)

    try:
        fixture = F.build_fixture(
            case.id,
            result,
            # A map, never a flat string: Phase 16 moves one of these models
            # without moving the other, and a recording that cannot say which
            # is which goes stale invisibly. One entry per role, each naming
            # the model that did that job in THIS recording -- the critic's is
            # read from `critic_model()` at record time, so a recording made
            # from an operator shell with CRITIC_MODEL set says so, and
            # `grade_fixture_current` compares it directly instead of
            # backfilling.
            models={
                "pipeline": graph.MODEL,
                "judge": judge.model,
                "critic": graph.critic_model(),
            },
        )
        outcome.path = F.write_fixture(fixture, result, force=force, directory=directory)
    except F.FixtureError as exc:
        outcome.refusal = str(exc)

    return outcome


def _per_case_memory(memory_factory):
    """Wrap a memory factory so a shared store cannot survive the loop.

    Pitfall 5: a record run inherits the operator's laptop. If `DATABASE_URL`
    is set and the recorder reaches for the persistent store, every case
    recalls the previous ones' notes -- and worse, the operator's real notes --
    which makes the recordings unreproducible and quietly poisons what a
    grounding grader is grading. `live_memory_factory` is the right factory;
    this checks the property rather than the identity, because the property is
    what matters and a test needs to be able to pass a fake.
    """
    seen: list = []

    def per_case():
        store = memory_factory()
        # Two failures, two messages, deliberately. A factory that always hands
        # back the persistent store trips the second check too (on its second
        # call), which is how a single shared message ends up unprovable: no
        # realistic factory can tell the two clauses apart, so the first one
        # looks like a guard while being decorative. Distinct messages make the
        # distinction observable, and the diagnosis is the point -- "you reached
        # for the process's store" and "you reused a store" are different bugs
        # with different fixes.
        if store is graph._memory:
            raise RuntimeError(
                "record mode was handed the process's own memory store. A recording "
                "that recalls the operator's real notes is not reproducible, and "
                "those notes end up inside a committed fixture."
            )
        if any(store is previous for previous in seen):
            raise RuntimeError(
                "record mode requires a fresh store per case: this factory handed "
                "back a store a previous case already used. Cross-case recall makes "
                "a recording depend on the order the dataset happens to be in."
            )
        seen.append(store)
        return store

    return per_case


def _state_judge_critic_relation(judge: G.Judge | None) -> None:
    """Say it out loud, once per record run, when the judge and the in-graph
    critic are the same model.

    This is a STATEMENT OF FACT about what the recordings can claim, not a
    complaint about how the machine is set up -- and the distinction matters
    because it fires on the DEPLOYED configuration: `JUDGE_MODEL` defaults to
    claude-opus-5 and Phase 16's cutover pins `CRITIC_MODEL` to claude-opus-5
    too, deliberately, so the critic is more capable than the writer it gates.
    Every record run made against production's configuration sees this line.
    Wording it as a misconfiguration would train the operator to ignore the one
    line that tells them what their fixtures are worth.

    What it narrows: ADR-0005 claimed the judge is independent of the pipeline.
    ADR-0010 keeps the load-bearing half -- the judge never shares the WRITER's
    model, pinned at `JUDGE_MODEL != graph.MODEL` -- and records the other half
    as accepted rather than met: a grounding failure the critic waved through
    is likelier to be one the judge waves through too, because the same model
    is looking at it twice.

    Not an exception and not a refusal: both variables are legitimate operator
    knobs and this combination is the chosen one. Policy belongs in the record,
    not in a crash.
    """
    if judge is None:
        return
    critic = graph.critic_model()
    if judge.model != critic:
        return
    print(
        f"note: the judge and the in-graph critic both run on {critic}. These recorded "
        "verdicts are independent of the writer's model and not of the critic's -- what "
        "one waves through, the other is likelier to wave through. This is the deployed "
        "configuration and it is accepted, recorded in ADR-0010.",
        file=sys.stderr,
    )


def record_suite(
    cases,
    *,
    client_factory,
    memory_factory,
    judge: G.Judge | None,
    force: bool = False,
    directory: pathlib.Path | None = None,
    min_pass_rate: float = 0.9,
    on_outcome=None,
) -> dict:
    """Record every selected case. One fixture per case that earned one.

    A refused case does not stop the loop, and the report says which were
    refused and why: stopping would waste the spend already made on the cases
    behind it, and hiding it would commit a partial recording set that looks
    complete.
    """
    # Once per run, before the loop: what these forty recordings will and will
    # not be able to claim is worth knowing before they are paid for, and
    # per-case it would print forty times and be read none.
    _state_judge_critic_relation(judge)

    guarded = _per_case_memory(memory_factory)
    # Before anything is spent, not after: a factory that hands out one shared
    # store would poison all forty recordings, and finding that out on case
    # forty costs forty cases' worth of money.
    guarded()
    guarded()

    outcomes: list[RecordOutcome] = []
    for case in cases:
        outcome = record_case_to_fixture(
            case,
            client_factory=client_factory,
            memory_factory=guarded,
            judge=judge,
            force=force,
            directory=directory,
        )
        outcomes.append(outcome)
        if on_outcome:
            on_outcome(outcome)

    results = [o.result for o in outcomes]
    return {
        "mode": "record",
        "model": graph.MODEL,
        "judge_model": judge.model if judge else None,
        "judge_calls": judge.calls if judge else 0,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cases": [r.as_dict() for r in results],
        "summary": summarise(results, min_pass_rate),
        "recordings": [o.as_dict() for o in outcomes],
    }


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
