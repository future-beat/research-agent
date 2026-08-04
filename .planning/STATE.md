---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Closing the limitations list
status: executing
stopped_at: "Plan 10.5-04 complete — the guard invariant is now structural and non-vacuous. Next: plan 10.5-05, the production cutover."
last_updated: "2026-08-04T00:00:00.000Z"
last_activity: "2026-08-04 — Plan 10.5-04 executed: a recursive route walker plus a non-vacuity assertion now prove no route under /sessions is anonymous, and pin the DELETE limiter and the unmetered reads structurally. All four mutation checks bit and were reverted. The code is ready to deploy; only the cutover remains"
progress:
  total_phases: 19
  completed_phases: 9
  total_plans: 5
  completed_plans: 4
  percent: 53
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness

## Current Position

Phase: 10.5 of 17 (Close the live endpoint exposure — hotfix)
Plan: 4 of 5 executed in current phase
Status: Executing — plan 04 complete, plan 05 (production cutover) next
Last activity: 2026-08-04 — Plan 10.5-04 executed: `api_routes()` walks `_IncludedRouter` recursively and `test_route_guard_invariant_over_the_sessions_tree` refuses to pass on fewer than six session routes, so a route added under `/sessions` without `guard` or `require_sessions_token` fails the suite and the test cannot go green by examining nothing. `test_delete_carries_the_rate_limiter` pins the DELETE limiter and proves the three reads carry neither it nor the daily cap. Four mutation checks run and reverted; the naive walker mutation confirmed a flat scan reports a *clean* sessions tree while the four leaking routes are invisible. The deployed service is still exposed until plan 05.

Progress: [█████░░░░░] 53% (9 of 17 phases complete; v1.0 shipped)
Phase 10.5: [████████░░] 4 of 5 plans

**Sequencing note:** Phase 10.5 (live endpoint exposure) is a hotfix inserted ahead of
Phase 11 and depends on nothing. It may be planned and shipped before, after, or alongside
Phase 10 — but it must not wait for Phase 11.

## Performance Metrics

**Velocity:**

- Total plans completed: 0 under GSD (phases 1–9 predate GSD planning)
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1–9 | pre-GSD | — | — |

**Recent Trend:**

- Last 5 plans: —
- Trend: — (no GSD-tracked plans yet)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Full ingested set (23, all soft):
`.planning/intel/decisions.md`.

Recent decisions affecting current work:

- [Ingest]: Zero ADRs existed at ingest — all 23 architectural decisions are soft/revisable. Nothing is LOCKED.
- [Phase 10, approved 2026-08-04]: Promote five load-bearing decisions (DEC-01, DEC-02, DEC-04, DEC-14, DEC-22) to numbered ADRs before any reversal lands.
- [Milestone scope, approved]: All nine README Limitations items are in scope for v1.1.
- [Ordering]: REQ-followup-live-search is last (deepest change); REQ-offline-eval-quality precedes both quality-affecting reversals so their effect is observable.
- [Phase 10.5-01]: Session endpoints reuse the `x-demo-token` header rather than a new `x-sessions-token` — one client-side auth story. CONTEXT left the header name to discretion.
- [Phase 10.5-01]: `require_sessions_token` fails closed (403 when no credential is configured), deliberately diverging from `check_token`'s open-when-unset convention. A control that goes inert on a missing env var is precisely the defect this hotfix exists to fix.
- [Phase 10.5-02]: The four session routes are grouped on an `APIRouter`, not given four per-route dependency lists. The defect was four routes each independently forgetting a credential, so membership had to become structural — a new route on `sessions_router` is guarded by construction.
- [Phase 10.5-02]: `check_rate_limit` on `DELETE /sessions/{id}` only, sharing the research bucket. Reads stay unmetered so the daily cap's "Read-only endpoints still work" message stays true.
- [Phase 10.5-02]: **Any assertion over `app.routes` must now be recursive.** fastapi 0.141.1 leaves an `_IncludedRouter` in `app.routes` rather than flattening, so a flat scan silently misses every session route. Two pre-existing tests were fixed for this; plan 04's structural test must not repeat the mistake.
- [Phase 10.5-03]: The daily-cap test records real spend and asserts `POST /research` 429s *before* asserting a read is 200. Under the fixture's `DEMO_DAILY_USD_CAP=0`, `check_daily_cap` returns early, so the obvious construction cannot fail even if the cap were wired onto the reads.
- [Phase 10.5-03]: A guard test is not done until the guard has been removed and the test observed failing. All six controls in this phase were mutation-checked individually; the mutation table lives in `10.5-03-SUMMARY.md` and is plan 04's acceptance shortcut.
- [Phase 10.5-04]: `api_routes()` **supersedes** wave 2's private `_served_routes()` walker rather than sitting beside it. Two independent recursive walkers over `fastapi.routing._IncludedRouter` — a private, version-specific internal — is two things to fix on the next FastAPI upgrade and two things that can drift.
- [Phase 10.5-04]: The non-vacuity threshold is **6 route objects across 5 paths**, not 5 — `/sessions/{session_id}` is served by both a GET and a DELETE. Do not "correct" it downward.
- [Phase 10.5-04]: A naive flat route scan does not find *zero* session routes as the obvious analysis suggests — it finds the two `@app.post` ask routes, both of which carry `guard`, and therefore reports a perfectly clean sessions tree. A guard invariant without a count assertion goes green over exactly this phase's defect. Verified by mutation.
- [Phase 10.5-01]: `REQ-live-endpoint-exposure` stays **Pending** until plan 05. Its text says "not reachable without credentials **on the deployed service**" — it cannot be honestly checked off by a plan that wires nothing and deploys nothing. Mark it at the cutover, not before.

### Pending Todos

None yet.

### Blockers/Concerns

- **LIVE SECURITY EXPOSURE — Phase 10.5.** `GET /sessions`, `GET /sessions/{id}`,
  `GET /sessions/{id}/trace` and `DELETE /sessions/{id}` have no `Depends(guard)`
  (`src/research_agent/service.py:514`, `:519`, `:533`, `:539`). Confirmed against the
  deployed service on 2026-08-04: an unauthenticated `GET /sessions` returned two real
  sessions with full task text, and two `DELETE` calls returned 204 from the open internet.
  `DEMO_TOKEN` does not close this — `check_token` runs only inside `guard`, which these
  paths never reach. The two exposed sessions were backed up and deleted with the owner's
  consent; two orphaned notes remain in the memory store (`/memory` exposes counts only,
  not content). Also: the SSE error handler leaks unredacted `str(exc)`
  (`service.py:263`) while `/health` correctly redacts using a helper that already exists.
  **Status after plan 10.5-02:** both halves are fixed in code on
  `gsd/phase-10.5-close-the-live-endpoint-exposure` — the four routes carry
  `require_sessions_token` and the SSE handler now redacts. **The deployed service is
  unchanged and still exploitable.** This blocker closes at the plan-05 cutover, which must
  stage `SESSIONS_TOKEN` as a Fly secret in the same release as the code (the routes fail
  closed, so a deploy without the secret 403s them).

- **Other findings from codebase mapping, not yet phased.** Notes are written to a shared
  store with no tenant scoping (`graph.py:274`) and recalled into other visitors' runs
  (`graph.py:248`), and the critic reads the same untrusted text it polices
  (`graph.py:385`) — so injection can force `APPROVED`. The daily spend cap counts only
  completed runs (`limits.py:198` vs `service.py:222`), so ~16 concurrent runs can overshoot
  the $5 cap roughly 3×. `pydantic` is unpinned — used by every API model, absent from
  `pyproject.toml`, floating in via FastAPI. `requires-python = ">=3.10"` while Docker and
  CI run 3.14, so the floor is untested. Voyage embedding spend is accounted nowhere.
  Decide in Phase 12 planning which of these belong there versus a later phase.

- **Six requirements are design reversals, not bug fixes.** Each needs a replacement guarantee decided in its own discuss-phase. Two are severe: Phase 17 (REQ-followup-live-search) retires the guarantee DESIGN.md calls "the single failure mode this whole pipeline exists to prevent"; Phase 16 (REQ-independent-critic-model) falsifies README's eval-judge rationale, which must be re-derived rather than inherited. See ROADMAP.md → Reversal register.
- **Docs assert a verified-false fact.** `docs/OPERATIONS.md` (~lines 49–51) says deploys run through Fly's GitHub integration and are not CI-gated. `fly releases -a research-agent` shows 3 releases, all from the owner's personal account — deploys are manual via `fly deploy -a research-agent`. Fixed in Phase 10.
- **Live release is 3 commits behind `main`** (README restructure, `src/` reorg, its bugfix). Functionally healthy — `/`, `/health`, `/demo`, `/metrics` all 200 — but the deployed tree differs from `main`. Redeploy is in Phase 10.
- **`docs/DESIGN.md` says three `MemoryStore` backends; there are four** (json, memory, chroma, pgvector). Stale since Phase 8. Fixed in Phase 10.
- **Pricing has a shelf life — but the code already handles it.** Verified 2026-08-04:
  `src/research_agent/usage.py:59-76` has contiguous windows (`until=date(2026, 8, 31)` and
  `since=date(2026, 9, 1)`), so no rollover work is needed. What does need a decision before
  2026-09-01: `AGENT_MAX_RUN_COST_USD=1.00` and `DEMO_DAILY_USD_CAP=5.00` in `fly.toml` will
  bind roughly a third sooner once the same workload costs 50% more. Planning docs must not
  quote a single rate as permanent. Touches Phase 14.

- Acceptance criteria in `.planning/intel/requirements.md` are synthesis proposals, **not user-ratified** — firm them up per phase.
- Verified 2026-08-04: nothing cites `/healthz` (which 404s); `/health` is cited correctly. No fix needed, but re-verify in Phase 10 rather than assume.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-04
Stopped at: Plan 10.5-03 complete (`c68cc87`, `5ebc861`) — the guarded sessions group now has
behavioural coverage: 401 anonymous on all four routes, 200/204 authorised, 403 fail-closed,
the `DEMO_TOKEN` fallback, unmetered reads, a rate-limited `DELETE` that checks the token first,
and the demo-survival regression test. Suite green at 386 passed / 28 skipped, `ruff` clean,
no production code touched. The live exposure is unchanged until plan 05 deploys.
Next: plan 10.5-04 (structural regression test — must walk `app.routes` recursively).
Resume file: None

**Carry into execution — the two findings that most shape this phase:**

- Setting `DEMO_TOKEN` in production would kill the public demo. `guard` already checks it and
  fronts `POST /research/stream`, and the demo page sends no token header. That is why the fix
  uses a separate `SESSIONS_TOKEN`. `DEMO_TOKEN` must stay unset in production.

- The structural invariant test passes **vacuously** with a naive route walker: FastAPI 0.141.1
  leaves a `fastapi.routing._IncludedRouter` in `app.routes`, so `isinstance(r, APIRoute)` finds
  zero session routes. Verified empirically. The recursive walker plus the `len(...) >= 6`
  non-vacuity assertion is load-bearing — do not "simplify" it to five.

Next: continue `/gsd:execute-phase 10.5` from plan 02 — then `/gsd:plan-phase 10`

Note: Plan 10.5-05 is `autonomous: false`. It stages a Fly secret and performs the production
cutover (carrying Phase 10's three pending commits in the same deploy), so it needs you at the
keyboard. Plans 01–04 are autonomous.
