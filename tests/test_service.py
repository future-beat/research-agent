"""
API tests against the real FastAPI app with the Claude client stubbed.

The session store is pointed at a temp database via dependency override, so
these exercise genuine SQLite persistence and genuine graph traversal -- the
only thing faked is the network.
"""

import base64
import concurrent.futures
import hashlib
import inspect
import json
import re
import threading
import time
from collections import Counter
from html.parser import HTMLParser

import anthropic
import httpx
import pytest
import test_graph_smoke

# Imported eagerly here on purpose, unlike in `service` and `memory`: the
# credential tests need the SDK's own typed exceptions, and asserting against
# anything else would be asserting against a stand-in for the contract.
import voyageai.error
from fastapi.testclient import TestClient
from test_graph_smoke import FakeClient
from test_memory_stores import FakeEmbedder, voyage_embedder

from research_agent import csp, db, graph, identity, limits, service
from research_agent import memory as memory_module
from research_agent import usage as usage_accounting
from research_agent.memory import InMemoryStore, PgVectorMemoryStore
from research_agent.metrics import FAILED, PostgresMetricsStore, SQLiteMetricsStore
from research_agent.sessions import PostgresSessionStore, SQLiteSessionStore

# Since Phase 12 this is the OPERATOR credential, not the visitor's: the
# default client sends it, so it sees every owner's sessions -- which is what
# most of this suite wants, since most of it is not about ownership. A test
# that wants a plain visitor drops the header (see `as_visitor`).
SESSIONS_TOKEN = "sessions-s3cret"

# The dependencies that count as "this route decides who is asking". `guard`
# fronts the money-spending routes; `require_session_access` fronts the session
# read/delete group. A route under /sessions carrying neither cannot know whose
# sessions it is serving, and is therefore open.
AUTH_DEPENDENCIES = {"guard", "require_session_access"}


def as_visitor(client):
    """The same client without the operator token: an ordinary caller.

    Mutates in place and returns it, because the identity cookie already in the
    jar is the point -- a fresh TestClient would be a different person.
    """
    client.headers.pop("x-demo-token", None)
    return client


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


class RecordingLimits(limits.InMemoryLimits):
    """The real in-memory store, plus a note of what it was asked to do.

    Behaviour is unchanged -- every call delegates -- so a test asserting on
    `reserved`/`settled` is reading the app's actual traffic, not a fake's idea
    of it. Needed because "the reservation was released" and "no reservation
    was ever made" look identical from the outside, and only one of them is the
    property being claimed.
    """

    def __init__(self):
        super().__init__()
        self.reserved: list[str] = []
        self.settled: list[str] = []

    def reserve(self, run_id, identity, est_usd, cap, spent_24h):
        self.reserved.append(run_id)
        return super().reserve(run_id, identity, est_usd, cap, spent_24h)

    def settle(self, run_id):
        self.settled.append(run_id)
        super().settle(run_id)


def limits_store() -> RecordingLimits:
    """The store make_client injected into the app under test."""
    return service.app.dependency_overrides[service.get_limits]()


def metrics_store():
    """The metrics store make_client injected, for reading settled spend back.

    Same accessor shape as `limits_store` above. Note that every client built
    from one `make_client` fixture shares the same database file, so a test
    comparing two runs reads the delta rather than the total.
    """
    return service.app.dependency_overrides[service.get_metrics]()


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
        # A fresh limits store per client, injected the same way. The rate
        # window and the spend reservations used to be process globals reset by
        # hand between cases; a per-client store means a test can no longer
        # inherit another's hits, and `limits_store()` below lets a test read
        # the reservations the app actually made.
        limits_backend = RecordingLimits()
        service.app.dependency_overrides[service.get_sessions] = lambda: store
        service.app.dependency_overrides[service.get_metrics] = lambda: metrics
        service.app.dependency_overrides[service.get_limits] = lambda: limits_backend

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
    # The credential cache is module state: without this, a verdict one test
    # probed for would be served warm to the next one in file order, and the
    # cold-read assertions would pass or fail depending on collection order.
    service._reset_credential_cache()
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
    separate request, and may not reach the same process.

    The reborn client carries the same identity cookie, because that is what a
    real returning browser does -- the cookie outlives the process by 400 days.
    Since Phase 12 a session belongs to whoever created it, so a genuinely
    different caller would (correctly) get a 404 here, and asserting on that
    would be asserting the opposite of what this test is about.

    Handed to the constructor rather than set on the jar afterwards:
    `client.cookies.set(..., domain="testserver")` looks equivalent and is
    silently not sent, which shows up as a mysterious fresh identity.
    """
    client, fake = make_client()
    session_id = client.post("/research", json={"question": "why?"}).json()["session_id"]

    with TestClient(  # new client, same store, same caller
        service.app, base_url="https://testserver", cookies={"ra_id": client.cookies["ra_id"]}
    ) as reborn:
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
def test_unknown_sessions_are_404_without_a_token(make_client, path):
    """A credential-less caller gets 404 -- and so does everyone else.

    This asserted 401 before Phase 12, and the reasoning was that answering 404
    first would tell an unauthenticated caller which ids exist. The concern was
    right; the mechanism has been replaced by a stronger one. There is no
    longer any answer that distinguishes ids, for any caller: missing, expired
    and foreign are one 404 with one body. The oracle is closed by making every
    door look the same rather than by refusing to open any of them.
    """
    make_client()  # for the env and the dependency overrides
    with TestClient(service.app, base_url="https://testserver") as visitor:
        assert visitor.get(path).status_code == 404


# --------------------------------------------------------------------------
# The guarded sessions group
# --------------------------------------------------------------------------
#
# The defect Phase 10.5 fixed passed a green suite for months because no test
# ever asked an unauthenticated question. These do -- and since Phase 12 the
# answer they must get has changed shape: a stranger is refused because the
# session is not theirs, not because they hold no shared secret.


@pytest.mark.parametrize(
    "method,template",
    [
        ("GET", "/sessions/{sid}"),
        ("GET", "/sessions/{sid}/trace"),
        ("DELETE", "/sessions/{sid}"),
    ],
)
def test_a_stranger_is_refused_on_every_session_route(make_client, method, template):
    """A real session id, a caller who is not its owner, all three id routes.

    404 rather than 401/403, uniformly: see `_require`. The stranger here holds
    a perfectly valid identity of their own -- this is not "no credential", it
    is "not yours", which is the harder case and the one that actually happens
    when a session id is pasted into a chat.
    """
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    with TestClient(service.app, base_url="https://testserver") as stranger:
        response = stranger.request(method, template.format(sid=sid))

    assert response.status_code == 404
    assert response.json()["detail"] == f"No session {sid!r}."


def test_a_stranger_sees_an_empty_listing_not_someone_elses(make_client):
    """The collection route's half of the same property: 200 and nothing."""
    client, _ = make_client()
    client.post("/research", json={"question": "why?"})

    with TestClient(service.app, base_url="https://testserver") as stranger:
        listed = stranger.get("/sessions")

    assert listed.status_code == 200
    assert listed.json()["sessions"] == []


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


def test_an_unset_sessions_token_closes_only_the_operator_view(make_client, monkeypatch):
    """The Phase 12 inversion, end to end.

    Before, an unset SESSIONS_TOKEN meant nobody could read any session -- the
    fail-closed posture that kept a forgotten secret from silently reopening
    the world-readable leak. Now the leak is closed by ownership instead, so an
    unset token closes exactly one thing: the cross-owner debugging view. The
    caller still reaches their own sessions, and -- the half that matters --
    still cannot reach anyone else's, with the operator header now inert.
    """
    client, _ = make_client()
    mine = client.post("/research", json={"question": "mine"}).json()["session_id"]

    with TestClient(service.app, base_url="https://testserver") as other:
        theirs = other.post("/research", json={"question": "theirs"}).json()["session_id"]

    monkeypatch.delenv("SESSIONS_TOKEN", raising=False)
    monkeypatch.delenv("DEMO_TOKEN", raising=False)

    # Still sending the now-unconfigured operator header: it must buy nothing.
    listed = client.get("/sessions")
    assert listed.status_code == 200
    assert [s["session_id"] for s in listed.json()["sessions"]] == [mine]
    assert client.get(f"/sessions/{theirs}").status_code == 404


def test_demo_token_fallback_still_reaches_the_operator_view(make_client, monkeypatch):
    """Setting only DEMO_TOKEN still buys the operator view, as it always has.

    The fallback is what makes "setting DEMO_TOKEN protects the session
    endpoints" true rather than quietly false; Phase 12 changed what the token
    unlocks, not which variables name it.
    """
    client, _ = make_client()
    mine = client.post("/research", json={"question": "why?"}).json()["session_id"]
    monkeypatch.delenv("SESSIONS_TOKEN", raising=False)
    monkeypatch.setenv("DEMO_TOKEN", "demo-only")

    with TestClient(service.app, base_url="https://testserver") as visitor:
        assert visitor.get("/sessions").json()["sessions"] == []

    with TestClient(
        service.app, base_url="https://testserver", headers={"x-demo-token": "demo-only"}
    ) as operator:
        listed = operator.get("/sessions")
        assert listed.status_code == 200
        # Not merely 200: the operator sees a session it does not own.
        assert mine in [s["session_id"] for s in listed.json()["sessions"]]


# --------------------------------------------------------------------------
# Session ownership (Phase 12, criterion 3)
# --------------------------------------------------------------------------


def _two_owners(make_client):
    """Two real identities with one session each, plus an operator client.

    The operator client is the fixture's own (it sends SESSIONS_TOKEN); the
    two visitors are separate TestClients, each minted its own cookie by the
    middleware on its first response, with the operator header removed. Real
    cookies through the real verify path -- IdentityMiddleware is not a
    dependency and must not be faked into agreeing.
    """
    operator, _ = make_client()
    alice = as_visitor(TestClient(service.app, base_url="https://testserver"))
    bob = as_visitor(TestClient(service.app, base_url="https://testserver"))
    a_sid = alice.post("/research", json={"question": "alice's"}).json()["session_id"]
    b_sid = bob.post("/research", json={"question": "bob's"}).json()["session_id"]
    assert alice.cookies["ra_id"] != bob.cookies["ra_id"], "the two clients are the same caller"
    return operator, alice, a_sid, bob, b_sid


def test_sessions_listing_scoped_and_dual_mode(make_client):
    """GET /sessions shows you yours; the operator token shows everyone's."""
    operator, alice, a_sid, bob, b_sid = _two_owners(make_client)

    assert [s["session_id"] for s in alice.get("/sessions").json()["sessions"]] == [a_sid]
    assert [s["session_id"] for s in bob.get("/sessions").json()["sessions"]] == [b_sid]

    all_sessions = {s["session_id"] for s in operator.get("/sessions").json()["sessions"]}
    assert {a_sid, b_sid} <= all_sessions, "the operator view is not unscoped"

    alice.close()
    bob.close()


def test_foreign_session_is_indistinguishable(make_client):
    """The 404 for someone else's session is byte-identical to a missing one.

    Asserted as an equality between two responses rather than as two separate
    status-code checks, because the property is *indistinguishability*: a 403,
    a differing detail string, or even a differing set of keys would each hand
    a stranger an existence oracle on ids that travel in shared URLs. Run over
    both id-shaped read routes.
    """
    operator, alice, a_sid, bob, _ = _two_owners(make_client)
    missing = "0" * 32

    for template in ("/sessions/{}", "/sessions/{}/trace"):
        foreign = bob.get(template.format(a_sid))
        absent = bob.get(template.format(missing))

        assert foreign.status_code == absent.status_code == 404
        assert foreign.json()["detail"] == f"No session {a_sid!r}."
        assert absent.json()["detail"] == f"No session {missing!r}."
        # Same shape, same wording, differing only in the id echoed back.
        assert foreign.json().keys() == absent.json().keys()
        assert foreign.json()["detail"].replace(a_sid, missing) == absent.json()["detail"]

    # Non-vacuity: the id really does name a live session for its owner.
    assert alice.get(f"/sessions/{a_sid}").status_code == 200

    alice.close()
    bob.close()


def test_expired_session_is_indistinguishable_from_missing(make_client, monkeypatch):
    """And so is one that timed out -- same route, same body, same status."""
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]
    assert client.get(f"/sessions/{sid}").status_code == 200  # live first

    # Zero days: everything written before this instant is already idle too long.
    monkeypatch.setenv("SESSION_TTL_DAYS", "0")

    expired = client.get(f"/sessions/{sid}")
    absent = client.get("/sessions/" + "0" * 32)
    assert expired.status_code == 404
    assert expired.json()["detail"] == f"No session {sid!r}."
    assert expired.json().keys() == absent.json().keys()
    assert client.get("/sessions").json()["sessions"] == []
    # Even the operator, who bypasses ownership, does not bypass expiry.
    assert client.get(f"/sessions/{sid}/trace").status_code == 404


def test_delete_owner_or_operator(make_client):
    """Owner: 204. Operator: 204. Anyone else: the missing-session 404."""
    operator, alice, a_sid, bob, b_sid = _two_owners(make_client)
    missing = "0" * 32

    # A third party is refused exactly as they would be on an invented id.
    refused = bob.delete(f"/sessions/{a_sid}")
    absent = bob.delete(f"/sessions/{missing}")
    assert refused.status_code == absent.status_code == 404
    assert refused.json()["detail"] == f"No session {a_sid!r}."
    # ...and the refusal is a refusal, not a silent success.
    assert alice.get(f"/sessions/{a_sid}").status_code == 200

    assert alice.delete(f"/sessions/{a_sid}").status_code == 204  # the owner
    assert operator.delete(f"/sessions/{b_sid}").status_code == 204  # the operator
    assert bob.get(f"/sessions/{b_sid}").status_code == 404  # really gone

    alice.close()
    bob.close()


def test_a_session_records_the_identity_that_created_it(make_client):
    """The thread from the cookie to the row, asserted end to end."""
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    owner = client.get(f"/sessions/{sid}").json()["owner"]
    assert owner, "the session was created with no owner"
    # The cookie is v1.<id>.<hmac>; the stored owner is that middle id.
    assert client.cookies["ra_id"].split(".")[1] == owner


def _run_and_count_recall(client, path: str, question: str) -> int:
    """Start a research run and report how many stored notes its researcher
    pulled into the prompt.

    Handles both shapes: the blocking route answers with a session id whose
    trace is read back, the streaming one carries the trace in its final
    `result` event. Parametrising over the two is not decoration -- the demo
    page uses the streaming route, so an owner threaded only through the
    blocking one would be scoping the path nobody uses.
    """
    response = client.post(path, json={"question": question})
    assert response.status_code == 200, response.text
    if path.endswith("/stream"):
        trace = sse_events(response)[-1][1]["trace"]
    else:
        session_id = response.json()["session_id"]
        trace = client.get(f"/sessions/{session_id}/trace").json()["trace"]
    researcher = [entry for entry in trace if entry.get("node") == "researcher"][-1]
    return researcher["recalled_from_memory"]


@pytest.mark.parametrize("path", ["/research", "/research/stream"])
def test_one_visitors_notes_never_reach_another_visitors_run(make_client, path):
    """The cross-visitor prompt-injection path, closed end to end.

    This is the reason note scoping exists, and it is worth being precise
    about the attack: recalled notes are pasted verbatim into the researcher
    prompt, the researcher's output becomes the draft, and the critic reviews
    that draft. Text one visitor caused to be written was therefore text that
    reached another visitor's critic -- untrusted input on the path to
    APPROVED. Bounding it to the caller is what closes that.

    Both directions, because either alone is satisfiable by a bug. Alice
    recalling her own note proves the recall path still works at all -- a
    store that returned nothing to anybody would pass the isolation half
    vacuously. And the shared-store assertion at the end proves Bob's zero is
    isolation rather than an empty store: all three notes are sitting in one
    backend, which is exactly the deployed topology.
    """
    question = "langgraph supervisor retry patterns"
    alice, _ = make_client()  # the fixture installs one InMemoryStore for the app

    assert _run_and_count_recall(alice, path, question) == 0, "nothing was stored yet"
    assert _run_and_count_recall(alice, path, question) >= 1, "a visitor lost their own memory"

    # A different visitor, same question, same note store, no operator token:
    # an ordinary stranger holding a valid identity of their own.
    with TestClient(service.app, base_url="https://testserver") as bob:
        assert _run_and_count_recall(bob, path, question) == 0, (
            "another visitor's notes reached this run's researcher, and therefore its critic"
        )

    assert len(graph.memory()) == 3, (
        "the three runs did not share one note store; the isolation above proved nothing"
    )


def _state_constructions(source: str) -> list[str]:
    """Every initial_state(...) / followup_state(...) call in a handler.

    Parentheses are matched rather than regexed to the first `)`, because
    `followup_state(session.state, body.cleaned(), owner=owner)` would
    otherwise be truncated at `cleaned(` and the owner argument -- the only
    thing this is looking for -- would never be seen.
    """
    found = []
    for match in re.finditer(r"(?:initial|followup)_state\(", source):
        depth, index = 0, match.end() - 1
        while index < len(source):
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        found.append(source[match.start():index + 1])
    return found


def test_every_run_starting_route_scopes_the_run_to_its_caller():
    """No route may start a run that does not know whose notes it may read.

    A tripwire, not the proof -- the proof is the behavioural test above, and
    it covers the two routes that actually touch the note store (a follow-up
    never runs the researcher). This exists because that behavioural test
    cannot cover the ask routes at all, and a control that only two of four
    call sites are checked for is the exact shape of the bug this codebase has
    now hit eleven times.

    Written as "every state construction carries an owner" rather than "the
    handler source mentions owner=" on purpose: three of these handlers pass
    `owner=owner` to something ELSE as well (store.create, reserve_or_429), so
    the looser form stays green when the state construction alone loses it.
    That mutation was run.
    """
    starters = {}
    for path, route in api_routes(service.app):
        constructions = _state_constructions(inspect.getsource(route.endpoint))
        if constructions:
            starters[(sorted(route.methods)[0], path)] = constructions

    # Non-vacuity: /research, /research/stream, and the two ask routes.
    assert len(starters) == 4, f"walker found {sorted(starters)}"

    unscoped = [
        (key, call)
        for key, calls in starters.items()
        for call in calls
        if "owner=" not in call
    ]
    assert unscoped == [], f"runs started without an owner: {unscoped}"


def test_a_reads_do_not_extend_a_sessions_life(make_client, monkeypatch):
    """Listing your sessions must not renew them. The service half of the
    store contract test, over the real HTTP path, because a renewal added in a
    handler rather than in the store would slip past that one."""
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]
    first = client.get(f"/sessions/{sid}").json()["updated_at"]

    for _ in range(3):
        assert client.get("/sessions").status_code == 200
        assert client.get(f"/sessions/{sid}/trace").status_code == 200

    assert client.get(f"/sessions/{sid}").json()["updated_at"] == first


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
    for _ in range(3):
        assert client.get("/sessions").status_code == 200
    assert client.get(f"/sessions/{sid}").status_code == 200
    assert client.get(f"/sessions/{sid}/trace").status_code == 200

    # Daily cap. This half only means anything if the cap is genuinely
    # exhausted: the reservation is skipped entirely for a cap of 0, which is
    # what the fixture ships, so a read asserted under the defaults would pass
    # even if the cap were wired onto it. So record real spend first, then
    # set a positive-but-tiny cap, then prove the cap is live.
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "0")  # unlimited again
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
    check_rate_limit, which shares the DELETE's per-identity bucket. Lowering
    the limit first would let the setup requests eat the only slot: the test
    would still go green, but for the wrong reason, and it would break the
    moment anyone raised the limit. Create first, then lower.
    """
    client, _ = make_client()
    first = client.post("/research", json={"question": "one"}).json()["session_id"]
    second = client.post("/research", json={"question": "two"}).json()["session_id"]

    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")

    assert client.delete(f"/sessions/{first}").status_code == 204
    refused = client.delete(f"/sessions/{second}")

    assert refused.status_code == 429
    assert "Retry-After" in refused.headers


def test_a_stranger_cannot_burn_the_owners_delete_quota(make_client, monkeypatch):
    """A refused DELETE must cost the refused caller, never the owner.

    Phase 10.5 got this from ordering: the shared-credential check sat on the
    router and fired before the limiter, so an unauthorised caller never
    reached the bucket at all. Phase 12 removed that check, and the refusal
    (404, in the handler) now happens *after* the limiter runs. The property
    survives anyway, for a better reason: the bucket is keyed on identity, so
    the slot a stranger burns is their own. Asserted by leaving the owner with
    a working DELETE after the stranger has spent the only slot there is.

    (A stolen cookie is out of scope by construction: replaying it makes you
    the owner for every purpose, including deleting the session outright, so a
    rate-limit slot is not the interesting loss. That is the documented meaning
    of "identity is possession of the token".)
    """
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")

    with TestClient(service.app, base_url="https://testserver") as stranger:
        assert stranger.delete(f"/sessions/{sid}").status_code == 404
        # The stranger's own slot is the one that went.
        assert stranger.delete(f"/sessions/{sid}").status_code == 429

    assert client.delete(f"/sessions/{sid}").status_code == 204


def test_ask_needs_no_operator_token_for_the_demos_second_turn(make_client):
    """POST /sessions/{id}/ask shares the prefix and must not share the guard.

    This is the demo's second turn, taken by a visitor who has never seen
    SESSIONS_TOKEN. Grouping the endpoints by path prefix instead of by
    dependency would have swept it up and broken follow-ups for every visitor.
    The caller here is the session's owner -- as the real one always is, since
    the cookie is minted at page load, before the first question -- and carries
    no credential at all.
    """
    client, _ = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]

    response = as_visitor(client).post(f"/sessions/{sid}/ask", json={"question": "and?"})

    assert response.status_code not in (401, 403)
    assert response.status_code == 200


def test_ask_on_someone_elses_session_is_404(make_client):
    """The follow-up route enforces ownership in the handler, not in its
    dependency set -- so this is the assertion that it enforces it at all."""
    client, fake = make_client()
    sid = client.post("/research", json={"question": "why?"}).json()["session_id"]
    fake.calls.clear()

    with TestClient(service.app, base_url="https://testserver") as stranger:
        response = stranger.post(f"/sessions/{sid}/ask", json={"question": "and?"})

    assert response.status_code == 404
    assert response.json()["detail"] == f"No session {sid!r}."
    assert fake.calls == [], "a refused follow-up must not have spent anything"


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


def test_the_session_group_and_the_ask_routes_carry_different_dependencies():
    """The structural half of Phase 12's ownership surgery.

    Two assertions that are easy to conflate and must not be. Every route in
    the read/delete group carries `require_session_access`, so a future
    `/sessions/{id}/notes` cannot ship not knowing whose sessions it is
    serving. And the ask routes deliberately do NOT carry it: they enforce
    ownership inside the handler instead, because dependency sets group by what
    they protect (ADR-0006 part 4) and a run is not a listing. Attaching the
    session dependency to them would re-fight that argument silently.
    """
    session_group = []
    ask_routes = []
    for path, route in api_routes(service.app):
        if not path.startswith("/sessions"):
            continue
        (ask_routes if "/ask" in path else session_group).append((path, route))

    assert len(session_group) >= 4, f"walker found only {session_group}"
    assert len(ask_routes) >= 2, f"walker found only {ask_routes}"

    # The ROUTER's own declaration, not just the routes'. Every handler also
    # injects `access` to read the value, and `dependency_names` cannot tell
    # the two sources apart -- so deleting the router-level dependency leaves
    # the per-route assertion below still green while quietly removing the
    # thing it is really protecting: that the NEXT route under this prefix
    # inherits access control without its author having to remember anything.
    # That inheritance is the entire argument of ADR-0006 part 4, and it is
    # exactly what four routes forgot four times before Phase 10.5.
    router_level = {
        getattr(d.dependency, "__name__", "") for d in service.sessions_router.dependencies
    }
    assert "require_session_access" in router_level, (
        f"sessions_router declares {router_level or 'no'} dependencies; membership must be "
        "structural, not repeated per route"
    )

    missing = [
        (sorted(route.methods), path)
        for path, route in session_group
        if "require_session_access" not in dependency_names(route)
    ]
    assert missing == [], f"session routes not carrying require_session_access: {missing}"

    for path, route in ask_routes:
        names = dependency_names(route)
        assert "guard" in names, f"{path} lost the spending guard"
        assert "require_session_access" not in names, (
            f"{path} took the session-tree dependency; ownership belongs in its handler"
        )
        # And it does enforce ownership, in the only place the route table
        # cannot see -- the same in-handler shape the reserve gate reads.
        assert "_require(store, session_id, owner)" in inspect.getsource(route.endpoint)


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
    assert "rate_limit" in dependency_names(delete)

    gets = [(key, route) for key, route in session_routes.items() if key[0] == "GET"]
    assert len(gets) == 3, sorted(key for key, _ in gets)
    metered_reads = [key for key, route in gets if "rate_limit" in dependency_names(route)]
    # Reads must stay unmetered: listing sessions may not consume the caller's
    # research quota (CONTEXT, Dependency composition).
    assert metered_reads == [], f"session reads must not be rate limited: {metered_reads}"

    # And none of the four may acquire the spend cap, so a later refactor
    # cannot quietly reach for `guard` -- which would 429 every read once the
    # $5/day budget is gone, contradicting the cap's own "Read-only endpoints
    # still work" message.
    #
    # Two ways to acquire it since Phase 12, so both are checked: as the
    # `guard` dependency, and as an in-handler `reserve_or_429` call, which no
    # amount of reading the route's dependencies would ever reveal.
    #
    # Note what this assertion is and is not, now that the cap has moved. It is
    # a structural tripwire against a future edit re-attaching the cap to a
    # read; it is NOT the proof that a capped caller can still read. That proof
    # is behavioural and lives in 12-03's gates:
    # test_all_spending_routes_reserve (below) asserts GET /sessions and
    # GET /sessions/{id} answer 200 while the cap is exhausted, and
    # test_limits.test_reads_survive_the_cap asserts the refusal still makes
    # the promise those reads keep.
    capped = [
        key
        for key, route in session_routes.items()
        if "guard" in dependency_names(route)
        or "reserve_or_429" in inspect.getsource(route.endpoint)
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


def test_pricing_payload_carries_multipliers_windows_and_embedding(make_client, monkeypatch):
    """The three additive sections, asserted by shape and never by which
    window happens to be current today.

    Values that depend on the calendar are checked the way this file already
    checks the input rate -- membership in the set of rates on file -- so the
    suite reads the same on 2026-08-31 and on 2026-09-01.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.9")
    client, _ = make_client()
    body = client.get("/pricing").json()

    # Nothing a deployed consumer already reads has moved.
    assert body["model"] == graph.MODEL
    assert set(body["usd_per_mtok"]) == {"input", "output", "cache_write_5m", "cache_read"}
    assert body["web_search_usd_per_request"] == 0.01
    assert body["max_run_cost_usd"] > 0

    # /pricing reports what is in effect, not what the defaults are.
    assert body["multipliers"]["cost_discount_factor"] == 0.9
    assert body["multipliers"]["inference_geo_multiplier"] > 0
    assert "usage.inference_geo" in body["multipliers"]["inference_geo_note"]

    current = body["windows"]["current"]
    assert set(current["usd_per_mtok"]) == {"input", "output", "cache_write_5m", "cache_read"}
    assert current["usd_per_mtok"]["input"] in (2.0, 3.0)
    # Present and nullable. Which of the two it is depends on today's date,
    # and asserting either would be an assertion about the calendar.
    assert "next" in body["windows"]
    upcoming = body["windows"]["next"]
    assert upcoming is None or set(upcoming) == {"since", "until", "usd_per_mtok"}

    assert body["embedding"]["model"] == memory_module.EMBEDDING_MODEL
    assert body["embedding"]["usd_per_mtok"] > 0
    assert "approximation" in body["embedding"]["note"]


def test_pricing_501_when_the_embedding_model_is_unpriced(make_client, monkeypatch):
    """The embedding provider fails as loud as the LLM one. A service that
    cannot say what its embeddings cost is misconfigured, and DEC-12's rule
    is that a misconfiguration is never reported as $0.00."""
    monkeypatch.setattr(memory_module, "EMBEDDING_MODEL", "voyage-4")
    client, _ = make_client()

    response = client.get("/pricing")

    assert response.status_code == 501
    assert "voyage-4" in response.json()["detail"]


def test_payload_additive_for_deployed_consumers(make_client):
    """Phase 12's rollout constraint, as a test rather than as a promise.

    The demo page and anything else reading these payloads is deployed
    separately from the service, so for a window of time an old consumer
    talks to a new service. New keys are free; a renamed or removed one is a
    broken client that cannot be fixed at the same instant.

    Written as explicit name sets rather than a snapshot: the point is that
    *these particular* names survive, and a snapshot that gets regenerated
    when it fails proves nothing.
    """
    client, _ = make_client()

    cost = client.get("/metrics").json()["cost"]
    pre_phase_cost_keys = {
        "total_usd", "avg_usd_per_run", "model_calls", "input_tokens",
        "output_tokens", "cache_read_tokens", "cache_creation_tokens", "web_searches",
    }
    assert pre_phase_cost_keys <= set(cost)
    assert {"embedding_tokens", "embedding_requests", "embedding_usd"} <= set(cost)

    body = client.post("/research", json={"question": "why?"}).json()
    pre_phase_run_fields = {
        "session_id", "mode", "task", "topic_type", "answer", "approved",
        "forced_stop_reason", "revision_count", "max_revisions", "iterations",
        "max_iterations", "retries", "usage", "cost_usd", "trace",
    }
    assert pre_phase_run_fields <= set(body)
    # The usage dict is where this phase added keys; it may grow, and the
    # fields around it may not.
    assert {"calls", "cost_usd", "pricing_unknown"} <= set(body["usage"])


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
    # The signing secret is the one credential here whose leak is directly
    # exploitable: it forges any caller's identity cookie. It gets the same
    # presence-not-value treatment and its own leak assertion.
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", "hunter2-secret-value")

    body = client.get("/health").json()

    # Pinned by name rather than by whole-dict equality since Phase 19: the
    # block now grows with validity fields, and an `==` here would turn every
    # additive change into a failure while saying nothing about the property
    # this test is actually for -- that presence is reported and the value
    # never is.
    credentials = body["credentials"]
    assert credentials["anthropic"] is True
    assert credentials["voyage"] is False
    assert credentials["identity_signing"] is True
    assert "secret-value" not in json.dumps(body)


def test_health_reports_an_unset_signing_secret_as_false(make_client, monkeypatch):
    """False here is the operator's only signal that a two-machine fleet is
    minting per-process ephemeral identities -- a cookie from one machine will
    not verify on the other, and visitors silently lose their sessions."""
    client, _ = make_client()
    monkeypatch.delenv("IDENTITY_SIGNING_SECRET", raising=False)

    assert client.get("/health").json()["credentials"]["identity_signing"] is False


def test_health_treats_an_empty_key_as_absent(make_client, monkeypatch):
    """An empty env var is a misconfigured deploy, not a configured one."""
    client, _ = make_client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    assert client.get("/health").json()["credentials"]["anthropic"] is False


# --------------------------------------------------------------------------
# Credential validity: does the key actually WORK
#
# Presence and validity are different facts. The block below is about the
# second one, and every test here runs keyless-by-default with a fake provider
# behind the same seam production calls -- a probe that reached the real
# network would break the suite's keyless invariant, not just cost money.
# --------------------------------------------------------------------------


def settle_credential_probes(timeout=5.0):
    """Wait for whatever refresh /health kicked off, instead of sleeping.

    `_credential_inflight` is the single-refresh guard and the test seam in one
    object. The worker writes the cache and only then pops itself in its
    `finally`, so a snapshot that comes back empty means the write has already
    happened rather than that nothing ran -- which is what makes this
    deterministic rather than a race dressed up as a wait.
    """
    inflight = list(service._credential_inflight.values())
    _, not_done = concurrent.futures.wait(inflight, timeout=timeout)
    assert not not_done, "a credential refresh did not land inside the timeout"


def test_health_credential_valid_true_after_the_probe_lands(make_client, monkeypatch):
    """The whole path in one test: cold read, fire-and-forget refresh, warm read.

    The cold read is the load-bearing half. /health must answer from the cache
    it has -- `null`, meaning "not yet known" -- rather than waiting on a
    provider, because the endpoint Fly restarts a machine over cannot be
    allowed to inherit a third party's latency.
    """
    client, fake = make_client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-not-a-real-key")

    cold = client.get("/health").json()["credentials"]

    assert cold["anthropic_valid"] is None
    assert cold["anthropic_checked_at"] is None
    assert cold["anthropic_error"] is None
    # Additive only: the presence booleans keep their names, their type and
    # their meaning beside the new fields.
    assert cold["anthropic"] is True
    assert cold["voyage"] is False
    assert cold["identity_signing"] in (True, False)

    settle_credential_probes()
    warm = client.get("/health").json()["credentials"]

    assert warm["anthropic_valid"] is True
    assert isinstance(warm["anthropic_checked_at"], float)
    assert warm["anthropic_error"] is None
    assert warm["anthropic"] is True

    probes = [kwargs for node, kwargs in fake.calls_with_kwargs if node == "credential_probe"]
    assert probes, "green without a provider call would be a vacuous pass"
    assert probes[0]["model"] == graph.MODEL


def install_voyage(monkeypatch, total_tokens=25, error=None):
    """A real VoyageEmbedder behind a fake client, reached the production way.

    The probe finds its embedder through `graph.memory().embedder` and calls
    `embed_query` on it, which is the same seam a run uses -- so these tests
    exercise the wrapper that reports tokens, not a stand-in that doesn't.
    """
    monkeypatch.setenv("VOYAGE_API_KEY", "pa-dummy-not-a-real-key")
    embedder = voyage_embedder(total_tokens=total_tokens, error=error)
    graph.set_memory(InMemoryStore(embedder=embedder))
    return embedder


def test_health_credential_invalid_key_reads_false(make_client, monkeypatch):
    """A provider that REJECTED us is the one case that is a verdict."""
    client, _ = make_client()
    install_voyage(monkeypatch, error=voyageai.error.AuthenticationError("401 unauthorized"))

    client.get("/health")
    settle_credential_probes()
    credentials = client.get("/health").json()["credentials"]

    assert credentials["voyage_valid"] is False
    assert credentials["voyage"] is True


def test_health_credential_provider_down_reads_null_with_an_error(make_client, monkeypatch):
    """An outage is "could not determine", never "your key is bad".

    Both halves are asserted because neither is sufficient alone: `null` by
    itself does not distinguish an outage from a key nobody has probed yet,
    and that distinction is the entire reason the error field exists. Report
    this as `false` and an operator spends the outage rotating a key that was
    never the problem.
    """
    client, _ = make_client()
    install_voyage(monkeypatch, error=voyageai.error.APIConnectionError("connection refused"))

    client.get("/health")
    settle_credential_probes()
    credentials = client.get("/health").json()["credentials"]

    assert credentials["voyage_valid"] is None
    assert credentials["voyage_error"] == "APIConnectionError"


def test_health_credential_error_never_carries_the_sdk_message(make_client, monkeypatch):
    """/health is deliberately unauthenticated, so this block is world-readable.

    An SDK's error message is not guaranteed free of the request that caused
    it. Storing the exception CLASS keeps the diagnostic and drops the payload.
    """
    leaked = "pa-l3aked-from-an-sdk-message"
    client, _ = make_client()
    install_voyage(
        monkeypatch,
        error=voyageai.error.AuthenticationError(f"401 for key {leaked}"),
    )

    client.get("/health")
    settle_credential_probes()
    response = client.get("/health")

    assert leaked not in response.text
    assert response.json()["credentials"]["voyage_error"] == "AuthenticationError"


def test_health_credential_probe_spend_is_excluded_from_the_embedding_meter(
    make_client, monkeypatch
):
    """The probe's tokens reach no run's bill, and that is by construction.

    `report_embedding` is a no-op unless a meter is open in the calling
    context, and the probe runs on a pool thread that has none -- so there is
    no special case to keep in sync, and no run to attribute it to either.

    The second half is the whole test. A meter reading zero is exactly what an
    embedder that never reports anything would also produce, so the same
    embedder is called directly inside the same meter and must report: without
    that control this test would pass against a broken accounting seam.
    """
    client, _ = make_client()
    embedder = install_voyage(monkeypatch, total_tokens=25)

    with usage_accounting.embedding_meter() as meter:
        client.get("/health")
        settle_credential_probes()

        assert embedder._client.calls, "the probe never embedded anything"
        assert meter.total_tokens == 0

        embedder.embed_query("the positive control")
        assert meter.total_tokens == 25


def test_health_credential_absent_key_reads_null_and_never_probes(make_client, monkeypatch):
    """A missing key is a presence fact. It is never a validity verdict.

    `false` here would send an operator hunting a bad key when what they have
    is no key at all -- and would spend a provider call to say it. `null`
    means "nobody asked", which is exactly true.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    probed = []

    def never_call_me():
        probed.append(1)

    for name in service._CREDENTIAL_PROBES:
        monkeypatch.setitem(service._CREDENTIAL_PROBES[name], "probe", never_call_me)

    client, _ = make_client()
    credentials = client.get("/health").json()["credentials"]

    for name in ("anthropic", "voyage"):
        assert credentials[name] is False
        assert credentials[f"{name}_valid"] is None
        assert credentials[f"{name}_checked_at"] is None
        assert credentials[f"{name}_error"] is None
    assert probed == [], "an unconfigured key was sent to a provider"


def test_health_credential_single_refresh_while_one_is_in_flight(make_client, monkeypatch):
    """Three reads, one refresh. Fly polls /health forever; without this guard
    the probe rate would track request volume rather than the TTL, and a
    provider's rate limit would be the thing that eventually stopped it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-not-a-real-key")
    started, release, calls = threading.Event(), threading.Event(), []

    def blocking_probe():
        calls.append(1)
        started.set()
        release.wait(30)  # a backstop; the `finally` is the mechanism

    monkeypatch.setitem(service._CREDENTIAL_PROBES["anthropic"], "probe", blocking_probe)
    client, _ = make_client()

    try:
        client.get("/health")
        assert started.wait(5), "the first read never kicked a refresh"
        client.get("/health")
        client.get("/health")

        assert calls == [1]
        assert list(service._credential_inflight) == ["anthropic"]
    finally:
        release.set()

    settle_credential_probes()

    assert calls == [1]
    assert client.get("/health").json()["credentials"]["anthropic_valid"] is True


def test_health_credential_cache_is_reused_within_the_ttl(make_client, monkeypatch):
    """A landed verdict is served, not re-earned -- and does get re-earned once
    it goes stale, which is the half that keeps the first half honest.

    Note the TTL is monkeypatched rather than set through CREDENTIAL_PROBE_TTL:
    P-02's 30 s floor clamps the env var, so a test driving it that way would
    be measuring the clamp and quietly proving nothing.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-not-a-real-key")
    client, fake = make_client()

    def probe_count():
        return sum(1 for node, _ in fake.calls_with_kwargs if node == "credential_probe")

    client.get("/health")
    settle_credential_probes()
    first = client.get("/health").json()["credentials"]["anthropic_checked_at"]
    calls_after_first = probe_count()

    second = client.get("/health").json()["credentials"]["anthropic_checked_at"]

    assert second == first
    assert probe_count() == calls_after_first

    # Now expire it: the same read path must go back to the provider.
    monkeypatch.setattr(service, "credential_probe_ttl", lambda: 0.0)
    client.get("/health")
    settle_credential_probes()

    assert probe_count() == calls_after_first + 1
    assert client.get("/health").json()["credentials"]["anthropic_checked_at"] > first


def test_health_credential_probe_ttl_floors_at_flys_check_interval(monkeypatch):
    """The floor is Fly's own 30 s check interval.

    Below it every liveness check would find the cache stale, and a mistuned
    env var would turn /health into a per-request prober against a provider's
    rate limit. A garbage value falls back rather than raising: /health failing
    to render because someone typed a word into a duration is the endpoint
    failing at its one job.
    """
    monkeypatch.setenv("CREDENTIAL_PROBE_TTL", "0.5")
    assert service.credential_probe_ttl() == 30.0

    monkeypatch.setenv("CREDENTIAL_PROBE_TTL", "not-a-number")
    assert service.credential_probe_ttl() == 300.0

    monkeypatch.delenv("CREDENTIAL_PROBE_TTL", raising=False)
    assert service.credential_probe_ttl() == 300.0


def test_health_never_waits_on_a_hanging_credential_probe(make_client, monkeypatch):
    """The invariant the whole design exists for.

    Fly restarts a machine whose liveness check fails. If /health waited on a
    provider, a provider's outage would become our restart loop -- taking down
    the endpoints that were still working, and fixing nothing, because a
    restart does not repair someone else's API.

    The bound is three orders of magnitude above the store probes' measured
    ~3 ms, so it is immune to CI jitter while still being falsified instantly
    by a `.result()` anywhere on the read path.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-not-a-real-key")
    release = threading.Event()

    def never_answers():
        release.wait(30)

    monkeypatch.setitem(service._CREDENTIAL_PROBES["anthropic"], "probe", never_answers)
    client, _ = make_client()

    try:
        started = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - started
    finally:
        # Never leave a worker blocked into the next test.
        release.set()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["credentials"]["anthropic_valid"] is None
    assert elapsed < 1.0, f"/health waited {elapsed:.2f}s on a provider that never answered"


def test_ready_carries_no_credentials_block(make_client, monkeypatch):
    """Readiness is about stores. Mixing provider validity in here would
    re-create the restart hazard one hop away: /ready returns 503, the load
    balancer drains the machine, and a third party's outage takes the service
    off the air even though every store it owns is answering fine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-not-a-real-key")
    client, _ = make_client()

    body = client.get("/ready").json()

    assert "credentials" not in body
    assert body["status"] == "ready"


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
        # Entries may carry a trailing annotation, e.g. "(your own)".
        method, path = advertised.split(" ")[:2]
        assert (method, path) in served, advertised


def test_index_does_not_claim_a_token_is_required_for_a_reachable_endpoint(make_client):
    """The index's auth annotations must not be false.

    test_every_advertised_endpoint_actually_exists checks only that the
    method+path is served -- the annotation text rides along unchecked, which
    is exactly how three entries went on claiming `X-Demo-Token required` for
    a full phase after Phase 12 made the session reads caller-scoped. A live
    GET /sessions with no header returned 200 against release v8 while the
    index still called the token required.

    The gate: for every advertised GET whose annotation says a token is
    required, a plain tokenless caller must actually be refused. An endpoint
    that answers 200 without the header makes the annotation a lie.
    """
    client, _ = make_client()
    index = client.get("/").json()["endpoints"]

    checked = 0
    for advertised in index.values():
        if "required" not in advertised.lower():
            continue
        method, path = advertised.split(" ")[:2]
        if method != "GET" or "{" in path:
            continue
        checked += 1
        response = client.get(path)
        assert response.status_code in (401, 403), (
            f"index advertises {advertised!r} but a tokenless caller got "
            f"{response.status_code} -- the annotation is false"
        )

    # Non-vacuity: today NO entry claims a token is required, so `checked` is
    # legitimately 0. Assert the shape we actually expect rather than letting
    # a silently-empty loop pass for a real check.
    assert checked == 0, (
        "an entry now claims a token is required; the loop above verified it "
        "-- update this baseline deliberately"
    )
    assert "X-Demo-Token required" not in " ".join(index.values())


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

    body = client.get("/demo").json()

    assert body["rate_limit_per_hour"] == 7
    assert body["daily_cap_usd"] == 5.00
    assert body["budget_exhausted"] is False


def test_the_rate_limit_refuses_a_flood(make_client, monkeypatch):
    client, fake = make_client()
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "2")

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


# --------------------------------------------------------------------------
# The spend reservation: every spending route, every terminal arm
# --------------------------------------------------------------------------
#
# `guard` gets its structural guarantee for free -- it is a route dependency,
# so the walker can see it, and test_route_guard_invariant_over_the_sessions_tree
# fails the moment a route appears without one. `reserve_or_429` cannot have
# that: the reservation needs a run_id, which does not exist until the handler
# has built the run state, so it is an IN-HANDLER call that no amount of
# reading route.dependant would ever reveal.
#
# That is precisely the shape ADR-0006 was written about -- "a control you have
# to remember to repeat is a control that will be forgotten" -- and it was
# forgotten four times before, on these same /sessions routes. So the reserve
# is held by two gates instead of one: a behavioural test that drives all four
# routes to a real 429, and a structural one that reads each handler's source.
# Deleting the reserve from `ask` alone fails both.

SPENDING_PATHS = [
    "/research",
    "/research/stream",
    "/sessions/{session_id}/ask",
    "/sessions/{session_id}/ask/stream",
]


@pytest.mark.parametrize("path", SPENDING_PATHS)
def test_all_spending_routes_reserve(make_client, monkeypatch, path):
    """Every route that spends money is refused once the budget is gone.

    The follow-up routes are in the parametrization deliberately: they are the
    cheap ones, they are the ones a reader is most likely to think do not need
    the check, and they are the ones that were missed last time.
    """
    client, fake = make_client()
    session_id = client.post("/research", json={"question": "seed"}).json()["session_id"]
    fake.calls.clear()

    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "0.0000001")
    response = client.post(path.format(session_id=session_id), json={"question": "one more"})

    assert response.status_code == 429, f"{path} did not reserve against the cap"
    assert "Read-only endpoints still work." in response.json()["detail"]
    assert fake.calls == []  # refused before anything billable ran

    # And the sentence in that refusal is true: reads still answer while capped.
    assert client.get("/sessions").status_code == 200
    assert client.get(f"/sessions/{session_id}").status_code == 200


def test_every_spending_route_calls_reserve():
    """The structural half. Costs no run, so it holds even for a route whose
    behavioural test someone deletes as flaky."""
    endpoints = {
        path: route for path, route in api_routes(service.app) if path in SPENDING_PATHS
    }
    # Non-vacuity first: a walker that found nothing would pass the loop below
    # over an empty dict, which is how a gate like this goes quietly green.
    assert len(endpoints) >= 4, f"found only {sorted(endpoints)}"

    missing = [
        path
        for path, route in endpoints.items()
        if "reserve_or_429" not in inspect.getsource(route.endpoint)
    ]
    assert missing == [], f"spending routes with no cap reservation: {missing}"


def test_reservation_settles_on_the_success_arms(make_client, monkeypatch):
    """A finished run's estimate must stop counting: its real cost is in the
    metrics table by then, and leaving both would double-count the run."""
    client, _ = make_client()
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "100.00")  # generous, but live
    store = limits_store()

    assert client.post("/research", json={"question": "why?"}).status_code == 200
    assert client.post("/research/stream", json={"question": "and?"}).status_code == 200

    assert len(store.reserved) == 2, store.reserved  # non-vacuity: it did reserve
    assert sorted(store.settled) == sorted(store.reserved)
    assert store.reservation_ids() == set()


def test_a_failed_run_settles_its_reservation(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "100.00")
    store = limits_store()

    def explode(state):
        # An upstream failure rather than a bug in ours: _http_error maps it to
        # a 503, so the response is a real one and TestClient does not re-raise
        # it -- which would leave this asserting on an exception rather than on
        # the reservation.
        raise anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )

    monkeypatch.setattr(graph.app, "invoke", explode)
    assert client.post("/research", json={"question": "why?"}).status_code >= 500

    assert store.reserved  # non-vacuity
    assert store.reservation_ids() == set()


def test_a_failed_stream_settles_its_reservation(make_client, monkeypatch):
    """The arm that is easy to forget. `_stream` swallows the exception to
    terminate the SSE cleanly, so the handler's own except never runs -- if the
    settle is not next to the failure record, every failed stream leaks a
    reservation until the staleness cutoff catches it."""
    client, _ = make_client()
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "100.00")
    store = limits_store()

    def explode(state):
        raise RuntimeError("the graph fell over mid-stream")

    monkeypatch.setattr(graph.app, "stream", explode)
    response = client.post("/research/stream", json={"question": "why?"})

    assert [name for name, _ in sse_events(response)] == ["error"]  # it did fail
    assert store.reserved  # and it did reserve
    assert store.reservation_ids() == set()


def test_a_persistence_failure_still_puts_the_run_in_the_ledger(make_client, monkeypatch):
    """A run that finished and then failed to persist is spend that happened.

    The v1.1 milestone audit found `_execute`'s try wrapping only the graph
    call, with `on_complete` and `metrics.record` outside it -- while `_stream`
    had both inside. So a session-store failure on the BLOCKING route raised
    past the ledger: the run never reached the runs table, and `spend_since`
    (the daily cap's only input) was blind to that run's cost forever. The
    leaked reservation self-healed at the staleness cutoff; the missing row
    never did.

    Both routes are asserted here, together, because the defect was the
    asymmetry rather than either route alone -- and both are asserted on the
    COST, not merely on the row count: `RunRecord.from_state` reads cost out of
    `state["usage"]`, so recording the pre-invoke state files a row worth $0.00
    and leaves the cap exactly as blind, with a passing row-count gate on top.
    """
    client, _ = make_client()
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "100.00")  # generous, but live
    store = limits_store()
    metrics = metrics_store()
    sessions = service.app.dependency_overrides[service.get_sessions]()

    def boom(*args, **kwargs):
        raise RuntimeError("the session store fell over after the run finished")

    monkeypatch.setattr(sessions, "create", boom)

    # Blocking. _http_error maps a RuntimeError to nothing, so it re-raises and
    # TestClient hands it back rather than turning it into a 500 response.
    with pytest.raises(RuntimeError):
        client.post("/research", json={"question": "why?"})

    assert store.reserved, "vacuous: the cap was off and nothing reserved"
    assert metrics.count() == 1, "the run never reached the ledger"
    assert store.reservation_ids() == set(), "the reservation leaked"
    blocking_cost = metrics.spend_since(0.0)
    assert blocking_cost > 0, "recorded, but at $0.00 -- the cap is still blind"

    # Streaming, same failure. The generator swallows the exception to
    # terminate the SSE cleanly, so this arm is invisible to the handler.
    response = client.post("/research/stream", json={"question": "and?"})

    # The nodes all ran, so the stream is a full one that failed at the very
    # end -- the terminal event is what carries the verdict.
    assert [name for name, _ in sse_events(response)][-1] == "error"
    assert len(store.reserved) == 2
    assert store.reservation_ids() == set()
    assert metrics.count() == 2
    assert metrics.spend_since(0.0) > blocking_cost, "the stream's spend vanished"


def test_a_failed_persist_records_the_finished_states_cost(monkeypatch):
    """The failure record is built from the state the GRAPH produced.

    `RunRecord.from_state` reads cost out of `state["usage"]`, and today the
    graph's nodes mutate the dict they were handed, so the pre-invoke state and
    the finished one are the same object -- which makes this indistinguishable
    through the app and invisible to the test above. That is an implementation
    detail of how the nodes return state, not a property anything guarantees;
    the day a node returns a fresh dict, recording `state` would file every
    failed-after-finish run at $0.00 and the daily cap would silently
    under-count. So this drives `_execute` directly with a graph that returns a
    NEW object, which is the only shape where the two can be told apart.
    """
    finished = {"run_id": "r1", "mode": "research", "usage": {"cost_usd": 0.31, "calls": 4}}
    monkeypatch.setattr(graph.app, "invoke", lambda _state: finished)

    class Ledger:
        def __init__(self):
            self.records = []

        def record(self, run):
            self.records.append(run)

    def boom(_final):
        raise RuntimeError("the session store fell over after the run finished")

    ledger, store = Ledger(), RecordingLimits()
    with pytest.raises(RuntimeError):
        service._execute({"run_id": "r1", "mode": "research"}, ledger, store, boom)

    assert [record.cost_usd for record in ledger.records] == [0.31]
    assert ledger.records[0].status == FAILED  # it is a failure, not a success

    # The streaming twin, driven the same way. Its `final_state` comes off the
    # chunk rather than off `invoke`, so it needs its own pin -- and the whole
    # point of W1 was that these two drifted apart once already.
    monkeypatch.setattr(graph.app, "stream", lambda _state: iter([{"writer": finished}]))
    ledger = Ledger()
    events = list(service._stream({"run_id": "r1", "mode": "research"}, ledger, store, boom))

    assert "event: error" in events[-1]  # it did fail
    assert [record.cost_usd for record in ledger.records] == [0.31]


def test_settle_sees_multiplied_cost(make_client, monkeypatch):
    """Reserve -> run -> record -> settle carries the multiplied cost, once.

    The whole premise of Phase 14 is that multipliers apply at
    `CallUsage.cost_usd` and every consumer inherits them for free. That is a
    claim about code nobody edited, so only a run can check it: the number in
    the API response and the number the daily cap will read back out of the
    runs table both have to move, by exactly the configured factor and no more.

    Written as ratios against an unmultiplied baseline rather than against
    hand-copied prices, so it keeps working when the Sonnet 5 introductory
    window closes in three weeks. The two failure modes it exists to catch are
    both red by construction: applying the discount a second time downstream
    gives 0.25, and a consumer that reads a pre-multiplier number gives 1.0.

    The cap is turned ON. `make_client` ships `DEMO_DAILY_USD_CAP=0`, under
    which `reserve_or_429` returns before reserving anything -- and "the
    reservation is gone afterwards" is trivially true of a reservation that was
    never made.
    """
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "100.00")  # generous, but live
    monkeypatch.delenv("COST_DISCOUNT_FACTOR", raising=False)
    monkeypatch.delenv("INFERENCE_GEO_MULTIPLIER", raising=False)

    # -- Run A: list price, nothing configured -----------------------------
    client, _ = make_client()
    metrics = metrics_store()
    reservations = limits_store()

    body = client.post("/research", json={"question": "why?"}).json()
    c0 = body["cost_usd"]
    s0 = metrics.spend_since(0.0)

    assert c0 > 0  # non-vacuity: a $0.00 run makes every ratio below trivial
    assert s0 == pytest.approx(c0)  # the settled row IS the reported cost
    assert reservations.reserved  # non-vacuity: the cap was live and reserved
    assert reservations.reservation_ids() == set()  # and the run settled it

    # -- Run B: the same run at a negotiated half price --------------------
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.5")
    client_b, _ = make_client()
    metrics_b = metrics_store()
    spent_before_b = metrics_b.spend_since(0.0)  # the file is shared with run A

    c1 = client_b.post("/research", json={"question": "why?"}).json()["cost_usd"]
    s1 = metrics_b.spend_since(0.0) - spent_before_b

    assert c1 == pytest.approx(c0 * 0.5)
    assert s1 == pytest.approx(c1)
    assert limits_store().reservation_ids() == set()

    # -- Run C: and the geo rate composes with it, on the token half -------
    # The response reports where inference ran; the fake carries the field as a
    # class attribute so every call in this run declares it. The published 1.1x
    # is scoped to token pricing categories, so the per-search fee -- which
    # this run does incur, two of them -- takes the discount and not the geo.
    monkeypatch.setattr(test_graph_smoke.Usage, "inference_geo", "us", raising=False)
    client_c, _ = make_client()
    metrics_c = metrics_store()
    spent_before_c = metrics_c.spend_since(0.0)

    body_c = client_c.post("/research", json={"question": "why?"}).json()
    c2 = body_c["cost_usd"]
    s2 = metrics_c.spend_since(0.0) - spent_before_c

    fee = body_c["usage"]["web_search_requests"] * usage_accounting.WEB_SEARCH_USD_PER_REQUEST
    assert fee > 0  # non-vacuity: the fee/token split below is a real split
    assert c2 == pytest.approx(((c0 - fee) * 1.1 + fee) * 0.5)
    assert s2 == pytest.approx(c2)
    assert c2 > c1  # the geo rate is a surcharge, and it survived the discount


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


# --------------------------------------------------------------------------
# Criterion 6: the first paint a stranger sees
#
# ROADMAP criterion 6 is that someone following a link from a resume reaches a
# working demo with zero added friction. Phase 12 gave the page an identity, an
# owned-session list and a resume flow, and the whole risk of that work is that
# it shows up before the first question. The constraint (12-UI-SPEC AC1) is that
# a cleared-storage first visit differs from the pre-phase page by exactly TWO
# text deltas -- the footer identity sentence, and the reworded #limits line --
# and by nothing else.
#
# These are static-file assertions: they read the file the service serves and
# need no client, no server and no browser. They are gates on a property a human
# would otherwise have to re-check by eye on every future edit, which is the
# same as not checking it.
# --------------------------------------------------------------------------


def _demo_page() -> str:
    """The exact file `GET /` serves, located the way the service locates it.

    Via service.DEMO_PAGE rather than a path assembled here, so moving the file
    cannot leave these gates reading a stale copy and passing.
    """
    with open(service.DEMO_PAGE, encoding="utf-8") as handle:
        return handle.read()


class _FirstPaintText(HTMLParser):
    """Every run of visible text in the markup, in document order.

    Script and style contents are skipped -- they are not paint. Whitespace is
    collapsed so that reindenting the markup is not a "change".
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._suppressed = 0
        self.runs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._suppressed += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._suppressed -= 1

    def handle_data(self, data):
        if self._suppressed:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.runs.append(text)


# Measured on the pre-phase tree (2026-08-05) and then re-measured after the
# Phase 12 page work: the ONLY difference between the two is the footer
# sentence, inserted at index 4. Anything else -- a banner, a consent line, an
# empty-state message, a "loading your sessions" placeholder -- adds or changes
# a run here and turns this red.
class _MarkupTags(HTMLParser):
    """Every element the served markup declares, and every attribute on it.

    The attribute half was added for the CSP gates below: they need to know that
    no tag carries an `on*` handler or a `style=`, and the walk that already
    visits every start tag is the right place to learn it. `handle_starttag`
    was always handed `attrs` and always dropped them; recording them opens no
    second parser over the same file.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attributes: list[tuple[str, str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for name, value in attrs:
            self.attributes.append((tag, name, value))

    def census(self) -> dict[str, int]:
        return dict(sorted(Counter(self.tags).items()))


# Measured: identical to the pre-phase census except `div` 2 -> 3, which is the
# footer identity sentence. Note what is NOT here and must never be: `details`
# and `summary`. The owned-session list is built in script and inserted only
# when it has rows, so an empty one cannot render on a first visit.
FIRST_PAINT_TAGS = {
    "a": 4, "body": 1, "button": 1, "div": 3, "footer": 1, "form": 1,
    "h1": 1, "head": 1, "header": 1, "html": 1, "input": 1, "meta": 2,
    "p": 2, "script": 1, "span": 1, "style": 1, "title": 1,
}

FIRST_PAINT_TEXT = (
    "Research agent",
    "Research agent",
    "Asks a question, searches the web, drafts a report, then fact-checks that "
    "draft against its own research notes and revises until every claim is "
    "grounded. Watch the critic push back.",
    "Research",
    "Your sessions and notes are private to this browser and expire after 7 days of inactivity.",
    "/docs",
    "·",
    "/metrics",
    "·",
    "/health",
    "·",
    "/pricing",
)

# Measured baseline, 12-UI-SPEC AC7, unchanged by this phase. Asserted as SETS:
# adding a value fails even though the count of declarations went up, which is
# what makes "no new sizes or weights" falsifiable rather than decorative.
FONT_SIZES = {".78rem", ".82rem", ".85em", ".88em", ".9rem", ".95rem", "1.15rem", "1.6rem"}
FONT_WEIGHTS = {"600", "700"}

# The `font:` shorthand also sets a size and a weight, so a gate that only reads
# the longhands can be walked straight past with `font: 1.1rem/1.6 serif`. These
# are the only two shorthand values on the page.
FONT_SHORTHANDS = {
    "inherit",
    '16px/1.6 ui-serif, Georgia, "Times New Roman", serif',
}


def test_page_keeps_innerhtml_at_zero():
    """Measured baseline on the current tree: 0.

    Session task text and model output are both untrusted input, and the page
    renders both. `el()`/`textContent` is the rule; one `innerHTML` anywhere in
    this file is a stored-XSS primitive, so the gate is zero rather than "not
    many".
    """
    page = _demo_page()

    # Non-vacuity: prove we read the real file before asserting an absence.
    assert "textContent" in page and len(page) > 5000

    assert page.count("innerHTML") == 0


def test_page_font_sets_unchanged():
    """The SETS of declared font sizes and weights equal the AC7 baselines.

    Set equality, not a count and not a `>= 1`: a new size raises the number of
    declarations, so a count-based gate stays green for exactly the change it
    exists to catch. This is the machine-checkable half of "the first visit
    looks like it always did".
    """
    page = _demo_page()
    # Real declarations only. Scanning the whole file matched a CSS comment
    # that quotes `font: inherit` while explaining why it is there -- a gate
    # that reads prose is a gate that can be fooled by prose in either
    # direction.
    declared = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
    css = re.sub(r"/\*.*?\*/", "", declared, flags=re.S)

    sizes = {m.strip() for m in re.findall(r"font-size:\s*([^;}]+)", css)}
    weights = {m.strip() for m in re.findall(r"font-weight:\s*([^;}]+)", css)}
    shorthands = {m.strip() for m in re.findall(r"(?<!-)\bfont:\s*([^;}]+)", css)}

    assert sizes == FONT_SIZES
    assert weights == FONT_WEIGHTS
    assert shorthands == FONT_SHORTHANDS

    # The other way a size could arrive: set from script, where no CSS gate
    # would ever see it. The page styles nothing from JS and must not start.
    script = re.search(r"<script>(.*?)</script>", page, re.S).group(1)
    assert "style" not in script


def test_page_first_paint_has_no_new_interactive_element():
    """AC1's other half: no new interactive element reachable before the first
    question.

    The text gate below cannot see this one -- an empty `<button>` or a
    `<details>` with a blank summary contributes no text run and sails past it,
    which was found by mutating that gate rather than by reading it. So the
    served markup's tag census is frozen outright. The measured baseline is the
    pre-phase census: Phase 12 adds ONE `div` (the footer sentence) and no
    interactive tag at all -- the session list is constructed at runtime and is
    the reason `details`/`summary` must not appear here.
    """
    parser = _MarkupTags()
    parser.feed(_demo_page())

    assert parser.census() == FIRST_PAINT_TAGS


def test_page_first_paint_text_is_frozen():
    """The visible text of the served markup, against a measured baseline.

    This is criterion 6 itself, as close as a static test gets: the pre-phase
    page produced these runs minus the footer sentence, so the markup delta of
    the whole phase is exactly one line of text. The second permitted delta --
    the reworded #limits line -- is not here because `<p id="limits">` ships
    empty and is filled from `/demo` at runtime; its copy is asserted below.

    A banner, a prompt, a consent notice, an empty-state message or a rendered
    session list would all appear here.
    """
    parser = _FirstPaintText()
    parser.feed(_demo_page())

    assert tuple(parser.runs) == FIRST_PAINT_TEXT


def test_page_copy_and_dom_present():
    """The Phase 12 additions are actually in the file, with the agreed copy.

    Verbatim strings, because the copywriting contract is the deliverable: a
    paraphrase of "private to this browser" that promises more than the cookie
    delivers would be the one dishonest sentence on an otherwise honest page.
    """
    page = _demo_page()

    assert (
        "Your sessions and notes are private to this browser "
        "and expire after 7 days of inactivity." in page
    )
    assert "Your recent research" in page
    assert "requests/hour for this browser" in page
    assert "spent by all visitors in the last 24h" in page
    assert "That session has expired" in page
    assert (
        "Sessions are kept for 7 days after their last activity. "
        "Ask a new question to start fresh." in page
    )
    # The follow-up placeholder is now set from two places (a completed run and
    # a resume) and must stay one string.
    assert page.count(
        "Follow up on that — from its notes, or a fresh search if they fall short"
    ) == 1

    # The side-effect-free renderer exists and `result()` goes through it, so a
    # stored turn cannot pick up result()'s fabricated cost and revision count.
    assert re.search(r"function renderTurnCard\(", page)
    assert re.search(r"out\.appendChild\(renderTurnCard\(payload", page)

    # The owned-session list is CONSTRUCTED, never declared in the markup. That
    # is the "not in the DOM until populated" rule: an empty disclosure element
    # in the served HTML would render a stray triangle on a first visit.
    # Note the shape of this gate -- a grep for the literal `<details id="mine">`
    # would be satisfied by a code comment mentioning it, and would be green in
    # exactly the state (the element shipped in the markup) it is meant to
    # forbid. So: assert the construction, and assert the tag is absent.
    assert 'mine.id = "mine"' in page
    assert re.search(r'el\("details"\)', page)
    assert "<details" not in page

    # The two new call sites, and the resumed session's follow-up target.
    assert 'fetch("/sessions")' in page
    assert "/sessions/${encodeURIComponent(id)}" in page
    assert "ask/stream" in page


def test_page_renderer_omits_absent_badges_instead_of_inventing_them():
    """The specific defect the renderer was extracted to remove.

    The old `result()` did `Number(payload.cost_usd || 0).toFixed(4)` and
    `payload.revision_count + " revision(s)"`, which for a stored turn -- whose
    payload carries only a question and an answer -- renders "$0.0000" and
    "undefined revision(s)". Both are inventions presented in the same badge
    style as measured facts, which is worse than showing nothing.

    Gated separately and by *presence* tests rather than truthiness, because
    truthiness would also drop a genuine $0 or a genuine zero-revision run.
    Found by mutation: restoring the `|| 0` fallback left every other gate in
    this block green.
    """
    body = re.search(
        r"function renderTurnCard\(.*?\n}\n", _demo_page(), re.S
    ).group(0)

    assert '"approved" in turn' in body
    assert 'typeof turn.cost_usd === "number"' in body
    assert 'typeof turn.revision_count === "number"' in body
    assert 'typeof turn.usage.calls === "number"' in body
    # The fallbacks that did the inventing.
    assert "|| 0" not in body
    assert "revision_count +" not in body or 'typeof turn.revision_count === "number"' in body


def test_page_session_list_enters_the_dom_only_when_populated():
    """The rule criterion 6 actually rests on.

    An empty `<details>` in the document renders a stray disclosure triangle, so
    "you have no sessions yet" would be visible to someone who has never asked
    anything -- the added friction the whole constraint forbids. Keeping the
    element out of the markup (asserted above) is only half of it; the other
    half is that script must not append it unconditionally either, and mutating
    that line to `if (!mine.parentNode)` left every other gate here green.
    """
    page = _demo_page()

    # Asserted on the insertion and removal LINES, not on the enclosing
    # function. The first version of this gate searched the whole of syncMine()
    # for "rows &&" -- which the `else if (!rows && ...)` branch satisfies, so
    # it stayed green under exactly the mutation it was written for. Twelfth
    # vacuous gate in this project, and the first one I wrote myself.
    insertion = re.search(r"^.*insertBefore\(mine, out\).*$", page, re.M).group(0)
    removal = re.search(r"^.*mine\.remove\(\).*$", page, re.M).group(0)

    assert re.search(r"\bif \(rows\b", insertion)   # only while it has rows
    assert "!rows" in removal                       # and back out when it has none
    # And nothing else in the file puts it in the document.
    assert page.count("insertBefore(mine, out)") == 1


def test_page_introduces_no_new_colour():
    """AC7's colour half: every new rule uses the existing custom properties.

    Dark mode is inherited for free precisely because nothing hardcodes a
    colour, so this is also what keeps the page working in both schemes with no
    new `@media` rule. Measured baseline: the only literal colour outside the
    two `:root` blocks is the `#fff` on the accent button's label.
    """
    declared = re.search(r"<style>(.*?)</style>", _demo_page(), re.S).group(1)
    outside_root = re.sub(r":root \{.*?\}", "", declared, flags=re.S)

    assert set(re.findall(r"#[0-9a-fA-F]{3,8}\b", outside_root)) == {"#fff"}


def test_page_is_self_contained():
    """No external resource of any kind.

    A strict CSP can then allow nothing external, the Dockerfile stays one COPY,
    and the demo cannot be taken down by someone else's CDN. Case-insensitive
    and wider than the plan's grep, since `HTTPS://` and `//cdn...` would both
    slip past a lowercase literal.
    """
    page = _demo_page()

    assert not re.search(r'(src|href)\s*=\s*"\s*(https?:)?//', page, re.IGNORECASE)
    assert not re.search(r"@import|url\(\s*['\"]?https?:", page, re.IGNORECASE)


# --------------------------------------------------------------------------
# The demo page's Content-Security-Policy
#
# These sit below the static-file gates rather than inside them: that section
# states in its own header that it needs no client, and half of these drive the
# real app to read a real response header. They do reuse `_demo_page()` and
# `_MarkupTags` from it, deliberately -- every assertion here is about the file
# the service actually serves, never a fixture copy. A fixture is a copy that
# can be right while the shipped page is wrong.
# --------------------------------------------------------------------------


def test_demo_page_is_served_with_a_hash_based_csp(make_client):
    """The header exists, carries both element hashes, and changed nothing.

    The last assertion is the UI-SPEC's whole premise -- the CSP is derived FROM
    the page, the page is not adapted TO the CSP -- stated as an assertion on the
    served bytes rather than left as trust.
    """
    client, _ = make_client()

    response = client.get("/", headers={"accept": "text/html"})

    assert response.status_code == 200
    # Membership before lookup, so a header that stops being sent reds as a named
    # failure here rather than as a KeyError out of httpx's header mapping.
    assert "content-security-policy" in response.headers, "the demo page carries no CSP"

    header = response.headers["content-security-policy"]
    assert "script-src 'sha256-" in header
    assert "style-src 'sha256-" in header

    # The directive NAMES, in order, are exactly the ones csp.DIRECTIVES
    # declares -- so a directive silently dropped, added or reordered on the way
    # to the wire fails here, not in a browser console someone happens to open.
    served = [directive.strip().split(" ", 1)[0] for directive in header.split(";")]
    assert served == [directive.split(" ", 1)[0] for directive in csp.DIRECTIVES]

    assert response.text == _demo_page()


def test_csp_hashes_are_derived_from_the_page_not_hand_maintained(make_client):
    """The load-bearing gate: recompute both hashes independently and compare.

    Deliberately does NOT call csp.inline_blocks or csp.sha256_source for the
    expected values. A test that runs the implementation's own helpers down both
    sides asserts only that a function equals itself; recomputing from scratch is
    what catches a wrong algorithm, a wrong encoding, a wrong extraction, the
    wrong file, or a literal somebody pasted in by hand.

    The unsafe-* assertions are against the SERVED string rather than a grep over
    source, so csp.py's docstring stays free to discuss both without tripping a
    gate that should only ever fire on what a browser is actually told.
    """
    page = _demo_page()

    expected = {}
    for tag in ("script", "style"):
        blocks = re.findall(rf"<{tag}>(.*?)</{tag}>", page, re.S)
        assert len(blocks) == 1, f"expected exactly one inline <{tag}>, found {len(blocks)}"
        digest = hashlib.sha256(blocks[0].encode("utf-8")).digest()
        expected[tag] = "sha256-" + base64.b64encode(digest).decode("ascii")

    client, _ = make_client()
    served = client.get("/", headers={"accept": "text/html"})
    header = served.headers["content-security-policy"]

    assert f"script-src '{expected['script']}'" in header, header
    assert f"style-src '{expected['style']}'" in header, header

    # A policy carrying either of these is decorative: 'unsafe-inline' permits
    # exactly the injected script the hashes exist to exclude, and
    # 'unsafe-hashes' exists to license inline handlers and style attributes,
    # which the test below asserts the page has none of.
    assert "unsafe-inline" not in header
    assert "unsafe-hashes" not in header


def test_demo_page_has_exactly_one_script_block_and_one_style_block():
    """The gate on the policy's SHAPE, which derivation cannot follow.

    A second inline block needs a second hash; a policy with one hash for two
    blocks blocks half the page in every browser while the server looks fine.

    Both forms are counted on purpose. The bare-tag count is what csp.py's
    extraction sees; the `<script`-prefix count sees a tag with attributes too.
    They must agree at one apiece, so `<script defer>` -- invisible to the
    extraction, and enough to make the derived policy silently omit that block's
    hash -- fails here rather than in production.
    """
    page = _demo_page()

    assert len(re.findall(r"<script\b", page)) == 1
    assert len(re.findall(r"<style\b", page)) == 1
    assert len(re.findall(r"<script>", page)) == 1
    assert len(re.findall(r"<style>", page)) == 1


def test_demo_page_has_no_inline_handlers_or_style_attributes():
    """Zero `on*` handlers, zero `style=`, zero `javascript:` URLs.

    Each of the three would require loosening the policy -- an inline handler or
    a style attribute needs 'unsafe-hashes' (or worse, 'unsafe-inline'), and a
    `javascript:` URL needs 'unsafe-inline' outright. The loosening is the
    regression this exists to prevent, so the gate is on the page, before anyone
    reaches for the directive that would make it work.
    """
    parser = _MarkupTags()
    parser.feed(_demo_page())

    # Non-vacuity: prove the walk saw attributes at all before asserting which
    # ones are absent. An empty list would pass all three assertions below.
    assert ("input", "id", "q") in parser.attributes
    assert len(parser.attributes) > 10

    assert [(tag, name) for tag, name, _ in parser.attributes if name.startswith("on")] == []
    assert [(tag, name) for tag, name, _ in parser.attributes if name == "style"] == []
    assert [
        (tag, name, value)
        for tag, name, value in parser.attributes
        if value and value.strip().lower().startswith("javascript:")
    ] == []
