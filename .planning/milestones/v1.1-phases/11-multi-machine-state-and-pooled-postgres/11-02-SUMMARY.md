---
phase: 11-multi-machine-state-and-pooled-postgres
plan: 02
subsystem: service
tags: [health-check, connection-pool, postgres, pgvector, advisory-lock, fly]

# Dependency graph
requires:
  - phase: 11-01
    provides: "The pooled db.Database, close_all_pools(), the pool/connection env readers, and SCHEMA_LOCK_KEY"
provides:
  - "A /health with a 9s ceiling that holds for a warm partitioned pool, not only a cold one"
  - "HEALTH_PROBE_BUDGET (3.0s default, 0.1 floor) and a rebuildable probe executor"
  - "A lifespan that disposes every pool, including graph.memory()'s, which nothing ever closed"
  - "A machine key in the /health body, sourced from FLY_MACHINE_ID -- the thing that makes SC-3 demonstrable in two curls"
  - "db._connection_was_lost() and a pool.check() on the read-retry failure path"
  - "Six real-Postgres tests: lock exclusivity, concurrent schema init, statement-timeout bound, search_path/pgvector cast, cross-instance resolution, concurrency past max_size"
  - "-k fails_closed: pinned Postgres backends raise without a DSN"
affects: [11-03, 11-04, 11-05, phase-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wall-clock deadline per health probe, bounding availability rather than execution"
    - "SQLSTATE as the discriminator between 'the connection died' and 'the server said no'"
    - "Repair-on-failure (pool.check) rather than verify-on-every-checkout (check=)"

key-files:
  created: []
  modified:
    - src/research_agent/service.py
    - src/research_agent/db.py
    - tests/test_service.py
    - tests/test_store_contract.py
    - tests/test_db.py

key-decisions:
  - "A local PostgreSQL 17 + pgvector was built to run the Postgres-gated suite, because Docker was unavailable and the inherited breakage was invisible without a server. It found two real bugs that no fake caught."
  - "_connection_was_lost() keys on SQLSTATE, not on exception class. Both obvious rules are wrong: 'any OperationalError' retries a QueryCanceled (57014) and doubles the statement timeout; 'has a SQLSTATE means the server is alive' refuses to retry AdminShutdown (57P01), which is what pg_terminate_backend actually sends. The second rule shipped in 6e05954 and was caught by the real server."
  - "The read retry calls pool.check() before its second attempt. A provider kills every idle connection at once, so a bare retry-once drew the next corpse and still failed. This is NOT the check= checkout callback 11-01 rejected: that costs a round trip on every checkout, this runs only after a connection is already known dead."
  - "Reads retry the whole statement; writes deliberately do not. A retried write is at-least-once and the client cannot tell 'never arrived' from 'committed, response lost'."
  - "The probe executor is lazily rebuilt after shutdown, because lifespan runs more than once per process -- the suite enters it nine times."
  - "No future.cancel() on a timed-out probe, so the documented reaping mechanism (tcp_user_timeout) stays the true one rather than being half-replaced by an undocumented queue-drain."

requirements-completed: [REQ-connection-pool, REQ-multi-machine-state]

# Metrics
duration: 95min
completed: 2026-08-05
---

# Phase 11 Plan 02: /health bounded, pools disposed, real-Postgres coverage Summary

**`/health` now carries a per-probe wall-clock deadline giving it a 9s ceiling that holds for a warm partitioned pool (0.32s measured against a store that never answers, versus 31.4s with the deadline removed), and the six new real-Postgres tests found two genuine `db.py` bugs that every fake in the repo had passed.**

## Performance

- **Duration:** ~95 min
- **Tasks:** 3, plus one unplanned prerequisite fix
- **Files modified:** 5

## Accomplishments

- `/health`'s bound is no longer an arithmetic argument that only holds when the pool is cold. Each probe runs under `HEALTH_PROBE_BUDGET`, so the warm-but-partitioned case — checkout returns in ~0ms, then the statement blocks on a peer that has gone away — is bounded too. That case was bounded by *nothing* before: `PG_POOL_TIMEOUT` was already spent, `PG_CONNECT_TIMEOUT` never applied to an established connection.
- **A local Postgres was built to run the gated suite.** Docker was unavailable, so PostgreSQL 17 + pgvector were installed via Homebrew and run on port 54329. This was the single highest-value decision in the plan: the suite was green locally and *broken* against a server, exactly as the plan warned.
- The inherited `_conn` breakage is fixed, and fixing it properly turned out to require three separate corrections — only the first of which was visible without a server.
- `graph.memory()`'s `Database`, which nothing has ever closed, is now disposed at shutdown.
- `/health` names the machine that answered. Without it SC-3 can only be demonstrated by reading `fly logs`.

## Task Commits

1. **Task 1: Bound every probe, dispose every pool, name the machine** — `b4208dc` (feat)
2. **Prerequisite fix: retry a read whose connection dies mid-statement** — `6e05954` (fix)
3. **Task 2: Repair the two invalidated tests, assert fail-closed** — `95576e7` (test)
4. **Task 3: Six real-Postgres gates, and fix what running them exposed** — `82f074b` (test)

## The inherited breakage, and what it actually was

The plan handed this forward as one repair: `test_the_connection_recovers_from_being_dropped` reaches into `store.db._conn`, which 11-01 deleted. Replacing the simulation with `pg_terminate_backend` was the easy half. The test then failed for three further reasons, in sequence:

**1. The reconnect contract did not survive the port to a pool.** Found *without* a server, using a fake pool. The old single connection failed at *entry* — `_conn.cursor()` touching a socket the provider had closed — so `cursor()`'s rebuild landed in the right place. A pool hands out a connection that still looks live, and the failure lands on `cur.execute`, inside the caller's `with` body. A `@contextmanager` cannot retry from there: yielding a second time after `gen.throw` raises `RuntimeError: generator didn't stop after throw()`, which fails the call *and* destroys the real error.

```
$ python probe_retry.py          # fake pool, first connection dead
RAISED RuntimeError: generator didn't stop after throw()
```

Fixed by giving `cursor()` a single yield via `ExitStack` (checkout retry unchanged, body exceptions propagate as themselves) and moving the statement-level retry into `fetchone`/`fetchall`, which own their whole statement.

**2. `AdminShutdown` has a SQLSTATE.** Found *only* with the server. The first retry rule was "a SQLSTATE means the server answered, so the connection is alive — do not retry", which correctly excluded `QueryCanceled` (57014, how `PG_STATEMENT_TIMEOUT` surfaces, and a subclass of `OperationalError`). But `pg_terminate_backend` arrives as `AdminShutdown`, SQLSTATE 57P01 — server-reported, connection gone. The rule raised instead of retrying.

```
E  psycopg.errors.AdminShutdown: terminating connection due to administrator command
1 failed, 77 passed
```

Replaced with `_connection_was_lost()`: SQLSTATE `None` (client-side), class `08` (connection_exception), or `57P01/02/03` (operator intervention) retry; everything else raises.

**3. One retry was still not enough.** Also only visible with the server. A provider that terminates backends terminates *all* of them, so the retry simply drew the next corpse — the log shows two connections discarded and the test still red. The failure path now calls `pool.check()`, which tests every idle connection and replaces the broken ones, so one retry suffices however many the pool held.

This is deliberately **not** the `check=` checkout callback 11-01 rejected. That one costs a server round trip on *every* checkout including `/health`'s, which is the objection and it still stands. This one runs only after a connection has already been found dead, where a round trip is the cheapest thing available.

## Falsification Checks

An unmutated green is not evidence.

| Gate | Mutation applied | Observed | Reverted |
|------|------------------|----------|----------|
| `-k health_probe_deadline` | `future.result(timeout=budget)` → `future.result()` | **RED, and it hangs**: 31.4s wall clock (the test's 30s backstop) versus 0.32s deadlined, failing on `assert 'ok' == 'degraded'` | Yes — re-run green in 1.9s |
| `-k statement_timeout_bounds_a_slow_query` | Removed the `options="-c statement_timeout=..."` connect kwarg | **RED** — `Failed: DID NOT RAISE QueryCanceled` against `pg_sleep(5)` | Yes — re-run green |
| `test_the_connection_recovers_from_being_dropped` | None needed — it was **observed red twice** against the real server before the two `db.py` fixes landed | `AdminShutdown`, then a second dead connection | n/a — the fixes are the revert |

The `health_probe_deadline` mutation is the one the plan demanded. Note the shape of the observation: it does not fail fast, it *hangs* for the full backstop and then fails. Without the 30s `Event` backstop it would hang forever, which is precisely the production failure — Fly's 15s check timeout expiring and both machines restarting for a fault a restart cannot fix.

## Measured Evidence

| Measurement | Result | Ceiling asserted | Why that ceiling |
|---|---|---|---|
| `/health` vs a store that never answers, `HEALTH_PROBE_BUDGET=0.3` | **0.32s** | 1.9s (`3 × 0.3 + 1.0`) | Undeadlined: 31.4s |
| `/health` vs three unreachable stores, cold pool, `PG_POOL_TIMEOUT=0.5` | **1.53s** | 2.3s | A reintroduced `PoolTimeout` retry costs 3.0s and fails it |
| `pg_sleep(5)` under `PG_STATEMENT_TIMEOUT=500` | **0.51s** | 2.0s | Unbounded: the full 5s |
| 12 concurrent reads against `PG_POOL_MAX_SIZE=5` | **0.02s**, 0 `PoolTimeout` | — | Pre-pool, all 12 serialise behind one connection |

Production defaults give the ceiling the plan specifies: 3 sequential probes × 3.0s = **9s**, inside Fly's 15s check timeout, whether the pool is cold, warm or partitioned. The ordinary cold-pool cost is 3 × `PG_POOL_TIMEOUT` ≈ 6s and is *not* the bound.

## Skip-count arithmetic

The plan's amended invariant, checkable:

- **Local, before:** 415 passed, **28 skipped** (11-01's baseline)
- **Local, after:** 434 passed, **34 skipped** — a rise of exactly **6**
- **With `DATABASE_URL` + `REQUIRE_POSTGRES=1`:** 468 passed, **0 skipped** — the operative gate, and it was actually run, not predicted

The six new skips are exactly the six new Postgres-gated tests:

1. `test_advisory_lock_is_exclusive_across_connections`
2. `test_concurrent_schema_init_from_two_processes_both_succeed`
3. `test_statement_timeout_bounds_a_slow_query`
4. `test_pgvector_search_path_lets_an_unqualified_cast_resolve`
5. `test_a_session_written_on_one_instance_resolves_on_a_cross_instance_read`
6. `test_concurrent_reads_run_past_the_pool_max_size`

No other skip appeared, and no previously-running test became a skip. `+19` passing locally: 5 in `test_service.py`, 6 in `test_db.py`, 8 in `test_store_contract.py` (3 `fails_closed` + 1 negative + 4 parametrised cases).

## What was proved against a real server, and what was not

Proved, on PostgreSQL 17.10 with pgvector in `public` (matching CI's `pgvector/pgvector:pg16` layout, where `extensions` does not exist and Postgres tolerates it in `search_path`): all 78 tests in `test_store_contract.py`, 0 skipped; the full suite at 468 passed, 0 skipped, twice, under both fixed and random ordering.

**Not proved, and not claimed:**

- **Supabase's actual `extensions` schema.** The `search_path` test asserts the setting took and that a `%s::vector` cast resolves. Both worlds pass because the setting is a literal string and a missing schema is tolerated — but a server that genuinely keeps pgvector in `extensions` has not been exercised. Plan 11-04 provisions the real DSN.
- **Fly's proxy routing two requests to two machines.** `cross_instance` proves the code path; a second machine adds a network boundary and a routing decision, not a new code path. Verified live in 11-05.
- **`-k fails_closed` is a property test, not a progress gate.** It passes against today's tree because the pins are env-driven. The gate that the pins are actually *set in production* is the stateless arm of `test_local_store_paths_live_under_the_mount`, written in 11-03 and armed by 11-05. Labelled as such in a comment in the file.
- **`concurrent_schema_init` is a regression test, not a lock test.** `CREATE ... IF NOT EXISTS` plus duplicate-object tolerance satisfies it with the advisory lock absent entirely. Said so in its docstring, pointing at `advisory_lock_is_exclusive` as the test that actually proves the lock.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The pooled reconnect contract was structurally unreachable**
- **Found during:** Task 2, before writing a line of it — the mechanism was probed against a fake pool first
- **Issue:** `cursor()`'s retry arm can only fire on a checkout failure. Under a pool the connection dies mid-statement, and the retry produced `RuntimeError: generator didn't stop after throw()` instead of reconnecting. `db.py`'s module docstring promised reconnection that could not happen.
- **Fix:** `ExitStack` so `cursor()` yields once; statement-level retry in `_read()` for `fetchone`/`fetchall`; writes deliberately excluded as at-least-once. Docstrings corrected.
- **Files modified:** `src/research_agent/db.py`, `tests/test_db.py` (3 tests, no server needed)
- **Commit:** `6e05954`

**2. [Rule 1 — Bug] The SQLSTATE retry rule was wrong in the one case that mattered**
- **Found during:** Task 3, on the first real-server run
- **Issue:** `AdminShutdown` (57P01) is server-reported but its connection is gone, so a "SQLSTATE means alive" rule refused to retry the exact failure the test simulates.
- **Fix:** `_connection_was_lost()` — SQLSTATE `None`, class `08`, or `57P01/02/03`. Six parametrised cases in `tests/test_db.py` pin both directions.
- **Files modified:** `src/research_agent/db.py`, `tests/test_db.py`
- **Commit:** `82f074b`

**3. [Rule 1 — Bug] One retry could not outlast a mass termination**
- **Found during:** Task 3, on the second real-server run
- **Issue:** A provider kills every idle connection, so the retry drew another dead one.
- **Fix:** `pool.check()` on the failure path only, with a comment distinguishing it from the `check=` callback 11-01 rejected. `FakePool.check()` records the call and a test asserts it.
- **Files modified:** `src/research_agent/db.py`, `tests/test_db.py`
- **Commit:** `82f074b`

**4. [Rule 3 — Blocking] Two acceptance greps tripped on my own explanatory prose**
- **Found during:** Task 2
- **Issue:** The comments explaining *why* `store.db._conn` and the `(?i)connect` string match were removed contained those literal tokens, so both greps returned 1 rather than 0. Exactly the tension 11-01 recorded as its Deviation 1.
- **Fix:** Reworded both to describe the removed construct without spelling it — "the private connection attribute the pool replaced", "pattern-matched the word connect case-insensitively". Every reason survives.
- **Files modified:** `tests/test_store_contract.py`
- **Commit:** `95576e7`

**5. [Rule 3 — Blocking] A module-level probe executor would break the suite**
- **Found during:** Task 1
- **Issue:** Nine tests use `with TestClient(...)`, which runs `lifespan`. A single module-level executor shut down on the first exit makes every later `/health` raise `cannot schedule new futures after shutdown` — a failure that only appears under some orderings.
- **Fix:** `_probes()` builds lazily and `_shutdown_probes()` clears the slot, so the next `/health` rebuilds.
- **Files modified:** `src/research_agent/service.py`
- **Commit:** `b4208dc`

**6. [Rule 3 — Blocking] Fixture ordering silently undid the Postgres overrides**
- **Found during:** Task 1
- **Issue:** `make_client()` is a *factory* called inside the test body, and it installs its own SQLite overrides — so a fixture that set Postgres overrides at setup time was overwritten, and `/health` reported `ok`.
- **Fix:** The fixture yields an `install()` callable invoked after `make_client()`, with the reason in its docstring.
- **Files modified:** `tests/test_service.py`
- **Commit:** `b4208dc`

**7. [Rule 1 — Accuracy] A docstring claimed more than its test proved**
- **Found during:** Task 3 review
- **Issue:** `advisory_lock_is_exclusive`'s docstring said the test fails if `_apply_schema` splits its lock across `cursor()` calls. It does not — it exercises the primitive with explicit cursors, not `_apply_schema`.
- **Fix:** Corrected the docstring to name `test_schema_lock_single_connection` as the test that catches a split, *and* added an assertion that reproduces the split's signature directly: an unlock from a non-holding connection returns `False`.
- **Files modified:** `tests/test_store_contract.py`
- **Commit:** `82f074b`

---

**Total deviations:** 7 auto-fixed (3 bugs, 3 blocking, 1 accuracy)
**Impact on plan:** All three tasks completed as specified. The three `db.py` bugs are the interesting ones — none was in the plan's scope, all three sat directly under an assertion the plan required, and two were invisible without a real server.

## Environment Change — needs your attention

**Homebrew packages were installed on this machine:** `postgresql@17` and `pgvector`. Docker was unavailable and the plan's note was explicit that a green local run is not evidence for this phase, so a real server was built to run the gated suite. It found three bugs.

- The server instance used for testing ran on port **54329** with its data directory in the session scratchpad. It has been **stopped** and the data directory **deleted**.
- **No `brew services` entry was created** — nothing starts at login. `brew services list` shows `postgresql@17 none`.
- Homebrew's formula did create a default cluster at `/opt/homebrew/var/postgresql@17`, which was never started.

To remove it all: `brew uninstall pgvector postgresql@17 && rm -rf /opt/homebrew/var/postgresql@17`

Worth keeping if you want to run `REQUIRE_POSTGRES=1` locally before 11-04's real DSN lands.

## Issues Encountered

**The residual on `/health`, accepted and documented (T-11-27).** An abandoned probe outlives the response: `future.result(timeout=...)` stops us waiting, it cannot interrupt a thread blocked in libpq. The executor bounds its **workers**, not its work **queue**, so against a persistently hung peer abandoned probes accumulate as queued futures at roughly three per 30s check interval — the worker count does not cap them. `tcp_user_timeout` and the keepalive sequence are the reaping mechanism. The 9s ceiling is unaffected, because the deadline bounds *availability* rather than execution: a probe that cannot even be scheduled still returns at its deadline. `future.cancel()` was deliberately not added, so that the documented mechanism stays the true one.

**Writes still have no mid-statement retry.** A write on a connection killed in the last few minutes surfaces as `OperationalError` rather than transparently retrying. This is the deliberate choice, not an oversight: the client cannot distinguish "never arrived" from "committed, response lost", and `metrics.record` duplicating a run or `sessions.create` raising `UniqueViolation` over a row that exists are both worse than a clean error. `max_idle=300` and `max_lifetime=1800` already recycle connections before a provider's overnight cull reaches them, so the exposed window is small.

**`fly.toml` untouched**, as scoped — `git status --porcelain fly.toml` is empty. Topology is 11-03 and 11-05.

## Verification

- `.venv/bin/pytest` (bare) — **434 passed, 34 skipped**
- `DATABASE_URL=... REQUIRE_POSTGRES=1 .venv/bin/pytest` — **468 passed, 0 skipped**, run twice under different orderings
- `.venv/bin/ruff check .` — exits 0
- `git status --porcelain fly.toml` — empty
- Acceptance greps: `db._conn` 0, `match="(?i)connect"` 0, `pg_terminate_backend` 2, `skipif(not HAS_POSTGRES` 10, `tests/conftest.py` absent, `HEALTH_PROBE_BUDGET` 4, `close_all_pools` 2, `FLY_MACHINE_ID` 2
- `-k fails_closed` selects 3; each of the six new tests is selectable by its plan-specified `-k`
- `test_postgres_really_ran_when_ci_said_it_would` byte-identical — no removed line in the diff matches its name

## User Setup Required

None for this plan. Optionally uninstall the Homebrew Postgres above. `DATABASE_URL` provisioning is 11-04.

## Next Phase Readiness

Ready for 11-03, which must:

1. Guard the new topology in `tests/test_deploy_config.py`, including the stateless arm of `test_local_store_paths_live_under_the_mount` — the real gate that `SESSION_BACKEND`/`METRICS_BACKEND`/`VECTOR_STORE` are pinned in production, which `-k fails_closed` deliberately does not prove.
2. Note for 11-05 Task 4: the skip-count invariant in `11-VALIDATION.md` needs amending from 28 to 34, with the six test names above as the justification.
3. `HEALTH_PROBE_BUDGET` is a new tunable with a 3.0s default and no `fly.toml` entry. It does not need one — the default is the intended production value — but 11-05 should confirm the 9s ceiling against the real check timeout in `fly.toml`.

## Self-Check: PASSED

All five modified files present. All four task commits resolve: `b4208dc`, `6e05954`, `95576e7`, `82f074b`.

---
*Phase: 11-multi-machine-state-and-pooled-postgres*
*Completed: 2026-08-05*
