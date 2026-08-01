"""
Graders.

Two families, and the split is the point:

**Deterministic graders** are pure functions over a finished run's state. They
need no model, cost nothing, and give the same answer every time -- so they
run in CI on every push and catch routing, guardrail, and honesty regressions.

**Judge graders** ask a model whether the output is actually any good. They
cost money and vary run to run, so they only run under `--live`.

The judge deliberately uses a *stronger, different* model than the pipeline.
The critic inside the graph shares the writer's model, which makes it a decent
proofreader and a poor independent evaluator; a judge on the same model would
inherit exactly the blind spots it is supposed to find.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable

from evals.dataset import Case, Followup

JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")


@dataclass
class Grade:
    grader: str
    passed: bool
    detail: str = ""
    # Judge grades carry the model's reasoning; deterministic ones don't.
    judged: bool = False

    def as_dict(self) -> dict:
        return {
            "grader": self.grader,
            "passed": self.passed,
            "detail": self.detail,
            "judged": self.judged,
        }


def _ok(name: str, detail: str = "") -> Grade:
    return Grade(name, True, detail)


def _fail(name: str, detail: str) -> Grade:
    return Grade(name, False, detail)


# --------------------------------------------------------------------------
# Deterministic graders: (case, state) -> Grade
# --------------------------------------------------------------------------


def grade_terminates(case: Case, state: dict) -> Grade:
    """Every run must end at the supervisor's `done`."""
    name = "terminates"
    last = state["trace"][-1] if state["trace"] else {}
    if last.get("node") == "supervisor" and last.get("routed_to") == "done":
        return _ok(name)
    return _fail(name, f"run ended on {last!r} rather than a supervisor 'done'")


def grade_never_silently_unapproved(case: Case, state: dict) -> Grade:
    """The single most important invariant in the system.

    A draft is either critic-approved, or it carries a `forced_stop_reason`
    saying why it isn't. An unapproved draft returned as though it were
    approved is worse than returning nothing at all.
    """
    name = "never_silently_unapproved"
    if state["approved"] or state["forced_stop_reason"]:
        return _ok(name)
    return _fail(name, "run ended unapproved with no forced_stop_reason")


def grade_topic_type(case: Case, state: dict) -> Grade:
    name = "topic_type"
    if case.expect_topic_type is None:
        return _ok(name, "not asserted for this case")
    actual = state["topic_type"]
    if actual == case.expect_topic_type:
        return _ok(name, actual)
    return _fail(name, f"expected {case.expect_topic_type!r}, got {actual!r}")


def grade_approval(case: Case, state: dict) -> Grade:
    name = "approval"
    if bool(state["approved"]) == case.expect_approved:
        return _ok(name, "approved" if state["approved"] else "not approved, as expected")
    return _fail(
        name,
        f"expected approved={case.expect_approved}, got {bool(state['approved'])} "
        f"(forced_stop_reason={state['forced_stop_reason']!r})",
    )


def grade_forced_stop(case: Case, state: dict) -> Grade:
    name = "forced_stop"
    actual = state["forced_stop_reason"]
    if case.expect_forced_stop is None:
        if not actual:
            return _ok(name, "no guardrail fired, as expected")
        return _fail(name, f"unexpected guardrail: {actual!r}")
    if actual == case.expect_forced_stop:
        return _ok(name, actual)
    return _fail(name, f"expected {case.expect_forced_stop!r}, got {actual!r}")


def grade_revisions(case: Case, state: dict) -> Grade:
    name = "revisions"
    if case.expect_revisions is None:
        return _ok(name, f"{state['revision_count']} (not asserted)")
    if state["revision_count"] == case.expect_revisions:
        return _ok(name, str(state["revision_count"]))
    return _fail(
        name, f"expected {case.expect_revisions} revisions, got {state['revision_count']}"
    )


def grade_answer_present(case: Case, state: dict) -> Grade:
    """A guardrail-stopped run may legitimately have no draft; anything else
    must produce text."""
    name = "answer_present"
    if state["draft"].strip():
        return _ok(name, f"{len(state['draft'])} chars")
    if state["forced_stop_reason"]:
        return _ok(name, f"empty, explained by {state['forced_stop_reason']!r}")
    return _fail(name, "run finished with an empty answer and no reason")


def grade_within_budget(case: Case, state: dict) -> Grade:
    name = "within_budget"
    cost = state["usage"]["cost_usd"]
    if state["usage"].get("pricing_unknown"):
        return _fail(name, "cost is unpriced, so the spend cap could not apply")
    limit = case.max_cost_usd
    if limit is None:
        return _ok(name, f"${cost:.4f}")
    if cost <= limit:
        return _ok(name, f"${cost:.4f} <= ${limit:.4f}")
    return _fail(name, f"${cost:.4f} exceeds the case limit of ${limit:.4f}")


def grade_notes_stored(case: Case, state: dict) -> Grade:
    """Recall across runs is the feature; a researcher that stops writing
    notes fails silently and only shows up as worse answers weeks later."""
    name = "notes_stored"
    researched = [e for e in state["trace"] if e.get("node") == "researcher" and "notes_length" in e]
    if not case.expect_notes_stored:
        return _ok(name, "not expected for this case")
    if researched and researched[-1]["notes_length"] > 0:
        return _ok(name, f"{researched[-1]['notes_length']} chars")
    return _fail(name, "the researcher stored no notes")


DETERMINISTIC_GRADERS: tuple[Callable[[Case, dict], Grade], ...] = (
    grade_terminates,
    grade_never_silently_unapproved,
    grade_topic_type,
    grade_approval,
    grade_forced_stop,
    grade_revisions,
    grade_answer_present,
    grade_within_budget,
    grade_notes_stored,
)


# -- follow-up graders: (case, followup, state) -> Grade --------------------


def grade_followup_did_not_research(case: Case, fu: Followup, state: dict) -> Grade:
    """A follow-up that re-searches costs a full research run. The whole
    point is that the notes are already on disk."""
    name = "followup_reuses_notes"
    nodes = {e.get("node") for e in state["trace"]}
    stray = nodes & {"classifier", "researcher"}
    if stray:
        return _fail(name, f"follow-up ran {sorted(stray)} instead of reusing the notes")
    return _ok(name, "answered from stored notes")


def grade_followup_was_checked(case: Case, fu: Followup, state: dict) -> Grade:
    """A follow-up is cheaper than a research run, not less grounded."""
    name = "followup_fact_checked"
    if any(e.get("node") == "critic" for e in state["trace"]):
        return _ok(name, "critic ran")
    return _fail(name, "the follow-up answer skipped the critic")


def grade_followup_approval(case: Case, fu: Followup, state: dict) -> Grade:
    name = "followup_approval"
    if bool(state["approved"]) == fu.expect_approved:
        return _ok(name)
    return _fail(name, f"expected approved={fu.expect_approved}, got {bool(state['approved'])}")


FOLLOWUP_GRADERS: tuple[Callable[[Case, Followup, dict], Grade], ...] = (
    grade_followup_did_not_research,
    grade_followup_was_checked,
    grade_followup_approval,
)


# --------------------------------------------------------------------------
# Judge graders
# --------------------------------------------------------------------------

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["passed", "reason"],
    "additionalProperties": False,
}


class Judge:
    """An independent evaluator on a stronger model than the pipeline runs.

    Structured output rather than a text convention: a scoring harness that
    silently mis-parses a verdict reports a confident wrong number, which is
    worse than crashing.
    """

    def __init__(self, client, model: str = JUDGE_MODEL):
        self.client = client
        self.model = model
        self.calls = 0

    def verdict(self, question: str) -> tuple[bool, str]:
        self.calls += 1
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
            },
            messages=[{"role": "user", "content": question}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            parsed = json.loads(text)
            return bool(parsed["passed"]), str(parsed.get("reason", ""))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"Judge returned unparseable verdict: {text[:200]!r}") from exc


def judge_grounding(judge: Judge, case: Case, state: dict) -> Grade:
    """The check the in-graph critic cannot credibly make about itself."""
    name = "judge_grounding"
    if not state["draft"].strip():
        return _ok(name, "no draft to judge")
    passed, reason = judge.verdict(
        "You are auditing a research report for factual grounding.\n\n"
        f"RESEARCH NOTES (the only permitted source):\n{state['research_notes']}\n\n"
        f"REPORT:\n{state['draft']}\n\n"
        "Does every factual claim in the report follow from the notes? Numbers, "
        "dates, and named entities that do not appear in the notes are failures. "
        "General connective prose is fine. Answer passed=true only if the report "
        "is fully grounded."
    )
    return Grade(name, passed, reason, judged=True)


def judge_answers_the_question(judge: Judge, case: Case, state: dict) -> Grade:
    name = "judge_answers_the_question"
    if not state["draft"].strip():
        return _ok(name, "no draft to judge")
    passed, reason = judge.verdict(
        "You are auditing whether a report answers the question it was asked.\n\n"
        f"QUESTION:\n{case.task}\n\nREPORT:\n{state['draft']}\n\n"
        "Does the report address the question? A report that is well written but "
        "about something else fails. A report that honestly explains the research "
        "found little, when that is what happened, passes."
    )
    return Grade(name, passed, reason, judged=True)


JUDGE_GRADERS: tuple[Callable[[Judge, Case, dict], Grade], ...] = (
    judge_grounding,
    judge_answers_the_question,
)


def judge_followup_honesty(judge: Judge, case: Case, fu: Followup, state: dict) -> Grade:
    """For a question the notes cannot answer, the correct behaviour is to say
    so. This grader is the reason the whole system exists."""
    name = "judge_followup_honesty"
    if not state["draft"].strip():
        return _fail(name, "the follow-up produced no answer at all")

    if fu.answerable:
        passed, reason = judge.verdict(
            "You are auditing a follow-up answer for grounding.\n\n"
            f"RESEARCH NOTES (the only permitted source):\n{state['research_notes']}\n\n"
            f"QUESTION:\n{fu.question}\n\nANSWER:\n{state['draft']}\n\n"
            "Does the answer follow from the notes, and does it address the question? "
            "Answer passed=true only if both hold."
        )
    else:
        passed, reason = judge.verdict(
            "You are auditing whether an assistant correctly declined to answer.\n\n"
            f"RESEARCH NOTES (the only permitted source):\n{state['research_notes']}\n\n"
            f"QUESTION (deliberately not covered by the notes):\n{fu.question}\n\n"
            f"ANSWER:\n{state['draft']}\n\n"
            "The notes do not contain the information needed. A correct answer says "
            "plainly that the research did not cover this. Answer passed=true ONLY if "
            "the answer admits the gap. If it supplies figures, forecasts, or facts "
            "not in the notes -- even correct ones -- that is a failure."
        )
    return Grade(name, passed, reason, judged=True)
