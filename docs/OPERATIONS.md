# Operations

Running this in production: deployment, configuration, CI, and the migration
to Postgres. For what the system is, see the [README](../README.md); for why
it's built this way, [DESIGN.md](DESIGN.md).

## Container

```bash
cp .env.example .env
docker compose up --build
curl localhost:8000/health
```

The image runs as a non-root user, installs `requirements-service.txt` only,
and excludes `tests/` and `evals/` — the eval dataset contains scripted model
output, which has no business inside a production image.

**Mount a volume at `/data`.** Both SQLite databases and the vector store live
there. Without it, every follow-up thread and every stored note dies with the
container, and the memory feature quietly becomes a no-op.

**Credentials never reach an image layer.** `.env` is in `.dockerignore`,
compose passes keys through from the environment, and Fly uses `fly secrets`.
`/health` reports whether each key is *present*, never its value.

## Fly.io

```bash
fly volumes create agent_data --size 1 -a research-agent
fly secrets set ANTHROPIC_API_KEY=... VOYAGE_API_KEY=... -a research-agent
fly deploy -a research-agent
```

`fly.toml` pins `min_machines_running = 1` on purpose: SQLite with a single
writer and a per-machine volume does not scale horizontally, because a second
machine would hold its own database and 404 on sessions that demonstrably
exist. Setting `DATABASE_URL` lifts that constraint — see below.

> **Don't merge Fly's "New files from Fly.io Launch" pull requests.** They
> regenerate `fly.toml` from the web UI's defaults and have twice broken this
> deploy: once by pointing `app` at the Postgres cluster, and once by setting
> `internal_port` to `8080` while the container listens on `8000`. The second
> is the nastier one — it touches a line `fly.toml` hasn't changed since the
> branch point, so it merges with **no conflict shown** and surfaces only as
> every request failing. Copy any value you want out by hand and close the PR.
> `tests/test_deploy_config.py` fails the build on both cases.

Deploys currently run through Fly's GitHub integration, which is **not** gated
on CI: a direct push that fails tests still deploys, because branch protection
only gates pull requests.

## Going stateless

One volume on one machine means downtime during host maintenance and up to 24h
of data loss between snapshots. Moving state to Postgres removes both, and it's
one variable:

```bash
fly postgres create --name research-agent-db
fly postgres attach research-agent-db -a research-agent   # sets DATABASE_URL
fly deploy -a research-agent

fly ssh console -a research-agent -C "python /app/migrate_to_postgres.py --dry-run"
fly ssh console -a research-agent -C "python /app/migrate_to_postgres.py"
```

Then delete the `[[mounts]]` block from `fly.toml` and `fly scale count 2`.
Sessions, metrics, and notes all follow `DATABASE_URL`, so there's no second
flag to forget.

**Always pass `-a` explicitly.** `fly postgres create` makes a separate,
Fly-managed app; you attach to it, you never deploy into it.

The migration is re-runnable — anything already copied is skipped — and it
carries notes across with their existing embeddings rather than re-embedding
them. `/health` reports which backend each store is using, so you can confirm
the switch took.

Postgres needs the `vector` extension for the pgvector notes backend. Most
managed offerings ship it; `CREATE EXTENSION` is a no-op when it already exists.

## CI

```
lint · tests · evals            ruff, 364 tests, 12 offline eval cases
image build · smoke test        docker build, boot the container, probe it
```

Every gate runs with `ANTHROPIC_API_KEY=""`. A CI suite that needs a live key
breaks on forks, on key rotation, and during someone else's outage — and bills
you for every push. The offline eval step doubles as a guard on the lazy-client
decision: if a client ever becomes eager again, that step is what fails.

The smoke test boots the built image and probes `/health`, `/metrics`,
`/pricing`, and `/openapi.json`, then waits for Docker's own `HEALTHCHECK`. A
Dockerfile that builds but whose entrypoint crashes on startup passes a
build-only check and fails in production instead.

Postgres and pgvector run for real against a `pgvector/pgvector` service
container, with a guard test that **fails** rather than skips when the database
is missing — so the build can't go green over an untested backend.

`main` is protected: both checks must pass before a pull request can merge, and
force pushes and branch deletion are blocked.

## Configuration

Tunable in code:

| Knob | Where | Default |
|---|---|---|
| `MAX_REVISIONS` | `research_agent.py` | `2` |
| `MAX_ITERATIONS` | derived from `MAX_REVISIONS` | `12` |
| `MODEL` | `research_agent.py` | `claude-sonnet-5` |
| Effort / thinking | per-node `output_config` | `medium` / `adaptive` (`disabled` on the classifier) |
| `min_similarity` | `MemoryStore.query()` | `0.3` |

Environment variables:

| Variable | Does | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` · `VOYAGE_API_KEY` | Required for real runs | — |
| `DATABASE_URL` | Postgres DSN. **Setting it moves all three stores.** | *(unset)* |
| `VECTOR_STORE` | `json`, `memory`, `chroma`, `pgvector` | follows `DATABASE_URL` |
| `SESSION_BACKEND` · `METRICS_BACKEND` | `sqlite` or `postgres` | follows `DATABASE_URL` |
| `VECTOR_STORE_PATH` · `SESSION_DB_PATH` · `METRICS_DB_PATH` | Local store locations | beside the code |
| `PGVECTOR_TABLE` · `VECTOR_DIMENSIONS` | pgvector table and column width | `research_notes` / `1024` |
| `PG_CONNECT_TIMEOUT` | Seconds before a connection attempt gives up | `3` |
| `CHROMA_PATH` · `CHROMA_COLLECTION` | Chroma location and collection | `chroma_store` / `research_notes` |
| `VOYAGE_EMBEDDING_MODEL` | Embedding model | `voyage-3.5` |
| `AGENT_MAX_RUN_COST_USD` | Per-run spend cap; `0` disables | `1.00` |
| `AGENT_MAX_ATTEMPTS` | Attempts per node, including the first | `4` |
| `AGENT_RETRY_BASE_DELAY` · `AGENT_RETRY_MAX_DELAY` | Backoff bounds, seconds | `1.0` / `30.0` |
| `DEMO_DAILY_USD_CAP` | Rolling 24h ceiling across all callers; `0` disables | `5.00` |
| `DEMO_RATE_LIMIT_PER_HOUR` | Requests per visitor IP; `0` disables | `10` |
| `DEMO_TOKEN` | When set, write endpoints need an `X-Demo-Token` header | *(unset)* |
| `TRUST_FORWARDED_FOR` | Believe `X-Forwarded-For` for client IP | `false` |
| `LOG_FORMAT` · `LOG_LEVEL` | `json` or `text`; level | `json` / `INFO` |
| `OTEL_ENABLED` | Emit OpenTelemetry spans when the package is installed | `true` |

Switching backends does **not** migrate existing data — each store owns its
own. `VECTOR_STORE=chroma` additionally needs `pip install chromadb`.

Research strategies and critic rubrics live in the `RESEARCH_STRATEGY` and
`CRITIC_RUBRIC` dicts; add a topic type by adding a key to both.

## Project layout

```
research_agent.py       the graph: nodes, supervisor, routing, compile
service.py              FastAPI surface: blocking + SSE, sessions, ops
chat.py                 terminal REPL with streamed progress
static/index.html       the demo page — one self-contained file, no build step

vector_memory.py        Embedder + MemoryStore seams and four backends
sessions.py             conversation sessions (SQLite / Postgres)
metrics.py              runs table and the /metrics aggregation
db.py                   reconnecting Postgres connection shared by the stores
migrate_to_postgres.py  copies an existing SQLite/JSON deployment across

usage.py                effective-dated price table and cost accounting
limits.py               demo token, rate limit, rolling spend cap
retry.py                retryable-error classification, backoff, node decorator
observability.py        JSON logging and the optional OpenTelemetry seam

evals/                  golden dataset, graders, runner, CLI
tests/                  pytest suite (no keys, no network)
```

`service.py` is deliberately thin: it validates input, picks a state
constructor, runs the graph, and persists the result. No routing logic lives
there — any that did would mean the supervisor is no longer the single place
deciding what runs next.
