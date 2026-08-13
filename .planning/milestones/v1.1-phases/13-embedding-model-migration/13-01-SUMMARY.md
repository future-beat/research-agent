---
phase: 13-embedding-model-migration
plan: 01
subsystem: database
tags: [migration, pgvector, owner-scoping, note-ttl, data-loss, gate-discipline]

# Dependency graph
requires:
  - phase: 12-caller-identity-session-ownership-bounded-stores
    provides: "owner on the sessions and notes schemas, SessionStore.create(owner=), the 7-day note TTL keyed on created_at, the FakeEmbedder/HAS_POSTGRES test idiom"
  - phase: 11-multi-machine-state-and-pooled-postgres
    provides: "The pooled db.Database that migrate.py drives through the store classes"
provides:
  - "migrate_notes inserts (text, embedding, owner, created_at) — nothing is orphaned to owner='' and no TTL is restarted"
  - "migrate_sessions passes owner=session.owner to create() and re-asserts it in the restoring UPDATE"
  - "Note dedup keyed on (text, owner, created_at) as a datetime, so the same text under two owners is two rows and a re-run recognises what it wrote"
  - "migrate_notes(table=, dimensions=) explicit parameters — waves 2–3 and the tests can target a scratch table without monkeypatching import-time constants"
  - "The TTL-expired sessions list() omits are counted against the raw table and printed"
  - "tests/test_migrate.py — the module's first-ever coverage, two Postgres-gated tests, five mutations recorded"
affects: [13-02, 13-03, 13-04, VALIDATION rows 1-2]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase (RESEARCH Package Legitimacy Audit: none)
  patterns:
    - "Timestamp identity across the sqlite/JSON->Postgres boundary is compared as a datetime, never as an epoch float: a ~1.8e9 epoch with microseconds exceeds float64's exact range and psycopg returns extract(epoch ...) as Decimal"
    - "Explicit table/dimensions parameters instead of module constants, so a 5-dim test can drive production code paths without reimport tricks"
    - "A dedup gate is only falsifiable on the second pass — a first pass into an empty table inserts everything whatever the key is"

key-files:
  created:
    - tests/test_migrate.py
  modified:
    - src/research_agent/migrate.py
    - docs/OPERATIONS.md

key-decisions:
  - "A missing or zero created_at migrates as epoch 0 — already expired under the note TTL — rather than as now(). That mirrors what the store itself does with pre-Phase-12 entries (they read as 0 and are swept); stamping them fresh would resurrect data the service had stopped serving."
  - "Expired sessions are still not migrated (the right call — a migration should not resurrect expired data) but the count is now printed. Silent omission and data loss are indistinguishable from the outside."
  - "The dedup key holds created_at as a datetime, not a rounded epoch. The first cut used round(epoch, 6) and would have failed to recognise rows it had just written, turning every re-run into a duplicate insert."
  - "migrate_notes gained keyword parameters rather than the tests monkeypatching VECTOR_DIMENSIONS: migrate.py binds that name at import, so a post-import monkeypatch changes nothing (RESEARCH Pitfall 5)."
  - "owner is written twice in migrate_sessions (create() kwarg and the restoring UPDATE) per the plan's belt-and-braces instruction. Consequence recorded honestly below: neither site is individually falsifiable, only their conjunction."
  - "The main() assertion in the round-trip test points --notes at a nonexistent file on purpose. main() reads the production VECTOR_DIMENSIONS at import; that assertion is about the CLI surface surviving, not the vector width."

# Metrics
duration: 41min
completed: 2026-08-06
---

# Phase 13 Plan 01: Repair and prove the legacy migration Summary

**One-liner:** `migrate.py`'s live data-loss bug is fixed — notes and sessions now carry `owner` and their original `created_at` instead of arriving orphaned with a restarted TTL — and the module has its first tests, with every gate observed red under mutation before it was trusted.

## What was built

### Task 1 — the repair (commit `6516c23`, plus follow-up fix `33bc377`)

`src/research_agent/migrate.py`, four repairs against RESEARCH §Migrate.py Forensics items 1–4:

1. **Notes carry owner and created_at.** The INSERT column list is now `(text, embedding, owner, created_at)`. The JSON entry's epoch float is bound as `datetime.fromtimestamp(ts, tz=timezone.utc)` for the TIMESTAMPTZ column. A missing/zero `created_at` migrates as epoch 0 — already expired under the 7-day TTL — with a comment saying why.
2. **Dedup is owner-aware.** The key is `(text, owner, created_at)`; the text-only `SELECT text FROM …` existing-set query is gone (grep count 1 → 0).
3. **Sessions carry owner.** `target.create(..., owner=session.owner)`, and `owner = %s` added to the restoring UPDATE.
4. **The expired-session skip is stated.** `source.count()` (raw table) minus `len(source.list(...))` (TTL-filtered) is printed as `N expired session(s) not migrated` when positive.

Testability: `migrate_notes(source_path, dry_run, table=PGVECTOR_TABLE, dimensions=VECTOR_DIMENSIONS)`. `main()` passes nothing, so the documented bare invocation and all four legacy flags are byte-compatible. The loud width-vs-dimensions `SystemExit` keeps its wording verbatim, now comparing against the parameter.

A follow-up commit (`33bc377`) changed the dedup key's timestamp half from `round(epoch, 6)` to the `datetime` itself. Two problems, one fix: psycopg returns `extract(epoch FROM …)` as a `Decimal`, which never compares equal to a Python float, and a ~1.8e9 epoch carrying microseconds needs 16 significant digits where float64 has ~15.95. Either would have made every re-run a duplicate insert — the exact failure dedup exists to prevent. `datetime.fromtimestamp` rounds to microseconds, which is precisely what timestamptz keeps, so both sides agree exactly.

### Task 2 — the proof (commit `91b59d1`)

`tests/test_migrate.py`, the module's first test file. `HAS_POSTGRES` guard from `db.postgres_configured()`, no conftest, dedicated table `migration_test_notes_legacy` (never the contract suite's `contract_test_notes`), uuid4-hex session ids and run id, everything dropped or deleted in teardown.

- **`test_migrate_preserves_owner_and_created_at`** — four JSON entries across owners `alice`, `bob`, `""`, including the same text under two owners, each with a distinct epoch hours in the past. Asserts per-row `(owner, text, epoch)` equality against the source (epoch to 1e-3), that exactly one row is `owner=''` (the one that started that way), that the newest migrated `created_at` is over a minute old — i.e. not `now()` — and then deletes bob's row and re-migrates to prove the dedup key.
- **`test_migrate_legacy_roundtrip`** — sqlite sessions (two live under distinct owners, one with `turns=2` from an `append_turn`, one aged 90 days by direct sqlite UPDATE), a sqlite runs row, and the JSON notes, migrated by the three `migrate_*` functions in the order `main()` calls them. Asserts session `owner`/`created_at`/`updated_at`/`turns`/`task` field equality, the expired session absent *and* announced, the run's `cost_usd`, note row-count, that a second pass copies zero of each and duplicates nothing, and that `main(["--dry-run", ...])` still prints its banner and returns 0.

## Gate discipline: five mutations, and one gate that was vacuous

Every gate was mutated before it was trusted. Baseline entering the phase: **`grep -rl migrate tests/` returned nothing — zero coverage**, so there was no prior green to compare against; the mutation column is the whole evidence.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| A | Drop `owner` from the notes INSERT column list | **RED** (both tests) | `AssertionError: 4 notes migrated to owner='' (belonging to nobody)` / `assert 4 == 1`; round trip also red on idempotency `assert (3, 1) == (0, 4)` |
| B | Drop the `created_at` binding, letting the column default to `now()` | **RED** (both tests) | `assert 1785951906.849466 < (1785951906.849955 - 60)` — the TTL restart, caught by "the newest migrated note is an hour old" |
| C | Drop `owner=session.owner` from `create()` only | **GREEN — did not fail** | see below |
| C′ | Drop `owner` from `create()` **and** the restoring UPDATE | **RED** (round trip) | `AssertionError: assert '' == 'alice'` on the migrated session's owner |
| D | Delete the `expired session(s) not migrated` print | **RED** (round trip) | `assert '1 expired session(s) not migrated' in ''` |
| E | Revert the dedup key to text alone | **GREEN at first — see below**, then **RED** | `assert (0, 4) == (1, 3)` |

All mutations reverted; the tree is byte-identical to the committed code (`git diff` clean after each revert, final `ruff check src tests` passes).

**Mutation C is honest redundancy, not a caught bug.** The plan asked for belt and braces — `create(owner=)` plus `owner = %s` in the restoring UPDATE — and the consequence is that neither line is individually falsifiable: removing either one leaves observable behaviour unchanged, because the other still writes the column. That is what redundancy *means*, and it is different from a vacuous gate: C′ proves the test catches actual owner loss. Recorded rather than papered over, because "mutation observed red" would have been a false claim for C on its own.

**Mutation E is a gate that was genuinely vacuous, and was fixed.** The first version of the dedup assertion checked that the same text under two owners produced two rows. Structurally sensible, and green under a text-only key — because on a first pass into an empty table the `existing` set is empty, so both rows insert whatever the key is. The key only bites on the second pass. The gate now deletes bob's row and re-migrates: owner-aware, exactly that one row returns; keyed on text alone, alice's identical text reads as "already present" and bob's note is skipped forever — one owner's data made permanently unrecoverable because another owner wrote the same sentence. **This is the fourteenth vacuous gate found, and the second consecutive phase where a structurally sensible assertion was blind to the exact mutation it existed to catch.** The lesson generalises: an idempotency or dedup gate that only runs once proves nothing about the key.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| `grep -c "owner, created_at" src/research_agent/migrate.py` | 0 | 4 |
| `grep -c "owner=session.owner" src/research_agent/migrate.py` | 0 | 1 |
| `grep -c "SELECT text FROM" src/research_agent/migrate.py` (text-only dedup) | 1 | 0 |
| `grep -rl migrate tests/` | 0 files | `tests/test_migrate.py` |
| `inspect.signature(migrate_notes)` has `table` and `dimensions` | no | yes |
| `python -m research_agent.migrate --dry-run` banner + exit 0 | prints, 0 | prints, 0 (unchanged) |
| `pytest tests/test_migrate.py` armed (:54329) | file absent | **2 passed** |
| `ruff check src tests` | clean | clean |
| Full suite, plain | 527 passed / 47 skipped | **527 passed / 49 skipped** |
| Full suite, armed (:54329) | 573 passed / 1 skipped | **575 passed / 1 skipped** |

**Delta fully explained.** Collected 574 → 576, +2 in both arms — the two new tests and nothing else. The armed run gains both as passes. The plain run gains both as **skips**, each reporting `DATABASE_URL is not set`, which is the correct and only honest behaviour: these tests assert field-level fidelity of rows written to Postgres and cannot be simulated. **A green plain run is therefore not evidence for this plan; the armed run is.** The two new plain skips are the justification for 47 → 49; no pre-existing test changed state.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — Bug] The dedup key's epoch comparison could not match rows it had just written**
- **Found during:** Task 2, first run of `test_migrate.py`
- **Issue:** Task 1 implemented the plan's instruction literally — "round the epoch comparison to microseconds". `extract(epoch FROM created_at)` returns a `Decimal` from psycopg, so `round(Decimal, 6)` never equals `round(float, 6)`; the test failed with `TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'`. Casting to float would have papered over the type error while leaving a precision hazard: 1.8e9 with six decimals needs 16 significant digits and float64 carries ~15.95, so microsecond-level equality was not reliably decidable in float at all. The consequence in production is a re-run duplicating every note.
- **Fix:** Key on the `datetime` on both sides — `SELECT text, owner, created_at` and `datetime.fromtimestamp(ts, tz=timezone.utc)` — which agrees exactly at timestamptz's own precision.
- **Files modified:** `src/research_agent/migrate.py`
- **Commit:** `33bc377`

**2. [Rule 2 — Missing critical coverage] The dedup gate the plan specified was vacuous**
- **Found during:** Task 2, mutation E
- **Issue:** The plan's acceptance criterion — "assert the same-text/two-owners pair produced two rows" — is green under a text-only dedup key, because the first pass inserts both regardless. T-13-03 (cross-tenant elevation via owner-blind dedup) would have shipped ungated.
- **Fix:** Added a delete-and-re-migrate phase to `test_migrate_preserves_owner_and_created_at` that exercises the key on the second pass, where it actually applies. Mutation E then goes red.
- **Files modified:** `tests/test_migrate.py`
- **Commit:** `91b59d1`

**3. [Rule 2 — Doc correctness, standing instruction] OPERATIONS.md said the migration path was merely unexercised**
- **Found during:** post-task doc sweep
- **Issue:** `docs/OPERATIONS.md` § Starting clean said `migrate.py` "has not been run against this data", inviting the reader to assume the code was fine and only the data unverified. The code was not fine.
- **Fix:** Records the bug, the repair, the new test coverage, and the narrower caveat that genuinely remains (proven about the code, still never run against the volume).
- **Files modified:** `docs/OPERATIONS.md`
- **Commit:** `7b8b312`

### Departure from the plan's written approach

The plan's Task 2 text debated how to drive `main()` under a 5-dimensional fixture and concluded: call the three `migrate_*` functions in sequence and reserve one thin `main(["--dry-run", ...])` assertion for the banner and exit code. That is what was implemented, with `--notes` pointed at a nonexistent path so `main()`'s dimension-sensitive branch returns early — noted here only because the plan left the sentence mid-argument with itself.

**README.md was reviewed and needs no change from this wave.** Its one migration-adjacent limitation — "Changing embedding model means a new pgvector table … the dimension check fails loudly but can't migrate for you" — is still true today; it is waves 2–3 that falsify it, and rewriting it now would be a claim ahead of the code.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-13-01 | mitigate | **Closed.** `owner` and `created_at` carried explicitly; mutations A and B both observed red. |
| T-13-02 | mitigate | **Closed.** Expired-session count printed; mutation D observed red. |
| T-13-03 | mitigate | **Closed, after the gate was repaired.** Dedup keys on `(text, owner, created_at)`; mutation E red only after the second-pass assertion was added. |
| T-13-SC | accept | No packages installed. Confirmed: `pyproject.toml` untouched this plan. |

No new threat surface: this plan adds no network endpoint, no auth path, and no schema change. It removes a trust-boundary defect.

## Known Stubs

None.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `6516c23` | fix | Carry owner and created_at through the legacy migration |
| `33bc377` | fix | Key note dedup on the timestamp itself, not an epoch float |
| `91b59d1` | test | First coverage for the legacy migration, mutation-falsified |
| `7b8b312` | docs | OPERATIONS: the migration path is proven now, and says what it cost |

## Self-Check: PASSED

All four claimed files exist on disk; all four claimed commits resolve in `git log`. Working tree clean apart from this summary. Both mutation reverts confirmed by `ruff check src tests` and a green armed run on the final tree.
