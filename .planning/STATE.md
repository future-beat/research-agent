---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Closing the limitations list
status: in-progress
stopped_at: "Completed 10-02-PLAN.md — records 0003–0006 written; docs/adr/ is now the complete six-record set. Next: plans 10-03 through 10-05."
last_updated: "2026-08-05T00:00:00.000Z"
last_activity: "2026-08-05 — Plan 10-02 executed: ADR-0003 (DEC-04, no_prior_research), ADR-0004 (DEC-14, SQLite not the checkpointer), ADR-0005 (DEC-22, Opus 5 judge) and ADR-0006 (Phase 10.5 auth, Source: not Promoted from:). Every filename in the index now resolves. No code touched; suite unchanged at 388/28"
progress:
  total_phases: 19
  completed_phases: 9
  total_plans: 10
  completed_plans: 7
  percent: 56
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness (Phase 10.5 hotfix shipped)

## Current Position

Phase: 10 of 17 (ADRs and doc correctness) — **IN PROGRESS**
Plan: 2 of 5 executed in current phase
Status: In progress — all six ADRs now exist on disk. Plans 10-03 and 10-04 (doc corrections) and 10-05 (verification) remain.
Last activity: 2026-08-05 — Plan 10-02 executed: records 0003–0006. DEC-04, DEC-14 and DEC-22 promoted from `docs/DESIGN.md`; ADR-0006 records the Phase 10.5 auth decisions with `**Source:**` rather than `**Promoted from:**` and states unmissably that `DEMO_TOKEN` must never be set in production. All six `Accepted`; nothing superseded. Documentation only — `git status --porcelain src/ tests/ evals/` is empty and the suite is unchanged at 388 passed, 28 skipped.

Progress: [█████░░░░░] 56% (9 of 17 phases complete + hotfix 10.5; v1.0 shipped)
Phase 10.5: [██████████] 5 of 5 plans — complete
Phase 10: [████░░░░░░] 2 of 5 plans

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
| 10 | 2 (10-01, 10-02) | 26min | 13min |

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
- [Phase 10-01]: ADR provenance is a two-form contract — `**Promoted from:**` for the five `docs/DESIGN.md` promotions, `**Source:**` for ADR-0006, which originates in Phase 10.5 and has no DESIGN.md passage. The index says so in prose so no reader hunts for one.
- [Phase 10-01]: Supersession is a status-line edit and nothing else. A superseded record's Context, Decision and Consequences are never rewritten, including claims that stopped being true. `docs/adr/README.md` states this as a verbatim three-step instruction for Phases 12, 16 and 17.
- [Phase 10-01]: Expected supersessions (Phase 16 → ADR-0005, Phase 17 → ADR-0003, Phase 12 → ADR-0006) are carried in the index as italicised forecasts. All six records are `Accepted` today; nothing is marked superseded.
- [Phase 10.5-02]: **Any assertion over `app.routes` must now be recursive.** fastapi 0.141.1 leaves an `_IncludedRouter` in `app.routes` rather than flattening, so a flat scan silently misses every session route. Two pre-existing tests were fixed for this; plan 04's structural test must not repeat the mistake.
- [Phase 10.5-03]: The daily-cap test records real spend and asserts `POST /research` 429s *before* asserting a read is 200. Under the fixture's `DEMO_DAILY_USD_CAP=0`, `check_daily_cap` returns early, so the obvious construction cannot fail even if the cap were wired onto the reads.
- [Phase 10.5-03]: A guard test is not done until the guard has been removed and the test observed failing. All six controls in this phase were mutation-checked individually; the mutation table lives in `10.5-03-SUMMARY.md` and is plan 04's acceptance shortcut.
- [Phase 10.5-04]: `api_routes()` **supersedes** wave 2's private `_served_routes()` walker rather than sitting beside it. Two independent recursive walkers over `fastapi.routing._IncludedRouter` — a private, version-specific internal — is two things to fix on the next FastAPI upgrade and two things that can drift.
- [Phase 10.5-04]: The non-vacuity threshold is **6 route objects across 5 paths**, not 5 — `/sessions/{session_id}` is served by both a GET and a DELETE. Do not "correct" it downward.
- [Phase 10.5-04]: A naive flat route scan does not find *zero* session routes as the obvious analysis suggests — it finds the two `@app.post` ask routes, both of which carry `guard`, and therefore reports a perfectly clean sessions tree. A guard invariant without a count assertion goes green over exactly this phase's defect. Verified by mutation.
- [Phase 10-02]: Each record with a named future reversal carries a `### Expected reversal` subsection, not a passing mention — which phase, which requirement, and what specifically breaks. ADR-0005's is the sharpest: Phase 16 removes the record's *premise* (the critic's shared model), so the stronger-judge rationale must be re-derived rather than inherited.
- [Phase 10-02]: ADR-0006 leads its Consequences with a dedicated heading, `### DEMO_TOKEN must never be set in production`, rather than a bullet. The record exists for that one consequence; a list would bury it, and the refactor it guards against ("tidy the two tokens into one") is the plausible-looking kind.
- [Phase 10-02]: ADR-0006 states all four decision parts with individual reasons because they are separable — a future change is most likely to pick off one (apply `guard` to the reads, or make the credential open-when-unset) without seeing the others.
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
  **✅ RESOLVED 2026-08-04 — Fly release v4.** `SESSIONS_TOKEN` was staged and deployed in the
  same release as the code. Verified from the open internet: all four endpoints return **401**
  anonymously and **200** with the token; `/`, `/health`, `/demo`, `/metrics` still 200;
  `/demo` still reports `token_required: false`; an anonymous browser research run still
  completes. The SSE handler redacts and truncates. The cutover also carried Phase 10's three
  pending commits, so the deployed tree now equals `main` and the deploy drift is gone.

  **Residual, now owned by Phase 12:** the token proves *authorised*, not *who* — there is
  still no per-caller ownership or session expiry, and `GET /sessions` still lists every
  session to any token holder. Two orphaned notes from the sessions deleted on 2026-08-04
  remain in the memory store. `_index_json` does not advertise `DELETE /sessions/{id}`.

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
- ~~**Live release is 3 commits behind `main`**~~ — **RESOLVED 2026-08-04.** The Phase 10.5 cutover
  (release v4) carried the README restructure, the `src/` reorganisation and its bugfix. The
  deployed tree now equals `main`. This satisfies Phase 10's SC-5 ahead of schedule; Phase 10 need
  only re-verify rather than redeploy.
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

Last session: 2026-08-05
Stopped at: **Completed 10-02-PLAN.md.** `docs/adr/` is now the complete six-record set —
0003 (`no_prior_research`), 0004 (SQLite, not the checkpointer), 0005 (the Opus 5 judge) and
0006 (the Phase 10.5 auth decisions) joined 0001–0002, and every filename in the index
resolves. All `Accepted`; nothing superseded. Plans 10-03 through 10-05 remain. (Phase 10.5
remains complete and shipped as Fly release v4.)
Resume file: None

**Carry forward — findings that outlive this phase:**

- **`DEMO_TOKEN` must stay UNSET in production.** `guard` checks it and fronts
  `POST /research/stream`; the demo page sends no token header, so setting it 401s every
  anonymous visitor and takes the public demo offline. Session endpoints use `SESSIONS_TOKEN`
  instead (sent as `x-demo-token`, fails closed at 403 when unset). Any future phase that
  touches auth must not "tidy" these into one variable.

- **Any assertion over `app.routes` must walk recursively.** fastapi 0.141.1 leaves a
  `fastapi.routing._IncludedRouter` in `app.routes` rather than flattening. A flat scan sees
  only the two `@app.post` ask routes — both legitimately guarded — computes an empty
  unguarded list, and reports a *clean* sessions tree while the four leaking routes stay
  invisible. Use `api_routes()` in `tests/test_service.py` and always assert a route count
  first. Two pre-existing tests had this bug.

- **`docs/adr/README.md` is owned by plan 10-01 and is already complete.** It carries index
  rows for all six records with their titles and expected superseders. Plan 10-02 wrote the
  record files 0003–0006 without editing the index; every row now resolves to a file on disk.

- **The `000[1-5]` ADR gates deliberately exclude 0006.** Records 0001–0005 are DESIGN.md
  promotions and are gated for a `DESIGN.md` citation; ADR-0006 has none by design. Widening
  those globs to `000[1-6]` would make the citation gate fail correctly-written work.

- **Deploys are manual and now proven so.** `fly secrets set --stage` then one `fly deploy`
  puts secret and code in the same release — required whenever a control fails closed.

Next: `/gsd:plan-phase 10` (ADRs and doc correctness). Note Phase 10's SC-5 (deployed release
matches `main`) is **already satisfied** by the v4 cutover — Phase 10 need only re-verify, not
redeploy.
