"""
API tests against the real FastAPI app with the Claude client stubbed.

The session store is pointed at a temp database via dependency override, so
these exercise genuine SQLite persistence and genuine graph traversal -- the
only thing faked is the network.
"""

import json
import threading
import time

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from test_graph_smoke import FakeClient
from test_memory_stores import FakeEmbedder

from research_agent import db, graph, identity, limits, service
from research_agent.memory import InMemoryStore, PgVectorMemoryStore
from research_agent.metrics import PostgresMetricsStore, SQLiteMetricsStore
from research_agent.sessions import PostgresSessionStore, SQLiteSessionStore

# The session read/delete routes fail closed, so every client the suite builds
# needs a credential. Configuring it here -- and sending it as a default header
# -- keeps the fixture the one place that knows about it, the way it already
# owns DEMO_RATE_LIMIT_PER_HOUR and SESSION_BACKEND. A test that wants the
# anonymous case builds a bare TestClient instead.
SESSIONS_TOKEN = "sessions-s3cret"

# The dependencies that count as "this route is not anonymous". `guard` fronts
# the money-spending routes; `require_sessions_token` fronts the session
# read/delete group. A route under /sessions carrying neither is open.
AUTH_DEPENDENCIES = {"guard", "require_sessions_token"}


def mint_cookie(monkeypatch, secret="test-identity-secret"):
    """A real signed identity token the middleware will accept.

    IdentityMiddleware is not a dependency, so it cannot be overridden the way
    the stores are -- and should not be: tests that need a fixed identity mint
    a genuine token under a pinned secret and present it as the ra_id cookie,
    exercising the real verify path. Later waves key limits and session
    ownership on this.
    """
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", secret)
    return identity.mint()


def api_routes(app):
    """Every APIRoute the app serves, including ones behind include_router.

    FastAPI 0.141 stopped flattening included routers into app.routes: an
    include leaves a single _IncludedRouter that resolves at match time.
    Filtering app.routes for APIRoute alone therefore finds nothing behind a
    router and iterates an empty list -- which is exactly how a guard test
    goes green over a wide-open service. Hence the recursion, and hence the
    non-vacuity assertion at every call site that reasons about auth.

    Returns (path, route) pairs with any include_router prefix composed in.
    Lives here rather than in a conftest.py because this repo has none: shared
    test helpers live in the module that owns the surface (this one owns the
    API) and are imported by name via pythonpath = [".", "src", "tests"].
    """
    from fastapi.routing import APIRoute

    try:
        from fastapi.routing import _IncludedRouter
    except ImportError:  # pragma: no cover - older fastapi flattens instead
        _IncludedRouter = ()

    found: list[tuple[str, APIRoute]] = []

    def walk(routes, prefix=""):
        for route in routes:
            if isinstance(route, APIRoute):
                found.append((prefix + route.path, route))
            elif _IncludedRouter and isinstance(route, _IncludedRouter):
                walk(route.original_router.routes, prefix + route.include_context.prefix)

    walk(app.routes)
    return found


def dependency_names(route) -> set[str]:
    """The names of the dependencies attached to a route.

    Router-level dependencies are visible here on the router's own APIRoute
    objects, so this sees both `dependencies=[...]` on the APIRouter and
    `dependencies=[...]` on the decorator.
    """
    return {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """Returns a factory so a test can script the critic before the app boots."""
    created = []

    # The app's lifespan builds a SessionStore at SESSION_DB_PATH before the
    # dependency override can redirect it. Without this, running the suite
    # drops a stray sessions.db next to the source.
    monkeypatch.setenv("SESSION_DB_PATH", str(tmp_path / "lifespan.db"))
    monkeypatch.setenv("METRICS_DB_PATH", str(tmp_path / "lifespan-metrics.db"))

    # The demo guardrails are off unless a test turns them on. Inheriting the
    # production defaults would make every test's result depend on how many
    # requests the tests before it happened to make.
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "0")
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "0")
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    monkeypatch.setenv("SESSIONS_TOKEN", SESSIONS_TOKEN)
    limits.reset_limiter()
    # The lifespan calls the backend factories, which follow DATABASE_URL.
    # Pinning them keeps these tests about the API rather than about whichever
    # database the surrounding environment happens to expose.
    monkeypatch.setenv("SESSION_BACKEND", "sqlite")
    monkeypatch.setenv("METRICS_BACKEND", "sqlite")

    def build(critic_verdicts=("APPROVED",) * 8):
        fake = FakeClient(critic_verdicts)
        monkeypatch.setattr(graph, "client", lambda: fake)
        graph.set_memory(InMemoryStore(embedder=FakeEmbedder()))

        store = SQLiteSessionStore(str(tmp_path / "sessions.db"))
        metrics = SQLiteMetricsStore(str(tmp_path / "metrics.db"))
        service.app.dependency_overrides[service.get_sessions] = lambda: store
        service.app.dependency_overrides[service.get_metrics] = lambda: metrics

        # https, not TestClient's default http: the identity cookie is Secure
        # (unconditionally -- no prod/test fork in a security attribute), and
        # httpx's jar silently withholds a Secure cookie over http. Under the
        # default base_url every request would re-mint a fresh identity and
        # the per-identity tests would pass vacuously.
        client = TestClient(
            service.app,
            base_url="https://testserver",
            headers={"x-demo-token": SESSIONS_TOKEN},
        )
        created.append((client, store, metrics))
        return client, fake

    yield build

    service.app.dependency_overrides.clear()
    graph.set_memory(None)
    limits.reset_limiter()
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
    assert body["dependencies"] == "ok"
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


@pytest.mark.parametrize("path", ["/sessions/nope", "/sessions/nope/trace"])
def test_unknown_sessions_are_401_without_a_token(make_client, path):
    """Auth runs before the handler, so an anonymous caller gets 401, not 404.

    That ordering is the point: answering 404 first would tell an
    unauthenticated caller which session IDs exist.
    """
    make_client()  # for the env and the dependency overrides
    with TestClient(service.app) as anonymous:
        assert anonymous.get(path).status_code == 401


# --------------------------------------------------------------------------
# The guarded sessions group
# --------------------------------------------------------------------------
#
# The defect this phase fixes passed a green suite for months because no test
# ever asked an unauthenticated question. These do.


@pytest.mark.parametrize(
    "method,template",
    [
        ("GET", "/sessions"),
        ("GET", "/sessions/{sid}"),
        ("GET", "/sessions/{sid}/trace"),
        ("DELETE", "/sessions/{sid}"),
    ],
)
def test_unauthenticated_sessions_routes_are_refused(make_client, method, template):
    """All four routes, against a real session id, from a caller with no header."""
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    with TestClient(service.app) as anonymous:
        response = anonymous.request(method, template.format(sid=sid))

    assert response.status_code == 401


def test_authorised_sessions_routes_still_work(make_client):
    """The other half of the same criterion: guarding them did not break them."""
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    listed = client.get("/sessions")
    assert listed.status_code == 200
    assert sid in [s["session_id"] for s in listed.json()["sessions"]]

    assert client.get(f"/sessions/{sid}").status_code == 200
    assert client.get(f"/sessions/{sid}/trace").status_code == 200
    assert client.delete(f"/sessions/{sid}").status_code == 204


def test_sessions_token_unset_fails_closed(make_client, monkeypatch):
    """Nothing configured means nobody passes -- 403, not 401 and not 200.

    The assertion is on 403 specifically. 401 would mean a caller could get in
    by guessing a token, and 200 would mean the hotfix had regressed to the
    original bug. That bug was not a missing control: it was a control that
    was present in the code and inert in production, which is exactly what an
    open-when-unset default reproduces.
    """
    client, _ = make_client()
    monkeypatch.delenv("SESSIONS_TOKEN", raising=False)
    monkeypatch.delenv("DEMO_TOKEN", raising=False)

    assert client.get("/sessions").status_code == 403


def test_demo_token_fallback_protects_the_session_routes(make_client, monkeypatch):
    """Setting only DEMO_TOKEN closes the group rather than leaving it open."""
    client, _ = make_client()
    client.post("/research", json={"question": "why?"})
    monkeypatch.delenv("SESSIONS_TOKEN", raising=False)
    monkeypatch.setenv("DEMO_TOKEN", "demo-only")

    with TestClient(service.app) as anonymous:
        assert anonymous.get("/sessions").status_code == 401

    with TestClient(service.app, headers={"x-demo-token": "demo-only"}) as holder:
        assert holder.get("/sessions").status_code == 200


def test_session_reads_not_metered_by_the_rate_limit_or_daily_cap(make_client, monkeypatch):
    """Reads carry the credential check and nothing else.

    Applying `guard` to them would have been the one-line fix, and it would
    have made listing sessions eat the caller's research quota and 429 every
    read once the daily cap was hit -- while the cap's own refusal message
    says "Read-only endpoints still work". A demo that hides its state at
    exactly the moment it starts refusing work is a demo you cannot debug.
    """
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    # Rate limit: one slot in the bucket, then several reads. If reads were
    # metered, the second one would be 429.
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    limits.reset_limiter()
    for _ in range(3):
        assert client.get("/sessions").status_code == 200
    assert client.get(f"/sessions/{sid}").status_code == 200
    assert client.get(f"/sessions/{sid}/trace").status_code == 200

    # Daily cap. This half only means anything if the cap is genuinely
    # exhausted: check_daily_cap returns early for a cap of 0, which is what
    # the fixture ships, so a read asserted under the defaults would pass
    # even if the cap were wired onto it. So record real spend first, then
    # set a positive-but-tiny cap, then prove the cap is live.
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "0")  # unlimited again
    limits.reset_limiter()
    client.post("/research", json={"question": "spend something"})
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "0.0000001")

    refused = client.post("/research", json={"question": "one too many"})
    assert refused.status_code == 429  # the cap is live, not dormant

    assert client.get("/sessions").status_code == 200
    assert client.get(f"/sessions/{sid}").status_code == 200
    assert client.get(f"/sessions/{sid}/trace").status_code == 200


def test_delete_rate_limited_after_the_hourly_limit(make_client, monkeypatch):
    """The destructive path is the one read-only reasoning does not cover.

    Order matters. Creating the sessions goes POST /research -> guard ->
    check_rate_limit, which shares the DELETE's per-IP bucket. Lowering the
    limit first would let the setup requests eat the only slot: the test would
    still go green, but for the wrong reason, and it would break the moment
    anyone raised the limit. Create first, then lower and reset.
    """
    client, _ = make_client()
    first = client.post("/research", json={"question": "one"}).json()["session_id"]
    second = client.post("/research", json={"question": "two"}).json()["session_id"]

    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    limits.reset_limiter()

    assert client.delete(f"/sessions/{first}").status_code == 204
    refused = client.delete(f"/sessions/{second}")

    assert refused.status_code == 429
    assert "Retry-After" in refused.headers


def test_delete_rate_limited_check_runs_after_the_token_check(make_client, monkeypatch):
    """An unauthorised caller must not be able to burn someone else's quota.

    Router dependencies run before decorator ones, so the credential check
    fires first and the request never reaches the limiter -- the same ordering
    limits.enforce already argues for.
    """
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    limits.reset_limiter()
    before = limits.limiter().tracked_keys()

    with TestClient(service.app) as anonymous:
        assert anonymous.delete(f"/sessions/{sid}").status_code == 401

    assert limits.limiter().tracked_keys() == before
    # The slot the refused caller could have burned is still there.
    assert client.delete(f"/sessions/{sid}").status_code == 204


def test_ask_still_anonymous_for_the_demos_second_turn(make_client):
    """POST /sessions/{id}/ask shares the prefix and must not share the guard.

    This is the demo's second turn. Grouping the endpoints by path prefix
    instead of by dependency would have swept it up and broken follow-ups for
    every anonymous visitor.
    """
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    with TestClient(service.app) as anonymous:
        response = anonymous.post(f"/sessions/{sid}/ask", json={"question": "and?"})

    assert response.status_code not in (401, 403)
    assert response.status_code == 200


def test_demo_stays_open_when_sessions_token_is_set(make_client):
    """The regression test for the failure mode that would end the project.

    The obvious remediation -- setting DEMO_TOKEN in production -- 401s every
    anonymous visitor, because the demo page sends no auth header at all.
    SESSIONS_TOKEN exists precisely so the session tree can be closed without
    closing the demo, and this asserts that setting it does not.
    """
    make_client()

    with TestClient(service.app) as anonymous:
        assert anonymous.post("/research/stream", json={"question": "why?"}).status_code == 200

        demo = anonymous.get("/demo")
        assert demo.status_code == 200
        assert demo.json()["token_required"] is False

        assert anonymous.get("/health").status_code == 200


def test_route_guard_invariant_over_the_sessions_tree():
    """No route under /sessions may be anonymous.

    Asserted over the route table rather than trusted to four decorators
    because the bug this phase exists to fix was four routes that each
    individually forgot one. A property checked against every route the app
    actually serves catches the fifth route nobody remembered, which a
    per-route review by construction cannot.

    Inspects the app object directly -- no client, nothing to boot.
    """
    routes = [
        (path, route) for path, route in api_routes(service.app) if path.startswith("/sessions")
    ]

    # This assertion is the point of the test. If a future FastAPI changes how
    # include_router stores routes, the walker above stops finding the session
    # group and everything below iterates an empty list and passes over a
    # wide-open service. Better to fail loudly and be fixed. Six is a count of
    # route *objects*, not of distinct paths: /sessions/{session_id} is served
    # by both a GET and a DELETE, so six objects span five paths. Do not lower
    # this to 5. (Same convention as the skip detector in test_store_contract.)
    assert len(routes) >= 6, f"the walker found only {len(routes)} /sessions routes; it is broken"

    unguarded = [
        (sorted(route.methods), path)
        for path, route in routes
        if not dependency_names(route) & AUTH_DEPENDENCIES
    ]
    # Asserted on the list, not on a boolean, so the failure names the route.
    assert unguarded == [], f"routes under /sessions with no auth dependency: {unguarded}"


def test_delete_carries_the_rate_limiter():
    """The destructive route is metered and the reads are not.

    Asserted structurally rather than behaviourally because the fixture runs
    with DEMO_RATE_LIMIT_PER_HOUR=0: driving enough real deletes to observe a
    429 is slower and more brittle than reading the wiring. The behavioural
    half exists too (test_delete_rate_limited_after_the_hourly_limit, which
    monkeypatches the limit) -- both are wanted, because a passing 429 test
    does not prove the reads stayed unmetered and this does.

    The shared-bucket consequence is documented on the DELETE decorator in
    service.py: the limiter's key space is the one research runs use, so an
    operator deleting many sessions consumes that IP's research quota. That
    is accepted for the hotfix.
    """
    session_routes = {}
    for path, route in api_routes(service.app):
        if path.startswith("/sessions") and "/ask" not in path:
            for method in route.methods:
                session_routes[(method, path)] = route

    # Non-vacuity again: four routes, one DELETE and three GETs.
    assert len(session_routes) >= 4, f"found only {sorted(session_routes)}"

    delete = session_routes[("DELETE", "/sessions/{session_id}")]
    assert "check_rate_limit" in dependency_names(delete)

    gets = [(key, route) for key, route in session_routes.items() if key[0] == "GET"]
    assert len(gets) == 3, sorted(key for key, _ in gets)
    metered_reads = [key for key, route in gets if "check_rate_limit" in dependency_names(route)]
    # Reads must stay unmetered: listing sessions may not consume the caller's
    # research quota (CONTEXT, Dependency composition).
    assert metered_reads == [], f"session reads must not be rate limited: {metered_reads}"

    # And none of the four may acquire the spend cap, so a later refactor
    # cannot quietly reach for `guard` -- which bundles check_daily_cap and
    # would 429 every read once the $5/day budget is gone, contradicting the
    # cap's own "Read-only endpoints still work" message.
    capped = [
        key
        for key, route in session_routes.items()
        if "check_daily_cap" in dependency_names(route)
    ]
    assert capped == [], f"session routes must not carry the daily cap: {capped}"


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

    monkeypatch.setattr(graph.app, "stream", explode)

    response = client.post("/research/stream", json={"question": "why?"})
    events = sse_events(response)

    assert [name for name, _ in events] == ["error"]
    assert events[0][1]["error"] == "APIConnectionError"


def test_sse_error_redacted_and_truncated(make_client, monkeypatch):
    """The error event lands in a browser, so it gets /health's treatment: one
    line, credentials substituted, and capped."""
    client, _ = make_client()

    def explode(state):
        raise ConnectionError(
            "connection failed: postgresql://user:sup3rsecret@host/db\n"
            + "second line with the rest of the parameters " * 6
        )

    monkeypatch.setattr(graph.app, "stream", explode)

    events = sse_events(client.post("/research/stream", json={"question": "why?"}))
    detail = events[0][1]["detail"]

    assert "sup3rsecret" not in detail
    assert "***@host/db" in detail          # redacted, not merely truncated
    assert "second line" not in detail      # only the first line
    assert len(detail) <= 160


def test_a_failed_stream_leaves_no_session_behind(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setattr(
        graph.app,
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
    monkeypatch.setattr(graph.app, "invoke", _raise(exc))

    assert client.post("/research", json={"question": "why?"}).status_code == expected


def test_a_failed_run_opens_no_session(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setattr(
        graph.app, "invoke", _raise(api_error(anthropic.RateLimitError, 429))
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

    assert body["model"] == graph.MODEL
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
        graph.app, "invoke", _raise(api_error(anthropic.RateLimitError, 429))
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
        graph.app,
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
    assert client.get("/health").json()["metrics"]["runs_recorded"] == 1


def test_an_unexpected_error_is_not_dressed_up_as_an_upstream_problem(make_client, monkeypatch):
    """A bug in our own code should surface as a 500, not a 502 blaming
    Anthropic for something we did."""
    client, _ = make_client()
    monkeypatch.setattr(graph.app, "invoke", _raise(ValueError("our bug")))

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


def _served_routes() -> set[tuple[str, str]]:
    """Every (method, path) the app actually serves.

    Recursive on purpose: fastapi no longer flattens an included router into
    app.routes, so a flat scan would silently miss every route on
    sessions_router and let this test pass over an index that advertises them.
    Built on api_routes() so there is one walker in this file, not two that
    can drift; every endpoint the index advertises is an APIRoute.
    """
    return {
        (method, path) for path, route in api_routes(service.app) for method in route.methods
    }


def test_every_advertised_endpoint_actually_exists(make_client):
    """An index that lists a route the app doesn't serve is worse than no
    index at all."""
    client, _ = make_client()
    served = _served_routes()
    assert ("GET", "/health") in served  # the walker found something

    for advertised in client.get("/").json()["endpoints"].values():
        # Entries may carry a trailing annotation, e.g. "(X-Demo-Token required)".
        method, path = advertised.split(" ")[:2]
        assert (method, path) in served, advertised


# --------------------------------------------------------------------------
# Liveness vs readiness
# --------------------------------------------------------------------------


class _Unreachable:
    """A store whose database has gone away."""

    path = "postgres://db.example.com/agent"

    def count(self):
        raise ConnectionError("connection to server at 10.0.0.1 failed: timeout expired")


def test_health_stays_200_when_a_store_is_unreachable(make_client, monkeypatch):
    """The bug this fixes: /health touched the database, so a paused
    free-tier Postgres made the check fail, which made Fly restart the
    machine, which did not reach the database either. A restart loop over a
    fault a restart cannot fix."""
    client, _ = make_client()
    service.app.dependency_overrides[service.get_sessions] = _Unreachable

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"                    # the process is alive
    assert body["dependencies"] == "degraded"        # and says what isn't
    assert body["unreachable"] == ["sessions"]
    assert body["sessions"]["reachable"] is False
    assert body["sessions"]["error"] == "ConnectionError"


def test_health_still_identifies_a_store_it_cannot_reach(make_client):
    """Backend and location come from the object, not the database, so they
    survive exactly the outage you most want them during."""
    client, _ = make_client()
    service.app.dependency_overrides[service.get_sessions] = _Unreachable

    sessions = client.get("/health").json()["sessions"]
    assert sessions["backend"] == "_Unreachable"
    assert sessions["location"] == "postgres://db.example.com/agent"


def test_ready_is_503_when_a_store_is_unreachable(make_client):
    """Readiness is where an unreachable store genuinely means "no traffic"."""
    client, _ = make_client()
    service.app.dependency_overrides[service.get_sessions] = _Unreachable

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_ready_is_200_when_everything_answers(make_client):
    client, _ = make_client()
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["unreachable"] == []
    assert all(body[d]["reachable"] for d in ("sessions", "metrics", "memory"))


def test_health_reports_all_three_stores(make_client):
    client, _ = make_client()
    body = client.get("/health").json()
    for dependency in ("sessions", "metrics", "memory"):
        assert body[dependency]["reachable"] is True


def test_a_probe_failure_does_not_leak_the_dsn(make_client):
    """psycopg echoes connection parameters back in some errors, and the DSN
    carries a password."""
    class LeakyStore(_Unreachable):
        def count(self):
            raise ConnectionError(
                "connection failed: postgresql://user:sup3rsecret@host/db\nmore detail"
            )

    client, _ = make_client()
    service.app.dependency_overrides[service.get_sessions] = LeakyStore

    detail = client.get("/health").json()["sessions"]["detail"]
    assert "sup3rsecret" not in detail
    assert "***@host/db" in detail          # redacted, not merely truncated
    assert "more detail" not in detail      # only the first line
    assert len(detail) <= 160


# --------------------------------------------------------------------------
# The /health timing budget
#
# Two different bounds, and conflating them is the whole hazard:
#
#   health_probe_deadline  -- the GENERAL bound. A store that hangs forever is
#                             reported unreachable when its wall clock runs
#                             out, whatever the pool was doing.
#   health_within_budget   -- the COLD-POOL bound only. Nothing is warm, so
#                             every probe pays a checkout timeout and the
#                             arithmetic happens to be PG_POOL_TIMEOUT-shaped.
#                             It says nothing about a warm partitioned pool.
# --------------------------------------------------------------------------


def test_health_probe_deadline_bounds_a_store_that_never_answers(make_client, monkeypatch):
    """The general bound, and the one that is not an arithmetic argument.

    A warm pool behind a partition hands out a checkout in ~0 ms and then
    blocks in libpq on a peer that has gone away: PG_POOL_TIMEOUT is already
    spent, PG_CONNECT_TIMEOUT never applied to an established connection, and
    a peer that keeps the socket alive while never answering is bounded by
    nothing libpq offers. The store here is a deterministic stand-in for that
    shape -- it blocks, with no network involved at all.

    Remove the deadline from `_probe` and this test does not fail, it *hangs*.
    That is what makes it falsifying rather than decorative.
    """
    monkeypatch.setenv("HEALTH_PROBE_BUDGET", "0.3")
    released = threading.Event()

    class _NeverAnswers:
        path = "postgres://db.example.com/agent"

        def count(self):
            # The 30 s is a backstop, not the mechanism: the test releases the
            # event in its `finally` so the abandoned worker finishes promptly
            # rather than making the interpreter's atexit join wait it out.
            released.wait(30)
            return 0

    client, _ = make_client()
    service.app.dependency_overrides[service.get_sessions] = _NeverAnswers
    try:
        started = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - started
    finally:
        released.set()
        service._shutdown_probes()

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"] == "degraded"
    assert body["sessions"]["reachable"] is False
    assert body["sessions"]["error"] == "TimeoutError"
    assert "0.3" in body["sessions"]["detail"]
    budget = 3 * 0.3 + 1.0
    assert elapsed < budget, f"/health took {elapsed:.2f}s against a {budget:.2f}s ceiling"


@pytest.fixture
def unreachable_postgres_stores(monkeypatch):
    """All three stores pointed at a blackhole address, cold.

    10.255.255.1 swallows packets rather than refusing them, so a connect
    hangs until it is bounded rather than failing instantly -- which is the
    case worth measuring. min_size=0 keeps pool construction from starting a
    background connect attempt whose disposal we would then wait on.

    The DSN password is deliberately distinctive: one of these tests asserts
    it never reaches the response body.
    """
    dsn = "postgresql://agent:sup3rsecret@10.255.255.1:5432/health_budget"
    monkeypatch.setenv("PG_POOL_TIMEOUT", "0.5")
    monkeypatch.setenv("PG_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "0")
    # Large enough that the deadline is not what is being measured here: this
    # test is about the cold-pool arithmetic, not about the general ceiling.
    monkeypatch.setenv("HEALTH_PROBE_BUDGET", "5.0")

    sessions = PostgresSessionStore(dsn=dsn)
    metrics = PostgresMetricsStore(dsn=dsn)
    notes = PgVectorMemoryStore(embedder=FakeEmbedder(), dsn=dsn, table="health_budget_notes")

    def install() -> str:
        """Redirect all three stores. Called AFTER make_client(), because the
        factory installs its own SQLite overrides and would undo these."""
        service.app.dependency_overrides[service.get_sessions] = lambda: sessions
        service.app.dependency_overrides[service.get_metrics] = lambda: metrics
        graph.set_memory(notes)
        return dsn

    try:
        yield install
    finally:
        for store in (sessions, metrics, notes):
            store.close()
        db.close_all_pools()


def test_health_within_budget_when_the_pool_is_cold(make_client, unreachable_postgres_stores):
    """The COLD-POOL bound only. `health_probe_deadline` is the general one.

    Nothing is warm, so each probe pays one checkout timeout and the cost is
    3 x PG_POOL_TIMEOUT. The margin is deliberately below 3 x 2 x the timeout,
    so a reintroduced retry of PoolTimeout -- which plan 11-01 removed
    precisely because it doubled this -- fails the test rather than merely
    slowing it.
    """
    client, _ = make_client()
    unreachable_postgres_stores()

    started = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"] == "degraded"
    assert sorted(body["unreachable"]) == ["memory", "metrics", "sessions"]
    ceiling = 3 * 0.5 + 0.8            # 2.3s; a reintroduced retry would cost 3.0s
    assert elapsed < ceiling, f"/health took {elapsed:.2f}s against a {ceiling:.2f}s ceiling"


def test_a_pool_failure_does_not_leak_the_dsn_password(make_client, unreachable_postgres_stores):
    """Not the same assertion as the redaction unit test above.

    That one hands `_redact` a string we wrote. This one takes whatever
    psycopg_pool actually says about a DSN it could not reach -- pool errors
    can echo conninfo -- and checks the *whole serialised body*, because a
    credential leaking through a field nobody thought to redact is exactly the
    failure a per-field assertion misses.
    """
    client, _ = make_client()
    dsn = unreachable_postgres_stores()
    assert "sup3rsecret" in dsn        # non-vacuity: there is a secret to leak

    body = client.get("/health").text

    assert body.count("sup3rsecret") == 0


# --------------------------------------------------------------------------
# Which machine answered
# --------------------------------------------------------------------------


def test_health_names_the_machine_that_answered(make_client, monkeypatch):
    """Without this, "the same session resolves on either machine" can only be
    demonstrated by reading `fly logs`: nothing in any response body says which
    machine served it."""
    monkeypatch.setenv("FLY_MACHINE_ID", "78156d2c32d738")
    client, _ = make_client()

    assert client.get("/health").json()["machine"] == "78156d2c32d738"


def test_health_machine_is_empty_rather_than_absent_off_fly(make_client, monkeypatch):
    """A missing key and an empty one are different failures to a caller
    parsing this, so the shape stays stable off Fly."""
    monkeypatch.delenv("FLY_MACHINE_ID", raising=False)
    client, _ = make_client()

    body = client.get("/health").json()
    assert "machine" in body
    assert body["machine"] == ""


# --------------------------------------------------------------------------
# Demo page and guardrails, through the real app
# --------------------------------------------------------------------------


def test_a_browser_gets_the_demo_page(make_client):
    client, _ = make_client()

    response = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Research agent</title>" in response.text


def test_curl_still_gets_the_json_index(make_client):
    """Content negotiation rather than a second URL: the machine-readable
    index has to keep working exactly as it did."""
    client, _ = make_client()

    body = client.get("/", headers={"accept": "*/*"}).json()

    assert body["docs"] == "/docs"
    assert "research" in body["endpoints"]


def test_the_demo_page_references_no_external_origin(make_client):
    """One self-contained file: no CDN, no fonts, no analytics. A strict CSP
    can then deny everything external, and the page still works offline."""
    client, _ = make_client()
    html = client.get("/", headers={"accept": "text/html"}).text

    for marker in ("http://", "https://", "//cdn", "<script src", "<link rel=\"stylesheet\""):
        assert marker not in html, marker


def test_demo_endpoint_reports_the_limits(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "7")
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    limits.reset_limiter()

    body = client.get("/demo").json()

    assert body["rate_limit_per_hour"] == 7
    assert body["daily_cap_usd"] == 5.00
    assert body["budget_exhausted"] is False


def test_the_rate_limit_refuses_a_flood(make_client, monkeypatch):
    client, fake = make_client()
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "2")
    limits.reset_limiter()

    first = client.post("/research", json={"question": "one"})
    second = client.post("/research", json={"question": "two"})
    third = client.post("/research", json={"question": "three"})

    assert (first.status_code, second.status_code) == (200, 200)
    assert third.status_code == 429
    assert "Retry-After" in third.headers
    # The refused request cost nothing: two runs' worth of calls, not three.
    assert fake.nodes_called().count("researcher") == 2


def test_the_daily_cap_refuses_new_runs(make_client, monkeypatch):
    """The per-run cap bounds one runaway run; this bounds the bill."""
    client, fake = make_client()
    client.post("/research", json={"question": "one"})  # records some spend
    fake.calls.clear()

    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "0.0000001")
    response = client.post("/research", json={"question": "two"})

    assert response.status_code == 429
    assert "daily budget" in response.json()["detail"]
    assert fake.calls == []  # nothing billable ran


def test_a_demo_token_gates_writes_but_not_reads(make_client, monkeypatch):
    """Read-only endpoints stay open: they cost nothing, and they are how you
    diagnose a service that is refusing work."""
    client, _ = make_client()
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")

    assert client.post("/research", json={"question": "why?"}).status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/", headers={"accept": "text/html"}).status_code == 200

    ok = client.post(
        "/research", json={"question": "why?"}, headers={"x-demo-token": "s3cret"}
    )
    assert ok.status_code == 200


def test_follow_ups_are_guarded_too(make_client, monkeypatch):
    """A follow-up is cheaper than a research run, not free."""
    client, _ = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    refused = client.post(f"/sessions/{session_id}/ask", json={"question": "and?"})
    assert refused.status_code == 401


def test_streaming_endpoints_are_guarded(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")

    assert client.post("/research/stream", json={"question": "why?"}).status_code == 401


def test_the_guard_runs_before_anything_is_spent(make_client, monkeypatch):
    """A refusal must not open a session or record a run.

    This test is about spend, not auth. Setting DEMO_TOKEN here refuses the
    POST; it does not change how the read below authenticates, because
    limits.sessions_token() prefers SESSIONS_TOKEN -- which the fixture set,
    and whose value the client sends by default -- and only falls back to
    DEMO_TOKEN when SESSIONS_TOKEN is unset.
    """
    client, _ = make_client()
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")

    client.post("/research", json={"question": "why?"})

    assert client.get("/sessions").json()["sessions"] == []
    assert client.get("/metrics").json()["runs"]["total"] == 0


# --------------------------------------------------------------------------
# Caller identity: mint-on-response, never 401
# --------------------------------------------------------------------------
#
# The property that breaks the demo if it regresses: a first-time visitor with
# no cookie hits POST /research/stream first, and that route returns a
# StreamingResponse directly -- where a dependency-set cookie is silently
# dropped. The middleware must carry the mint on every response shape the
# service produces, and must never refuse anyone.


def _cookie_header(response) -> str:
    """The raw Set-Cookie header for ra_id, or '' if none was sent."""
    for value in response.headers.get_list("set-cookie"):
        if value.startswith(f"{identity.COOKIE_NAME}="):
            return value
    return ""


def _assert_locked_attributes(header: str) -> None:
    assert header, "no ra_id Set-Cookie on the response"
    assert "HttpOnly" in header
    assert "SameSite=Lax" in header
    assert "Secure" in header
    assert f"Max-Age={identity.COOKIE_MAX_AGE}" in header


def test_mint_on_response_reaches_the_sse_stream(make_client):
    """The load-bearing shape: headers go out at http.response.start, before
    the stream body, so the SSE response can and must carry the cookie -- and
    the stream itself still completes with its terminal event."""
    make_client()
    with TestClient(service.app, base_url="https://testserver") as cookieless:
        response = cookieless.post("/research/stream", json={"question": "why?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in sse_events(response)]
    assert names[-1] == "result"  # the stream completed, body unaffected
    _assert_locked_attributes(_cookie_header(response))


def test_mint_on_response_reaches_the_demo_page(make_client):
    """GET / with an html Accept returns a FileResponse directly -- the second
    shape where a dependency-set cookie would vanish."""
    make_client()
    with TestClient(service.app, base_url="https://testserver") as cookieless:
        response = cookieless.get("/", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    _assert_locked_attributes(_cookie_header(response))


def test_mint_on_response_reaches_a_json_route(make_client):
    """The ordinary shape, asserted so all three are proven, not two."""
    make_client()
    with TestClient(service.app, base_url="https://testserver") as cookieless:
        response = cookieless.get("/health")

    assert response.status_code == 200
    _assert_locked_attributes(_cookie_header(response))


def test_a_valid_cookie_is_not_reminted(make_client, monkeypatch):
    """Mint only on absent-or-invalid: a caller presenting a good token keeps
    it, otherwise every response would rotate the identity that later waves
    key limits and ownership on."""
    make_client()
    token = mint_cookie(monkeypatch)
    with TestClient(service.app, base_url="https://testserver") as holder:
        holder.cookies.set(identity.COOKIE_NAME, token)
        response = holder.get("/health")

    assert response.status_code == 200
    assert _cookie_header(response) == ""


def test_a_returning_caller_keeps_the_identity_they_were_minted(make_client):
    """The round trip through the client's own jar: first response mints, the
    jar stores it (Secure, hence the https base_url), the second request
    presents it back, and no new mint happens."""
    make_client()
    with TestClient(service.app, base_url="https://testserver") as visitor:
        first = visitor.get("/health")
        second = visitor.get("/health")

    _assert_locked_attributes(_cookie_header(first))
    assert _cookie_header(second) == ""


def test_invalid_token_reminted_never_401(make_client, monkeypatch):
    """A tampered cookie is treated as absent: the request succeeds -- 200,
    explicitly not 401 -- and a fresh identity arrives on the response. An
    attacker who forges a token gains a new empty identity, never an error
    and never someone else's."""
    make_client()
    token = mint_cookie(monkeypatch)
    version, ident, sig = token.split(".")
    tampered = f"{version}.{ident}.{sig[:-1]}{'0' if sig[-1] != '0' else '1'}"

    with TestClient(service.app, base_url="https://testserver") as forger:
        forger.cookies.set(identity.COOKIE_NAME, tampered)
        stream = forger.post("/research/stream", json={"question": "why?"})

    assert stream.status_code != 401
    assert stream.status_code == 200
    assert [name for name, _ in sse_events(stream)][-1] == "result"
    fresh = _cookie_header(stream)
    _assert_locked_attributes(fresh)
    assert tampered not in fresh  # a fresh mint, not the forgery echoed back


def test_identity_state_is_populated_before_the_handler(monkeypatch):
    """request.state.identity is the contract every later wave keys on, so it
    must exist before any handler runs -- proven against the middleware
    directly, since no current route echoes it."""
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", "state-test-secret")
    seen = {}

    async def inner(scope, receive, send):
        seen["identity"] = scope["state"]["identity"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    # No `with`: the context manager runs lifespan, which this bare stub does
    # not speak. A plain request is all the property needs.
    client = TestClient(identity.IdentityMiddleware(inner), base_url="https://testserver")
    assert client.get("/anything").status_code == 200

    assert len(seen["identity"]) == 32 and seen["identity"].isalnum()
