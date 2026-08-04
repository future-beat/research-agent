# External Integrations

**Analysis Date:** 2026-08-04

Two paid third-party APIs, one hosting platform, one CI provider. Everything else is self-hosted or optional.

## APIs & External Services

**Model provider — Anthropic:**
- Claude — every node in the research graph (classifier, researcher, writer, critic, reviser)
  - SDK: `anthropic==0.120.0`
  - Client: `anthropic.Anthropic()`, built lazily at `src/research_agent/graph.py:58` and memoized in the module-level `_client`. Lazy construction is load-bearing — the CI eval gate runs with `ANTHROPIC_API_KEY=""` specifically to catch a regression back to eager construction.
  - Call site: `client().messages.create(model=MODEL, **kwargs)` at `graph.py:99`, wrapped in an observability span and fed into cost accounting on the next line.
  - Model: `claude-sonnet-5` (`graph.MODEL`, `graph.py:38`)
  - Auth: `ANTHROPIC_API_KEY` (read by the SDK from the environment; never passed explicitly)

**Server-side tools (Anthropic-hosted, billed separately):**
- `web_search` — declared at `graph.py:260` as `{"type": "web_search_20260209", "name": "web_search"}`. Only the researcher node gets it. Billed at $10 per 1,000 searches (`WEB_SEARCH_USD_PER_REQUEST`, `usage.py:26`); failed searches are not billed and the API only counts successful ones, so no error handling is needed around the accounting.
- `web_fetch` — **counted but never enabled.** `CallUsage.web_fetch_requests` (`usage.py:110`) and the `web_fetch_requests` totals field exist and are threaded through the whole accounting path, but no node registers a `web_fetch` tool. It is always zero. Deliberate per the module docstring (fetched content bills as input tokens, which usage already reports), so this is instrumentation ahead of a feature rather than dead code — but a reader will wonder.

**Embeddings — Voyage AI:**
- Text-to-vector for long-term memory
  - SDK: `voyageai==0.5.0`
  - Client: `voyageai.Client()`, built lazily inside the `VoyageEmbedder.client` property (`memory.py:90-96`), same reasoning as the Anthropic client — eager construction would make `memory.py` unimportable without a key and the graph untestable.
  - Model: `voyage-3.5` (`VOYAGE_EMBEDDING_MODEL`, `memory.py:40`), 1024 dimensions
  - Two call shapes: `embed_documents()` with `input_type="document"` for stored notes, `embed_query()` with `input_type="query"` for retrieval. Voyage distinguishes the two, so the `Embedder` protocol does too.
  - Auth: `VOYAGE_API_KEY` — a **separate account** from Anthropic (`dashboard.voyageai.com`)
  - Not priced. Voyage spend appears in no cost report; `usage.py` accounts for Claude tokens and web searches only. Small relative to model spend, but it is a blind spot.

## Data Storage

**Databases:**
- SQLite (default) — `sessions.db` and `metrics.db`
  - Paths: `SESSION_DB_PATH`, `METRICS_DB_PATH` (both `/data/...` in the container)
  - Code: `src/research_agent/sessions.py`, `src/research_agent/metrics.py`
  - `METRICS_DB_PATH` defaults to `SESSION_DB_PATH` (`metrics.py:32`) — one file unless split explicitly
- PostgreSQL (optional, and the documented production path)
  - Connection: `DATABASE_URL`. Setting this one variable moves sessions, metrics, **and** notes off local disk — there is no second flag to forget. See `db.postgres_configured()` (`db.py:179`) and the three `default_backend()` functions that consult it (`memory.py:439`, `sessions.py:333`, `metrics.py:396`).
  - Client: `psycopg[binary]==3.3.4`, imported lazily at `db.py:55`, `dict_row` row factory
  - Shared reconnecting connection wrapper: `src/research_agent/db.py` (`Database`)
  - Connection timeout: `PG_CONNECT_TIMEOUT`, default 3 seconds (`db.py:38`) — bounded deliberately so `/health` can probe three stores inside Fly's 15s check window
  - Per-backend overrides: `SESSION_BACKEND`, `METRICS_BACKEND` (`sqlite` | `postgres`)

**Vector store (four backends, selected by `VECTOR_STORE`):**
- `json` (default without Postgres) — `JSONMemoryStore`, `memory.py:209`. Whole file rewritten on every add, write-then-rename so an interrupted save can't truncate. Path: `VECTOR_STORE_PATH`.
- `memory` — `InMemoryStore`, `memory.py:201`. Nothing persisted; used by tests and by workers that want in-process recall only.
- `chroma` — `ChromaMemoryStore`, `memory.py:239`. `chromadb.PersistentClient` with `metadata={"hnsw:space": "cosine"}`. Requires the `[chroma]` extra. Config: `CHROMA_PATH`, `CHROMA_COLLECTION`.
- `pgvector` (default when `DATABASE_URL` is set) — `PgVectorMemoryStore`, `memory.py:311`. HNSW index over `vector_cosine_ops`, `<=>` cosine distance operator. Needs the `vector` extension (`CREATE EXTENSION IF NOT EXISTS vector`, a no-op when present). Config: `PGVECTOR_TABLE` (validated alphanumeric-or-underscore before DDL interpolation, `memory.py:339`), `VECTOR_DIMENSIONS`.
- Embeddings are always produced by our own `Embedder`, never by the store's built-in one — switching backends must not silently switch embedding models, which would invalidate every vector already written.

**File Storage:**
- Local filesystem only, all under `/data` in the container (volume `agent_data` on Fly, named volume `agent-data` in compose). No S3, no object store.

**Caching:**
- No cache service. Anthropic prompt caching is *accounted for* — `cache_read_input_tokens` and `cache_creation_input_tokens` are extracted and priced separately (`usage.py:105-108`, `Price.cache_write_5m` / `Price.cache_read`) — but no node currently sets `cache_control`, so those counters read zero. Same shape as `web_fetch`: instrumentation waiting on the feature.

**Migration:**
- `src/research_agent/migrate.py`, run as `python -m research_agent.migrate [--dry-run]`. Re-runnable (already-copied rows are skipped) and carries notes across with their existing embeddings rather than re-embedding — which matters, because re-embedding would be a second Voyage bill for data you already paid to vectorize.

## Authentication & Identity

**End-user auth:** None. There are no users and no accounts.

**Demo guardrails** (`src/research_agent/limits.py`) stand in for auth on a publicly reachable URL:
- `DEMO_TOKEN` — when set, write endpoints require a matching `X-Demo-Token` header. Applied via `dependencies=[Depends(guard)]` on the four write routes in `service.py` (`/research`, `/research/stream`, `/sessions/{id}/ask`, `/sessions/{id}/ask/stream`). Read and ops endpoints are open.
- `DEMO_RATE_LIMIT_PER_HOUR` — per visitor IP, default 10. `0` disables.
- `DEMO_DAILY_USD_CAP` — rolling 24h spend ceiling across all callers, default 5.00. `0` disables.
- `TRUST_FORWARDED_FOR` — default false. Client IP comes from the socket unless explicitly told to believe `X-Forwarded-For` (`limits.py:84`). Behind Fly's proxy this must be enabled for per-IP limiting to mean anything; left off, every request looks like it came from the proxy.

**Service-to-service:** Two bearer keys read from the environment by their respective SDKs. Nothing else authenticates outbound.

## Monitoring & Observability

**Error tracking:** No Sentry, no Rollbar, no external error service. Failures surface as structured log lines and in the per-run execution trace.

**Logs:**
- `src/research_agent/observability.py`. Custom `JSONFormatter` emitting one JSON object per line, with `extra=` fields promoted to top level.
- `LOG_FORMAT=json` (default, containers) | `text` (terminal); `LOG_LEVEL` default `INFO`.
- Configures only the `graph` logger, never root, and sets `propagate = False` — a library that reconfigures root logging breaks whatever imported it.
- One line per model call and one per completed run, keyed by `run_id`.
- Destination is stdout. On Fly that means `fly logs`; there is no aggregator configured.

**Tracing:**
- OpenTelemetry, entirely optional. `observability.span()` is a context manager that yields `None` when `opentelemetry-api` is not installed or `OTEL_ENABLED` is false/0/no (`observability.py:86-95`). Call sites are identical either way.
- The `[otel]` extra is **not** installed in the production image (`Dockerfile` installs `.[service]` only), so tracing is dormant in the current deploy. No collector endpoint is configured anywhere.

**Metrics:**
- Self-hosted. `src/research_agent/metrics.py` writes a `runs` table and `/metrics` aggregates it. No Prometheus exposition format, no scrape target — it is a JSON endpoint, not a Prometheus one.

**Health endpoints** (`src/research_agent/service.py`):
- `GET /health` (line 388) — **liveness.** Reports unreachable dependencies in the body and still returns **200**, because restarting a machine does not fix a database that is down. Also reports whether each API key is *present* (`service.py:418-419`), never its value. Never calls Claude or Voyage — it measures whether *we* are up, not whether a third party is.
- `GET /ready` (line 424) — **readiness.** Returns 503 when a store is unreachable.
- Fly's check and Docker's `HEALTHCHECK` both point at `/health`. Pointing either at `/ready` would produce a restart loop during a database outage — `fly.toml:62-65` says so explicitly.

## CI/CD & Deployment

**Hosting:**
- Fly.io, app `research-agent`, region `syd` (`fly.toml`)
- Single machine (`min_machines_running = 1`, `auto_stop_machines = 'suspend'`), 1 GB shared-cpu-1x
- Concurrency: soft 8 / hard 16 requests
- Volume `agent_data` at `/data`

**Deploys are MANUAL.**
- The actual mechanism is a human running `fly deploy -a research-agent` from a workstation. Verified against `fly releases` — releases do not originate from GitHub.
- **`docs/OPERATIONS.md:49-51` is wrong.** It states: *"Deploys currently run through Fly's GitHub integration, which is not gated on CI: a direct push that fails tests still deploys."* That was true at one point and is not true now. The stated *risk* is also inverted by the correction — with manual deploys, a failing push does **not** ship; the real exposure is that a human can deploy a dirty or unpushed tree with no CI gate at all.
- Fix `docs/OPERATIONS.md` before anyone relies on it during an incident. `fly.toml:84-95` and the README are consistent with manual deploys; that one paragraph is the outlier.
- Nothing in `.github/workflows/` deploys. `ci.yml` is the only workflow and it has no deploy job — consistent with the manual finding.

**CI Pipeline** — GitHub Actions, `.github/workflows/ci.yml`, two jobs:
1. `lint · tests · evals` — ruff, pytest, then the offline eval suite at `--min-pass-rate 0.9`. Runs against a real `pgvector/pgvector:pg16` service container with `REQUIRE_POSTGRES=1`, so the Postgres and pgvector backends **fail** rather than skip when the database is missing. Eval report uploaded as an artifact.
2. `image build · container smoke test` — buildx with GHA cache, then boots the image and probes `/health`, `/metrics`, `/pricing`, `/openapi.json`, and finally waits for Docker's own `HEALTHCHECK` to report healthy.
- Every gate runs with `ANTHROPIC_API_KEY=""` and `VOYAGE_API_KEY=""`. No live key ever touches CI — it would break on forks, on rotation, and during someone else's outage, and bill for every push.
- Triggers: push to any branch, pull requests, manual dispatch. Concurrency group cancels in-progress runs per ref.
- `main` is branch-protected: both checks must pass to merge; force pushes and deletion blocked.

**Local container:** `docker-compose.yml`. `docker compose up --build` for the agent alone; `--profile postgres` adds a `pgvector/pgvector:pg16` sidecar for parity with a stateless deploy. Keys use `${VAR:?message}` so a missing key fails the run with a clear message instead of starting a container that looks healthy and 500s on the first request.

## Environment Configuration

**Required for live runs:**
- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY`

Neither is required for tests, evals, or a container boot — the smoke test runs on `ci-not-a-real-key`.

**Critical operational vars:**
- `DATABASE_URL` — the single switch that makes the service stateless
- `AGENT_MAX_RUN_COST_USD` (default 1.00) — per-run spend cap
- `DEMO_DAILY_USD_CAP` (default 5.00) / `DEMO_RATE_LIMIT_PER_HOUR` (default 10) / `DEMO_TOKEN` — public-URL guardrails
- `VECTOR_STORE`, `SESSION_BACKEND`, `METRICS_BACKEND` — backend overrides; all follow `DATABASE_URL` when unset
- `EVAL_JUDGE_MODEL` (default `claude-opus-5`) — eval-time only

Full table with defaults: `docs/OPERATIONS.md` § Configuration.

**Note on the cost caps:** Sonnet 5 introductory pricing ends 2026-08-31. From 2026-09-01 the same run costs 50% more, so both the per-run and daily caps bind proportionally sooner. Revisit those two numbers before the rollover.

**Secrets location:**
- Local: `.env`, gitignored and listed in `.dockerignore` — a key must never reach an image layer
- Fly: `fly secrets set ANTHROPIC_API_KEY=... VOYAGE_API_KEY=... -a research-agent`. `DATABASE_URL` is set automatically by `fly postgres attach` as a secret on the *agent* app.
- CI: no secrets consumed by any job
- Non-secret config sits in `fly.toml [env]`; secrets never do

## Webhooks & Callbacks

**Incoming:** None. No webhook endpoints, no signature verification anywhere in `service.py`.

**Outgoing:** None. All external calls are synchronous request/response to Anthropic and Voyage.

**Streaming:** Server-Sent Events to the browser via FastAPI's `StreamingResponse` on `/research/stream` and `/sessions/{id}/ask/stream`. Consumed by `src/research_agent/static/index.html`, served at `GET /demo`. This is an internal transport, not a third-party integration.

---

*Integration audit: 2026-08-04*
