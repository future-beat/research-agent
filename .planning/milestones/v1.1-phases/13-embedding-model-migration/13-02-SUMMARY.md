---
phase: 13-embedding-model-migration
plan: 02
subsystem: database
tags: [migration, pgvector, recall, hnsw, exact-scan, golden-set, gate-discipline]

# Dependency graph
requires:
  - phase: 13-embedding-model-migration
    plan: 01
    provides: "a repaired migrate.py that carries owner/created_at, and migrate_notes(table=, dimensions=) so a 5-dimensional scratch table can drive production code"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    provides: "owner on the notes schema, the 7-day note TTL keyed on created_at, the FakeEmbedder/HAS_POSTGRES test idiom"
  - phase: 11-multi-machine-state-and-pooled-postgres
    provides: "Database.transaction() — without it there is no transaction for SET LOCAL enable_indexscan to be local to"
provides:
  - "src/research_agent/recall_golden.py — a frozen, tie-free golden recall set with owner-scoped queries, an exact-scan runner, an indexed runner, recall_delta, and assert_tie_free"
  - "`python -m research_agent.migrate embeddings copy --from OLD --to NEW [--dry-run]` — server-side INSERT..SELECT, non-destructive, idempotent, self-checking on four fidelity numbers"
  - "memory.validate_table_name() — one table-name rule, now shared by the store and the CLI"
  - "SC-5's copy half: zero golden delta under exact scan, proven, with the HNSW index outside the claim and separately sanity-checked"
affects: [13-03, 13-04, 13-05, VALIDATION rows golden_set / copy_fidelity / copy_recall_identical / index_sanity]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase (RESEARCH Package Legitimacy Audit: none)
  patterns:
    - "Tie-freedom is checked over the rows a query can RETURN (floor-passing), not over every row: with 5-dim binary vectors, any two notes sharing no word with the query both sit at similarity 0, so a global tie-freedom requirement is not strict but impossible"
    - "A copy command that self-checks makes some downstream gates unreachable — the command's own nonzero exit fires before the test's later assertion. Worth knowing when reading a mutation table"
    - "A recall-equality assertion needs an anti-vacuity floor: two empty result sets are also identical"

key-files:
  created:
    - src/research_agent/recall_golden.py
  modified:
    - src/research_agent/migrate.py
    - src/research_agent/memory.py
    - tests/test_migrate.py

key-decisions:
  - "assert_tie_free checks only rows at or above each query's min_similarity, which is a deliberate departure from the plan's 'unfiltered' wording. Unfiltered is unsatisfiable over this vocabulary and, more importantly, is not the property that matters: rows the query cannot return cannot affect its order."
  - "The golden set's below-floor query is 'chroma retry' under owner '' — neither word appears under that owner, so the emptiness is a property of the corpus rather than of an artificially raised floor. It doubles as the tenancy gate: a copy that loses `owner` drops alice's and bob's rows into that bucket and it stops being empty."
  - "main() dispatches on the literal token `embeddings` rather than using a top-level subparser set. A required subparser would have turned the invocation OPERATIONS.md documents into an error about a missing subcommand."
  - "--dry-run creates nothing at all, not even the target table. It asks to_regclass whether the target exists and treats every source row as pending when it does not, rather than running the DDL to make its own counting query legal."
  - "The copy refuses an empty source. A copy of nothing satisfies every fidelity check there is."
  - "The table-name rule moved out of PgVectorMemoryStore.__init__ into module-level validate_table_name(), which the constructor now calls. Two callers (env var, operator argv) and one rule."
  - "The index-sanity check lives in its own test and asserts set-equality only, with a docstring saying it is scale-bounded and must never be promoted into the recall claim."

# Metrics
duration: 55min
completed: 2026-08-06
---

# Phase 13 Plan 02: The golden recall set and the copy-only migration Summary

**One-liner:** `embeddings copy` moves a pgvector corpus server-side and proves it did nothing to recall — byte-identity by SQL join, golden-query identity under exact scan, and the approximate HNSW index deliberately outside the claim and checked separately.

## What was built

### Task 1 — `src/research_agent/recall_golden.py` (commit `e7e2c06`)

A production-importable module (the CLI and the tests both use it; it takes an `Embedder` as an argument and imports no test code). Importable with neither `DATABASE_URL` nor `VOYAGE_API_KEY` set — verified with `env -u`.

**The corpus:** 12 notes over the test embedder's five-word vocabulary, across owners `alice` (5), `bob` (4) and `""` (3). Per-owner the vocabulary *sets* are pairwise distinct, because the embedder maps a set to a point and two notes with the same set are the same point. `"chroma retry"` is stored under **both** alice and bob — the tenancy probe.

**The queries:** 8, covering per-owner relevance ordering, the tenancy probe asked once per owner, a query that must return `[]`, and the unowned bucket returning rows.

**The runners:** `exact_scan_results` opens a `Database.transaction()`, issues `SET LOCAL enable_indexscan = off`, and runs the production `SELECT` shape minus the TTL predicate (the golden rows are minutes old, so the predicate is vacuous, and leaving it in would make every comparison depend on the wall clock). `indexed_results` runs the same query through the planner, for the separate sanity check only. `recall_delta` is store-agnostic — it speaks `(text, score)` pairs and knows nothing about Postgres.

**`seed`** writes through a direct INSERT carrying `(text, embedding, owner, created_at)` on a descending one-minute ladder, not through `store.add()`, whose `now()` stamping and TTL sweep would make the join key non-reproducible. The DDL still goes through `PgVectorMemoryStore` so the measured table is the production schema.

**`assert_tie_free`** is the module's real guarantee and the reason the plan called it not-optional. Distinct vocabulary sets do **not** preclude ties: similarity depends only on (overlap, size), so `{chroma,retry}` and `{chroma,voyage}` sit at exactly the same distance from `"chroma"`. Every golden query was hand-verified tie-free offline before the module was committed; two candidate queries (`"langgraph chroma supervisor"@bob` and `"retry"@bob`) were **discarded during design** because they tied two of bob's notes at 0.4082 and 0.7071 respectively.

### Task 2 — `embeddings copy` (commit `5ab6a6e`)

```
python -m research_agent.migrate embeddings copy --from OLD --to NEW [--dry-run]
```

- **Server-side.** One `INSERT INTO {target} (text, embedding, owner, created_at) SELECT o.text, o.embedding, o.owner, o.created_at FROM {source} o WHERE NOT EXISTS (…)`. Embeddings never become Python floats, so byte-identity is by construction rather than by `repr()` round-tripping.
- **Idempotent on `(text, owner, created_at)`** — deliberately the same key the fidelity join uses, so a row the copy skipped is a row the check can match. `id` is BIGSERIAL and left behind.
- **Self-checking.** After a real copy it prints four numbers and exits nonzero on any of them: row counts, matched-of-source, unmatched (LEFT JOIN, target side NULL) and byte-differing embeddings (`o.embedding::text IS DISTINCT FROM n.embedding::text`). The matched-of-source number is RESEARCH's A3 guard: a duplicate key fans the join out and every other number is then measured over the wrong row set.
- **Non-destructive.** Zero statements against `--from`; no `DROP` anywhere in the file (grep count 0, baseline 0 — stated as the weak check it is; the real gate is a full-contents comparison in the tests).
- **Dimension derived from the source** via `vector_dims(embedding)`, and an empty source is refused loudly.
- **Table names validated** through `memory.validate_table_name()`, which the store's constructor now also calls — one rule, two callers, no second hand-typed copy of it.

The legacy surface is byte-compatible: `main()` claims the token `embeddings` and hands everything else to the unchanged legacy parser. 13-01's round-trip test, which asserts the bare `--dry-run` banner and exit code, stayed green throughout.

### Task 3 — the four gates (commit `9262aeb`)

Dedicated tables `migration_test_notes_old` / `migration_test_notes_new`, dropped on setup *and* teardown (Pitfall 7), never the contract suite's `contract_test_notes`.

| Test | What it claims |
|------|----------------|
| `test_golden_set_tie_free_and_owner_scoped` | `assert_tie_free` passes; alice and bob each see only their own neighbourhood around the shared text (`{alice} ∩ {bob} == {"chroma retry"}`); the unowned bucket sees only its own notes and returns `[]` for the tenancy query |
| `test_copy_fidelity` | counts, unmatched, byte-diff, joined == source; a second copy is a no-op; the source's **full contents including embeddings** are unchanged after the copy AND after a `--dry-run` |
| `test_copy_recall_identical` | `recall_delta` over all 8 golden queries is `[]`, ordered and score-bearing — after an anti-vacuity assertion that the queries actually answered |
| `test_index_sanity` | the indexed path equals the exact scan **as a set**, in its own test, labelled scale-bounded |

## Gate discipline: six mutations, all red

Fourteen vacuous gates across six phases, and 13-01's own was specified by its plan. Baseline before mutating: **4 passed** on `-k "golden_set or copy_fidelity or copy_recall_identical or index_sanity"` against `:54329`.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| M1 | After the copy, `UPDATE {target} SET embedding = '[1,1,1,1,1]'` on one row | **RED** (both tests) | `test_copy_fidelity:414` `assert byte_diff == 0` → `assert 1 == 0`; `test_copy_recall_identical` delta of 3 queries, `('chroma retry', 1.0)` → `('chroma retry', 0.632…)` |
| M2 | Drop `owner` from the copy column list | **RED** (all three copy tests) | The command's own gate fires first: `matched 0 of 12`, `FIDELITY FAILED`, so `assert main(...) == 0` fails at `:386`/`:441`/`:469` |
| M2′ | M2, with the return-code assertion relaxed so the golden comparison is reached | **RED** | `assert golden.recall_delta(old, new) == []` — **all 8** queries deltaed, first extra item `{'query': "'chroma retry'@''", 'old': [], 'new': [('chroma retry', 1.0), ('chroma retry', 1.0), ('chroma supervisor', 0.5)]}` — i.e. alice's and bob's rows both surfacing in the unowned bucket |
| M3 | Drop `created_at` from the copy column list (target defaults `now()`) | **RED** | `unmatched 12`, `matched 0 of 12`, `FIDELITY FAILED`, `test_copy_fidelity:386` |
| M4 | `DELETE` one row from the new table before the comparison | **RED** | `test_copy_recall_identical:456`, 2 queries deltaed; the `top_k` boundary row `('langgraph chroma voyage supervisor', 0.3535…)` promoted into the new results |
| M5 | Two same-vocab notes under alice in `GOLDEN_NOTES` | **RED** | `test_golden_set_tie_free_and_owner_scoped:357` — `ValueError: … 'chroma retry' and 'retry chroma' both score 1.0 -- the order between them is arbitrary` (two such lines) |
| M6 | Drop the `NOT EXISTS` skip clause | **RED** | `test_copy_fidelity:416` — the **second** copy: `row counts differ: 12 vs 24`, `24 joined row(s) for 12 source row(s): (text, owner, created_at) is not unique` |

All reverted; `git status` clean after each; `ruff check src tests` clean on the final tree.

**Two honest notes on the table.**

**M2 landed one assertion earlier than the plan predicted, and that is worth stating rather than glossing.** The plan expected "the owner-scoped golden query comparison red". What actually happens is that the copy command's *own* fidelity gate catches the loss first (the join key includes `owner`, so dropping the column makes every row unmatched) and exits 1, so the test fails at `assert main(...) == 0` and the golden comparison never runs. That is the command working correctly, but it means the run does not, by itself, demonstrate that the *golden set* can see tenancy loss. M2′ exists for exactly that: same mutation, return code ignored, and the golden comparison then goes red on all eight queries in precisely the way tenancy loss should look. Without M2′ the recorded evidence would have been weaker than it appears.

**M6 is red on the second pass, never the first**, which is 13-01's lesson applied rather than re-learnt: a first copy into an empty table inserts everything whatever the skip clause is. The idempotence assertion is the falsifiable one, and it is the one that goes red.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| `src/research_agent/recall_golden.py` exists | file absent | 12 notes, 8 queries, 4 `enable_indexscan` occurrences |
| Module imports with no `DATABASE_URL` and no `VOYAGE_API_KEY` | n/a | `ok` (`env -u` both) |
| Server-side `INSERT..SELECT` carrying `owner, created_at` in migrate.py | 0 | 1 (whitespace-flattened match — see the caveat below) |
| `grep -c "DROP" src/research_agent/migrate.py` | 0 | 0 |
| `python -m research_agent.migrate --help` / `embeddings copy --help` | 0 / n/a | 0 / 0 |
| `python -m research_agent.migrate --dry-run` legacy banner | prints, 0 | prints, 0 (13-01's round-trip test green) |
| `pytest tests/test_migrate.py -k "golden_set or copy_fidelity or copy_recall_identical or index_sanity"` armed | tests absent | **4 passed** |
| `pytest tests/test_migrate.py` armed | 2 passed | **6 passed** |
| `ruff check src tests` | clean | clean |
| Full suite, plain | 527 passed / 49 skipped | **527 passed / 53 skipped** |
| Full suite, armed (`DATABASE_URL` only, matching 13-01's measurement) | 575 passed / 1 skipped | **579 passed / 1 skipped** |
| Full suite, armed + `REQUIRE_POSTGRES=1` | — | **580 passed / 0 skipped** |

**Delta fully explained.** Collected 576 → 580, +4 in both arms — the four new tests and nothing else. Armed, all four pass. Plain, all four **skip**, each reporting `DATABASE_URL is not set` (`tests/test_migrate.py:344, 378, 433, 456`), which is the only honest behaviour: they assert byte-level fidelity of pgvector rows and exact-scan query results against a real server. No pre-existing test changed state. **A green plain run is not evidence for this plan; the armed run is.**

The armed baseline needed one clarification: 13-01's `575 / 1` was measured with `DATABASE_URL` alone (the single skip is `test_store_contract.py:771`, `REQUIRE_POSTGRES is not set`). Both numbers are recorded above so the comparison is like-for-like.

**On the `INSERT..SELECT` grep gate — stated rather than quietly satisfied.** The plan asked for a grep on migrate.py. A line-oriented `grep -c "INSERT INTO .* SELECT"` returns **1 against the tree before and after the change**, because it matches the *prose* `INSERT INTO ... SELECT` in a docstring. That is a vacuous gate as written. The SQL is a multi-line template, so no single-line grep can see it honestly. What is recorded above is a whitespace-flattened regex over the file that requires the full column list and the full select list; the real gate is `test_copy_fidelity`'s byte-diff assertion, falsified by M1.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — Correctness of the specified check] `assert_tie_free` filters by the query floor**
- **Found during:** Task 1, designing the corpus
- **Issue:** The plan says "run the exact-scan distances **unfiltered** and raise if any two stored rows under the queried owner are at equal distance". Over 5-dimensional binary bag-of-words vectors that is not merely strict, it is unsatisfiable: any two notes sharing no word with the query both sit at similarity 0 and tie. A corpus satisfying it does not exist.
- **Fix:** The check scores every row under the owner and then examines the rows at or above that query's `min_similarity`. That is also the property that actually matters — rows the query cannot return cannot affect its order — and the docstring says so.
- **Does it weaken M5?** No. M5 adds two same-vocabulary notes under alice; they tie at 1.0 for a query alice actually asks, well above the floor, and the check names both pairs.
- **Files modified:** `src/research_agent/recall_golden.py`
- **Commit:** `e7e2c06`

**2. [Rule 2 — Missing critical assertion] The recall-equality gate needed an anti-vacuity floor**
- **Found during:** Task 3
- **Issue:** `recall_delta({}, {}) == []` and `recall_delta` over eight empty result sets is also `[]`. A seeding failure, a wrong owner, or a floor set too high would make `test_copy_recall_identical` green while proving nothing — the same shape as the fourteen vacuous gates this project has already found.
- **Fix:** The test asserts that at least seven of the eight queries answered and that at least 12 rows were returned in total, *before* comparing.
- **Files modified:** `tests/test_migrate.py`
- **Commit:** `9262aeb`

**3. [Rule 2 — Non-vacuous non-destructive gate] Compare contents, not counts**
- **Found during:** Task 3
- **Issue:** The plan asks for "old-table count unchanged after the copy AND after `--dry-run`". A row count is green against a table whose rows were replaced, and green against a `TRUNCATE`+re-`INSERT`. It is also green against an `UPDATE` that rewrote every embedding — which is the exact corruption M1 simulates.
- **Fix:** `_fingerprint()` compares the full `(text, owner, created_at, embedding::text)` set before and after.
- **Files modified:** `tests/test_migrate.py`
- **Commit:** `9262aeb`

### Departures from the plan's written approach

- **Table-name validation** was implemented as the plan's explicitly-permitted third option ("a tiny module-level helper the store also uses"), rather than by constructing a store for `--from`. Constructing a store for the *source* would have run DDL against it, which a read-only command must not do.
- **`--dry-run` does not construct the target store**, so it performs no DDL. The plan's step 3 implies the target exists by the time the pending count is taken; asking `to_regclass` first is what keeps the dry run genuinely dry.
- **The four fidelity numbers print as five lines**, because "source count vs target count" reads better as one line naming both tables.

### README

**Reviewed; no change from this wave.** The one migration-adjacent limitation — *"Changing embedding model means a new pgvector table. The column width is fixed at creation; the dimension check fails loudly but can't migrate for you"* (README.md:209) — is still true today. This wave adds a **copy-only** path: same vectors, same width, new table. Nothing here re-embeds, so nothing here gives a model change a migration path. Wave 3 is what falsifies that sentence, and rewriting it now would be a claim ahead of the code — the same call 13-01 made, for the same reason.

`docs/OPERATIONS.md` deliberately untouched: the copy command's operator procedure belongs with the cutover story, which is a later wave's, and the `--help` epilog documents the subcommand in the meantime.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-13-04 | mitigate | **Closed.** The copy is a single server-side `INSERT..SELECT`; no vector is materialised in Python on that path. M1 (perturbing one target vector) turns both the byte-diff join and the exact-scan golden comparison red. |
| T-13-05 | mitigate | **Closed.** `owner` travels in the column list; the tenancy probe is a golden query per owner. M2 red on the command's own gate, M2′ red on the golden comparison with alice's and bob's rows surfacing in the unowned bucket. |
| T-13-06 | mitigate | **Closed.** No equality-of-recall assertion touches the index. `exact_scan_results` is the only runner used for the claim; `test_index_sanity` is set-equality, in its own test, documented as scale-bounded. |
| T-13-07 | mitigate | **Closed.** Both `--from` and `--to` go through `memory.validate_table_name()` — the store's own rule, now shared rather than duplicated — before any SQL is built. |
| T-13-08 | mitigate | **Closed.** No statement is issued against `--from`; `--dry-run` performs no DDL at all; the source's full contents (embeddings included) are compared before and after both invocations. |
| T-13-SC | accept | No packages installed. `pyproject.toml` untouched this plan. |

New threat surface: none. No network endpoint, no auth path, no production schema change — the new table is created by the existing store DDL.

## Known Stubs

None.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `e7e2c06` | feat | A frozen, tie-free golden recall set measured under exact scan |
| `5ab6a6e` | feat | `embeddings copy` — server-side, non-destructive, self-checking |
| `9262aeb` | test | The copy gates — fidelity, exact-scan identity, index sanity |

## Deferred Issues

None. One process note for the record: a `git stash`/`git stash pop` pair was used once to measure a pre-existing `ruff format` baseline on `memory.py`. It restored cleanly (`git stash list` empty, both modified files intact, the tree verified afterwards), but it was the wrong tool — `git show HEAD:path` answers the same question without touching the working tree, and the stash stack is shared across worktrees. Noted so it is not repeated.

For the record on that measurement: `ruff format --check` fails on `memory.py` and `tests/test_migrate.py` at lines this wave did not write, on the tree at `HEAD` before any of this wave's edits. The project's lint gate is `ruff check`, which is clean; `ruff format` is not enforced here and was not "fixed" as drive-by scope.

## Self-Check: PASSED

- `src/research_agent/recall_golden.py` — FOUND
- `src/research_agent/migrate.py` — FOUND (modified)
- `src/research_agent/memory.py` — FOUND (modified)
- `tests/test_migrate.py` — FOUND (modified)
- Commits `e7e2c06`, `5ab6a6e`, `9262aeb` — all three resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
