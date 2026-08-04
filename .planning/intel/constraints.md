# Constraints

Operational invariants and hard limits lifted from `docs/OPERATIONS.md` (and, for
the reversal analysis, `README.md` + `docs/DESIGN.md`).

Source type note: OPERATIONS.md classified `DOC`, not `SPEC`. Its two contract
tables document *existing defaults* rather than mandating them, so nothing below
is a ratified SLO or API contract. Treat as observed invariants — accurate as of
ingest, revisable by decision.

---

## Requirements that reverse a stated design position

This is the most important section on this page. All nine `## Limitations` items
are being taken on in the next milestone, but they are not nine bugs. Several
reverse a position DESIGN.md argues *for*. Reversing them is legitimate — but it
must be an explicit decision, not a silent consequence of "closing the
limitations list."

**Strongly design-reversing (the two flagged as most significant):**

1. **REQ-followup-live-search reverses DEC-04.**
   `README.md` says follow-ups can't reach for new information "**By design**."
   `docs/DESIGN.md` builds the whole follow-up path around it: the responder is
   *told* that "the research didn't cover that" is a correct answer, and a
   follow-up with no prior notes stops with `no_prior_research` rather than
   answering from model knowledge — which DESIGN.md calls "the single failure
   mode this whole pipeline exists to prevent." Adding live search to follow-ups
   does not patch an oversight; it retires a stated invariant. Planning must say
   what replaces the grounding guarantee, and what `no_prior_research` now means.

2. **REQ-independent-critic-model reverses the premise DEC-22 rests on.**
   The shared critic model is not accidental. `docs/DESIGN.md` uses it as the
   explicit justification for the stronger eval judge: "The in-graph critic
   shares the writer's model — good enough to catch ungrounded claims, not an
   independent evaluator... so it runs on Opus 5 against Sonnet 5." Giving the
   critic its own model removes the reason the judge is stronger. The judge
   decision must be re-derived rather than inherited, and the README sentence
   "The eval judge runs on a stronger model precisely because of this" becomes
   false the moment this lands.

**Also design-reversing, at lower stakes:**

3. **REQ-embedding-model-migration is in tension with DEC-10.** The migration
   deliberately copies embeddings instead of re-embedding, specifically so recall
   behaviour doesn't change at the same moment infrastructure does ("two suspects
   and no way to separate them"). A re-embedding migration path must isolate
   those two variables or it re-opens exactly the ambiguity DEC-10 avoided.

4. **REQ-offline-eval-quality is in tension with DEC-20.** DESIGN.md argues
   offline evals *should not* claim to grade quality, and prints that caveat under
   every run because "a green suite that quietly implies 'the model is good' is
   worse than no suite." Grading quality is fine; grading it in a way that
   re-introduces the implication, or that breaks the free/deterministic/every-push
   property, is the reversal to watch.

5. **REQ-demo-authentication reverses a scope choice.** "Rate-limited, not
   authenticated" was a deliberate call that guardrails bounding *spend* were
   sufficient for a public portfolio demo. Authenticating adds friction to the
   thing whose entire value is that a stranger can click it.

6. **REQ-connection-pool reverses a sizing judgement.** The single lock-guarded
   connection is described as "right when a run occupies a worker for tens of
   seconds." Pooling is correct only alongside raised concurrency.

**Not reversals — completion of already-stated paths or pure extensions:**

- REQ-multi-machine-state — DEC-15 and OPERATIONS already document `DATABASE_URL`
  as the lift; this executes it.
- REQ-real-cost-accounting — extends DEC-12's price table, contradicts nothing.
- REQ-store-lifecycle-and-ownership — the README calls unbounded growth a known
  gap, not a chosen property.

---

## Deployment invariants

- source: `docs/OPERATIONS.md` ("Fly.io", "Container")
- `min_machines_running = 1` while SQLite is the backend. A second machine holds
  its own database and 404s on sessions that demonstrably exist. Lifted only by
  `DATABASE_URL`.
- A volume must be mounted at `/data`, or both SQLite databases and the vector
  store die with the container and "the memory feature quietly becomes a no-op."
- The container listens on port **8000** (`internal_port`). A Fly Launch PR once
  set it to `8080` and merged with **no conflict shown**, surfacing only as every
  request failing. `tests/test_deploy_config.py` fails the build on that case and
  on `app` being pointed at the Postgres cluster.
- **Never merge Fly's "New files from Fly.io Launch" pull requests.** They have
  twice broken this deploy. Copy wanted values out by hand and close the PR.
- Always pass `-a` explicitly to `fly` commands. `fly postgres create` makes a
  separate Fly-managed app: you attach to it, you never deploy into it.
- Credentials never reach an image layer: `.env` is in `.dockerignore`, compose
  passes keys through from the environment, Fly uses `fly secrets`. `/health`
  reports key *presence*, never value.
- The image runs non-root, installs `[service]` only, excludes `tests/` and `evals/`.
- Postgres requires the `vector` extension for the pgvector notes backend.
- Switching backends does **not** migrate existing data — each store owns its own.

## CI invariants

- source: `docs/OPERATIONS.md` ("CI")
- Gates: `ruff` · 364 tests · 12 offline eval cases · image build · container
  smoke test (boot the image, probe `/health`, `/metrics`, `/pricing`,
  `/openapi.json`, then wait for Docker's `HEALTHCHECK`).
- Every gate runs with `ANTHROPIC_API_KEY=""`. A suite needing a live key "breaks
  on forks, on key rotation, and during someone else's outage — and bills you for
  every push." The offline eval step doubles as a guard on the lazy-client
  decision (DEC-18): if a client becomes eager again, that step fails.
- The pgvector guard test **fails rather than skips** when the database is
  missing, "so the build can't go green over an untested backend."
- `main` is protected: both checks must pass before a PR can merge; force pushes
  and branch deletion are blocked.
- **Deploys are not CI-gated.** Branch protection gates pull requests only; a
  direct push to `main` that fails tests still deploys. See INGEST-CONFLICTS
  WARNING — this statement is disputed and must be verified before it is planned
  against.

## Configuration defaults (observed, not mandated)

- source: `docs/OPERATIONS.md` ("Configuration")
- Code knobs: `MAX_REVISIONS` `2`; `MAX_ITERATIONS` derived, `12`;
  `MODEL` `claude-sonnet-5`; effort `medium`, thinking `adaptive`
  (`disabled` on the classifier); `min_similarity` `0.3`.
- Spend: `AGENT_MAX_RUN_COST_USD` `1.00` per run (`0` disables);
  `DEMO_DAILY_USD_CAP` `5.00` rolling 24h across all callers;
  `DEMO_RATE_LIMIT_PER_HOUR` `10` per visitor IP.
- Retry: `AGENT_MAX_ATTEMPTS` `4` (including the first);
  `AGENT_RETRY_BASE_DELAY` `1.0`s; `AGENT_RETRY_MAX_DELAY` `30.0`s.
- Vectors: `VECTOR_DIMENSIONS` `1024` (fixed at table creation, for `voyage-3.5`);
  `PGVECTOR_TABLE` `research_notes`; `VOYAGE_EMBEDDING_MODEL` `voyage-3.5`.
- Postgres: `PG_CONNECT_TIMEOUT` `3`s.
- Backends: `VECTOR_STORE` / `SESSION_BACKEND` / `METRICS_BACKEND` all follow
  `DATABASE_URL` by default. `VECTOR_STORE=chroma` needs the `[chroma]` extra.
- Demo/observability: `DEMO_TOKEN` unset; `TRUST_FORWARDED_FOR` `false`;
  `LOG_FORMAT` `json`; `LOG_LEVEL` `INFO`; `OTEL_ENABLED` `true`.
- Research strategies and critic rubrics live in the `RESEARCH_STRATEGY` and
  `CRITIC_RUBRIC` dicts; adding a topic type means adding a key to both.

## Time-sensitive constraint

- source: `docs/DESIGN.md` ("Cost")
- Claude Sonnet 5 introductory pricing ($2/$10 per MTok) expires **2026-08-31**;
  rates move to $3/$15 on 2026-09-01. Ingest date is 2026-08-04. Any cost figure
  in planning documents has a 27-day shelf life; `/pricing` is the live source.

## Architectural boundary

- source: `docs/OPERATIONS.md` ("Project layout")
- `service.py` is deliberately thin: validate input, pick a state constructor,
  run the graph, persist the result. **No routing logic lives there** — "any that
  did would mean the supervisor is no longer the single place deciding what runs
  next." Constrains where REQ-followup-live-search may be implemented.
