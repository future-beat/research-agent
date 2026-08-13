---
phase: 11-multi-machine-state-and-pooled-postgres
plan: 03
subsystem: deploy-config
tags: [fly, deploy-guard, supabase, runbook, documentation, health-check]

# Dependency graph
requires:
  - phase: 11-01
    provides: "The pool env readers whose semantics OPERATIONS now documents: PG_POOL_MIN_SIZE/MAX_SIZE/TIMEOUT, PG_STATEMENT_TIMEOUT, PG_TCP_USER_TIMEOUT"
  - phase: 11-02
    provides: "HEALTH_PROBE_BUDGET and the measured 9s /health ceiling that fly.toml's comment now states"
provides:
  - "Two-armed topology guards: deleting [[mounts]] flips them to their second arm instead of silencing them"
  - "A stateless arm that requires SESSION_BACKEND/METRICS_BACKEND/VECTOR_STORE pinned -- the gate that the production pins are actually set, which -k fails_closed deliberately does not prove"
  - "A guard that DATABASE_URL never lands in the committed [env]"
  - "A -k runbook guard keeping `fly postgres create`/`attach` out of fly.toml"
  - "The Supabase cutover sequence, in both fly.toml's footer and docs/OPERATIONS.md, with the volume kept"
  - "SC-6: four-way timeout semantics in the env table and in prose"
affects: [11-04, 11-05, phase-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-armed guard: assert in both topologies rather than skip in one, so deleting config cannot disarm the check"
    - "Assert on the parsed [env] table, never the file text, when one key name is a substring of another"

key-files:
  created: []
  modified:
    - tests/test_deploy_config.py
    - fly.toml
    - docs/OPERATIONS.md
    - README.md

key-decisions:
  - "The topology itself is untouched. `git diff -U0 fly.toml` shows no changed line that is not a comment; mount, the three *_DB_PATH vars and min_machines_running = 1 all survive to 11-05."
  - "Arm (b) of the store-paths guard requires the three backend pins, not just the absence of the local paths. Removing the paths alone leaves the SQLite fallback reachable, and that failure is invisible: /health reports ok because SQLite is perfectly reachable."
  - "The runbook-staleness test was written in Task 2, with the edit that makes it green, not in Task 1 -- Task 1's verify runs the whole file and it would have ended red."
  - "The plan's SC-6 gate was replaced because the original (`PG_CONNECT_TIMEOUT >= 1`) already passed on the untouched tree."
  - "README's `No connection pool.` limitation was removed as well as the two the plan named -- 11-01 falsified it and the plan's own task title is 'the README claims the phase falsifies'."

requirements-completed: []

# Metrics
duration: 50min
completed: 2026-08-05
---

# Phase 11 Plan 03: Arming the guards and correcting the runbook Summary

**Two deploy guards that `pytest.skip()`d whenever `[[mounts]]` was absent — so plan 11-05's mount removal would have turned them into no-ops with CI still green — now assert in both topologies, and the stateless arm demands the three Postgres backend pins that are the difference between a missing DSN failing loudly and each machine quietly serving its own container-local SQLite.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- **The disarm-by-deletion hole is closed.** `grep -c 'pytest.skip' tests/test_deploy_config.py` went `3 → 1`; the survivor is the `fly` fixture's legitimate no-`fly.toml` skip. Both guards now name the topology they are guarding and assert in each direction.
- **The stateless arm asks for more than the plan's predecessor did.** Absence of the `*_DB_PATH` keys is arm (a); arm (b) requires `SESSION_BACKEND=postgres`, `METRICS_BACKEND=postgres`, `VECTOR_STORE=pgvector`. This is the gate 11-02 flagged as missing — `-k fails_closed` proves the pins *work*, nothing proved they are *set*.
- **Neither `fly.toml` nor `OPERATIONS.md` now instructs an operator to run `fly postgres create`.** Both counts are 0, from `1` and `2` respectively, and a `-k runbook` test keeps `fly.toml` that way.
- **The health-budget comment was wrong by a factor of two and is now honest in both directions** — it stated a typical figure as if it were a bound, and the arithmetic it used didn't even hold for the typical case.
- **The topology is byte-identical.** Every `fly.toml` change is a comment.

## Task Commits

1. **Task 1: Two-armed topology guards, the pin arm, the secret guard** — `9b4afe6` (test)
2. **Task 2: fly.toml's runbook, health budget, region and concurrency comments + the `-k runbook` guard** — `53fb6a0` (docs)
3. **Task 3: OPERATIONS rewritten for Supabase, SC-6 timeout semantics, README corrections** — `1991f7d` (docs)

## Falsification checks

An unmutated green is not evidence. Each guard was run against a scratch `fly.toml` violating exactly one arm. The guards take the parsed table as their argument, so each scratch file went through the same `tomllib` load the fixture uses — no test code was bypassed. The real `fly.toml` was never touched (`git status --porcelain fly.toml` empty throughout).

| # | Scratch file | Guard | Observed |
|---|---|---|---|
| 1 | no `[[mounts]]`, `min_machines_running = 1`, pins present | `test_the_machine_count_matches_the_topology` | **FAILS** — *"min_machines_running=1 with no volume…"* |
| 2 | no `[[mounts]]`, 2 machines, pins present, `*_DB_PATH` left behind | `test_the_store_paths_match_the_topology` | **FAILS on arm (a)** — names all three stray keys |
| 3 | no `[[mounts]]`, 2 machines, no paths, **no pins** | `test_the_store_paths_match_the_topology` | **FAILS on arm (b)** — *"SESSION_BACKEND must be pinned to 'postgres' (found None)"* |
| 4 | `DATABASE_URL` smuggled into `[env]` | `test_the_database_url_is_not_committed` | **FAILS** |
| — | correct stateless file (no mount, 2 machines, no paths, pins) | both topology guards | **PASS** — the control, so the guards are not simply always-red |

**Check 1 is the one that proves the plan's premise.** The same scratch file was fed to the *old* guard, loaded from `git show HEAD:tests/test_deploy_config.py`:

```
test_a_volume_means_a_single_machine -> Skipped: no volume; the app is stateless and can scale out
```

Old code: `Skipped`. New code: `AssertionError`. That is the disarm-by-deletion, demonstrated rather than argued.

## The `-k runbook` test, red against HEAD

The plan required this recorded rather than asserted. Pointing the new guard at `git show HEAD:fly.toml`:

```
RED against HEAD (good): fly.toml's comments still tell an operator to run
`fly postgres create`, which provisions unmanaged Fly Postgres -- unsupported by Fly.
```

Green against the edited file. A guard that asserts a string is *absent* is worthless unless the string was provably present, and it was.

## The SC-6 gate substitution, and why

`11-VALIDATION.md` proposed `grep -c 'PG_CONNECT_TIMEOUT' docs/OPERATIONS.md >= 1` for SC-6. **That returned `1` on the untouched tree** — the variable already had a table row. The gate would have passed with no work done at all, which is this repo's recurring vacuous-gate failure and the reason the plan replaced it with three falsifiable parts:

| Substitute gate | Baseline | Result | Why it is falsifiable |
|---|---|---|---|
| `grep -v '^\|' OPERATIONS.md \| grep -c PG_POOL_TIMEOUT >= 1` | `0` | **2** | Excludes table rows, so only prose satisfies it |
| `PG_CONNECT_TIMEOUT`'s row text ≠ *"Seconds before a connection attempt gives up"* | present | **0 occurrences** | The old text is gone, so the row was genuinely rewritten |
| One paragraph naming `PG_CONNECT_TIMEOUT`, `PG_POOL_TIMEOUT` and `HEALTH_PROBE_BUDGET` | `0` | **2 paragraphs** | A table cannot satisfy it; the distinction has to be written out |

The same correction was applied to the `SESSION_BACKEND` gate, which the plan had already caught: it returns `1` today (the env table at `docs/OPERATIONS.md:143`), not `0`, so the `>= 1` form would have passed without the pins being documented anywhere. It is now `>= 2` **plus** a same-line tie to `pin|cutover`. Final: count `2`, tied occurrences `2`.

And per the plan, line 143's default column — which read "follows `DATABASE_URL`" — was updated. That becomes stale for production the moment the pins ship, because production no longer *follows* the DSN, it *requires* it. The `VECTOR_STORE` row above it carried the identical stale claim and was corrected with it.

## The single surviving `research_agent.migrate` mention

`grep -c 'research_agent.migrate' docs/OPERATIONS.md` went `2 → 1`, and `grep 'research_agent.migrate' … | grep -c 'not exercised'` returns `1` — i.e. the survivor *is* the deliberate note:

> `python -m research_agent.migrate` is therefore deliberately **not exercised** by this cutover. A later phase that needs a real migration must not assume that path is proven.

The two removed lines were `fly ssh console … "python -m research_agent.migrate --dry-run"` and its non-dry-run twin, sitting inside a copy-pasteable code block. This cutover starts against an empty database; leaving runnable migration commands in a runbook nobody intends to run is how someone runs them.

## Measured / verified

| Check | Baseline | Now |
|---|---|---|
| `grep -c 'pytest.skip' tests/test_deploy_config.py` | 3 | **1** |
| `grep -c 'min_machines_running' tests/test_deploy_config.py` | 1 | **3** |
| `grep -c 'SESSION_BACKEND' tests/test_deploy_config.py` | 0 | **2** |
| `grep -c 'fly postgres create' fly.toml` / `attach` | 1 / 2 | **0 / 0** |
| `grep -c 'PG_POOL_TIMEOUT' fly.toml` / `HEALTH_PROBE_BUDGET` | 0 / 0 | **2 / 1** |
| `grep -c 'sslmode=require' fly.toml` / `pooler.supabase.com` | 0 / 0 | **2 / 1** |
| `grep -c 'fly postgres create' docs/OPERATIONS.md` | 2 | **0** |
| `grep -c 'PG_POOL_TIMEOUT' docs/OPERATIONS.md` | 0 | **3** (2 in prose) |
| `PG_POOL_MIN_SIZE` / `MAX_SIZE` / `PG_STATEMENT_TIMEOUT` / `PG_TCP_USER_TIMEOUT` / `HEALTH_PROBE_BUDGET` | all 0 | **1 / 2 / 2 / 2 / 2** |
| `grep -c 'Supabase' docs/OPERATIONS.md` / `README.md` | 0 / 0 | **8 / 4** |
| `grep -c 'DEMO_DAILY_USD_CAP' docs/OPERATIONS.md`, tied to `32` | 1, 0 | **2, 1** |
| Topology unchanged (`tomllib`: `min_machines_running == 1`, `mounts` truthy, `SESSION_DB_PATH` in `env`) | — | **`topology unchanged`** |
| `git diff -U0 fly.toml` non-comment changed lines | — | **0** |

- `.venv/bin/pytest tests/test_deploy_config.py -v` — **12 passed, 0 skipped, 0 failed**, at the end of each task
- `.venv/bin/pytest` (bare) — **436 passed, 34 skipped**. Passing rose by exactly 2 (the runbook and `DATABASE_URL` guards); **the skip count is unchanged at 34**, as it must be — this plan adds no Postgres-gated test
- `.venv/bin/ruff check .` — exits 0
- Collected total **470**, which is the figure README and OPERATIONS now state

## The health-budget correction

The old comment claimed the 15s check timeout "allows for three store probes each bounded by `PG_CONNECT_TIMEOUT` (3s)". Two things were wrong and the plan was right to insist both be fixed rather than one:

1. **The arithmetic.** The pre-pool `cursor()` made *two* 3s connect attempts per probe, so three probes could cost **18s against a 15s timeout** — the check expires and both machines restart for a fault a restart cannot fix.
2. **The category.** Replacing it with "3 × `PG_POOL_TIMEOUT` = 6s" would have been a narrower version of the same error. A checkout timeout bounds a checkout. A warm pool holding a connection to a peer that has gone away returns from checkout in ~0ms and then blocks on a socket, with `PG_POOL_TIMEOUT` already spent.

The comment now carries both numbers, labelled: ~6s typical for a cold pool, and **9s as the ceiling** (3 × `HEALTH_PROBE_BUDGET`), enforced by 11-02's per-probe wall-clock deadline and holding cold, warm or partitioned — with 11-02's measured 0.32s-vs-31.4s cited.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Accuracy] README's "No connection pool" limitation was falsified by 11-01 and still stood**
- **Found during:** Task 3
- **Issue:** `README.md:206` read *"**No connection pool.** One lock-guarded Postgres connection per machine"*. Plan 11-01 replaced exactly that with a `psycopg_pool.ConnectionPool`. The plan named lines ~187 and ~205 but its own task title is "the README claims the phase falsifies", and this is one.
- **Fix:** Removed, and replaced with two limitations that *are* true after this phase — the single-region free-tier database, and the spend-cap overshoot that two machines widen.
- **Files modified:** `README.md`
- **Commit:** `1991f7d`

**2. [Rule 1 — Accuracy] The stale test count appeared in three places, not one**
- **Found during:** Task 3
- **Issue:** The plan asked for `README.md:13`. `README.md:161` and `docs/OPERATIONS.md`'s CI block carried the same `364`. Fixing one of three leaves two verified-false claims of the exact class Phase 10 existed to remove.
- **Fix:** All three set to `470`, the collected total.
- **Files modified:** `README.md`, `docs/OPERATIONS.md`
- **Commit:** `1991f7d`

**3. [Rule 2 — Missing] The `VECTOR_STORE` table row carried the same stale default as the row the plan named**
- **Found during:** Task 3
- **Issue:** The criterion targeted `docs/OPERATIONS.md:143` ("follows `DATABASE_URL`"). Line 142's `VECTOR_STORE` row said the same thing and becomes stale for the same reason at the same moment.
- **Fix:** Both rows now read "follows `DATABASE_URL` locally; **pinned** in production".
- **Files modified:** `docs/OPERATIONS.md`
- **Commit:** `1991f7d`

---

**Total deviations:** 3 auto-fixed, all documentation accuracy. No architectural decisions, no blockers, no authentication gates.

## Issues Encountered

**A grep gate tripped on line wrapping, twice.** `grep 'DEMO_DAILY_USD_CAP' … | grep -c '32'` requires both tokens on one *physical* line, and prose reflowed at 80 columns kept separating them. The sentence was rewritten until they shared a line. Worth recording because it is a real property of line-oriented gates and the fix is to write the sentence for the gate, not to weaken the gate.

**No `fly.toml` value was changed, and this was verified mechanically rather than by eye:** `git diff -U0 fly.toml | grep -vE '^[+-]\s*#'` returns nothing, and the `tomllib` assertion on `min_machines_running`, `mounts` and `SESSION_DB_PATH` prints `topology unchanged`. The 82-line insertion is entirely comments.

## What is guarded and what still is not

Guarded now: the mount/machine-count pairing in both directions, the pins whenever the mount is absent, `DATABASE_URL` staying out of the committed file, and `fly.toml`'s footer staying off the unsupported command.

**Not guarded:** `docs/OPERATIONS.md` has no equivalent of the `-k runbook` test — nothing stops the operator runbook drifting back. It is prose in a file no test reads. Worth a docs guard in a later phase; deliberately not added here, since inventing an unplanned doc-linting test at the end of a plan is how gates get written vacuously.

**Not proved:** every stateless-arm assertion has been exercised only against scratch files. The real `fly.toml` still has its mount, so the second arm of both guards is live-fire-tested for the first time in 11-05. That is the intended order — the guards were written first precisely so they are already in place when the topology moves.

## User Setup Required

None. `DATABASE_URL` provisioning is 11-04; the cutover this plan documents is executed in 11-05.

## Next Phase Readiness

Ready for 11-04 (provision Supabase, real DSN) and 11-05 (apply the topology). Notes forward:

1. **11-05's `fly.toml` edit is now constrained by tests.** Removing `[[mounts]]` without also removing the three `*_DB_PATH` vars, adding the three pins and raising `min_machines_running` to ≥ 2 fails `tests/test_deploy_config.py`. That is the intent: the four changes are one change.
2. **`11-VALIDATION.md`'s skip-count invariant still says 28.** 11-02 flagged this; it is 34, and this plan leaves it at 34. Amend in 11-05 Task 4.
3. **The cutover order lives in two places now** — `fly.toml`'s footer and `docs/OPERATIONS.md`. They were written to agree; 11-05 should re-read both before executing rather than working from memory of one.

## Self-Check: PASSED

All four modified files present (`tests/test_deploy_config.py`, `fly.toml`, `docs/OPERATIONS.md`, `README.md`). All three task commits resolve: `9b4afe6`, `53fb6a0`, `1991f7d`.

---
*Phase: 11-multi-machine-state-and-pooled-postgres*
*Completed: 2026-08-05*
