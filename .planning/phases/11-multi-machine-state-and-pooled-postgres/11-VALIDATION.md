---
phase: 11
slug: multi-machine-state-and-pooled-postgres
status: blocked
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-05
reconciled: 2026-08-05
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

This is the first v1.1 phase that changes **production code and infrastructure**. Unlike Phase 10,
the suite is the primary evidence — but three claims are only provable against a real Postgres
(CI has one) and one is only provable live (two machines, one session).

**Reconciled 2026-08-05 by plan 11-05 Task 4.** This file was written before the plans existed and
had drifted four ways: every Task ID was an unfilled placeholder, the Wave column stopped at 4 while the plans run
1–5, two config gates counted comment and prose text, one gate was vacuous, three criteria asserted
mechanisms the phase deliberately stopped using, and the skip-count invariant was superseded.
All six are corrected below. No Criterion or Automated Command was rewritten *after* its gate had
been run — the two config-gate substitutions and the SC-6 substitution were all made before the
corresponding gate ran for the first time, which is recorded per row.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml`, `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` — `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Quick run command** | `.venv/bin/pytest tests/test_store_contract.py tests/test_deploy_config.py` |
| **Full suite command** | `.venv/bin/pytest` (bare — `addopts = "-q"` makes `-q` into `-qq` and hides counts) |
| **Estimated runtime** | ~23 seconds local |

**Baseline entering this phase: 388 passed, 28 skipped locally; 392 passed, 0 skipped in CI.**
The 28 local skips were `tests/test_store_contract.py` (27 needing `DATABASE_URL`, 1 needing
`REQUIRE_POSTGRES`). Unlike Phase 10 these numbers **are expected to move** — this phase adds
tests. See § The skip-count amendment for what replaced the original invariant.

---

## Sampling Rate

- **After every task commit:** the task's own test selector
- **After every plan wave:** bare `.venv/bin/pytest` plus `.venv/bin/ruff check .`
- **Before `/gsd:verify-work`:** full suite green, CI green with real Postgres, live cutover verified
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

Task IDs assigned by the planner. Every row maps to a real task; no row may be dropped, and no
Criterion or Automated Command may be rewritten after the gate has been run.

Wave mapping is one plan per wave: 11-01 → 1, 11-02 → 2, 11-03 → 3, 11-04 → 4, 11-05 → 5. Two
kinds of row moved during reconciliation: the `[[mounts]]` and `*_DB_PATH` config gates are
executed by **11-05 Task 1** (wave 5), not wave 3, because the topology is not touched until the
database is proven live; and the SC-3 live row is **11-05 Task 3** (wave 5), not wave 4.

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| 11-01-T3 | 11-01 | 1 | REQ-connection-pool | `PoolTimeout` is NOT treated as a retryable `OperationalError` — it subclasses it, so a naive port doubles every timeout | unit | `pytest tests/ -k pool_timeout_not_retried` | ✅ green |
| 11-01-T1 | 11-01 | 1 | REQ-connection-pool | Pool has configurable min/max size via env, defaults `min_size=1 max_size=5` | unit | `pytest tests/ -k pool_sizing_configurable` | ✅ green |
| 11-01-T1 | 11-01 | 1 | REQ-connection-pool | `prepare_threshold=None` is set — psycopg's default of 5 breaks on the **sixth** execution behind a transaction pooler, i.e. in production, not in smoke tests | unit | `pytest tests/ -k prepare_threshold_disabled` | ✅ green |
| 11-01-T2 | 11-01 | 1 | REQ-connection-pool | Reconnect-on-failure survives the port | unit | `pytest tests/ -k reconnect` | ✅ green |
| 11-01-T3 | 11-01 | 1 | REQ-connection-pool | **No DDL at construction time** (SC-4) still holds — lazy schema application preserved | unit | `pytest tests/ -k no_ddl_at_construction` | ✅ green |
| 11-01-T2 | 11-01 | 1 | REQ-connection-pool | ONE shared pool per machine, not three. Each store previously built its own `db.Database` | unit | `pytest tests/ -k single_shared_pool` | ✅ green |
| 11-01-T2 | 11-01 | 1 | REQ-connection-pool | Pool disposal does not break the other holders — `service.lifespan` closed 2 of 3 `Database` objects and never closed `graph.memory()`'s | unit | `pytest tests/ -k pool_disposal` | ✅ green |
| 11-02-T3 | 11-02 | 2 | REQ-multi-machine-state | Concurrent `CREATE ... IF NOT EXISTS` from two machines booting against an empty database is serialised (`pg_advisory_lock`) | integration (real PG) | `pytest tests/ -k concurrent_schema_init` | ✅ green |
| 11-02-T3 | 11-02 | 2 | REQ-multi-machine-state | The advisory lock is genuinely exclusive across two separate connections — a lock that does not block is not a lock | integration (real PG) | `pytest tests/ -k advisory_lock_is_exclusive` | ✅ green |
| 11-02-T3 | 11-02 | 2 | REQ-multi-machine-state | `statement_timeout` bounds a slow query at the server, so a hung statement cannot outlive the probe budget | integration (real PG) | `pytest tests/ -k statement_timeout_bounds_a_slow_query` | ✅ green |
| 11-02-T3 | 11-02 | 2 | REQ-multi-machine-state | pgvector casts resolve — Supabase installs the extension into the `extensions` schema, so unqualified `::vector` needs `search_path` set via the pool's `configure` callback. **See § Wave 1's search_path rationale, corrected** — this is insurance, not a fix for an observed break | integration (real PG) | `pytest tests/ -k pgvector_search_path` | ✅ green |
| 11-02-T3 | 11-02 | 2 | REQ-multi-machine-state | Concurrent reads exceeding `max_size` queue on checkout rather than opening an unbounded number of connections | integration (real PG) | `pytest tests/ -k concurrent_reads_run_past_the_pool_max_size` | ✅ green |
| 11-02-T2 | 11-02 | 2 | REQ-multi-machine-state | The byte-identical cross-backend metrics assertion still passes (SC-5) | integration (real PG) | `pytest tests/test_store_contract.py` | ✅ green |
| 11-02-T2 | 11-02 | 2 | REQ-multi-machine-state | **Criterion rewritten during reconciliation, before this row was ever marked.** Was: *"`pytest.raises(Exception, match="(?i)connect")` still matches"*. 11-02 Task 2 **deleted** that string-match in favour of a type-based assertion, and the old `-k connect` selector would still have collected `test_the_connection_recovers_from_being_dropped` and gone green over a criterion that no longer exists. Now: an unreachable DSN raises `psycopg.OperationalError` (or a subclass) by **type**, not by message text | integration (real PG) | `pytest tests/test_store_contract.py -k unreachable_dsn_raises` | ✅ green |
| 11-02-T2 | 11-02 | 2 | REQ-multi-machine-state | With no `DATABASE_URL`, each Postgres-pinned backend raises `RuntimeError` naming `DATABASE_URL` at store construction rather than falling back to SQLite/JSON | unit | `pytest tests/ -k fails_closed` | ✅ green |
| 11-02-T1 | 11-02 | 2 | REQ-multi-machine-state | **Row split during reconciliation.** *Cold-pool path only:* `/health` completes inside Fly's 15s check when the pool is empty and the database unreachable — 3 × `PG_POOL_TIMEOUT` ≈ 6s. 11-02 Task 1 narrowed this test to exactly that case | unit (timing) | `pytest tests/ -k health_within_budget` | ✅ green |
| 11-02-T1 | 11-02 | 2 | REQ-multi-machine-state | **Row split during reconciliation.** *General ceiling, and the number that matters:* a per-probe wall-clock deadline bounds `/health` at 3 × `HEALTH_PROBE_BUDGET` = 9s whether the pool is cold, warm or partitioned. The cold-pool row above cannot cover a warm pool holding a connection to a peer that has gone away — checkout returns instantly and then blocks on a socket. Measured 0.32s against a store that never answers, versus 31.4s with the deadline removed | unit (timing) | `pytest tests/ -k health_probe_deadline` | ✅ green |
| 11-03-T1 | 11-03 | 3 | REQ-multi-machine-state | `test_deploy_config.py` guards the NEW topology. Two guards previously `pytest.skip()`d when there was no mount, so removing `[[mounts]]` would silently disarm them and CI would stay green — both are now two-armed assertions (SC-5) | unit | `pytest tests/test_deploy_config.py` | ✅ green |
| 11-03-T2 | 11-03 | 3 | — | `fly.toml`'s "Going stateless" runbook no longer documents the unsupported `fly postgres create` | grep gate | `grep -c 'fly postgres create' fly.toml` returns 0 | ✅ green |
| 11-03-T3 | 11-03 | 3 | REQ-multi-machine-state | **Gate replaced during reconciliation, before it had been run.** The original — `grep -c 'PG_CONNECT_TIMEOUT' docs/OPERATIONS.md ≥ 1` — already returned `1` on the untouched tree, so it would have passed with no work done. Replaced with 11-03 Task 3's three falsifiable parts: (a) `grep -v '^|' docs/OPERATIONS.md \| grep -c 'PG_POOL_TIMEOUT'` ≥ 1, which excludes table rows so only prose satisfies it; (b) `PG_CONNECT_TIMEOUT`'s old row text *"Seconds before a connection attempt gives up"* has 0 occurrences, proving the row was rewritten; (c) at least one paragraph names `PG_CONNECT_TIMEOUT`, `PG_POOL_TIMEOUT` and `HEALTH_PROBE_BUDGET` together, which a table cannot satisfy (SC-6) | grep gate (3 parts) | see criterion — observed 2 / 0 / 2 | ✅ green |
| 11-05-T1 | 11-05 | 5 | REQ-multi-machine-state | **Gate replaced during reconciliation, before it had been run.** Was `grep -c 'SESSION_DB_PATH\|METRICS_DB_PATH\|VECTOR_STORE_PATH' fly.toml returns 0`, which counts comments and prose — and 11-03 Task 2 added runbook prose naming those very strings, so it would have passed over an unchanged topology. The three vars are gone from `[env]` | config gate | `grep -v '^[[:space:]]*#' fly.toml \| grep -c 'SESSION_DB_PATH\|METRICS_DB_PATH\|VECTOR_STORE_PATH'` returns 0 | ✅ green |
| 11-05-T1 | 11-05 | 5 | REQ-multi-machine-state | **Gate replaced during reconciliation, before it had been run.** Was `grep -c '\[\[mounts\]\]' fly.toml returns 0`, which counts the runbook footer's prose. `[[mounts]]` is gone from the parsed config and `min_machines_running` ≥ 2 (SC-2, config half) | config gate | `grep -v '^[[:space:]]*#' fly.toml \| grep -c '\[\[mounts\]\]'` returns 0 | ✅ green |
| 11-05-T1 | 11-05 | 5 | REQ-multi-machine-state | **Criterion rewritten during reconciliation, before this row was ever marked.** The old text claimed removing the three `*_DB_PATH` vars is what prevents the silent SQLite fallback. That mechanism was corrected away — see `T-11-21`. `sessions.py:43` has a module-dir default and `default_backend()` returns `sqlite` whenever `postgres_configured()` is false, so removal alone changes nothing. The real mechanism is the pins: `SESSION_BACKEND='postgres'`, `METRICS_BACKEND='postgres'`, `VECTOR_STORE='pgvector'`. **This `tomllib` form is the authoritative version of all three config rows above**, because it reads the parsed table rather than the file text — `grep -c 'VECTOR_STORE' fly.toml` matches `VECTOR_STORE_PATH` and cannot tell the two apart | config gate | `python3 -c "import tomllib;f=tomllib.load(open('fly.toml','rb'));e=f['env'];assert not f.get('mounts');assert f['http_service']['min_machines_running']>=2;assert not {'SESSION_DB_PATH','METRICS_DB_PATH','VECTOR_STORE_PATH'} & set(e);assert e['SESSION_BACKEND']=='postgres';assert e['METRICS_BACKEND']=='postgres';assert e['VECTOR_STORE']=='pgvector'"` | ✅ green |
| 11-05-T1 | 11-05 | 5 | REQ-multi-machine-state | The fail-closed mechanism is real at runtime, not just declared in config: with `DATABASE_URL` absent and `SESSION_BACKEND=postgres`, store construction exits non-zero with a `RuntimeError` naming `DATABASE_URL` | spot check | `env -u DATABASE_URL SESSION_BACKEND=postgres .venv/bin/python -c "from research_agent.sessions import get_session_store; get_session_store()"` exits 1 | ✅ green |
| 11-05-T2 | 11-05 | 5 | REQ-multi-machine-state | **SC-2 live half:** two machines running in `syd`, both `started`, neither holding a volume, and `agent_data` surviving unattached | manual | `fly machines list -a research-agent`; `fly volumes list -a research-agent` | 🚫 blocked |
| 11-05-T3 | 11-05 | 5 | REQ-multi-machine-state | **SC-3 live:** a session created against one machine resolves identically from another, over HTTP, with both machine ids recorded | manual | see Manual-Only Verifications | 🚫 blocked |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 🚫 blocked (cannot be run; reason recorded)*

### Anti-pattern guards — not progress gates

These rows assert that something was **not** introduced. Every one of them passes against the
tree as it stood *before* any work in this phase, so a green here is evidence that nothing
regressed — **not** evidence that work was done. A reader counting green ticks must not mistake
them for progress. Each is an anti-pattern guard by construction.

| Task ID | Plan | Wave | Criterion | Automated Command | Expected | Status |
|---------|------|------|-----------|-------------------|----------|--------|
| 11-01-T2 | 11-01 | 1 | No `pool.wait()` at construction — it would make pool creation block on the database and reintroduce I/O at import time | `grep -c 'pool.wait()' src/research_agent/db.py` | `0` | ✅ green |
| 11-01-T3 | 11-01 | 1 | No `pg_advisory_xact_lock` — the transaction-scoped variant releases at commit, which is the wrong lifetime for lazy DDL | `grep -c 'pg_advisory_xact_lock' src/research_agent/db.py` | `0` | ✅ green |
| 11-01-T2 | 11-01 | 1 | No `check_connection` callback — it adds a round trip to every checkout for a failure mode the retry already covers | `grep -c 'check_connection' src/research_agent/db.py` | `0` | ✅ green |
| 11-05-T1 | 11-05 | 5 | `fly volumes destroy` is never *instructed*. **Corrected during reconciliation:** 11-05's plan asserted this grep returns `0` across `fly.toml`, `docs/OPERATIONS.md` and `README.md`. It does not — it returns `1`, `1`, `0`. Both occurrences are **prohibitions** written by 11-03 Task 2/3 ("`fly volumes destroy` is not part of this procedure at any point"), and deleting them to satisfy a `0` would remove the very warning that mitigates `T-11-20`. The correct criterion is that no occurrence is an instruction and the command was never run | `grep -c 'fly volumes destroy' fly.toml docs/OPERATIONS.md README.md` | `1 / 1 / 0`, all prohibitive | ✅ green |

---

## Wave 0 Requirements

- [x] `psycopg-pool==3.3.1` added to `pyproject.toml`. It is versioned independently of
      `psycopg`, so pin it explicitly rather than relying on the `[pool]` extra.
- [x] New test module(s) for pool behaviour, following the repo convention — shared fakes in
      the owning module, **no `conftest.py`**.
- [x] The real-Postgres rows above need `DATABASE_URL`; CI already provides one. Locally they
      skip. See § The skip-count amendment for the operative invariant.

### The skip-count amendment

The original invariant — *the local skip count is capped at the old figure of 28* — is **superseded**, and
the amendment is recorded here rather than only inside 11-02's plan body, because this file is the
validation contract and a stale invariant here means nothing can be marked green honestly.

Plan 11-02 adds six Postgres-gated tests that skip locally **by design**, so the local figure
becomes **34**. A flat local count would have meant the new coverage was never written.

The operative gate is 11-02's two clauses, and the first is the real guard:

1. **CI, under `DATABASE_URL` + `REQUIRE_POSTGRES=1`: `0` skipped.** Unchanged, and the clause that
   actually prevents Postgres coverage being disarmed. Measured: **468 passed, 0 skipped**, run
   twice under different orderings.
2. **Locally, the count rises by exactly 6, each named.** Measured: 415 passed / 28 skipped →
   434 passed / **34** skipped. The six, and no others, are:
   `test_advisory_lock_is_exclusive_across_connections`,
   `test_concurrent_schema_init_from_two_processes_both_succeed`,
   `test_statement_timeout_bounds_a_slow_query`,
   `test_pgvector_search_path_lets_an_unqualified_cast_resolve`,
   `test_a_session_written_on_one_instance_resolves_on_a_cross_instance_read`,
   `test_concurrent_reads_run_past_the_pool_max_size`.

No previously-running test became a skip. Final local figure after wave 3 and wave 5's config
change: **436 passed, 34 skipped** — passing rose by 2 (11-03's runbook and `DATABASE_URL`
guards); the skip count held at 34, as it must, since neither plan adds a Postgres-gated test.

---

## Wave 1's `search_path` rationale, corrected

11-01 added a pool `configure` callback setting `search_path` so that `memory.py`'s unqualified
`::vector` casts would resolve on a provider that keeps pgvector outside `public`. 11-04 measured
the real server and found:

```
default search_path : "$user", public, extensions
unqualified ::vector on DEFAULT search_path       : RESOLVES
unqualified ::vector with CONFIGURED search_path  : RESOLVES
```

Supabase's default `search_path` **already contains `extensions`**, so the casts would have
resolved without the callback. The callback stays — explicit beats inheriting a provider default
that Supabase can change without telling us, and it is what makes the code portable to a provider
whose default omits `extensions`. But the honest framing is **insurance that has not yet been
needed**, not a fix for an observed break. Nobody reading 11-01's rationale should conclude that
the cast was failing before.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC-3: cross-machine session resolution | REQ-multi-machine-state | Needs two live Fly machines and a real external database; unprovable in-process. 11-02's `test_a_session_written_on_one_instance_resolves_on_a_cross_instance_read` proves the *mechanism* in CI, but cannot prove the Fly proxy routes to two machines, that both hold the secret, or that neither holds a volume | 1. `fly scale count 2 -a research-agent` 2. Create a session against the live service and record the `machine` id that served it 3. Read it back pinned to the other machine: `curl -H "fly-force-instance-id: <machine-B>" -H "X-Demo-Token: $SESSIONS_TOKEN" https://research-agent.fly.dev/sessions/<id>` — `fly-force-instance-id` has no fallback if the machine is unavailable, which is what makes this proof rather than suggestion 4. Confirm the session comes back, not a 404, with content matching what machine A wrote; repeat pinned to A for symmetry 5. Record **both machine ids and the session id** |
| Latency budget | REQ-multi-machine-state | Fly-syd → Supabase ap-southeast-2 latency is unmeasured | Measure during cutover and record the number. If a single store probe exceeds ~1s, the `/health` arithmetic must be re-done before scaling. **Measured (11-04):** connect+TLS 119.2 ms, query p50 2.73 ms, p95 6.37 ms; worst store probe 6.90 ms against a 3000 ms budget — about 435× headroom |

**Recommendation carried from research, now implemented:** expose `FLY_MACHINE_ID` in `/health`.
Without it, SC-3 is not demonstrable to a stranger — you cannot tell which machine answered.

---

## Cutover Safety

Every intermediate state must be safe, and the order is load-bearing:

1. Provision Supabase, enable pgvector, note the **session-mode pooler** host
   (`aws-<region>.pooler.supabase.com:5432` — IPv4; the direct endpoint is IPv6-only on free)
2. `fly secrets set DATABASE_URL=... -a research-agent` — **`sslmode=require`**
3. `fly deploy` — stores move to Postgres while the volume is still mounted (reversible)
4. Verify `/health` reports Postgres-backed stores and stays inside the budget
5. Remove `[[mounts]]` and the three `*_DB_PATH` env vars, **add the three backend pins**, redeploy
6. `fly scale count 2`
7. Verify SC-3 live

Steps 1–4 are complete (11-04, release v5/v6). Step 5's **repository half** is complete (11-05
Task 1); its **deploy half** is blocked — see § Sign-off. Steps 6 and 7 are not started.

**Keep the volume.** Detaching is reversible; destroying is not. Steps 1–4 are reversible; step 5
is the point of no return for per-machine state. Note that the documented rollback
(`fly secrets unset DATABASE_URL`) has **never been exercised** — everything it depends on is
verified, but it is the documented escape hatch, not a proven one.

---

## Validation Sign-Off

- [x] Every criterion above has a runnable gate
- [x] Local skip count is **34**, up by exactly the six named Postgres-gated tests; CI reports 0 skipped
- [x] CI green with a real Postgres — 468 passed, 0 skipped
- [x] `.venv/bin/ruff check .` clean
- [ ] SC-3 verified live with two machine IDs recorded — **BLOCKED**
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** withheld. Every repository-side gate is green and every row has a runnable command,
which is what `nyquist_compliant: true` records. The phase's headline claim (SC-3) is **not**
proven: `fly deploy` cannot complete the mount-removal release non-interactively on flyctl
v0.4.78, so production still runs one machine on release v6 with the volume attached. Sign-off
needs the operator to land that deploy. See `11-05-SUMMARY.md` § The blocker.
