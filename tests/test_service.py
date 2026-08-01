"""
API tests against the real FastAPI app with the Claude client stubbed.

The session store is pointed at a temp database via dependency override, so
these exercise genuine SQLite persistence and genuine graph traversal -- the
only thing faked is the network.
"""

import json

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from test_graph_smoke import FakeClient
from test_memory_stores import FakeEmbedder

import research_agent
import service
from metrics import SQLiteMetricsStore
from sessions import SQLiteSessionStore
from vector_memory import InMemoryStore


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """Returns a factory so a test can script the critic before the app boots."""
    created = []

    # The app's lifespan builds a SessionStore at SESSION_DB_PATH before the
    # dependency override can redirect it. Without this, running the suite
    # drops a stray sessions.db next to the source.
    monkeypatch.setenv("SESSION_DB_PATH", str(tmp_path / "lifespan.db"))
    monkeypatch.setenv("METRICS_DB_PATH", str(tmp_path / "lifespan-metrics.db"))

    def build(critic_verdicts=("APPROVED",) * 8):
        fake = FakeClient(critic_verdicts)
        monkeypatch.setattr(research_agent, "client", lambda: fake)
        research_agent.set_memory(InMemoryStore(embedder=FakeEmbedder()))

        store = SQLiteSessionStore(str(tmp_path / "sessions.db"))
        metrics = SQLiteMetricsStore(str(tmp_path / "metrics.db"))
        service.app.dependency_overrides[service.get_sessions] = lambda: store
        service.app.dependency_overrides[service.get_metrics] = lambda: metrics

        client = TestClient(service.app)
        created.append((client, store, metrics))
        return client, fake

    yield build

    service.app.dependency_overrides.clear()
    research_agent.set_memory(None)
    for client, store, metrics in created:
        client.close()
        store.close()
        metrics.close()


def sse_events(response) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, payload) pairs."""
    events = []
    for block in response.text.strip().split("\n\n"):
        if not block.strip():
            continue
        name = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        events.append((name, data))
    return events


# --------------------------------------------------------------------------
# Ops
# --------------------------------------------------------------------------


def test_health_reports_backends_without_calling_them(make_client):
    """A health check that fails when Anthropic is down gets a perfectly
    healthy container restarted."""
    client, fake = make_client()

    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["memory"]["backend"] == "InMemoryStore"
    assert body["sessions"]["count"] == 0
    assert fake.calls == []


def test_memory_endpoint_reports_the_live_backend(make_client):
    client, _ = make_client()
    body = client.get("/memory").json()
    assert body["backend"] == "InMemoryStore"
    assert body["notes"] == 0


def test_openapi_schema_is_served(make_client):
    client, _ = make_client()
    assert client.get("/openapi.json").status_code == 200


# --------------------------------------------------------------------------
# POST /research
# --------------------------------------------------------------------------


def test_research_returns_a_grounded_report_and_opens_a_session(make_client):
    client, fake = make_client()

    body = client.post("/research", json={"question": "why is the sky blue?"}).json()

    assert body["mode"] == "research"
    assert body["answer"] == "REPORT: the sky is blue."
    assert body["topic_type"] == "technical"
    assert body["approved"] is True
    assert body["forced_stop_reason"] == ""
    assert body["retries"] == 0
    assert body["session_id"]
    assert fake.nodes_called() == ["classifier", "researcher", "writer", "critic"]


def test_research_persists_the_session(make_client):
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    detail = client.get(f"/sessions/{session_id}").json()
    assert detail["task"] == "why?"
    assert detail["latest_answer"] == "REPORT: the sky is blue."
    assert detail["turns"] == 1


def test_research_reports_an_unapproved_draft_honestly(make_client):
    """A caller must be able to tell a fact-checked report from one that hit
    the revision cap. Silently returning the latter would be the worst bug
    this service could have."""
    client, _ = make_client(["REVISE: nope"] * 20)

    body = client.post("/research", json={"question": "why?"}).json()

    assert body["approved"] is False
    assert body["forced_stop_reason"] in (
        "max_revisions_exceeded",
        "max_iterations_exceeded",
    )


def test_revision_count_is_reported(make_client):
    client, _ = make_client(["REVISE: cite it", "APPROVED"])
    body = client.post("/research", json={"question": "why?"}).json()
    assert body["revision_count"] == 1
    assert body["approved"] is True


@pytest.mark.parametrize(
    "payload", [{}, {"question": ""}, {"question": "   "}, {"question": "x" * 3000}]
)
def test_bad_questions_are_rejected(make_client, payload):
    client, fake = make_client()
    assert client.post("/research", json=payload).status_code == 422
    assert fake.calls == []  # nothing billable happens on a bad request


# --------------------------------------------------------------------------
# Follow-ups
# --------------------------------------------------------------------------


def test_ask_answers_from_the_session_without_searching_again(make_client):
    client, fake = make_client()
    session_id = client.post(
        "/research", json={"question": "why is the sky blue?"}
    ).json()["session_id"]
    fake.calls.clear()

    body = client.post(f"/sessions/{session_id}/ask", json={"question": "what causes it?"}).json()

    assert fake.nodes_called() == ["responder", "critic"]
    assert body["mode"] == "followup"
    assert body["answer"] == "ANSWER: because of Rayleigh scattering."
    assert body["session_id"] == session_id


def test_follow_ups_accumulate_into_the_session_conversation(make_client):
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    client.post(f"/sessions/{session_id}/ask", json={"question": "first?"})
    client.post(f"/sessions/{session_id}/ask", json={"question": "second?"})

    detail = client.get(f"/sessions/{session_id}").json()
    assert [turn["question"] for turn in detail["conversation"]] == ["first?", "second?"]
    assert detail["turns"] == 3


def test_a_follow_up_survives_a_restart(make_client):
    """The whole reason sessions are on disk: the follow-up arrives as a
    separate request, and may not reach the same process."""
    client, fake = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    with TestClient(service.app) as reborn:  # new app instance, same store
        fake.calls.clear()
        body = reborn.post(f"/sessions/{session_id}/ask", json={"question": "and?"}).json()

    assert body["answer"] == "ANSWER: because of Rayleigh scattering."
    assert fake.nodes_called() == ["responder", "critic"]


def test_ask_on_an_unknown_session_is_404(make_client):
    client, fake = make_client()
    assert client.post("/sessions/nope/ask", json={"question": "?"}).status_code == 404
    assert fake.calls == []


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


def test_sessions_are_listed_newest_first(make_client):
    client, _ = make_client()
    first = client.post("/research", json={"question": "first"}).json()["session_id"]
    second = client.post("/research", json={"question": "second"}).json()["session_id"]

    listed = client.get("/sessions").json()["sessions"]
    assert [s["session_id"] for s in listed] == [second, first]
    assert "the report" not in str(listed)  # summaries only


def test_trace_is_retrievable_after_the_run(make_client):
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    trace = client.get(f"/sessions/{session_id}/trace").json()["trace"]
    assert [e["node"] for e in trace if e["node"] != "supervisor"] == [
        "classifier", "researcher", "writer", "critic",
    ]


def test_sessions_can_be_deleted(make_client):
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    assert client.delete(f"/sessions/{session_id}").status_code == 204
    assert client.get(f"/sessions/{session_id}").status_code == 404
    assert client.delete(f"/sessions/{session_id}").status_code == 404


@pytest.mark.parametrize("path", ["/sessions/nope", "/sessions/nope/trace"])
def test_unknown_sessions_are_404(make_client, path):
    client, _ = make_client()
    assert client.get(path).status_code == 404


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------


def test_stream_emits_progress_then_exactly_one_result(make_client):
    client, _ = make_client()

    with client.stream("POST", "/research/stream", json={"question": "why?"}) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        response.read()

    events = sse_events(response)
    names = [name for name, _ in events]

    assert names[:-1] == ["node"] * (len(names) - 1)
    assert names[-1] == "result"
    assert names.count("result") == 1
    assert [payload["node"] for _, payload in events[:-1]] == [
        "classifier", "researcher", "writer", "critic",
    ]


def test_stream_does_not_emit_supervisor_hops(make_client):
    """The supervisor fires between every worker; streaming it would bury the
    real progress. It still appears in the final trace, where it belongs."""
    client, _ = make_client()
    response = client.post("/research/stream", json={"question": "why?"})
    events = sse_events(response)

    assert all(payload["node"] != "supervisor" for name, payload in events if name == "node")
    assert any(e["node"] == "supervisor" for e in events[-1][1]["trace"])


def test_streamed_run_is_persisted_like_a_blocking_one(make_client):
    client, _ = make_client()
    response = client.post("/research/stream", json={"question": "why?"})

    session_id = sse_events(response)[-1][1]["session_id"]
    detail = client.get(f"/sessions/{session_id}").json()
    assert detail["latest_answer"] == "REPORT: the sky is blue."


def test_stream_carries_node_detail(make_client):
    client, _ = make_client()
    response = client.post("/research/stream", json={"question": "why?"})

    detail = {payload["node"]: payload for _, payload in sse_events(response) if _ == "node"}
    assert detail["classifier"]["topic_type"] == "technical"
    assert detail["critic"]["approved"] is True


def test_ask_stream_persists_the_follow_up(make_client):
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    response = client.post(f"/sessions/{session_id}/ask/stream", json={"question": "and?"})

    names = [name for name, _ in sse_events(response)]
    assert names == ["node", "node", "result"]  # responder, critic
    assert client.get(f"/sessions/{session_id}").json()["turns"] == 2


def test_ask_stream_on_an_unknown_session_is_404_before_streaming(make_client):
    """The 404 has to land while headers can still carry it -- once the stream
    opens, the status is already 200."""
    client, _ = make_client()
    assert client.post("/sessions/nope/ask/stream", json={"question": "?"}).status_code == 404


def test_stream_reports_a_mid_run_failure_as_an_error_event(make_client, monkeypatch):
    """Headers are long sent by the time a node fails, so the failure has to
    arrive in-band or the client just sees a truncated stream."""
    client, _ = make_client()

    def explode(state):
        raise anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )

    monkeypatch.setattr(research_agent.app, "stream", explode)

    response = client.post("/research/stream", json={"question": "why?"})
    events = sse_events(response)

    assert [name for name, _ in events] == ["error"]
    assert events[0][1]["error"] == "APIConnectionError"


def test_a_failed_stream_leaves_no_session_behind(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setattr(
        research_agent.app,
        "stream",
        lambda state: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client.post("/research/stream", json={"question": "why?"})

    assert client.get("/sessions").json()["sessions"] == []


# --------------------------------------------------------------------------
# Upstream failure mapping
# --------------------------------------------------------------------------


def _raise(exc):
    def invoke(state):
        raise exc

    return invoke


def api_error(cls, code):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize(
    "exc, expected",
    [
        (api_error(anthropic.RateLimitError, 429), 429),
        (api_error(anthropic.InternalServerError, 500), 502),
        (
            anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            ),
            502,
        ),
    ],
)
def test_upstream_failures_map_to_useful_status_codes(make_client, monkeypatch, exc, expected):
    """Retries have already been spent inside the nodes by this point, so the
    caller needs to know whether to back off (429) or whether upstream is
    simply unwell (502)."""
    client, _ = make_client()
    monkeypatch.setattr(research_agent.app, "invoke", _raise(exc))

    assert client.post("/research", json={"question": "why?"}).status_code == expected


def test_a_failed_run_opens_no_session(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setattr(
        research_agent.app, "invoke", _raise(api_error(anthropic.RateLimitError, 429))
    )

    client.post("/research", json={"question": "why?"})

    assert client.get("/sessions").json()["sessions"] == []


# --------------------------------------------------------------------------
# Cost reporting and metrics
# --------------------------------------------------------------------------


def test_a_run_reports_what_it_cost(make_client):
    client, _ = make_client()
    body = client.post("/research", json={"question": "why?"}).json()

    assert body["usage"]["calls"] == 4
    assert body["usage"]["web_search_requests"] == 2
    assert body["cost_usd"] > 0
    assert body["usage"]["pricing_unknown"] is False


def test_pricing_endpoint_reports_todays_rates(make_client):
    """Sonnet 5's introductory pricing ends 2026-08-31, so the same run costs
    50% more the next day. A cost dashboard that steps without explanation is
    a support ticket."""
    client, _ = make_client()
    body = client.get("/pricing").json()

    assert body["model"] == research_agent.MODEL
    assert body["usd_per_mtok"]["input"] in (2.0, 3.0)
    assert body["web_search_usd_per_request"] == 0.01
    assert body["max_run_cost_usd"] > 0


def test_metrics_start_empty(make_client):
    client, _ = make_client()
    summary = client.get("/metrics").json()

    assert summary["runs"]["total"] == 0
    assert summary["quality"]["approval_rate"] is None


def test_a_completed_run_lands_in_metrics(make_client):
    client, _ = make_client()
    client.post("/research", json={"question": "why?"})

    summary = client.get("/metrics").json()
    assert summary["runs"]["total"] == 1
    assert summary["runs"]["completed"] == 1
    assert summary["runs"]["research"] == 1
    assert summary["quality"]["approval_rate"] == 1.0
    assert summary["cost"]["total_usd"] > 0
    assert summary["cost"]["model_calls"] == 4
    assert summary["latency_ms"]["p50"] > 0


def test_follow_ups_are_counted_separately_from_research_runs(make_client):
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]
    client.post(f"/sessions/{session_id}/ask", json={"question": "and?"})

    runs = client.get("/metrics").json()["runs"]
    assert (runs["research"], runs["followup"], runs["total"]) == (1, 1, 2)


def test_a_failed_run_is_counted_even_though_it_opens_no_session(make_client, monkeypatch):
    """Counting only successes would make an upstream outage look like a
    quiet day."""
    client, _ = make_client()
    monkeypatch.setattr(
        research_agent.app, "invoke", _raise(api_error(anthropic.RateLimitError, 429))
    )

    client.post("/research", json={"question": "why?"})

    summary = client.get("/metrics").json()
    assert summary["runs"]["failed"] == 1
    assert summary["runs"]["failure_rate"] == 1.0
    assert summary["reliability"]["errors"] == {"RateLimitError": 1}
    assert client.get("/sessions").json()["sessions"] == []


def test_a_failed_stream_is_counted_too(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setattr(
        research_agent.app,
        "stream",
        lambda state: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client.post("/research/stream", json={"question": "why?"})

    summary = client.get("/metrics").json()
    assert summary["runs"]["failed"] == 1
    assert summary["reliability"]["errors"] == {"RuntimeError": 1}


def test_a_guardrail_firing_shows_up_in_metrics(make_client):
    client, _ = make_client(["REVISE: nope"] * 20)
    client.post("/research", json={"question": "why?"})

    quality = client.get("/metrics").json()["quality"]
    assert quality["forced_stops"] == 1
    assert sum(quality["forced_stop_reasons"].values()) == 1
    assert quality["approval_rate"] == 0.0


def test_a_streamed_run_is_recorded_like_a_blocking_one(make_client):
    client, _ = make_client()
    client.post("/research/stream", json={"question": "why?"})

    assert client.get("/metrics").json()["runs"]["completed"] == 1


def test_health_reports_how_many_runs_have_been_recorded(make_client):
    client, _ = make_client()
    client.post("/research", json={"question": "why?"})
    assert client.get("/health").json()["runs_recorded"] == 1


def test_an_unexpected_error_is_not_dressed_up_as_an_upstream_problem(make_client, monkeypatch):
    """A bug in our own code should surface as a 500, not a 502 blaming
    Anthropic for something we did."""
    client, _ = make_client()
    monkeypatch.setattr(research_agent.app, "invoke", _raise(ValueError("our bug")))

    with pytest.raises(ValueError):
        client.post("/research", json={"question": "why?"})

    assert client.get("/metrics").json()["reliability"]["errors"] == {"ValueError": 1}


def test_health_reports_credential_presence_never_values(make_client, monkeypatch):
    """The clients are lazy, so a container with no keys starts up perfectly
    healthy and then fails every real request. Better to learn that from the
    deploy than from the first user."""
    client, _ = make_client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value")
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)

    body = client.get("/health").json()

    assert body["credentials"] == {"anthropic": True, "voyage": False}
    assert "secret-value" not in json.dumps(body)


def test_health_treats_an_empty_key_as_absent(make_client, monkeypatch):
    """An empty env var is a misconfigured deploy, not a configured one."""
    client, _ = make_client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    assert client.get("/health").json()["credentials"]["anthropic"] is False


def test_the_root_url_is_not_a_404(make_client):
    """A successful deploy whose front door returns FastAPI's bare
    `{"detail": "Not Found"}` is indistinguishable from a broken one."""
    client, _ = make_client()

    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["docs"] == "/docs"
    assert "health" in body["endpoints"]


def test_every_advertised_endpoint_actually_exists(make_client):
    """An index that lists a route the app doesn't serve is worse than no
    index at all."""
    client, _ = make_client()
    served = {
        (method, route.path)
        for route in service.app.routes
        for method in getattr(route, "methods", ())
    }

    for advertised in client.get("/").json()["endpoints"].values():
        method, path = advertised.split(" ", 1)
        assert (method, path) in served, advertised
