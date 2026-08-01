"""
End-to-end runs of the compiled graph with the Claude client stubbed out.

The routing tests prove supervisor_node picks the right next step; these prove
the compiled graph actually goes there -- that the edges exist, the nodes write
the fields the supervisor reads, and a run terminates.
"""

import pytest

import research_agent
from research_agent import app, followup_state, initial_state
from vector_memory import InMemoryStore

from test_memory_stores import FakeEmbedder


class Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class Response:
    def __init__(self, text):
        self.content = [Block(text)]


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
        return Response(text)

    def nodes_called(self):
        return [node for node, _ in self.calls]


@pytest.fixture
def fake_client(monkeypatch):
    def install(critic_verdicts=("APPROVED",)):
        client = FakeClient(critic_verdicts)
        monkeypatch.setattr(research_agent, "client", lambda: client)
        research_agent.set_memory(InMemoryStore(embedder=FakeEmbedder()))
        return client

    yield install
    research_agent.set_memory(None)  # don't leak a store into other tests


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
    unapproved draft has to be labelled as such."""
    client = fake_client(["REVISE: still wrong"] * 20)
    result = app.invoke(initial_state("why is the sky blue?"))

    assert result["approved"] is False
    assert result["forced_stop_reason"] in (
        "max_revisions_exceeded",
        "max_iterations_exceeded",
    )
    assert client.nodes_called().count("writer") <= research_agent.MAX_REVISIONS + 1


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

    store = research_agent.memory()
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
