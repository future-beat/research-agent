---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Closing the limitations list
status: planned
stopped_at: "Phase 11 planned — 5 plans, 5 waves. Checker: 0 blockers after one revision. Next: /gsd:execute-phase 11."
last_updated: "2026-08-05T00:00:00.000Z"
last_activity: "2026-08-05 — Phase 11 planned. Supabase chosen over Neon on evidence (Neon free tier meters 100 CU-h/month; /health probes keep compute awake and exhaust it ~day 16). Checker found 4 blockers, all silent-failure modes; fixed in one revision"
progress:
  total_phases: 19
  completed_phases: 9
  total_plans: 10
  completed_plans: 10
  percent: 56
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness (Phase 10.5 hotfix shipped)

## Current Position

Phase: 11 of 17 (Multi-machine state and pooled Postgres) — **PLANNED, not started**
Plan: 0 of 5 executed in current phase
Status: Planned and verified. Checker returned 4 blockers on the first pass; all four were
silent-failure modes, fixed in one revision, re-verified to 0 blockers. Three residual warnings
were closed by hand.
Last activity: 2026-08-05 — Phase 11 planned: 5 plans across 5 sequential waves.

**Phase 10 is closed** — PR #4 merged, both required checks green, so the SC-5 push gate that
held it open is satisfied and `REQ-adr-promotion` is complete.

Progress: [██████░░░░] 59% (10 of 17 phases complete + hotfix 10.5; v1.0 shipped)
Phase 10.5: [██████████] 5 of 5 plans — complete
Phase 10:   [██████████] 5 of 5 plans — complete (PR #4 merged)
Phase 11:   [░░░░░░░░░░] 0 of 5 plans — planned

**Carry into execution — the four findings the plans are built around:**

- **`psycopg_pool.PoolTimeout` subclasses `psycopg.OperationalError`**, and `Database.cursor()`
  retries once on `OperationalError`. A naive port doubles every timeout.
- **`/health` already blows its budget today**, before any Phase 11 change: two 3s connect
  attempts × three sequential probes = up to 18s against Fly's 15s check. Phase 11 fixes it with
  a `HEALTH_PROBE_BUDGET` deadline giving a 9s ceiling that holds cold, warm *and* partitioned.
- **`pg_advisory_lock` is session-scoped**, so lock + DDL + unlock must share ONE pooled
  connection or the lock serialises nothing and leaks.
- **Removing the three `*_DB_PATH` env vars does NOT prevent SQLite fallback.** `sessions.py:43`
  has a module-dir default and `default_backend()` returns `sqlite` whenever `DATABASE_URL` is
  empty — two mountless machines would each boot their own ephemeral database and `/health` would
  report `ok`. The fix is pinning `SESSION_BACKEND`/`METRICS_BACKEND`/`VECTOR_STORE` so a missing
  DSN fails closed at construction.

Plans 11-04 and 11-05 are `autonomous: false` — they provision Supabase, set a Fly secret, drop
the mount and scale to two machines. The volume `agent_data` is **kept as backup, never destroyed**.

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
| 10 | 5 (10-01, 10-02, 10-03, 10-04, 10-05) | 55min | 11min |

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
- [Phase 10-04]: The forward-links point at **ADR-0001…0005 only**. ADR-0006 is not linked from `docs/DESIGN.md` and must not be added: it originates in the Phase 10.5 hotfix and carries `**Source:**`, not `**Promoted from:**`. A link from DESIGN.md would assert a provenance that does not exist.
- [Phase 10-04]: The link text carries both the record number and the path (`Recorded as [ADR-000N](adr/000N-slug.md)`) rather than a bare title link, so a reader scanning the prose gets the identifier that supersession notices will use.
- [Phase 10-04]: The "expires this month" clause was replaced with "is time-boxed" rather than a fresher relative date. Any wording anchored to a writing date decays; the two ISO dates carry the fact.
- [Phase 10-05]: A red gate is recorded as red. SC-5 step 3 failed and the row was marked ❌ with the approval left pending, rather than the criterion being reworded to match the observed state. The Criterion and Automated Command columns of `10-VALIDATION.md` were not touched after the gates ran.
- [Phase 10-05]: Two edits were made to `10-VALIDATION.md` prose that the verify block forced, and neither weakens a gate: the `⬜ pending` token was dropped from the status legend (nothing is pending, so the key entry was dead), and the sign-off item `` `nyquist_compliant: true` set in frontmatter`` was reworded to "Frontmatter marks the phase Nyquist-compliant" so the literal token appears exactly once, in the frontmatter that owns it.
- [Phase 10-05]: `ruff` is not on `PATH` in this environment; `.venv/bin/ruff` is the working invocation, matching the `.venv/bin/pytest` convention. Recorded so a future phase does not read a bare `ruff check .` failure as a lint regression.
- [Phase 10-05]: The non-vacuity control is now four probes, not one — the zero-occurrence search, the file counter, the link resolver and the `Status` gate were each shown to fail on input that must fail. This repo has shipped five vacuous gates across two phases; a gate that has only ever passed is treated as unproven.
- [Phase 10.5-01]: `REQ-live-endpoint-exposure` stays **Pending** until plan 05. Its text says "not reachable without credentials **on the deployed service**" — it cannot be honestly checked off by a plan that wires nothing and deploys nothing. Mark it at the cutover, not before.

### Pending Todos

None yet.

### Blockers/Concerns

- **OPEN — `main` is 21 commits ahead of `origin/main`; Phase 10 sign-off waits on a push.**
  Found by plan 10-05's SC-5 re-verification on 2026-08-05, after a `git fetch origin` so the
  count is against a current remote and not a stale tracking ref. `origin/main` sits at
  `804b873` (the Phase 10.5 close); `main` sits at `238d479`. Every one of the 21 commits is
  Phase 10 documentation — `.planning/`, `docs/`, `docs/adr/`, `README.md` — **including the
  phase base `715e9aa` itself**, which is also unpushed.
  `git diff --name-only origin/main..main -- src/ tests/ evals/ pyproject.toml Dockerfile fly.toml`
  returns **0 files**, so the code in Fly release v4, on `origin/main` and on `main` is
  identical and the deployed image is not stale. **This is not a deploy problem and must not be
  answered with `fly deploy`** — `git push` alone turns the row green, after which Phase 10 and
  `REQ-adr-promotion` can both be closed. Recorded as ❌ red in
  `10-VALIDATION.md` § Execution Record with `**Approval:** pending`.

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
- ~~**`docs/DESIGN.md` says three `MemoryStore` backends; there are four**~~ (json, memory, chroma, pgvector) — **RESOLVED 2026-08-05, plan 10-04.** The seams paragraph now reads "four implementations" and names pgvector alongside the other three.
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
Stopped at: **Completed 10-05-PLAN.md — the phase gate battery.** Every gate in
`10-VALIDATION.md` was run as written on macOS and recorded with its literal output: five ADRs
with `Status` lines and Nygard sections, all five citing `docs/DESIGN.md` and all five linked
back from it, ADR-0006 verified separately (exists, `Accepted`, `DEMO_TOKEN` present, zero
`Promoted from`) so the `000[1-5]` globs stayed as written, `GitHub integration` at zero,
`Deploys are manual` and `enforce_admins` present, four backends with `pgvector`, no unpaired
`$2/$10`, `src/` byte-identical to `715e9aa`, the suite at exactly 388 passed / 28 skipped, and
`.venv/bin/ruff check .` clean. Four non-vacuity controls were run and recorded. SC-5 was
re-verified read-only — release v4 `complete` under the owner's personal account, `/`, `/health`,
`/demo`, `/metrics` all 200 — with **nothing redeployed**. One row is ❌ red: SC-5 step 3
returned `21` for `origin/main..main`, so `**Approval:** pending`. ROADMAP's stale Phase 10.5 row
was reconciled to 5/5 Complete. `REQ-adr-promotion` is left Pending with the blocker named.
Resume file: None

Superseded — previous session: **Completed 10-04-PLAN.md.** SC-2, SC-4 and the DESIGN half of SC-6 are done, so
every corrective criterion in Phase 10 has now landed. `docs/DESIGN.md` names four
`MemoryStore` implementations including pgvector; its pricing paragraph carries both windows
as `2026-08-31` / `2026-09-01` on one line with `/pricing` as the live source and no
"this month" phrasing; and its five promoted paragraphs each end with a `Recorded as ADR-000N`
link, with `adr/README.md` linked from the preamble. All five paths resolve on disk and the
reverse citation from each record back to `docs/DESIGN.md` still holds. `docs/OPERATIONS.md`
and `README.md` remain as 10-03 left them; `docs/adr/` remains the complete six-record set
from 10-01/10-02. Only plan 10-05 (phase-wide verification, including the SC-5 live re-check)
remains. (Phase 10.5 remains complete and shipped as Fly release v4.)
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

- **`docs/DESIGN.md` is now a two-way index into `docs/adr/`.** Any future phase that renames
  an ADR file must update the five `adr/000N-slug.md` links in `docs/DESIGN.md` as well as the
  index rows in `docs/adr/README.md`. The check is
  `for f in $(grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md | sort -u); do test -f "docs/$f" || echo "DANGLING $f"; done`.

- **The `000[1-5]` ADR gates deliberately exclude 0006.** Records 0001–0005 are DESIGN.md
  promotions and are gated for a `DESIGN.md` citation; ADR-0006 has none by design. Widening
  those globs to `000[1-6]` would make the citation gate fail correctly-written work.

- **Deploys are manual and now proven so.** `fly secrets set --stage` then one `fly deploy`
  puts secret and code in the same release — required whenever a control fails closed.

Next: **push `main`** (21 documentation-only commits, no deployable file among them), then flip
the SC-5 row in `10-VALIDATION.md` to ✅, set `**Approval:** approved`, mark Phase 10 Complete in
ROADMAP and tick `REQ-adr-promotion` in REQUIREMENTS.md. After that, `/gsd:plan-phase 11`
(multi-machine state and pooled Postgres). No deploy is pending — release v4 is current and was
re-verified live on 2026-08-05.
