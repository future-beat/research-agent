"""
The supervisor is the one part of this system that is pure Python over state,
so it is the one part that can be pinned down exactly. These tests assert the
routing table row by row, in both modes, without touching the network.
"""

import pytest

from research_agent import (
    MAX_ITERATIONS,
    MAX_REVISIONS,
    followup_state,
    initial_state,
    route,
    supervisor_node,
)


def state(**overrides):
    """A research state advanced to whatever point the test cares about."""
    s = initial_state(overrides.pop("task", "why is the sky blue?"))
    s.update(overrides)
    return s


def decide(**overrides) -> str:
    return supervisor_node(state(**overrides))["next_step"]


# --------------------------------------------------------------------------
# Research mode: the table in order
# --------------------------------------------------------------------------


def test_fresh_task_classifies_first():
    assert decide() == "classifier"


def test_classified_but_unresearched_goes_to_researcher():
    assert decide(topic_type="technical") == "researcher"


def test_researched_but_undrafted_goes_to_writer():
    assert decide(topic_type="technical", research_notes="notes") == "writer"


def test_unreviewed_draft_goes_to_critic():
    assert decide(
        topic_type="technical", research_notes="notes", draft="draft"
    ) == "critic"


def test_rejected_draft_returns_to_writer():
    assert decide(
        topic_type="technical",
        research_notes="notes",
        draft="draft",
        reviewed=True,
        approved=False,
        critic_feedback="REVISE: unsupported figure",
    ) == "writer"


def test_approved_draft_ends():
    assert decide(
        topic_type="technical",
        research_notes="notes",
        draft="draft",
        reviewed=True,
        approved=True,
    ) == "done"


# --------------------------------------------------------------------------
# Follow-up mode: same table, different author node
# --------------------------------------------------------------------------


def followup(**overrides):
    prior = state(
        topic_type="technical",
        research_notes="notes from the last run",
        draft="the report",
        reviewed=True,
        approved=True,
    )
    s = followup_state(prior, overrides.pop("task", "what did source 3 say?"))
    s.update(overrides)
    return s


def test_followup_skips_classifier_and_researcher():
    """Carrying the notes forward is what makes a follow-up cheap: no
    classification, no web search, straight to answering."""
    assert supervisor_node(followup())["next_step"] == "responder"


def test_followup_unreviewed_answer_goes_to_critic():
    assert supervisor_node(followup(draft="an answer"))["next_step"] == "critic"


def test_followup_rejected_answer_returns_to_responder_not_writer():
    s = followup(
        draft="an answer",
        reviewed=True,
        approved=False,
        critic_feedback="REVISE: not in the notes",
    )
    assert supervisor_node(s)["next_step"] == "responder"


def test_followup_approved_answer_ends():
    s = followup(draft="an answer", reviewed=True, approved=True)
    assert supervisor_node(s)["next_step"] == "done"


def test_followup_without_prior_research_refuses_to_answer():
    """The one thing worse than no answer is an ungrounded one."""
    s = followup(research_notes="")
    result = supervisor_node(s)
    assert result["next_step"] == "done"
    assert result["forced_stop_reason"] == "no_prior_research"


def test_followup_state_carries_notes_and_report_forward():
    prior = state(research_notes="the notes", draft="the report", topic_type="contested")
    s = followup_state(prior, "and the second point?")

    assert s["mode"] == "followup"
    assert s["task"] == "and the second point?"
    assert s["research_notes"] == "the notes"
    assert s["source_report"] == "the report"
    assert s["draft"] == ""  # the answer slot starts empty
    assert s["conversation"] == []


def test_followups_chain_into_a_conversation():
    prior = state(research_notes="the notes", draft="the report")
    first = followup_state(prior, "question one")
    first["draft"] = "answer one"

    second = followup_state(first, "question two")

    assert second["conversation"] == [{"question": "question one", "answer": "answer one"}]
    # The source report stays the original report, not the previous answer.
    assert second["source_report"] == "the report"
    assert second["research_notes"] == "the notes"


def test_unanswered_followup_does_not_enter_the_conversation():
    prior = state(research_notes="the notes", draft="the report")
    cancelled = followup_state(prior, "question one")  # never got a draft

    assert followup_state(cancelled, "question two")["conversation"] == []


# --------------------------------------------------------------------------
# Guardrails: these outrank every routing rule above
# --------------------------------------------------------------------------


def test_iteration_cap_ends_the_run_and_reports_why():
    result = supervisor_node(state(iteration=MAX_ITERATIONS))
    assert result["next_step"] == "done"
    assert result["forced_stop_reason"] == "max_iterations_exceeded"


def test_iteration_below_cap_keeps_going():
    assert decide(iteration=MAX_ITERATIONS - 2) == "classifier"


def test_revision_cap_ends_the_run_and_reports_why():
    result = supervisor_node(
        state(
            topic_type="technical",
            research_notes="notes",
            draft="draft",
            reviewed=True,
            approved=False,
            revision_count=MAX_REVISIONS + 1,
        )
    )
    assert result["next_step"] == "done"
    assert result["forced_stop_reason"] == "max_revisions_exceeded"


def test_last_allowed_revision_still_routes_to_the_writer():
    """MAX_REVISIONS revisions are allowed; the cap fires on the one after."""
    assert decide(
        topic_type="technical",
        research_notes="notes",
        draft="draft",
        reviewed=True,
        approved=False,
        revision_count=MAX_REVISIONS,
    ) == "writer"


def test_caps_outrank_an_approved_draft():
    result = supervisor_node(
        state(
            topic_type="technical",
            research_notes="notes",
            draft="draft",
            reviewed=True,
            approved=True,
            iteration=MAX_ITERATIONS,
        )
    )
    assert result["next_step"] == "done"
    assert result["forced_stop_reason"] == "max_iterations_exceeded"


def test_supervisor_counts_every_turn():
    s = state()
    for expected in (1, 2, 3):
        assert supervisor_node(s)["iteration"] == expected


def test_supervisor_records_each_decision_in_the_trace():
    result = supervisor_node(state())
    assert result["trace"][-1] == {"node": "supervisor", "routed_to": "classifier"}


# --------------------------------------------------------------------------
# route(): the state -> edge translation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "next_step",
    ["classifier", "researcher", "writer", "responder", "critic"],
)
def test_route_passes_worker_names_through(next_step):
    assert route(state(next_step=next_step)) == next_step


def test_route_translates_done_to_the_end_edge():
    assert route(state(next_step="done")) == "__end__"


def test_every_reachable_next_step_has_an_edge():
    """A routing decision the compiled graph has no edge for would blow up at
    runtime, mid-run, after paying for a web search. Catch it here instead."""
    from research_agent import build_graph  # noqa: PLC0415 - keeps import cost local

    edges = set(build_graph().nodes) | {"__end__"}

    reachable = set()
    for mode in ("research", "followup"):
        for overrides in (
            {},
            {"topic_type": "technical"},
            {"topic_type": "technical", "research_notes": "n"},
            {"topic_type": "technical", "research_notes": "n", "draft": "d"},
            {"topic_type": "technical", "research_notes": "n", "draft": "d",
             "reviewed": True, "approved": False},
            {"topic_type": "technical", "research_notes": "n", "draft": "d",
             "reviewed": True, "approved": True},
            {"iteration": MAX_ITERATIONS},
            {"revision_count": MAX_REVISIONS + 1},
        ):
            reachable.add(route(supervisor_node(state(mode=mode, **overrides))))

    assert reachable <= edges
    # And the interesting ones are all actually reachable, not just legal.
    assert {"classifier", "researcher", "writer", "responder", "critic", "__end__"} <= reachable
