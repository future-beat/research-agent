---
phase: 18-independent-eval-judge
plan: 03
subsystem: docs/adr
tags: [adr-ceremony, supersession-chain, derived-counts-checker, ordering-trap, register-reopened, whole-file-pass]

# Dependency graph
requires:
  - phase: 18-independent-eval-judge
    plan: "01"
    provides: "the judge on claude-opus-4-8 at zero cost change — the decision ADR-0012 records"
  - phase: 18-independent-eval-judge
    plan: "02"
    provides: "the refusal guard ADR-0012 records as part of the same requirement"
  - phase: 18-independent-eval-judge
    plan: "research"
    provides: "trap #2 (the :2560 status-line collision), pitfall 7 (whole-file passes mean counting), assumption A2 (the Fable reasons are attributed, not measured)"
  - phase: 17-doc-correctness
    plan: "04"
    provides: "probe A5's shape — the derived-counts checker specified there and never built"
provides:
  - "docs/adr/0012-judge-independent-of-the-critic.md — the record: independence by model identity, the family residual stated, the register reopened, Fable declined and attributed"
  - "ADR-0010 status line: Superseded by ADR-0012 (Phase 18), one-line diff"
  - "the extended chain test — 0005 -> 0010 -> 0012, every status line asserted, the pointer 18-04 will aim at ADR-0012 guaranteed to resolve"
  - "test_the_adr_index_counting_prose_is_derived_from_the_table — counts derived from the table's Status cells, plus a successor-exists-and-claims-it check on every superseded row"
  - "the measured fact that the supersession convention DELETES a middle-of-chain record's own `supersedes` claim — which is trap #2's mechanism and also killed the checker's first back-reference design"
affects: [18-04, 21, 22]

# Tech tracking
tech-stack:
  added: []  # zero packages installed
  patterns:
    - "Derive a document's counting prose from the document's own table; never grep for the string you just typed. Under a row flip both literal greps stay green and the derived checker reds."
    - "A back-reference gate must assert text that the conventions it polices are not allowed to delete. `supersedes ADR-NNNN` lives in a status line the next supersession overwrites; `Carried forward from ADR-NNNN` lives in a body no supersession may edit."
    - "When a record is superseded in part, the index says which part. A `Superseded` status invites the reading that everything under it is dead, and ADR-0010 has a position that is still deployed."
    - "Attribute a decision's reasons at the granularity they were verified. One of Fable's three was checked against a price table; two were the owner's stated context. The record says which is which."

key-files:
  created:
    - docs/adr/0012-judge-independent-of-the-critic.md
  modified:
    - docs/adr/0010-judge-rederived-for-an-independent-critic.md
    - docs/adr/README.md
    - README.md
    - tests/test_evals.py
    - .planning/PROJECT.md
    - .planning/phases/18-independent-eval-judge/deferred-items.md

key-decisions:
  - "The checker's first back-reference design was wrong, and its red is the finding. It required every `Superseded by` target to contain `supersedes ADR-`; it reds on ADR-0010, because the convention had just replaced the status line where that phrase lived. **A middle-of-chain record stops claiming its own supersession the day it is superseded** — that is trap #2's mechanism seen from one level up, and it is why the 0005->0010 half now has to be held from 0005's side. Re-targeted at `Carried forward from ADR-NNNN`, which lives in a body the convention forbids editing, with either form accepted."
  - "The plan's arithmetic was CHECKED and was correct for the first time in this lesson family. Twelve records, eight Accepted, four supersessions — derived cell by cell from the index table before a number was typed (0001,0002,0004,0007,0008,0009,0011,0012 Accepted; 0003,0005,0006,0010 Superseded). Recorded because five prior plans in this family had it wrong (13-05, 14-02, 15-03, 16-02, 16-03, 17-01) and the discipline is to check, not to expect a miss."
  - "`each was forecast by the record it overturned` was false and was rewritten rather than deleted. Verified: ADR-0005, ADR-0003 and ADR-0006 each carry an `### Expected reversal` section; ADR-0010 carries none — its only `Expected reversal` hit is a reference to 0005's. The index now says three of four were forecast and the fourth was not, and says why: 0010 was written into a register the project was closing."
  - "The index's `Reading a superseded record` prose gained a paragraph rather than an edit, because ADR-0010 is the first PARTIAL supersession in the trail. Only the judge==critic acceptance died; the critic-above-writer position is still deployed and still has no successor record. A `Superseded` status with no such note invites a reader to treat the whole record as dead and quietly reopen the critic's model."
  - "Root README.md joined the ADR commit; .planning/PROJECT.md did not. README:40's `(Nine then; eleven now, three superseded)` is a count this commit falsified, so it belongs in the commit that falsified it. PROJECT.md's two count sites are planning state and rode the metadata commit. The two stale TEST counts found in the same sweep were logged to deferred-items.md instead: they were stale before this phase and 18-VALIDATION already assigns README's to 18-04, so fixing one of the pair would leave them disagreeing."

# Metrics
duration: 41min
completed: 2026-08-13
---

# Phase 18 Plan 03: ADR-0012 and the supersession chain Summary

**One-liner:** ADR-0012 supersedes exactly one of ADR-0010's two positions — the judge==critic
acceptance, not the critic-above-writer stance — states the residual it accepts in its own voice
(Opus 4.8 is the critic's *family*, so this buys model identity and a family-correlation argument
survives), states plainly that it reopens the reversal register v1.1 closed as spent, and lands in
ONE commit with the status flip, the re-derived index and the extended chain test, because the
convention's status-line edit deletes the very string the chain test asserted.

## Measured baselines and deltas

| Gate | Before (post-18-02) | After | Delta |
|------|---------------------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:cacheprovider`) | 747 passed / 67 skipped | **748 passed / 67 skipped**, exit 0 | **+1 passed, +0 skipped** — exactly the one test this wave added, no unexplained skip |
| `tests/test_evals.py` | 177 passed | 178 passed | +1 (the index checker; the chain test was extended in place, not duplicated) |
| Offline evals (`ANTHROPIC_API_KEY="" .venv/bin/python -m evals`) | 41/41 exit 0 | **41/41 (100% vs 90% required), exit 0** (real `$?`) | unchanged — a docs wave stales nothing |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | clean, both forms | — |
| ADR records on disk | 11 | **12** | +0012 |
| ADR records `Accepted` | 8 | **8** | +0012, −0010 |
| Supersessions that have happened | 3 | **4** | 0010 → 0012 |
| `grep -rc "judge and the critic share" docs/adr/0012-…md` | — | **0** | 18-04's grep gate stays anchored at its 1 → 0 baseline (`docs/OPERATIONS.md:803`) |

## What shipped — Tasks 1 + 2 + 3, one commit, `bc7cf40`

```
bc7cf40 docs(18-03): ADR-0012 supersedes ADR-0010's judge==critic acceptance
 README.md                                          |   2 +-
 docs/adr/0010-judge-rederived-for-an-independent-critic.md |   2 +-
 docs/adr/0012-judge-independent-of-the-critic.md   | 209 +++++++++++++++++++++
 docs/adr/README.md                                 |  38 +++-
 tests/test_evals.py                                | 122 ++++++++++--
 5 files changed, 348 insertions(+), 25 deletions(-)
```

One commit by necessity. Verified by `git show --stat`, which is validation contract row 5.

### Task 1 — the record

`docs/adr/0012-judge-independent-of-the-critic.md`, house shape (title, `**Status:**`,
`**Source:**`, `## Context`, `## Decision`, `## Consequences` with `### Accepted` /
`### Rejected alternatives`). Status line is convention step 2 verbatim:
`**Status:** Accepted — supersedes ADR-0010`. All seven required contents present:

| # | Requirement | Where in the record |
|---|-------------|---------------------|
| 1 | Supersedes ONLY the judge==critic acceptance; critic-above-writer untouched | `## Context` — "The position being superseded" / "The position left standing", with `CRITIC_MODEL` named as unmoved and "**Nothing in this record is a judgement about the critic**" |
| 2 | Reopens the register, plainly | `## Context` closing paragraph + `### Accepted` bullet 2; says the reopening is stated *here* rather than inferred from a table that quietly grew a row |
| 3 | The family residual, in the record's own voice | `### The residual, in this record's own voice` — the skeptic's argument "still has his argument after this record", and the exact sentence: independent of the writer's model, independent of the critic's model, **not** independent of the critic's family |
| 4 | Fable offered and declined, attributed and dated | `### claude-fable-5 was offered and declined` — 2026-08-13, the owner's decision; reason 1 (2× leg) verified against the table, reasons 2–3 (retention, hotter classifiers) explicitly "the decision context he stated, not measurements this project made" |
| 5 | Zero cost change against the price identity | `### Zero cost change, and *exactly* zero` — the two-row table, $5/$25/$6.25/$0.50 identical |
| 6 | `### Carried forward from ADR-0010` | Six carries: the different job, judge ≠ writer, the critic's flip, the structured verdict + fail-loud parse, `EVAL_JUDGE_MODEL` and "stronger" as a preference, and 0010's own supersession of 0005 |
| 7 | The refusal guard as part of the same requirement | `### The refusal guard is part of the same decision` — "not a property of which model the judge runs on"; a latent defect on Opus 5, on Opus 4.8, and loudest on the declined candidate |

**Phrasing fence honoured.** The literal fragment `judge and the critic share` appears **0** times
in ADR-0012 and exactly **1** time in `docs/` — `docs/OPERATIONS.md:803`, which is 18-04's
baseline. 18-04's recursive grep gate is not contaminated.

**ADR-0010's body was not touched.** `git show bc7cf40 -- docs/adr/0010-…md` is one line.

### Task 2 — the convention, the index, the checker

**ADR-0010:** line 3 only. `-**Status:** Accepted — supersedes ADR-0005` /
`+**Status:** Superseded by ADR-0012 (Phase 18)`. One insertion, one deletion.

**`docs/adr/README.md` — whole-file pass, and a whole-file pass meant counting.** Every number
was derived from the table before it was typed:

| Derived from the table | Count | Rows |
|------------------------|-------|------|
| Records | 12 | 0001–0012 |
| `Accepted` | 8 | 0001, 0002, 0004, 0007, 0008, 0009, 0011, 0012 |
| `Superseded` | 4 | 0003, 0005, 0006, 0010 |

Changed:
- **Index table:** the 0012 row; 0010's Status → `Superseded` and Superseded-by →
  `[ADR-0012](0012-judge-independent-of-the-critic.md) (Phase 18)`, formatted to match the
  0003/0005/0006 superseded rows.
- **Counting prose:** eleven → twelve, three → four supersessions, with 0012's overturn of 0010
  in Phase 18 named alongside the other three.
- **The forecasting claim, rewritten rather than deleted.** "each was forecast by the record it
  overturned" is now false. Verified against the files, not assumed: `### Expected reversal`
  exists in 0005, 0003 and 0006 and does **not** exist in 0010 (its single `Expected reversal`
  hit is a citation of 0005's). The prose now says three of four were forecast, the fourth was
  not, and why — 0010 was written into a register the project was closing.
- **The spent-register paragraph, rewritten.** The empty-set claim is gone. The register was
  declared spent with Phase 17 and reopened once, deliberately, by Phase 18, with ADR-0012
  stating the reopening in its own text. The honest reading is now spelled out: no supersession
  in the table is *pending*, and the register is no longer closed.
- **The enumerating paragraph** (17-04's lesson, and the one a count-only grep would miss):
  "ADR-0006 onward are the odd ones out … there is no `docs/DESIGN.md` passage behind any of the
  **six**, so all **six** carry `**Source:**`" → **seven**, with ADR-0012 added to the list by
  name and phase.
- **`Reading a superseded record`** gained a paragraph for ADR-0010, because it is the first
  **partial** supersession and the first three-deep chain: which record to read for what, that
  only one of 0010's two positions was overturned, that the critic-above-writer position is
  still deployed with no successor record, and that nothing below 0010's status line was edited.

**The new checker** — `test_the_adr_index_counting_prose_is_derived_from_the_table`, beside the
`:2560` family, selected alone by `-k "index"` (verified: that selector collected **0** tests
before this wave). It parses `| NNNN |` rows, derives the three counts from the Status cells,
asserts `accepted + superseded == len(rows)` so a mis-parse cannot shrink both silently, and
asserts the prose carries the spelled forms. Nothing hardcodes twelve/eight/four: a thirteenth
record makes the checker demand the word *thirteen*.

It also holds one thing the plan did not ask for and the chain test cannot reach: **every
`Superseded by` cell must name a file on disk that claims the record the index credits it with**,
and every `Accepted` row must carry no successor link. The index is the third party to a
supersession the chain test holds two halves of.

### Task 3 — the chain test, extended

`test_judge_critic_collision_warning_points_at_a_record_that_exists` now holds three records and
four status facts:

| Claim | Held from |
|-------|-----------|
| 0005, 0010, 0012 all exist on disk | `path.exists()` per record, named in the message |
| 0005 → 0010 (Phase 16) | `Superseded by ADR-0010` in **0005** |
| 0010 → 0012 (Phase 18) | `Superseded by ADR-0012` in **0010** |
| 0010 → 0012, other half | `supersedes ADR-0010` in **0012** |

Extended, not duplicated — the same test keeps holding both halves of every supersession it
names, which is the 16-03 lesson it was created by. Its docstring now states that the operator
line it serves points at ADR-0012, and states **why one assertion was replaced rather than
dropped**: `supersedes ADR-0005` lived only in 0010's status line, which the convention
overwrites, so the 0005 half moved to 0005's own permanent side.

## The trap, demonstrated rather than dodged

With Tasks 1 and 2 in the working tree and Task 3 not yet written, the pre-existing test reds
exactly as 18-RESEARCH's pitfall 2 predicted:

```
>       assert "supersedes ADR-0005" in record.read_text()
E       AssertionError: assert 'supersedes ADR-0005' in '# ADR-0010 — The judge is re-derived …'
tests/test_evals.py:2859: AssertionError
1 failed, 177 deselected
```

That is the whole argument for one commit, observed rather than inherited.

## Mutation probes — each observed red, then reverted

### Probe 1 (17-04's probe A5) — flip a table row's Status, leave the prose alone

`| 0009 | … | Accepted |` → `Superseded`, prose untouched:

```
=== the literal greps a typed-string gate would use ===
1        # grep -c "Eight of the twelve records"
1        # grep -c "Four supersessions"
(both nonzero => a literal grep gate stays GREEN under this mutation)

=== the derived checker ===
E       assert 'seven of the twelve records' in '…eight of the twelve records are `accepted` today…'
FAILED tests/test_evals.py::test_the_adr_index_counting_prose_is_derived_from_the_table
```

The exact contrast 17-04 specified and 18-03 built: **the gate that greps the string it was typed
from is green; the gate that derives the number is red.** Reverted; checker green again.

### Probe 2 — revert ADR-0010's status line to `Accepted — supersedes ADR-0005`

```
>       assert "Superseded by ADR-0012" in records["0010"].read_text()
E       AssertionError: assert 'Superseded by ADR-0012' in '# ADR-0010 — The judge is re-derived …'
FAILED tests/test_evals.py::test_judge_critic_collision_warning_points_at_a_record_that_exists
1 failed, 1 passed, 176 deselected
```

The chain breaks at 0010 → 0012 and the chain test says so. The index checker stays green in the
same selector — correctly: it reads the table, not the record status lines, and the two gates
cover different halves.

### Probe 3 — rename ADR-0012 away

```
E   AssertionError: the record trail names ADR-0012; 0012-judge-independent-of-the-critic.md is not on disk
FAILED tests/test_evals.py::test_judge_critic_collision_warning_points_at_a_record_that_exists
E   AssertionError: index points at a missing record: 0012-judge-independent-of-the-critic.md
FAILED tests/test_evals.py::test_the_adr_index_counting_prose_is_derived_from_the_table
```

**Both** gates red, on different grounds — the pointer and the index link. The record 16-03
renamed away to prove nothing caught it now reds two tests. Restored; `git status --short` clean
of any rename.

## Deviations from plan

### [Rule 1 — the gate was wrong, and its red is the finding] The checker's back-reference had to be re-targeted

The first version of the index checker required every `Superseded by` target to contain the text
`supersedes ADR-`. It went red on its first run — on **ADR-0010**:

```
E   AssertionError: 0010-judge-rederived-for-an-independent-critic.md does not claim the
    supersession the index credits it with
```

Not a mis-typed assertion: a real property of the convention nobody had written down. **The day a
record is superseded, the convention overwrites the status line that carried its own `supersedes`
claim** — so every middle link in a chain stops claiming, in text, the supersession the index
still credits it with. That is trap #2 seen one level up, and it is why the 0005 half of the
chain test had to move to 0005's side rather than be re-asserted from 0010's.

Re-targeted at `Carried forward from ADR-NNNN`, which lives in a body the convention explicitly
forbids editing, with the status-line form still accepted for a live superseder. Verified present
in all four superseders (0007, 0010, 0011, 0012). The comment in the test states the reasoning so
the next reader amends a stated reason instead of "simplifying" it back.

**House-discipline note:** the plan said "if a probe comes back green, re-target it and say so."
This is the mirror case — a probe came back **red on correct code**, and the gate was at fault
rather than the tree. Same rule, same disclosure.

### [Rule 1 — this commit falsified a count elsewhere] `README.md:40`

`*(Nine then; eleven now, three of them superseded on the record — see 16 and 17.)*` became false
the moment ADR-0012 landed. Corrected to twelve / four **inside the same commit**, because a
commit that falsifies a count and leaves it standing is the drift the whole ADR ceremony exists
to prevent. The cross-reference "see 16 and 17" was left alone: it points at README phase-log
entries, and v1.2 has no entry yet.

`README.md:285`'s Limitations bullet was **not** touched (Phase 22's, by milestone scope), and
neither was the phase-16 log bullet at `:47` — a historical entry, true as written at its time,
which the 16-03 convention tolerates.

### [Rule 2 — a live doc asserting a superseded position] `.planning/PROJECT.md`

Three sites, all falsified by this commit, all corrected in the metadata commit rather than the
ADR one (planning state, not a doc deliverable):

- § Current State: "the reversal register … is now spent. `docs/adr/` holds 11 records, three of
  them superseded" → the register "closed as spent, then was reopened once, deliberately, by
  v1.2's ADR-0012", and 12 records / four superseded.
- § Key Decisions, the ADR-promotion row: "11 records now, 3 superseded" → 12 / 4.
- § Key Decisions, the eval-judge row: still says "Judge == critic is recorded as an
  **acceptance**". The row is a correct assessment of the decision as it stood, so it was
  extended rather than rewritten — the different-job leg still stands, the acceptance is
  superseded by ADR-0012, and the link is there.

### [out of scope, logged not fixed] Two stale test counts

The number sweep turned up `README.md:15` and `:199` (740, both) and `.planning/PROJECT.md:31`
(737 keyless / 801 with Postgres) against a measured **748**. Neither was falsified by this plan —
PROJECT.md's was already stale at the phase's 740 baseline — and 18-VALIDATION row 7 assigns
README's count to **18-04**. Fixing one of the pair here would leave them disagreeing. Logged in
`deferred-items.md` with the measurement and the owner.

### [not a deviation, stated to be explicit] What was not touched

`evals/harness.py`'s `_state_judge_critic_relation` and the collision wording tests (18-04's
deliverable — the tests still pin `ADR-0010` in the stderr line, and that record still exists,
now `Superseded`, which is precisely the state 18-04's re-derivation resolves). `graders.py`'s
module docstring, `docs/DESIGN.md`'s trailer, `docs/OPERATIONS.md`'s record-mode paragraph — all
18-04's. `README.md:285` — Phase 22's. The critic, `fly.toml [env]`, `evals/` source — untouched.
No packages installed.

## Success criteria, measured

| Criterion | Evidence |
|-----------|----------|
| ROADMAP SC-3: ADR-0012 exists, records the supersession, states the register reopening plainly, carries the family residual honestly | The record, § Context closing paragraph, § The residual in this record's own voice |
| One commit contains 0012 + 0010's status line + the index + the test extensions | `git show --stat bc7cf40`, quoted above |
| ADR-0010 differs from its committed state by exactly one line | `1 file changed, 1 insertion(+), 1 deletion(-)` on the status line |
| Counting prose provably agrees with the table, by derivation | The checker; probe 1's contrast against the literal greps |
| Chain test red under both mutations | Probes 2 and 3, quoted |
| Full suite + offline evals 41/41 + ruff green, keyless | 748/67 exit 0; `PASS 41/41 (100% vs 90% required)` exit 0; ruff clean both forms |

## Threat register — dispositions discharged

| Threat ID | Disposition | Discharged by |
|-----------|-------------|---------------|
| T-18-06 (repudiation, supersession chain) | mitigate | The chain test holds three records and four status facts in one assertion set. A dangling record reds it (probe 3); a disagreeing status line reds it (probe 2). The pointer 18-04 will aim at ADR-0012 cannot go dangling without the suite saying so. |
| T-18-07 (repudiation, index counting prose) | mitigate | Counts derived from the Status cells, never from the typed string — probe 1 shows the literal greps are decorative under the mutation that matters. Extended beyond the plan: a `Superseded by` cell must name a file on disk that claims the supersession, so an index link cannot dangle either. |
| T-18-SC (package installs) | accept | Zero packages installed. |

## What wave 4 inherits

- **ADR-0012 exists and the chain resolves**, so 18-04 can point the re-derived collision line at
  it without creating a dangling pointer. The chain test is the guarantee, and it already names
  0012 — 18-04 does not need to add a record-exists assertion, only to change what the stderr
  line says.
- **The collision tests are untouched and still pin `ADR-0010`.** That is deliberate: the record
  they name still exists, now `Superseded`, which is the exact state 18-04's re-derivation
  resolves. Nothing was pre-empted.
- **`docs/OPERATIONS.md:803` is still the sole `judge and the critic share` hit in `docs/`** — the
  1 → 0 baseline for 18-04's grep gate is intact and uncontaminated by the new record.
- **The deferred test counts** — `README.md:15`/`:199` and `.planning/PROJECT.md:31` — measured at
  748 and owned by 18-04's README pass.
- **A warning about the convention, now written down:** a superseded record stops claiming its own
  supersession in text. Any future gate that checks a supersession from the superseder's side must
  use `Carried forward from ADR-NNNN`, not the status line.

## Self-Check: PASSED

- `docs/adr/0012-judge-independent-of-the-critic.md` — present, 209 lines, status line
  `**Status:** Accepted — supersedes ADR-0010`.
- `docs/adr/0010-judge-rederived-for-an-independent-critic.md` — present, status line
  `**Status:** Superseded by ADR-0012 (Phase 18)`, one-line diff from its committed state.
- `docs/adr/README.md`, `README.md`, `tests/test_evals.py` — present and modified as claimed.
- `.planning/phases/18-independent-eval-judge/18-03-SUMMARY.md` — this file.
- Commit `bc7cf40` exists on `gsd/phase-18-independent-eval-judge` and lists all five files in
  `git show --stat`.
- Working tree clean of every mutation: 0009's row restored, 0010's status line restored, ADR-0012
  restored to its filename (`git status --short` showed no rename).
