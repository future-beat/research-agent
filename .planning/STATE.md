# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness

## Current Position

Phase: 10.5 of 17 (Close the live endpoint exposure — hotfix)
Plan: 0 of 5 executed in current phase
Status: Planned — ready to execute
Last activity: 2026-08-04 — Phase 10.5 planned: 5 plans across 5 sequential waves, checker returned 0 blockers, 6 warnings fixed in one revision

Progress: [█████░░░░░] 53% (9 of 17 phases complete; v1.0 shipped)

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
Stopped at: Phase 10.5 planned and verified (0 blockers). Nothing executed yet; no code changed.
Resume file: None

**Carry into execution — the two findings that most shape this phase:**
- Setting `DEMO_TOKEN` in production would kill the public demo. `guard` already checks it and
  fronts `POST /research/stream`, and the demo page sends no token header. That is why the fix
  uses a separate `SESSIONS_TOKEN`. `DEMO_TOKEN` must stay unset in production.
- The structural invariant test passes **vacuously** with a naive route walker: FastAPI 0.141.1
  leaves a `fastapi.routing._IncludedRouter` in `app.routes`, so `isinstance(r, APIRoute)` finds
  zero session routes. Verified empirically. The recursive walker plus the `len(...) >= 6`
  non-vacuity assertion is load-bearing — do not "simplify" it to five.

Next: `/gsd:execute-phase 10.5` — then `/gsd:plan-phase 10`

Note: Plan 10.5-05 is `autonomous: false`. It stages a Fly secret and performs the production
cutover (carrying Phase 10's three pending commits in the same deploy), so it needs you at the
keyboard. Plans 01–04 are autonomous.
