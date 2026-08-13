---
phase: 12-caller-identity-session-ownership-bounded-stores
plan: 04
subsystem: sessions
tags: [ownership, expiry, ttl, existence-oracle, dual-mode, structural-gate, adr-0006]

# Dependency graph
requires:
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 02
    provides: "request.state.identity on every request, and the make_client/mint_cookie test seam"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 03
    provides: "caller_identity() as the one place an identity is read, and the daily cap's move out of guard into reserve_or_429"
provides:
  - "sessions.owner on both backends, migrated lazily (idempotent ALTER under the advisory-locked Postgres DDL; PRAGMA table_info probe for SQLite)"
  - "Derived 7-day expiry from updated_at via SESSION_TTL_DAYS; Postgres compares against EXTRACT(EPOCH FROM now()) so two machines read one clock"
  - "Opportunistic sweep on create(); reads never renew updated_at"
  - "SessionStore.list(limit, owner=None) — the data path behind the dual-mode listing"
  - "limits.require_session_access: ('operator', None) or ('identity', id), never raises"
  - "service._require(store, id, owner, *, operator) — one 404 for missing, expired and foreign"
  - "The extended walker: per-route coverage, the ask routes' exclusion, and the router's own declaration"
affects: [12-05, 12-06, SC-3, SC-4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Derived expiry over a stored one: a second timestamp is a second thing to keep in sync, and append_turn already renews updated_at for free"
    - "Expiry evaluated inside the database (EXTRACT(EPOCH FROM now())) rather than in Python, so two machines cannot disagree about the cutoff"
    - "Refusal moved from 'do you hold the shared secret' to 'is this yours' — the second question has an answer for every caller, so the dependency stopped raising"
    - "One refusal shape at one choke point: _require is the only place a session can be refused, so missing/expired/foreign cannot drift apart into an oracle"
    - "A router-level dependency needs its OWN assertion once handlers also inject it: dependency_names() cannot tell the two sources apart"

key-files:
  created: []
  modified:
    - src/research_agent/sessions.py
    - src/research_agent/service.py
    - src/research_agent/limits.py
    - tests/test_store_contract.py
    - tests/test_service.py
    - tests/test_limits.py
    - README.md
    - docs/OPERATIONS.md
    - .env.example

key-decisions:
  - "404 for foreign AND expired, byte-identical to missing, asserted as an equality between two live responses rather than as two status codes — 403 would confirm that an id names a real session, and session ids travel in shared URLs"
  - "delete_session calls _require before store.delete: store.delete alone returns True/False and would have distinguished a real id from an invented one even while refusing both"
  - "The structural walker needed a THIRD assertion. Every handler injects require_session_access to read its value, so deleting the router-level dependency left the per-route check green — verified by mutation. sessions_router.dependencies is now asserted directly"
  - "The 10.5 401-block was rewritten rather than deleted: the property it protected (no existence oracle) survives with a stronger mechanism, and the tests now assert that instead of asserting the retired mechanism"
  - "The stale cap rationale 12-04 was sent to fix had already been corrected by 12-03; what was added is the missing forward reference to the behavioural gates that carry the real proof"

# Metrics
duration: 29min
completed: 2026-08-05
---

# Phase 12 Plan 04: Session ownership, derived expiry, and the operator dual-mode Summary

**One-liner:** A session now belongs to the identity that created it and stops resolving seven days after its last turn, `SESSIONS_TOKEN` turned from the visitor's credential into the operator's unscoped debugging view, and everyone else — foreign, expired or invented id alike — gets one 404 with one body.

## What was built

### Task 1 — owner and expiry in the store (commit 82af2cc)

- **Ownership, migrated lazily on both backends.** `POSTGRES_SCHEMA` gained `ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT ''` plus `CREATE INDEX IF NOT EXISTS sessions_owner (owner, updated_at DESC)`, which run inside the existing advisory-locked lazy DDL — so the two live rows migrate on the first post-deploy request with both machines serialised, no script and no downtime. SQLite has no `ADD COLUMN IF NOT EXISTS`, so `_add_owner_column()` probes `PRAGMA table_info(sessions)` first. The owner index is created **after** that probe, never inside `SQLITE_SCHEMA`: a pre-Phase-12 `sessions.db` already has the table, so the `CREATE TABLE IF NOT EXISTS` is a no-op there and an index over `owner` would run against a column that does not exist yet.
- **Expiry is derived, not stored.** `session_ttl_seconds()` reads `SESSION_TTL_DAYS` per call (default 7). `get`/`list` filter `updated_at > cutoff`; `create` sweeps `updated_at <= cutoff`. Postgres computes the cutoff from `EXTRACT(EPOCH FROM now())` — the database's own clock, so the two machines cannot disagree about what expired; SQLite is single-machine by construction and uses `time.time()`, with the contract suite pinning identical observable behaviour.
- **Reads never renew.** No UPDATE in `get` or `list`, stated as an invariant in the `SessionStore` docstring with the reason (a renewing read turns "7 days after last activity" into "7 days after last glance", and the table never shrinks).
- **Orphans need no special case.** Pre-Phase-12 rows land on `owner=''`; identities are 32-hex uuids, so that value matches no caller. They resolve for nobody immediately and are swept once past the seven-day line — claim-by-nobody-and-expire, as RESEARCH recommended.
- Four contract tests over **both** session backends: `expiry_lazy_and_reads_do_not_renew` (the renewal half asserted on a *live* session before the expiry half on an idle one; then the TTL widened to 30 days to prove the filter reads the setting rather than a hardcoded seven), `sweep_deletes_expired` (asserted on unfiltered `count()`, because against `get`/`list` a lazy filter alone looks identical to a sweep and only one of them bounds the table), `list_scopes_to_an_owner_and_none_is_unscoped` (including `owner=""` as a real value, never a wildcard), and `owner_round_trips_and_defaults_to_empty`.

### Task 2 — the access dependency, the 404 choke point, and the walker (commit b87a088)

- **`require_sessions_token` → `require_session_access`**, returning `("operator", None)` on a `SESSIONS_TOKEN` match and `("identity", id)` otherwise. It never raises. The fail-closed property **inverts**, and the docstring says so rather than leaving it to be discovered: an unset token used to mean nobody passes, because the token was the only thing between a stranger and someone else's research; it is no longer the only thing, so an unset token now closes the operator view and nothing else.
- **`_require(store, session_id, owner, *, operator=False)`** raises `HTTPException(404, f"No session {session_id!r}.")` when the session is missing, expired (already filtered to `None` by `store.get`, so it cannot accidentally acquire a different status code) or owned by someone else. One shape, one choke point.
- **Handlers:** `list_sessions` scopes to the caller or goes unscoped for the operator; `get_session`/`get_trace` pass the mode through; `delete_session` calls `_require` **before** `store.delete` — `store.delete`'s True/False would otherwise have distinguished a real id from an invented one even while refusing both. `ask`/`ask_stream` keep `dependencies=[Depends(guard)]` and enforce ownership in-handler (ADR-0006 part 4 is not re-litigated); `research`/`research_stream` stamp `owner=` onto `store.create`.
- **The walker was extended, not bypassed.** `AUTH_DEPENDENCIES` renamed; the `>= 6` non-vacuity floor and the delete `>= 4` / GETs `== 3` structure kept verbatim. New: every session-group route carries `require_session_access`; the ask routes carry `guard` and do **not** carry it, and do call `_require(store, session_id, owner)` in their source.
- **A third assertion the plan did not ask for, added because mutation testing demanded it.** Every handler injects `require_session_access` as a parameter to read its value, and `dependency_names()` cannot tell a router-level dependency from a parameter-level one — so **deleting the router-level dependency left the new gate green**. Observed, not theorised. `service.sessions_router.dependencies` is now asserted directly, and the same mutation is red. Structural membership is the whole of ADR-0006 part 4 and is exactly what four routes forgot four times.
- **API tests:** `sessions_listing_scoped_and_dual_mode`, `foreign_session_is_indistinguishable` (over both id-shaped read routes, asserting equal status, equal key sets, and detail strings that differ only in the echoed id), `expired_session_is_indistinguishable_from_missing` (including that the operator bypasses ownership but not expiry), `delete_owner_or_operator`, `ask_on_someone_elses_session_is_404` (with `fake.calls == []`, so a refused follow-up demonstrably spent nothing), `a_session_records_the_identity_that_created_it` (the cookie's middle segment equals the stored owner — the thread from cookie to row), and `a_reads_do_not_extend_a_sessions_life` over real HTTP, because a renewal added in a handler rather than the store would slip past the contract test.

### README, OPERATIONS, .env.example (commit 6b52781)

Per the standing per-phase freshness deliverable, corrected by the wave that falsified them: the API table's "`X-Demo-Token` required" on the session reads/delete; the known-limitation bullet that lumped sessions in with unbounded notes; the test count 534 → 551; OPERATIONS' `SESSIONS_TOKEN` row and the two-tokens paragraph (with the fail-closed reversal explained, not deleted); `SESSION_TTL_DAYS` added to both the OPERATIONS env table and `.env.example`.

**Deliberately untouched:** README's "The public demo is rate-limited, not authenticated" bullet at ~line 210. Its second sentence is now false as well, but the user assigned that line to Wave 5, which owns the ADR and the deployed-identity story.

## Verification record

| Gate | Baseline (measured 2026-08-05) | Result |
|------|-------------------------------|--------|
| `grep -c "ADD COLUMN…owner" sessions.py` | 0 | **2** (Postgres + SQLite paths) |
| `grep -c "table_info(sessions)" sessions.py` | 0 | **1** |
| `grep -c "expires_at" sessions.py` | 0 | **0** (expiry derived) |
| `grep -rc "require_sessions_token" src/research_agent` | 3 | **0** — a rename, not an addition alongside |
| `grep -c require_session_access` limits.py + service.py | 0 | **1 + 6** |
| `AUTH_DEPENDENCIES` | `{"guard", "require_sessions_token"}` | `{"guard", "require_session_access"}` |
| `/sessions` route objects in the walker | 6 | **6**, floor still `>= 6` |
| `grep -c "bundles check_daily_cap" tests/test_service.py` | 0 (12-03 already fixed it) | **0** |
| `grep -c "reserve_or_429" tests/test_service.py` | 3 | **4** |
| `pytest tests/test_store_contract.py` | — | green plain **and** armed |
| `pytest tests/test_service.py tests/test_limits.py` | — | 159 passed, 4 skipped |
| Full suite, plain | 493 passed / 41 skipped | **506 passed / 45 skipped** |
| Full suite, armed (`:54329`) | 533 passed / 1 skipped | **550 passed / 1 skipped** |
| ruff | clean | clean |

**Delta fully explained.** Collected 534 → 551, +17 in both arms.

- Task 1: 4 contract tests × 2 backends = 8. Plain: **+4 passed, +4 skipped** (the Postgres arms, each reporting `DATABASE_URL is not set`). Armed: +8 passed.
- Task 2: `test_service.py` **+8** net (4 replacing the 4 retired `unauthenticated_sessions_routes_are_refused` params, then +1 ask-ownership, +1 structural, +6 ownership block), `test_limits.py` **+1** net (5 `require_sessions_token` tests replaced by 6 `require_session_access` ones, the extra being the empty-token-cannot-match regression).
- Plain +13 = 4 + 9; armed +17 = 8 + 9. ✓

**The four new plain skips are justified and named:** they are the postgres arms of the four new session-contract tests. They are not new *coverage* gaps — the same four assertions run green under the armed run, which is where the multi-machine backend's DB-clock expiry is actually proven. A green plain run is not evidence that Postgres expiry works.

### Falsification checks

Every gate this plan adds was mutated and observed red, then reverted.

| Mutation | Expected red | Observed |
|----------|-------------|----------|
| Drop the owner check from `_require` | ownership tests | 7 failed (3 stranger params, foreign, delete, quota, ask) |
| `scope = None` unconditionally in `list_sessions` | scoping tests | 3 failed (dual-mode, empty listing, unset-token) |
| Delete `dependencies=[...]` from `sessions_router` | structural walker | **initially GREEN** — gate strengthened, then red |

## Deviations from Plan

**1. [Rule 2 — Missing critical control] The structural walker was vacuous against its own primary mutation**
- **Found during:** Task 2, falsification pass
- **Issue:** the plan's assertion ("every sessions_router route carries `require_session_access`") passes whether the dependency comes from the router or from each handler's `access=Depends(...)` parameter. Deleting the router-level declaration — the thing ADR-0006 part 4 exists to protect — left both walker tests green.
- **Fix:** a third assertion reading `service.sessions_router.dependencies` directly, with the reason in a comment. Mutation now red.
- **Files modified:** tests/test_service.py
- **Commit:** b87a088

**2. [Rule 1 — Falsified tests] The Phase 10.5 401-block was rewritten, not preserved**
- **Found during:** Task 2
- **Issue:** five tests asserted the retired mechanism — `test_unknown_sessions_are_401_without_a_token`, `test_unauthenticated_sessions_routes_are_refused` (4 params), `test_sessions_token_unset_fails_closed`, `test_demo_token_fallback_protects_the_session_routes`, `test_delete_rate_limited_check_runs_after_the_token_check`.
- **Fix:** each rewritten to assert the *property* rather than the mechanism, with the reversal explained in the docstring. The oracle concern is now met more strongly (no answer distinguishes ids, for any caller) and asserted that way. The fail-closed test became `test_an_unset_sessions_token_closes_only_the_operator_view`, which still asserts the half that matters — a stranger's session stays unreachable with the operator header inert.
- **Commit:** b87a088

**3. [Rule 1 — Bug in an existing test's premise] `client.cookies.set(..., domain="testserver")` does not send the cookie**
- **Found during:** Task 2, while fixing `test_a_follow_up_survives_a_restart`
- **Issue:** the pattern (introduced in 12-03's `test_delete_rate_limited_check_runs_after_the_token_check`) silently fails to attach the cookie — the request arrives with a fresh identity. That test still passed, but its stated premise ("the refused caller carries the VICTIM'S identity cookie") was false, so it was proving less than it claimed.
- **Fix:** cookies are handed to the `TestClient` constructor instead, with the trap noted in the docstring. The 12-03 test was independently rewritten (its ordering rationale no longer holds; the property now survives because the rate bucket is identity-keyed, so a stranger burns their own slot — asserted by leaving the owner a working DELETE).
- **Commit:** b87a088

**4. [Rule 1 — Falsified docs] README, OPERATIONS and .env.example**
- README.md, docs/OPERATIONS.md and .env.example were outside the plan's `files_modified`. Leaving "`X-Demo-Token` required" on routes that no longer require it, and "no expiry or ownership for sessions" next to the code that adds both, would have been knowingly false documents. Same reasoning as Waves 0–2. **Commit:** 6b52781

**5. [Scope] The stale cap rationale was already correct**
- The plan's Task 2 asked for the `~L605-608` comment to stop claiming `guard` "bundles check_daily_cap". 12-03 had already rewritten it (`grep -c "bundles check_daily_cap"` was **0** on entry, `reserve_or_429` already present). What was genuinely missing was the plan's other half — the forward reference to where the real read-survives-the-cap proof lives — so the comment now names `test_all_spending_routes_reserve` and `test_limits.test_reads_survive_the_cap` and states explicitly that the structural assertion is a tripwire, not the proof. The `capped == []` line is unchanged.

**6. [Additive, plan-directed] `owner` on the wire**
- The plan specified adding `owner` to `Session.summary()`, which flows into `GET /sessions` and `SessionDetail`. Declared explicitly on the pydantic model rather than left to extra-ignore, so listing and detail agree. A caller can only ever see their own id (which is the non-secret half of their own cookie); the operator's cross-owner listing is where it earns its place.

## Deferred Issues

Logged to `deferred-items.md`: `docs/OPERATIONS.md` still carries two claims that **12-03** falsified — the "Concurrency and the spend cap interact, and this is not fixed" paragraph, and `DEMO_RATE_LIMIT_PER_HOUR` described as "per visitor IP" (plus `DEMO_RESERVED_RUN_USD` missing from the env table). Out of this wave's scope; 12-06 owns the phase doc pass.

## Threat Flags

None. Every row in the plan's register is implemented and gated:

| Threat | Where it is closed |
|--------|--------------------|
| T-12-04-01 existence oracle | one `_require`; `foreign_session_is_indistinguishable` asserts equal responses, not equal status codes |
| T-12-04-02 reading/deleting another's session | owner check in `_require`; delete gated through it; ask routes enforce in-handler — all four mutated red |
| T-12-04-03 operator view without the credential | `sessions_token()` match only, and `test_an_unset_token_cannot_be_matched_by_an_absent_header` forbids the one-character regression that would make every anonymous caller the operator |
| T-12-04-04 a new session route ships unguarded | router membership asserted **directly**, after the per-route form was shown vacuous |
| T-12-04-05 unbounded store | derived TTL + sweep on create, asserted on unfiltered `count()`, both backends |
| T-12-04-06 stale rationale makes an assertion trivially true | comment states what the tripwire is and is not, and names the behavioural gates |

## Requirements

`REQ-store-lifecycle-and-ownership` stays **Pending**. Its text has two halves and this plan delivers one: sessions carry an owner and an expiry, `/sessions` lists only the caller's, and `/sessions/{id}` 404s for others. The notes half — "notes carry at least one bound … consistent across JSON/memory/Chroma/pgvector" — is Wave 4 (12-05). Checking it off now would mark a requirement complete on half its sentence.

## Self-Check: PASSED

- `src/research_agent/sessions.py`, `service.py`, `limits.py`, `tests/test_store_contract.py`, `tests/test_service.py`, `tests/test_limits.py`, `README.md`, `docs/OPERATIONS.md`, `.env.example` all exist and are modified as claimed
- Commits `82af2cc`, `b87a088`, `6b52781` all present on `gsd/phase-12-caller-identity`
