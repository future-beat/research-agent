"""
The supervisor is the one part of this system that is pure Python over state,
so it is the one part that can be pinned down exactly. These tests assert the
routing table row by row, in both modes, without touching the network.
"""

import pytest

from research_agent.graph import (
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


def test_followup_no_notes_routes_to_researcher():
    """The reversal (Phase 17, path 1).

    A follow-up with nothing behind it used to END with `no_prior_research`,
    on the reasoning that refusing beat answering from the model's own
    knowledge. Both are still true of *answering*; neither was ever an
    argument against going and getting notes first. So the row keeps its
    place and changes its destination.

    Everything asserted here except `next_step` is a side effect, deliberately:
    the generic `not research_notes -> researcher` row below routes this same
    state to the same node, so a swapped or deleted row is invisible to a
    destination assertion. The trace event, the flag and the empty stop reason
    are what say *this* row decided it.
    """
    s = followup(research_notes="")
    result = supervisor_node(s)

    assert result["next_step"] == "researcher"
    assert result["forced_stop_reason"] == ""
    assert result["followup_research_done"] is True
    assert result["trace"][-1] == {
        "node": "supervisor",
        "routed_to": "researcher",
        "followup_research": "no_prior_research",
    }


def test_a_fresh_run_has_reached_for_nothing_yet():
    s = initial_state("why?")
    assert s["notes_insufficient"] is False
    assert s["followup_research_done"] is False


def test_every_followup_turn_gets_its_own_research_allowance():
    """The one-pass bound is per TURN, and that is the design, not a leak.

    A follow-up turn is a new run with its own run_id, its own budget and its
    own reservation; it gets a fresh pass allowance on the same reasoning. The
    flags come from `initial_state`, which `followup_state` builds on -- so
    even a previous turn that spent its pass hands the next one a clean slate,
    and nothing is read off `previous` (a state blob written before this phase
    has neither key).
    """
    prior = state(research_notes="notes", draft="report")
    prior.update({"notes_insufficient": True, "followup_research_done": True})

    s = followup_state(prior, "and?")
    assert s["notes_insufficient"] is False
    assert s["followup_research_done"] is False

    legacy = {k: v for k, v in prior.items()
              if k not in ("notes_insufficient", "followup_research_done")}
    fresh = followup_state(legacy, "and?")
    assert fresh["notes_insufficient"] is False
    assert fresh["followup_research_done"] is False


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


def test_a_run_carries_the_owner_its_notes_belong_to():
    """The state half of the note-scoping thread (Phase 12).

    `owner` has to survive into the state dict, because researcher_node reads
    it from there and nowhere else. The default is "" rather than absent: the
    REPL and the eval harness construct runs with no caller, and "" is a real
    owner value that matches nobody rather than a wildcard that matches all.
    """
    assert initial_state("why?", owner="alice")["owner"] == "alice"
    assert initial_state("why?")["owner"] == ""

    # A follow-up belongs to whoever is asking it...
    prior = initial_state("why?", owner="alice")
    assert followup_state(prior, "and?", owner="bob")["owner"] == "bob"
    # ...and carries the previous turn's owner forward when nobody is named,
    # which is what keeps REPL chaining working.
    assert followup_state(prior, "and?")["owner"] == "alice"

    # A session state blob written before Phase 12 has no owner key at all.
    # Reading it must not raise: that state is a live row in production.
    legacy = {k: v for k, v in prior.items() if k != "owner"}
    assert followup_state(legacy, "and?")["owner"] == ""


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
    from research_agent.graph import build_graph  # noqa: PLC0415 - keeps import cost local

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


# --------------------------------------------------------------------------
# Budget guardrail
# --------------------------------------------------------------------------


def spent(amount: float, **overrides):
    s = state(**overrides)
    s["usage"]["cost_usd"] = amount
    return s


def test_exceeding_the_budget_ends_the_run(monkeypatch):
    """The iteration and revision caps bound how many calls a run makes;
    this bounds what they cost."""
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.50")
    result = supervisor_node(spent(0.51, topic_type="technical", research_notes="n"))

    assert result["next_step"] == "done"
    assert result["forced_stop_reason"] == "budget_exceeded"


def test_spending_up_to_the_budget_keeps_going(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.50")
    assert supervisor_node(
        spent(0.50, topic_type="technical", research_notes="n")
    )["next_step"] == "writer"


def test_a_zero_budget_disables_the_cap(monkeypatch):
    """An explicit opt-out, distinct from "spend nothing" -- which would make
    every run stop before its first node."""
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0")
    assert supervisor_node(
        spent(99.0, topic_type="technical", research_notes="n")
    )["next_step"] == "writer"


def test_the_budget_stops_a_followup_too(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.10")
    s = spent(0.20, mode="followup", topic_type="technical", research_notes="n")
    assert supervisor_node(s)["forced_stop_reason"] == "budget_exceeded"


def test_the_iteration_cap_still_outranks_the_budget(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.10")
    result = supervisor_node(spent(99.0, iteration=MAX_ITERATIONS))
    assert result["forced_stop_reason"] == "max_iterations_exceeded"


def test_an_unpriced_model_does_not_silently_disable_the_budget(monkeypatch):
    """cost_usd stays 0 when pricing is unknown, so the cap cannot fire --
    `pricing_unknown` is the flag that says the number is a floor, not a total."""
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.10")
    s = state(topic_type="technical", research_notes="n")
    s["usage"]["pricing_unknown"] = True

    assert supervisor_node(s)["next_step"] == "writer"
    assert s["usage"]["pricing_unknown"] is True


def test_a_fresh_run_starts_with_a_run_id_and_empty_usage():
    s = state()
    assert s["run_id"]
    assert s["usage"]["cost_usd"] == 0.0
    assert s["usage"]["calls"] == 0


def test_each_run_gets_its_own_run_id():
    assert initial_state("a")["run_id"] != initial_state("b")["run_id"]


def test_a_followup_is_a_new_run_with_its_own_id_and_budget():
    """Follow-ups are separately budgeted: a long conversation shouldn't
    inherit the spend of the research run it started from."""
    prior = state(research_notes="notes", draft="report")
    prior["usage"]["cost_usd"] = 0.90

    s = followup_state(prior, "and?")
    assert s["run_id"] != prior["run_id"]
    assert s["usage"]["cost_usd"] == 0.0
