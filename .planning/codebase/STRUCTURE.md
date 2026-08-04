# Codebase Structure

**Analysis Date:** 2026-08-04

## Directory Layout

```
Research agent/
├── src/
│   └── research_agent/          # The installable package — everything shipped
│       ├── __init__.py
│       ├── graph.py             # Nodes + the supervisor routing table
│       ├── memory.py            # Embedder + MemoryStore seams, 4 backends
│       ├── sessions.py          # SessionStore ABC + SQLite/Postgres backends
│       ├── metrics.py           # RunRecord, MetricsStore ABC + 2 backends
│       ├── db.py                # One lock-guarded reconnecting Postgres conn
│       ├── service.py           # FastAPI app: routes, SSE, health/ready
│       ├── chat.py              # Terminal REPL (console script entry point)
│       ├── limits.py            # Demo token, rate limit, daily spend cap
│       ├── usage.py             # Effective-dated pricing, cost accounting
│       ├── retry.py             # Node-boundary retry decorator
│       ├── observability.py     # JSON logging + optional OTel spans
│       ├── migrate.py           # SQLite/JSON → Postgres one-shot migration
│       └── static/
│           └── index.html       # Demo page; hand-rolled SSE reader
├── tests/                       # Pytest suite — outside the package
├── evals/                       # Offline + live eval harness — outside the package
│   ├── __main__.py              # `python -m evals`
│   ├── dataset.py               # Cases incl. scripted model output
│   ├── graders.py               # Judge on a stronger model (Opus 5)
│   └── harness.py               # ScriptedClient, HashEmbedder, run_suite
├── docs/
│   ├── DESIGN.md                # Architectural rationale (source for DEC- entries)
│   └── OPERATIONS.md            # Deploy, config table, runbook
├── .github/workflows/ci.yml     # Lint + tests + offline evals
├── .planning/                   # GSD planning + intel + codebase maps
├── pyproject.toml               # Single manifest; base / [service] / [dev] / extras
├── Dockerfile                   # Installs .[service], never .[dev]
├── docker-compose.yml           # Local Postgres + pgvector
├── fly.toml                     # Fly.io deployment config
└── README.md
```

## Directory Purposes

**`src/research_agent/`:**
- Purpose: the entire shipped application. `src/` layout means the package is
  only importable once installed, so a passing test run can't rely on a module
  that would never reach the image (DEC-23).
- Contains: one module per concern, flat — no sub-packages except `static/`.
- Key files: `graph.py` (orchestration), `service.py` (HTTP), `memory.py` (seams)

**`tests/`:**
- Purpose: pytest suite, one file per module plus cross-backend contract tests
- Contains: `test_supervisor_routing.py` (the routing table, no API keys needed),
  `test_store_contract.py` (behavioural tests run against every backend),
  `test_memory_stores.py`, `test_sessions.py`, `test_metrics.py`,
  `test_service.py`, `test_limits.py`, `test_retry.py`, `test_usage.py`,
  `test_observability.py`, `test_graph_smoke.py`, `test_evals.py`,
  `test_deploy_config.py`
- Deliberately outside the package so it never reaches the image

**`evals/`:**
- Purpose: drive the real compiled `graph.app` with a scripted client
- Contains: dataset with authored model output, graders, harness, CLI
- Outside the package on purpose — "the eval dataset contains scripted model
  output, which has no business inside a production image" (DEC-23)

**`docs/`:**
- Purpose: narrative design and operations detail lifted out of the README
- `DESIGN.md` is the primary source behind `.planning/intel/decisions.md`

**`src/research_agent/static/`:**
- Purpose: the `/demo` page, served by `FileResponse` from `service.py:48`
- Shipped via `[tool.setuptools.package-data]` in `pyproject.toml`

## Key File Locations

**Entry Points:**
- `src/research_agent/service.py`: FastAPI `app` — `uvicorn research_agent.service:app`
- `src/research_agent/chat.py`: `main()`, wired as the `research-agent` console script
- `src/research_agent/graph.py`: `app = build_graph()` at module scope, plus a
  `__main__` block that runs one research question end to end
- `evals/__main__.py`: `python -m evals`
- `src/research_agent/migrate.py`: `main(argv)` for the Postgres migration

**Configuration:**
- `pyproject.toml`: the single manifest — deps, extras, scripts, packaging, ruff
- `fly.toml`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- `.env.example`: documents every env var (never read `.env` itself)
- `.github/workflows/ci.yml`

**Core Logic:**
- `src/research_agent/graph.py:403` — `supervisor_node`, the routing table
- `src/research_agent/graph.py:38` — `MODEL`, shared by every node
- `src/research_agent/graph.py:39,47` — `MAX_REVISIONS`, `MAX_ITERATIONS`
- `src/research_agent/memory.py:110` — `MemoryStore` ABC (the four-method contract)
- `src/research_agent/memory.py:431` — `BACKENDS` registry
- `src/research_agent/service.py:232` — `_stream`, the SSE generator
- `src/research_agent/db.py:64` — `Database`

**Testing:**
- `tests/test_supervisor_routing.py` — row-order and precedence assertions
- `tests/test_store_contract.py` — one behavioural suite, every backend

**Generated / runtime artefacts (not source):**
- `sessions.db`, `src/research_agent/sessions.db` — SQLite session stores
- `agent_memory_store.json` — JSON note store
- `src/research_agent.egg-info/` — editable-install metadata

## Naming Conventions

**Files:**
- One lowercase noun per module, no prefixes: `graph.py`, `limits.py`, `usage.py`
- Tests mirror the module: `tests/test_<module>.py`

**Modules:**
- A seam module owns its ABC, its backends, its `BACKENDS`/selector dict, its
  `default_backend()`, and its `get_*()` factory — all in one file
  (`memory.py`, `sessions.py`, `metrics.py`)

**Symbols:**
- Nodes are `<role>_node` (`classifier_node`, `critic_node`)
- Backends are `<Backend><Kind>Store` (`PgVectorMemoryStore`,
  `PostgresSessionStore`, `SQLiteMetricsStore`)
- Module-private helpers take a leading underscore (`_text`, `_sse`, `_probe`,
  `_BruteForceStore`)
- Env-var-derived settings are module constants read via `os.environ.get` with a
  default at the top of the file

## Where to Add New Code

**A new graph node:**
- Implement in `src/research_agent/graph.py` as `@retry_node("name")` +
  `def name_node(state: AgentState) -> AgentState`
- Always call the model through `call_model(state, "name", ...)`, never
  `client()` directly
- Append a dict to `state["trace"]` before returning
- Register in `build_graph()` (`graph.py:474`): `add_node`, add it to the
  worker tuple so it edges back to `supervisor`, add it to the conditional-edge
  map and to the `Literal` in `route()` (`graph.py:468`)
- Add the routing row to `supervisor_node` **with an explicit decision about
  where it sits relative to the guardrails**, and a test in
  `tests/test_supervisor_routing.py` pinning that position
- If it should show progress on the demo page, extend `_node_detail`
  (`service.py:266`) and `LABELS`/`nodeDetail` in
  `src/research_agent/static/index.html`

**A new memory backend:**
- Subclass `MemoryStore` in `src/research_agent/memory.py` (or
  `_BruteForceStore` if it scans in-process)
- Implement `add`, `query`, `__len__`, `describe`; override `close()` only if it
  holds a connection
- Register in `BACKENDS` (`memory.py:431`); update `default_backend()` only if
  the selection rule genuinely changes
- Add it to the shared behavioural suite in `tests/test_store_contract.py` —
  do not write a bespoke test file

**A new session or metrics backend:**
- Same shape, in `sessions.py` / `metrics.py`. Postgres backends must go through
  `db.Database` and register DDL via `ensure_schema()`, never run DDL in
  `__init__`

**A new endpoint:**
- Add to `src/research_agent/service.py` under the Routes section
- If it spends money, add `dependencies=[Depends(guard)]`; if it is read-only,
  leave it open
- Add it to `_index_json()["endpoints"]` (`service.py:302`)
- Take stores via `Depends(get_sessions)` / `Depends(get_metrics)`, never import
  module globals
- No routing or mode logic here

**A new env-var setting:**
- Constant + `os.environ.get(...)` with a default at the top of the owning module
- Document it in `.env.example` and the config table in `docs/OPERATIONS.md`

**Tests:**
- `tests/test_<module>.py`; cross-backend behaviour goes in
  `tests/test_store_contract.py`

**Evals:**
- New case in `evals/dataset.py` with its scripted model output; graders in
  `evals/graders.py`

## Special Directories

**`.planning/`:**
- Purpose: GSD planning state, ingested intel, and these codebase maps
- Generated: yes, by GSD commands
- Committed: yes
- `.planning/intel/decisions.md` holds DEC-01…DEC-23 — cite these rather than
  re-deriving rationale from `docs/DESIGN.md`

**`src/research_agent.egg-info/`:**
- Purpose: setuptools metadata from the editable install
- Generated: yes. Committed: no

**`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`:**
- Generated: yes. Committed: no

**`docs/`:**
- Purpose: DESIGN and OPERATIONS, split out of the README
- Generated: no. Committed: yes

---

*Structure analysis: 2026-08-04*
