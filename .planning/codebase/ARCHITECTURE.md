<!-- refreshed: 2026-08-04 -->
# Architecture

**Analysis Date:** 2026-08-04

Architectural rationale for most decisions below is already extracted in
`.planning/intel/decisions.md` (DEC-01 … DEC-23). This document records the
*mechanism*; cite the DEC- entries for the *why*.

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                      Entry surfaces                          │
├──────────────────┬──────────────────┬───────────────────────┤
│   HTTP service   │   Terminal REPL  │    Eval harness       │
│ `src/research_   │ `src/research_   │  `evals/harness.py`   │
│  agent/service.py│  agent/chat.py`  │  (scripted client)    │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         └──────────────────┴─────────────────────┘
                            │  graph.app.invoke() / .stream()
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Compiled LangGraph state machine                │
│                 `src/research_agent/graph.py`                │
│                                                              │
│   supervisor (routing table, plain Python)                   │
│      ├─► classifier ──┐                                      │
│      ├─► researcher ──┤                                      │
│      ├─► writer     ──┼─► every worker edges back to         │
│      ├─► responder  ──┤    supervisor; only supervisor       │
│      └─► critic     ──┘    can route to END                  │
└───────┬──────────────────────┬─────────────────┬────────────┘
        │                      │                  │
        ▼                      ▼                  ▼
┌────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│ call_model()   │  │ MemoryStore seam   │  │ retry_node()     │
│ + usage/cost   │  │ + Embedder seam    │  │ `retry.py`       │
│ `usage.py`     │  │ `memory.py`        │  │                  │
└───────┬────────┘  └─────────┬──────────┘  └──────────────────┘
        │                     │
        ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Persistence (all pick Postgres when DATABASE_URL is set)    │
│  sessions `sessions.py`  metrics `metrics.py`  notes         │
│  shared connection: `db.py` (one lock-guarded conn, no pool) │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `supervisor_node` | The entire routing table; the only node that can end a run | `src/research_agent/graph.py:403` |
| `classifier_node` | One-word topic label (`technical`/`contested`/`sparse`/`general`) | `src/research_agent/graph.py:218` |
| `researcher_node` | Recalls prior notes, web-searches, stores new notes | `src/research_agent/graph.py:246` |
| `writer_node` | Drafts the report from notes (research mode author) | `src/research_agent/graph.py:283` |
| `responder_node` | Answers a follow-up from notes only, no search (followup mode author) | `src/research_agent/graph.py:327` |
| `critic_node` | Grounding check against notes; sets `approved` / `critic_feedback` | `src/research_agent/graph.py:374` |
| `call_model` | Single choke point for every model call: span, latency log, usage folding | `src/research_agent/graph.py:84` |
| `MemoryStore` / `Embedder` | Two independent pluggability seams for note recall | `src/research_agent/memory.py:110`, `:68` |
| `SessionStore` | Persists the final `AgentState` of completed runs | `src/research_agent/sessions.py:96` |
| `MetricsStore` | Per-run records, aggregate summary, spend windows | `src/research_agent/metrics.py:241` |
| `Database` | One reconnecting, lock-guarded Postgres connection shared by all three stores | `src/research_agent/db.py:64` |
| `retry_node` | Node-boundary retry decorator | `src/research_agent/retry.py:140` |
| FastAPI app | HTTP + SSE surface; no routing logic | `src/research_agent/service.py:166` |
| `limits` | Demo token, per-IP rate limit, daily spend cap | `src/research_agent/limits.py` |

## Pattern Overview

**Overall:** Supervisor-routed multi-agent graph (LangGraph `StateGraph`) with a
separate critic node, wrapped in a deliberately thin HTTP layer.

**Key Characteristics:**
- Control flow is **deterministic Python**, never an LLM choice (DEC-01). The
  supervisor is a chain of `if`/`elif` over `AgentState`; the LLM does the work,
  the graph decides the order. Consequence: the whole routing table is
  unit-testable with no API keys — see `tests/test_supervisor_routing.py`.
- Star topology. Every worker has exactly one outgoing edge, back to
  `supervisor` (`src/research_agent/graph.py:484`). Only `supervisor` has
  conditional edges, and only it can reach `END`.
- Two run modes share one graph. `mode` changes exactly one thing: which node
  authors the text (`writer` vs `responder`). Caps, the critic hop, and the
  revision loop are identical either way (`graph.py:412`).
- Nothing is constructed at import time (DEC-18). `client()` and `memory()` are
  lazy globals (`graph.py:58`, `:65`); Postgres stores *register* DDL and apply
  it on first use (`db.py:116`).

## Layers

**Graph / orchestration:**
- Purpose: decide what runs next and in what order
- Location: `src/research_agent/graph.py`
- Contains: `AgentState` TypedDict, six nodes, `supervisor_node`, `route`, `build_graph`
- Depends on: `usage`, `memory`, `observability`, `retry`
- Used by: `service.py`, `chat.py`, `evals/harness.py`

**Seams / pluggable backends:**
- Purpose: keep storage and embedding choices out of the graph
- Location: `src/research_agent/memory.py`, `sessions.py`, `metrics.py`, `db.py`
- Contains: ABCs/Protocols plus concrete backends and a `get_*_store()` selector
- Used by: graph (memory only), service lifespan (sessions, metrics)

**Cross-cutting:**
- Purpose: retries, cost accounting, structured logs/spans, demo guardrails
- Location: `retry.py`, `usage.py`, `observability.py`, `limits.py`
- Used by: every node and every money-spending endpoint

**Interface:**
- Purpose: HTTP/SSE, terminal REPL, offline evals
- Location: `service.py`, `chat.py`, `static/index.html`, `evals/`
- Rule: no routing logic here. `service.py:1-8` states it explicitly — putting
  any here would mean the supervisor is no longer the single place that decides
  what runs next.

## The Supervisor Routing Table

**This is the load-bearing part of the system, and row order is the known bug
class.** Source: `src/research_agent/graph.py:415-445`. The relationship
between the caps was itself a shipped bug (DEC-21).

Evaluated top to bottom; **first match wins**:

| # | Line | Condition | Result | `forced_stop_reason` |
|---|------|-----------|--------|----------------------|
| 1 | `graph.py:415` | `iteration > MAX_ITERATIONS` | `done` | `max_iterations_exceeded` |
| 2 | `graph.py:418` | `revision_count > MAX_REVISIONS` | `done` | `max_revisions_exceeded` |
| 3 | `graph.py:421` | `budget > 0 and usage.cost_usd > budget` | `done` | `budget_exceeded` |
| 4 | `graph.py:428` | `mode == "followup" and not research_notes` | `done` | `no_prior_research` |
| 5 | `graph.py:434` | `not topic_type` | `classifier` | — |
| 6 | `graph.py:436` | `not research_notes` | `researcher` | — |
| 7 | `graph.py:438` | `not draft` | `author` (`writer`\|`responder`) | — |
| 8 | `graph.py:440` | `not reviewed` | `critic` | — |
| 9 | `graph.py:443` | `not approved` | `author` | — |
| 10 | `graph.py:445` | *(else)* | `done` | `""` (approved) |

`author` is bound once at the top of the function:
`author = "responder" if state["mode"] == "followup" else "writer"`
(`graph.py:412`).

### Precedence facts that must not change silently

- **Rows 1-3 (the three guardrails) sit above row 4.** A follow-up that has no
  prior notes *and* is over budget reports `budget_exceeded`, not
  `no_prior_research`. Guardrails outrank everything, including an approved
  draft — pinned by `test_caps_outrank_an_approved_draft` and
  `test_the_iteration_cap_still_outranks_the_budget` in
  `tests/test_supervisor_routing.py:199,313`.
- **Row 4 sits above row 6, and that is the whole point.** Row 6 routes on
  `not research_notes` without checking mode. If row 4 were moved below row 6, a
  follow-up with empty notes would fall through to `researcher` and silently run
  a live web search — the exact behaviour DEC-04 forbids ("the single failure
  mode this whole pipeline exists to prevent"). Pinned by
  `test_followup_without_prior_research_refuses_to_answer`
  (`tests/test_supervisor_routing.py:117`).
- **Row 4 also sits above row 5**, so a note-less follow-up never burns a
  classifier call before stopping.
- **Row 8 (`not reviewed`) must stay above row 9 (`not approved`).** `approved`
  is `False` on a fresh state, so if row 9 came first a brand-new draft would be
  sent straight back to the author and the critic would never run.
- **Row 1 above row 2 is why `MAX_ITERATIONS` must exceed the worst-case
  revision path.** `MAX_ITERATIONS = 2 * (MAX_REVISIONS + 2) + 4` = 12
  (`graph.py:47`). At the original hard-coded `8` the revision cap was
  unreachable in research mode and an ungrounded run reported
  `max_iterations_exceeded` — reads like an internal fault — instead of the
  truth, `max_revisions_exceeded`. Found by the evals, not by unit tests, since
  each cap was correct in isolation (DEC-21). A test pins the derivation.

`route()` (`graph.py:468`) is a pure translation of `next_step`: worker names
pass through, `"done"` becomes `"__end__"`. `test_every_reachable_next_step_has_an_edge`
(`tests/test_supervisor_routing.py:242`) asserts the table can never emit a
`next_step` with no matching edge.

## Loop Bounds and `forced_stop_reason`

- `MAX_REVISIONS = 2` (`graph.py:39`) caps the critic↔author cycle.
  `revision_count` increments in `writer_node`/`responder_node` only when
  `critic_feedback` is non-empty (`graph.py:308`, `:364`).
- `MAX_ITERATIONS = 12` (`graph.py:47`) is a backstop on total supervisor turns;
  `iteration` increments on every supervisor entry (`graph.py:411`).
- `AGENT_MAX_RUN_COST_USD` (`usage.max_run_cost_usd()`) is **a routing rule, not
  a wrapper** (DEC-11). Each node folds usage into `state["usage"]` inside
  `call_model` before returning (`graph.py:103`), so the supervisor reads true
  running cost on its next hop. Checked *between* nodes — a run can overshoot by
  at most one node, never unboundedly. `budget <= 0` disables the cap.
- `forced_stop_reason` is a plain string on state, set only by rows 1-4, and
  propagated all the way out: `RunResponse.forced_stop_reason`
  (`service.py:77`), the REPL banner (`graph.py:513`), and the metrics table.
  An unapproved draft is never returned as if approved — the evals assert this
  invariant directly (DEC-20).

## The Critic and the Shared Model

- The critic is a **separate node with its own rubric** (DEC-02), given the
  research notes as the sole source of truth. Verdict parsing is a strict
  prefix check: `state["approved"] = verdict.startswith("APPROVED")`
  (`graph.py:396`). Anything else becomes `critic_feedback` verbatim and is
  pasted into the author's next prompt.
- `CRITIC_RUBRIC` (`graph.py:205`) keys the extra instruction off `topic_type`,
  mirroring `RESEARCH_STRATEGY` (`graph.py:195`).
- Follow-ups reuse the critic rather than bypassing it. `responder_node` writes
  into the **same `state["draft"]` field** as the writer (`graph.py:362`), which
  is the mechanism that makes the critic loop apply unchanged.
- **Every node shares one model constant**: `MODEL = "claude-sonnet-5"`
  (`graph.py:38`), read by `call_model` at `graph.py:99`. There is no per-node
  model override — only per-node inference settings (DEC-05): the classifier
  runs `thinking={"type": "disabled"}` under a 20-token ceiling
  (`graph.py:222-224`); researcher/writer/responder/critic run
  `thinking={"type": "adaptive"}`; everything at `effort: "medium"`.
  The critic therefore shares the writer's model and its blind spots. The
  compensating control is the eval judge on a stronger model
  (`JUDGE_MODEL` in `evals/graders.py`, Opus 5 — DEC-22). An open requirement
  proposes giving the critic an independent model; if it lands, the rationale
  for the stronger judge must be re-derived, not inherited.

## Pluggability Seams

**`Embedder` (Protocol, `memory.py:68`)** — `embed_documents()` /
`embed_query()`. Default `VoyageEmbedder` (`memory.py:78`), `voyage-3.5`,
1024 dimensions, client built on first use. `evals/harness.py:66` supplies a
deterministic `HashEmbedder` instead.

**`MemoryStore` (ABC, `memory.py:110`)** — exactly four methods the graph is
allowed to touch: `add`, `query`, `__len__`, `describe` (plus a non-abstract
`close()` no-op default). A reach test asserts the graph never touches anything
past those four, so the seam can't rot (DEC-08).

Four backends, selected by `VECTOR_STORE` via `get_memory_store()`
(`memory.py:452`, `BACKENDS` dict at `memory.py:431`):

| Value | Class | Line | Notes |
|-------|-------|------|-------|
| `json` | `JSONMemoryStore` | `memory.py:209` | File-backed, rewrites whole file per add, write-then-rename |
| `memory` | `InMemoryStore` | `memory.py:201` | Ephemeral; tests and workers |
| `chroma` | `ChromaMemoryStore` | `memory.py:239` | HNSW cosine collection; needs `chromadb` extra |
| `pgvector` | `PgVectorMemoryStore` | `memory.py:311` | Shared + HNSW-indexed; `<=>` cosine distance |

`json` and `memory` share `_BruteForceStore` (`memory.py:151`) — exact cosine,
O(n) per query, RLock-guarded list, embedding call deliberately outside the lock.
`default_backend()` (`memory.py:439`) picks `pgvector` when `DATABASE_URL` is
set, `json` otherwise. Embedder and store are **separate seams on purpose**:
switching stores must never silently switch embedding models, which would
invalidate every vector already written. `PgVectorMemoryStore._check_dimensions`
(`memory.py:371`) fails loudly on a mismatch rather than letting it surface as a
Postgres type error mid-insert.

`graph.set_memory()` (`graph.py:73`) swaps the backend at runtime; tests and the
eval harness use it.

## Session Persistence

- **Completed runs only, in SQLite — deliberately NOT LangGraph's checkpointer**
  (DEC-14, `sessions.py:1-15`). The final `AgentState` is serialised per session
  id; `/sessions/{id}/ask` loads it back. A follow-up arrives as a separate
  request, probably on a different worker, possibly after a redeploy. The
  checkpointer solves resuming a half-finished graph — a different feature with
  a different failure model — and would couple the schema to LangGraph
  internals. Accepted consequence: a crash mid-run loses that run; the caller
  retries.
- Two backends behind `SessionStore` (`sessions.py:96`): `SQLiteSessionStore`
  (`:132`) and `PostgresSessionStore` (`:231`), selected by `SESSION_BACKEND`,
  defaulting to postgres when `DATABASE_URL` is set. Postgres stores state as
  `JSONB` (`sessions.py` `POSTGRES_SCHEMA`) so a future query can reach into the
  blob without a migration.
- **One `DATABASE_URL` moves sessions, metrics, and notes together** (DEC-15).
  Three separate flags would be more configurable and worse: the failure you'd
  actually hit is setting one and forgetting another.
- Migration (`migrate.py`) copies embeddings rather than re-embedding (DEC-10).

## Postgres Connection Model

`db.Database` (`db.py:64`) is **one connection guarded by an `RLock`, not a
pool** (`db.py:11-14`, `db.py:69`). A research run occupies a worker for tens of
seconds while database calls take milliseconds, so serialising them costs
nothing measurable and keeps the concurrency story identical to the SQLite
backends alongside it.

- `cursor()` (`db.py:88`) reconnects **exactly once** on `OperationalError` /
  `InterfaceError`, and only on those — a genuine SQL error must surface rather
  than run twice.
- `autocommit=True` (`db.py:81`): every store does single-statement writes.
- `PG_CONNECT_TIMEOUT` defaults to 3s (`db.py:36`) because a paused free-tier
  instance accepts the TCP connection and then says nothing.
- `ensure_schema()` (`db.py:116`) registers DDL and *suppresses* failure, so the
  service boots degraded and self-heals on first successful use (DEC-18).

## Data Flow

### Blocking research run (`POST /research`)

1. `guard` dependency → `limits.enforce` (token, per-IP rate, daily cap) (`service.py:134`)
2. `initial_state(question)` (`graph.py:144`)
3. `_execute` → `graph.app.invoke(state)` (`service.py:206`)
4. supervisor → classifier → supervisor → researcher → supervisor → writer →
   supervisor → critic → supervisor → (`writer` again, capped) → `END`
5. `store.create(question, final)` persists the session (`service.py:456`)
6. `metrics.record(RunRecord.from_state(...))` (`service.py:222`)
7. `RunResponse.build(session_id, state)` flattens `draft` into `answer`
   (`service.py:87`)

On exception: `_failed_record` still writes a metrics row (failed runs count in
the denominator — DEC-13), then `_http_error` maps to 429/502 or re-raises
(`service.py:174`).

### SSE streaming run (`POST /research/stream`, `POST /sessions/{id}/ask/stream`)

1. `_sse_response` wraps `_stream` in a `StreamingResponse` with
   `Cache-Control: no-cache` and `X-Accel-Buffering: no` — without the latter a
   Fly/nginx proxy buffers the progress stream until it is no longer progress
   (`service.py:594`)
2. `_stream` iterates `graph.app.stream(state)` (`service.py:242`), a **sync**
   generator that Starlette runs in a worker thread, which is what we want since
   the graph is blocking
3. Per chunk: `supervisor` frames are skipped as pure noise on the wire
   (`service.py:245`); every other node emits `event: node` with
   `_node_detail` (`service.py:266`) — `topic_type` for classifier,
   `recalled_from_memory` for researcher, `revision` for writer/responder,
   `approved` for critic, plus `retries` when non-zero
4. **Exactly one terminal event, never both, never neither** (DEC-19):
   `event: result` with the full `RunResponse`, or `event: error` with
   `{error, detail}` from the blanket `except` (`service.py:259`). By the time a
   node dies the 200 and headers are gone, so without the in-band error a mid-run
   failure is indistinguishable from a truncated connection.
5. `src/research_agent/static/index.html` parses the stream **by hand** with
   `fetch` + a line reader (`index.html:294`) — `EventSource` cannot issue a
   POST. It renders a stage row per `node` event, and warns if the stream ends
   with neither terminal event: "No result or error arrived. The run may still
   have completed and been billed." (`index.html:336`).

### Endpoint set (`service.py`, index at `_index_json`, `service.py:302`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Demo page for `Accept: text/html`, JSON index otherwise |
| GET | `/demo` | Remaining budget/rate status shown above the input box |
| GET | `/health` | Liveness; always 200, reports degraded dependencies in the body |
| GET | `/ready` | Readiness; 503 when any store is unreachable |
| POST | `/research` | Blocking full pipeline; opens a session |
| POST | `/research/stream` | Same, as SSE |
| POST | `/sessions/{id}/ask` | Follow-up from stored notes; no web search |
| POST | `/sessions/{id}/ask/stream` | Same, as SSE |
| GET | `/sessions` | Recent sessions (limit 50) |
| GET | `/sessions/{id}` | Session detail + conversation |
| GET | `/sessions/{id}/trace` | Stored `state["trace"]` |
| DELETE | `/sessions/{id}` | 204, or 404 |
| GET | `/metrics` | Aggregate summary |
| GET | `/pricing` | Effective-dated rates + run cap |
| GET | `/memory` | Backend name, note count, `describe()` |

The four money-spending endpoints carry `dependencies=[Depends(guard)]`; the
read-only ones deliberately do not — a demo that hides `/health` when it hits
its budget is a demo you cannot debug (`service.py:134-141`).

## Key Abstractions

**`AgentState` (TypedDict, `graph.py:124`):**
- The single mutable dict every node reads and writes. Nodes mutate in place and
  return the same object.
- `draft` is shared by writer and responder — the mechanism behind follow-up
  criticism.
- `usage` and `trace` accumulate across the whole run; `run_id` ties logs, spans,
  and the metrics row together.
- `followup_state(previous, question)` (`graph.py:167`) builds the next turn from
  either a research run or an earlier follow-up, so chaining is just
  `followup_state(last_state, q)`. Each follow-up gets a **fresh `run_id` and a
  fresh budget** — a long conversation shouldn't inherit an exhausted cap.

**`state["trace"]` (DEC-06):** every node appends a dict — routing decisions,
recall counts, draft lengths, critic verdicts, retry attempts. Surfaced via
`/sessions/{id}/trace` and the REPL.

## Architectural Constraints

- **Threading:** FastAPI runs these sync endpoints in Starlette's thread pool, so
  multiple graph runs execute concurrently in-process. `_BruteForceStore` guards
  its list + file with an `RLock` (`memory.py:164`); `db.Database` serialises all
  Postgres traffic behind one `RLock` (`db.py:69`); `RateLimiter` has its own
  lock (`limits.py:92`).
- **Global state:** `graph._client` and `graph._memory` are module-level lazy
  singletons (`graph.py:54-55`). `set_memory()` mutates the global — the eval
  harness saves and restores both around each case (`evals/harness.py:243`).
  `observability` and `limits` hold their own module singletons.
- **Import-time purity:** no API client, no DB connection, no DDL at import.
  Violating this makes `graph.py` unimportable without a full key set and the
  routing table untestable (DEC-18).
- **`PGVECTOR_TABLE` is interpolated into DDL** and is validated as
  alphanumeric-plus-underscore rather than trusted (`memory.py:339`); psycopg
  cannot parameter-bind identifiers.
- **Circular imports:** none at module scope. `PgVectorMemoryStore.describe()`
  imports `sessions._describe_dsn` inside the function (`memory.py:419`), and
  `db.py` imports psycopg lazily.

## Anti-Patterns

### Routing logic outside the supervisor

**What happens:** adding an `if mode == ...` branch in `service.py`, `chat.py`, or
a worker node to decide what runs next.
**Why it's wrong:** the supervisor stops being the single place that decides
order, and `tests/test_supervisor_routing.py` — which runs with no API keys — no
longer describes real behaviour.
**Do this instead:** add a row to the table in `supervisor_node`
(`graph.py:415-445`) and a test that pins its position relative to its
neighbours.

### Inserting a routing row without deciding its precedence

**What happens:** a new `elif` is appended near the bottom, or dropped in above
the guardrails because it "seems more specific".
**Why it's wrong:** this is the project's known bug class. Row 4
(`no_prior_research`) is only correct because it sits *below* the three
guardrails and *above* the `not research_notes` row; move it below row 6 and a
follow-up silently web-searches instead of refusing.
**Do this instead:** state the intended precedence in a comment, then add a test
asserting the new row both outranks and is outranked by the right neighbours —
`test_caps_outrank_an_approved_draft` and
`test_the_iteration_cap_still_outranks_the_budget` are the models to copy.

### Letting an LLM choose the next node

**What happens:** replacing the `if` chain with a model call that returns a node
name.
**Why it's wrong:** control flow becomes nondeterministic, untestable without
keys, and unauditable (DEC-01).
**Do this instead:** the LLM does the work; the graph decides the order.

### Bypassing the critic on a "cheap" path

**What happens:** a follow-up or short answer returned without a critic hop.
**Why it's wrong:** DEC-04 — the responder writes into the same `draft` field
precisely so the follow-up is fact-checked exactly as hard as the report it's
about.
**Do this instead:** author into `state["draft"]`, set `reviewed = False`, and let
row 8 route to the critic.

### Returning an unapproved draft as if approved

**What happens:** dropping `forced_stop_reason` from a response shape or UI.
**Why it's wrong:** "a silent unapproved draft would be worse than no draft"
(DEC-03). The evals assert this invariant.
**Do this instead:** propagate `forced_stop_reason` and `approved` together, as
`RunResponse` does.

### Calling `client().messages.create()` directly from a node

**What happens:** a node makes its own model call.
**Why it's wrong:** it loses the span, the latency log, and — critically — the
usage fold, so the supervisor's budget row reads a stale cost and the guardrail
fails open.
**Do this instead:** go through `call_model(state, node_name, ...)`
(`graph.py:84`).

### Reaching past the four `MemoryStore` methods

**What happens:** graph code touching `store.entries`, `store._collection`, or a
backend-specific method.
**Why it's wrong:** the seam rots and a backend swap stops being a config change.
A test exists specifically to catch this (DEC-08).
**Do this instead:** `add` / `query` / `len()` / `describe()` only.

### Eager construction at import time

**What happens:** building an Anthropic/Voyage client or running DDL in a
constructor or at module scope.
**Why it's wrong:** eager clients make the module unimportable without keys;
eager DDL meant an unreachable database stopped the service *booting*, making
`/health`'s degraded reporting unreachable by definition, and against a provider
that pauses idle instances produced a deadlock no restart could break (DEC-18).
**Do this instead:** lazy accessor (`graph.client()`) or
`db.ensure_schema()` + `_apply_schema()` on first statement.

### Emitting zero or two terminal SSE events

**What happens:** an exception escaping `_stream`, or a `result` followed by an
`error`.
**Why it's wrong:** headers are already flushed, so a mid-run failure becomes
indistinguishable from a truncated connection (DEC-19).
**Do this instead:** keep the terminal `yield`s inside the single `try`/`except`
in `_stream` (`service.py:232`).

## Error Handling

**Strategy:** retry at the node boundary; classify at the HTTP boundary; never
let a probe or a stream raise.

**Patterns:**
- `@retry_node("name")` wraps every worker (`graph.py:217`, `:245`, `:282`,
  `:326`, `:373`). Retries connection errors and 408/429/5xx only; 400/401 raise
  straight through. Exponential backoff with equal jitter, and a server's
  `retry-after` wins when longer. Every attempt lands in `state["trace"]` as an
  entry with `event == "retry"`, which `RunResponse.retries` counts
  (`service.py:100`). `sleep` and `rng` are injectable (DEC-17).
- `_http_error` (`service.py:174`) maps only known upstream failures —
  `RateLimitError` → 429, `APIStatusError`/`APIConnectionError` → 502. Anything
  else is our bug and surfaces as a 500 with a traceback rather than being
  dressed up as an upstream problem.
- `_probe` (`service.py:347`) never raises: an unreachable store is information
  for the response body, not a reason to fail the probe that decides whether to
  restart the process. `/health` stays 200; `/ready` returns 503.
- `_redact` (`service.py:337`) strips URL credentials from error text before it
  reaches `/health`.
- Guardrail exits are **not** errors — they are a normal `END` carrying
  `forced_stop_reason`.

## Cross-Cutting Concerns

**Logging:** `observability.get_logger()` returns a JSON-formatting logger
(`observability.py:37`). Structured events: `model_call` and `graph_finished`
from `graph.py`; `startup`, `run_finished` and `run_failed` from `service.py`.
Every record carries `run_id`. The split is deliberate (Phase 19): the graph
reports only that it reached its terminal state, and the service emits exactly
one of `run_finished` / `run_failed` per HTTP-initiated run — `run_finished`
alone carries `session_id`, because the id is minted after the graph returns.

**Tracing:** `observability.span()` (`observability.py:101`) is a no-op unless
the `otel` extra is installed; `call_model` opens `node.{name}` per call.

**Cost:** `usage.record()` folds every call into `state["usage"]` inside
`call_model`. Prices are effective-dated; an unpriced model still counts tokens
but flags `pricing_unknown` rather than costing zero, because a cost control
that fails open without saying so is worse than none (DEC-12).

**Validation:** Pydantic at the edge (`AskRequest`, `max_length=2000`), plus
`cleaned()` rejecting blank-after-strip with 422.

**Demo guardrails:** `limits.enforce` (`limits.py:208`) — optional shared token,
per-IP hourly rate limit, and a daily USD cap read from the metrics store.
`/demo` publishes remaining budget so a refused visitor can see it was a shared
cap rather than a broken service.

**Authentication:** none beyond the optional demo token; read-only endpoints are
open by design.

---

*Architecture analysis: 2026-08-04*
