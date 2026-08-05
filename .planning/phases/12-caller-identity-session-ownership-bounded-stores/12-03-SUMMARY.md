---
phase: 12-caller-identity-session-ownership-bounded-stores
plan: 03
subsystem: limits
tags: [rate-limit, spend-cap, reservation, advisory-lock, postgres, identity, sse]

# Dependency graph
requires:
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 01
    provides: "Database.transaction() and CAP_LOCK_KEY -- the real transaction on the autocommit pool that pg_advisory_xact_lock needs"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 02
    provides: "request.state.identity on every request, and the make_client/mint_cookie test seam"
provides:
  - "LimitsStore ABC + InMemoryLimits + PostgresLimits, with get_limits_store() defaulting on DATABASE_URL like sessions and metrics"
  - "The rate window keys on caller identity, not the client address -- TRUST_FORWARDED_FOR is no longer load-bearing for fairness"
  - "Reservation-based daily cap: reserve_or_429 claims DEMO_RESERVED_RUN_USD before a run starts, settled to real cost at every terminal arm, with a 900s stale-reclaim backstop"
  - "app.state.limits + get_limits injection seam; guard() now token + rate only"
  - "The two gates that hold the in-handler reserve: parametrized four-route 429 + structural inspect.getsource invariant"
affects: [12-04, 12-05, 12-06, SC-2]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two halves of one store with deliberately different strictness: check_rate is one statement (fairness, a small overshoot is free), reserve is check-and-insert inside a transaction holding pg_advisory_xact_lock (money, a race costs the invoice)"
    - "Settle at the metrics.record choke points inside _execute/_stream, never in the handler's except -- _stream swallows the exception to terminate the SSE cleanly, so the handler's except never sees a failed stream"
    - "A structural source gate (inspect.getsource) standing in for the api_routes walker when the control cannot be a route dependency"
    - "Opportunistic sweeps every Nth call (SWEEP_EVERY=500) mirrored from RateLimiter into PostgresLimits for both tables"

key-files:
  created: []
  modified:
    - src/research_agent/limits.py
    - src/research_agent/service.py
    - tests/test_limits.py
    - tests/test_service.py
    - README.md

key-decisions:
  - "caller_identity() falls back to ONE SHARED bucket, never to client_ip: a shared bucket is more restrictive than the truth (the safe direction), while an address fallback would reinstate the forgeable key this phase removed -- and would do it exactly when the identity layer was broken."
  - "The cap left enforce() rather than gaining a run_id parameter there: a reservation needs state the guard cannot see, and a guard that half-enforces the cap is worse than one that visibly does not."
  - "reserve_or_429 raises synchronously inside the handler, before any StreamingResponse is constructed, so a capped caller gets a real 429 rather than a 200 whose body turns out to be an error event."
  - "settle() never raises. A failed settle must not turn a finished run into a 500 or truncate a stream that already delivered its result; RESERVATION_STALE_SECONDS makes the failure survivable, and the warning makes the leak visible."
  - "The four-route gate is doubled on purpose (behavioural 429 + structural source read) because reserve_or_429 is an in-handler call the api_routes walker cannot see -- the exact ADR-0006 shape, on the same /sessions routes that forgot a credential four times."
  - "README's 'rate-limited, not authenticated' line (~210) is still left to Wave 5; the falsified spend-cap limitation at ~208 is corrected here, by the wave that falsified it."

# Metrics
duration: 24min
completed: 2026-08-05
---

# Phase 12 Plan 03: Identity-keyed limits and a reservation-based spend cap Summary

**One-liner:** Rate limiting and the daily spend cap moved out of per-machine memory into a `LimitsStore` seam keyed on the signed identity, and the cap now counts in-flight runs by reserving `$0.20` per run inside a transaction holding `pg_advisory_xact_lock` — so two concurrent guards can no longer both pass, proven by a two-thread race against real Postgres.

## What was built

### Task 1 — the LimitsStore seam (commit fe50a83)

- `LimitsStore` ABC: `check_rate(identity, limit, window) -> (allowed, retry_after)`, `reserve(run_id, identity, est_usd, cap, spent_24h) -> bool`, `settle(run_id)`, `reservation_ids()`, and a concrete `close()` (the memory backend has nothing to release, and forcing an empty override is how you get a `close()` that does nothing by accident rather than on purpose).
- `InMemoryLimits` wraps the existing `RateLimiter` — now keyed on identity — plus a lock-guarded reservation dict that drops stale rows before summing. `PostgresLimits` creates `rate_hits(identity, ts)` + index and `run_reservations(run_id PK, identity, est_usd, created_at)` + index via the lazy advisory-locked `ensure_schema`.
- The two halves have deliberately different strictness, documented at the seam: `check_rate` is the single-statement `INSERT ... SELECT ... WHERE (SELECT COUNT(*)...) < limit RETURNING ts` (one round trip; the residual concurrent-insert overshoot is a fine trade for a fairness tool), while `reserve` runs `SELECT pg_advisory_xact_lock(CAP_LOCK_KEY)` then the conditional INSERT inside `db.transaction()` — because a bare conditional INSERT is **not** race-free under READ COMMITTED, where two guards each evaluate the WHERE against a snapshot excluding the other's uncommitted row.
- The process-global limiter is **gone**. It was what made "the rate limit" mean something different on each machine, and a module global is not something a request can be pointed away from.
- Both tables get opportunistic purges every 500th call, suppressed on failure — housekeeping never fails a request.

### Task 2 — module rewire (commit 9db9125, limits.py half)

- `DEMO_RESERVED_RUN_USD` (default 0.20, floor 0), sized on observation (~$0.15/run) rather than on `AGENT_MAX_RUN_COST_USD`'s $1.00, which would let only five runs at once against a $5 budget and turn the cap into a queue.
- `enforce(request, metrics, limits_store)` is now token → identity-rate. The cap left it for `reserve_or_429(limits_store, run_id, identity, metrics)`, which computes `spend_since(now-24h)`, reserves, and on refusal raises the 429 carrying **"Read-only endpoints still work."** verbatim with `Retry-After: 3600`. A cap of 0 short-circuits before the spend query, so disabling it costs no round trip.
- `client_ip` and `TRUST_FORWARDED_FOR` survive for logging with an explicit do-not-key-limits-on-this comment; `caller_identity()` is the new key, falling back to a shared `"anonymous"` bucket rather than to the address.
- `status()` is additive: all five original keys retained, `rate_limit_scope` and `reserved_run_usd` appended for the Wave 5 UI.

### Task 3 — service wiring and the two gates (commits 9db9125, 40d2de9)

- `lifespan` builds `app.state.limits = get_limits_store()`, logs the backend, and closes it before `db.close_all_pools()`. `get_limits(request)` is the single accessor, so one dependency override points the whole app at one store.
- All four spending handlers call `limits.reserve_or_429(...)` after the state build and before the run starts (`grep -c reserve_or_429 service.py` = 5: one import-side reference plus four call sites).
- `limits.settle(...)` sits immediately after **every** `metrics.record` in both `_execute` and `_stream` — success and `_failed_record`, four terminal arms. Never in the handler's `except`: `_stream` swallows its exception to terminate the SSE cleanly, so the handler's own `except` never runs on a failed stream.
- Gate (a) `test_all_spending_routes_reserve`, parametrized over `/research`, `/research/stream`, `/sessions/{id}/ask`, `/sessions/{id}/ask/stream`: each returns a real 429 containing the sentence, nothing billable ran, and both `GET /sessions` and `GET /sessions/{id}` still answer 200 while capped — the refusal's own claim, asserted.
- Gate (b) `test_every_spending_route_calls_reserve`: `api_routes(service.app)` filtered to the four paths, a non-vacuity floor of `len >= 4` asserted **before** the loop, then `"reserve_or_429" in inspect.getsource(route.endpoint)`.
- **Falsified, not assumed:** removing the reserve from `ask()` alone turned both gates red (the `[/sessions/{session_id}/ask]` case and the structural one); restored green.
- Settle is gated on all four arms against a recording store: `test_reservation_settles_on_the_success_arms`, `test_a_failed_run_settles_its_reservation`, `test_a_failed_stream_settles_its_reservation`, each asserting the reservation was actually taken (non-vacuity) before asserting it was released.

### Task 4 — real-Postgres concurrency (commit 7fb1c72)

- `test_cap_reservation_no_overshoot`: two threads, two independent `Database` handles on `_dsn_tagged` DSNs (separate pool connections, mirroring 11-02's schema-lock exclusivity shape), reserving distinct run_ids against a cap sized for exactly one. Asserts `sum(results) == 1` — a bare single-statement INSERT admits both and fails this.
- `test_postgres_reservation_settles_and_reclaims`: a settled row is absent; a row with `created_at` older than 900s does not count toward a fresh reserve and is purged.

### README (commit fd5267f)

This wave falsified the known-limitation entry "The demo spend cap counts completed runs only." Replaced with what is now true and what residual remains (900s stale-reclaim window, estimate accuracy). Test count 504 → 534.

## Verification record

| Gate | Baseline (measured 2026-08-05) | Result |
|------|-------------------------------|--------|
| `grep -c "class LimitsStore" limits.py` | 0 | **1** (+ `InMemoryLimits`, `PostgresLimits`) |
| `grep -c pg_advisory_xact_lock limits.py` | 0 | **3** |
| `grep -c CAP_LOCK_KEY limits.py` | 0 | **2** |
| `grep -c "def reserve_or_429" limits.py` | 0 | **1** |
| `grep -c DEMO_RESERVED_RUN_USD limits.py` | 0 | **3** |
| `grep -rc "Read-only endpoints still work" src tests` | 3 | **4** (limits.py 1, test_service.py 2, test_limits.py 1) — did not drop |
| `grep -c "app.state.limits\|get_limits" service.py` | 0 | **12** |
| `grep -c reserve_or_429 service.py` | 0 | **5** (≥4: four handlers + import) |
| `grep -c settle service.py` | 0 | **5** (≥2: four record points + import) |
| T-03-1 `pytest -k "rate_limit_per_identity or reserve or settle"` | — | 3 passed, 1 skipped (PG-gated) |
| T-03-2 `pytest -k "reads_survive_the_cap or status"` | — | 6 passed |
| T-03-3 `pytest test_service.py -k "all_spending_routes_reserve or every_spending_route_calls_reserve or reservation_settles_and_reclaims or cap"` | — | 7 passed |
| T-03-4 armed `pytest -k "cap_reservation_no_overshoot or reservation_settles_and_reclaims"` | — | 2 passed |
| `pytest tests/test_limits.py` armed | — | 54 passed |
| Full suite, plain | 467 passed / 37 skipped | **493 passed / 41 skipped** |
| Full suite, armed (`:54329`) | 503 passed / 1 skipped | **533 passed / 1 skipped** |
| ruff | clean | clean |

**Delta fully explained.** Collected 504 → 534, +30 in both arms. Plain gains +26 passed and +4 skipped; armed gains +30 passed. The four extra plain skips are exactly the Postgres-gated `test_limits.py` tests, each reporting `DATABASE_URL is not set` — the rate-window-persists and reservations-round-trip smokes from Task 1 plus the two-thread race and stale-reclaim from Task 4. A green plain run is therefore **not** evidence for Task 4; the armed run is.

## Deviations from Plan

**1. [Rule 1 — Falsified documentation] README known-limitation entry corrected**
- **Found during:** post-task review (README freshness is a per-phase deliverable; Waves 0 and 1 each did the same)
- **Issue:** line ~208 stated the spend cap counts completed runs only and that concurrency overshoots it — the exact defect this plan closes. Test count also read 504.
- **Fix:** the entry now describes the reservation mechanism and states the residual honestly (900s stale window, estimate accuracy) rather than deleting the limitation. Count 504 → 534.
- **Files modified:** README.md
- **Commit:** fd5267f
- Not a scope expansion: `README.md` was outside the plan's `files_modified`, but leaving a claim this wave disproved would have been a knowingly false document.

**2. [Mechanical] A named `rate_limit` dependency added alongside `guard`**
- `limits.check_rate_limit` needs the injected store, and FastAPI can only supply that to a parameter carrying a `Depends` default — which `check_rate_limit` deliberately does not carry, so it stays callable from plain unit tests. The thin `rate_limit()` wrapper in `service.py` bridges the two without pushing FastAPI types into `limits.py`.

Everything else executed as written.

## Threat Flags

None. Every row in the plan's register (T-12-03-01..06) is dispositioned `mitigate` and each is implemented and gated:

| Threat | Where it is closed |
|--------|--------------------|
| T-12-03-01 concurrency overshoot | `pg_advisory_xact_lock` in `PostgresLimits.reserve`; `test_cap_reservation_no_overshoot` |
| T-12-03-02 Sybil identities | the global cap survives untouched as the backstop; documented at the top of `limits.py` |
| T-12-03-03 crashed run pins the cap | `RESERVATION_STALE_SECONDS = 900` excluded from the sum + purged; settle on all four arms |
| T-12-03-04 reworded 429 | count held at 4 (≥ baseline 3); `test_reads_survive_the_cap` asserts the substring |
| T-12-03-05 IP key regression | rate table keyed on identity only; `caller_identity` falls back to a shared bucket, not the address; `test_the_rate_limit_keys_on_identity_not_the_address` |
| T-12-03-06 reserve dropped from a route | the doubled four-route gate, falsified by deleting `ask`'s reserve |

## Requirements

`REQ-demo-authentication` stays **Pending**, matching 12-02's reasoning: this plan delivers Criterion 2's machinery, but the requirement's text is only demonstrable on the deployed service, which is Wave 5 (12-06).

## Self-Check: PASSED

- `src/research_agent/limits.py`, `src/research_agent/service.py`, `tests/test_limits.py`, `tests/test_service.py`, `README.md` all exist and modified as claimed
- Commits fe50a83, 9db9125, 40d2de9, 7fb1c72, fd5267f all present on `gsd/phase-12-caller-identity`
