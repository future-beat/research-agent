# Coding Conventions

**Analysis Date:** 2026-08-04

All conventions below are observed in the current tree, not aspirational. Ruff
(`ruff check .`) passes clean, so the lint rules in `pyproject.toml` are the
enforced floor; everything else here is convention held by hand.

## Naming Patterns

**Files:**
- Flat, single-word lowercase modules under `src/research_agent/`: `graph.py`,
  `memory.py`, `sessions.py`, `metrics.py`, `limits.py`, `retry.py`, `usage.py`,
  `observability.py`, `db.py`, `migrate.py`, `service.py`, `chat.py`.
- No `utils.py`, no `helpers.py`, no nested subpackages. One module owns one concern.
- Tests mirror the module they cover: `tests/test_retry.py` for
  `src/research_agent/retry.py`. Two tests are cross-cutting rather than
  per-module: `tests/test_store_contract.py` (one suite, every backend) and
  `tests/test_graph_smoke.py` (whole-graph).

**Functions:**
- `snake_case`. Public API is unprefixed; module-private helpers take a leading
  underscore: `_text()`, `_env_float()`, `_psycopg()`, `_tracer()`,
  `_row_to_session()`, `_http_error()`, `_describe_dsn()`.
- Env-var readers are named after what they return, not after the variable:
  `connect_timeout()` (`src/research_agent/db.py:37`), `daily_cap_usd()` and
  `rate_limit_per_hour()` (`src/research_agent/limits.py:60,65`),
  `max_run_cost_usd()` (`src/research_agent/usage.py:198`).
- Predicates read as assertions: `is_retryable()` (`src/research_agent/retry.py:57`),
  `postgres_configured()` (`src/research_agent/db.py:178`).
- Graph nodes are `<role>_node`; see `supervisor_node`, `classifier_node`,
  `researcher_node`, `writer_node`, `critic_node`, `responder_node` in
  `src/research_agent/graph.py`.

**Variables:**
- `snake_case` locals; module-level configuration in `SCREAMING_SNAKE_CASE`
  read once at import: `MODEL`, `MAX_REVISIONS`, `MAX_ITERATIONS`
  (`src/research_agent/graph.py:37-47`), `MAX_QUESTION_CHARS`,
  `SESSION_LIST_LIMIT` (`src/research_agent/service.py:45-46`).
- Lazily-constructed singletons are underscore-prefixed module globals paired
  with an accessor function: `_client`/`client()`, `_memory`/`memory()`
  (`src/research_agent/graph.py:53-77`).
- Sets of constants use `frozenset`, not `set` or `tuple`:
  `RETRYABLE_STATUS` (`src/research_agent/retry.py:54`),
  `_STANDARD_RECORD_FIELDS` (`src/research_agent/observability.py:32`).

**Types:**
- `PascalCase` for classes, dataclasses, Pydantic models, and exceptions.
- Abstract base + concrete backends named `<Backend><Thing>Store`:
  `SessionStore` / `SQLiteSessionStore` / `PostgresSessionStore`
  (`src/research_agent/sessions.py:96,132,231`); `MetricsStore` /
  `SQLiteMetricsStore` / `PostgresMetricsStore` (`src/research_agent/metrics.py`);
  `MemoryStore` / `InMemoryStore` / `JSONMemoryStore` / `PgVectorMemoryStore`
  (`src/research_agent/memory.py`).
- Exceptions subclass the closest stdlib type, not bare `Exception`:
  `class UnknownModelPricing(LookupError)` (`src/research_agent/usage.py:79`).

## Code Style

**Formatting:**
- No autoformatter. `pyproject.toml` documents this deliberately: several
  tables and dict literals are hand-aligned for readability and `ruff format`
  would flatten them.
- `line-length = 100`, `target-version = "py310"` (`pyproject.toml`, `[tool.ruff]`).
- 4-space indent, double quotes throughout.
- Modules and long modules' internals are divided by a 74-dash banner comment:

  ```python
  # --------------------------------------------------------------------------
  # Schemas
  # --------------------------------------------------------------------------
  ```

  Seen in `src/research_agent/service.py:49`, `src/research_agent/observability.py:83`,
  `evals/graders.py:54`, `tests/test_service.py:88`. Inside dataclasses the
  same idea appears as a short `# -- expectations ---` rule
  (`evals/dataset.py:56`, `src/research_agent/db.py:71`).

**Linting:**
- `ruff check .` — rule set `E, W, F, I, B, UP, C4, SIM` (`pyproject.toml`).
- Global ignore: `B008`, because `Depends(...)` in a parameter default is
  FastAPI's documented idiom.
- Per-file ignores: `evals/__main__.py = ["E402"]` (LOG_LEVEL must be set
  before the agent is imported), `tests/* = ["E402"]`.
- Inline suppressions always carry a reason after the code, never a bare
  `# noqa`: `# noqa: BLE001 - the stream must terminate cleanly`
  (`src/research_agent/service.py:259`), `# noqa: PLC0415 - optional dependency`
  (`src/research_agent/observability.py:92`), `# noqa: E731 - one live client
  for all cases` (`evals/__main__.py:81`).
- `# pragma: no cover - depends on env` marks env-dependent branches
  (`src/research_agent/db.py:56`).

## Import Organization

**Order** (enforced by ruff `I`, with `known-first-party = ["research_agent", "evals"]`):
1. `from __future__ import annotations` — first line of code in essentially
   every module in `src/` and `evals/`. Notably **absent from `tests/`**.
2. Standard library.
3. Third-party (`anthropic`, `fastapi`, `pydantic`, `langgraph`, `numpy`).
4. First-party (`research_agent.*`, `evals.*`).

**Path Aliases:**
- None. `src/` layout with `[tool.setuptools.packages.find] where = ["src"]`.
- Absolute first-party imports only — `from research_agent.memory import MemoryStore`,
  never relative `from .memory import ...`.
- Module-vs-symbol split is intentional: import the *module* when tests need to
  monkeypatch it (`from research_agent import graph, limits`), import the
  *symbol* for values (`from research_agent.graph import MAX_ITERATIONS`).
  `src/research_agent/service.py:38-42` does both in the same block.
- Aliasing avoids shadowing a local name: `from research_agent import usage as
  usage_accounting` (`src/research_agent/graph.py:31`, `service.py:39`), and
  `from evals import graders as G` (`evals/__main__.py:27`).

**Lazy imports** are used where a dependency is optional or expensive, always
inside a function with a comment explaining why:
- `psycopg` in `_psycopg()` (`src/research_agent/db.py:53`)
- `opentelemetry` in `_tracer()` (`src/research_agent/observability.py:92`)
- `anthropic` in the `--live` branch of `evals/__main__.py:76`

## Typing

- Type hints on public function signatures and returns:
  `def price_for(model: str, on: date | None = None) -> Price:`
  (`src/research_agent/usage.py:83`).
- PEP 604 unions (`str | None`) and builtin generics (`list[Session]`,
  `dict[str, Any]`) throughout — `from __future__ import annotations` makes
  this safe on the declared floor of Python 3.10.
- `collections.abc` for callables and iterators, not `typing`:
  `from collections.abc import Callable` (`src/research_agent/retry.py:27`),
  `from collections.abc import Iterator` (`src/research_agent/service.py:27`).
- `TypeVar("T")` for the generic retry decorator (`src/research_agent/retry.py:31`).
- Graph state is a `TypedDict` (`AgentState`, `src/research_agent/graph.py`), and
  it stays a plain `dict` at the edges — `usage` totals are deliberately a dict
  rather than a dataclass "because it lives in AgentState"
  (`src/research_agent/usage.py:146`).
- Frozen dataclasses for value objects: `@dataclass(frozen=True) class Case` and
  `class Followup` (`evals/dataset.py:41,52`); mutable dataclasses where the
  harness accumulates (`evals/harness.py`, `field(default_factory=...)`).
- `abc.ABC` + `@abstractmethod` for backend contracts, with ellipsis bodies for
  the trivial ones: `def count(self) -> int: ...` (`src/research_agent/sessions.py:126`).
- Pydantic `BaseModel` only at the HTTP boundary, with `Field` constraints
  rather than hand-written validation:
  `question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)`
  (`src/research_agent/service.py:56`).

## Error Handling

**Config parsing never raises.** The `_env_float` / `_env_int` pair is
duplicated verbatim in `src/research_agent/retry.py:34-44` and
`src/research_agent/limits.py:43-55`, and both swallow `(KeyError, ValueError)`
and return the default. `connect_timeout()` (`src/research_agent/db.py:37`)
does the same with a `max(1, ...)` floor. A malformed env var degrades to the
default; it does not crash the process.

**Missing required config raises with the fix in the message:**

```python
raise RuntimeError(
    "DATABASE_URL is not set. Postgres-backed stores need it, e.g. "
    "postgresql://user:pass@host:5432/dbname"
)
```
(`src/research_agent/db.py:46`)

Same shape for the optional driver — `ImportError` re-raised with the exact
pip command (`src/research_agent/db.py:57`).

**Always chain with `from`:** `raise ... from exc` at
`src/research_agent/db.py:60`, `src/research_agent/service.py:218,573`.

**HTTP errors are `HTTPException(status, message)` positionally**, with the
offending value repr'd: `raise HTTPException(404, f"No session {session_id!r}.")`
(`src/research_agent/service.py:542,590`). Domain exceptions are translated at
the boundary, not leaked:

```python
except usage_accounting.UnknownModelPricing as exc:
    raise HTTPException(501, str(exc)) from exc
```
(`src/research_agent/service.py:572`)

**Broad catches are allowed only where terminating cleanly matters more than the
error**, and each is annotated: the SSE generator (`service.py:259`) and the
`/health` probe (`service.py:356`), which "must never raise". The blocking
handler catches `BaseException` (`service.py:207`) so a cancelled run is still
recorded as `FAILED` before re-raising.

**Retry classification is an allowlist, not a catch-all.**
`RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})`
deliberately excludes 400/401/403/404/422 — "those are our bug or our key"
(`src/research_agent/retry.py:52`). Server `retry-after` headers win over the
computed backoff (`retry_after_seconds()`, `src/research_agent/retry.py:67`).

**Optional subsystems fail silently by design.** `span()` is a no-op context
manager when OTel is absent (`src/research_agent/observability.py:99`), and it
coerces non-primitive attribute values to `str` because "a tracing call should
never be the thing that fails a run".

## Logging

**Framework:** stdlib `logging`, one named logger (`LOGGER_NAME = "graph"`),
configured through `get_logger()` → `configure_logging()`
(`src/research_agent/observability.py:56,80`).

**Rules observed:**
- Every module that logs does `log = get_logger()` at module scope
  (`src/research_agent/graph.py:49`, `src/research_agent/service.py:43`).
- Structured only: facts go in `extra=`, never interpolated into the message.
  `JSONFormatter` promotes every non-standard `LogRecord` field to a top-level
  JSON key (`src/research_agent/observability.py:38`).
- Log volume is intentionally low — one line per model call
  (`src/research_agent/graph.py:105`), one per completed run
  (`graph.py:450`, `service.py:150`), one warning on a failed run
  (`service.py:209`). Nodes do not narrate.
- `configure_logging` is idempotent, never touches the root logger, and sets
  `logger.propagate = False`. `LOG_FORMAT=json|text`, `LOG_LEVEL` (default `INFO`).

## Comments and Docstrings

**Module docstrings are the primary documentation.** Every module in `src/`,
`evals/`, and `tests/` opens with one, and they follow a consistent shape:
one-line summary, a blank line, then prose explaining *why the module is built
this way* — often several paragraphs. See `src/research_agent/db.py:1-27`
(why one lock-guarded connection instead of a pool) and
`src/research_agent/retry.py:1-18` (why retry at the node boundary).

Modules with tunables list them as an indented block inside the module
docstring rather than in a separate config doc:

```
    AGENT_MAX_ATTEMPTS      total attempts per node, including the first (4)
    AGENT_RETRY_BASE_DELAY  seconds before the first retry (1.0)
    AGENT_RETRY_MAX_DELAY   ceiling for any single sleep (30.0)
```
(`src/research_agent/retry.py:13`)

Modules with a CLI put usage in the docstring and feed it to argparse:
`argparse.ArgumentParser(prog="evals", description=__doc__)` (`evals/__main__.py:43`).

**Function/class docstrings are used where behaviour is non-obvious, skipped
where the signature says it.** No JSDoc/Sphinx/Google-style param blocks
anywhere — no `:param:`, `Args:`, or `Returns:` sections. Prose only.
`def get_logger() -> logging.Logger:` has no docstring; `client_ip()` has six
lines explaining the header trust model (`src/research_agent/limits.py:73`).

**Inline comments explain decisions and tradeoffs, not mechanics.** The strong
pattern across this codebase is that a comment justifies a choice or records a
past bug. Representative examples:
- `# 12: reachable, with headroom` plus a nine-line derivation of `MAX_ITERATIONS`,
  including the bug the evals found (`src/research_agent/graph.py:39-47`)
- `# autocommit: ... an implicit transaction left open by an idle connection
  holds locks` (`src/research_agent/db.py:77`)
- `# the handler above is the only one that should fire` (`observability.py:77`)
- In tests: `# don't leak a store into other tests` (`tests/test_graph_smoke.py:96`)

Comments in `pyproject.toml`, `.github/workflows/ci.yml`, and `docker-compose.yml`
follow the same rule and explain *why* a setting exists.

## Function Design

**Size:** small. Config accessors and predicates are 1–5 lines. The largest
functions are the FastAPI handlers and graph nodes, and they stay under ~60
lines by pushing work into helpers (`_text()`, `call_model()`).

**Parameters:** keyword-friendly with defaults; `**kwargs` forwarded only at the
one model-call choke point (`call_model(state, node, **kwargs)`,
`src/research_agent/graph.py:83`). Constructors take optional injectable
collaborators so tests can substitute:
`def __init__(self, dsn: str | None = None, database: db.Database | None = None)`
(`src/research_agent/sessions.py:240`).

**Return values:** `None` for "not found" on stores (`get() -> Session | None`),
`bool` for "did it exist" on `delete()`, plain dicts for graph state updates.
Small structured returns use frozen dataclasses (`Grade`, `Price`, `CallUsage`)
rather than tuples.

**Single choke points are a deliberate pattern.** Every model call goes through
`call_model()`; every SQL statement goes through `Database.cursor()`; every
node is wrapped by `retry_node`. New code should route through these rather
than calling the client or the driver directly.

## Module Design

**Exports:** no `__all__` anywhere. `src/research_agent/__init__.py` is 7 lines
and does not re-export the package surface — callers import from the concrete
module. There are no barrel files.

**Lazy construction over import-time side effects.** Clients, stores, and
connections are built on first use behind an accessor, with an explanatory
comment: "Constructing them at module scope would mean you cannot import this
module — or unit-test the routing table — without a full set of API keys"
(`src/research_agent/graph.py:51`). CI enforces this: the offline eval step
runs with `ANTHROPIC_API_KEY=""` specifically to catch a client that becomes
eager again.

**Swappable backends are chosen by a `get_*_store()` factory** that reads an
env var and falls back on whether `DATABASE_URL` is present:
`get_memory_store()` / `VECTOR_STORE` (`src/research_agent/memory.py:447`),
`get_session_store()` / `SESSION_BACKEND` (`sessions.py:333`),
`get_metrics_store()` / `METRICS_BACKEND` (`metrics.py:396`). Each normalises
with `.strip().lower()`. A matching `set_memory()` setter exists for runtime
substitution (`graph.py:73`).

## Env Config

Read directly via `os.environ` at the point of use — there is no settings class,
no pydantic-settings, no central config module. Two shapes:

- **Read once at import** into a module constant, for values that cannot change
  after boot: `EMBEDDING_MODEL`, `STORE_PATH`, `PGVECTOR_TABLE`,
  `VECTOR_DIMENSIONS` (`src/research_agent/memory.py:40-57`),
  `SESSION_DB_PATH` (`sessions.py:43`), `METRICS_DB_PATH` (`metrics.py:32`),
  `MAX_ATTEMPTS`/`BASE_DELAY`/`MAX_DELAY` (`retry.py:47-49`).
- **Read per call** through a function, for anything a test or an operator may
  flip at runtime: `demo_token()`, `rate_limit_per_hour()`, `daily_cap_usd()`
  (`limits.py:57-66`), `max_run_cost_usd()` (`usage.py:198`),
  `connect_timeout()`/`database_url()` (`db.py:37,43`). Tests rely on this —
  `tests/test_service.py:24` uses `monkeypatch.setenv` for exactly these.

Boolean env vars are parsed by membership in a tuple of spellings, never
`bool(...)`: `in ("0", "false", "no")` (`observability.py:91`),
`in ("1", "true", "yes")` (`limits.py:84`). Defaults are always supplied
inline as the second argument to `os.environ.get`. `.env.example` documents the
full set; `.env` is gitignored.

---

*Convention analysis: 2026-08-04*
