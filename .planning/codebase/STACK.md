# Technology Stack

**Analysis Date:** 2026-08-04

## Languages

**Primary:**
- Python — the entire application. Package source under `src/research_agent/`, eval suite under `evals/`, tests under `tests/`.

**Secondary:**
- HTML + inline CSS/JS — the demo page, one self-contained file at `src/research_agent/static/index.html`. No build step, no bundler, no JS package manager.
- SQL — schema and queries written inline in `src/research_agent/db.py`, `src/research_agent/sessions.py`, `src/research_agent/metrics.py`, and `src/research_agent/memory.py` (pgvector DDL and cosine search).

## Runtime

**Environment:**
- CPython. Three different version signals, and they do not agree:
  - `pyproject.toml` declares `requires-python = ">=3.10"`
  - `[tool.ruff] target-version = "py310"`
  - `Dockerfile` builds and runs on `python:3.14-slim` (both stages)
  - `.github/workflows/ci.yml` tests on `python-version: "3.14"`
  - Local `.venv` is Python 3.14.6
- Net effect: 3.14 is the only version actually exercised. The `>=3.10` floor and the `py310` lint target are aspirational — nothing verifies 3.10 still works.

**Package Manager:**
- pip. Install paths: `pip install -e '.[dev]'` (development and CI), `pip install '.[service]'` (Docker image, `Dockerfile:29`).
- Lockfile: **missing**. No `requirements.txt`, no `uv.lock`, no `poetry.lock`, no `pip-tools` output. Reproducibility rests entirely on the `==` pins in `pyproject.toml` — which cover direct dependencies only, not the transitive tree.

**Build backend:**
- setuptools (`requires = ["setuptools>=68"]`, `build-backend = "setuptools.build_meta"`).
- `src/` layout via `[tool.setuptools.packages.find] where = ["src"]`. The package is importable only once installed, which is the point: a green test run can't be leaning on a module that sits in the working directory but would never reach the image.
- Package data: `research_agent = ["static/*.html"]` — this is how the demo page reaches the runtime image, since the Dockerfile never copies `src/` into the final stage.

## Frameworks

**Core:**
- `langgraph==1.2.9` — the agent is an explicit state graph. `StateGraph`/`END` imported in `src/research_agent/graph.py`; supervisor routing and node compilation all live there.
- `anthropic==0.120.0` — official Claude SDK. Client is constructed lazily in `graph.py:58` (`client()`), which is a load-bearing decision: eager construction would make the module unimportable without `ANTHROPIC_API_KEY` and break the offline CI eval gate.
- `fastapi==0.141.1` (extra: `service`) — HTTP surface in `src/research_agent/service.py`. Blocking + SSE endpoints, sessions, ops routes.
- `uvicorn[standard]==0.52.0` (extra: `service`) — ASGI server. Container entrypoint is `uvicorn research_agent.service:app --host 0.0.0.0 --port 8000`.

**Testing:**
- `pytest==9.1.1` (extra: `dev`) — config lives in `[tool.pytest.ini_options]` in `pyproject.toml`. `testpaths = ["tests"]`, `pythonpath = [".", "src", "tests"]`, `addopts = "-q"`. 13 test modules in `tests/`.
- Custom eval harness in `evals/` (`harness.py`, `graders.py`, `dataset.py`, `__main__.py`). Runs fully offline with scripted model responses; invoked as `python -m evals --report evals-report.json --min-pass-rate 0.9`.

**Build/Dev:**
- `ruff==0.16.1` (extra: `dev`) — lint only, `line-length = 100`, rule set `E,W,F,I,B,UP,C4,SIM`. `ruff format` is deliberately not used (`pyproject.toml:65-67`): several hand-aligned tables would be flattened for no behavioural gain.
- Docker + docker-compose for local containers (`Dockerfile`, `docker-compose.yml`).
- GitHub Actions for CI (`.github/workflows/ci.yml`).

## Key Dependencies

**Critical (always installed):**
- `langgraph==1.2.9` — without it there is no graph, no supervisor, no routing.
- `anthropic==0.120.0` — every node is a Claude call; also carries the server-side `web_search` tool.
- `voyageai==0.5.0` — embeddings for long-term memory. Separate vendor and separate API key from Anthropic.
- `numpy==2.5.1` — cosine similarity for the brute-force memory stores (`memory.py:144`, `_cosine`).
- `python-dotenv==1.2.2` — loads `.env` for the terminal REPL (`chat.py`).

**Infrastructure (extra: `service`):**
- `psycopg[binary]==3.3.4` — Postgres driver for sessions, metrics, and pgvector notes. Imported lazily (`db.py:55`) so a SQLite/JSON deployment never touches it, but present in the image so a deploy that provisions a database doesn't fail on a missing driver.

**Optional extras (not installed by default):**
- `chromadb==1.4.1` (extra: `chroma`) — ANN-indexed vector store. Imported inside `ChromaMemoryStore.__init__` (`memory.py:255`) with an explicit ImportError message pointing back at the extra.
- `opentelemetry-api==1.31.1` (extra: `otel`) — tracing seam. `observability.py:_tracer()` returns `None` when the package is absent, so `span()` degrades to a no-op context manager rather than failing.

**Undeclared but imported:**
- `pydantic` — `service.py:35` imports `BaseModel, Field` but pydantic appears nowhere in `pyproject.toml`. It arrives transitively via FastAPI, so the actual version floats with whatever FastAPI 0.141.1 resolves. **This is the one genuinely unpinned runtime import.** If pydantic is load-bearing for the API contract (it is — every request/response model), it should be pinned explicitly.
- `starlette` — reached only through FastAPI's re-exports (`StreamingResponse`, `FileResponse`), so no direct import to pin.

**Pinning summary:**
- Every declared dependency uses exact `==` pins. Nothing uses `>=`, `~=`, or a bare name.
- Gaps: no lockfile (transitive tree floats), `pydantic` undeclared, `setuptools>=68` in `[build-system]` is a floor rather than a pin, and CI actions use floating major tags (`actions/checkout@v4`, `docker/build-push-action@v6`, etc.).

## Configuration

**Environment:**
- Configured entirely through environment variables; no config file format, no settings class. Every knob is read via `os.environ.get` at the module or call site.
- `.env` for local development (gitignored, and in `.dockerignore` so a key can never reach an image layer). `.env.example` is the committed template and documents only the two required keys plus the common optional ones.
- Full variable table lives in `docs/OPERATIONS.md` ("Configuration" section) and the README.
- Defaults are chosen so that setting one variable (`DATABASE_URL`) moves all three stores to Postgres — see `db.postgres_configured()` at `db.py:179`, `memory.default_backend()` at `memory.py:439`, `sessions.py:333`, `metrics.py:396`.

**In-code constants (not env-tunable):**
- `MODEL = "claude-sonnet-5"` — `graph.py:38`
- `MAX_REVISIONS` / derived `MAX_ITERATIONS` — `graph.py`
- `DEFAULT_TOP_K = 3`, `DEFAULT_MIN_SIMILARITY = 0.3` — `memory.py:59-60`
- Per-node `output_config={"effort": "medium"}` and `max_tokens` — `graph.py:222, 257, 292, 343, 379`

**Build:**
- `pyproject.toml` — the single manifest. Dependencies, extras, console script (`research-agent = "research_agent.chat:main"`), pytest config, and ruff config all live here. No `setup.py`, no `setup.cfg`, no `tox.ini`.
- `Dockerfile` — two-stage. Builder installs into `/opt/venv`; runtime copies the venv only, so no compiler and no build cache ship.
- `.dockerignore` — excludes `.env`, `tests/`, `evals/`.

## Model Configuration

**Pipeline model:** `claude-sonnet-5`, hardcoded as `graph.MODEL` (`graph.py:38`). Every node — classifier, researcher, writer, critic, reviser — runs on it.

**Eval judge:** `claude-opus-5`, via `EVAL_JUDGE_MODEL` (`evals/graders.py:28`). This is the only place Opus appears, and it is deliberately a different and stronger model than the one being graded.

**Embedding model:** `voyage-3.5` via `VOYAGE_EMBEDDING_MODEL` (`memory.py:40`). Emits 1024 dimensions, which is why `VECTOR_DIMENSIONS` defaults to `1024` — the pgvector column width is validated against the embedder on first write (`memory.py:371`, `_check_dimensions`) rather than trusted.

## Pricing Table — Action Required

`src/research_agent/usage.py` holds an **effective-dated** price table (`PRICES`, `usage.py:59-76`) resolved by `price_for(model, on)` (`usage.py:83`). Each entry is a `PriceWindow` with inclusive `since`/`until` dates.

Current state for `claude-sonnet-5`:
- Introductory: $2 / $10 per MTok, `until=date(2026, 8, 31)`
- Standard: $3 / $15 per MTok, `since=date(2026, 9, 1)`

**Today is 2026-08-04.** The rollover entry is already present and correct — the introductory window closes in 27 days and the successor window picks it up with no gap. No code change is needed for the 2026-09-01 transition itself.

What *does* need attention: `AGENT_MAX_RUN_COST_USD` defaults to `1.00` and `DEMO_DAILY_USD_CAP` to `5.00` (both in `fly.toml [env]`). On 2026-09-01 the same workload costs 50% more, so those caps will bind roughly a third sooner than they do today. Either raise them deliberately or accept the tighter ceiling — but decide before the date, not after a user hits a cap mid-run.

Unpriced models are handled honestly rather than silently: `record()` sets `totals["pricing_unknown"] = True` and returns `0.0` (`usage.py:175-182`), making `cost_usd` a documented floor rather than a wrong total.

## Platform Requirements

**Development:**
- Python 3.14 (nominally 3.10+, untested below 3.14)
- `pip install -e '.[dev]'`
- Two API keys for live runs: `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`
- Docker + docker-compose for container work
- Neither the test suite nor the eval suite needs a key or network access — CI runs both with `ANTHROPIC_API_KEY=""`

**Production:**
- Fly.io app `research-agent`, primary region `syd` (`fly.toml:22-23`)
- VM: `shared-cpu-1x`, 1 GB memory, 1 shared CPU
- `min_machines_running = 1`, `auto_stop_machines = 'suspend'` — pinned to one machine because the SQLite stores sit on a per-machine volume
- Volume `agent_data` mounted at `/data`, holding `sessions.db`, `metrics.db`, and `agent_memory_store.json`
- Container listens on port 8000; `force_https = true`
- Postgres (with the `vector` extension) is the documented path off local disk — provision it and all three stores follow `DATABASE_URL`

---

*Stack analysis: 2026-08-04*
