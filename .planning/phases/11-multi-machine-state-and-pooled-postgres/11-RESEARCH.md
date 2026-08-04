# Phase 11: Multi-machine state and pooled Postgres - Research

**Researched:** 2026-08-05
**Domain:** Managed Postgres provisioning, PgBouncer/Supavisor interaction with `psycopg` 3, connection pooling, Fly.io multi-machine topology
**Confidence:** HIGH on the driver/pooling mechanics and the provider limits (all from official docs fetched today); MEDIUM on the cutover ergonomics; LOW on measured cross-provider latency (must be measured during execution, not assumed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Database: external Postgres (Neon or Supabase), not Fly Postgres**
- the service points at an **external managed Postgres** via `DATABASE_URL`. Neon or Supabase —
  the researcher should recommend one on the evidence below, but the decision to go external is
  settled.
- **Why not Fly Postgres:** `fly postgres create` — the command this repo's own `fly.toml`
  runbook documents — is now the **unsupported** path. Its supported replacement is `fly mpg`.
- **Why external over `fly mpg`:** generous free tiers, pgvector available, and the database
  survives independently of Fly.
- **Hard requirement:** the chosen provider must support **pgvector**.
- **Region matters:** the app runs in Fly `syd`. Pick the provider region closest to Sydney and
  record the measured latency.

**The two-pool problem**
- Transaction-mode pooling breaks server-side prepared statements and session-level state.
  `psycopg` 3 uses prepared statements automatically after a threshold — this is a real failure
  mode, not a theoretical one.
- Establish which endpoint to use (pooled vs direct), what `psycopg_pool` settings are correct
  behind PgBouncer, and whether `prepare_threshold` must be disabled.
- **`sslmode=require`** is mandatory for both providers.

**Data: start clean, keep the volume as a backup**
- Point at an empty Postgres and let new data accumulate. Do **not** run a migration.
- The volume `agent_data` is **kept, not destroyed**. Detaching is reversible; destroying is not.
- What is knowingly given up: the cumulative `/metrics` history. Say this in the phase summary
  rather than letting it look like an oversight.
- `research_agent.migrate` is **not** exercised by this phase — a deliberate choice, not a gap.

**Scale: two machines**
- `fly scale count 2`. `min_machines_running` rises from 1; `auto_stop_machines = 'suspend'` stays.
- The `[[mounts]]` block is removed **only after** `DATABASE_URL` is confirmed working.

**Concurrency, and why the pool is justified**
- `fly.toml` already sets `hard_limit = 16`, `soft_limit = 8`. With two machines that is up to 32
  in-flight requests against one database. The pool is justified by the machine count rising, and
  the phase must state that link explicitly.

### Claude's Discretion
- Neon vs Supabase, on the researcher's evidence.
- Pool min/max sizes and their env var names, provided they are configurable.
- Whether `PG_CONNECT_TIMEOUT` keeps its name in the pooled case.
- Test structure, following the repo's existing conventions.

### Deferred Ideas (OUT OF SCOPE)
- **Caller identity, session ownership, expiry, note lifecycle** — Phase 12.
- **Exercising `research_agent.migrate`** — deliberately skipped.
- **Changing `primary_region`** — possible once stateless, but not this phase.
- **The spend-cap race** (cap counts completed runs only, so ~16 concurrent runs can overshoot ~3×)
  — becomes *worse* at 32 concurrent requests across two machines. Not in scope, but the phase
  should note the interaction rather than silently making it worse.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-multi-machine-state | `DATABASE_URL` set in production, `[[mounts]]` gone from `fly.toml`, machine count > 1, sessions resolve identically from any machine | Provider recommendation + region evidence (§Provider Decision); cutover sequence with reversibility (§Cutover Sequence); `fly-force-instance-id` as the live proof mechanism (§Validation Architecture); Fly volume-detach semantics [CITED: fly.io/docs/volumes/overview] |
| REQ-connection-pool | A pool with configurable min/max size replaces the single lock-guarded connection, preserving reconnect-on-failure and lazy schema application | `psycopg_pool.ConnectionPool` API and lifecycle (§Standard Stack, §Pattern 1); the `PoolTimeout ⊂ OperationalError` retry trap (§Pitfall 1); sizing against `hard_limit = 16` × 2 machines (§Pool Sizing); what must not change in `db.py` (§What Changes in db.py) |
</phase_requirements>

## Summary

Both pre-approved providers offer a Sydney region (`aws-ap-southeast-2`) and both ship pgvector, so
the decision turns on free-tier economics under *this* service's traffic shape. That shape is
unusual and it decides the question: Fly runs `GET /health` every 30 s against every running
machine, and `/health` deliberately issues one query per store. With `min_machines_running = 2`
the database is therefore queried roughly four times a minute, forever, whether or not a human is
using the demo. **Neon's free plan meters compute at 100 CU-hours per project per month — about
400 hours at 0.25 CU** [CITED: neon.com/docs/introduction/plans]. A compute kept permanently awake
by health probes bills ~730 h/month, so the project's compute would be **suspended around day 16
of every month**, dropping existing connections and refusing new ones
[CITED: neon.com/faqs/free-plan-limits-and-quotas]. Neon's scale-to-zero (fixed at 5 minutes on
free) never fires, so it cannot rescue the budget. **Supabase's free tier has no compute meter** —
a Nano instance runs continuously — and its only idle risk is a pause after ~7 days of low
activity, which those same health probes prevent
[CITED: supabase.com/docs/guides/platform/going-into-prod]. The design that disqualifies Neon is
the same design that keeps Supabase alive. **Recommendation: Supabase, region `ap-southeast-2`
(Oceania/Sydney), via the Supavisor session-mode pooler.**

On the two-pool problem, the psycopg documentation is unambiguous: *"Unless a connection pooling
middleware explicitly declares otherwise, they are not compatible with prepared statements… If such
middleware is used you should disable prepared statements, by setting the
`Connection.prepare_threshold` attribute to `None`"* [CITED: psycopg.org/psycopg3/docs/advanced/prepare].
`prepare_threshold` defaults to `5`, so the failure appears only after a query has run six times —
i.e. in production, not in a smoke test. Supabase states plainly that transaction mode does not
support prepared statements [CITED: supabase.com/docs/guides/database/connecting-to-postgres]. The
correct endpoint here is the **session-mode** pooler (`aws-<region>.pooler.supabase.com:5432`): it
is IPv4-reachable (the direct endpoint is IPv6-only on free tier, and Fly→Supabase IPv6 has a
documented history of packet loss), it preserves session semantics the current code assumes, and it
is what Supabase recommends for persistent backends. `prepare_threshold=None` should still be set
unconditionally, so the endpoint choice stops being load-bearing.

The sharpest finding is not about providers at all. `psycopg_pool.PoolTimeout` **subclasses
`psycopg.OperationalError`** [VERIFIED: psycopg_pool/errors.py source]. The existing
`Database.cursor()` retries exactly once on `OperationalError`, so a naive port doubles the
worst-case wait on an unreachable database. That already bites today: the current code makes *two*
3 s connect attempts per probe, so three probes cost up to **18 s against a 15 s Fly health-check
timeout** — the `fly.toml` comment claiming the budget holds is arithmetically wrong. This phase
must fix it, not inherit it.

**Primary recommendation:** Supabase (`ap-southeast-2`) over the Supavisor session pooler; one
process-wide `psycopg_pool.ConnectionPool` shared by all three stores with
`min_size=1, max_size=5, timeout≈2s, prepare_threshold=None, autocommit=True`; retry-once logic that
explicitly excludes `PoolTimeout`/`PoolClosed`; DDL guarded by a Postgres advisory lock because two
machines now boot at once.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Connection lifecycle, retry, pool sizing | Application (`db.py`) | — | The stores must not each own connection policy; `db.py` is already the single owner and stays so |
| Server-side connection multiplexing | Provider (Supavisor) | — | Supabase fronts Postgres with its own pooler; the app pool talks to it, not to Postgres directly |
| Schema application (DDL) | Application (`db.py` lazy path) | Database (advisory lock) | SC-4 forbids DDL at construction; the lock is the only tier that can serialise two machines |
| Session/metrics/note persistence | Database (Postgres) | — | This is the whole point of the phase — moving state off the machine |
| Request→machine routing | Fly Proxy | — | The app must not care which machine serves; that is the claim SC-3 tests |
| Health/liveness reporting | Application (`/health`) | Fly checks | `/health` must stay 200-with-degraded-body; Fly only decides restarts |
| Idle-cost control | Fly (`auto_stop_machines`) + provider tier | — | With `min_machines_running = 2` the Fly side no longer suspends, which is what makes provider compute metering decisive |

## Provider Decision: Supabase, not Neon

### The deciding evidence

| Factor | Neon (Free) | Supabase (Free) | Winner |
|--------|-------------|-----------------|--------|
| Sydney region | `aws-ap-southeast-2` [CITED: neon.com/docs/introduction/regions] | `ap-southeast-2` "Oceania (Sydney)" [CITED: supabase.com/docs/guides/platform/regions] | tie |
| pgvector | listed in extension explorer [CITED: neon.com/docs/connect/connection-pooling nav] | `vector` extension, documented [CITED: supabase.com/docs/guides/database/extensions/pgvector] | tie |
| **Compute metering** | **100 CU-hours/project/month ≈ 400 h at 0.25 CU** [CITED: neon.com/docs/introduction/plans] | **no compute meter; Nano runs continuously** [CITED: supabase.com/docs/guides/platform/compute-and-disk] | **Supabase** |
| Behaviour when exhausted | *"the project's compute is suspended until the next billing period or until you upgrade. Existing connections drop and new ones can't open."* [CITED: neon.com/faqs/free-plan-limits-and-quotas] | n/a | **Supabase** |
| Idle suspension | scale-to-zero after 5 min, **fixed** on Free; wakes in "a few hundred milliseconds" [CITED: neon.com/docs/introduction/scale-to-zero] | project paused after ~7 days of low activity; manual restore from dashboard [CITED: supabase.com/docs/guides/platform/going-into-prod] | tie in practice — health probes defeat both |
| Storage | 0.5 GB/project | 500 MB (Nano recommended max DB size) | tie |
| Max connections | 104 at 0.25 CU, 7 reserved → 97 usable [CITED: neon.com/docs/connect/connection-pooling] | 60 direct, 200 pooler clients (Nano) [CITED: supabase.com/docs/guides/platform/compute-and-disk] | Neon, immaterially |
| Pooler | PgBouncer, up to 10,000 client connections | Supavisor (shared); PgBouncer only as a paid dedicated pooler | tie |
| IPv4 | pooled + direct endpoints resolve normally | direct endpoint is **IPv6-only** on free; the shared pooler is IPv4 [CITED: supabase.com/docs/guides/database/connecting-to-postgres] | Neon |

### The argument, stated plainly

`/health` is the LIVENESS probe and it deliberately queries all three stores. Fly runs it every
30 s per machine. With `min_machines_running = 2`, that is a query every ~15 s, permanently.

- On **Neon**, the compute therefore never scales to zero. 730 h/month × 0.25 CU = **182.5
  CU-hours**, against a 100 CU-hour allowance. The project's compute is suspended roughly
  two-thirds of the way through each month, and a suspended Neon compute *drops connections and
  refuses new ones* — a hard outage on a portfolio URL, recurring monthly, with no in-app remedy.
  The only fixes are (a) stop probing the database on `/health`, which contradicts the deliberate
  design recorded in `service.py` and `fly.toml`, (b) run one machine, which contradicts SC-2, or
  (c) pay. All three are worse than picking the other provider.
- On **Supabase**, the same probe traffic costs nothing (Nano is $0 and unmetered) and actively
  *prevents* the only free-tier hazard, the 7-day inactivity pause.

The cost of choosing Supabase is the IPv4/IPv6 wrinkle, which the session-mode pooler removes
entirely, and a 500 MB storage ceiling that Phase 12's `REQ-store-lifecycle-and-ownership` is
already scheduled to bound.

**Note for the README/summary:** this is a defensible engineering story, not a coin flip — "the
health-check design forces an always-on database, and only one of the two free tiers prices an
always-on database at zero."

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `psycopg[binary]` | `3.3.4` (already pinned) | Postgres driver | Already in `pyproject.toml`; no change [VERIFIED: pyproject.toml] |
| `psycopg-pool` | `3.3.1` | Thread-safe connection pool for `psycopg` 3 | Maintained by the psycopg team in the same repo; the only first-party pool for psycopg 3 [VERIFIED: PyPI + psycopg docs] |

`psycopg-pool` is versioned **independently** of `psycopg` — the docs say so explicitly: *"The
version numbers indicated in this page refer to the `psycopg_pool` package, not to `psycopg`"*
[CITED: psycopg.org/psycopg3/docs/api/pool]. `3.3.1` was published 2026-05-01, requires Python
>= 3.10, and declares support through 3.14 (the CI interpreter) [VERIFIED: PyPI JSON API].

**Installation** — add to the `service` extra in `pyproject.toml`, next to the existing driver:

```toml
service = [
    "fastapi==0.141.1",
    "uvicorn[standard]==0.52.0",
    "psycopg[binary]==3.3.4",
    # The pool. Versioned independently of psycopg; imported lazily for the
    # same reason psycopg is -- a SQLite/JSON deployment needs neither.
    "psycopg-pool==3.3.1",
]
```

Prefer the explicit `psycopg-pool==3.3.1` line over `psycopg[binary,pool]==3.3.4`: the repo pins
every dependency to an exact version, and the extra would leave the pool version floating.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ConnectionPool` | `NullConnectionPool` | Keeps no idle connections — correct when a server-side pooler is doing all the work, but it pays a TLS handshake per request. Wrong here: the point of `min_size ≥ 1` is a warm connection so the first request after a quiet period doesn't pay handshake latency. |
| `ConnectionPool` | `AsyncConnectionPool` | The stores are synchronous and called from FastAPI's threadpool. Going async would mean rewriting all three stores — a much larger change than REQ-connection-pool asks for. Also: *"Opening an async pool in the constructor is deprecated"* [CITED: psycopg docs], adding lifecycle complexity for no gain. |
| App-side pool at all | Rely solely on Supavisor | Rejected by REQ-connection-pool, and rightly: a server-side pooler does not save the client the TCP+TLS handshake, which is the expensive part across a provider boundary. |
| Session-mode pooler | Transaction-mode pooler (`:6543`) | Transaction mode is for serverless/transient clients; it breaks prepared statements and session state. We are a persistent backend. |
| Session-mode pooler | Direct connection (`db.<ref>.supabase.co:5432`) | Lower latency and no pooler hop, but IPv6-only on free tier, and Fly→Supabase IPv6 has documented outage reports. Revisit only if latency measurement shows the pooler hop matters. |

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `psycopg-pool` | PyPI | first release 3.0 in 2021; `3.3.1` published 2026-05-01 | high (psycopg ecosystem) | github.com/psycopg/psycopg | `[OK]` | Approved |

- Verified on the correct ecosystem registry: `pip index versions psycopg-pool` → `3.3.1`
  [VERIFIED: PyPI].
- `slopcheck install psycopg-pool` → `[OK]` (1 scanned, 1 OK) [VERIFIED: slopcheck 2026-08-05].
- Discovered from the official psycopg documentation, not from search — the docs name it directly:
  *"use `pip install "psycopg[pool]"`, or `pip install psycopg_pool`"* [CITED: psycopg.org].

**Packages removed due to slopcheck `[SLOP]` verdict:** none
**Packages flagged as suspicious `[SUS]`:** none

## Architecture Patterns

### System architecture after this phase

```
              Internet
                 │
          Fly Proxy (syd)  ── routes on concurrency; fly-force-instance-id pins a machine
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Machine A          Machine B          ← fly scale count 2, no volume, no local state
   (uvicorn)          (uvicorn)
        │                 │
   one ConnectionPool per machine        ← min_size=1, max_size=5, shared by all 3 stores
   (sessions ▸ metrics ▸ notes)
        │                 │
        └────────┬────────┘
                 │  TLS, sslmode=require, IPv4
                 ▼
   aws-ap-southeast-2.pooler.supabase.com:5432   ← Supavisor, SESSION mode
                 │
                 ▼
        Supabase Postgres (Nano, ap-southeast-2)
          ├── sessions      (JSONB state)
          ├── runs          (metrics)
          └── research_notes (pgvector, HNSW)

   Fly volume agent_data ── detached, retained, unattached, NOT destroyed
```

Notes on the flow that matter for planning:
- Every `/health` hit fans out to three queries, once per machine, every 30 s. That traffic is what
  keeps the Supabase project un-paused, and it is what makes the pool checkout timeout part of the
  liveness budget rather than an implementation detail.
- Both machines apply schema DDL on first use. They can do so simultaneously. See Pitfall 2.

### Pattern 1: one lazily-created, process-wide pool shared by every store

Today each store constructs its own `db.Database(dsn)`, so a machine holds **three** Postgres
connections. A naive port gives three *pools* per machine — 6 pools across the fleet, and the
`min_size` floor multiplies by three. Share one pool per DSN behind a module-level registry:

```python
# Source: pattern derived from psycopg.org/psycopg3/docs/advanced/pool (official)
_pools: dict[str, "ConnectionPool"] = {}
_pools_lock = threading.Lock()

def _pool_for(dsn: str) -> "ConnectionPool":
    from psycopg_pool import ConnectionPool          # lazy, like _psycopg()

    with _pools_lock:
        pool = _pools.get(dsn)
        if pool is None:
            pool = ConnectionPool(
                dsn,
                min_size=pool_min_size(),            # PG_POOL_MIN_SIZE, default 1
                max_size=pool_max_size(),            # PG_POOL_MAX_SIZE, default 5
                timeout=pool_timeout(),              # PG_POOL_TIMEOUT,  default 2.0s
                max_lifetime=1800,                   # 30 min; below any proxy idle cull
                max_idle=300,
                check=ConnectionPool.check_connection,
                kwargs={
                    "autocommit": True,              # unchanged semantics
                    "connect_timeout": connect_timeout(),   # PG_CONNECT_TIMEOUT, unchanged name
                    "prepare_threshold": None,       # REQUIRED behind a pooler -- see Pitfall 3
                },
                open=True,                           # non-blocking; does NOT raise if DB is down
                name="research-agent",
            )
            _pools[dsn] = pool
        return pool
```

**Why `open=True` is safe for SC-4.** The docs: *"After a pool is open, it can accept new clients
even if it doesn't have `min_size` connections ready yet. However, if the application is
misconfigured and cannot connect to the database server, the clients will block until failing with
a `PoolTimeout`"* [CITED: psycopg.org/psycopg3/docs/advanced/pool]. Construction does not connect
synchronously and does not raise. **Do not call `pool.wait()`** — that is precisely the "fail to
boot when the database is down" behaviour the codebase deliberately removed
(`db.ensure_schema` docstring; `tests/test_store_contract.py:477`).

### Pattern 2: retry-once, with pool errors excluded

```python
# The retry must stay narrow. PoolTimeout and PoolClosed are OperationalError
# subclasses (psycopg_pool/errors.py), so catching OperationalError alone would
# retry a timeout and double the worst-case wait -- straight through the Fly
# health-check budget.
@contextmanager
def cursor(self, row_factory=None):
    psycopg = _psycopg()
    from psycopg_pool import PoolClosed, PoolTimeout

    try:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=row_factory) as cur:
                yield cur
    except (PoolTimeout, PoolClosed):
        raise                                   # never retried: the wait already happened
    except (psycopg.OperationalError, psycopg.InterfaceError):
        with self._pool.connection() as conn:   # one more attempt, fresh connection
            with conn.cursor(row_factory=row_factory) as cur:
                yield cur
```

Two properties this preserves from the current code, both load-bearing:
- the retry is limited to **one** attempt and to **connection** errors, so a genuine SQL error
  surfaces immediately rather than running twice;
- `KeyError` raised inside the `with` block (`sessions.append_turn`) still propagates. It is not an
  `OperationalError`, so it is not retried; the pool sees an exception, rolls back (a no-op under
  autocommit) and returns the connection.

### Pattern 3: DDL under an advisory lock

`ensure_schema` / `_apply_schema` stay exactly where they are — deferred, retried on first use,
never in a constructor. The one change two machines force is serialisation (see Pitfall 2):

```python
def _apply_schema(self) -> None:
    if self._schema_applied or self._schema_sql is None:
        return
    with self.cursor() as cur:
        # CREATE ... IF NOT EXISTS is not atomic against a concurrent creator;
        # two machines booting together race and one gets a duplicate-object
        # error from the catalog. A session-level advisory lock costs one
        # round trip on the first use of each process and nothing after.
        cur.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_LOCK_KEY,))
        try:
            cur.execute(self._schema_sql)
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_LOCK_KEY,))
    self._schema_applied = True
```

Under `autocommit=True` there is no transaction to hang the lock on, so use the session-level
`pg_advisory_lock`/`pg_advisory_unlock` pair with an explicit `finally`, **not**
`pg_advisory_xact_lock`. Pick one constant key (e.g. a hash of `"research_agent.schema"`), not one
per store, so the three schema blocks serialise against each other too.

### Pattern 4: connection-level `search_path` for pgvector on Supabase

Supabase installs the `vector` extension into the **`extensions` schema**, not `public` — their own
example writes `embedding extensions.vector(384)`
[CITED: supabase.com/docs/guides/database/extensions/pgvector]. `memory.py` emits unqualified
`vector({dim})` column types and `%s::vector` casts, which only resolve if `extensions` is on the
role's `search_path`. Don't gamble on the default; set it on every pooled connection with the pool's
`configure` callback, or via `options` in the DSN:

```python
def _configure(conn) -> None:
    conn.execute("SET search_path TO public, extensions")
```

This is cheap, explicit, and harmless on CI's stock `pgvector/pgvector:pg16` image (where
`extensions` does not exist — Postgres tolerates missing schemas in `search_path`).

### Anti-Patterns to Avoid

- **Calling `pool.wait()` at startup.** Reintroduces boot-blocks-on-database, which
  `tests/test_store_contract.py:477` exists to prevent.
- **One pool per store.** Triples the connection floor and triples the background worker threads
  for no benefit.
- **Letting one store's `close()` shut a shared pool.** `service.lifespan` closes `sessions` and
  `metrics` on shutdown, and the memory store is never closed at all. A `Database.close()` that
  disposes a shared pool would break the other holders — and, in the test suite, every subsequent
  test using that DSN. Reference-count, or make `close()` release only this `Database`'s claim and
  add an explicit `db.close_all_pools()` for the lifespan `finally`.
- **Leaving the pool `timeout` at its 30 s default.** See Pitfall 1.
- **Transaction-mode pooler (`:6543`).** Wrong tier for a persistent backend.
- **Keeping `SESSION_DB_PATH` / `METRICS_DB_PATH` / `VECTOR_STORE_PATH` in `[env]` after the mount
  is gone.** They would point into an ephemeral container filesystem, and if `DATABASE_URL` were
  ever unset the backends silently fall back to SQLite/JSON per machine — the exact split-brain
  this phase exists to remove, but now invisible because the data no longer even survives a
  restart.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Connection pooling | A list of connections + a lock + a health timer | `psycopg_pool.ConnectionPool` | Background reconnect with exponential backoff, `max_lifetime` jitter to avoid mass eviction, `max_idle` shrink, queue with timeout, broken-connection detection — all documented behaviours you would otherwise reimplement badly |
| Detecting a stale connection | A `SELECT 1` sprinkled through the stores | `check=ConnectionPool.check_connection` | Runs once per checkout, in the pool's own code path, and transparently fetches a different connection on failure |
| Serialising concurrent DDL | A "who booted first" flag in a table | `pg_advisory_lock` | Postgres primitive, no schema needed, released automatically if the session dies |
| Bounding a failing probe | `signal.alarm` / thread kill | libpq `connect_timeout` + pool `timeout` | Both are already parameters; a killed thread mid-query leaves the connection unusable |
| Vector literal formatting | (already hand-rolled, deliberately) | keep `PgVectorMemoryStore._literal` | Documented decision in `memory.py`; not this phase's business |

**Key insight:** the interesting engineering in this phase is not writing a pool — it is choosing
its four numbers so that the liveness budget still closes, and proving the numbers with tests.

## What Changes in `db.py` — and what must not

Read of `src/research_agent/db.py` (179 lines) as it stands:

| Element | Today | After this phase |
|---------|-------|------------------|
| `connect_timeout()` | reads `PG_CONNECT_TIMEOUT`, default 3, floor 1 | **keep the name and the semantics.** It still bounds a single libpq connect attempt — now made by a pool background worker rather than the request thread. Document that it no longer bounds how long a *caller* waits; `PG_POOL_TIMEOUT` does. (SC-6 is exactly this sentence.) |
| `database_url()` | raises with a helpful message when unset | unchanged |
| `_psycopg()` | lazy import with an install hint | unchanged; add a sibling `_psycopg_pool()` with the same shape |
| `Database.__init__` | stores dsn, RLock, `_conn=None`, `_schema_sql`, `_schema_applied=False` | acquires the shared pool instead of the RLock + `_conn`; **still performs no I/O that can raise** |
| `Database._connect` / `_connection` | build/reuse one connection | deleted; the pool owns this |
| `Database._lock` (RLock) | serialises every statement | **deleted.** This is the reversal REQ-connection-pool asks for, and the whole point: statements now run concurrently |
| `Database.cursor()` | one retry on `OperationalError`/`InterfaceError` | same contract, but pool-based and with `PoolTimeout`/`PoolClosed` excluded (Pattern 2) |
| `Database.ensure_schema()` | registers SQL, tries once, **suppresses all exceptions** | unchanged in contract; add the advisory lock inside `_apply_schema` |
| `Database._apply_schema()` / `schema_applied` | idempotent, retried on first use | unchanged in contract — SC-4's "no DDL at construction time" **stays true** |
| `Database.execute/fetchone/fetchall` | `_apply_schema()` then run | unchanged |
| `Database.close()` | closes the connection | must not dispose a pool other holders share (see Anti-Patterns) |
| `postgres_configured()` | `bool(DATABASE_URL)` | unchanged |
| Module docstring | describes the single lock-guarded connection and *why* | **must be rewritten.** It is currently the canonical statement of the decision this phase reverses; leaving it would make the code lie about itself. The new text should say what changed and why (machine count rose), not silently delete the old reasoning. |

Three call-site facts the planner needs:
1. `sessions.py`, `metrics.py` and `memory.py` each do `self.db = database or db.Database(dsn)` and
   then `ensure_schema(...)`. None of them touch `_conn` or `_lock`. **No store needs editing** for
   the pool itself — only `db.py` — which is a good property to state in the plan.
2. `migrate.py` reaches into `source._lock` and `source._conn` — but only on the **SQLite** store,
   not the Postgres one. It is unaffected. (It is out of scope anyway.)
3. `service.lifespan` closes `sessions` and `metrics` but never the memory store; `graph.memory()`
   holds a third `Database`. Pool disposal must account for that.

## Pool Sizing — and the concurrency link that justifies it

The reversal is only defensible if the numbers are tied to the concurrency change. They are:

| Quantity | Value | Source |
|----------|-------|--------|
| Requests per machine before Fly stops routing | `hard_limit = 16` | `fly.toml` |
| Soft limit (Fly starts another machine) | `soft_limit = 8` | `fly.toml` |
| Machines after this phase | 2 | locked decision |
| Fleet-wide in-flight requests | up to **32** | 16 × 2 |
| Database max connections (Supabase Nano) | **60** | [CITED: supabase.com/docs/guides/platform/compute-and-disk] |
| Supavisor max pooler clients (Nano) | 200 | same |

Before this phase, 32 concurrent requests would have queued behind **one** lock-guarded connection.
That was defensible at `min_machines_running = 1` with a run occupying a worker for tens of seconds;
it is not defensible once a second machine exists and `/health`, `/ready`, `/metrics`, `/sessions`
and every run boundary all contend for the same serialised connection across a ~5 ms network hop
instead of a local socket. **The pool is justified by the machine count rising — that is the link,
and it belongs in the plan and the phase summary verbatim.**

Recommended defaults:

| Setting | Env var | Default | Reasoning |
|---------|---------|---------|-----------|
| `min_size` | `PG_POOL_MIN_SIZE` | `1` | One warm, TLS-established connection so the first request after a quiet spell doesn't pay a handshake. Raising to 2 costs 2 more fleet connections and buys a spare — acceptable, not necessary. |
| `max_size` | `PG_POOL_MAX_SIZE` | `5` | Fleet worst case 2 × 5 = **10 of 60** connections, ~17 %. Requests beyond 5 queue; since each store call is a few ms, a queue of 16 drains in well under the pool `timeout`. |
| `timeout` | `PG_POOL_TIMEOUT` | `2.0` s | The caller's maximum wait. Chosen so three sequential probes cost ≤ 6 s inside a 15 s Fly budget. |
| `connect_timeout` | `PG_CONNECT_TIMEOUT` | `3` (unchanged) | Still bounds one libpq connect, now made by a background worker |
| `max_lifetime` | — | `1800` s | Comfortably under any proxy idle cull; the psycopg default of 3600 s is fine too, but 30 min matches the "a managed provider's proxy *will* close you out" concern already documented in `db.py` |

**Headroom check:** 10 app connections + Supabase's own internal consumers (~10–20 on Nano) leaves
ample margin under 60, and far under Supavisor's 200 client ceiling. There is room to raise
`max_size` to 10 later without touching the provider tier.

**Spend-cap interaction (flagged, not fixed — deferred by decision):** the daily cap counts only
*completed* runs, so ~16 concurrent runs can overshoot ~3×. At 32 concurrent that overshoot roughly
doubles. Nothing in this phase makes the race *more likely* per-request, but it raises the ceiling
on how far a burst can exceed `DEMO_DAILY_USD_CAP`. The phase should say so out loud and point at
the deferred item; silently doubling a money-bounding failure mode is the sort of thing a reviewer
notices.

## The `/health` Timing Budget — redone, and it does not currently hold

Fly's check: `timeout = '15s'`, `interval = '30s'`, `grace_period = '20s'` (`fly.toml`).
`/health` calls `_dependencies()`, which probes three stores **sequentially** (`service.py:380-389`):
`store.count()`, `metrics.count()`, `len(memory)`.

**Today, with the single connection:** each probe enters `Database.cursor()`, `self._connection()`
raises `OperationalError` after `connect_timeout` (3 s), the `except` branch reconnects — **a second
3 s attempt** — and then raises. So each probe costs up to **6 s**, and three probes cost up to
**18 s > 15 s**. The `fly.toml` comment ("three store probes each bounded by `PG_CONNECT_TIMEOUT`
(3s), so a fully unreachable database still answers inside the window") is **wrong by a factor of
two**. It has not bitten yet because the database has been on local disk. Once `DATABASE_URL`
points across a provider boundary, an outage would time the check out and restart the machines —
the exact restart loop `/health` was designed to prevent. **This is a pre-existing defect the phase
must fix, and the fly.toml comment must be corrected with it.**

**After this phase**, the dominant bound changes. A caller waiting for a connection is bounded by
the pool's `timeout`, not by `connect_timeout` (connect attempts happen on background workers).
With `PG_POOL_TIMEOUT = 2.0` and `PoolTimeout` excluded from the retry:

| Scenario | Worst case | Budget |
|----------|-----------|--------|
| Database reachable, Sydney→Sydney | 3 probes × (checkout ≈ 0 + query ~2–10 ms) ≈ **< 100 ms** | 15 s ✔ |
| Database unreachable, pool empty | 3 probes × 2 s `PoolTimeout` = **6 s** | 15 s ✔ (margin 9 s) |
| Database unreachable, `PoolTimeout` accidentally retried | 3 × 2 × 2 s = **12 s** | 15 s — passes but with only 3 s of margin; do not rely on it |
| Same, with `PG_POOL_TIMEOUT` left at psycopg's 30 s default | 3 × 30 s = **90 s** | 15 s ✘ restart loop |

Cross-provider latency: Fly `syd` and AWS `ap-southeast-2` are both in Sydney, so the added RTT
should be low single-digit milliseconds — but **this must be measured, not assumed** (see Open
Questions). Even a pessimistic 50 ms RTT changes nothing above: the budget is dominated by timeout
constants, not by query latency.

`/health` must keep returning **200 with a degraded body** — `_probe()` already swallows every
exception (`service.py:362-378`), so a `PoolTimeout` surfaces as `reachable: false` rather than a
500. `/ready` keeps returning 503. Neither contract changes; only the timing does.

## Cutover Sequence

Deploys are manual and `enforce_admins` is false, so a direct push bypasses checks. Use a PR.

| # | Step | Command / change | Reversible? | Safe intermediate state? |
|---|------|------------------|-------------|--------------------------|
| 0 | Land code on `main` via PR (pool, tests, `fly.toml` comment, config guards) — **without** removing `[[mounts]]` or raising machine count | PR + merge | yes (revert) | yes — code is inert while `DATABASE_URL` is unset; stores stay on SQLite/JSON |
| 1 | Create the Supabase project, region **Oceania (Sydney) `ap-southeast-2`** | dashboard | yes (delete project) | yes — production untouched |
| 2 | Enable the `vector` extension | dashboard → Database → Extensions, or `create extension vector` | yes | yes |
| 3 | Measure latency from a Fly machine to the pooler host | `fly ssh console -a research-agent -C "python -c '...'"` (see Open Questions) | n/a | yes |
| 4 | Set the DSN as a Fly secret | `fly secrets set -a research-agent DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-<n>-ap-southeast-2.pooler.supabase.com:5432/postgres?sslmode=require'` | yes (`fly secrets unset`) | **This triggers a deploy.** Machines restart, all three backends flip to Postgres, schema applies on first use. Volume still mounted — SQLite data intact underneath, just unused |
| 5 | Verify | `curl .../health` shows three Postgres-backed stores, `dependencies: ok`; create a session and read it back | n/a | yes |
| 6 | Remove `[[mounts]]` **and** the three local store-path env vars; deploy | edit `fly.toml`, `fly deploy -a research-agent` | yes (re-add the block; the volume still exists) | yes — machine now holds no state, database already proven in step 5 |
| 7 | Confirm the volume survived, unattached | `fly volumes list -a research-agent` | n/a | yes — *"A Fly Machine that does not require a volume will never attach itself to one"* [CITED: fly.io/docs/volumes/overview] |
| 8 | Raise `min_machines_running` to 2 and scale | edit `fly.toml`; `fly scale count 2 -a research-agent` | yes (`fly scale count 1`) | yes |
| 9 | Prove SC-3 across machines | create a session against machine A, read it with `fly-force-instance-id: <machine-B-id>` | n/a | yes |
| 10 | **Do not** destroy the volume | — | **irreversible if done** | — |

**Reversibility summary:** every step from 0 to 9 is reversible. The only irreversible action in
the vicinity is `fly volumes destroy`, which this phase explicitly does not take. Note also that
Neon/Supabase **project region cannot be changed after creation** [CITED: both providers' region
docs] — step 1 is the one choice worth double-checking before clicking.

**Ordering constraint that matters:** step 6 (remove the mount) must come after step 5 (database
proven), per the locked decision — "a machine with neither a volume nor a reachable database is a
broken machine." Step 8 must come after step 6, because a machine that requires a volume will
either grab an unattached one or fail to create.

## `fly.toml` Changes

### The runbook comment is wrong and must be rewritten

Current footer:

```
# --- Going stateless (Phase 8) ---
#   fly postgres create --name research-agent-db
#   fly postgres attach <db-app> -a research-agent
#   ...
# Then remove the [[mounts]] block above and: fly scale count 2
```

`fly postgres create` is the now-unsupported unmanaged path (per CONTEXT). Replace with the
external-provider sequence above. Note that `fly secrets set DATABASE_URL=...` **replaces**
`fly postgres attach` — there is no attach step, and the "the database app is never a deploy
target" warning becomes moot (though `test_fly_config_does_not_target_a_database_app` should stay:
it guards against Fly's GitHub integration, not against the Postgres product).

### Other edits

| Change | Why |
|--------|-----|
| Remove `[[mounts]]` | REQ-multi-machine-state / SC-2 |
| Remove `SESSION_DB_PATH`, `METRICS_DB_PATH`, `VECTOR_STORE_PATH` from `[env]` | They point into a volume that no longer exists; leaving them makes a `DATABASE_URL` outage fall back silently to per-machine ephemeral storage |
| `min_machines_running = 1` → `2` | SC-2 |
| Rewrite the one-machine comment above `auto_stop_machines` | It currently explains why a second machine is unsafe — the opposite of the new truth |
| Correct the health-check timeout comment | The 3×3s arithmetic is wrong (see budget section); state the new `PG_POOL_TIMEOUT`-based bound |
| Keep `auto_stop_machines = 'suspend'` | Locked |
| Keep `primary_region = 'syd'`, but the "pinned to the volume" comment is now stale | Region change is deferred; the comment should say the pin is now a *choice* (proximity to the database), not a constraint |
| Optionally surface `FLY_MACHINE_ID` in `/health` | Without it, SC-3 ("demonstrable to a stranger") is hard to show — you cannot tell which machine answered. Small, self-contained; planner's call |

## `tests/test_deploy_config.py` — what it asserts today, and what must change

| Test | Today | Required change |
|------|-------|-----------------|
| `test_fly_config_parses` | `fly["app"]` truthy | none |
| `test_fly_config_does_not_target_a_database_app` | app name isn't `*-db` / contains "postgres" | **keep** — it guards against Fly's GitHub integration, not the Postgres product |
| `test_the_service_port_matches_the_container` | fly port == EXPOSE == `--port` | none |
| `test_the_healthcheck_path_is_served` | every check path is a real route | none |
| `test_local_store_paths_live_under_the_mount` | **skips** when no mounts | **invert:** with no mount, assert those keys are *absent* from `[env]` — otherwise removing the mount silently disarms the guard |
| `test_a_volume_means_a_single_machine` | **skips** when no mounts; else `min_machines_running <= 1` | **add the positive guard:** no mount ⇒ `min_machines_running >= 2`. Keep the existing arm — the invariant "a volume implies one machine" is still true and still worth guarding if a mount ever returns |
| `test_the_image_runs_as_a_non_root_user` | — | none |
| `test_secrets_are_excluded_from_the_build_context` | `.env` in `.dockerignore` | none |
| `test_the_demo_page_*` | packaging | none |
| *(new)* | — | assert the runbook comment does not mention `fly postgres create` — the comment is documentation that has already gone stale once |

Two tests **skip** rather than fail when the mount is absent. That is the trap: deleting
`[[mounts]]` turns two guards into no-ops and the suite still goes green. Converting both to
two-armed assertions is the substance of SC-5's "guards the new topology".

## Common Pitfalls

### Pitfall 1: `PoolTimeout` is an `OperationalError`, so the existing retry doubles every timeout
**What goes wrong:** `Database.cursor()` catches `psycopg.OperationalError` and retries once.
`psycopg_pool.PoolTimeout` and `PoolClosed` both subclass it
[VERIFIED: `psycopg_pool/errors.py`, github.com/psycopg/psycopg]. A database outage therefore costs
`2 × timeout` per store probe instead of `1 × timeout`.
**Why it happens:** the inheritance is not obvious and nothing in the pool docs highlights it.
**How to avoid:** catch `(PoolTimeout, PoolClosed)` *first* and re-raise; keep `PG_POOL_TIMEOUT`
small (2 s). Test it: assert `/health` with an unreachable DSN answers inside a bound.
**Warning signs:** Fly health checks timing out during a provider incident; machines restarting
while `/health` itself is healthy-by-design.

### Pitfall 2: two machines apply the same DDL at the same time
**What goes wrong:** `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` /
`CREATE EXTENSION IF NOT EXISTS` are **not atomic** against a concurrent creator. Two machines
booting together (which `fly deploy` does, and which a fresh database guarantees, because the phase
starts clean) can produce a duplicate-object error from the catalog on one of them.
**Why it happens:** this is the first phase where two processes ever run the lazy schema path
simultaneously against an *empty* database. It was structurally impossible before.
**How to avoid:** `pg_advisory_lock` around the DDL (Pattern 3). Belt-and-braces: treat
`psycopg.errors.DuplicateTable` / `DuplicateObject` / `UniqueViolation` on the catalog as "already
applied" rather than as failure.
**Warning signs:** an intermittent 500 or a permanently `schema_applied = False` store on exactly
one of two machines, which then looks like a routing bug.

### Pitfall 3: prepared statements silently break after the sixth execution
**What goes wrong:** `prepare_threshold` defaults to `5`
[CITED: psycopg.org/psycopg3/docs/api/connections], so psycopg starts using server-side prepared
statements on the *sixth* execution of a query on a connection. Behind transaction-mode pooling the
prepared statement may not exist on whichever server session the next execution lands on.
**Why it happens:** the threshold means smoke tests pass and production fails later — the worst
possible shape for a deploy-day bug.
**How to avoid:** `prepare_threshold=None` in the pool's `kwargs`, unconditionally. psycopg's own
guidance: *"Unless a connection pooling middleware explicitly declares otherwise, they are not
compatible with prepared statements… you should disable prepared statements"*
[CITED: psycopg.org/psycopg3/docs/advanced/prepare]. psycopg ≥ 3.2 *can* support PgBouncer prepared
statements, but only with PgBouncer ≥ 1.22, `max_prepared_statements > 0`, **and** client libpq
from PostgreSQL 17+ — three conditions we neither control nor can verify on a shared Supavisor
pooler. Setting `None` costs nothing measurable at this query volume and makes the endpoint choice
non-load-bearing.
**Warning signs:** `prepared statement "_pg3_N" does not exist` in logs, appearing minutes after a
deploy rather than immediately.

### Pitfall 4: `sslmode` defaults to `prefer`, not `require`
**What goes wrong:** libpq's default `sslmode` is `prefer`, which silently accepts a plaintext
connection. The DSN copied from a provider dashboard may not include `sslmode`.
**How to avoid:** append `?sslmode=require` to `DATABASE_URL` explicitly. Note that `db.py` passes
the DSN through untouched to `psycopg.connect`, so whatever is in the secret is what is used —
there is no place in the code that would add it for you. Consider a startup log line or a test that
asserts a production-shaped DSN carries `sslmode`.
**Warning signs:** none — that is the problem.

### Pitfall 5: shared-pool disposal breaks the other holders (and the test suite)
**What goes wrong:** `service.lifespan` calls `sessions.close()` then `metrics.close()`; the memory
store's `Database` is never closed. `tests/test_store_contract.py` closes a store after **every**
parametrised case. If `Database.close()` disposes a process-wide shared pool, the second `close()`
and every later test hit `PoolClosed`. A `ConnectionPool` also cannot be reopened after `close()`.
**How to avoid:** reference-count the shared pool, or make `close()` release only this `Database`'s
claim and dispose the pool when the last claim goes; expose `db.close_all_pools()` for the lifespan.
Also make sure the `UNREACHABLE_DSN` pools created by the existing tests are actually disposed —
otherwise background workers keep retrying for `reconnect_timeout` (300 s default) across the whole
test session.
**Warning signs:** `PoolClosed` in tests; lingering threads at pytest exit; a 300 s tail of
reconnect log noise.

### Pitfall 6: `pgvector`'s `vector` type does not resolve on Supabase
**What goes wrong:** Supabase puts the extension in the `extensions` schema; unqualified
`vector(1024)` and `::vector` casts fail with `type "vector" does not exist`.
**How to avoid:** `SET search_path TO public, extensions` in the pool's `configure` callback
(Pattern 4).
**Warning signs:** notes store degraded on `/health` while sessions and metrics are fine — an
asymmetry that reads as a pgvector problem rather than a schema-resolution one.

### Pitfall 7: an existing test asserts on an error message that is about to change
**What goes wrong:** `tests/test_store_contract.py` has
`with pytest.raises(Exception, match="(?i)connect")` for the unreachable-database case. `PoolTimeout`'s
message is *"couldn't get a connection after N.NN sec"* — no "connect". The test breaks.
**How to avoid:** plan the edit deliberately (assert on the exception *type*, which is more
meaningful than the string), rather than discovering it as a red CI run and loosening the match.

### Pitfall 8: removing the mount silently disarms two config guards
Covered above — both `test_local_store_paths_live_under_the_mount` and
`test_a_volume_means_a_single_machine` `pytest.skip()` when there is no mount.

## Code Examples

### Verifying prepared-statement behaviour is off

```python
# Source: psycopg.org/psycopg3/docs/advanced/prepare (official)
with pool.connection() as conn:
    assert conn.prepare_threshold is None      # never auto-prepare behind a pooler
```

### Bounded checkout for a health probe

```python
# Source: psycopg.org/psycopg3/docs/api/pool -- connection() accepts a per-call timeout
# "Note that these methods allow to override the timeout default."
with pool.connection(timeout=1.0) as conn:
    conn.execute("SELECT 1")
```

### Measuring the Fly→Supabase round trip from a real machine

```bash
fly ssh console -a research-agent -C "python - <<'PY'
import os, time, psycopg
dsn = os.environ['DATABASE_URL']
t0 = time.perf_counter(); conn = psycopg.connect(dsn, connect_timeout=5)
print('connect+TLS  %.1f ms' % ((time.perf_counter()-t0)*1000))
ts = []
for _ in range(20):
    t = time.perf_counter(); conn.execute('SELECT 1'); ts.append((time.perf_counter()-t)*1000)
ts.sort(); print('query p50 %.2f ms  p95 %.2f ms' % (ts[10], ts[19]))
PY"
```

Record the numbers in the phase summary — CONTEXT asks for measured latency, and it is also the
evidence that the `/health` budget closes.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `fly postgres create` (unmanaged Fly Postgres) | `fly mpg` (Managed Postgres), or an external provider | Fly deprecated the unmanaged path | The repo's own runbook comment documents the dead path — must be rewritten this phase |
| Supabase fronted by PgBouncer | **Supavisor** for the shared pooler; PgBouncer only as a paid *dedicated* pooler | Supabase replaced PgBouncer with Supavisor (2024) | CONTEXT says "both providers front Postgres with PgBouncer" — accurate for Neon, **out of date for Supabase**. The prepared-statement conclusion is unchanged; only the component name differs |
| `psycopg` never works with PgBouncer + prepared statements | Supported since psycopg 3.2, with three simultaneous preconditions (PgBouncer ≥ 1.22, `max_prepared_statements > 0`, client libpq ≥ 17) | psycopg 3.2 | Doesn't help us — we cannot verify those on a shared pooler. Disable anyway |
| Supabase direct connection over IPv4 | Direct endpoint is **IPv6-only** unless you buy the IPv4 add-on; the add-on is not dual-stack | ongoing | Pushes a Fly-hosted client toward the session-mode pooler |

**Deprecated/outdated:**
- Neon's Azure regions (`azure-eastus2`, `azure-westus3`, `azure-gwc`) — no new projects; free
  projects inactive ≥ 90 days subject to deletion from 2026-10-05 [CITED: neon.com/docs/introduction/regions].
  Irrelevant given the recommendation, but worth not stumbling into.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `fly` CLI | cutover (secrets, deploy, scale, ssh) | ✓ | 0.4.77 | — |
| Python | everything | ✓ | 3.14.6 | — |
| `pytest` / `ruff` | test + lint gates | ✓ (in `.venv`) | 9.1.1 / 0.16.1 | use `.venv/bin/pytest` |
| `psycopg` | Postgres stores | ✓ (in `.venv`) | 3.3.4 | — |
| `psycopg_pool` | this phase | ✗ | — | **must be installed** — `pip install psycopg-pool==3.3.1` after the `pyproject.toml` edit |
| Local Postgres (`docker` / `psql`) | running the 28 Postgres contract tests locally | ✗ | — | **CI covers it** — the `pgvector/pgvector:pg16` service in `.github/workflows/ci.yml` with `REQUIRE_POSTGRES=1`. Locally those tests skip. Plan verification accordingly: "green locally" is not proof for this phase |
| Supabase account/project | the database itself | unknown (human action) | — | none — a `checkpoint:human` step |

**Missing dependencies with no fallback:**
- The Supabase project must be created by a human (dashboard). Plan it as a checkpoint, not a task.

**Missing dependencies with fallback:**
- No local Docker/psql: Postgres-path verification runs in CI. Any new pool test that needs a real
  server must be written to skip cleanly without `DATABASE_URL`, exactly like the existing contract
  tests, and the CI run is the gate.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (pinned in the `dev` extra) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (no `pytest.ini`, no `conftest.py`) |
| Quick run command | `.venv/bin/pytest tests/test_db.py tests/test_deploy_config.py -q` |
| Full suite command | `.venv/bin/pytest -q` (392 collected; 364 pass / 28 skip without `DATABASE_URL`) |
| Postgres coverage | CI service `pgvector/pgvector:pg16` + `REQUIRE_POSTGRES=1`; locally `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=pw pgvector/pgvector:pg16` |

### Phase Requirements → Test Map

| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|-------------|
| REQ-connection-pool | Pool min/max/timeout read from env, configurable | unit | `pytest tests/test_db.py -k pool_size -x` | ❌ Wave 0 (`tests/test_db.py` does not exist) |
| REQ-connection-pool | Constructing a `Database` against an unreachable DSN does not raise and does not connect | unit | `pytest tests/test_store_contract.py -k unreachable -x` | ✅ exists (`:477`) — must keep passing |
| REQ-connection-pool | Schema still deferred; `schema_applied` False until reachable (SC-4) | unit | `pytest tests/test_store_contract.py -k deferred_schema -x` | ✅ exists (`:492`) — **assertion needs updating** (Pitfall 7) |
| REQ-connection-pool | `PoolTimeout` is **not** retried; an unreachable probe returns within one timeout, not two | unit | `pytest tests/test_db.py -k not_retried -x` | ❌ Wave 0 |
| REQ-connection-pool | `/health` with an unreachable database answers within the Fly budget and still returns 200 | unit | `pytest tests/test_service.py -k health_budget -x` | ❌ Wave 0 (extends existing `test_health_stays_200_when_a_store_is_unreachable`, `:992`) |
| REQ-connection-pool | `prepare_threshold=None` and `autocommit=True` reach the connection kwargs | unit | `pytest tests/test_db.py -k prepare_threshold -x` | ❌ Wave 0 |
| REQ-connection-pool | Three stores on one DSN share one pool | unit | `pytest tests/test_db.py -k shared_pool -x` | ❌ Wave 0 |
| REQ-connection-pool | One store's `close()` does not break the others | unit | `pytest tests/test_db.py -k close -x` | ❌ Wave 0 |
| REQ-connection-pool | Reconnect-on-failure survives a server-side connection kill | integration (real PG) | `pytest tests/test_store_contract.py -k reconnect -x` | ❌ Wave 0 — uses `pg_terminate_backend` on our own backends |
| REQ-connection-pool | Concurrent access: N threads all succeed, none exceed `max_size` | integration (real PG) | `pytest tests/test_store_contract.py -k concurrent -x` | ❌ Wave 0 |
| REQ-connection-pool | Concurrent schema application from two independent `Database`s doesn't error | integration (real PG) | `pytest tests/test_store_contract.py -k concurrent_schema -x` | ❌ Wave 0 |
| REQ-connection-pool | Byte-identical cross-backend metrics summary still passes (SC-5) | integration (real PG) | `pytest tests/test_store_contract.py -k identical -x` | ✅ exists (`:282`) |
| REQ-multi-machine-state | No mount ⇒ `min_machines_running >= 2` | unit | `pytest tests/test_deploy_config.py -k machine -x` | ✅ exists — **must be inverted**, currently skips |
| REQ-multi-machine-state | No mount ⇒ no local store paths in `[env]` | unit | `pytest tests/test_deploy_config.py -k store_paths -x` | ✅ exists — **must be inverted**, currently skips |
| REQ-multi-machine-state | Runbook comment no longer names `fly postgres create` | unit | `pytest tests/test_deploy_config.py -k runbook -x` | ❌ Wave 0 |
| REQ-multi-machine-state | A session written through one store instance resolves through a *separate* store instance on the same DSN | integration (real PG) | `pytest tests/test_store_contract.py -k cross_instance -x` | ❌ Wave 0 |
| REQ-multi-machine-state | Same session resolves from a *different machine* | **live only** | `curl -H "fly-force-instance-id: <B>" https://research-agent.fly.dev/sessions/<id>` after creating against A | manual — `checkpoint:human-verify` |

### What is testable where — the honest split

- **Unit-testable, no database.** Everything about pool *configuration and error handling*: env-var
  parsing, kwargs assembly, non-blocking construction, which exceptions are retried, timing bounds
  against `UNREACHABLE_DSN` (the existing `10.255.255.1` idiom, with `PG_CONNECT_TIMEOUT=1` and a
  small `PG_POOL_TIMEOUT`), pool sharing and close semantics, and every `fly.toml` invariant. This
  is the majority of the phase's risk and it needs no server.
- **Needs a real Postgres (CI has one).** Concurrency, reconnect after a killed backend, concurrent
  DDL, the byte-identical metrics assertion, and — importantly — **cross-instance session
  resolution**: two independently constructed `PostgresSessionStore` objects on the same DSN, one
  writing and the other reading. That is the *actual mechanism* SC-3 depends on. A second machine
  adds a network boundary and a Fly routing decision; it does not add a new code path. So the claim
  "a session created against one machine resolves from another" is testable in CI up to routing.
- **Genuinely live-only.** That the Fly *proxy* routes to two machines, that both machines have the
  secret, and that neither holds a volume. Verified with `fly-force-instance-id`
  [CITED: fly.io/docs/networking/dynamic-request-routing], which *"Forces routing to a specific
  Machine… No fallback if Machine is ultimately unavailable"* — the "no fallback" property is what
  makes it proof rather than suggestion. Surfacing `FLY_MACHINE_ID` in the `/health` body would make
  this demonstrable to a stranger in two `curl`s.

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_db.py tests/test_deploy_config.py -q && .venv/bin/ruff check .`
- **Per wave merge:** `.venv/bin/pytest -q` (expect 364 passed / 28+ skipped locally)
- **Phase gate:** full suite green in CI **with Postgres** (0 skipped), then the live checks in the
  cutover table, then `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_db.py` — does not exist; `db.py` is currently covered only indirectly through the
      store contract tests. Conventions say tests mirror their module, and the pool is the phase's
      main risk surface. Covers REQ-connection-pool.
- [ ] New Postgres-path cases inside `tests/test_store_contract.py` (concurrency, reconnect,
      concurrent DDL, cross-instance resolution) — skip cleanly without `DATABASE_URL`, following
      the existing `_skip_without_postgres` / `HAS_POSTGRES` idiom.
- [ ] No `conftest.py` — shared fakes live in the owning module and are imported across test modules
      via `pythonpath = [".", "src", "tests"]`. Follow that; do not introduce one.
- [ ] Framework install: none needed. `pip install -e '.[dev]'` after the `pyproject.toml` edit
      brings `psycopg-pool==3.3.1`.
- [ ] The meta-test at `tests/test_store_contract.py:441` asserts CI is genuinely exercising
      Postgres. Any new Postgres-only test must not undermine it by skipping under `REQUIRE_POSTGRES`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (deferred to Phase 12) | `SESSIONS_TOKEN` stays as-is; `DEMO_TOKEN` stays unset per ADR-0006 |
| V3 Session Management | no | HTTP session identity is Phase 12 |
| V4 Access Control | no | unchanged |
| V5 Input Validation | yes | Already parameterised (`%s`) throughout; `PGVECTOR_TABLE` is validated as alphanumeric before f-string interpolation (`memory.py:340`). No new SQL construction in this phase — **keep it that way** |
| V6 Cryptography | yes | TLS in transit via `sslmode=require`; no application crypto |
| V7 Error Handling & Logging | yes | `_describe_dsn()` strips the password before `/health` returns a store location (`sessions.py:305`). The new DSN puts the project ref in the *username* (`postgres.<ref>`), which `urlparse().hostname` discards — verify this still holds for the pooler-shaped DSN, and that pool error messages (which can echo conninfo) never reach a response body |
| V14 Configuration | yes | `DATABASE_URL` as a Fly secret, never in `fly.toml` (which is committed); `.env` already in `.dockerignore` |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leak via health/error output | Information disclosure | `_describe_dsn()`; add a test that a pool error surfaced through `/health` carries no password |
| Plaintext transport to the provider | Information disclosure | `sslmode=require` in the DSN, asserted at the config level |
| Connection exhaustion (DoS on a 60-connection Nano) | Denial of service | Bounded `max_size` per machine × bounded machine count; `max_waiting` could be set if queueing ever becomes a concern |
| Public demo writing unbounded data into a 500 MB free tier | Denial of service | Existing `DEMO_DAILY_USD_CAP` / rate limit bound run volume; store lifecycle is Phase 12 (`REQ-store-lifecycle-and-ownership`) — note the coupling |
| Secret committed to `fly.toml` | Information disclosure | Set via `fly secrets set`; `fly.toml` already carries the warning comment |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Fly `syd` → AWS `ap-southeast-2` RTT is low single-digit ms | Summary, /health budget | Low — the budget is dominated by timeout constants, not latency. Still: **measure it** (step 3 of the cutover) rather than asserting it |
| A2 | Supabase Nano's 60 `max_connections` leaves ≥ 40 for the application after Supabase's own internal consumers | Pool Sizing | Low — even 20 usable leaves 2× headroom at `max_size = 5`. Verify with `SELECT count(*) FROM pg_stat_activity` after cutover |
| A3 | Supavisor **session** mode preserves prepared statements (only transaction mode is documented as breaking them) | Provider decision | **None, by construction** — the recommendation sets `prepare_threshold=None` regardless, which is why the assumption was made non-load-bearing |
| A4 | `CREATE TABLE/INDEX/EXTENSION IF NOT EXISTS` can race between two concurrent creators in Postgres | Pitfall 2 | Medium — if wrong, the advisory lock is merely unnecessary (one extra round trip per process). Cheap insurance either way |
| A5 | A `ConnectionPool` cannot be reopened after `close()` | Pitfall 5 | Low — affects only the disposal design; verify with a one-line test rather than trusting this |
| A6 | Supabase's free-tier "low activity in a 7-day period" pause is prevented by 30-second health-check queries | Provider decision | Medium — the criterion is not precisely defined by Supabase. Mitigation: the demo is also externally reachable, and a pause is manually restorable from the dashboard (not data loss). Worth a note in OPERATIONS |
| A7 | Both `[env]` store-path variables are inert once `DATABASE_URL` is set (backend selection defaults to Postgres) | fly.toml changes | Low — verified by reading `sessions.default_backend()` / `metrics.default_backend()` / `memory.default_backend()`, all of which key off `db.postgres_configured()` |

## Open Questions

1. **What is the actual Fly `syd` → Supabase `ap-southeast-2` latency?**
   - What we know: both are in Sydney; the Supavisor shared pooler is in the same AWS region as the
     project.
   - What's unclear: the pooler hop's cost, and whether the connect+TLS handshake is slow enough
     that `min_size = 1` is insufficient.
   - Recommendation: measure it in the cutover (command supplied above) and record the numbers in
     the phase summary — CONTEXT explicitly asks for measured latency.

2. **ROADMAP SC-1 contradicts the locked decision.**
   - SC-1 reads: *"`DATABASE_URL` is set in production, `research_agent.migrate` has been run
     dry-run then real…"*. CONTEXT locks: no migration; `migrate` deliberately not exercised.
   - Recommendation: the planner must restate SC-1 (drop the migrate clause, keep the
     `DATABASE_URL` + `/health` clause) and record *why* in the phase docs, so the plan-checker sees
     a deliberate amendment rather than an unmet criterion. Do not quietly ignore it.

3. **Should `/health` expose `FLY_MACHINE_ID`?**
   - What we know: SC-3 requires "demonstrable to a stranger"; today nothing in a response says
     which machine answered.
   - What's unclear: whether this counts as scope creep.
   - Recommendation: include it — it is three lines, it costs nothing, and without it the phase's
     headline claim can only be demonstrated by reading `fly logs`.

4. **Does the 7-day Supabase inactivity clock count health-check queries as activity?**
   - What we know: the pause criterion is "low activity in a 7-day period"; the definition is not
     published.
   - Recommendation: accept the risk (a paused project is manually restorable and loses nothing),
     and document the restore step in `docs/OPERATIONS.md` alongside the manual-deploy runbook.

5. **Where should the pool be disposed?**
   - `service.lifespan` closes two of three `Database` holders; `graph.memory()`'s store is never
     closed. Recommendation: add `db.close_all_pools()` to the lifespan `finally`, and leave
     `Database.close()` as a claim-release. Planner's call on refcounting vs. a simple registry.

## Sources

### Primary (HIGH confidence)
- psycopg 3 docs — Prepared statements / PgBouncer: https://www.psycopg.org/psycopg3/docs/advanced/prepare.html
- psycopg 3 docs — Connection pools (behaviour, startup, lifecycle): https://www.psycopg.org/psycopg3/docs/advanced/pool.html
- psycopg 3 docs — `ConnectionPool` API (all constructor parameters and defaults): https://www.psycopg.org/psycopg3/docs/api/pool.html
- psycopg 3 docs — `Connection.connect` (`prepare_threshold` default = 5): https://www.psycopg.org/psycopg3/docs/api/connections.html
- psycopg source — `psycopg_pool/errors.py` (`PoolTimeout(OperationalError)`): https://github.com/psycopg/psycopg/blob/master/psycopg_pool/psycopg_pool/errors.py
- PyPI JSON API — `psycopg-pool` 3.3.1, published 2026-05-01, requires-python >= 3.10, classifiers through 3.14
- Neon docs — Regions: https://neon.com/docs/introduction/regions
- Neon docs — Plans (100 CU-hours/project/month): https://neon.com/docs/introduction/plans
- Neon docs — Scale to zero (5 min, fixed on Free): https://neon.com/docs/introduction/scale-to-zero
- Neon docs — Connection pooling (PgBouncer, `max_connections` by CU): https://neon.com/docs/connect/connection-pooling
- Neon FAQ — Free plan limits and exhaustion behaviour: https://neon.com/faqs/free-plan-limits-and-quotas
- Supabase docs — Available regions: https://supabase.com/docs/guides/platform/regions
- Supabase docs — Connect to Postgres (endpoints, IPv4/IPv6, transaction mode + prepared statements): https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase docs — Compute and Disk (Nano: 60 connections, 200 pooler clients, 500 MB): https://supabase.com/docs/guides/platform/compute-and-disk
- Supabase docs — Going into prod (7-day inactivity pause): https://supabase.com/docs/guides/platform/going-into-prod
- Supabase docs — pgvector (`extensions.vector(...)`): https://supabase.com/docs/guides/database/extensions/pgvector
- Fly docs — Volumes overview (unattached volumes, "a Machine that does not require a volume will never attach itself to one"): https://fly.io/docs/volumes/overview/
- Fly docs — Dynamic request routing (`fly-force-instance-id`): https://fly.io/docs/networking/dynamic-request-routing/
- Codebase — `src/research_agent/db.py`, `sessions.py`, `metrics.py`, `memory.py`, `migrate.py`, `service.py`, `fly.toml`, `pyproject.toml`, `tests/test_deploy_config.py`, `tests/test_store_contract.py`, `.github/workflows/ci.yml`

### Secondary (MEDIUM confidence)
- slopcheck 2026-08-05 — `psycopg-pool` → `[OK]` on PyPI
- Local environment probe — `fly` 0.4.77 present; no `docker`/`psql`; `.venv` has psycopg 3.3.4, no `psycopg_pool`

### Tertiary (LOW confidence — flagged, not relied upon)
- Fly community reports of IPv6 packet loss to Supabase endpoints (community.fly.io). Used only as
  supporting motivation for the session-mode pooler, which is independently recommended by
  Supabase's own docs for IPv4 clients.

## Metadata

**Confidence breakdown:**
- Provider decision: **HIGH** — the deciding numbers (100 CU-hours, suspension behaviour, Nano being
  unmetered) all come from the providers' own docs, fetched 2026-08-05
- Pool mechanics and settings: **HIGH** — every parameter and default read from the official API
  reference; the `PoolTimeout` inheritance read from source
- `/health` budget arithmetic: **HIGH** on the timeout maths, **MEDIUM** on the conclusion that the
  *current* code already exceeds 15 s (derived by reading `cursor()`'s retry path; worth confirming
  with the new timing test rather than trusting the reading)
- Cutover ergonomics: **MEDIUM** — Fly volume-detach semantics are documented, but the exact
  behaviour of `fly deploy` against a machine that currently has a volume when the mount is removed
  is inferred, not tested
- Pitfalls: **HIGH** for 1, 3, 5, 7, 8 (each traceable to source or to a line in this repo);
  **MEDIUM** for 2, 4, 6

**Research date:** 2026-08-05
**Valid until:** 2026-09-04 (30 days). Free-tier terms are the volatile part — re-check Supabase's
Nano allowances and Neon's CU-hour allowance before executing if this sits for more than a month.
