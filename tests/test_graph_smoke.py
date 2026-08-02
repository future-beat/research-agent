"""
End-to-end runs of the compiled graph with the Claude client stubbed out.

The routing tests prove supervisor_node picks the right next step; these prove
the compiled graph actually goes there -- that the edges exist, the nodes write
the fields the supervisor reads, and a run terminates.
"""

import pytest
from test_memory_stores import FakeEmbedder

from research_agent import graph
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

    def __init__(self, critic_verdicts=("APPROVED",)):
        self.critic_verdicts = list(critic_verdicts)
        self.calls = []
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
            text = "ANSWER: because of Rayleigh scattering."
        elif "Does the" in prompt:
            node = "critic"
            text = self.critic_verdicts.pop(0) if self.critic_verdicts else "APPROVED"
        else:
            node = "writer"
            text = "REPORT: the sky is blue."

        self.calls.append((node, prompt))
        # Only the researcher has the web search tool, so only it bills searches.
        return Response(text, web_search_requests=2 if node == "researcher" else 0)

    def nodes_called(self):
        return [node for node, _ in self.calls]


@pytest.fixture
def fake_client(monkeypatch):
    def install(critic_verdicts=("APPROVED",)):
        client = FakeClient(critic_verdicts)
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


def test_followup_without_prior_research_makes_no_api_calls(fake_client):
    """Refusing costs nothing; answering ungrounded would cost the user's trust."""
    client = fake_client()
    empty = initial_state("why is the sky blue?")
    empty.update({"mode": "followup", "topic_type": "general"})

    result = app.invoke(empty)

    assert client.calls == []
    assert result["forced_stop_reason"] == "no_prior_research"


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


def test_every_run_carries_a_distinct_run_id(fake_client):
    fake_client(["APPROVED"] * 4)
    first = app.invoke(initial_state("why?"))
    second = app.invoke(initial_state("why again?"))
    assert first["run_id"] != second["run_id"]
