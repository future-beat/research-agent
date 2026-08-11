---
phase: 4
slug: service
milestone: v1.0
status: complete
executed: 2026-08-01
remastered: 2026-08-12
---

# Phase 4: Service — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** The pipeline is reachable over HTTP, blocking or streaming, with durable sessions.

**Shipped in:** `22e4607` (2026-08-01) — `service.py` (317 lines), `sessions.py` (165),
and 562 test lines (`test_service.py` 400, `test_sessions.py` 162).

## What shipped

- **FastAPI over the same graph.** `POST /research` blocking and `POST /research/stream`
  as SSE; follow-ups as `POST /sessions/{id}/ask` and `/ask/stream`. The service is a
  transport: `service.py` holds no routing logic, a boundary that later became a stated
  project constraint and shaped where Phase 17's routing change was allowed to live.
- **Sessions in SQLite, deliberately not LangGraph's checkpointer** (DEC-14). The final
  state of every completed run is persisted; follow-ups arrive as separate requests,
  likely on a different worker, possibly after a redeploy. The checkpointer was rejected
  as "a different feature with a different failure model" — it resumes half-finished
  graphs and would couple the schema to LangGraph internals. Consequence accepted on the
  record: a crash mid-run loses that run and the caller retries.
- **Exactly one terminal event per stream** (DEC-19). `_stream` catches everything and
  emits an in-band `error` event — never both a `result` and an `error`, never neither.
  By the time a node dies the `200` and headers are gone; without the in-band event a
  mid-run failure is indistinguishable from a truncated connection.
- **Session read surface**: `GET /sessions`, `/sessions/{id}`, `/sessions/{id}/trace`
  (DEC-06's trace made addressable), `DELETE /sessions/{id}`.

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| DEC-14 sessions in SQLite, not the checkpointer | Promoted to [ADR-0004](../../../docs/adr/0004-sessions-in-sqlite-not-langgraph-checkpointer.md) in Phase 10; never reversed — Phase 8 swapped the *backend* (Postgres), not the decision |
| DEC-19 one terminal event | Never reversed; the SSE error detail was additionally *redacted* in Phase 10.5 |
| `service.py` holds no routing logic | Became a PROJECT.md constraint, binding on Phase 17 |
| Session routes ship unauthenticated | v1.0's costliest omission — reachable by anyone, confirmed against production in v1.1 and closed the same day as Phase 10.5 (Fly v4), then given real ownership semantics in Phase 12 |

## Where it lives today

`src/research_agent/service.py` and `sessions.py`. The endpoints survived v1.1 intact in
shape; what changed around them is identity (Phase 12's auto-issued cookie), ownership
(sessions list only their owner's), and guarding (Phase 10.5's `SESSIONS_TOKEN`).
Tests measured 2026-08-12: `test_service.py` **128**, `test_sessions.py` **14** collected.
