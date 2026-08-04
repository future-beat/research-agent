# Requirements

Source: `README.md` → `## Limitations`, nine items, framed as "Known, and
deliberate for the scope." The project owner has decided to take on **all nine**
in the next milestone. They are therefore captured here as requirements, not as
accepted constraints.

**Important framing:** these are *not* bug reports. Every one closes a gap that
was consciously left open. Several **reverse** a stated design position rather
than fix a defect — see `constraints.md` → "Requirements that reverse a stated
design position" before planning any of them. Acceptance criteria below are
derived from the limitation text plus the corresponding DESIGN.md rationale;
they are proposals, not user-ratified criteria.

No competing acceptance variants exist — a single source document produced all
nine, so nothing here needed variant preservation.

---

### REQ-followup-live-search — Follow-ups can reach for new information
- source: `README.md` ("Follow-ups can't reach for new information")
- scope: responder node, supervisor routing, follow-up mode
- current state: by design, a follow-up needing a fresh search gets "the research
  didn't cover that" rather than an answer.
- description: allow a follow-up to trigger a new research pass when the existing
  notes cannot support an answer, instead of terminating with a refusal.
- proposed acceptance criteria:
  - A follow-up whose question is unsupported by prior notes routes to the
    researcher rather than returning "the research didn't cover that."
  - New notes join the session's note set and are attributed to the follow-up turn.
  - The critic still grades the follow-up answer against notes as sole source of
    truth (DEC-02, DEC-04 grounding invariant preserved).
  - Spend cap and iteration/revision caps still bound the expanded path (DEC-03, DEC-11).
  - `no_prior_research` behaviour is redefined or retired explicitly, not left dangling.
- reverses: **DEC-04** (strongest reversal in the set)

### REQ-independent-critic-model — The critic does not share the writer's model
- source: `README.md` ("The critic shares the writer's model")
- scope: critic node, `MODEL` in `graph.py`, eval judge rationale
- current state: `MODEL = "claude-sonnet-5"` is used by every node including the
  critic (verified in `src/research_agent/graph.py:38`). The eval judge runs on
  Opus 5 "precisely because of this."
- description: give the critic an independent model so it is a genuinely
  independent evaluator rather than "independent enough."
- proposed acceptance criteria:
  - Critic model is separately configurable from the writer/researcher model.
  - Cost accounting prices each model correctly per node (DEC-12 price table must
    carry a row for whatever the critic runs on, or `pricing_unknown` fires).
  - The per-run spend cap accounts for the more expensive critic path (DEC-11).
  - The README Limitations claim and DESIGN.md's judge rationale (DEC-22) are
    both updated — the compensating control changes meaning.
- reverses: **DEC-22's premise** (second-strongest reversal in the set)

### REQ-offline-eval-quality — Evals can measure answer quality
- source: `README.md` ("Offline evals can't measure answer quality, and twelve
  live cases are a smoke test, not a benchmark")
- scope: `evals/`, dataset, graders
- current state: offline runs use a scripted client whose answers are authored in
  the dataset, so they cannot grade quality; only `--live` can, over 12 cases.
- description: make answer quality measurable, and grow the live set beyond
  smoke-test size.
- proposed acceptance criteria:
  - Answer quality is graded by some mechanism that does not require every push
    to spend money (e.g. recorded-response fixtures, a periodic scheduled live
    run, or a separately gated job).
  - The live case count grows past 12 to a size defensible as a benchmark.
  - Offline determinism, zero-key operation, and the every-push CI gate survive
    (DEC-20, and OPERATIONS' `ANTHROPIC_API_KEY=""` invariant).
  - The printed offline caveat is updated to match whatever becomes true.
- tension with: **DEC-20**

### REQ-real-cost-accounting — Cost reflects the actual bill
- source: `README.md` ("Cost is computed from list prices")
- scope: `usage.py`, `/pricing`, `/metrics`
- current state: list prices only; no enterprise discounts, no `inference_geo`
  multiplier. `/metrics` "tracks the shape of the bill, not the bill."
- description: support discount and geo multipliers so reported cost approximates
  the real invoice.
- proposed acceptance criteria:
  - A configurable discount factor and `inference_geo` multiplier feed cost
    computation.
  - Effective-dating (DEC-12) still applies, including across the 2026-08-31
    Sonnet 5 introductory-price boundary.
  - `/pricing` exposes which multipliers are in effect, not just base rates.
  - `pricing_unknown` semantics are unchanged — still fails loud, never zero.
- reverses: nothing; pure extension of DEC-12.

### REQ-store-lifecycle-and-ownership — Stores do not grow without bound; sessions have owners
- source: `README.md` ("Stores grow without bound")
- scope: `memory.py`, `sessions.py`, service auth surface
- current state: no eviction, dedup, or summarisation for notes; no expiry or
  ownership for sessions. "Anyone who can reach the service can read any session."
- description: two coupled concerns — bounded note growth, and session ownership
  with expiry. The README lists them as one item; planning may split them.
- proposed acceptance criteria:
  - Notes have at least one bound: eviction, dedup, or summarisation.
  - Sessions carry an owner identity and an expiry; `/sessions` lists only the
    caller's sessions and `/sessions/{id}` 403s or 404s for others.
  - Applies uniformly across SQLite and Postgres backends, proven by the shared
    behavioural suite (DEC-16).
  - Note deletion is consistent across JSON/memory/Chroma/pgvector stores.
- interacts with: REQ-demo-authentication (ownership needs an identity to attach to)

### REQ-multi-machine-state — SQLite no longer pins the service to one machine
- source: `README.md` ("SQLite pins you to one machine")
- scope: `fly.toml` (`min_machines_running`, `[[mounts]]`), deployment topology
- current state: `min_machines_running = 1` on purpose; a second machine would
  hold its own database and 404 on sessions that demonstrably exist.
  `DATABASE_URL` lifts the constraint but has not been taken.
- description: complete the documented Postgres path and actually run more than
  one machine.
- proposed acceptance criteria:
  - `DATABASE_URL` set in production; `research_agent.migrate` run (dry-run then
    real) and verified via `/health` backend reporting.
  - `[[mounts]]` removed from `fly.toml`; machine count > 1.
  - Sessions resolve identically from any machine.
  - `tests/test_deploy_config.py` guards updated for the new topology.
- note: not a design reversal — this is the path DEC-15 and OPERATIONS already
  lay out. Blocked-adjacent on the deploy-gating question (see INGEST-CONFLICTS).

### REQ-connection-pool — Postgres access is pooled
- source: `README.md` ("No connection pool")
- scope: `db.py`
- current state: one lock-guarded Postgres connection per machine — "right when a
  run occupies a worker for tens of seconds, but a ceiling worth knowing before
  raising concurrency."
- description: replace the single lock-guarded connection with a pool.
- proposed acceptance criteria:
  - A pool with configurable min/max size replaces the shared single connection.
  - Reconnect-on-failure behaviour of the current `db.py` is preserved.
  - Lazy schema application (DEC-18) still holds — no DDL at construction.
  - Byte-identical metrics assertion across backends still passes (DEC-16).
  - `PG_CONNECT_TIMEOUT` semantics documented for the pooled case.
- reverses: the sizing judgement in the current design, mildly.

### REQ-embedding-model-migration — Changing embedding model does not require a hand-built new table
- source: `README.md` ("Changing embedding model means a new pgvector table")
- scope: `memory.py` pgvector backend, `PGVECTOR_TABLE`, `VECTOR_DIMENSIONS`,
  `research_agent.migrate`
- current state: the pgvector column width is fixed at creation (1024 for
  `voyage-3.5`); the dimension check "fails loudly but can't migrate for you."
- description: provide a migration path when the embedding model or dimension changes.
- proposed acceptance criteria:
  - A command re-embeds an existing corpus into a new table at the new dimension.
  - The loud dimension check remains — it must not become a silent coercion.
  - Cutover is explicit and reversible; the old table survives until confirmed.
  - Cost of re-embedding is reported before the run starts.
- tension with: **DEC-10** (migration deliberately copies embeddings rather than
  re-embedding, specifically to avoid changing recall behaviour mid-migration).
  Any re-embedding path must isolate the recall change from infrastructure change.

### REQ-demo-authentication — The public demo identifies callers
- source: `README.md` ("The public demo is rate-limited, not authenticated")
- scope: `limits.py`, `service.py`, `DEMO_TOKEN`, `TRUST_FORWARDED_FOR`
- current state: guardrails bound spend (`AGENT_MAX_RUN_COST_USD` $1.00,
  `DEMO_DAILY_USD_CAP` $5.00, `DEMO_RATE_LIMIT_PER_HOUR` 10/IP) but "don't
  identify callers." `DEMO_TOKEN` is a shared secret, not an identity.
- description: introduce real caller identity for the public demo.
- proposed acceptance criteria:
  - Callers authenticate to an identity, not a shared token.
  - Rate limit and rolling spend cap key on identity rather than visitor IP,
    making `TRUST_FORWARDED_FOR` no longer load-bearing for fairness.
  - Identity is the anchor for session ownership (REQ-store-lifecycle-and-ownership).
  - The live demo remains usable without friction that defeats its purpose —
    this is a portfolio demo, and an auth wall has a cost.
- reverses: the deliberate scope choice that guardrails-not-identity is enough.
