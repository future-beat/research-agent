---
phase: 11
slug: multi-machine-state-and-pooled-postgres
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

This is the first v1.1 phase that changes **production code and infrastructure**. Unlike Phase 10,
the suite is the primary evidence — but three claims are only provable against a real Postgres
(CI has one) and one is only provable live (two machines, one session).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml`, `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` — `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Quick run command** | `.venv/bin/pytest tests/test_store_contract.py tests/test_deploy_config.py` |
| **Full suite command** | `.venv/bin/pytest` (bare — `addopts = "-q"` makes `-q` into `-qq` and hides counts) |
| **Estimated runtime** | ~11 seconds local |

**Baseline entering this phase: 388 passed, 28 skipped locally; 392 passed, 0 skipped in CI.**
The 28 local skips are `tests/test_store_contract.py` (27 need `DATABASE_URL`, 1 needs
`REQUIRE_POSTGRES`). Unlike Phase 10 these numbers **are expected to move** — this phase adds
tests. What must NOT happen is the skip count rising, which would mean Postgres coverage was
quietly disarmed.

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

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| TBD | TBD | 1 | REQ-connection-pool | `PoolTimeout` is NOT treated as a retryable `OperationalError` — it subclasses it, so a naive port doubles every timeout | unit | `pytest tests/ -k pool_timeout_not_retried` | ⬜ pending |
| TBD | TBD | 1 | REQ-connection-pool | Pool has configurable min/max size via env, defaults `min_size=1 max_size=5` | unit | `pytest tests/ -k pool_sizing_configurable` | ⬜ pending |
| TBD | TBD | 1 | REQ-connection-pool | `prepare_threshold=None` is set — psycopg's default of 5 breaks on the **sixth** execution behind a transaction pooler, i.e. in production, not in smoke tests | unit | `pytest tests/ -k prepare_threshold_disabled` | ⬜ pending |
| TBD | TBD | 1 | REQ-connection-pool | Reconnect-on-failure survives the port | unit | `pytest tests/ -k reconnect` | ⬜ pending |
| TBD | TBD | 1 | REQ-connection-pool | **No DDL at construction time** (SC-4) still holds — lazy schema application preserved | unit | `pytest tests/ -k no_ddl_at_construction` | ⬜ pending |
| TBD | TBD | 1 | REQ-connection-pool | ONE shared pool per machine, not three. Each store currently builds its own `db.Database` | unit | `pytest tests/ -k single_shared_pool` | ⬜ pending |
| TBD | TBD | 1 | REQ-connection-pool | Pool disposal does not break the other holders — `service.lifespan` closes 2 of 3 `Database` objects and never closes `graph.memory()`'s | unit | `pytest tests/ -k pool_disposal` | ⬜ pending |
| TBD | TBD | 2 | REQ-multi-machine-state | Concurrent `CREATE ... IF NOT EXISTS` from two machines booting against an empty database is serialised (`pg_advisory_lock`) | integration (real PG) | `pytest tests/ -k concurrent_schema_init` | ⬜ pending |
| TBD | TBD | 2 | REQ-multi-machine-state | pgvector casts resolve — Supabase installs the extension into the `extensions` schema, so unqualified `::vector` needs `search_path` set via the pool's `configure` callback | integration (real PG) | `pytest tests/ -k pgvector_search_path` | ⬜ pending |
| TBD | TBD | 2 | REQ-multi-machine-state | The byte-identical cross-backend metrics assertion still passes (SC-5) | integration (real PG) | `pytest tests/test_store_contract.py` | ⬜ pending |
| TBD | TBD | 2 | REQ-multi-machine-state | `tests/test_store_contract.py:497` — `pytest.raises(Exception, match="(?i)connect")` still matches. `PoolTimeout`'s message is "couldn't get a connection after N sec" | integration (real PG) | `pytest tests/test_store_contract.py -k connect` | ⬜ pending |
| TBD | TBD | 2 | REQ-multi-machine-state | `/health` completes inside Fly's 15s check budget. **Pre-existing defect:** two 3s connect attempts × three probes = up to 18s today | unit (timing) | `pytest tests/ -k health_within_budget` | ⬜ pending |
| TBD | TBD | 3 | REQ-multi-machine-state | `test_deploy_config.py` guards the NEW topology. Two guards currently `pytest.skip()` when there is no mount, so removing `[[mounts]]` silently disarms them and CI stays green — invert both into two-armed assertions (SC-5) | unit | `pytest tests/test_deploy_config.py` | ⬜ pending |
| TBD | TBD | 3 | REQ-multi-machine-state | `SESSION_DB_PATH`, `METRICS_DB_PATH`, `VECTOR_STORE_PATH` are gone from `fly.toml [env]` — left in place, a `DATABASE_URL` outage silently falls back to per-machine ephemeral SQLite | config gate | `grep -c 'SESSION_DB_PATH\|METRICS_DB_PATH\|VECTOR_STORE_PATH' fly.toml` returns 0 | ⬜ pending |
| TBD | TBD | 3 | REQ-multi-machine-state | `[[mounts]]` gone and `min_machines_running` ≥ 2 (SC-2) | config gate | `grep -c '\[\[mounts\]\]' fly.toml` returns 0 | ⬜ pending |
| TBD | TBD | 3 | — | `fly.toml`'s "Going stateless" runbook no longer documents the unsupported `fly postgres create` | grep gate | `grep -c 'fly postgres create' fly.toml` returns 0 | ⬜ pending |
| TBD | TBD | 3 | REQ-multi-machine-state | `PG_CONNECT_TIMEOUT` semantics documented for the pooled case (SC-6) | grep gate | `grep -c 'PG_CONNECT_TIMEOUT' docs/OPERATIONS.md` ≥ 1 | ⬜ pending |
| TBD | TBD | 4 | REQ-multi-machine-state | **SC-3 live:** a session created against one machine resolves identically from another | manual | see Manual-Only Verifications | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `psycopg-pool==3.3.1` added to `pyproject.toml`. It is versioned independently of
      `psycopg`, so pin it explicitly rather than relying on the `[pool]` extra.
- [ ] New test module(s) for pool behaviour, following the repo convention — shared fakes in
      the owning module, **no `conftest.py`**.
- [ ] The real-Postgres rows above need `DATABASE_URL`; CI already provides one. Locally they
      skip. **The skip count must not rise above 28** — a rise means Postgres coverage was
      disarmed rather than extended.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC-3: cross-machine session resolution | REQ-multi-machine-state | Needs two live Fly machines and a real external database; unprovable in-process | 1. `fly scale count 2 -a research-agent` 2. Create a session via `POST /research` 3. Fetch `GET /sessions/{id}` repeatedly until both machines have served it — confirm identical results, no 404 4. Record the `FLY_MACHINE_ID` of each responder as the evidence |
| Latency budget | REQ-multi-machine-state | Fly-syd → Supabase ap-southeast-2 latency is unmeasured | Measure during cutover and record the number. If a single store probe exceeds ~1s, the `/health` arithmetic must be re-done before scaling |

**Recommendation carried from research:** expose `FLY_MACHINE_ID` in `/health`. Without it, SC-3
is not demonstrable to a stranger — you cannot tell which machine answered.

---

## Cutover Safety

Every intermediate state must be safe, and the order is load-bearing:

1. Provision Supabase, enable pgvector, note the **session-mode pooler** host
   (`aws-<region>.pooler.supabase.com:5432` — IPv4; the direct endpoint is IPv6-only on free)
2. `fly secrets set DATABASE_URL=... -a research-agent` — **`sslmode=require`**
3. `fly deploy` — stores move to Postgres while the volume is still mounted (reversible)
4. Verify `/health` reports Postgres-backed stores and stays inside the budget
5. Remove `[[mounts]]` and the three `*_DB_PATH` env vars, redeploy
6. `fly scale count 2`
7. Verify SC-3 live

**Keep the volume.** Detaching is reversible; destroying is not. Steps 1–4 are reversible; step 5
is the point of no return for per-machine state.

---

## Validation Sign-Off

- [ ] Every criterion above has a runnable gate
- [ ] Local skip count still **28** — Postgres coverage extended, not disarmed
- [ ] CI green with a real Postgres
- [ ] `.venv/bin/ruff check .` clean
- [ ] SC-3 verified live with two machine IDs recorded
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
