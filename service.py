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

import json
import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import research_agent
from research_agent import MAX_ITERATIONS, MAX_REVISIONS, followup_state, initial_state
from sessions import SESSION_DB_PATH, Session, SessionStore

MAX_QUESTION_CHARS = 2000
SESSION_LIST_LIMIT = 50


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
    trace: list[dict[str, Any]]

    @classmethod
    def build(cls, session_id: str, state: dict) -> "RunResponse":
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
            trace=state["trace"],
        )


class SessionDetail(BaseModel):
    session_id: str
    created_at: float
    updated_at: float
    task: str
    turns: int
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sessions = SessionStore(os.environ.get("SESSION_DB_PATH", SESSION_DB_PATH))
    try:
        yield
    finally:
        app.state.sessions.close()


app = FastAPI(
    title="Research agent",
    version="0.4.0",
    summary="Supervisor-routed research pipeline with fact-checked reports and follow-ups.",
    lifespan=lifespan,
)


def _run(state: dict) -> dict:
    """Run the graph, translating API failures into HTTP status codes.

    Transient errors have already been retried with backoff inside each node,
    so anything arriving here is either persistent or has outlived its budget.
    That distinction is what the caller needs, so it maps to the status code:
    429 means slow down, 502 means upstream is unwell, 500 means our bug.
    """
    try:
        return research_agent.app.invoke(state)
    except anthropic.RateLimitError as exc:
        raise HTTPException(429, "Upstream rate limit exceeded after retries.") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(502, f"Upstream API error ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(502, "Could not reach the upstream API.") from exc


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _stream(state: dict, on_complete) -> Iterator[str]:
    """Emit one SSE `node` event per finished node, then a single terminal
    event -- `result` or `error`, never both, never neither.

    A sync generator: Starlette iterates it in a worker thread, which is what
    we want anyway since the graph is blocking.
    """
    final_state = None
    try:
        for chunk in research_agent.app.stream(state):
            for node_name, node_state in chunk.items():
                final_state = node_state
                if node_name == "supervisor":
                    continue  # fires between every node; pure noise on the wire
                yield _sse("node", {"node": node_name, **_node_detail(node_name, node_state)})

        if final_state is None:  # pragma: no cover - graph always yields
            raise RuntimeError("graph produced no state")

        session_id = on_complete(final_state)
        yield _sse("result", RunResponse.build(session_id, final_state).model_dump())

    except anthropic.APIError as exc:
        yield _sse("error", {"error": type(exc).__name__, "detail": str(exc)})
    except Exception as exc:  # noqa: BLE001 - the stream must terminate cleanly
        # Headers are long gone by now, so an exception here would otherwise
        # look to the client like a truncated stream rather than a failure.
        yield _sse("error", {"error": type(exc).__name__, "detail": str(exc)})


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


@app.get("/health", tags=["ops"])
def health(store: SessionStore = Depends(get_sessions)) -> dict:
    """Liveness plus the two facts worth knowing at a glance: which memory
    backend is live, and whether sessions are actually persisting.

    Deliberately does not call Claude or Voyage -- a health check that fails
    when a third party is down will get a healthy container killed.
    """
    memory = research_agent.memory()
    return {
        "status": "ok",
        "memory": {"backend": type(memory).__name__, "notes": len(memory)},
        "sessions": {"count": store.count(), "path": store.path},
    }


@app.post("/research", response_model=RunResponse, tags=["research"])
def research(body: AskRequest, store: SessionStore = Depends(get_sessions)) -> RunResponse:
    """Full pipeline: classify, search, draft, fact-check. Opens a session."""
    question = body.cleaned()
    state = _run(initial_state(question))
    session_id = store.create(question, state)
    return RunResponse.build(session_id, state)


@app.post("/research/stream", tags=["research"])
def research_stream(body: AskRequest, store: SessionStore = Depends(get_sessions)):
    question = body.cleaned()
    return _sse_response(
        initial_state(question), lambda state: store.create(question, state)
    )


@app.post("/sessions/{session_id}/ask", response_model=RunResponse, tags=["research"])
def ask(
    session_id: str, body: AskRequest, store: SessionStore = Depends(get_sessions)
) -> RunResponse:
    """Follow up on a session's research notes. No new web search."""
    session = _require(store, session_id)
    state = _run(followup_state(session.state, body.cleaned()))
    store.append_turn(session_id, state)
    return RunResponse.build(session_id, state)


@app.post("/sessions/{session_id}/ask/stream", tags=["research"])
def ask_stream(
    session_id: str, body: AskRequest, store: SessionStore = Depends(get_sessions)
):
    session = _require(store, session_id)

    def on_complete(state: dict) -> str:
        store.append_turn(session_id, state)
        return session_id

    return _sse_response(followup_state(session.state, body.cleaned()), on_complete)


@app.get("/sessions", tags=["sessions"])
def list_sessions(store: SessionStore = Depends(get_sessions)) -> dict:
    return {"sessions": [s.summary() for s in store.list(SESSION_LIST_LIMIT)]}


@app.get("/sessions/{session_id}", response_model=SessionDetail, tags=["sessions"])
def get_session(session_id: str, store: SessionStore = Depends(get_sessions)) -> SessionDetail:
    session = _require(store, session_id)
    state = session.state
    conversation = list(state.get("conversation") or [])
    if state["mode"] == "followup" and state["draft"]:
        conversation = conversation + [{"question": state["task"], "answer": state["draft"]}]
    return SessionDetail(
        **session.summary(),
        latest_answer=state["draft"],
        conversation=conversation,
    )


@app.get("/sessions/{session_id}/trace", tags=["sessions"])
def get_trace(session_id: str, store: SessionStore = Depends(get_sessions)) -> dict:
    session = _require(store, session_id)
    return {"session_id": session_id, "trace": session.state["trace"]}


@app.delete("/sessions/{session_id}", status_code=204, tags=["sessions"])
def delete_session(session_id: str, store: SessionStore = Depends(get_sessions)) -> None:
    if not store.delete(session_id):
        raise HTTPException(404, f"No session {session_id!r}.")


@app.get("/memory", tags=["ops"])
def memory_stats() -> dict:
    store = research_agent.memory()
    return {"backend": type(store).__name__, "notes": len(store), "detail": store.describe()}


def _require(store: SessionStore, session_id: str) -> Session:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(404, f"No session {session_id!r}.")
    return session


def _sse_response(state: dict, on_complete) -> StreamingResponse:
    return StreamingResponse(
        _stream(state, on_complete),
        media_type="text/event-stream",
        # Without this, an nginx or Fly proxy will happily buffer a
        # progress stream until it is no longer progress.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
