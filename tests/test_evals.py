"""
Tests for the eval harness.

An eval suite is only worth its exit code if the harness is itself correct: a
grader that can't fail, a summary that rounds a regression away, or a runner
that reports success on zero cases would all make CI green through a bug.
"""

import json

import pytest

from evals import fixtures as F
from evals import graders as G
from evals.__main__ import main
from evals.dataset import GOLDEN, Case, Followup, by_id, select
from evals.harness import (
    CaseResult,
    HashEmbedder,
    ScriptedClient,
    TurnResult,
    offline_client_factory,
    offline_memory_factory,
    run_case,
    run_suite,
    summarise,
)
from research_agent import graph
from research_agent.graph import initial_state


def finished(**overrides) -> dict:
    state = initial_state(overrides.pop("task", "why?"))
    state.update(
        {
            "topic_type": "technical",
            "research_notes": "FACTS: the sky scatters blue light.",
            "draft": "# Report\n\nThe sky scatters blue light.",
            "approved": True,
            "reviewed": True,
            "trace": [
                {"node": "researcher", "notes_length": 40, "recalled_from_memory": 0},
                {"node": "critic", "approved": True},
                {"node": "supervisor", "routed_to": "done"},
            ],
        }
    )
    state.update(overrides)
    return state


CASE = Case(id="t", task="why?", why="because", expect_topic_type="technical")


# --------------------------------------------------------------------------
# The dataset
# --------------------------------------------------------------------------


def test_case_ids_are_unique():
    ids = [case.id for case in GOLDEN]
    assert len(ids) == len(set(ids))


def test_every_case_explains_what_regressing_it_costs():
    """`why` is printed next to a failure. A case nobody can justify is a
    case nobody will fix."""
    for case in GOLDEN:
        assert len(case.why) > 30, case.id


def test_the_dataset_covers_every_topic_type():
    covered = {case.expect_topic_type for case in GOLDEN}
    assert {"technical", "contested", "sparse", "general"} <= covered


def test_the_dataset_covers_both_guardrails():
    stops = {case.expect_forced_stop for case in GOLDEN if case.expect_forced_stop}
    assert stops == {"max_revisions_exceeded", "budget_exceeded"}


def test_the_dataset_covers_an_unanswerable_followup():
    """The refusal case is the point of the whole pipeline; losing it from
    the dataset would be the quietest possible regression."""
    assert any(
        not fu.answerable for case in GOLDEN for fu in case.followups
    ), "no case checks that an uncovered follow-up is refused"


def test_select_returns_everything_by_default():
    assert select() == GOLDEN


def test_select_picks_named_cases_in_order():
    assert [c.id for c in select(["followups-chain", "general-summary"])] == [
        "followups-chain",
        "general-summary",
    ]


def test_selecting_an_unknown_case_raises():
    with pytest.raises(KeyError):
        by_id("no-such-case")


# --------------------------------------------------------------------------
# Deterministic graders
# --------------------------------------------------------------------------


def test_a_clean_run_passes_every_deterministic_grader():
    grades = [grader(CASE, finished()) for grader in G.DETERMINISTIC_GRADERS]
    assert all(g.passed for g in grades), [g for g in grades if not g.passed]


def test_the_silent_unapproved_draft_is_caught():
    """The invariant that matters most: unapproved and unexplained."""
    grade = G.grade_never_silently_unapproved(
        CASE, finished(approved=False, forced_stop_reason="")
    )
    assert not grade.passed


def test_an_unapproved_draft_with_a_reason_is_fine():
    grade = G.grade_never_silently_unapproved(
        CASE, finished(approved=False, forced_stop_reason="max_revisions_exceeded")
    )
    assert grade.passed


def test_a_wrong_topic_type_is_caught():
    grade = G.grade_topic_type(CASE, finished(topic_type="general"))
    assert not grade.passed
    assert "technical" in grade.detail


def test_an_unexpected_guardrail_is_caught():
    """A run that silently stopped early still produced *an* answer; without
    this grader it would look like a pass."""
    grade = G.grade_forced_stop(CASE, finished(forced_stop_reason="budget_exceeded"))
    assert not grade.passed


def test_a_missing_expected_guardrail_is_caught():
    case = Case(id="t", task="x", why="y" * 40, expect_forced_stop="budget_exceeded")
    assert not G.grade_forced_stop(case, finished()).passed


def test_a_run_that_did_not_terminate_is_caught():
    state = finished()
    state["trace"] = [{"node": "supervisor", "routed_to": "writer"}]
    assert not G.grade_terminates(CASE, state).passed


def test_an_empty_answer_is_only_acceptable_with_a_reason():
    assert not G.grade_answer_present(CASE, finished(draft="")).passed
    assert G.grade_answer_present(
        CASE, finished(draft="", forced_stop_reason="budget_exceeded")
    ).passed


def test_unpriced_cost_fails_the_budget_grader():
    """If cost is unpriced the spend cap cannot fire, so "within budget" is
    unknowable -- reporting a pass would be a guess."""
    state = finished()
    state["usage"]["pricing_unknown"] = True
    assert not G.grade_within_budget(CASE, state).passed


def test_exceeding_a_case_cost_limit_is_caught():
    case = Case(id="t", task="x", why="y" * 40, max_cost_usd=0.01)
    state = finished()
    state["usage"]["cost_usd"] = 0.5
    assert not G.grade_within_budget(case, state).passed


def test_a_researcher_that_stored_nothing_is_caught():
    state = finished()
    state["trace"] = [
        {"node": "researcher", "notes_length": 0},
        {"node": "supervisor", "routed_to": "done"},
    ]
    assert not G.grade_notes_stored(CASE, state).passed


# -- follow-up graders ------------------------------------------------------


FU = Followup(question="and?")


def followup_state_dict(**overrides) -> dict:
    state = finished(**overrides)
    state["mode"] = "followup"
    return state


def test_a_followup_that_researched_again_is_caught():
    state = followup_state_dict()
    state["trace"] = [{"node": "researcher", "notes_length": 10}, {"node": "critic"}]
    grade = G.grade_followup_did_not_research(CASE, FU, state)
    assert not grade.passed
    assert "researcher" in grade.detail


def test_a_followup_that_skipped_the_critic_is_caught():
    """Cheaper than a research run, not less grounded."""
    state = followup_state_dict()
    state["trace"] = [{"node": "responder", "answer_length": 10}]
    assert not G.grade_followup_was_checked(CASE, FU, state).passed


def test_a_clean_followup_passes_every_grader():
    state = followup_state_dict()
    state["trace"] = [{"node": "responder", "answer_length": 10}, {"node": "critic"}]
    assert all(g.passed for g in (grader(CASE, FU, state) for grader in G.FOLLOWUP_GRADERS))


# --------------------------------------------------------------------------
# The judge
# --------------------------------------------------------------------------


class FakeJudgeClient:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.prompts = []
        self.messages = self

    def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])

        class Block:
            type = "text"

            def __init__(self, text):
                self.text = text

        class Response:
            def __init__(self, text):
                self.content = [Block(text)]

        return Response(self.payloads.pop(0))


def test_judge_parses_a_structured_verdict():
    judge = G.Judge(FakeJudgeClient('{"passed": true, "reason": "grounded"}'))
    assert judge.verdict("check this") == (True, "grounded")
    assert judge.calls == 1


def test_judge_raises_on_an_unparseable_verdict():
    """Silently scoring a malformed verdict as a pass would make the suite
    report a confident wrong number."""
    judge = G.Judge(FakeJudgeClient("I think it's fine, honestly"))
    with pytest.raises(ValueError, match="unparseable"):
        judge.verdict("check this")


def test_the_judge_runs_on_a_different_model_than_the_pipeline():
    """A judge sharing the writer's model inherits the blind spots it exists
    to find -- the same limitation the in-graph critic already has."""

    assert G.JUDGE_MODEL != graph.MODEL


def test_grounding_judge_is_given_the_notes_and_the_draft():
    client = FakeJudgeClient('{"passed": false, "reason": "invented a figure"}')
    grade = G.judge_grounding(G.Judge(client), CASE, finished())

    assert not grade.passed
    assert grade.judged is True
    assert "the sky scatters blue light" in client.prompts[0]
    assert "# Report" in client.prompts[0]


def test_the_refusal_judge_is_told_the_question_is_uncovered():
    """The unanswerable branch has to grade the opposite of the normal one:
    supplying a correct fact is a failure here."""
    client = FakeJudgeClient('{"passed": true, "reason": "admitted the gap"}')
    fu = Followup(question="what did Gartner forecast?", answerable=False)

    G.judge_followup_honesty(G.Judge(client), CASE, fu, finished())

    prompt = client.prompts[0]
    assert "declined" in prompt
    assert "even correct ones" in prompt


def test_the_refusal_judge_fails_an_empty_answer():
    fu = Followup(question="?", answerable=False)
    grade = G.judge_followup_honesty(G.Judge(FakeJudgeClient()), CASE, fu, finished(draft=""))
    assert not grade.passed


# --------------------------------------------------------------------------
# The scripted client
# --------------------------------------------------------------------------


def test_the_scripted_client_dispatches_on_the_real_prompts():
    """Nodes are recognised by their prompts, so rewriting a prompt beyond
    recognition fails the evals instead of silently passing."""
    case = by_id("revision-then-approval")
    client = ScriptedClient(case)

    run_case(case, client_factory=lambda c: client, memory_factory=offline_memory_factory)

    assert client.calls == ["classifier", "researcher", "writer", "critic", "writer", "critic"]


def test_the_hash_embedder_is_deterministic_and_shaped_right():
    embedder = HashEmbedder()
    assert embedder.embed_query("langgraph state graph") == embedder.embed_query(
        "langgraph state graph"
    )
    assert len(embedder.embed_documents(["x"])[0]) == HashEmbedder.DIMENSIONS


def test_the_hash_embedder_never_returns_a_zero_vector():
    """A zero vector makes cosine similarity undefined."""
    assert any(HashEmbedder().embed_query(""))


# --------------------------------------------------------------------------
# Running cases and summarising
# --------------------------------------------------------------------------


def test_running_a_case_grades_every_turn():
    result = run_case(
        by_id("followups-chain"),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
    )

    assert result.passed, result.failures
    assert [t.label for t in result.turns][0] == "research"
    assert len(result.turns) == 3  # research + two follow-ups


def test_a_case_that_raises_is_recorded_not_propagated():
    """One broken case must not take the suite down with it."""
    def explode(case):
        raise RuntimeError("client is on fire")

    result = run_case(
        by_id("general-summary"),
        client_factory=explode,
        memory_factory=offline_memory_factory,
    )

    assert not result.passed
    assert "RuntimeError" in result.error


def test_run_case_restores_the_global_client_and_memory():
    """The harness swaps module globals; leaking them would poison every
    test that runs afterwards."""

    before = (graph._client, graph._memory)
    run_case(
        by_id("general-summary"),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
    )
    assert (graph._client, graph._memory) == before


def test_the_budget_override_is_scoped_to_its_case(monkeypatch):
    """The guardrail case sets a tiny budget; leaking it would fail every
    case that ran after it."""
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "5.00")
    run_case(
        by_id("budget-cap-is-labelled"),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
    )
    import os

    assert os.environ["AGENT_MAX_RUN_COST_USD"] == "5.00"


def passing(case_id="a") -> CaseResult:
    return CaseResult(case_id, "why", [TurnResult("research", [G.Grade("g", True)])])


def failing(case_id="b") -> CaseResult:
    return CaseResult(case_id, "why", [TurnResult("research", [G.Grade("g", False, "nope")])])


def test_summary_counts_and_rates():
    summary = summarise([passing("a"), passing("b"), failing("c")], min_pass_rate=0.5)
    assert (summary["cases"], summary["passed"], summary["failed"]) == (3, 2, 1)
    assert summary["pass_rate"] == pytest.approx(0.6667, abs=1e-4)
    assert summary["ok"] is True


def test_summary_fails_below_the_threshold():
    assert summarise([passing(), failing()], min_pass_rate=0.9)["ok"] is False


def test_a_pass_rate_exactly_at_the_threshold_passes():
    assert summarise([passing(), failing()], min_pass_rate=0.5)["ok"] is True


def test_an_empty_suite_is_not_a_pass():
    """A broken --case selector must not produce a green build."""
    summary = summarise([], min_pass_rate=0.9)
    assert summary["ok"] is False
    assert summary["cases"] == 0


def test_summary_breaks_results_down_by_grader():
    summary = summarise([passing(), failing()], min_pass_rate=0.0)
    assert summary["by_grader"]["g"] == {"passed": 1, "failed": 1}


def test_the_whole_offline_suite_passes():
    """The suite that CI runs. If this fails, something in the pipeline
    regressed -- read the failing grader, not this test."""
    report = run_suite(
        GOLDEN,
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
        min_pass_rate=1.0,
    )
    failures = {
        c["case_id"]: [g for t in c["turns"] for g in t["grades"] if not g["passed"]]
        for c in report["cases"]
        if not c["passed"]
    }
    assert report["summary"]["ok"], failures


def test_the_report_is_json_serialisable():
    """It is written to a file and read by CI; an unserialisable field would
    only surface at the end of a live run that cost real money."""
    report = run_suite(
        select(["general-summary"]),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
    )
    assert json.loads(json.dumps(report))["summary"]["cases"] == 1


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_cli_exits_zero_when_the_suite_passes(capsys):
    assert main(["--quiet"]) == 0


def test_cli_exits_nonzero_when_the_threshold_is_not_met(monkeypatch, capsys):
    """The exit code is the whole contract with CI."""
    monkeypatch.setattr(
        "evals.__main__.run_suite",
        lambda *a, **k: {"summary": {"ok": False, "passed": 3, "cases": 12,
                                     "pass_rate": 0.25, "min_pass_rate": 0.9,
                                     "cost_usd": 0.0, "duration_ms": 0.0},
                         "judge_calls": 0},
    )
    assert main(["--quiet"]) == 1


def test_cli_rejects_an_unknown_case_rather_than_running_nothing(capsys):
    assert main(["--case", "no-such-case"]) == 2
    assert "no-such-case" in capsys.readouterr().err


def test_cli_writes_the_report(tmp_path, capsys):
    path = tmp_path / "report.json"
    main(["--case", "general-summary", "--quiet", "--report", str(path)])

    report = json.loads(path.read_text())
    assert report["mode"] == "offline"
    assert report["judge_model"] is None  # no judge offline
    assert len(report["cases"]) == 1


def test_cli_says_offline_mode_does_not_measure_the_model(capsys):
    """The one thing a reader must not conclude from a green offline run."""
    main(["--quiet"])
    assert "not the model" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

MODELS = {"pipeline": graph.MODEL, "judge": G.JUDGE_MODEL}


def recorded(*turns: TurnResult) -> CaseResult:
    """A CaseResult shaped like one `run_case(capture_state=True)` returns."""
    return CaseResult("t", "why", list(turns))


def captured(label="research", grades=(), **state_overrides) -> TurnResult:
    return TurnResult(label, list(grades), state=finished(**state_overrides))


def test_fixture_roundtrip(tmp_path):
    """Serialise, deserialise, and get the same state back.

    AgentState is JSON-safe by construction -- it is already persisted as
    JSON between a run and its follow-ups -- and this pins that, because a
    lossy round-trip would grade something subtly different from what ran."""
    state = finished(task="why is the sky blue?")
    result = recorded(TurnResult("research", [G.Grade("terminates", True)], state=state))

    fixture = F.build_fixture("t", result, models=MODELS)
    path = F.write_fixture(fixture, result, directory=tmp_path)
    loaded = F.load_fixture(path)

    assert path.name == "t.json"
    assert loaded["turns"][0]["state"] == state
    assert loaded["schema_version"] == F.SCHEMA_VERSION
    assert loaded["case_id"] == "t"
    assert loaded["git_sha"]


def test_a_fixture_records_a_models_map_not_a_flat_model_string(tmp_path):
    """Phase 16 makes the critic's model configurable independently of
    `graph.MODEL`. A flat `"model"` string would keep matching after that
    change and let the recordings go stale invisibly; a map takes new roles
    without a schema bump."""
    result = recorded(captured())
    models = {**MODELS, "critic": "claude-haiku-5"}

    loaded = F.load_fixture(
        F.write_fixture(F.build_fixture("t", result, models=models), result, directory=tmp_path)
    )

    assert loaded["models"] == models
    assert "model" not in loaded


def test_recorder_refuses_failed_judge(tmp_path):
    """A committed fixture is by construction one the judge approved -- which
    is the only reason replay asserting those verdicts is a real gate."""
    result = recorded(
        TurnResult(
            "research",
            [
                G.Grade("terminates", True),
                G.Grade("judge_grounding", passed=False, detail="ungrounded", judged=True),
            ],
            state=finished(),
        )
    )
    fixture = F.build_fixture("t", result, models=MODELS)

    with pytest.raises(F.FixtureError, match="judge_grounding"):
        F.write_fixture(fixture, result, directory=tmp_path)
    assert list(tmp_path.glob("*.json")) == [], "a refused recording must leave no file"

    path = F.write_fixture(fixture, result, directory=tmp_path, force=True)
    assert json.loads(path.read_text())["forced"] is True


def test_recorder_refuses_failed_deterministic_grade(tmp_path):
    result = recorded(
        TurnResult("research", [G.Grade("approval", False, "expected approved")], state=finished())
    )
    fixture = F.build_fixture("t", result, models=MODELS)

    with pytest.raises(F.FixtureError, match="approval"):
        F.write_fixture(fixture, result, directory=tmp_path)


def test_recorder_refuses_a_run_that_errored(tmp_path):
    result = CaseResult("t", "why", [captured()], error="RuntimeError: client is on fire")
    fixture = F.build_fixture("t", result, models=MODELS)

    with pytest.raises(F.FixtureError, match="errored"):
        F.write_fixture(fixture, result, directory=tmp_path)


def test_a_malformed_fixture_fails_loudly(tmp_path):
    """The dangerous fixture is not a hostile one, it is a plausible one: a
    truncated write or a botched edit that loads as a half-empty dict and
    grades vacuously green."""
    result = recorded(captured())
    good = F.build_fixture("t", result, models=MODELS)

    variants = {
        "missing-models": {k: v for k, v in good.items() if k != "models"},
        "future-schema": {**good, "schema_version": 2},
        "no-pipeline-role": {**good, "models": {"judge": G.JUDGE_MODEL}},
        "empty-turns": {**good, "turns": []},
        "state-is-a-string": {**good, "turns": [{"label": "research", "state": "", "judge": []}]},
    }

    for name, payload in variants.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(F.FixtureError) as caught:
            F.load_fixture(path)
        assert name in str(caught.value), f"{name}: the error should name the file"


def test_a_truncated_fixture_fails_loudly(tmp_path):
    path = tmp_path / "t.json"
    path.write_text('{"schema_version": 1, "case_id": "t", "turns": [')
    with pytest.raises(F.FixtureError, match="not valid JSON"):
        F.load_fixture(path)


def test_fixture_size_guard_rejects_a_runaway_draft(tmp_path):
    """A megabyte-scale draft is a bug in the pipeline worth seeing, not a
    recording worth committing."""
    result = recorded(captured(draft="x" * 300_000))
    fixture = F.build_fixture("t", result, models=MODELS)

    with pytest.raises(F.FixtureError, match="bytes"):
        F.write_fixture(fixture, result, directory=tmp_path)
    assert list(tmp_path.glob("*.json")) == []


def test_a_large_fixture_warns_but_still_writes(tmp_path, capsys):
    result = recorded(captured(draft="x" * 150_000))
    fixture = F.build_fixture("t", result, models=MODELS)

    path = F.write_fixture(fixture, result, directory=tmp_path)

    assert path.exists()
    assert "warning" in capsys.readouterr().err


def test_build_fixture_refuses_a_recording_that_captured_nothing():
    """Recording without `capture_state=True` would write an empty file that
    replay would then grade against nothing."""
    with pytest.raises(F.FixtureError, match="captured no state"):
        F.build_fixture("t", recorded(TurnResult("research", [])), models=MODELS)


def test_build_fixture_requires_the_pipeline_and_judge_models():
    result = recorded(captured())
    with pytest.raises(F.FixtureError, match="pipeline"):
        F.build_fixture("t", result, models={"judge": G.JUDGE_MODEL})


def test_a_fixture_records_the_judge_verdicts_and_not_the_deterministic_ones():
    """Judge verdicts cost money once and replay free forever; deterministic
    grades are recomputed from the recorded state, so storing them would only
    create a second source of truth."""
    result = recorded(
        TurnResult(
            "research",
            [
                G.Grade("terminates", True),
                G.Grade("judge_grounding", True, "grounded", judged=True),
            ],
            state=finished(),
        )
    )

    fixture = F.build_fixture("t", result, models=MODELS)

    assert [g["grader"] for g in fixture["turns"][0]["judge"]] == ["judge_grounding"]


def test_fixture_paths_is_empty_before_any_recording(tmp_path):
    """The pre-recording state of the repo is not an error -- replay simply
    has nothing to grade yet."""
    assert F.fixture_paths(tmp_path / "never-recorded") == []


def test_fixture_paths_reads_the_module_directory_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "FIXTURES_DIR", tmp_path)
    (tmp_path / "b.json").write_text("{}")
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "notes.txt").write_text("not a fixture")

    assert [p.name for p in F.fixture_paths()] == ["a.json", "b.json"]


def test_git_sha_falls_back_to_unknown(monkeypatch):
    """Metadata, never a gate: a recording made without git still records,
    and says plainly that it does not know its commit."""

    def explode(*args, **kwargs):
        raise OSError("no git on this machine")

    monkeypatch.setattr(F.subprocess, "run", explode)
    assert F.git_sha() == "unknown"


def test_git_sha_falls_back_when_git_says_nothing(monkeypatch):
    class Empty:
        stdout = "\n"

    monkeypatch.setattr(F.subprocess, "run", lambda *a, **k: Empty())
    assert F.git_sha() == "unknown"


# --------------------------------------------------------------------------
# The recorder seam
# --------------------------------------------------------------------------

# The fields the graders read off a recorded state. If a future state shape
# drops one of these, replay would grade against a hole rather than fail.
GRADED_STATE_KEYS = (
    "task", "mode", "topic_type", "research_notes", "draft", "approved",
    "forced_stop_reason", "revision_count", "usage", "trace",
)


def test_recorder_captures_schema(tmp_path):
    """The seam and the fixture layer, proven together against the FAKE
    client -- no network, no key, no spend. This is the whole recorder
    mechanism minus the money."""
    case = by_id("followup-uses-prior-notes")

    result = run_case(
        case,
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
        capture_state=True,
    )

    assert result.passed, result.failures
    assert len(result.turns) == 2  # research + one follow-up
    for turn in result.turns:
        assert turn.state is not None, turn.label
        missing = [k for k in GRADED_STATE_KEYS if k not in turn.state]
        assert not missing, f"{turn.label}: recorded state is missing {missing}"

    fixture = F.build_fixture(case.id, result, models=MODELS)
    loaded = F.load_fixture(F.write_fixture(fixture, result, directory=tmp_path))

    assert [t["label"] for t in loaded["turns"]] == ["research", case.followups[0].question]
    assert loaded["turns"][0]["state"]["draft"] == result.turns[0].state["draft"]
    assert loaded["turns"][1]["state"]["mode"] == "followup"
    assert loaded["models"]["pipeline"] == graph.MODEL


def test_each_captured_turn_is_its_own_state():
    result = run_case(
        by_id("followups-chain"),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
        capture_state=True,
    )

    states = [t.state for t in result.turns]
    assert len({id(s) for s in states}) == len(states)
    assert len({s["draft"] for s in states}) == len(states)


def test_a_captured_state_survives_a_driver_that_reuses_one_dict(monkeypatch):
    """The capture is a copy taken at append time.

    `graph.app.invoke` returns a fresh dict per turn today, so no test
    against the real graph can tell a copy from an alias -- which is exactly
    why this one fakes a driver that reuses one. An aliasing capture would
    record the last turn's answer for every turn: a fixture that looks
    complete and is silently one answer repeated."""
    drafts = iter(["# Turn one", "# Turn two"])
    shared = finished()

    class ReusesOneDict:
        def invoke(self, state):
            shared["draft"] = next(drafts)
            return shared

    monkeypatch.setattr(graph, "app", ReusesOneDict())

    result = run_case(
        by_id("followup-uses-prior-notes"),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
        capture_state=True,
    )

    assert not result.error
    assert [t.state["draft"] for t in result.turns] == ["# Turn one", "# Turn two"]


def _without_durations(result: CaseResult) -> dict:
    """Wall-clock timings differ between any two runs; everything else in the
    report must not."""
    payload = result.as_dict()
    for turn in payload["turns"]:
        turn.pop("duration_ms")
    return payload


def test_capture_state_default_leaves_results_unchanged():
    """Every existing caller passes nothing. The report shape, the grades and
    the costs must be exactly what they were before the seam existed."""
    case = by_id("followup-uses-prior-notes")
    kwargs = {
        "client_factory": offline_client_factory,
        "memory_factory": offline_memory_factory,
    }

    plain = run_case(case, **kwargs)
    capturing = run_case(case, capture_state=True, **kwargs)

    assert _without_durations(plain) == _without_durations(capturing)
    assert all(t.state is None for t in plain.turns)
    assert "state" not in plain.as_dict()["turns"][0]


def test_a_captured_state_is_not_written_into_the_report():
    """States are tens of KB each; the report is read by humans and CI, and
    the fixture file is a recorded state's home."""
    result = run_case(
        by_id("general-summary"),
        client_factory=offline_client_factory,
        memory_factory=offline_memory_factory,
        capture_state=True,
    )

    assert result.turns[0].state is not None
    assert "state" not in result.turns[0].as_dict()
    assert "research_notes" not in json.dumps(result.as_dict())
