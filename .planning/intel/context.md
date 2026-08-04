# Context

Running notes by topic from the three ingested documents. All three classified
`DOC` at `medium` confidence.

Sources:
- `README.md`
- `docs/DESIGN.md`
- `docs/OPERATIONS.md`

---

## Project identity

- source: `README.md`
- A supervisor-routed multi-agent research pipeline. Ask a question; it
  classifies the topic, searches the web, drafts a report, then fact-checks the
  draft against its own research notes and revises until every claim is grounded.
- Positioned explicitly as "a production service, not a notebook": bounded loops,
  per-run cost accounting, a spend cap, swappable Postgres/pgvector backends, an
  eval harness, and 364 tests that run with no API keys.
- Live at `research-agent.fly.dev`. Repo `github.com/future-beat/research-agent`. MIT.
- Stack: Python 3.10+ · LangGraph · Claude Sonnet 5 · Voyage embeddings ·
  FastAPI · SQLite/Postgres.
- The README's own framing of the interesting part: "Watch the critic push back
  — that's the part worth seeing."

## Phase status

- source: `README.md` ("## Status")
- All nine phases marked complete; no open roadmap items derive from this section.
  1. Core loop — supervisor pattern; deterministic Python routing.
  2. Memory — Voyage embeddings, cosine recall with relevance floor, persisted.
  3. Conversation & resilience — follow-ups over prior notes; pluggable stores;
     per-node retry with jittered backoff.
  4. Service — FastAPI, blocking and SSE, sessions surviving restart.
  5. Cost & observability — date-aware price table, spend cap as routing rule,
     JSON logs, `/metrics`.
  6. Evals — twelve-case golden set, deterministic graders plus an LLM judge on a
     stronger model. "Found a real bug on its first run."
  7. Ship it — two-stage Dockerfile, non-root, healthchecked; CI runs lint, tests,
     evals, container smoke test.
  8. Stateless — Postgres and pgvector behind existing interfaces; one contract
     suite proves every backend agrees.
  9. Demo & guardrails — streaming demo page, rolling spend cap, per-visitor rate
     limit, optional token.
- Next milestone is therefore net-new work, sourced from `## Limitations`.

## Graph topology

- source: `README.md` ("Architecture"), `docs/DESIGN.md`
- Every worker returns to a central supervisor which re-reads state and picks the
  next hop. Nodes: classifier, researcher, writer, responder, critic.
- Routing table, in order, *is* `supervisor_node`:
  - iteration or revision cap exceeded → END (sets `forced_stop_reason`)
  - run cost over budget → END (`budget_exceeded`)
  - follow-up with no prior notes → END (`no_prior_research`)
  - `topic_type` unset → classifier
  - no research notes → researcher
  - no draft → author
  - draft not yet reviewed → critic
  - critic returned `REVISE` → author (revision)
  - otherwise, approved → END
- "author" is the writer in research mode, the responder in follow-up mode. That
  substitution is the **only** thing `mode` changes; caps, critic hop, and
  revision loop are byte-identical in both.
- The classifier's label is load-bearing, not cosmetic: it selects the
  researcher's strategy *and* the critic's rubric. A `technical` run is hunted
  for numbers absent from the notes; a `sparse` one is checked for overstated
  confidence.

## API surface

- source: `README.md` ("API")
- `GET /` — demo page in a browser, JSON index to `curl`
- `POST /research` · `/research/stream` — full pipeline, blocking or SSE
- `POST /sessions/{id}/ask` · `/ask/stream` — follow-up from that session's
  notes, **no new search** (the behaviour REQ-followup-live-search targets)
- `GET /sessions` · `/sessions/{id}` · `/{id}/trace` — list, thread, node-by-node trace
- `GET /health` · `/ready` — liveness always 200 · readiness 503 when a store is down
- `GET /metrics` · `/pricing` · `/demo` — volume/approval rate/cost/latency ·
  live rates · guardrail state
- Interactive docs at `/docs`. SSE emits `node` events then exactly one terminal
  `result` (or `error`) event.

## Testing posture

- source: `README.md` ("Tests and evals"), `docs/DESIGN.md` ("Testing")
- `pytest` — 364 tests, ~10s, no API keys, no network.
- `python -m evals` — 12 golden cases, offline and free.
- `python -m evals --live` — real API plus LLM-judge graders, costs money.
- What is faked and why: the Claude client is stubbed and a fake embedder
  replaces Voyage; SQLite, Postgres and the FastAPI app are **real**, "because
  persistence and routing are what would be worth faking least."
- Postgres runs in CI against a `pgvector/pgvector` container with a guard that
  fails rather than skips.

## Notable war stories worth preserving

- source: `docs/DESIGN.md`
- **The evals earned their keep on run one.** `MAX_ITERATIONS=8` /
  `MAX_REVISIONS=2` made the revision cap unreachable in research mode; reaching
  `revision_count > 2` needs supervisor turn 10, so the backstop always fired
  first and reported `max_iterations_exceeded` — reading as an internal fault
  instead of the truth, `max_revisions_exceeded` (the draft never got grounded).
  Both caps "worked"; they were the wrong way round. No unit test caught it
  because each cap was correct in isolation — "it took running whole scenarios
  and asserting on *which* guardrail fired."
- **The `Decimal` that would have 500'd `/metrics`.** Postgres returns
  `SUM(BIGINT)` as `Decimal`, which isn't JSON-serialisable; the cross-backend
  contract suite caught it before the first recorded run.
- **The boot deadlock.** Running DDL in `__init__` meant an unreachable database
  stopped the service booting, so `/health`'s degraded reporting was unreachable
  by definition — and against a provider that pauses idle instances, the app
  couldn't boot, so it never connected, so nothing ever woke the database.
- **The silent `internal_port` merge.** A Fly Launch PR set `internal_port` to
  `8080` against a container listening on `8000`, touching a line unchanged since
  the branch point — merged with no conflict shown, surfaced only as every
  request failing.

## Ingest provenance

- Classification files: `.planning/intel/classifications/README-7b3e9a41.json`,
  `DESIGN-a7f3c21b.json`, `OPERATIONS-0a7f3c21.json`.
- The classifier for `docs/DESIGN.md` emitted a non-schema `decision_candidates`
  array holding 22 architectural decisions. It was **read and carried**, not
  discarded — it is the real architectural record for this project despite the
  document classifying as `DOC`. Those 22 form the backbone of `decisions.md`.
- Both classifier hash suffixes are placeholders, not real SHA-256 of the source
  path (the classifier had no hashing tool). Do not rely on them for change
  detection.
- Cross-ref graph is mutual: README ↔ DESIGN, README ↔ OPERATIONS, OPERATIONS →
  DESIGN. These are navigational "see also" links, not derivation edges. See
  INGEST-CONFLICTS INFO for why the cycle gate was not tripped.
