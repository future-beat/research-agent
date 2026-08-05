---
phase: 11-multi-machine-state-and-pooled-postgres
plan: 01
subsystem: database
tags: [postgres, psycopg, psycopg-pool, connection-pool, advisory-lock, pgvector]

# Dependency graph
requires:
  - phase: pre-GSD (phases 1-9)
    provides: "src/research_agent/db.py — the single lock-guarded Postgres connection, ensure_schema's deferred-DDL contract, and the three stores that each construct their own Database"
provides:
  - "A pooled db.Database: one psycopg_pool.ConnectionPool per DSN, shared by every Database on it"
  - "close_all_pools() for the service lifespan's finally (wired in 11-02)"
  - "Five new env readers: PG_POOL_MIN_SIZE, PG_POOL_MAX_SIZE, PG_POOL_TIMEOUT, PG_STATEMENT_TIMEOUT, PG_TCP_USER_TIMEOUT"
  - "A retry that excludes PoolTimeout/PoolClosed, so an outage costs one checkout timeout rather than two"
  - "DDL serialised under pg_advisory_lock(3895545195), taken/held/released on a single connection with the unlock's result checked"
  - "tests/test_db.py — 27 tests, no server required"
affects: [11-02, 11-03, 11-04, 11-05, phase-12]

# Tech tracking
tech-stack:
  added: [psycopg-pool==3.3.1]
  patterns:
    - "Module-level per-DSN pool registry with a claim refcount"
    - "Exception-arm ordering as a correctness device (subclass before superclass)"
    - "Single-checkout invariant for session-scoped Postgres state"

key-files:
  created:
    - tests/test_db.py
  modified:
    - src/research_agent/db.py
    - pyproject.toml

key-decisions:
  - "check=ConnectionPool.check_connection deliberately DROPPED against RESEARCH's suggestion: the liveness check is itself a server round trip performed during checkout and the pool's timeout does not interrupt one in flight, so on a partitioned database it adds an unbounded cost to every checkout — on the exact endpoint whose budget this phase closes. Staleness is already covered by the retry-once arm."
  - "PoolTimeout/PoolClosed are re-raised in an arm placed BEFORE the OperationalError arm, because they subclass it. Measured: 0.505s with the exclusion, 1.007s without."
  - "The advisory lock, the schema DDL and the unlock share ONE cursor() call. pg_advisory_lock is session-scoped, which under a pool means per checkout."
  - "pg_advisory_unlock's return value is read and false raises. False is exactly the signature of the single-connection invariant having broken; ensure_schema still suppresses, so the cost is a deferred retry rather than a crash — but it is no longer silent."
  - "prepare_threshold=None set unconditionally, so the choice of pooler endpoint stops being load-bearing."
  - "Database.close() is a claim release and is idempotent; the pool is disposed only when the last holder lets go."
  - "min_size=0 in the registry tests (fixture `cold_pool`), so opening a pool against a blackhole address starts no background connect attempts."

patterns-established:
  - "Anti-pattern guards vs progress gates: two acceptance greps assert a string is ABSENT and were already 0 before the work. They are labelled as guards in the plan and stayed labelled here."
  - "A gate is unproven until it has been observed failing. Both behavioural gates in this plan were mutated, observed red, and reverted."
  - "Tests that build a pool use a test-unique DSN plus an autouse close_all_pools() fixture, because _pool_for caches per DSN with pool_timeout() read at construction."

requirements-completed: [REQ-connection-pool]

# Metrics
duration: 55min
completed: 2026-08-05
---

# Phase 11 Plan 01: Pooled Postgres Summary

**`db.py` moved from one RLock-guarded connection to one shared `psycopg_pool.ConnectionPool` per DSN, with `PoolTimeout` excluded from the retry (0.505s instead of 1.007s on an unreachable database) and schema DDL serialised under a single-connection advisory lock.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-08-05T03:33:00Z
- **Completed:** 2026-08-05T04:30:00Z
- **Tasks:** 3
- **Files modified:** 3 (2 modified, 1 created)

## Accomplishments

- One pool per DSN shared by all three stores, where a naive port would have given three pools per machine and tripled the warm-connection floor across the fleet.
- The retry is narrowed. `PoolTimeout` and `PoolClosed` subclass `psycopg.OperationalError`, so the pre-existing `except OperationalError: retry once` arm would have retried a checkout timeout and doubled every wait — straight through the Fly health-check budget. Measured both ways (below).
- Statements are bounded, not just checkouts: `statement_timeout` via `options`, `tcp_user_timeout` plus keepalives, with the residual (a peer that stays TCP-alive and never answers) named in the docstring rather than papered over.
- The advisory lock, the DDL and the unlock run on one connection, and the unlock's boolean is read and raised on.
- `tests/test_db.py` exists — 27 tests, no server needed. `db.py` was previously covered only indirectly, through the Postgres-gated half of the store contract suite.

## Task Commits

1. **Task 1: Pin psycopg-pool and add the pool and connection-bound config readers** — `8c7a145` (feat)
2. **Task 2: One shared pool per DSN, claim-released disposal, query-level bounds** — `9e46158` (feat)
3. **Task 3: Narrow the retry to exclude PoolTimeout, serialise DDL on one connection** — `5df970b` (feat)

## Files Created/Modified

- `src/research_agent/db.py` — pooled `Database`, the `_pools`/`_pool_claims` registry, `_connect_kwargs()`, `_configure()`, `_pool_for()`, `_release_pool()`, `close_all_pools()`, `SCHEMA_LOCK_KEY`, five env readers, and a rewritten module docstring
- `tests/test_db.py` — new. Config readers, connection bounds, pool sharing, disposal, retry narrowing, the timing bound, and the single-connection lock invariant
- `pyproject.toml` — `psycopg-pool==3.3.1` in the `service` extra

## Falsification Checks

The plan required these and they were run. An unmutated green is not evidence.

| Gate | Mutation applied | Observed | Reverted |
|------|------------------|----------|----------|
| `-k schema_lock_single_connection` | Split the block: `pg_advisory_lock` in one `cursor()` call, DDL + unlock in a second | **RED** — `AssertionError: the whole block must run on ONE checkout / assert 2 == 1`, the fake pool having handed out two `FakeConnection` objects | Yes — re-run green (2 passed) |
| `-k pool_timeout_not_retried` | Replaced `except (PoolTimeout, PoolClosed): raise` with `except ():`, i.e. the naive port | **RED** — `assert 1.0073656251188368 < 1.0`, exactly the doubled timeout the exclusion exists to prevent | Yes — re-run green, 0.505s |

The second was not strictly demanded by the plan; it was cheap and it is the phase's headline claim, so it was mutated too.

## Measured Evidence

Unreachable DSN (`10.255.255.1`, a blackhole so connections hang rather than being refused), `PG_CONNECT_TIMEOUT=1`, `PG_POOL_TIMEOUT=0.5`, `PG_POOL_MIN_SIZE=0`:

```
0.505s  PoolTimeout: couldn't get a connection after 0.50 sec
```

versus `1.007s` with the exclusion removed. The test asserts `< 1.0`, so a reintroduced retry fails the test rather than merely slowing it.

Incidentally this settles RESEARCH's Pitfall 7 in the opposite direction from the prediction: `PoolTimeout`'s message is *"couldn't get a connection after 0.50 sec"*, and `test_store_contract.py`'s `pytest.raises(Exception, match="(?i)connect")` is a `re.search`, which "connection" satisfies. The test did **not** break and needed no edit.

## Decisions Made

See `key-decisions` in the frontmatter. The one that most deserves a reader's attention:

**`check=ConnectionPool.check_connection` was deliberately dropped**, against RESEARCH's Pattern 1 which suggested it. The reason, recorded both in a comment in `_pool_for()` and here: the check is a server round trip performed *during* checkout, and the pool's `timeout` does not interrupt a check already in flight. Against a partitioned database it therefore becomes an unbounded addition to every caller's wait — on `/health`, the exact endpoint whose budget this phase exists to close. Connection staleness is already handled by the retry-once arm, which is the pre-existing contract and is unchanged. A silently omitted parameter reads as an oversight, which is why the reason is written down in two places and gated by `grep -c 'check_connection' src/research_agent/db.py` returning 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Two acceptance greps failed because the prose that documents a choice contains the string the gate forbids**
- **Found during:** Tasks 2 and 3
- **Issue:** The anti-pattern guards `grep -c 'pool.wait()\|\.wait()'` and `grep -c 'check_connection'` (and later `grep -c 'pg_advisory_xact_lock'`) returned 1, not 0 — not because the code did the wrong thing, but because the comments explaining why it does *not* do the wrong thing named the forbidden call.
- **Fix:** Reworded three comments to describe the rejected option without spelling its identifier: "nothing here blocks until the pool is warm", "NO `check=` liveness callback", "the transaction-scoped variant". Every reason survives; only the literal token is gone.
- **Files modified:** `src/research_agent/db.py`
- **Verification:** All three greps now return 0; the reasoning is still readable in place.
- **Committed in:** `9e46158`, `5df970b`

**2. [Rule 3 — Blocking] Registry tests were paying `PG_CONNECT_TIMEOUT` per pool at disposal**
- **Found during:** Task 2
- **Issue:** With the default `min_size=1`, opening a pool against the blackhole DSN starts a background connect attempt, and disposal waits for it. The Task 2 selector took 10.1s for eight tests that are about the registry, not about warm connections.
- **Fix:** Added a `cold_pool` fixture setting `PG_POOL_MIN_SIZE=0` for the registry and disposal tests. The timing test keeps its own explicit env, so nothing it measures is affected.
- **Files modified:** `tests/test_db.py`
- **Verification:** `tests/test_db.py` runs in 5.1s; the whole suite is 16.3s against a 18.4s baseline.
- **Committed in:** `9e46158`

**3. [Rule 1 — Lint] Four `SIM117` and one `SIM300` from ruff**
- **Found during:** Tasks 2 and 3
- **Issue:** Nested `with pytest.raises(...)` / `with handle.cursor()` blocks and one Yoda condition.
- **Fix:** `ruff check --fix` for the four; hand-fixed the Yoda comparison.
- **Files modified:** `tests/test_db.py`
- **Verification:** `.venv/bin/ruff check .` exits 0.
- **Committed in:** `9e46158`, `5df970b`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 lint)
**Impact on plan:** None on behaviour. Deviation 1 is the only interesting one — it is a real tension between "gate on the absence of a string" and "document why the string is absent", and it was resolved in favour of keeping both the gate and the reasoning.

## Issues Encountered

**Handed to plan 11-02, as the plan anticipated:** `tests/test_store_contract.py::test_the_connection_recovers_from_being_dropped` reaches into `store.db._conn`, an attribute this plan deletes. It is `skipif(not HAS_POSTGRES)`, so it **skips locally and did not turn the local suite red** — but it will fail in CI, which sets `DATABASE_URL`. Repairing it is 11-02's job and it was deliberately not patched here. `store.db._schema_sql`, the other attribute the contract suite reaches for, survives under its own name.

**Not an issue, recorded so nobody re-derives it:** the retry arm in `cursor()` can only fire on an exception raised at *checkout*, not one raised inside the caller's `with` body — a `@contextmanager` that yields a second time after an exception is thrown in raises `RuntimeError: generator didn't stop after throw()`. This is the pre-existing shape of the code, unchanged by the port, and `test_the_connection_recovers_from_being_dropped` passes because the connection is rebuilt at entry rather than failing mid-body. Worth knowing before anyone "improves" the retry.

**Spend-cap interaction, flagged not fixed (deferred by decision):** the daily cap counts only completed runs, so ~16 concurrent runs can overshoot ~3×. At 32 fleet-wide concurrent requests the ceiling on that overshoot roughly doubles. Nothing here makes the race more likely per request; it raises how far a burst can exceed `DEMO_DAILY_USD_CAP`. Phase 12 owns it.

## Verification

- `.venv/bin/pytest` (bare) — **415 passed, 28 skipped**. Baseline was 388/28: +27 tests, skip count unchanged, so Postgres coverage was extended rather than disarmed.
- `.venv/bin/ruff check .` — exits 0.
- `git status --porcelain fly.toml` — empty. This plan does not touch topology; that is 11-03 and 11-05.
- Order independence: `tests/test_db.py` passes under `-p no:randomly`, with the timing test run alone, and alongside `tests/test_store_contract.py`.
- Acceptance greps, all as specified: `RLock` 0, `self._lock` 0, `self._conn` 0, `pool.wait()|.wait()` 0, `check_connection` 0, `pg_advisory_xact_lock` 0; `prepare_threshold` 1, `statement_timeout` 4, `tcp_user_timeout` 5, `keepalives` 5, `search_path` 3, `close_all_pools` 1, `PoolTimeout` 2, `pg_advisory_lock` 4, `pg_advisory_unlock` 2, `PG_POOL_TIMEOUT` 5, `hard_limit` 2, `SCHEMA_LOCK_KEY = 3895545195` 1.

## User Setup Required

None for this plan. `DATABASE_URL` provisioning is 11-04.

## Next Phase Readiness

Ready for 11-02, which must:

1. Repair `test_the_connection_recovers_from_being_dropped` — assert on reconnect behaviour rather than on `store.db._conn`.
2. Wire `db.close_all_pools()` into `service.lifespan`'s `finally`. It exists and is tested; nothing calls it yet.
3. Add the per-probe wall-clock deadline on `/health`. This plan's docstring already forward-references it as the bound on the residual that libpq cannot cover, so leaving it unbuilt would make `db.py` promise something that does not exist.
4. Add the real-server halves: the two-connection advisory-lock exclusivity test (`concurrent_schema_init`) and `pgvector_search_path`. The `_configure` callback that the latter tests is written but has never run against a server — nothing in this plan opens a connection.

## Self-Check: PASSED

All three files present (`src/research_agent/db.py`, `tests/test_db.py` at 493 lines, `pyproject.toml`);
all three task commits resolve (`8c7a145`, `9e46158`, `5df970b`).

---
*Phase: 11-multi-machine-state-and-pooled-postgres*
*Completed: 2026-08-05*
