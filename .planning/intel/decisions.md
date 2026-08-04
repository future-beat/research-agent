# Decisions

**STATUS OF EVERY ENTRY ON THIS PAGE: SOFT / REVISABLE.**

All three ingested source documents classified as `DOC`, not `ADR`. Nothing here
is LOCKED. No entry below carries an `Accepted` status, a supersession chain, or
any other ADR signal — they are architectural decisions recorded as narrative
rationale, lifted into decision form by synthesis.

Consequence for downstream consumers: any of these may be reversed by a new
requirement without a supersession ceremony. Several **are** being reversed in
the next milestone (see `constraints.md` → "Requirements that reverse a stated
design position"). Do not treat any DEC- entry as a constraint on planning.

Recommended follow-up (not performed here): promote the high-traffic entries —
DEC-01, DEC-02, DEC-04, DEC-13, DEC-20 — into numbered ADRs with explicit
status, so the next reversal is recorded rather than silent.

Primary source: `docs/DESIGN.md` (22 decision candidates carried from the
classifier's non-schema `decision_candidates` field, plus in-document rationale).
Supporting: `README.md`, `docs/OPERATIONS.md`.

---

## Graph and routing

### DEC-01 — Routing is a deterministic Python state machine, not an LLM prompt
- source: `docs/DESIGN.md` ("The graph"), `README.md` ("Architecture")
- status: soft (DOC-derived)
- scope: `supervisor_node`, control flow
- decision: `supervisor_node` is a chain of `if` statements over `AgentState`. No
  model call decides the next hop. Control flow is deterministic, unit-testable,
  identical every run. The LLM does the work; the graph decides the order.
- rejected alternative: an LLM router choosing the next node.
- consequence: the routing table is testable with no API keys (see DEC-17).

### DEC-02 — The critic is a separate node with its own rubric
- source: `docs/DESIGN.md` ("The graph")
- status: soft (DOC-derived)
- scope: critic node
- decision: draft and grounding-check are separate model calls. The critic is
  given the research notes as the *sole* source of truth.
- rejected alternative: one model drafting and self-assessing in a single call —
  "reliably produces 'looks good to me.'"

### DEC-03 — Every loop is bounded and forced stops are reported honestly
- source: `docs/DESIGN.md` ("The graph")
- status: soft (DOC-derived)
- scope: `MAX_REVISIONS`, `MAX_ITERATIONS`, `forced_stop_reason`
- decision: `MAX_REVISIONS` caps the critic↔writer cycle; `MAX_ITERATIONS` is a
  backstop on total supervisor turns. When a cap fires, `forced_stop_reason`
  propagates to output so the user knows the report was never approved.
- rationale: "a silent unapproved draft would be worse than no draft."

### DEC-04 — Follow-ups reuse the critic instead of bypassing it; no prior notes stops with `no_prior_research`
- source: `docs/DESIGN.md` ("The graph"), `README.md` (API, Limitations)
- status: soft (DOC-derived) — **being reversed in part; see REQ-followup-live-search**
- scope: responder node, follow-up mode
- decision: the responder writes into the same `draft` field as the writer, so
  the critic grades a follow-up with the same rubric and revision loop. The
  responder is told "the research didn't cover that" is a *correct* answer. A
  follow-up with no prior notes stops with `no_prior_research` rather than
  answering from model knowledge — "the single failure mode this whole pipeline
  exists to prevent."
- rejected alternative: a cheaper uncritiqued follow-up path; answering from
  parametric knowledge when notes are absent.

### DEC-05 — Inference settings are tuned per node, not globally
- source: `docs/DESIGN.md`, `docs/OPERATIONS.md` (config table)
- status: soft (DOC-derived)
- scope: per-node `output_config`
- decision: classifier runs thinking-disabled under a 20-token ceiling (one word
  from a fixed set); researcher/writer/critic run adaptive thinking. Everything
  at `effort: "medium"`.

### DEC-06 — Every run is traceable via `state["trace"]`
- source: `docs/DESIGN.md`
- status: soft (DOC-derived)
- scope: state trace, `/trace`, REPL
- decision: each node appends routing decisions, recall counts, draft lengths,
  and critic verdicts to `state["trace"]`.

### DEC-21 — `MAX_ITERATIONS` is derived from `MAX_REVISIONS`
- source: `docs/DESIGN.md` ("Testing"), `docs/OPERATIONS.md` (config table)
- status: soft (DOC-derived)
- scope: guardrail relationship
- decision: the iteration backstop is computed from the revision cap so it always
  stays above it (currently `2` → `12`). A test pins the relationship.
- rationale: with `MAX_ITERATIONS=8` / `MAX_REVISIONS=2` the revision cap was
  *unreachable* in research mode; the backstop always fired first and the run
  reported `max_iterations_exceeded` (reads like an internal fault) instead of
  `max_revisions_exceeded` (the truth: the draft never got grounded). Found by
  the evals, not by unit tests — each cap was correct in isolation.

---

## Memory

### DEC-07 — Memory is vector retrieval with a relevance floor, not a growing prompt
- source: `docs/DESIGN.md` ("Memory"), `README.md`
- status: soft (DOC-derived)
- scope: note recall
- decision: notes embedded with `voyage-3.5`, retrieved by cosine similarity
  above a `min_similarity` floor (default `0.3`), so an unrelated past task
  cannot leak into the current one. The researcher is told to prefer information
  not already covered — memory as coverage-expander, not echo.

### DEC-08 — `MemoryStore` and `Embedder` are separate seams, guarded by a reach test
- source: `docs/DESIGN.md` ("Memory")
- status: soft (DOC-derived)
- scope: `MemoryStore` ABC (`add`, `query`, `len`, `describe`), `Embedder` protocol
- decision: store and embedder are independent seams so switching stores never
  silently switches embedding models — "that would invalidate every vector
  already written." A test asserts the graph never reaches past those four
  methods, so the seam can't rot.
- note: DESIGN.md names three implementations (JSON, in-memory, Chroma); the
  current count is four (pgvector added in Phase 8). See INGEST-CONFLICTS INFO.

### DEC-09 — pgvector/HNSW replaces the O(n) scan and makes recall shared across machines
- source: `docs/DESIGN.md` ("Memory")
- status: soft (DOC-derived)
- scope: pgvector backend
- decision: brute-force stores score every note per query and pull the whole
  corpus into the agent process. HNSW keeps the same cosine ranking and stops
  doing either; being shared, every machine recalls everything the agent learned.

### DEC-10 — Migration copies embeddings rather than re-embedding
- source: `docs/DESIGN.md` ("Memory"), `docs/OPERATIONS.md` ("Going stateless")
- status: soft (DOC-derived) — **tension with REQ-embedding-model-migration**
- scope: `research_agent.migrate`
- decision: the SQLite→Postgres migration carries notes across with existing
  embeddings.
- rationale: free and exact, but the real reason is that re-embedding would
  change recall behaviour at the same moment infrastructure changes — "two
  suspects and no way to separate them."

---

## Cost and metrics

### DEC-11 — The spend cap is a routing rule, not a wrapper
- source: `docs/DESIGN.md` ("Cost")
- status: soft (DOC-derived)
- scope: `AGENT_MAX_RUN_COST_USD`, supervisor
- decision: every node folds usage into `state["usage"]` before returning, so the
  supervisor reads running cost on its next hop. Budget is one more row in the
  same routing table with the same `forced_stop_reason` machinery.
- consequence: checked *between* nodes (cost is only knowable after a call
  returns), so a run can overshoot by at most one node, never unboundedly.

### DEC-12 — Prices are effective-dated; unpriced models report `pricing_unknown`
- source: `docs/DESIGN.md` ("Cost"), `README.md`
- status: soft (DOC-derived)
- scope: `usage.py` price table, `/pricing`
- decision: `price_for()` resolves a rate for a date. Sonnet 5 is on introductory
  $2/$10 per MTok through **2026-08-31**, moving to $3/$15 on 2026-09-01; a test
  pins both windows. Cache-rate constants are asserted to be the documented 1.25×
  and 0.1× of base input rather than trusted as typed-in numbers.
- decision (companion): a model with no price-table row still has tokens counted,
  but `cost_usd` becomes a floor and `pricing_unknown` goes true. Costing unknown
  calls at zero "would quietly disable the budget guardrail — a cost control that
  fails open without saying so is worse than none."

### DEC-13 — Failed runs count in the metrics denominator; zero-denominator rates return `null`
- source: `docs/DESIGN.md` ("Cost")
- status: soft (DOC-derived)
- scope: `/metrics`
- decision: a failed run opens no session but still burned tokens and still
  happened, so it is counted. Rates with a zero denominator return `null`, not
  `0.0` — "no runs yet" and "nothing was approved" are different facts. Latency
  percentiles cover completed runs only; mixing in time-to-failure "makes an
  outage look like a speed-up."

---

## Data and backends

### DEC-14 — Sessions store completed runs in SQLite, deliberately not LangGraph's checkpointer
- source: `docs/DESIGN.md` ("Data and backends")
- status: soft (DOC-derived)
- scope: `sessions.py`
- decision: the final state of every run is persisted; follow-ups arrive as
  separate requests, likely on a different worker, possibly after a redeploy.
- rejected alternative: LangGraph's checkpointer — "solves resuming a
  half-finished graph, a different feature with a different failure model," and
  would couple the schema to LangGraph internals.
- consequence accepted: a crash mid-run loses that run and the caller retries.

### DEC-15 — One `DATABASE_URL` moves sessions, metrics, and notes together
- source: `docs/DESIGN.md`, `docs/OPERATIONS.md`, `README.md`
- status: soft (DOC-derived)
- scope: backend selection
- decision: all three stores default to Postgres when `DATABASE_URL` is present,
  local disk when it isn't. Any one can still be pinned explicitly.
- rejected alternative: three separate backend flags — "more configurable and
  worse: the failure you'd actually hit is setting one and forgetting another,"
  producing a deployment that degrades only as slowly worsening answers.

### DEC-16 — "Swappable" is enforced by shared behavioural tests and a byte-identical metrics assertion
- source: `docs/DESIGN.md` ("Data and backends")
- status: soft (DOC-derived)
- scope: cross-backend test suite
- decision: behavioural tests live in one file and run against every backend; one
  test asserts both metrics backends produce byte-identical summaries from
  identical input.
- rationale: two hand-written SQL dialects agreeing "quietly stops being true" —
  SQLite sums booleans where Postgres needs `COUNT(*) FILTER`, and Postgres
  returns `SUM(BIGINT)` as `Decimal`, which isn't JSON-serialisable and would
  have 500'd `/metrics` on the first recorded run.

---

## Reliability

### DEC-17 — Retries at the node boundary, only for retryable statuses, with recorded attempts and injectable sleep/rng
- source: `docs/DESIGN.md` ("Reliability"), `docs/OPERATIONS.md` (config table)
- status: soft (DOC-derived)
- scope: `retry.py`
- decision: retry at the node boundary (a whole unit of work), so a transient 529
  costs one repeated node rather than a failed run. Retry only connection errors
  and 408/429/5xx; raise straight through on 400/401. Exponential backoff with
  equal jitter; a server's `retry-after` wins when longer ("our curve is a guess
  and the header isn't"). Every attempt lands in `state["trace"]`. `sleep` and
  `rng` are injectable so retry tests run in milliseconds and assert exact delays.

### DEC-18 — Nothing is constructed at import time; the service boots degraded and self-heals
- source: `docs/DESIGN.md` ("Reliability")
- status: soft (DOC-derived)
- scope: API clients, Postgres DDL
- decision: both API clients are built on first use; Postgres stores *register*
  their schema and apply it on first use rather than executing DDL in `__init__`.
- rationale: eager clients would make modules unimportable without a full key set
  — the routing table could not be tested at all. Eager DDL meant an unreachable
  database stopped the service *booting*, making `/health`'s degraded-dependency
  reporting unreachable by definition, and against a provider that pauses idle
  instances produced a deadlock no restart could break.

### DEC-19 — A stream emits exactly one terminal event, including an in-band `error` event
- source: `docs/DESIGN.md` ("Reliability"), `README.md` (SSE sample)
- status: soft (DOC-derived)
- scope: `_stream` in `service.py`
- decision: `_stream` catches everything and emits a terminal `error` event —
  exactly one terminal event per stream, never both, never neither.
- rationale: by the time a node dies the `200` and headers are gone; without it a
  mid-run failure is indistinguishable from a truncated connection.

---

## Testing and evals

### DEC-20 — Offline evals grade the pipeline only, with the caveat printed under every offline run
- source: `docs/DESIGN.md` ("Testing"), `README.md`
- status: soft (DOC-derived) — **tension with REQ-offline-eval-quality**
- scope: `evals/`
- decision: offline runs drive the real compiled graph with a scripted client
  whose output is authored in the dataset — free, deterministic, safe on every
  push. It checks routing, both guardrails, follow-up isolation, and the
  invariant that an unapproved draft is never returned as if approved. It
  *cannot* speak to answer quality, and the CLI prints that caveat every run:
  "a green suite that quietly implies 'the model is good' is worse than no suite."

### DEC-22 — The eval judge runs on a stronger model than the pipeline and returns a structured verdict
- source: `docs/DESIGN.md` ("Testing"), verified in `evals/graders.py`, `src/research_agent/graph.py`
- status: soft (DOC-derived) — **directly implicated by REQ-independent-critic-model**
- scope: `evals/graders.py`
- decision: judge on Opus 5 (`JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")`)
  against a Sonnet 5 pipeline (`MODEL = "claude-sonnet-5"`), returning a
  structured verdict rather than a text convention.
- rationale: the in-graph critic shares the writer's model — "good enough to
  catch ungrounded claims, not an independent evaluator." A judge on that same
  model "would inherit exactly the blind spots it exists to find." A harness that
  mis-parses a text verdict "reports a confident wrong number, which is worse
  than crashing."
- note: this decision is the *compensating control* for the shared critic model.
  If REQ-independent-critic-model lands, the rationale for the stronger judge
  changes and should be re-derived, not inherited.

---

## Packaging

### DEC-23 — The web server is isolated in a `[service]` extra; `src/` layout keeps tests and evals out of the image
- source: `docs/DESIGN.md` ("Packaging"), `docs/OPERATIONS.md` ("Project layout"), `README.md`
- status: soft (DOC-derived)
- scope: `pyproject.toml` extras, image contents
- decision: base package is the agent alone; `[service]` adds FastAPI/uvicorn;
  `[dev]` adds pytest/ruff. The image installs `[service]`, never `[dev]`.
  `src/` layout means the package is only importable once installed, so a passing
  test run can't rely on a module that would never reach the image. `tests/` and
  `evals/` sit outside the package — "the eval dataset contains scripted model
  output, which has no business inside a production image."
