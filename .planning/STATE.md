---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Closing the limitations list
status: executing
stopped_at: "Completed 11-02-PLAN.md — /health is bounded, pools are disposed, and the real-Postgres gates run. Next: 11-03 (deploy-config guards for the new topology)."
last_updated: "2026-08-05T06:05:00.000Z"
last_activity: "2026-08-05 — Executed 11-02: HEALTH_PROBE_BUDGET gives /health a 9s ceiling that holds for a warm partitioned pool (0.32s measured vs 31.4s undeadlined), close_all_pools wired into lifespan, FLY_MACHINE_ID in the body, and six real-Postgres tests run against a local PostgreSQL 17 + pgvector — which found three db.py bugs no fake had caught"
progress:
  total_phases: 19
  completed_phases: 9
  total_plans: 12
  completed_plans: 12
  percent: 56
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness (Phase 10.5 hotfix shipped)

## Current Position

Phase: 11 of 17 (Multi-machine state and pooled Postgres) — **EXECUTING**
Plan: 2 of 5 executed in current phase
Status: 11-02 complete. `/health` bounds every store probe with a `HEALTH_PROBE_BUDGET` wall
clock, giving a 9s ceiling that holds for a warm partitioned pool and not only a cold one; the
lifespan disposes every pool including `graph.memory()`'s, which nothing had ever closed; the
body names the answering machine via `FLY_MACHINE_ID`. The two contract tests 11-01 invalidated
are repaired — the reconnect claim is now proved by a server-side `pg_terminate_backend` — and
six real-Postgres tests run green with **zero skips** under `REQUIRE_POSTGRES=1`.
Last activity: 2026-08-05 — Executed 11-02-PLAN.md (3 tasks, 4 commits).

**11-02 ran the Postgres-gated suite for real.** Docker was unavailable, so PostgreSQL 17 +
pgvector were installed via Homebrew and run on port 54329 (stopped and data dir deleted after;
no `brew services` entry). This was load-bearing, not thoroughness theatre: the suite was green
locally and red against a server, and the run found three `db.py` bugs — see 11-02-SUMMARY.md
§ "The inherited breakage, and what it actually was".

**Phase 10 is closed** — PR #4 merged, both required checks green, so the SC-5 push gate that
held it open is satisfied and `REQ-adr-promotion` is complete.

Progress: [██████░░░░] 59% (10 of 17 phases complete + hotfix 10.5; v1.0 shipped)
Phase 10.5: [██████████] 5 of 5 plans — complete
Phase 10:   [██████████] 5 of 5 plans — complete (PR #4 merged)
Phase 11:   [██████░░░░] 3 of 5 plans — executing

**Carry into execution — the four findings the plans are built around:**

- ~~**`psycopg_pool.PoolTimeout` subclasses `psycopg.OperationalError`**~~ — **CLOSED by 11-01.**
  Both `PoolTimeout` and `PoolClosed` are now caught and re-raised in an arm placed *before* the
  `OperationalError` arm. Measured against an unreachable DSN with `PG_POOL_TIMEOUT=0.5`: 0.505s
  with the exclusion, 1.007s without it — the naive port was mutated in and observed red.
- ~~**`/health` already blows its budget today**~~ — **CLOSED by 11-02.** Every probe now runs
  under `HEALTH_PROBE_BUDGET` (3.0s default), giving a 9s ceiling that holds cold, warm *and*
  partitioned. Measured 0.32s against a store that never answers; removing the deadline was
  mutated in and observed **hanging** for 31.4s before failing.
- ~~**`pg_advisory_lock` is session-scoped**~~ — **CLOSED by 11-02.** The unit half landed in
  11-01 (one `cursor()`, unlock boolean checked, splitting observed red); the real-server half is
  now `test_advisory_lock_is_exclusive_across_connections`, which shows a second connection
  refused a held lock and an unlock from a non-holder returning `False` — the exact signature a
  split across checkouts produces.
- **Removing the three `*_DB_PATH` env vars does NOT prevent SQLite fallback.** `sessions.py:43`
  has a module-dir default and `default_backend()` returns `sqlite` whenever `DATABASE_URL` is
  empty — two mountless machines would each boot their own ephemeral database and `/health` would
  report `ok`. The fix is pinning `SESSION_BACKEND`/`METRICS_BACKEND`/`VECTOR_STORE` so a missing
  DSN fails closed at construction. **Half closed by 11-02:** `-k fails_closed` asserts that a
  pinned Postgres backend with no `DATABASE_URL` raises, and a companion test pins the negative
  (unpinned + no DSN boots happily on container-local storage). That is a *property* test, not a
  progress gate — it passes against today's tree. The gate that the pins are actually **set in
  production** is still owed: the stateless arm of `test_local_store_paths_live_under_the_mount`,
  written in 11-03 and armed by 11-05.

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
| 11 | 2 of 5 (11-01, 11-02) | 150min | 75min |

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
- [Phase 11-03]: **A guard that skips is a guard that config deletion disarms.** Two deploy tests `pytest.skip()`d whenever `[[mounts]]` was absent, so removing the mount would have made them no-ops with CI still green. Both are now two-armed — they assert in *both* topologies and skip in neither. The old guard was fed the same scratch file as the new one and returned `Skipped` where the new one raises. Any future mount-conditional or DSN-conditional check should be written this way from the start.
- [Phase 11-03]: **Removing the `*_DB_PATH` vars does not close the SQLite fallback; the pins do.** `sessions.py` defaults its path to a file beside the module and the backend selector returns `sqlite` with no DSN, so a mount-less machine with an unset `DATABASE_URL` boots on container-local SQLite, `/health` reports `dependencies: "ok"` because SQLite is perfectly reachable, and the only difference on the wire is a class name nothing reads. `SESSION_BACKEND`/`METRICS_BACKEND`/`VECTOR_STORE` pinned makes it fail closed at store construction instead. This is the gate `-k fails_closed` deliberately does not provide.
- [Phase 11-03]: **Assert on the parsed `[env]` table, never the file text, when one key name is a substring of another.** `grep -c 'VECTOR_STORE' fly.toml` returns 1 on a file with no `VECTOR_STORE` key at all, because `VECTOR_STORE_PATH` contains it. The inverse also applies: the `-k runbook` guard deliberately *does* read the text, because a comment is precisely what it guards and `tomllib` discards comments.
- [Phase 11-03]: **A test that is red until an edit lands belongs in the task that makes the edit.** The runbook-staleness guard was written in Task 2, not Task 1, because Task 1's verify runs the whole file and would have ended red. Recording the red observation against `git show HEAD:fly.toml` is what makes an absence-asserting gate falsifiable.
- [Phase 11-03]: **Two more vacuous gates caught before running** — bringing this repo to eight across four phases. `PG_CONNECT_TIMEOUT >= 1` and `SESSION_BACKEND >= 1` in `docs/OPERATIONS.md` both already passed on the untouched tree. Replaced with prose-only greps (`grep -v '^|'`), an old-text-is-gone check, a same-paragraph co-occurrence check, and a same-line tie to `pin|cutover`. The rule: state the *measured* baseline in the gate, and if it is not zero, the `>= 1` form proves nothing.
- [Phase 11-03]: **Line-oriented gates need line-oriented prose.** `grep 'X' file | grep -c 'Y'` requires both tokens on one *physical* line, and 80-column reflow kept separating them. The sentence was rewritten to suit the gate rather than the gate weakened to suit the sentence.
- [Phase 11-01]: `check=ConnectionPool.check_connection` is **deliberately not used**, against RESEARCH's own Pattern 1. The check is a server round trip performed *during* checkout and the pool's `timeout` does not interrupt one in flight, so on a partitioned database it adds an unbounded cost to every checkout — on `/health`, the exact endpoint this phase is bounding. Staleness stays covered by the retry-once arm. Gated by `grep -c 'check_connection' src/research_agent/db.py` returning 0, with the reason in a comment so the omission does not read as an oversight.
- [Phase 11-02]: **A local Postgres was built to run the gated suite**, because Docker was unavailable and this phase's plans state explicitly that a green local run is not evidence. It found three `db.py` bugs, two of which no fake could have caught. The rule this establishes: for a phase whose claims are server-shaped, "the Postgres tests skipped locally" is an unverified result, not a pass.
- [Phase 11-02]: **The retry discriminator is the SQLSTATE, not the exception class.** Both obvious rules are wrong. "Any `OperationalError`" retries `QueryCanceled` (57014) and doubles the statement timeout that just fired. "Has a SQLSTATE means the server is alive" refuses to retry `AdminShutdown` (57P01), which is exactly what `pg_terminate_backend` sends. The second rule shipped and was caught only by the real server. `_connection_was_lost()` now retries SQLSTATE `None`, class `08`, and `57P01/02/03`.
- [Phase 11-02]: **Reads retry the whole statement; writes deliberately do not.** A client cannot distinguish "never arrived" from "committed, response lost", so a retried write is at-least-once — a duplicated run in `/metrics` or a `UniqueViolation` over a row that exists. The asymmetry is documented in `_read()` rather than left to be inferred.
- [Phase 11-02]: **`pool.check()` on the failure path is not the `check=` callback 11-01 rejected.** A provider terminates every idle connection at once, so a bare retry-once drew the next dead connection and still failed against a real server. `check()` replaces all broken idle connections, but runs *only* after one has been found dead — so 11-01's objection (a round trip on every checkout, including `/health`'s) does not apply and still stands.
- [Phase 11-02]: **`_probe`'s deadline bounds availability, not execution**, and the docstring says so precisely. A `ThreadPoolExecutor` bounds its *workers*, not its *queue*; abandoned probes against a persistently hung peer are reaped by `tcp_user_timeout`, not by the worker count. `future.cancel()` was deliberately not added so the documented mechanism stays the true one.
- [Phase 11-02]: **The skip-count invariant rises from 28 to 34**, and the operative gate is restated as (1) `0` skipped in CI under `REQUIRE_POSTGRES=1` — actually run, not predicted — and (2) locally, skips rise by exactly 6, each named in the summary. 11-05 Task 4 must mirror this into `11-VALIDATION.md`.
- [Phase 11-02]: Two acceptance greps again tripped on the prose explaining why the forbidden token was removed — the same tension 11-01 logged. Resolved the same way: keep the gate, reword the reason. This is now a repeat pattern and a plan author should expect it.
- [Phase 11-01]: `Database.close()` is a **claim release**, not a disposal, and is idempotent. `service.lifespan` closes sessions and metrics but never the memory store, and the contract suite closes after every parametrised case; a `close()` that disposed a shared pool would break the remaining holders, and a `ConnectionPool` cannot be reopened. `db.close_all_pools()` exists for the lifespan `finally` and is not wired yet — that is 11-02.
- [Phase 11-01]: RESEARCH's Pitfall 7 was **wrong in the safe direction**. `PoolTimeout`'s message is "couldn't get a connection after 0.50 sec", and `test_store_contract.py`'s `match="(?i)connect"` is a `re.search`, which "connection" satisfies. The test needed no edit; do not loosen it later on the strength of the prediction.
- [Phase 11-01]: The retry arm in `cursor()` can only fire on an exception raised at *checkout*. A `@contextmanager` that yields a second time after an exception is thrown in raises `RuntimeError: generator didn't stop after throw()`. This is the pre-existing shape, unchanged by the port — worth knowing before anyone "improves" it.
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
Stopped at: **Completed 11-03-PLAN.md — the deploy guards are armed and the runbook is honest.**
Three tasks, three commits (`9b4afe6`, `53fb6a0`, `1991f7d`). Both mount-conditional guards in
`tests/test_deploy_config.py` used to `pytest.skip()` when `[[mounts]]` was absent, so 11-05's
mount removal would have silenced them with CI green; both now assert in **both** topologies and
`grep -c 'pytest.skip'` is `1` (the `fly` fixture's legitimate no-`fly.toml` skip), down from `3`.
The stateless arm requires more than the absence of the `*_DB_PATH` keys — it requires
`SESSION_BACKEND=postgres`, `METRICS_BACKEND=postgres`, `VECTOR_STORE=pgvector`, asserted on the
parsed `[env]` table because `VECTOR_STORE_PATH` contains the string `VECTOR_STORE`. Two new
guards: `DATABASE_URL` must not appear in the committed `[env]`, and a `-k runbook` test keeps
`fly postgres create`/`attach` out of `fly.toml` (recorded red against `git show HEAD:fly.toml`).
Four falsification checks run against scratch files, all four observed failing, plus a passing
control; check 1 was also fed to the old guard, which returned `Skipped` where the new one raises
`AssertionError` — the disarm-by-deletion demonstrated rather than argued.
`fly.toml`'s footer, health-budget, `auto_stop_machines`, `primary_region` and concurrency
comments were rewritten for the external-Supabase path, and `docs/OPERATIONS.md` carries the
ordered cutover, the fail-closed pins, the start-clean tradeoff, the kept volume and SC-6's
four-way timeout semantics. **Every `fly.toml` change is a comment** — `git diff -U0 fly.toml`
shows no changed non-comment line, and `tomllib` confirms `min_machines_running == 1`, `mounts`
present and `SESSION_DB_PATH` in `[env]`. Suite **436 passed, 34 skipped** (+2 tests, skip count
unchanged); `ruff` clean.
**Owed to 11-05:** removing `[[mounts]]` is now a four-part change or the tests fail — the three
`*_DB_PATH` vars out, the three pins in, `min_machines_running` ≥ 2. And `11-VALIDATION.md`'s
skip-count invariant still says 28; it is 34.
Resume file: None

Superseded — previous session: **Completed 11-01-PLAN.md — `db.py` is pooled.** Three tasks, three commits
(`8c7a145`, `9e46158`, `5df970b`). `psycopg-pool==3.3.1` pinned and installed; five new env
readers (`PG_POOL_MIN_SIZE`, `PG_POOL_MAX_SIZE`, `PG_POOL_TIMEOUT`, `PG_STATEMENT_TIMEOUT`,
`PG_TCP_USER_TIMEOUT`); one `ConnectionPool` per DSN behind a claim-refcounted registry, shared
by all three stores; the RLock and single `_conn` deleted; `prepare_threshold=None`,
`statement_timeout`, `tcp_user_timeout`, keepalives and a `search_path` `configure` callback all
reaching the connection; `PoolTimeout`/`PoolClosed` re-raised ahead of the retry; DDL under
`pg_advisory_lock(3895545195)` on one connection with the unlock's result checked. `tests/test_db.py`
is new (27 tests, no server needed). Suite **415 passed, 28 skipped** against a 388/28 baseline —
skip count unchanged, so Postgres coverage was extended rather than disarmed. `ruff` clean.
`fly.toml` untouched. Both behavioural gates were mutated, observed red and reverted; the table
is in `11-01-SUMMARY.md` § Falsification Checks.
**Owed to 11-02:** `test_the_connection_recovers_from_being_dropped` reaches into `store.db._conn`,
which this plan deletes. It is Postgres-gated so it skips locally, but it **will fail in CI**.
Repairing it, wiring `close_all_pools()` into the lifespan, the `/health` per-probe deadline and
the real-server lock/pgvector tests are all 11-02's.
Resume file: None

Superseded — previous session: **Completed 10-05-PLAN.md — the phase gate battery.** Every gate in
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

- **A `@contextmanager` cannot retry from inside the caller's `with` body.** Yielding a second
  time after `gen.throw` raises `RuntimeError: generator didn't stop after throw()`, which fails
  the call *and* destroys the original exception. This is why `db.cursor()` retries only the
  checkout and `db._read()` owns the statement-level retry. Anyone "improving" the retry should
  read both docstrings first.

- **`HEALTH_PROBE_BUDGET` is a new tunable**, 3.0s default with a 0.1 floor, and it has no
  `fly.toml` entry on purpose — the default is the intended production value. 11-05 should
  confirm the resulting 9s ceiling against the real check timeout in `fly.toml`.

Next: **11-03** — guard the new deploy topology in `tests/test_deploy_config.py`, including the
stateless arm of `test_local_store_paths_live_under_the_mount`, which is the real gate that the
three backend pins are set in production. No deploy is pending — release v4 is current and was
re-verified live on 2026-08-05. `DATABASE_URL` provisioning is 11-04.
