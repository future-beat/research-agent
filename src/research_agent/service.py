"""
HTTP surface over the research graph.

The graph, the memory store, and the session store are all already decoupled,
so this module is deliberately thin: it validates input, picks the right state
constructor, runs the graph, and persists the result. No routing logic lives
here -- putting any here would mean the supervisor is no longer the single
place that decides what runs next.

Two shapes for every run:

    POST /research                blocking; returns the finished report
    POST /research/stream         server-sent events; node-by-node progress

A research run takes tens of seconds. Blocking is fine for a job queue calling
this; anything with a human waiting wants the stream, for the same reason the
REPL streams instead of printing nothing for a minute.

Run it:  uvicorn service:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import threading
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import anthropic
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from research_agent import db, graph, limits
from research_agent import usage as usage_accounting
from research_agent.graph import MAX_ITERATIONS, MAX_REVISIONS, followup_state, initial_state
from research_agent.identity import IdentityMiddleware
from research_agent.limits import LimitsStore, get_limits_store
from research_agent.metrics import FAILED, MetricsStore, RunRecord, get_metrics_store
from research_agent.observability import get_logger
from research_agent.sessions import Session, SessionStore, get_session_store

log = get_logger()

MAX_QUESTION_CHARS = 2000
SESSION_LIST_LIMIT = 50
DEMO_PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)

    def cleaned(self) -> str:
        question = self.question.strip()
        if not question:
            raise HTTPException(422, "question must not be blank")
        return question


class RunResponse(BaseModel):
    """One completed run. `answer` holds the report in research mode and the
    follow-up answer in followup mode -- they are the same field in state, and
    flattening them into one here keeps clients from special-casing modes."""

    session_id: str
    mode: str
    task: str
    topic_type: str
    answer: str
    approved: bool
    forced_stop_reason: str = ""
    revision_count: int
    max_revisions: int = MAX_REVISIONS
    iterations: int
    max_iterations: int = MAX_ITERATIONS
    retries: int
    usage: dict[str, Any]
    cost_usd: float
    trace: list[dict[str, Any]]

    @classmethod
    def build(cls, session_id: str, state: dict) -> RunResponse:
        run_usage = state.get("usage") or usage_accounting.new_usage()
        return cls(
            session_id=session_id,
            mode=state["mode"],
            task=state["task"],
            topic_type=state["topic_type"],
            answer=state["draft"],
            approved=bool(state["approved"]),
            forced_stop_reason=state["forced_stop_reason"],
            revision_count=state["revision_count"],
            iterations=state["iteration"],
            retries=sum(1 for e in state["trace"] if e.get("event") == "retry"),
            usage=run_usage,
            cost_usd=round(run_usage.get("cost_usd", 0.0), 6),
            trace=state["trace"],
        )


class SessionDetail(BaseModel):
    session_id: str
    created_at: float
    updated_at: float
    task: str
    turns: int
    # Whose session this is. Declared rather than left to pydantic's
    # extra-ignore so the detail view and the listing agree; harmless to the
    # caller, who can only ever reach their own, and the one field that makes
    # the operator's cross-owner listing legible.
    owner: str
    topic_type: str
    approved: bool
    latest_answer: str
    conversation: list[dict[str, Any]]


# --------------------------------------------------------------------------
# App wiring
# --------------------------------------------------------------------------


def get_sessions(request: Request) -> SessionStore:
    """Injected rather than imported so tests can point at a temp database
    without touching module globals."""
    return request.app.state.sessions


def get_metrics(request: Request) -> MetricsStore:
    return request.app.state.metrics


def get_limits(request: Request) -> LimitsStore:
    """The rate window and spend reservations.

    The one accessor: every metered route reaches the store through this, so a
    test can point the whole app at one store with a single override and the
    DELETE route cannot quietly end up metering against a different one.
    """
    return request.app.state.limits


def rate_limit(request: Request, limits_store: LimitsStore = Depends(get_limits)) -> None:
    """The rate half of `guard`, without the spend reservation.

    A named dependency rather than `Depends(limits.check_rate_limit)` because
    the check now needs the injected store, and FastAPI can only supply that to
    a function whose parameter carries a `Depends` default -- which
    limits.check_rate_limit deliberately does not, so it stays callable from
    plain unit tests.
    """
    limits.check_rate_limit(request, limits_store)


def guard(request: Request, metrics: MetricsStore = Depends(get_metrics),
          limits_store: LimitsStore = Depends(get_limits)) -> None:
    """Applied to every endpoint that spends money, and to no others.

    Ops reads -- /health, /ready, /metrics, /pricing, /memory, /demo -- stay
    open on purpose: they cost nothing, and they are how you diagnose a
    service that is refusing work. A demo that hides /health when it hits its
    budget is a demo you cannot debug.

    Session reads are a different matter and are *not* open: they return
    someone's research, and since Phase 12 only that someone's. They go through
    limits.require_session_access on sessions_router -- a separate, unmetered
    dependency, and deliberately not this one. Applying guard to them would
    spend the caller's research quota on a listing and 429 every read once the
    daily cap is hit, which would contradict the cap's own message that
    read-only endpoints still work.

    Note what this no longer does: the daily spend cap. The cap now reserves
    against a specific run, which does not exist until the handler has built
    the run state, so it is called there (`limits.reserve_or_429`) rather than
    here. That is the one control on the spending routes a route dependency
    cannot hold, which is why tests/test_service.py gates it twice over.
    """
    limits.enforce(request, metrics, limits_store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Backends are chosen here, once, from the environment -- the rest of the
    # module only ever sees the interfaces.
    app.state.sessions = get_session_store()
    app.state.metrics = get_metrics_store()
    app.state.limits = get_limits_store()
    log.info(
        "service starting",
        extra={
            "event": "startup",
            "sessions_backend": type(app.state.sessions).__name__,
            "metrics_backend": type(app.state.metrics).__name__,
            "limits_backend": type(app.state.limits).__name__,
            "memory_backend": type(graph.memory()).__name__,
        },
    )
    try:
        yield
    finally:
        app.state.sessions.close()
        app.state.metrics.close()
        app.state.limits.close()
        # Those two close()es release two claims on the shared pool. There is a
        # THIRD Database on this machine -- graph.memory()'s -- that nothing has
        # ever closed, so without this a shutdown leaves a pool and its
        # background reconnect workers alive in a process on its way out.
        # close_all_pools() disposes every registered pool regardless of who
        # holds a claim, which is the right hammer at shutdown and the wrong one
        # anywhere else.
        db.close_all_pools()
        _shutdown_probes()


app = FastAPI(
    title="Research agent",
    version="0.9.0",
    summary="Supervisor-routed research pipeline with fact-checked reports and follow-ups.",
    lifespan=lifespan,
)

# A middleware rather than a dependency, because /research/stream, /ask/stream
# and GET / return Response objects directly and FastAPI drops dependency-set
# cookies on those -- the three routes a first-time visitor hits first. This
# runs for every route, sets request.state.identity before any handler, and
# never refuses anyone (see identity.py).
app.add_middleware(IdentityMiddleware)


def _http_error(exc: BaseException) -> HTTPException | None:
    """Map an upstream failure to the status code that tells the caller what
    to do about it.

    Transient errors have already been retried with backoff inside each node,
    so anything arriving here is either persistent or has outlived its budget:
    429 means slow down, 502 means upstream is unwell. Anything else is our
    bug and should surface as a 500 with a traceback, not be dressed up as an
    upstream problem.
    """
    if isinstance(exc, anthropic.RateLimitError):
        return HTTPException(429, "Upstream rate limit exceeded after retries.")
    if isinstance(exc, anthropic.APIStatusError):
        return HTTPException(502, f"Upstream API error ({exc.status_code}).")
    if isinstance(exc, anthropic.APIConnectionError):
        return HTTPException(502, "Could not reach the upstream API.")
    return None


def _failed_record(state: dict, exc: BaseException, started: float) -> RunRecord:
    """A run that raised still belongs in the metrics table. Counting only the
    runs that finished would make an upstream outage look like a quiet day."""
    record = RunRecord.from_state(state, duration_ms=(time.perf_counter() - started) * 1000)
    record.status = FAILED
    record.error_type = type(exc).__name__
    return record


def _execute(
    state: dict, metrics: MetricsStore, limits_store: LimitsStore, on_complete
) -> tuple[str, dict]:
    """Run the graph to completion, persist the result, and record the run.

    `limits_store` is here for one reason: this function owns both terminal
    paths, so it is the only place a reservation can be settled on every one of
    them. Settling in the handler would miss the failure arm.
    """
    started = time.perf_counter()
    try:
        final_state = graph.app.invoke(state)
    except BaseException as exc:
        metrics.record(_failed_record(state, exc, started))
        limits.settle(limits_store, state.get("run_id", ""))
        log.warning(
            "run failed",
            extra={
                "event": "run_failed",
                "run_id": state.get("run_id", ""),
                "mode": state.get("mode", ""),
                "error": type(exc).__name__,
            },
        )
        raise (_http_error(exc) or exc) from exc

    duration_ms = (time.perf_counter() - started) * 1000
    session_id = on_complete(final_state)
    metrics.record(
        RunRecord.from_state(final_state, session_id=session_id, duration_ms=duration_ms)
    )
    # Immediately after the record, never before it: the estimate stops
    # counting against the cap only once the real cost is in the table, or the
    # spend briefly disappears from both.
    limits.settle(limits_store, state.get("run_id", ""))
    return session_id, final_state


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _stream(
    state: dict, metrics: MetricsStore, limits_store: LimitsStore, on_complete
) -> Iterator[str]:
    """Emit one SSE `node` event per finished node, then a single terminal
    event -- `result` or `error`, never both, never neither.

    A sync generator: Starlette iterates it in a worker thread, which is what
    we want anyway since the graph is blocking.
    """
    final_state = None
    started = time.perf_counter()
    try:
        for chunk in graph.app.stream(state):
            for node_name, node_state in chunk.items():
                final_state = node_state
                if node_name == "supervisor":
                    continue  # fires between every node; pure noise on the wire
                yield _sse("node", {"node": node_name, **_node_detail(node_name, node_state)})

        if final_state is None:  # pragma: no cover - graph always yields
            raise RuntimeError("graph produced no state")

        duration_ms = (time.perf_counter() - started) * 1000
        session_id = on_complete(final_state)
        metrics.record(
            RunRecord.from_state(final_state, session_id=session_id, duration_ms=duration_ms)
        )
        limits.settle(limits_store, state.get("run_id", ""))
        yield _sse("result", RunResponse.build(session_id, final_state).model_dump())

    except Exception as exc:  # noqa: BLE001 - the stream must terminate cleanly
        # Headers are long gone by now, so an exception here would otherwise
        # look to the client like a truncated stream rather than a failure.
        metrics.record(_failed_record(state, exc, started))
        # THE ARM THAT IS EASY TO FORGET. A stream that fails still holds a
        # reservation, and this is the only place it can be released -- the
        # handler's own except never sees this exception, because the SSE
        # contract requires the generator to swallow it and emit an error
        # event. Missing it leaks $0.20 of budget per failed stream until the
        # staleness cutoff catches up.
        limits.settle(limits_store, state.get("run_id", ""))
        # Same treatment /health gives a probe failure, for the same reason:
        # first line only, because a psycopg error is multi-line and the DSN
        # tends to sit below the first; _redact, because the DSN carries a
        # password; and a cap, because redaction alone still lets an arbitrarily
        # long body reach a browser that will render it.
        message = str(exc).splitlines()[0] if str(exc) else ""
        yield _sse("error", {"error": type(exc).__name__, "detail": _redact(message)[:160]})


def _node_detail(node_name: str, state: dict) -> dict:
    detail: dict[str, Any] = {}
    if node_name == "classifier":
        detail["topic_type"] = state["topic_type"]
    elif node_name == "researcher":
        detail["recalled_from_memory"] = state["trace"][-1].get("recalled_from_memory", 0)
    elif node_name in ("writer", "responder"):
        detail["revision"] = state["revision_count"]
    elif node_name == "critic":
        detail["approved"] = bool(state["approved"])
    retries = sum(
        1 for e in state["trace"] if e.get("node") == node_name and e.get("event") == "retry"
    )
    if retries:
        detail["retries"] = retries
    return detail


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/", tags=["ops"])
def index(request: Request):
    """The demo page for a browser, the JSON index for anything else.

    Content negotiation rather than two URLs: `curl /` keeps returning the
    machine-readable index it always did, and a person who pastes the bare
    URL gets something they can actually use.
    """
    if "text/html" in request.headers.get("accept", ""):
        return FileResponse(DEMO_PAGE, media_type="text/html")
    return _index_json()


def _index_json() -> dict:
    """A front door.

    Without this, the first thing anyone sees after a successful deploy is
    FastAPI's bare `{"detail": "Not Found"}` at the root URL, which is
    indistinguishable from a broken deployment. The service is up; it just
    had nothing to say at `/`.
    """
    return {
        "service": app.title,
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "endpoints": {
            "health": "GET /health",
            "ready": "GET /ready",
            "demo": "GET /demo",
            "research": "POST /research",
            "research_stream": "POST /research/stream",
            "ask": "POST /sessions/{session_id}/ask",
            "ask_stream": "POST /sessions/{session_id}/ask/stream",
            "sessions": "GET /sessions (X-Demo-Token required)",
            "session": "GET /sessions/{session_id} (X-Demo-Token required)",
            "trace": "GET /sessions/{session_id}/trace (X-Demo-Token required)",
            "metrics": "GET /metrics",
            "pricing": "GET /pricing",
            "memory": "GET /memory",
        },
    }


# Credentials inside a URL, e.g. postgresql://user:secret@host/db
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-zA-Z][\w+.-]*://)[^/@\s]*:[^/@\s]*@")


def _redact(text: str) -> str:
    """Strip URL credentials from an error message.

    Connection errors echo back the parameters they were given, and /health
    is typically the one endpoint left unauthenticated. A DSN password in a
    health response is a credential leak to anyone who can curl the service.
    """
    return _URL_CREDENTIALS.sub(r"\g<scheme>***@", text)


def health_probe_budget() -> float:
    """HEALTH_PROBE_BUDGET -- wall-clock seconds one store probe may take.

    Default 3.0, floor 0.1. See `_probe` for why a wall clock is the only
    thing that actually bounds this.
    """
    try:
        return max(0.1, float(os.environ.get("HEALTH_PROBE_BUDGET", "3.0")))
    except ValueError:
        return 3.0


# The probe executor is built lazily and rebuilt after a shutdown, because
# `lifespan` can run more than once per process -- the test suite alone enters
# it nine times. A module-level executor shut down on the first exit would make
# every later /health raise "cannot schedule new futures after shutdown".
_probe_executor: concurrent.futures.ThreadPoolExecutor | None = None
_probe_executor_lock = threading.Lock()


def _probes() -> concurrent.futures.ThreadPoolExecutor:
    global _probe_executor
    with _probe_executor_lock:
        if _probe_executor is None:
            _probe_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=3, thread_name_prefix="health-probe"
            )
        return _probe_executor


def _shutdown_probes() -> None:
    """Drop the probe executor. For the lifespan's `finally`."""
    global _probe_executor
    with _probe_executor_lock:
        executor, _probe_executor = _probe_executor, None
    if executor is not None:
        # No wait: a probe blocked on a dead socket must not hold up shutdown,
        # and cancel_futures clears anything still queued behind it.
        executor.shutdown(wait=False, cancel_futures=True)


def _probe(fn) -> dict:
    """Report whether a dependency answered, without letting it raise, and
    without letting it take longer than `HEALTH_PROBE_BUDGET`.

    The whole point of splitting liveness from readiness: a store that cannot
    be reached is information to put in the response body, not a reason to
    fail the probe that decides whether to restart the process.

    **Why a wall clock and not the pool's timeouts.** `PG_POOL_TIMEOUT` bounds
    a *checkout*, not the statement after it. The case it does not cover is a
    warm pool behind a partition: the pool holds a connection that still looks
    live, the checkout returns in ~0 ms, and then `store.count()` blocks on a
    socket to a peer that has gone away. `PG_CONNECT_TIMEOUT` never applied to
    an established connection. `statement_timeout` covers a slow server and
    `tcp_user_timeout` covers a peer that stops ACKing -- but a peer that keeps
    the socket alive and simply never answers is bounded by nothing in libpq.
    Left there, /health can exceed Fly's 15 s check timeout, Fly restarts both
    machines, and the phase reintroduces exactly the restart loop /health was
    split from /ready to prevent -- now reachable, because the database moved
    across a provider boundary.

    **The ceiling.** Three sequential probes x HEALTH_PROBE_BUDGET (3.0 s) =
    **9 s guaranteed**, inside Fly's 15 s check timeout, whether the pool was
    cold, warm or partitioned. The ordinary cold-pool cost is
    3 x PG_POOL_TIMEOUT = ~6 s, which is the typical case and not the bound.
    The pre-pool code had no ceiling at all in the warm case, and up to 18 s in
    the cold one (two 3 s connect attempts per probe, three probes) against a
    15 s timeout -- so this is a defect the phase fixes rather than inherits.

    **The tradeoff, stated rather than hidden.** An abandoned probe outlives
    the response: `future.result(timeout=...)` stops us *waiting*, it cannot
    interrupt a thread blocked in libpq. The executor bounds its **workers**,
    not its work **queue**, so against a persistently hung peer abandoned
    probes accumulate as queued futures at roughly three per 30 s check
    interval -- the worker count does not cap them. What reaps them is
    `tcp_user_timeout` and the keepalive sequence, not the executor. The 9 s
    ceiling is unaffected either way, because the deadline bounds availability
    rather than execution: a probe that cannot even be scheduled still returns
    at its deadline.
    """
    budget = health_probe_budget()
    future = _probes().submit(fn)
    try:
        result = future.result(timeout=budget)
    except Exception as exc:  # noqa: BLE001 - a probe must never raise
        if not future.done():
            # Not done means we stopped waiting; the exception is our deadline
            # rather than anything the store said. Checking done-ness instead
            # of the exception type keeps a store that raises its own
            # TimeoutError reported as the failure it is.
            return {
                "reachable": False,
                "error": "TimeoutError",
                "detail": f"probe exceeded {budget:g}s",
            }
        message = str(exc).splitlines()[0] if str(exc) else ""
        return {
            "reachable": False,
            "error": type(exc).__name__,
            "detail": _redact(message)[:160],
        }
    return {"reachable": True, **result}


def _dependencies(store: SessionStore, metrics: MetricsStore) -> dict:
    """Each store's identity always, its counts only if it answers."""
    memory = graph.memory()
    return {
        "sessions": {"backend": type(store).__name__, "location": store.path,
                     **_probe(lambda: {"count": store.count()})},
        "metrics": {"backend": type(metrics).__name__, "location": metrics.path,
                    **_probe(lambda: {"runs_recorded": metrics.count()})},
        "memory": {"backend": type(memory).__name__,
                   **_probe(lambda: {"notes": len(memory)})},
    }


@app.get("/demo", tags=["ops"])
def demo_status(metrics: MetricsStore = Depends(get_metrics)) -> dict:
    """What the demo page shows above the input box.

    Publishing the remaining budget is deliberate: a visitor who gets refused
    should be able to see it was a shared cap rather than a broken service.
    """
    return limits.status(metrics)


@app.get("/health", tags=["ops"])
def health(
    store: SessionStore = Depends(get_sessions),
    metrics: MetricsStore = Depends(get_metrics),
) -> dict:
    """Liveness. Returns 200 whenever this process is running.

    It reports what it can reach without failing on what it can't, and that
    distinction is the entire design. Fly restarts a machine whose health
    check fails -- but a restart does not fix an unreachable database, a
    paused free-tier instance, or a third party's outage. It just turns one
    broken dependency into a restart loop, and takes down the endpoints that
    were still working.

    Use /ready for the question "should traffic come here", which is the one
    where an unreachable store genuinely means no.

    Deliberately never calls Claude or Voyage. Credentials are reported as
    present or absent, never by value: the clients are lazy, so a container
    with no keys starts up perfectly healthy and then fails every real
    request -- better to learn that from the deploy than from a user.

    `machine` is FLY_MACHINE_ID, and it is what makes "the state is shared
    across machines" demonstrable in two curls rather than by reading
    `fly logs`: without it nothing in any response says which machine
    answered. Empty string off Fly, never absent, so the shape is stable.
    Not a secret -- Fly already exposes it in its own response headers and
    accepts it as the fly-force-instance-id request header.
    """
    dependencies = _dependencies(store, metrics)
    degraded = [name for name, d in dependencies.items() if not d["reachable"]]
    return {
        "status": "ok",
        "machine": os.environ.get("FLY_MACHINE_ID", ""),
        "dependencies": "degraded" if degraded else "ok",
        "unreachable": degraded,
        **dependencies,
        "credentials": {
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "voyage": bool(os.environ.get("VOYAGE_API_KEY")),
        },
    }


@app.get("/ready", tags=["ops"])
def ready(
    response: Response,
    store: SessionStore = Depends(get_sessions),
    metrics: MetricsStore = Depends(get_metrics),
) -> dict:
    """Readiness: 200 when every store answers, 503 when one doesn't.

    Point a load balancer here to drain a machine whose database is down.
    Do *not* point a restart-triggering liveness check here -- that is
    precisely the loop /health exists to avoid.
    """
    dependencies = _dependencies(store, metrics)
    degraded = [name for name, d in dependencies.items() if not d["reachable"]]
    if degraded:
        response.status_code = 503
    return {
        "status": "degraded" if degraded else "ready",
        "unreachable": degraded,
        **dependencies,
    }


@app.post("/research", response_model=RunResponse, tags=["research"], dependencies=[Depends(guard)])
def research(
    request: Request,
    body: AskRequest,
    store: SessionStore = Depends(get_sessions),
    metrics: MetricsStore = Depends(get_metrics),
    limits_store: LimitsStore = Depends(get_limits),
) -> RunResponse:
    """Full pipeline: classify, search, draft, fact-check. Opens a session."""
    question = body.cleaned()
    run = initial_state(question)
    owner = limits.caller_identity(request)
    limits.reserve_or_429(limits_store, run["run_id"], owner, metrics)
    session_id, state = _execute(
        run, metrics, limits_store, lambda final: store.create(question, final, owner=owner)
    )
    return RunResponse.build(session_id, state)


@app.post("/research/stream", tags=["research"], dependencies=[Depends(guard)])
def research_stream(
    request: Request,
    body: AskRequest,
    store: SessionStore = Depends(get_sessions),
    metrics: MetricsStore = Depends(get_metrics),
    limits_store: LimitsStore = Depends(get_limits),
):
    question = body.cleaned()
    run = initial_state(question)
    owner = limits.caller_identity(request)
    # Before the StreamingResponse is built, so a capped caller gets a real 429
    # instead of a 200 whose body turns out to be an error event.
    limits.reserve_or_429(limits_store, run["run_id"], owner, metrics)
    return _sse_response(
        run, metrics, limits_store, lambda state: store.create(question, state, owner=owner)
    )


@app.post(
    "/sessions/{session_id}/ask",
    response_model=RunResponse,
    tags=["research"],
    dependencies=[Depends(guard)],
)
def ask(
    request: Request,
    session_id: str,
    body: AskRequest,
    store: SessionStore = Depends(get_sessions),
    metrics: MetricsStore = Depends(get_metrics),
    limits_store: LimitsStore = Depends(get_limits),
) -> RunResponse:
    """Follow up on a session's research notes. No new web search.

    Ownership is enforced HERE rather than by adding the session-tree
    dependency to this route. The dependency set stays grouped by what it
    protects (ADR-0006 part 4) and this route protects a *run*, not a listing;
    what it needs from ownership is one line of `_require`, which it already
    calls. A stranger's session id therefore 404s exactly as it does on a read,
    while the demo's second turn keeps working -- the follow-up caller holds
    the cookie that created the session, minted at page load, before the first
    question was even asked.
    """
    owner = limits.caller_identity(request)
    session = _require(store, session_id, owner)

    def on_complete(final: dict) -> str:
        store.append_turn(session_id, final)
        return session_id

    run = followup_state(session.state, body.cleaned())
    # A follow-up is cheaper than a research run, not free -- so it reserves
    # too. Forgetting it here is the specific regression the four-route gate in
    # tests/test_service.py exists to catch.
    limits.reserve_or_429(limits_store, run["run_id"], owner, metrics)
    _, state = _execute(run, metrics, limits_store, on_complete)
    return RunResponse.build(session_id, state)


@app.post("/sessions/{session_id}/ask/stream", tags=["research"], dependencies=[Depends(guard)])
def ask_stream(
    request: Request,
    session_id: str,
    body: AskRequest,
    store: SessionStore = Depends(get_sessions),
    metrics: MetricsStore = Depends(get_metrics),
    limits_store: LimitsStore = Depends(get_limits),
):
    owner = limits.caller_identity(request)
    session = _require(store, session_id, owner)

    def on_complete(state: dict) -> str:
        store.append_turn(session_id, state)
        return session_id

    run = followup_state(session.state, body.cleaned())
    limits.reserve_or_429(limits_store, run["run_id"], owner, metrics)
    return _sse_response(run, metrics, limits_store, on_complete)


# The session read/delete group. Membership is structural rather than
# per-route on purpose: four routes each independently forgot to name a
# credential, and a control you have to remember to repeat is a control that
# will be forgotten again. A future `@sessions_router.get("/{id}/notes")`
# inherits the guard by construction, with nothing to remember.
#
# The ask routes share the /sessions prefix but are NOT here: grouping is by
# dependency, not by path. They are the demo's second turn, and ownership is
# enforced inside their handlers instead -- see `ask`.
#
# The router dependency is kept even though every handler injects the same
# value again. FastAPI caches it within a request, so it costs nothing, and it
# is what the structural walker test reads: a future
# `@sessions_router.get("/{id}/notes")` inherits access control by
# construction, with nothing for its author to remember.
sessions_router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(limits.require_session_access)],
)


@sessions_router.get("")
def list_sessions(
    store: SessionStore = Depends(get_sessions),
    access: tuple = Depends(limits.require_session_access),
) -> dict:
    """The caller's sessions -- or everyone's, for the operator."""
    mode, owner = access
    scope = None if mode == "operator" else owner
    return {"sessions": [s.summary() for s in store.list(SESSION_LIST_LIMIT, owner=scope)]}


@sessions_router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str,
    store: SessionStore = Depends(get_sessions),
    access: tuple = Depends(limits.require_session_access),
) -> SessionDetail:
    mode, owner = access
    session = _require(store, session_id, owner, operator=mode == "operator")
    state = session.state
    conversation = list(state.get("conversation") or [])
    if state["mode"] == "followup" and state["draft"]:
        conversation = conversation + [{"question": state["task"], "answer": state["draft"]}]
    return SessionDetail(
        **session.summary(),
        latest_answer=state["draft"],
        conversation=conversation,
    )


@sessions_router.get("/{session_id}/trace")
def get_trace(
    session_id: str,
    store: SessionStore = Depends(get_sessions),
    access: tuple = Depends(limits.require_session_access),
) -> dict:
    mode, owner = access
    session = _require(store, session_id, owner, operator=mode == "operator")
    return {"session_id": session_id, "trace": session.state["trace"]}


# The only one of the four that is metered, because it is the only one that
# destroys anything. Router dependencies run before decorator dependencies, so
# an unauthorised caller is refused before it can consume a rate-limit slot --
# the same cheapest-first ordering limits.enforce already argues for. The
# bucket is deliberately the same one research runs use: a second key space
# would buy nothing here.
#
# Metered but NOT capped, which since Phase 12 is a distinction the wiring can
# express: `rate_limit` is the rate half of `guard` on its own. Reaching for
# `guard` instead would attach the spend reservation to a delete, and 429 the
# only cleanup tool the operator has at exactly the moment the budget is gone.
@sessions_router.delete(
    "/{session_id}",
    status_code=204,
    dependencies=[Depends(rate_limit)],
)
def delete_session(
    session_id: str,
    store: SessionStore = Depends(get_sessions),
    access: tuple = Depends(limits.require_session_access),
) -> None:
    """Owner or operator. Everyone else gets the same 404 a stranger's id gets.

    `_require` first, then delete: checking ownership through the same choke
    point the reads use means a foreign or expired session cannot be destroyed,
    and cannot be *detected* either -- `store.delete` alone would have
    distinguished a real id (True) from a made-up one (False).
    """
    mode, owner = access
    _require(store, session_id, owner, operator=mode == "operator")
    store.delete(session_id)


app.include_router(sessions_router)


@app.get("/memory", tags=["ops"])
def memory_stats() -> dict:
    store = graph.memory()
    return {"backend": type(store).__name__, "notes": len(store), "detail": store.describe()}


@app.get("/metrics", tags=["ops"])
def metrics_summary(metrics: MetricsStore = Depends(get_metrics)) -> dict:
    """Aggregate volume, approval rate, guardrail firings, cost, and latency.

    Rate fields are null rather than zero when their denominator is zero --
    "no runs yet" and "nothing was approved" are different facts.
    """
    return metrics.summary()


@app.get("/pricing", tags=["ops"])
def pricing() -> dict:
    """The rates cost accounting is using today.

    Worth exposing: Claude Sonnet 5 is on introductory pricing that ends
    2026-08-31, so the same run costs 50% more the following day. A cost
    dashboard that steps without explanation is a support ticket.
    """
    model = graph.MODEL
    try:
        price = usage_accounting.price_for(model)
    except usage_accounting.UnknownModelPricing as exc:
        raise HTTPException(501, str(exc)) from exc
    return {
        "model": model,
        "usd_per_mtok": {
            "input": price.input,
            "output": price.output,
            "cache_write_5m": price.cache_write_5m,
            "cache_read": price.cache_read,
        },
        "web_search_usd_per_request": usage_accounting.WEB_SEARCH_USD_PER_REQUEST,
        "max_run_cost_usd": usage_accounting.max_run_cost_usd(),
    }


def _require(
    store: SessionStore, session_id: str, owner: str | None, *, operator: bool = False
) -> Session:
    """The session, or the one refusal shape the session tree ever gives.

    Missing, expired, and belonging-to-someone-else all raise the SAME 404 with
    the SAME body. Not 403: a 403 confirms the id names a real session, and
    session ids travel in shared URLs, screenshots and logs, so telling a
    stranger "that one exists, you just can't have it" is an existence oracle
    handed out for free. Phase 10.5 chose to leak least; this continues it.

    `store.get` has already applied the expiry filter, so expired arrives here
    as None and needs no separate branch -- and could not accidentally get a
    different status code if it did.
    """
    session = store.get(session_id)
    if session is None or (not operator and session.owner != owner):
        raise HTTPException(404, f"No session {session_id!r}.")
    return session


def _sse_response(
    state: dict, metrics: MetricsStore, limits_store: LimitsStore, on_complete
) -> StreamingResponse:
    return StreamingResponse(
        _stream(state, metrics, limits_store, on_complete),
        media_type="text/event-stream",
        # Without this, an nginx or Fly proxy will happily buffer a
        # progress stream until it is no longer progress.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
