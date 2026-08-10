"""
End-to-end runs of the compiled graph with the Claude client stubbed out.

The routing tests prove supervisor_node picks the right next step; these prove
the compiled graph actually goes there -- that the edges exist, the nodes write
the fields the supervisor reads, and a run terminates.
"""

import logging
from contextlib import contextmanager

import pytest
from test_memory_stores import FakeEmbedder

from research_agent import graph
from research_agent import usage as usage_accounting
from research_agent.graph import app, followup_state, initial_state
from research_agent.memory import InMemoryStore


class Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class ServerToolUse:
    def __init__(self, web_search_requests=0):
        self.web_search_requests = web_search_requests
        self.web_fetch_requests = 0


class Usage:
    """Mirrors the shape of the SDK's usage object closely enough for the
    cost accounting under test -- including the None-valued cache fields the
    real API returns when nothing was cached."""

    def __init__(self, web_search_requests=0):
        self.input_tokens = 1000
        self.output_tokens = 100
        self.cache_read_input_tokens = None
        self.cache_creation_input_tokens = None
        self.server_tool_use = ServerToolUse(web_search_requests)


class Response:
    def __init__(self, text, web_search_requests=0):
        self.content = [Block(text)]
        self.usage = Usage(web_search_requests)


class FakeClient:
    """Replies based on which node is calling, recognised by its prompt.

    `critic_verdicts` is consumed one per critic call, so a test can script
    "reject, then approve" and watch the revision loop run.
    """

    def __init__(self, critic_verdicts=("APPROVED",), responder_answers=()):
        self.critic_verdicts = list(critic_verdicts)
        # Consumed one per responder call, the `critic_verdicts` idiom. A
        # follow-up that signals insufficiency speaks twice in one turn -- the
        # sentinel, then the answer built from the enlarged notes -- so a
        # single fixed reply cannot script the path this phase adds. Empty
        # means "behave exactly as before".
        self.responder_answers = list(responder_answers)
        self.calls = []
        # The whole request payload per call, not just the prompt. The fakes
        # ignore `model`, which is exactly why nothing here could catch a
        # mis-threaded one until this existed.
        self.calls_with_kwargs = []
        self.messages = self

    def create(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]

        if "Respond with exactly one word" in prompt:
            node = "classifier"
            text = "technical"
        elif "Search the web" in prompt:
            node = "researcher"
            text = "FACTS: the sky scatters blue light."
        elif "follow-up question" in prompt:
            node = "responder"
            text = (
                self.responder_answers.pop(0) if self.responder_answers
                else "ANSWER: because of Rayleigh scattering."
            )
        elif "Does the" in prompt:
            node = "critic"
            text = self.critic_verdicts.pop(0) if self.critic_verdicts else "APPROVED"
        else:
            node = "writer"
            text = "REPORT: the sky is blue."

        self.calls.append((node, prompt))
        self.calls_with_kwargs.append((node, dict(kwargs)))
        # Only the researcher has the web search tool, so only it bills searches.
        return Response(text, web_search_requests=2 if node == "researcher" else 0)

    def nodes_called(self):
        return [node for node, _ in self.calls]


@pytest.fixture
def fake_client(monkeypatch):
    def install(critic_verdicts=("APPROVED",), responder_answers=()):
        client = FakeClient(critic_verdicts, responder_answers)
        monkeypatch.setattr(graph, "client", lambda: client)
        graph.set_memory(InMemoryStore(embedder=FakeEmbedder()))
        return client

    yield install
    graph.set_memory(None)  # don't leak a store into other tests


def test_research_run_visits_every_node_and_ends_approved(fake_client):
    client = fake_client()
    result = app.invoke(initial_state("why is the sky blue?"))

    assert client.nodes_called() == ["classifier", "researcher", "writer", "critic"]
    assert result["draft"] == "REPORT: the sky is blue."
    assert result["topic_type"] == "technical"
    assert result["approved"] is True
    assert result["forced_stop_reason"] == ""


def test_rejected_draft_is_rewritten_then_approved(fake_client):
    client = fake_client(["REVISE: cite the scattering claim", "APPROVED"])
    result = app.invoke(initial_state("why is the sky blue?"))

    assert client.nodes_called() == [
        "classifier", "researcher", "writer", "critic", "writer", "critic",
    ]
    assert result["revision_count"] == 1
    assert result["approved"] is True


def test_a_critic_that_never_approves_stops_at_the_revision_cap(fake_client):
    """The guardrail has to hold against a critic stuck in a loop, and the
    unapproved draft has to be labelled as such.

    The reason must be the *revision* cap, not the iteration backstop: the
    former says the draft never got grounded, the latter reads like an
    internal fault. They were the wrong way round until the evals caught it.
    """
    client = fake_client(["REVISE: still wrong"] * 20)
    result = app.invoke(initial_state("why is the sky blue?"))

    assert result["approved"] is False
    assert result["forced_stop_reason"] == "max_revisions_exceeded"
    assert client.nodes_called().count("writer") <= graph.MAX_REVISIONS + 2


def test_the_iteration_backstop_sits_above_the_revision_cap():
    """If the backstop fires first it isn't a backstop -- it's the cap, wearing
    a misleading name. Pin the relationship so tuning one can't silently
    smother the other."""
    assert graph.MAX_ITERATIONS > 2 * (graph.MAX_REVISIONS + 2)


def test_a_never_approving_followup_also_blames_the_revisions(fake_client):
    fake_client(["APPROVED"] + ["REVISE: still wrong"] * 20)
    first = app.invoke(initial_state("why?"))

    result = app.invoke(followup_state(first, "and?"))

    assert result["forced_stop_reason"] == "max_revisions_exceeded"


def test_followup_answers_without_searching_again(fake_client):
    client = fake_client(["APPROVED", "APPROVED"])
    first = app.invoke(initial_state("why is the sky blue?"))
    client.calls.clear()

    answer = app.invoke(followup_state(first, "what causes that scattering?"))

    assert client.nodes_called() == ["responder", "critic"]  # no classifier, no researcher
    assert answer["draft"] == "ANSWER: because of Rayleigh scattering."
    assert answer["approved"] is True


def test_followup_prompt_carries_the_notes_and_the_report(fake_client):
    client = fake_client(["APPROVED", "APPROVED"])
    first = app.invoke(initial_state("why is the sky blue?"))
    client.calls.clear()

    app.invoke(followup_state(first, "what causes that scattering?"))

    prompt = dict(client.calls)["responder"]
    assert "FACTS: the sky scatters blue light." in prompt
    assert "REPORT: the sky is blue." in prompt
    assert "what causes that scattering?" in prompt


def test_second_followup_sees_the_first_exchange(fake_client):
    client = fake_client(["APPROVED"] * 4)
    first = app.invoke(initial_state("why is the sky blue?"))
    second = app.invoke(followup_state(first, "what causes that scattering?"))
    client.calls.clear()

    app.invoke(followup_state(second, "and at sunset?"))

    prompt = dict(client.calls)["responder"]
    assert "what causes that scattering?" in prompt
    assert "ANSWER: because of Rayleigh scattering." in prompt


def test_a_followup_with_no_prior_notes_researches_instead_of_refusing(fake_client):
    """The reversal, through the compiled graph (Phase 17, path 1).

    This run used to make zero API calls and end `no_prior_research`: refusing
    cost nothing, and answering ungrounded would have cost the user's trust.
    The second half still holds -- what changed is that a third option exists.
    The follow-up now goes and gets notes, drafts from them, and the critic
    checks the draft, which is the same grounding contract a research run has.
    No answer ships that the critic has not reviewed.
    """
    client = fake_client()
    empty = initial_state("why is the sky blue?")
    empty.update({"mode": "followup", "topic_type": "general"})

    result = app.invoke(empty)

    assert client.nodes_called() == ["researcher", "responder", "critic"]
    assert result["forced_stop_reason"] == ""
    assert result["draft"]
    assert result["approved"] is True


SENTINEL_NOTES = "PRIOR NOTES MUST SURVIVE"


def test_notes_append_not_replace_on_a_followup_pass(fake_client):
    """A follow-up's research pass ENLARGES the session's note set.

    `state["research_notes"] = notes` was a REPLACE. On a follow-up that
    silently discards everything the session already gathered -- and nothing
    goes red, because the critic grades the draft against whatever notes it is
    handed, so a swapped note set reads exactly like an enlarged one. The
    prior notes have to survive verbatim, as a prefix, or every earlier turn
    in the conversation quietly loses its grounding.
    """
    fake_client()
    prior = initial_state("why is the sky blue?")
    prior.update({
        "topic_type": "technical",
        "research_notes": SENTINEL_NOTES,
        "draft": "the report",
    })
    s = followup_state(prior, "and what about at sunset?")

    result = graph.researcher_node(s)

    assert result["research_notes"].startswith(SENTINEL_NOTES)
    assert "FACTS: the sky scatters blue light." in result["research_notes"]


def test_a_followup_pass_files_its_notes_under_the_followup_question(fake_client):
    """SC-2 attribution, with no schema change: the note store has no session
    or turn column, but the stored text is prefixed with the task -- and in
    follow-up mode the task IS the follow-up question. So the note says which
    turn went and got it, and `owner` says whose it is."""
    fake_client()
    prior = initial_state("why is the sky blue?")
    prior.update({
        "topic_type": "technical",
        "research_notes": SENTINEL_NOTES,
        "draft": "the report",
    })

    graph.researcher_node(followup_state(prior, "and what about at sunset?"))

    newest = graph.memory().entries[-1]["text"]
    assert newest.startswith("[and what about at sunset?] ")
    assert SENTINEL_NOTES not in newest  # the note is what this pass found


# --------------------------------------------------------------------------
# Path 2: the notes exist but don't cover the question (Phase 17)
# --------------------------------------------------------------------------

RESEARCHER_FINDING = "FACTS: the sky scatters blue light."
SENTINEL_REPLY = "INSUFFICIENT: the notes name no such figure"


def _followup_over_notes(question="what does lock_timeout default to?"):
    """A follow-up turn whose session already has notes -- so row 4 (no prior
    notes) cannot fire and only the responder's own signal can start a pass."""
    prior = initial_state("postgres locking defaults")
    prior.update({
        "topic_type": "technical",
        "research_notes": SENTINEL_NOTES,
        "draft": "the report",
    })
    return followup_state(prior, question)


def _nodes(result):
    return [e["node"] for e in result["trace"]]


def test_insufficiency_signal_routes_to_researcher_and_ships_no_answer(fake_client):
    """Path 2 end to end: the signal ROUTES, it never generates.

    The window between "these notes don't cover it" and "new notes arrive"
    produces no answer at all. The sentinel is a flag's origin, not a draft:
    it never reaches the critic and it never reaches the caller. What ships is
    written from the enlarged note set and reviewed like any other answer.
    """
    client = fake_client(responder_answers=[
        SENTINEL_REPLY, "a grounded answer from the enlarged notes",
    ])

    result = app.invoke(_followup_over_notes())

    assert result["draft"] == "a grounded answer from the enlarged notes"
    assert SENTINEL_REPLY not in result["draft"]
    assert _nodes(result) == [
        "supervisor", "responder",    # the signal
        "supervisor", "researcher",   # the one pass it buys
        "supervisor", "responder",    # the answer, from the enlarged notes
        "supervisor", "critic",
        "supervisor",
    ]
    # The signalling pass produced no answer: it reports insufficiency and
    # nothing else. An `answer_length` here would mean a draft was written.
    signal = [e for e in result["trace"] if e["node"] == "responder"][0]
    assert signal == {"node": "responder", "insufficient": True}
    assert "answer_length" not in signal
    # The pass enlarged the note set rather than swapping it, so the answer is
    # grounded in everything the session has, not only in what this pass found.
    assert result["research_notes"].startswith(SENTINEL_NOTES)
    assert RESEARCHER_FINDING in result["research_notes"]
    assert client.nodes_called().count("researcher") == 1


def test_one_pass_bound_ships_the_honest_refusal_with_the_attempt(fake_client):
    """The other half of the bound: one pass, then the honest tail ships.

    If the enlarged notes still don't cover the question, "the research didn't
    cover that" is the correct answer -- and now it ships as a critic-reviewed
    draft WITH the attempt visible in the trace, which is the difference
    between a refusal that looked before it spoke and one that didn't.
    """
    client = fake_client(responder_answers=[
        SENTINEL_REPLY, "The research didn't cover the default value.",
    ])

    result = app.invoke(_followup_over_notes())

    assert result["draft"] == "The research didn't cover the default value."
    assert result["approved"] is True
    assert result["forced_stop_reason"] == ""
    assert client.nodes_called().count("researcher") == 1
    reaches = [e["followup_research"] for e in result["trace"] if "followup_research" in e]
    assert reaches == ["notes_insufficient"]


def test_one_pass_bound_post_research_sentinel_is_an_ordinary_draft(fake_client):
    """The leak gate. The parse is gated on the SAME condition as the prompt.

    After the pass, the prompt no longer asks for a sentinel -- so a reply that
    starts with one is just text the model produced, and it is treated as an
    ordinary draft for the critic to judge. A parse that outlived its prompt
    would read routing input out of a response nobody asked for.
    """
    client = fake_client(responder_answers=[
        SENTINEL_REPLY, "INSUFFICIENT: still nothing about lock_timeout",
    ])

    result = app.invoke(_followup_over_notes())

    assert result["draft"] == "INSUFFICIENT: still nothing about lock_timeout"
    assert result["reviewed"] is True                  # the critic saw it
    assert "critic" in client.nodes_called()
    assert result["notes_insufficient"] is False       # nothing re-flagged
    assert client.nodes_called().count("researcher") == 1  # and no second pass


def test_the_sentinel_is_asked_for_only_before_the_pass(fake_client):
    """The prompt half of the identical gating.

    The parse only ever reads a sentinel out of a response the prompt asked
    for. That is a claim about two branches at once, and only the prompts can
    show the first of them: before the pass the responder is told to signal,
    after it the wording is the pre-Phase-17 one verbatim, because by then
    saying so plainly IS the answer.
    """
    client = fake_client(responder_answers=[
        SENTINEL_REPLY, "a grounded answer from the enlarged notes",
    ])

    app.invoke(_followup_over_notes())

    before, after = [p for node, p in client.calls if node == "responder"]
    assert "INSUFFICIENT: " in before
    assert "say plainly" not in before
    assert "say plainly that the research didn't cover it" in after
    assert "INSUFFICIENT" not in after
    # And the line the eval harness dispatches the responder on survives both
    # branches -- rewriting it would make every scripted follow-up case fall
    # through to the writer's reply.
    assert "follow-up question" in before
    assert "follow-up question" in after


def test_grounding_survives_followup_research(fake_client):
    """SC-3: no path ships an answer the critic has not reviewed.

    The reach adds a node to the front of the follow-up path; it does not move
    the critic hop, which stays the last thing between the responder and the
    caller.
    """
    fake_client(responder_answers=[
        SENTINEL_REPLY, "a grounded answer from the enlarged notes",
    ])

    result = app.invoke(_followup_over_notes())

    workers = [n for n in _nodes(result) if n != "supervisor"]
    assert workers == ["responder", "researcher", "responder", "critic"]
    assert workers.index("critic") == len(workers) - 1  # the last word is the critic's
    assert result["reviewed"] is True
    assert result["approved"] is True


def test_the_researcher_stores_what_it_finds(fake_client):
    fake_client()
    app.invoke(initial_state("why is the sky blue?"))

    store = graph.memory()
    assert len(store) == 1


def test_the_researcher_recalls_stored_notes_on_a_later_run(fake_client):
    client = fake_client(["APPROVED"] * 4)
    app.invoke(initial_state("langgraph supervisor patterns"))
    client.calls.clear()

    result = app.invoke(initial_state("langgraph supervisor retry"))

    prompt = dict(client.calls)["researcher"]
    assert "previous research sessions" in prompt
    recall = [e for e in result["trace"] if e.get("node") == "researcher"][-1]
    assert recall["recalled_from_memory"] == 1


def test_the_trace_records_the_whole_run(fake_client):
    fake_client(["REVISE: fix it", "APPROVED"])
    result = app.invoke(initial_state("why is the sky blue?"))

    assert [e["node"] for e in result["trace"]] == [
        "supervisor", "classifier",
        "supervisor", "researcher",
        "supervisor", "writer",
        "supervisor", "critic",
        "supervisor", "writer",
        "supervisor", "critic",
        "supervisor",
    ]


# --------------------------------------------------------------------------
# Cost accounting
# --------------------------------------------------------------------------


def test_usage_accumulates_across_every_node(fake_client):
    client = fake_client()
    result = app.invoke(initial_state("why is the sky blue?"))

    usage = result["usage"]
    assert usage["calls"] == len(client.nodes_called()) == 4
    assert usage["input_tokens"] == 4000
    assert usage["output_tokens"] == 400
    assert usage["web_search_requests"] == 2  # researcher only
    assert usage["cost_usd"] > 0
    assert usage["pricing_unknown"] is False


def test_a_revision_costs_more_than_a_clean_run(fake_client):
    """Two extra model calls, two extra calls' worth of spend -- the thing
    the budget guardrail exists to bound."""
    fake_client(["APPROVED"])
    clean = app.invoke(initial_state("why?"))["usage"]["cost_usd"]

    fake_client(["REVISE: fix it", "APPROVED"])
    revised = app.invoke(initial_state("why?"))["usage"]["cost_usd"]

    assert revised > clean


def test_the_budget_guardrail_stops_a_run_mid_flight(fake_client, monkeypatch):
    """A budget small enough to blow on the first call: the run stops with a
    named reason rather than continuing to spend."""
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.000001")
    client = fake_client()

    result = app.invoke(initial_state("why?"))

    assert result["forced_stop_reason"] == "budget_exceeded"
    assert result["approved"] is False
    assert len(client.nodes_called()) < 4  # stopped before finishing the pipeline


def test_a_generous_budget_never_fires(fake_client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "100")
    fake_client()
    assert app.invoke(initial_state("why?"))["forced_stop_reason"] == ""


def test_a_followup_is_costed_separately_from_its_research_run(fake_client):
    fake_client(["APPROVED", "APPROVED"])
    first = app.invoke(initial_state("why?"))

    answer = app.invoke(followup_state(first, "and?"))

    assert answer["usage"]["calls"] == 2  # responder + critic only
    assert answer["usage"]["cost_usd"] < first["usage"]["cost_usd"]


class BillingStore:
    """A store whose embedder bills, the way the real one does.

    `InMemoryStore(FakeEmbedder())` -- what every other test here uses --
    reports nothing, which is correct for those tests and useless for this
    one: it cannot tell "the node opened a meter" apart from "the node forgot
    to". This store reports 25 tokens per embed, exactly as the Voyage seam
    now does, and only the researcher's own with-block can pick them up.
    """

    def __init__(self, tokens_per_embed=25):
        self.tokens_per_embed = tokens_per_embed

    def query(self, query_text, top_k=3, min_similarity=0.3, owner=""):
        usage_accounting.report_embedding("voyage-3.5", self.tokens_per_embed)
        return []

    def add(self, text, owner=""):
        usage_accounting.report_embedding("voyage-3.5", self.tokens_per_embed)


def test_the_researcher_meters_the_embeddings_it_causes(fake_client):
    """The wiring gate. Every piece below is unit-tested elsewhere; what only
    a run can show is that the node actually *opens* the meter around both
    embed calls and folds the result into this run's usage."""
    fake_client()
    graph.set_memory(BillingStore())
    state = initial_state("why is the sky blue?")
    state["topic_type"] = "technical"

    result = graph.researcher_node(state)

    usage = result["usage"]
    assert usage["embedding_requests"] == 2  # one recall, one note written
    assert usage["embedding_tokens"] == 50
    assert usage["embedding_cost_usd"] > 0
    # And it is in the one number every consumer reads, on top of the model
    # call this node also made.
    assert usage["cost_usd"] > usage["embedding_cost_usd"]
    assert usage["pricing_unknown"] is False


def test_a_run_whose_store_never_embeds_records_no_embedding_spend(fake_client):
    """The other half: no embed calls means no $0.00 Voyage line item invented
    for a run that never called Voyage. This is the path every other test in
    this file takes, so it is also what keeps them unchanged."""
    fake_client()
    result = app.invoke(initial_state("why is the sky blue?"))

    assert result["usage"]["embedding_requests"] == 0
    assert result["usage"]["embedding_tokens"] == 0
    assert result["usage"]["embedding_cost_usd"] == 0.0


def test_every_run_carries_a_distinct_run_id(fake_client):
    fake_client(["APPROVED"] * 4)
    first = app.invoke(initial_state("why?"))
    second = app.invoke(initial_state("why again?"))
    assert first["run_id"] != second["run_id"]


# --------------------------------------------------------------------------
# The critic's own model
#
# `call_model` names a model in four places -- the span, the API call, the
# cost record, and the log line -- and none of them reads it back off the
# response. `CallUsage.from_response` never touches `response.model`; the name
# that ends up on the invoice is the one the caller passed in. So the model is
# threaded, and every one of the four sites is asserted separately: a critic
# threaded to the API call but recorded as `MODEL` bills an Opus critic at
# Sonnet rates, 2.5x under, with no error anywhere to notice.
#
# Exact-dollar assertions here use only the UNDATED price rows (haiku $1/$5,
# opus $5/$25). `call_model` prices at wall-clock today and Sonnet's
# introductory window closes 2026-08-31, so an exact figure written against
# Sonnet would go red on a date nobody chose.
# --------------------------------------------------------------------------

HAIKU = "claude-haiku-4-5"  # undated row, $1/$5
OPUS = "claude-opus-5"  # undated row, $5/$25
UNPRICED = "some-unpriced-model"  # no row at all -> pricing_unknown

# FakeClient bills 1000 input / 100 output tokens on every call.
HAIKU_CALL_USD = (1000 * 1.0 + 100 * 5.0) / 1e6  # $0.0015
OPUS_CALL_USD = (1000 * 5.0 + 100 * 25.0) / 1e6  # $0.0075


def _models_by_node(client):
    return {node: kwargs["model"] for node, kwargs in client.calls_with_kwargs}


def _run(fake_client, question="why is the sky blue?"):
    """One clean research run against a FRESH client and a FRESH store.

    The fresh store matters: `fake_client()` installs a new InMemoryStore, and
    a second run against the *same* store recalls the first run's notes, which
    changes the researcher's prompt. A payload-equality test would then fail
    for a reason that has nothing to do with the model.
    """
    client = fake_client()
    return client, app.invoke(initial_state(question))


# --- A. the accessor, and the neutral default ------------------------------


def test_critic_model_accessor_defaults_to_the_writers_model(monkeypatch):
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    assert graph.critic_model() == graph.MODEL


def test_critic_model_accessor_returns_the_configured_model(monkeypatch):
    monkeypatch.setenv("CRITIC_MODEL", OPUS)
    assert graph.critic_model() == OPUS


def test_critic_model_accessor_treats_blank_as_unset(monkeypatch):
    """An env var exported empty by a deploy template must not name a model
    called "" -- it means "not configured"."""
    monkeypatch.setenv("CRITIC_MODEL", "   ")
    assert graph.critic_model() == graph.MODEL


def test_critic_model_accessor_reads_the_environment_on_every_call(monkeypatch):
    """The value is read per call, never cached at import. A module-scope read
    would freeze it at import time, so an operator changing configuration
    would not change what the process does -- and no test could flip it."""
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    assert graph.critic_model() == graph.MODEL

    monkeypatch.setenv("CRITIC_MODEL", HAIKU)
    assert graph.critic_model() == HAIKU

    monkeypatch.setenv("CRITIC_MODEL", OPUS)
    assert graph.critic_model() == OPUS

    monkeypatch.delenv("CRITIC_MODEL")
    assert graph.critic_model() == graph.MODEL


def test_critic_model_accessor_unset_is_byte_identical_to_setting_it(
    fake_client, monkeypatch
):
    """The neutral default, demonstrated rather than claimed.

    Unset must produce the same requests as CRITIC_MODEL explicitly set to the
    writer's model -- so the default path adds nothing, and shipping the
    capability is a no-op until an operator acts. Full payload dicts are
    compared, not just the model key: that also catches the default path
    growing an extra kwarg.

    This is the CI guard too. The keyless 41/41 evals and the recorded
    fixture's green replay both depend on `critic_model() == MODEL` in CI;
    a future workflow that exports CRITIC_MODEL should surface as this red,
    not as a mystery-stale fixture.
    """
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    unset_client, unset = _run(fake_client)

    monkeypatch.setenv("CRITIC_MODEL", graph.MODEL)
    set_client, _ = _run(fake_client)

    assert set(_models_by_node(unset_client)) == {
        "classifier", "researcher", "writer", "critic",
    }
    assert all(m == graph.MODEL for m in _models_by_node(unset_client).values())
    assert unset_client.calls_with_kwargs == set_client.calls_with_kwargs
    assert unset["usage"]["pricing_unknown"] is False


# --- B. all four naming sites ----------------------------------------------


def test_critic_threading_four_sites_a_reaches_the_api_payload(
    fake_client, monkeypatch
):
    monkeypatch.setenv("CRITIC_MODEL", HAIKU)
    client, _ = _run(fake_client)

    models = _models_by_node(client)
    assert models["critic"] == HAIKU
    assert models["writer"] == graph.MODEL
    assert models["researcher"] == graph.MODEL
    assert models["classifier"] == graph.MODEL


def test_critic_threading_four_sites_b_reaches_the_span(fake_client, monkeypatch):
    """Telemetry that disagrees with the invoice is worse than no telemetry."""
    spans = []

    @contextmanager
    def recording_span(name, **attributes):
        spans.append((name, attributes))
        yield None

    monkeypatch.setattr(graph, "span", recording_span)
    monkeypatch.setenv("CRITIC_MODEL", HAIKU)
    _run(fake_client)

    by_name = dict(spans)
    assert by_name["node.critic"]["model"] == HAIKU
    assert by_name["node.writer"]["model"] == graph.MODEL


def test_critic_threading_four_sites_c_reaches_the_cost_record(
    fake_client, monkeypatch
):
    """The site that decides what the run says it cost.

    Measured as a difference so no Sonnet rate appears in an exact figure:
    the same run with an UNPRICED critic contributes exactly $0 for that call
    (record() catches UnknownModelPricing and returns 0.0), so the gap between
    the two runs is the critic call and nothing else. If record() were still
    passed `MODEL`, the unpriced run would price the critic at Sonnet and this
    difference would be neither $0.0015 nor even positive.
    """
    monkeypatch.setenv("CRITIC_MODEL", HAIKU)
    _, priced = _run(fake_client)

    monkeypatch.setenv("CRITIC_MODEL", UNPRICED)
    _, uncosted = _run(fake_client)

    critic_share = priced["usage"]["cost_usd"] - uncosted["usage"]["cost_usd"]
    assert critic_share == pytest.approx(HAIKU_CALL_USD, abs=1e-9)


def test_critic_threading_four_sites_d_reaches_the_log_line(
    fake_client, monkeypatch, caplog
):
    """The agent logger deliberately does not propagate -- its own handler is
    the only one that should fire -- so propagation is turned on for the
    duration rather than the log call being replaced by a fake. What is under
    test is the real `log.info(..., extra={"model": ...})`.
    """
    monkeypatch.setattr(graph.log, "propagate", True)
    monkeypatch.setenv("CRITIC_MODEL", HAIKU)

    with caplog.at_level(logging.INFO, logger=graph.log.name):
        _run(fake_client)

    by_node = {
        r.node: r.model
        for r in caplog.records
        if getattr(r, "event", "") == "model_call"
    }
    assert by_node["critic"] == HAIKU
    assert by_node["writer"] == graph.MODEL


# --- C. the misbilling discriminator ---------------------------------------


def test_critic_misbilling_discriminator_unpriced_critic_is_reported(
    fake_client, monkeypatch
):
    """The phase's central test.

    `pricing_unknown` can flip only if the threaded name reached `record()`.
    Threading `messages.create` alone changes nothing here -- the fakes ignore
    the model they are handed -- so this is the one red that separates "the
    critic runs on its own model" from "the critic runs on its own model and
    the bill knows it". The rest of the run stays priced: an unpriced critic
    makes `cost_usd` a floor, not a zero.
    """
    monkeypatch.setenv("CRITIC_MODEL", UNPRICED)
    _, result = _run(fake_client)

    assert result["usage"]["pricing_unknown"] is True
    assert result["usage"]["cost_usd"] > 0
    assert result["usage"]["calls"] == 4  # the call is counted, just not costed


def test_critic_misbilling_discriminator_stays_silent_when_unset(
    fake_client, monkeypatch
):
    """The twin. Unset means the writer's model, which is priced -- so the
    flag must not fire, or it would mean nothing when it did."""
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    _, result = _run(fake_client)

    assert result["usage"]["pricing_unknown"] is False
    assert result["usage"]["cost_usd"] > 0


def test_critic_misbilling_discriminator_spares_the_other_nodes(
    fake_client, monkeypatch
):
    """An unpriced critic must not take the whole run's accounting with it.
    Three priced calls still cost what three priced calls cost -- the same
    figure a run whose critic is priced at $0 would report."""
    monkeypatch.setenv("CRITIC_MODEL", UNPRICED)
    _, unpriced_critic = _run(fake_client)

    monkeypatch.setenv("CRITIC_MODEL", HAIKU)
    _, priced_critic = _run(fake_client)

    assert unpriced_critic["usage"]["cost_usd"] > 0
    assert unpriced_critic["usage"]["cost_usd"] == pytest.approx(
        priced_critic["usage"]["cost_usd"] - HAIKU_CALL_USD, abs=1e-9
    )


# --- D. per-node attribution, exact and date-safe --------------------------


def test_per_node_attribution_prices_the_critic_at_its_own_rate(
    fake_client, monkeypatch
):
    """Exact arithmetic without naming a dated rate.

    One critic call per run at 1000 in / 100 out. Opus $5/$25 and haiku $1/$5
    are both single undated windows, so the difference between the two runs is
    fixed forever at ($5000 + $2500 - $1000 - $500)/1M = $0.0060. Everything
    else in the run -- three Sonnet-priced calls and two web searches -- is
    identical and cancels, which is what keeps the 2026-08-31 Sonnet boundary
    out of the assertion. Phase 14's multipliers sit at their 1.0 defaults
    under the fakes and cancel too.
    """
    monkeypatch.setenv("CRITIC_MODEL", HAIKU)
    _, cheap = _run(fake_client)

    monkeypatch.setenv("CRITIC_MODEL", OPUS)
    _, dear = _run(fake_client)

    delta = dear["usage"]["cost_usd"] - cheap["usage"]["cost_usd"]
    assert delta == pytest.approx(OPUS_CALL_USD - HAIKU_CALL_USD, abs=1e-9)
    assert delta == pytest.approx(0.0060, abs=1e-9)
    assert cheap["usage"]["pricing_unknown"] is False
    assert dear["usage"]["pricing_unknown"] is False


def test_per_node_attribution_leaves_every_other_node_on_the_writers_model(
    fake_client, monkeypatch
):
    """Independence is the critic's alone. A revision run makes two critic
    calls and three writer calls; each is attributed to its own model, and the
    token counts stay identical to a uniform-model run -- only the dollars
    move."""
    monkeypatch.setenv("CRITIC_MODEL", OPUS)
    client = fake_client(["REVISE: cite the scattering claim", "APPROVED"])
    result = app.invoke(initial_state("why is the sky blue?"))

    per_call = [(node, kwargs["model"]) for node, kwargs in client.calls_with_kwargs]
    assert per_call == [
        ("classifier", graph.MODEL),
        ("researcher", graph.MODEL),
        ("writer", graph.MODEL),
        ("critic", OPUS),
        ("writer", graph.MODEL),
        ("critic", OPUS),
    ]
    assert result["usage"]["calls"] == 6
    assert result["usage"]["input_tokens"] == 6000
    assert result["usage"]["pricing_unknown"] is False


def test_per_node_attribution_a_pricier_critic_costs_more(fake_client, monkeypatch):
    """The plain-language claim behind the arithmetic, on the production
    config's own terms: an Opus critic makes a run cost more than a Sonnet one,
    and the difference is the critic call, not the rest of the pipeline."""
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    _, shared = _run(fake_client)

    monkeypatch.setenv("CRITIC_MODEL", OPUS)
    _, independent = _run(fake_client)

    assert independent["usage"]["cost_usd"] > shared["usage"]["cost_usd"]
    assert independent["usage"]["input_tokens"] == shared["usage"]["input_tokens"]
    assert independent["usage"]["calls"] == shared["usage"]["calls"]
