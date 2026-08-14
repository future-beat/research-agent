---
phase: 20-note-count-bound
verified: 2026-08-14T11:53:06Z
status: passed
score: 3/3 roadmap success criteria verified (7/7 plan must-have truths)
method: goal-backward — every criterion re-proven from the tree by a mutation or an independent measurement the verifier performed and observed, then reverted. SUMMARYs were read as claims, never as evidence
verifier_mutations: 4  # each observed red, each reverted; tree confirmed clean before the first and after the last
verifier_experiments: 4  # a four-backend eviction/isolation/collision harness, a four-backend sweep-first harness, a '' -bucket + return-type probe, and the clamp table read straight out of note_cap_per_owner()
overrides_applied: 0
re_verification: false

# Gates re-run by the verifier, not read from a SUMMARY
gates:
  full_suite: "796 passed / 71 skipped, exit 0, 31.93s, ANTHROPIC_API_KEY='' VOYAGE_API_KEY=''"
  armed_contract_file: "118 passed / 1 skipped, DATABASE_URL=postgresql://postgres@localhost:54329/postgres — the one skip is the REQUIRE_POSTGRES-gated CI self-check"
  pgvector_cap_arms: "4 passed armed; the same four report `SKIPPED … DATABASE_URL is not set` with the DSN removed — so the arm genuinely runs rather than skipping quietly"
  offline_evals: "PASS 41/41 cases (100% vs 90% required), real $? = 0 from a bare invocation"
  ruff: "All checks passed! — both `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals`"
  graph_py_diff: "0 lines across the whole phase (`git diff ccbc7b2 HEAD -- src/research_agent/graph.py`)"
  seam_signatures: "no +/- line in the memory.py diff matches `def (add|query|__len__|describe)\\(`"
  readme_bullet: "byte-identical — `diff` of README:289-295 at ccbc7b2 vs HEAD prints nothing; still line 291; grep count 1"
  working_tree: "clean at start and at end"

# Not gaps. Recorded so the next phase inherits the fact rather than the silence.
warnings:
  - finding: "\"Proven by the shared 4-arm contract suite\" is true for three arms and one property short on the fourth — and the phase said so first"
    evidence: "The verifier reproduced 20-01's mutation 2c independently: chroma's eviction sort changed from `seq` to `created_at`, then the armed suite run. `test_note_cap_tie_break_is_deterministic_when_created_at_collides[json|memory|chroma|pgvector]` — all four PASSED. Only `test_chroma_cap_eviction_survives_a_reordered_get` failed ('Extra items in the right set: langgraph note-2'). The claim in 20-01-SUMMARY:141-158 and 20-VALIDATION row 3 is exactly right, not overstated."
    why_it_counts: "Criterion 2's wording attributes the byte-identical proof to the shared suite. For the chroma tie-break specifically, the shared suite is structurally blind — chromadb 1.4.1 returns `get()` in insertion order, so the wrong sort key is rescued by the vendor. The property is still gated, but by the stubbed single-backend gate beside the suite, not by the suite."
    fix: "None. The gate exists, reds under the mutation, and its docstring names the hazard. The transferable rule is written into 20-01-SUMMARY and STATE: if chromadb is ever unpinned from 1.4.1, that gate is the test that still means something."
  - finding: "README:291 'Notes are bounded by expiry alone' is now actively false and stays that way until Phase 22"
    evidence: "Byte-identical on the git axis, not merely by grep: `diff <(git show ccbc7b2:README.md | sed -n '289,295p') <(sed -n '289,295p' README.md)` prints nothing, and the whole README diff for the phase is four lines — two test counts, 773 → 796."
    why_it_counts: "Deliberate and stated in four places the verifier checked independently (20-CONTEXT:101-104, 20-01-SUMMARY:194, 20-02-SUMMARY:190-213, ROADMAP). It is the third such bullet standing after Phase 18's :285 and Phase 19's :289."
    fix: "Phase 22 deletes all three. Removing it here would strand that phase and would also drop the bullet's second sentence — the dedup/summarisation refusal — which is still true and still in REQUIREMENTS' Out of Scope."
  - finding: "REQ-note-count-bound is still `- [ ]` in REQUIREMENTS.md and reads `Pending` in the traceability table"
    evidence: "REQUIREMENTS.md:57 unchecked; :100 `| REQ-note-count-bound | Phase 20 — Note count bound | Pending |`."
    why_it_counts: "Honest pre-verification state rather than drift — the row names verification as the missing step, exactly as Phase 19's did. That step is now done, so the flip is due."
    fix: "One checkbox and one table cell, in the ship or milestone-close commit. Phases 18 and 19 were closed the same way."
  - finding: "Two stale planning surfaces the phase found, measured, and deliberately did not fix"
    evidence: "`.planning/codebase/CONCERNS.md:242-270` still asserts 'There is genuinely no eviction, deduplication, or summarisation anywhere' and that the seam would need widening first — false since Phase 12's sweep, and its prediction is now disproven by a character-identical seam. `.planning/PROJECT.md:31-32` still reads '749 tests … 67 Postgres-gated — 816 collected' against a measured 796 / 71 / 867."
    why_it_counts: "CONCERNS is the single most misleading sentence about this subsystem in the repository, and it is `/gsd-map-codebase` output regenerated wholesale rather than hand-edited."
    fix: "Both are recorded with their measured replacements in `.planning/phases/20-note-count-bound/deferred-items.md` and named in STATE's deferred block. PROJECT.md is a two-line edit; CONCERNS waits for the next map run."

# Verifier nits. None changes a verdict.
notes:
  - "No contract case asserts that the `''` bucket is itself CAPPED — `test_note_cap_never_crosses_owners` only proves the orphan survives another owner's eviction. The verifier measured the missing direction directly: four `owner=''` notes at cap 3 leave `{orphan-2, orphan-3, orphan-4}` and `len() == 3` on all four backends. The behaviour holds; only the gate for it is absent, and the isolation case would catch the likelier regression (`''` treated as a wildcard) anyway."
  - "Two of the verifier's four mutations target the pgvector arm, which the phase's own six mutations never touched (they hit brute force, chroma and migrate.py). Dropping the DELETE's owner predicate reds `test_note_cap_never_crosses_owners[pgvector]` on the bob assertion; dropping `id DESC` from its ORDER BY reds the tie-break case on `[pgvector]` deterministically across three consecutive runs. The SQL arm's owner scoping and its secondary sort key are both genuinely gated."
  - "Wave 2 edited `.planning/STATE.md` and `.planning/ROADMAP.md` though neither is in 20-02-PLAN's `files_modified`. Assessed and accepted: this is the phase's closing wave, both files are hand-edited by convention in this project (SDK verbs corrupted STATE three times in Phase 18), and Phase 19's final wave did the same. The alternative was closing the phase with its own record still saying Phase 19 was the last thing that happened."
  - "Wave 2's refusal to edit `docs/DESIGN.md` was judged by reading the file rather than by trusting the judgement. All 83 lines were read: the Memory section argues retrieval-with-a-floor, the store/embedder seams, HNSW, and migration-copies-vectors, and `grep -iE 'expir|ttl|evict|bound|forever|prune'` returns four hits, none of them about the note store. The antecedent of 20-CONTEXT's conditional is genuinely false. Adding a cap paragraph would have been defensible under DESIGN's own admission criterion (the clamp direction and the `seq` tie-break are both choices that could have gone the other way) but is not something this phase's scope required."
---

# Phase 20: Note count bound — Verification Report

**Phase Goal:** Notes are bounded by count as well as expiry, with identical eviction behaviour
on every backend.

**Verified:** 2026-08-14T11:53:06Z
**Status:** passed — 3/3 roadmap success criteria, 7/7 plan must-have truths
**Method:** goal-backward. Both SUMMARYs and 20-VALIDATION were read as *claims*. Every criterion
below was re-proven from the tree — four mutations applied, observed red and reverted, plus four
independent measurements run against all four live backends. Working tree confirmed clean before
the first mutation and after the last.

---

## Goal Achievement

### Success Criteria (the ROADMAP contract)

| # | Criterion | Status | Evidence the verifier observed |
|---|-----------|--------|--------------------------------|
| 1 | Each owner's notes are capped at a fixed per-owner count, with the oldest note evicted first once the cap is exceeded | VERIFIED | Verifier's own harness, reading **raw storage** rather than `query()` so a read-side filter cannot masquerade as an eviction: cap 3, four adds for `alice`, on every backend `len()==3`, raw row count 3, survivors exactly `{note-2, note-3, note-4}`. `note_cap_per_owner()` measured directly at `memory.py:91-113`; eviction blocks read at `:325-336` (brute force), `:500-509` (chroma), `:661-690` (pgvector). Mutations 2 and 3 below red |
| 2 | Eviction semantics are byte-identical across json, memory, chroma and pgvector, proven by the shared 4-arm contract suite | VERIFIED — with one recorded qualification | Identical survivor sets on all four arms in the verifier's harness for eviction, owner isolation and the forced collision. Armed contract file **118 passed / 1 skipped**; the four pgvector cap arms **run armed** (4 passed) and report `SKIPPED … DATABASE_URL is not set` when the DSN is removed, so the arm is real. **Qualification:** for chroma's tie-break the shared suite is structurally blind — mutation 1 (reproduced by the verifier) leaves all four arms of the collision case GREEN and reds only the stubbed reordered-`get()` gate. The property is gated; the gate is just not the shared suite. Warning 1 |
| 3 | The README's notes-unbounded-by-count limitation is falsified by a passing test, not merely narrowed in prose | VERIFIED | Falsified by tests, not by prose: five new gates (four 4-arm contract cases + the chroma gate) prove notes are bounded by count, and the prose was left byte-identical — the README diff for the entire phase is four lines, both of them test counts. `README.md:291` is unchanged at the byte level against `ccbc7b2`. The bullet's *narrowing* was deliberately not performed; Phase 22 deletes it. Warning 2 |

**Score: 3/3.**

### Plan must-have truths (20-01-PLAN frontmatter)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Adding past the cap evicts oldest-first until the owner holds exactly the cap, same outcome on all four backends | VERIFIED | Criterion 1 above; four-backend harness, raw-storage reads |
| 2 | Eviction never crosses owners; the `''` bucket is untouched; another owner adding at their own cap evicts nothing of the first's | VERIFIED | Harness with bob's note written first (globally oldest): buckets after alice overflows are `{'': [orphan-1], 'alice': [alice-2, alice-3], 'bob': [bob-1]}` on **all four** backends, `len()==4`. Verifier mutation 2 (pgvector owner predicate dropped) reds precisely the bob assertion |
| 3 | The tie-break is deterministic and identical on every arm — list order, chroma `seq`, BIGSERIAL id, never wall-clock alone | VERIFIED | Verifier re-forced the collision itself: distinct `created_at` **before=3 → after=1** on json, memory, chroma and pgvector, then the fourth add left `{alice-2, alice-3, alice-4}` everywhere. The forcing is real, not decorative. Verifier mutation 3 (drop `id DESC` from the pgvector ORDER BY) reds the case on `[pgvector]` three runs out of three |
| 4 | The TTL sweep stays unconditional and runs before the cap count | VERIFIED | Independent harness, owner at 2-of-3 before **and** after the add so the cap branch cannot fire: `len()` 2 → 2 with survivors `{alice-2, alice-3}` on all four backends — the expired row was physically removed by a sweep that had no cap reason to run. Order confirmed in source on each backend (`memory.py:321-336`, `:478-509`, `:653-690`). `test_note_ttl` is untouched by the phase's diff and green |
| 5 | `NOTE_CAP_PER_OWNER` unset, unparseable or `<= 0` reads 100; read per call, never cached | VERIFIED | Verifier called `note_cap_per_owner()` directly across nine inputs: unset→100, `''`→100, `'   '`→100, `'banana'`→100, `'0'`→100, `'-5'`→100, `'3.5'`→100, `' 25 '`→25, `'1'`→1. Flipping the env between two calls returned 7 then 9 — read per call |
| 6 | The add/query/len/describe seam is unchanged in name, signature and return type; graph.py untouched | VERIFIED | `git diff ccbc7b2 HEAD -- src/research_agent/graph.py` is **0 lines**; no `+`/`-` line in the memory.py diff matches `def (add\|query\|__len__\|describe)\(`; `add()` returns `NoneType` on all four backends in the verifier's probe. The pre-existing seam tests appear nowhere in the test diff and are green |
| 7 | migrate.py and recall_golden.py bypass `add()` by design, pinned by a test rather than folklore | VERIFIED | Verifier re-ran the inventory: `grep -rn "store\.add(" src evals` → `graph.py:368` (sole production caller), `recall_golden.py:187` (docstring), `evals/harness.py:300` (per-case seed). `migrate.py` absent. Verifier mutation 4 (a comment carrying the token appended to migrate.py) reds the pin at `test_memory_stores.py:235`; restored, green. The pin's `count == 1` + `in seed.__doc__` pair correctly accommodates recall_golden's legitimate docstring mention |

---

## Mutations Performed by the Verifier

Each was applied to the tree, run, observed red, and reverted from a byte copy.
`git status --porcelain` printed nothing before the first and after the last.

| # | Target | Mutation | Observed |
|---|--------|----------|----------|
| 1 | chroma tie-break (reproduces 20-01's 2c) | `owned.sort(key=… "seq")` → `… "created_at"` | **The finding is real.** `test_note_cap_tie_break_is_deterministic_when_created_at_collides` PASSED on all four arms, chroma included (armed run, `-rA`). Only `test_chroma_cap_eviction_survives_a_reordered_get` failed — `Extra items in the right set: 'langgraph note-2'` |
| 2 | pgvector eviction (**not** mutated by the phase) | `WHERE owner = %s` → `WHERE owner = %s OR true` in the DELETE subquery | `test_note_cap_never_crosses_owners[pgvector]` red at line 763 — `Extra items in the right set: 'langgraph bob-1'`. Every other note test stayed green: the isolation case is the sole gate and it points at the right assertion |
| 3 | pgvector tie-break (**not** mutated by the phase) | `ORDER BY created_at DESC, id DESC` → `ORDER BY created_at DESC` | `test_note_cap_tie_break_is_deterministic_when_created_at_collides[pgvector]` red on **three consecutive runs** — the secondary key is load-bearing and the gate is not flaky-green |
| 4 | the blast-radius pin | a comment carrying the `store.add(` token appended to `migrate.py` | `test_migration_and_seed_paths_bypass_add_by_design` red at `test_memory_stores.py:235`; green again after restore. The pin reads real source |

Mutations 2 and 3 are the ones worth noting: the phase's own six mutations exercised the brute-force
stores, chroma and `migrate.py`, and left the hand-written SQL — the arm most likely to drift from
the other three — unmutated. Both properties the SQL arm has to carry alone, owner scoping and the
`id` tie-break, are genuinely gated.

---

## Criterion 2 in Detail — where "byte-identical" is proven, and where it is only true

The phase claims parity on four backends and proves it with one shared suite. Three separate
questions had to be answered, and each was measured rather than reasoned.

**1. Do the four arms produce the same survivors?** Yes, and not only inside the phase's own
assertions. The verifier's harness constructs each store from `FakeEmbedder`, drives `add()`, and
then reads survivors **out of raw storage** — `entries` for the brute-force pair, `_collection.get`
for chroma, a `SELECT … ORDER BY id` for pgvector. Three constructions, one answer each time:

```
[json]     eviction len=3 survivors=['langgraph note-2','langgraph note-3','langgraph note-4']
[memory]   eviction len=3 survivors=['langgraph note-2','langgraph note-3','langgraph note-4']
[chroma]   eviction len=3 survivors=['langgraph note-2','langgraph note-3','langgraph note-4']
[pgvector] eviction len=3 survivors=['langgraph note-2','langgraph note-3','langgraph note-4']
```

**2. Does the pgvector arm actually run?** Yes. `-k "cap and pgvector"` armed at `:54329` reports
`4 passed`; the identical selection with the DSN removed reports four `SKIPPED … DATABASE_URL is
not set` lines naming the four cap cases. A suite that skipped its fourth arm would look the same
in a headline count, so the two-sided check is the one that matters.

**3. Is the collision the test asserts against actually manufactured?** Yes, and the verifier
re-measured it rather than reading 20-01's figure. Distinct `created_at` values among the three
existing notes, before and after the forcing, on each live backend:

```
[json]     distinct before=3 after=1
[memory]   distinct before=3 after=1
[chroma]   distinct before=3 after=1
[pgvector] distinct before=3 after=1
```

`before=3` on every arm is the honest reading: three sequential `add()` calls through a real store
(embedding, a chroma write, a Postgres round trip) are slow enough that the clock separates them
here, so the tie is genuinely manufactured rather than hit by luck. The suite's own claim about
14-unique-values-per-200-calls describes a tight `time.time()` loop, not this path, and 20-01
says so.

**The qualification.** Criterion 2 credits the shared suite with the proof. For one property on
one backend that credit is misplaced, and the phase reported it before the verifier could find it.
With chroma's eviction sorted by `created_at` instead of `seq`, the four-arm collision case passes
on all four arms — chromadb 1.4.1 hands `get()` back in insertion order and Python's sort is
stable, so the wrong key produces the right answer. The regression is caught only by
`test_chroma_cap_eviction_survives_a_reordered_get`, which lies about `get()`'s order **and** pins
the clock; 20-01-SUMMARY:153-158 is correct that either alone would leave the gate green over a
broken tie-break. That gate is in the tree, is red under the mutation, and names the hazard in its
docstring. The verdict stands; the wording "proven by the shared 4-arm contract suite" should be
read as "proven by the shared suite plus one stubbed gate the suite structurally cannot replace".

---

## Criterion 1 in Detail — the bound is physical, per-owner, and holds in both directions

`len()` is unfiltered on all four backends, which is why every case asserts on it: against
`query()` alone an eviction is indistinguishable from a relevance or TTL filter, and only one of
those bounds the store. The verifier went one step further and read raw storage, so even a
mutated `__len__` could not have produced the results above.

Owner scoping was checked in **three** directions, because the interesting failures are not
symmetric:

| Direction | Construction | Result on all four backends |
|-----------|--------------|------------------------------|
| Overflowing owner does not take another's | bob's note written FIRST, so it is globally oldest; alice then overflows a cap of 2 | `{'': [orphan-1], 'alice': [alice-2, alice-3], 'bob': [bob-1]}`, `len()==4` |
| A second owner reaching their own cap evicts nothing of the first's | bob's second note added after alice sits at cap | alice unchanged, bob holds both, `len()==5` (contract case, armed, green) |
| `''` is a real bucket in both senses — it survives others' evictions **and** is itself capped | four `owner=''` notes at cap 3 | `len()==3`, survivors `{orphan-2, orphan-3, orphan-4}` |

The third row is the one the suite does not gate (see notes). The behaviour is correct on every
backend; only the test for it is missing, and the likelier regression — `''` treated as a wildcard
— is already caught by the isolation case.

---

## Criterion 3 in Detail — falsified by a test, and the prose left alone on purpose

The criterion asks for a *test* to falsify the README's claim, not a rewrite of the claim. Both
halves check out.

The test half: five gates now assert notes are bounded by count — four 4-arm contract cases
(`evicts_the_oldest_first`, `never_crosses_owners`, `and_ttl_compose_sweep_first`,
`tie_break_is_deterministic_when_created_at_collides`) plus the chroma reordered-`get()` gate.
The contract file's diff is a single additive block after `test_note_ttl` (`@@ -610,6 +611,303 @@`)
plus one import line; no pre-existing case was edited, so the +23 is genuinely new coverage rather
than rewritten coverage. The `--collect-only` reconciliation 20-01 performed matches the counts
the verifier measured independently: **796 / 71** keyless, **118 / 1** armed.

The prose half: `README.md:291` is byte-identical to `ccbc7b2`, verified on the git axis rather
than by grep alone. The whole README diff for the phase is two hunks of one line each, both test
counts. The bullet is now false, deliberately, and is the third such bullet standing. That is a
real cost of the sequencing and it is written down in three places rather than absorbed.

---

## Documentation Truth

Checked against `memory.py`, not against the SUMMARY's description of it.

| Doc claim (`docs/OPERATIONS.md:675`) | Code | Verdict |
|---|---|---|
| default `100` | `NOTE_CAP_PER_OWNER_DEFAULT = 100` (`:65`) | true |
| `≤ 0` or unparseable falls back to `100` | `:108-113`; verifier measured `'0'`,`'-5'`,`'3.5'`,`'banana'`,`''`,`'   '` → 100 | true |
| "inside the same `add()` that already sweeps expiry" | sweep → insert → evict in all four `add()` bodies | true |
| "identically on all four vector backends" | four-arm harness above | true |
| "never across owners" | owner-exact predicate in all four eviction blocks; verifier mutation 2 | true |
| "bounds **every** `add()`, including the notes the eval harness seeds" | `evals/harness.py:300` calls `store.add(note, owner="")` | true |
| README `:15` and `:199` read `796 tests` | verifier's own keyless run: 796 passed | true |
| `docs/OPERATIONS.md:609` CI block reads `796` | `grep -c "773"` on README and OPERATIONS both 0 | true |

`docs/DESIGN.md` is unmodified, and the verifier read all 83 lines rather than accepting the
judgement: its Memory section makes four arguments and none of them states what bounds the store.
The conditional in 20-CONTEXT ("DESIGN gets the whole-file treatment **if** this phase falsifies
it") has a false antecedent. Wave 2's call was correct.

---

## Scope Fences

| Fence | Measurement |
|-------|-------------|
| No semantic dedup or summarisation | The ABC's refusal is kept verbatim in substance at `memory.py:231-235`; no dedup code anywhere in the diff; REQUIREMENTS' Out of Scope unchanged |
| No change to recall, the relevance floor, or TTL semantics | `test_notes_are_recalled`, `test_the_relevance_floor_excludes_unrelated_notes`, `test_note_scoping`, `test_note_ttl` appear nowhere in the test diff and are green on all four arms |
| Wave 2 touched no source or tests | `git diff --stat 0941a7f HEAD -- src tests` → **0 lines** |
| Whole phase touched exactly three code files | `src/research_agent/memory.py`, `tests/test_store_contract.py`, `tests/test_memory_stores.py`; plus `README.md` (4 lines), `docs/OPERATIONS.md` (3 lines) and planning metadata |
| No dependency added | `pyproject.toml` absent from the phase diff |

---

## Verdict

**The phase can close.** All three ROADMAP success criteria hold against the tree, and all seven
plan must-have truths were re-proven by measurement or by mutation rather than accepted from a
SUMMARY. Both SUMMARYs' numbers reproduce exactly: 796 / 71 keyless, 118 / 1 armed, 41/41 evals
with a real exit 0, ruff clean both forms.

Two things distinguish this phase from one that merely passed. First, its central claim was
qualified by its own executor before verification: the shared four-arm suite cannot see a chroma
tie-break regression, and the phase found that by mutation, reported it in the SUMMARY, in
20-VALIDATION and in ROADMAP, and shipped a separate gate for it. The verifier reproduced the
mutation and confirms the finding is true as stated — the honest report was accurate, not
defensive. Second, the phase's own mutation set left the SQL arm untouched; two verifier mutations
against it found both of its distinguishing properties genuinely gated, so the gap in the mutation
coverage did not conceal a gap in the tests.

Nothing blocks Phase 21. The four warnings are: the criterion-2 qualification above (recorded, not
actionable), the knowingly-false README bullet (Phase 22's, byte-identical as intended), the
REQUIREMENTS checkbox flip (due at ship, one line), and two stale planning surfaces the phase
measured and deferred with their replacements already written down.

## Gap closed after verification

The verifier's one nit — the `""` bucket had no case asserting it is itself capped — was closed
in the same session rather than deferred, matching Phase 18's precedent of closing what
verification finds. `test_note_cap_applies_to_the_orphan_bucket_too` now runs on all four arms.
It is not redundant with the isolation case: an implementation that skips the empty owner
entirely passes that case (the orphan rows do survive alice's eviction) and fails only this one.
The mutation was observed — `if owner and len(owned) > cap` reds json and memory with
`orphan-1` surviving, chroma passes and pgvector skips, since the mutation reaches only the
brute-force path. Suite moved to **799 passed / 72 skipped** keyless and **122 / 1** armed;
README and OPERATIONS counts followed. This changes no verdict above; it removes the one
behaviour the phase relied on measurement alone to know.

---

_Verified: 2026-08-14T11:53:06Z_
_Verifier: Claude (gsd-verifier) — goal-backward, 4 mutations, 4 independent measurements_
