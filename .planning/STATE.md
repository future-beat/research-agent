# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness

## Current Position

Phase: 10 of 17 (ADRs and doc correctness) — first phase of milestone v1.1
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-08-04 — Doc ingest complete; PROJECT.md, REQUIREMENTS.md, ROADMAP.md created

Progress: [█████░░░░░] 53% (9 of 17 phases complete; v1.0 shipped)

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

- **Six requirements are design reversals, not bug fixes.** Each needs a replacement guarantee decided in its own discuss-phase. Two are severe: Phase 17 (REQ-followup-live-search) retires the guarantee DESIGN.md calls "the single failure mode this whole pipeline exists to prevent"; Phase 16 (REQ-independent-critic-model) falsifies README's eval-judge rationale, which must be re-derived rather than inherited. See ROADMAP.md → Reversal register.
- **Docs assert a verified-false fact.** `docs/OPERATIONS.md` (~lines 49–51) says deploys run through Fly's GitHub integration and are not CI-gated. `fly releases -a research-agent` shows 3 releases, all from the owner's personal account — deploys are manual via `fly deploy -a research-agent`. Fixed in Phase 10.
- **Live release is 3 commits behind `main`** (README restructure, `src/` reorg, its bugfix). Functionally healthy — `/`, `/health`, `/demo`, `/metrics` all 200 — but the deployed tree differs from `main`. Redeploy is in Phase 10.
- **`docs/DESIGN.md` says three `MemoryStore` backends; there are four** (json, memory, chroma, pgvector). Stale since Phase 8. Fixed in Phase 10.
- **Pricing has a shelf life.** Sonnet 5 introductory $2/$10 per MTok ends 2026-08-31; $3/$15 from 2026-09-01. The effective-dated table handles it at runtime; planning docs must not quote a single rate as permanent. Touches Phase 14.
- Acceptance criteria in `.planning/intel/requirements.md` are synthesis proposals, **not user-ratified** — firm them up per phase.
- Verified 2026-08-04: nothing cites `/healthz` (which 404s); `/health` is cited correctly. No fix needed, but re-verify in Phase 10 rather than assume.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-04
Stopped at: Roadmap created for milestone v1.1 (Phases 10–17); all 9 ingested requirements mapped, 0 orphans
Resume file: None

Next: `/gsd:plan-phase 10`
