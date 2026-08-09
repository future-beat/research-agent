---
phase: 13-embedding-model-migration
plan: 04
subsystem: docs
tags: [migration, pgvector, cutover, adr, operations, gate-discipline, vacuous-gates]

# Dependency graph
requires:
  - phase: 13-embedding-model-migration
    plan: 03
    provides: "`embeddings re-embed`, VOYAGE_PRICES, the --yes spend gate, and the README limitation rewrite that pre-satisfied half of this plan's README gate"
  - phase: 13-embedding-model-migration
    plan: 02
    provides: "recall_golden (seed / exact_scan_results / run_golden / assert_tie_free / query_key), `embeddings copy`, the migration_test_notes_* table discipline and the _fingerprint idiom"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    provides: "owner on the notes schema, the 7-day TTL that makes quiesce-migrate-flip defensible, the FakeEmbedder/HAS_POSTGRES test idiom"
provides:
  - "tests/test_migrate.py::test_cutover_reversible — SC-3 proven both directions through the production store, old table re-fingerprinted after every step"
  - "docs/adr/0008-embedding-migration-two-commands.md — Accepted, Source:-line, the DEC-10 reversal recorded in prose"
  - "docs/OPERATIONS.md § Changing the embedding model or dimension — the six-step quiesce-migrate-flip runbook"
  - "The honest-scale caveat and the index-exclusion sentence the README limitation was still missing"
affects: [13-05, VALIDATION rows cutover_reversible / ADR grep gate / README grep gate]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase (RESEARCH Package Legitimacy Audit: none)
  patterns:
    - "A grep gate over a document is vacuous whenever the word it greps for already appears somewhere unrelated in that document. `grep -qi rollback docs/OPERATIONS.md` was green at baseline and stayed green with the entire rollback paragraph deleted"
    - "An acceptance criterion with no clause in the verify command is not a gate. The 'deliberately not exercised' criterion had none, and the plan's command stays green with the claim restored"
    - "Env-var-at-import config is testable at the constructor it feeds, never by reimporting the module: the reimport leaves a second module object alive for the rest of the session"

key-files:
  created:
    - docs/adr/0008-embedding-migration-two-commands.md
  modified:
    - tests/test_migrate.py
    - docs/adr/README.md
    - docs/OPERATIONS.md
    - README.md
    - .planning/intel/decisions.md

key-decisions:
  - "The cutover test exercises `PgVectorMemoryStore(table=...)`, not `PGVECTOR_TABLE` + reimport. The env var is read once at import into the constructor's default, so the constructor is the same seam entered at the end a test can hold; reimporting `memory` would leave a second module object live for every later test in the process."
  - "The test's docstring says out loud that `query()` is the indexed path, so the equality against exact-scan expectations is indexed-vs-exact and rests on `test_index_sanity`'s scale-bounded argument. Written as an ordered equality because at twelve rows the stronger claim is the true one — and labelled so nobody promotes it."
  - "ADR-0008 supersedes nothing and says so. DEC-10 has no numbered record, so the README's supersession convention does not apply; the reversal lives in prose under `### What survives of DEC-10` / `### What is new`, imitating ADR-0007's carried-forward section."
  - "The OPERATIONS runbook is a top-level section, not a subsection of 'Going stateless'. It is a standalone procedure an operator follows on its own; the stateless-cutover section links to it."
  - "The README limitation was rewritten by wave 3 and is not rewritten again — but the honest-scale caveat and the index-exclusion sentence the plan's action required were genuinely absent, so those two were added rather than declared pre-satisfied."

# Metrics
duration: 40min
completed: 2026-08-06
---

# Phase 13 Plan 04: The cutover, proven and recorded Summary

**One-liner:** The cutover is a config flip and nothing else — proven forward and back through the production store with the old table re-fingerprinted after every step — and the DEC-10 reversal now has an ADR that says exactly what survives, an operator runbook that says what to actually type, and two gate clauses caught being vacuous before they were trusted.

## What was built

### Task 1 — `test_cutover_reversible` (commit `7f6a7b1`)

Postgres-gated, in a dedicated `migration_test_notes_cutover` table dropped on setup and teardown.

1. Seed the golden corpus into `migration_test_notes_old`, then `golden.assert_tie_free` — asserted here rather than inherited from 13-02's test, because an ordered comparison over a tie-bearing corpus measures the query executor.
2. `_fingerprint(old)` — the full `(text, owner, created_at, embedding::text)` set — taken **before** anything happens.
3. `expected` = `golden.run_golden(...)` over the old table (exact scan), **projected to texts**: `query()` returns `list[str]` (memory.py:546) while the runner returns `(text, similarity)` tuples. Anti-vacuity assertions on `expected` before it is trusted: seven of eight queries answered, ≥12 rows in total.
4. `embeddings copy` to the cutover table.
5. **Flip forward:** `PgVectorMemoryStore(table="migration_test_notes_cutover", dimensions=5, embedder=FakeEmbedder(), database=db.Database())` answers all eight golden queries and equals `expected`.
6. **Flip back:** a store constructed against the OLD table, same equality. Rollback is pointing back, proven rather than asserted in prose.
7. `_fingerprint(old) == before` after the copy, after the flip forward, and after the flip back — three times, not once at the end, where a step that dropped and recreated the table would still pass. Plus a final check that the new table still holds its rows, so a second flip forward needs no second migration.

**On the seam, stated in the test rather than assumed.** `PGVECTOR_TABLE` is read once, at import (memory.py:58), into a module constant that becomes `PgVectorMemoryStore.__init__`'s default for `table=`. The env var and the constructor parameter are the same seam entered at different ends, and the constructor is the end a test can hold — setting the variable and reimporting `memory` would leave a second module object alive for every later test in the process (Pitfall 5). What is therefore **not** proven is the process restart itself; the comment says so.

**On the comparison, also stated in the test.** `expected` comes from the exact-scan runner; `store.query()` is the *indexed* production path. So this is an indexed-vs-exact equality, defensible only under `test_index_sanity`'s argument: a dozen rows against `hnsw.ef_search = 40`, so the search effectively explores everything, over a tie-free set so the order is not the executor's choice. At a corpus size where HNSW does real approximation it would have to weaken to set equality. It is written as an ordered equality because at this size the stronger claim is the true one — and it is labelled so nobody promotes it into a general guarantee.

The flip-back store runs the same idempotent `ensure_schema` production runs at startup against an existing table; the fingerprint immediately after is what says that touched no data.

### Task 2 — ADR-0008, the index row, the DEC-10 annotation (commit `7010064`)

`docs/adr/0008-embedding-migration-two-commands.md`, **`Status: Accepted`** with a **`Source:`** line — not `Promoted from:`, and **not** `Accepted — supersedes ADR-000M`. DEC-10 was never promoted to a numbered record, so by the README's own convention there is nothing to supersede and no existing status line to touch. None was touched.

- `## Context` — DEC-10's rule, its real reason ("two suspects and no way to separate them"), why a re-embed path re-opens exactly that ambiguity, and the honest-scale note.
- `## Decision` — two commands, never one, with `### What survives of DEC-10` (the copy-only command **is** DEC-10's operation verbatim; its rationale survives as the rule that the two variables are never changed in one command, now *measured* by the golden set rather than *enforced by prohibition*), `### What is new`, `### What "byte-identical recall" means, exactly` (the three-part decomposition with the HNSW index explicitly outside the claim), `### Writes during a migration: quiesce–migrate–flip`, and `### Cutover is the config flip that already existed`.
- `## Consequences` — `### Accepted` (priced preview but no `/metrics` accounting, named as Phase 14's; the production flip stays an operator decision; >2000 refused; the re-embed delta is the operator's measurement and tie-freedom does not travel across a model change; the old table survives until someone deletes it by hand) and `### Rejected alternative` (one do-everything command, which re-confounds the variables DEC-10 separated; and in-place `ALTER COLUMN`, which is the "new setting instead of a new table" the dimension check's own message forbids).

`docs/adr/README.md`: index row added (Accepted, Superseded by —), the prose updated from "Six of the seven" to "Seven of the eight", 0008 added to the odd-ones-out `Source:` paragraph, and a new paragraph saying 0008 supersedes nothing *deliberately* so a later reader does not go looking for the missing supersession.

`.planning/intel/decisions.md`: one line appended to DEC-10 naming Phase 13's disposition and linking ADR-0008. The entry's original text is unchanged.

### Task 3 — the operator runbook, and the two README sentences wave 3 left out (commit `59d8df3`)

`docs/OPERATIONS.md` gains a top-level **`## Changing the embedding model or dimension`**, six numbered steps, placed after the Supabase specifics and linked from the stateless-cutover section:

1. **Quiesce** — with the justification printed rather than the gap left implicit: the corpus is ≤7 days of notes by TTL, a note missed mid-migration expires on its own within a week, and dual-write for a self-erasing corpus is engineering theatre. What the operator is accepting is named.
2. **Migrate** — both invocations in full, `copy` for the infrastructure variable and `re-embed` for the model one, with the preview/`--yes`/`--dry-run` semantics and the note that the **first `count_tokens` call downloads a tokenizer from the Hugging Face hub** (the failure a no-egress box hits, and where it hits).
3. **Verify** — what each command's own numbers mean and which of them means *stop*; plus a pointer at `recall_golden` and the warning that `assert_tie_free` must be re-run against a re-embedded table before an ordered comparison over it means anything.
4. **Flip** — `fly secrets set PGVECTOR_TABLE=` (+ `VECTOR_DIMENSIONS=` after a re-embed), why setting a secret restarts (both are read at import), and **rollback is pointing back**, naming the test that proves it.
5. **Drop the old table** — by hand, later, or never. No automation, and none should exist.
6. **The dimension ceiling** — 2000, why voyage-3.5's 2048 makes it a real mistake rather than a hypothetical, and `halfvec` named as the unbuilt path.

The `deliberately **not exercised**` claim about `migrate.py` is gone. The honest replacement: it plays no part in the *stateless cutover* (there is nothing to migrate), but it is no longer an unproven tool.

**README.** The limitation bullet was rewritten by wave 3 and is not rewritten again — but two things this plan's action explicitly required were genuinely absent from it, so they were added: the **honest-scale caveat** (7-day TTL, the point is the path and not corpus rescue) and the statement that **recall equality is never asserted through the HNSW index**. Links to the runbook and to ADR-0008 were added at the same time. See "Deviations" for why this counts as this wave's work rather than a re-edit.

## Gate discipline: seven mutations, five red, and **two clauses caught green when they should have been red**

Sixteen vacuous gates across six phases after this wave — two of the plan's own verify clauses turned out to be unfalsifiable, and both are recorded below rather than glossed. Measured baseline before mutating: `pytest tests/test_migrate.py` armed = **15 passed**; the new test green as the 16th.

### The cutover gate

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| C1 | *(plan-specified)* `DELETE` alice's `chroma retry` from the cutover table, then point the **flip-back** store at the cutover table instead of the old one | **RED** | `test_cutover_reversible:921` — `{"'chroma retry'@'alice'": ['chroma supervisor', 'voyage supervisor retry', 'langgraph chroma voyage supervisor']} != [... 'chroma retry', 'chroma supervisor', 'voyage supervisor retry']`. The deleted row is gone from the answers, so the assertion does read the table it is pointed at and is not comparing a table to itself |
| C2 | `DELETE` alice's `langgraph` from the **old** table after the copy | **RED** | `test_cutover_reversible:913` — `assert _fingerprint(handle, old) == before` fails. The old-table integrity check is falsifiable at the step it guards |
| C3 | `UPDATE` one cutover-table embedding to `'[1,1,1,1,1]'` before the **flip-forward** assertion | **RED** | Two golden queries deltaed — `'voyage supervisor'@'alice'` and `'langgraph'@'alice'` each gain a spurious `'chroma retry'`. Falsifies the flip-forward equality on its own terms and with a row *count* that never changed, which a count-based check would have missed |

C1 is the plan's mutation and it needs both halves to mean anything: pointing flip-back at the cutover table *without* the delete would stay green, because the two tables are identical by construction. The pairing is what makes it evidence.

### The ADR gate

| # | Mutation | Result | Observed |
|---|----------|--------|----------|
| A1 | *(plan-specified)* `**Source:**` → `**Promoted from:**` in 0008 | **RED** | The verify's `[ "$(grep -c "Promoted from" …)" -eq 0 ]` clause fails |
| A2 | Delete the 0008 **index row** from `docs/adr/README.md`, leaving the prose | **GREEN — vacuous clause** | `grep -q "0008" docs/adr/README.md` stays satisfied by the prose alone. A row-shaped gate — `grep -qE '^\| 0008 \| \[0008-…\]\(0008-…\) \|.*\| Accepted \| — \|$'` — goes **RED** on the same mutation |

**A2 is the finding.** The plan's index clause cannot tell the difference between "the record is in the index table" and "the number 0008 appears anywhere in the file", and this ADR's own prose mentions 0008 four times. The row-shaped grep above is what actually gates the `key_links` requirement, it is red under A2, and it is green on the committed tree.

### The docs gate

| # | Mutation | Result | Observed |
|---|----------|--------|----------|
| O1 | *(plan-specified)* Restore `Changing embedding model means a new pgvector table.` in README.md | **RED** | The verify's first clause fails |
| O2 | Rewrite OPERATIONS' `re-embed` invocation as a second `copy` invocation | **RED** | `grep -q "embeddings re-embed" docs/OPERATIONS.md` fails |
| O3 | Delete the **entire** `**Rollback is pointing back.**` paragraph from the new section | **GREEN — vacuous clause** | `grep -qi "rollback" docs/OPERATIONS.md` stays satisfied by an unrelated Phase-11 sentence at line 157 (*"The rollback is untested."*). `grep -c "Rollback is pointing back"` goes 1 → **0**, red |
| O4 | Restore `is therefore deliberately **not exercised** by this cutover` | **GREEN — no clause exists** | The plan's verify command has nothing that looks at this, though it is an acceptance criterion. `grep -c "not exercised" docs/OPERATIONS.md` goes 0 → **1**, red |

**O3 and O4 are the second and third findings, and O1 needs a caveat too.**

**O3:** `grep -qi "rollback" docs/OPERATIONS.md` was **already green at baseline** (1 occurrence, from Phase 11's *"The rollback is untested"*), so it could never have been evidence for anything this plan wrote. Deleting the whole rollback paragraph from the new runbook leaves it green. The gate that bites is the sentence-level one, measured 0 → 1.

**O4:** "the 'deliberately not exercised' claim about migrate.py is gone" is an acceptance criterion with **no clause in the verify command at all**. An acceptance criterion nothing checks is a note, not a gate. `grep -c "not exercised" docs/OPERATIONS.md`, baseline 1 → 0, is the missing clause, and it is red under O4.

**O1's caveat:** the clause is live (O1 proves it), but it was **already satisfied entering this wave** — wave 3 rewrote the bullet, taking the phrase to 0. This plan did not falsify it; wave 3 did. Recorded because the VALIDATION baseline ("current phrase present today at 1 occurrence") was measured before wave 3 and no longer holds, exactly as 13-03's summary warned.

All seven mutations reverted; every revert verified by byte comparison against a pre-mutation snapshot (`diff -q … && echo True` → `True` in each case, and the test file's SHA-1 restored to `24f0fe3c…`). `ruff check src tests` clean on the final tree.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| `pytest tests/test_migrate.py -k cutover_reversible` armed | test absent | **1 passed** |
| `pytest tests/test_migrate.py` armed | 15 passed | **16 passed** |
| `ls docs/adr/0*.md \| wc -l` | 7 | **8** |
| `grep -c "Source:" docs/adr/0008-…md` | file absent | **1** |
| `grep -c "Promoted from" docs/adr/0008-…md` | file absent | **0** |
| `^\*\*Status:\*\* Accepted` in 0008 | file absent | present; no existing ADR's status line modified |
| Row-shaped 0008 index gate in `docs/adr/README.md` | absent | **present** (red under A2) |
| `grep -c "ADR-0008" .planning/intel/decisions.md` | 0 | **1** |
| `grep -c "Changing embedding model means a new pgvector table" README.md` | **0** (wave 3, not this wave) | 0 |
| `grep -c "embeddings re-embed" README.md` | 1 (wave 3) | 1 |
| `grep -c "embeddings re-embed" docs/OPERATIONS.md` | **0** | **1** |
| `grep -c "Rollback is pointing back" docs/OPERATIONS.md` | **0** | **1** |
| `grep -c "not exercised" docs/OPERATIONS.md` | **1** | **0** |
| Six numbered runbook steps in OPERATIONS.md | absent | **6** (`### 1.` … `### 6.`) |
| `ruff check src tests` | clean | clean |
| Full suite, plain | 529 passed / 60 skipped | **529 passed / 61 skipped** |
| Full suite, armed (`DATABASE_URL` only) | 588 passed / 1 skipped | **589 passed / 1 skipped** |
| Full suite, armed + `REQUIRE_POSTGRES=1` | 589 passed / 0 skipped | **590 passed / 0 skipped** |

**Delta fully explained.** Collected 589 → 590 in every arm: `test_cutover_reversible` and nothing else.

- Armed: it passes (588 → 589; 589 → 590 with `REQUIRE_POSTGRES=1`).
- Plain: **+1 skip, 0 new passes** (60 → 61), reported as `tests/test_migrate.py:869: DATABASE_URL is not set`. **The one new skip, justified:** the test seeds a real pgvector table, runs `embeddings copy` server-side, and answers eight queries through `PgVectorMemoryStore` against both tables while comparing `embedding::text` fingerprints. Every claim it makes is a claim about rows in a real Postgres; there is nothing left to assert with the database absent, and a fake would be measuring the fake.

No pre-existing test changed state in either arm. **A green plain run is not evidence for this plan; the armed run is.**

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — Missing critical gate] Two of the plan's verify clauses were unfalsifiable**
- **Found during:** Task 2 mutation A2 and Task 3 mutation O3
- **Issue:** `grep -q "0008" docs/adr/README.md` cannot distinguish an index row from a prose mention, and `grep -qi "rollback" docs/OPERATIONS.md` was green at baseline from an unrelated Phase-11 sentence. Both stayed green under mutations that removed exactly the artefact the clause exists to require.
- **Fix:** Added the row-shaped index grep and the `Rollback is pointing back` sentence grep, ran both, and observed each red on its own terms. The plan's commands are recorded unchanged (13-05.2 owns VALIDATION reconciliation); the stronger gates are recorded here alongside them.
- **Files modified:** none (mutations, not code changes)

**2. [Rule 2 — Missing critical gate] An acceptance criterion with no clause behind it**
- **Found during:** Task 3 mutation O4
- **Issue:** "the 'deliberately not exercised' claim is gone" is an acceptance criterion that the verify command does not check, so restoring the claim leaves the gate green.
- **Fix:** `grep -c "not exercised" docs/OPERATIONS.md`, baseline 1 → 0, run and observed red under O4.
- **Files modified:** none

**3. [Rule 2 — Missing content the plan required] The README was missing two of the sentences 13-04.3 asked for**
- **Found during:** Task 3
- **Issue:** 13-03 rewrote the limitation bullet and pre-satisfied the *grep* gate, and the plan says to verify rather than re-edit. But two things the plan's action explicitly required were absent from the rewritten bullet: the honest-scale caveat ("with the 7-day note TTL the live corpus is tiny — the point is the path, not corpus rescue") and, per the acceptance criterion "no doc claims byte-identical recall through the index", any statement of what the recall claim excludes. Declaring the README done because a grep passed would have been the exact failure this project keeps cataloguing.
- **Fix:** Both sentences added to the existing bullet, plus links to the new runbook and to ADR-0008. The rest of wave 3's rewrite is untouched.
- **Files modified:** `README.md`
- **Commit:** `59d8df3`

### Departures from the plan's written approach

- **The OPERATIONS section is top-level (`##`), not a subsection of "Going stateless".** The plan says "near the existing migrate section". That section is the Phase-11 stateless cutover, whose whole point is that there was nothing to migrate; nesting a model-change runbook inside it would file the procedure under an unrelated event. It sits immediately after that section instead, and "Starting clean" links forward to it.
- **Three cutover mutations rather than one.** The plan specified C1. C1 falsifies the flip-*back* assertion; the flip-*forward* equality and the old-table integrity check each had nothing behind them, so C2 and C3 exist. This is 13-02's M2/M2′ and 13-03's M4/M4′ pattern applied before the fact rather than after.
- **`golden.assert_tie_free` is called inside the cutover test** rather than inherited from `test_golden_set_tie_free_and_owner_scoped`. The ordered comparison is this test's own claim; a precondition asserted in a different test is a precondition this test does not have.
- **The ADR gained a `### What "byte-identical recall" means, exactly` subsection.** The plan asked for the decomposition to be recorded in `## Decision`; giving it its own heading makes it findable by someone checking whether the claim was overstated, which is the only reason to write it down.

### README

**Amended, not rewritten** (commit `59d8df3`) — see auto-fixed issue 3. The per-phase README deliverable was substantially discharged by wave 3; this wave supplied the honest-scale caveat and the index-exclusion sentence its own plan required, and linked the bullet to the runbook and the ADR.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-13-14 | mitigate | **Closed.** The procedure is env-flip only; `test_cutover_reversible` proves both directions with the old table's full contents re-compared after every step; OPERATIONS step 5 states that no command drops anything and that deleting the old table is a manual act. C1/C2/C3 red. |
| T-13-15 | mitigate | **Closed.** ADR-0008 states the three-part decomposition with the HNSW index explicitly outside the claim, and the README now says the same thing in one sentence. No doc anywhere claims byte-identical recall through the index (`grep -i "byte-identical"` across README/docs returns only ADR-0008's heading, ADR-0007's 404 sentence, and DESIGN.md's metrics-backend sentence). The honest-scale caveat is in the ADR, the runbook and the README. |
| T-13-16 | accept | **Accepted and stated.** OPERATIONS step 1 names the risk (notes written between migrate and flip are lost), the bound (≤7 days by TTL, self-healing), and the reason dual-write was not built. ADR-0008 records the same in `### Writes during a migration`. |
| T-13-SC | accept | No packages installed. `pyproject.toml` untouched this plan. |

New threat surface: none. No code outside `tests/` changed this plan.

## Known Stubs

None introduced. The two **untested-by-construction** functions 13-03 named are still unexecuted and are still 13-05's:

- **`_default_token_counter`** — the real `count_tokens` wrapper; first call downloads an HF tokenizer from the Hugging Face hub. Every test injects `_word_counter`. The new OPERATIONS runbook documents that download as operator-visible behaviour, which is documentation of it, not execution of it.
- **`_ReembedEmbedder.embed_documents`** and the `billed` reconciliation line — reachable only through a real Voyage response.

13-05's live run is the first execution of both.

## Deferred Issues

- **The re-embed recall delta remains unmeasured.** Carried in from 13-03 and not closed here: this plan's tasks were the cutover and the record, and no task asked for a golden comparison across a model change. **13-05 now owns it**, and the warning is unchanged and load-bearing: the golden set is tie-free under the 5-dimensional `FakeEmbedder`, tie-freedom does not travel across a re-scoring, so `assert_tie_free` must run against the re-embedded table before any `recall_delta` over it means anything. The OPERATIONS runbook's step 3 states this to operators as well, so the requirement is now written down in two places.
- **Voyage spend is still absent from `/metrics`** (Phase 14). Named in ADR-0008's Consequences and in the README.
- **Two vacuous clauses remain in 13-VALIDATION's recorded commands** for rows 13-04.2 and 13-04.3. They are not rewritten here — 13-05.2 owns VALIDATION reconciliation, and the convention is that an Automated Command is never rewritten after its gate has run. The stronger gates and their red mutations are recorded in this summary for 13-05.2 to reconcile against.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `7f6a7b1` | test | The cutover is a flip, and it goes both ways |
| `7010064` | docs | ADR-0008 records what survives of DEC-10 and what is new |
| `59d8df3` | docs | The operator procedure for changing embedding model |

## Self-Check: PASSED

- `tests/test_migrate.py` — FOUND (modified)
- `docs/adr/0008-embedding-migration-two-commands.md` — FOUND (created)
- `docs/adr/README.md` — FOUND (modified)
- `docs/OPERATIONS.md` — FOUND (modified)
- `README.md` — FOUND (modified)
- `.planning/intel/decisions.md` — FOUND (modified)
- Commits `7f6a7b1`, `7010064`, `59d8df3` — all three resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
