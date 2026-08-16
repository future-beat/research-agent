---
phase: 22-limitations-recorded
plan: 01
subsystem: docs + evals gates
tags: [adr, close-out, derived-counts, known-defects, operations-posture, keyless, zero-spend]

# Dependency graph
requires:
  - phase: 21.5-classifier-on-opus-5
    plan: "*"
    provides: "the settled split this plan measures rather than assumes — 25 fixtures / 15 refusals, evals denominator 65, suite 827/72, ADR-0013 TAKEN by the classifier record, and REQ-classifier-model already flipped"
  - phase: 21-forty-recorded-answers
    plan: "*"
    provides: "evals/REFUSALS.json with per-case kind/detail/cost_usd — the evidence store the defect record points at; and the eval-section prose this plan re-derives rather than authors"
  - phase: 18-independent-eval-judge
    plan: "*"
    provides: "ADR-0012, the fence that keeps the judge's token budget out of this phase, and the 0012 Nygard register ADR-0014 is written in"
provides:
  - "docs/adr/0014-cost-approximation-by-design.md — the cost position stated as a decision for the first time, with the four measured Admin-API rejection reasons; criterion 1's record half. NOTE THE NUMBER: 0014, not 0013."
  - "docs/adr/README.md — the 0014 index row plus every counting sentence re-derived (ten of the fourteen; the newest-record sentence now covering 0013 and 0014; the Source paragraph at nine, with a note on why DESIGN.md's Cost section is not a promotion)"
  - "docs/OPERATIONS.md '### The free-tier posture, and the upgrade path' under '## Going stateless' — the anchor #the-free-tier-posture-and-the-upgrade-path that 22-02's database bullet links; criterion 3's target half"
  - "README.md's Tests-and-evals section — the fifteen refusals decomposed 7/2/6 and both paid-run defects recorded with their evidence and the reason neither is fixed here"
  - "tests/test_evals.py::test_the_readme_eval_counts_are_derived_from_the_tree — the derived-counts gate, +1 keyless test; _SPELLED extended to forty"
  - "the wave-2 handoff: the seven Limitations bullets at their CURRENT line numbers (README:326 heading, bullets :334–:340), the exact link targets 22-02 must use, and the four deletion candidates confirmed present exactly once"
affects: [22-02]

# Tech tracking
tech-stack:
  added: []  # zero packages. 22-RESEARCH's Package Legitimacy Audit is N/A and stays N/A.
  patterns:
    - "A derived gate holds the KIND LIST, not just the per-kind numbers. Three counts that are each correct while a fourth category exists uncounted is the one drift a per-number check cannot see — so the test asserts the set of refusal kinds is a subset of the kinds the prose describes, and a new kind demands the paragraph move before the list does."
    - "A count that falls to zero is DROPPED from prose, never written as a zero. An eval section announcing 'zero are a real defect' reads as a boast; the sentence that belongs there is none. The gate asserts the phrase's ABSENCE on that branch, across every spelling."
    - "Re-read the external source at execution instead of trusting the research's quote. Two of three sourced facts reproduced verbatim; the third had moved off the page entirely. A rejection reason resting on a sentence that is no longer there is worse than one that names which sentence moved."
    - "Slug-anchor a plan's file gates, not the number. ADR-0013 was taken between planning and execution and every Task 2 gate passed unchanged because they matched *-cost-approximation-by-design.md."

key-files:
  created:
    - docs/adr/0014-cost-approximation-by-design.md
    - .planning/phases/22-limitations-recorded/22-01-SUMMARY.md
  modified:
    - docs/adr/README.md
    - docs/OPERATIONS.md
    - README.md
    - tests/test_evals.py

key-decisions:
  - "ADR-0014, not ADR-0013. Phase 21.5 took 0013 for `classifier-on-its-own-model` between this plan being written and executing, so the plan's step-5 renumber contingency became the live path. The slug `cost-approximation-by-design` is unchanged and every Task 2 gate was slug-anchored, so none of them needed editing. 22-02 must link `docs/adr/0014-cost-approximation-by-design.md`."
  - "One of the research's four Admin-API facts could NOT be reproduced at re-read, and the ADR says so. The quoted sentence 'Admin API keys are owned by the organization and remain active even after the creator is removed' is not on the Usage & Cost API page, the Create-an-Admin-API-key page, or the Admin API overview page today. Reason 1 now rests on what IS there and is stronger: Console keys 'do not have selectable scopes; every key carries full access to all endpoints that accept Admin API keys.' Reasons 2 (daily-only buckets, workspace/description grouping) and 3 (~5-minute lag, 'delays may occasionally be longer') reproduced verbatim."
  - "A fact the research did not have, added: the docs state the Admin API is unavailable to individual accounts. For a single-developer project that makes reason 1 a precondition problem, not only a blast-radius one. Stated as the documented precondition rather than as a claim about this account."
  - "The ADR names the alternative's OWN stated purpose before rejecting it — the endpoint's docs list 'Cost reconciliation: Match internal records with Anthropic billing' as a use case. Rejected on fit for this service, never on capability. A rejected-alternatives section that pretends the alternative is bad at its job is the weaker record."
  - "The eval prose now decomposes the refusals THREE ways (7 grader / 2 judge_truncated / 6 recorded_then_failed_replay), not two. This is a deviation from the plan's template list, which named only the two defect counts. The seven were the one part of the split nobody had ever had to state — the prose said 'Most refusals are the machinery working' with no number — and the derived gate caught it on its first execution."
  - "P-01 honoured with zero drift: no Limitations bullet was created for the refusal residue or either defect, and the Limitations section is proven byte-identical to the phase's start by diffing HEAD's copy against the working tree's. It is 22-02's diff exclusively."
  - "The OPERATIONS posture note's no-replica claim is labelled as carried from the free tier's published shape, not measured here (22-RESEARCH Assumption A2 handled honestly rather than quietly). It is also noted to be wrong in the safe direction if wrong at all: the posture claims less capability than exists."

# Metrics
duration: 70min
completed: 2026-08-16
status: complete

actuals:
  tokens: 6906    # chars/4 over the realized diff (27,624 chars across 5 files)
  tasks: 3
  commits: 2      # Task 1 is measurement and makes no commit, by design
---

# Phase 22 Plan 01: The records the close-out points at Summary

**One-liner:** ADR-**0014** (not 0013 — 21.5 took it) states cost-approximation-by-design with the four Admin-API rejection reasons re-read at execution and one of them corrected on the record; OPERATIONS gains the argued free-tier posture and its upgrade path; README's eval section decomposes the fifteen refusals 7/2/6 and records both paid-run defects with their evidence, gated by a derived-counts test that found an unquantified claim on its very first run.

**Zero spend.** Every command in this plan ran with `ANTHROPIC_API_KEY="" VOYAGE_API_KEY=""` explicitly prefixed. No `--yes`, no `--live`, no `--record`.

---

## Task 1 — the execution baseline, measured 2026-08-16, before any edit

Every number below came from a command run this session. **No value from any planning
document was carried into any surface this plan wrote.**

### The suite

```
$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:warnings | tail -1
827 passed, 72 skipped in 27.37s

$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:warnings --collect-only | tail -1
899 tests collected in 0.77s
```

**827 passed / 72 skipped / 899 collected.** The plan's own frontmatter and 22-VALIDATION
carried **806/72/878** — a planning-time snapshot. 21.5 added 21 tests; the drift is
exactly that.

### The evals

```
$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --quiet; echo "evals exit: $?"
PASS  65/65 cases (100% vs 90% required)
  $2.8240 · 0.1s
evals exit: 0
```

**Denominator 65**, real exit 0. Planning said **59/59**. The +6 is 21.5's six new
recordings, each adding a replay leg (40 behavioural + 25 replayed).

### The split, and which cases moved

```
$ ls evals/fixtures/*.json | wc -l
      25
$ python -c "...Counter(e['kind'] for e in refusals.values())"
refusals total: 15
  grader                       7
  judge_truncated              2
  recorded_then_failed_replay  6
```

**25 recorded / 15 refused = 40, overlap empty.** Planning said **19/21**. Six cases moved
from `REFUSALS.json` into `evals/fixtures/`, named in 21.5-02-SUMMARY:
`empty-label-falls-back`, `general-defines-a-term`, `general-explains-a-concept`,
`general-how-a-mechanism-works`, `general-summary`, `injection-tries-to-force-approval`.

Two more entries did not move but were **rewritten**: `followup-with-no-prior-research`
and `followups-chain-of-three` re-attempted under the Opus 5 classifier, lost their
`topic_type` cause, and now refuse on a different grader each — their details say so
rather than carrying an invalidated reason. Both are `kind: grader` today.

**Both defect counts are unchanged at 2 and 6.** README's existing "two are a real defect
… and six are recordings that passed at record time" sentence was still true; 21.5 had
already re-checked it. What was NOT stated anywhere was the seven — see the finding below.

### The Limitations section — current locations, all seven present

`grep -n '^## Limitations' README.md` → **:293** at measurement time (**:326** after this
plan's eval-section expansion; the section content is byte-identical, only its offset
moved). All seven bullets present. The four deletion candidates each grep **exactly once**:

| Phrase | Count | Line (at measurement) | Line (now, for 22-02) |
|---|---|---|---|
| `The eval judge shares the critic's model` | 1 | :295 | **:334** |
| `Only one of forty answers is recorded` | 1 | :296 | **:335** |
| `checks that the API keys are *present*` | 1 | :299 | **:338** |
| `Notes are bounded by expiry alone` | 1 | :301 | **:340** |

Survivors, also exactly once each: `Reported cost is an approximation` (:297 → **:336**),
`Identities are free to mint` (:298 → **:337**), `The database is a single region on a
free tier` (:300 → **:339**).

The plan's hinted :295/:296/:299/:301 and :297/:298/:300 were **correct at measurement
time** — 21.5 did not move the section. This plan's own Task 3 then moved it +33 lines.

### The next ADR number — the contingency fired

```
$ ls docs/adr/ | sort | tail -3
0012-judge-independent-of-the-critic.md
0013-classifier-on-its-own-model.md
README.md
```

**0013 is TAKEN** by Phase 21.5's classifier record. The cost ADR is **0014**, slug
unchanged. Carried into Task 2's filename and flagged for 22-02's link task.

### Ruff, and the requirement flips

```
$ .venv/bin/ruff check .
All checks passed!
```

`REQ-classifier-model` is **already flipped** — `.planning/REQUIREMENTS.md:50` carries
`[x]`, and its traceability row (:120) is filled with the measured 37/38-vs-32/38 result
and the ADR-0013 pointer. ROADMAP's Phase 21.5 entry (:144) is checked; the precondition
grep returns **1**. `REQ-limitations-recorded` is still `[ ]` / `Pending` — 22-02 Task 3's
work, untouched here.

### 21.5's artifacts — no new finding category

Read in full: both plan SUMMARYs, the VERIFICATION, and the two committed reports. **No
finding beyond the two known defects appeared.** 22-RESEARCH's Open Question 1 resolves
NO: the eval-section prose needed its numbers re-derived and its third kind quantified,
but not a change of shape. One adjacent finding worth carrying: 21.5 hit a third
count-pinned-as-a-literal going stale (`test_cli_writes_the_report`), which is the
argument this plan's Task 3 gate is built on.

---

## Task 2 — ADR-0014, the index, and the OPERATIONS posture

**Commit `b10b8d1`.**

### ADR-0014, and the fact that had moved

`docs/adr/0014-cost-approximation-by-design.md`, three `##` headings, `**Status:**
Accepted`, `**Source:** Phase 22 (2026-08-16), REQ-limitations-recorded`, with
`### Rejected alternatives` under Consequences — the 0012/0013 register.

Context leans on the telemetry record already committed rather than re-deriving it:
`price_for()`'s effective-dating, `/pricing`, `cost_usd` in the SSE `result` event,
OPERATIONS' dated 2026-08-09 Voyage measurement (40 predicted / 25 reported / 0 for a
one-word document), `record_embedding`'s "Zero tokens is not an error" docstring, and the
no-multipliers-across-vendors argument. It closes with a finite, named list of what the
estimate can be wrong ABOUT, so the gap has a shape.

**The four rejection reasons were re-read at execution, and the record says what changed:**

| Reason | Research (2026-08-16) | Re-read at execution | Status |
|---|---|---|---|
| 1 — key blast radius | *"owned by the organization and remain active even after the creator is removed"* | **Sentence not present** on the Usage & Cost page, the Create-an-Admin-API-key page, or the Admin API overview. What IS there: Console keys *"do not have selectable scopes; every key carries full access to all endpoints that accept Admin API keys"* | **CORRECTED** — reason stands, on stronger current text |
| 2 — no per-run dimension | daily-only buckets, group by workspace/description | *"Time buckets: Daily granularity only (`1d`)"*, *"Group costs by workspace or description"* | verbatim |
| 3 — lag | ~5 min, may be longer | *"typically appears within 5 minutes of API request completion, though delays may occasionally be longer"* | verbatim |
| 4 — infrastructure | scheduled job + storage + correlation | argument, not a doc claim | unchanged |

**Plus one fact the research did not have:** the page states the Admin API is unavailable
for individual accounts. Recorded as a documented precondition, not as a claim about this
project's account type.

The ADR also names the endpoint's own advertised use case (*"Cost reconciliation: Match
internal records with Anthropic billing"*) before rejecting it — the rejection is on fit,
not capability. Reason 1 doubles as T-22-01's mitigation: the unbuilt alternative's blast
radius, documented.

Three further alternatives are on the record as considered and refused: reconciling
against Voyage, dropping `cost_usd` entirely, and presenting the estimate as the invoice.

### The index, same commit

Row added. Every counting sentence re-derived:

- above the table: *"Nine of the thirteen"* → **"Ten of the fourteen records are `Accepted`
  today"** (the sentence the existing test derives)
- the newest-record sentence, which named only 0013, now covers both records and states
  that neither supersedes anything
- below the table: the `**Source:**` paragraph moves from **eight to nine** and gains "and
  ADR-0014 in Phase 22's close-out" in the existing sentence pattern
- one new short paragraph, because `docs/DESIGN.md` DOES have a Cost section and a reader
  may reasonably expect a promotion — it covers the spend cap, effective-dating and
  unpriced-model handling, and never argues that the reported figure is an estimate rather
  than the invoice. That negative finding is 22-RESEARCH's, now on the surface where a
  reader would look for it.

**Mutation observed (named in the plan).** Deleted the 0014 row, left the prose:

```
E   assert 'nine of the thirteen records' in '...ten of the fourteen records are `accepted` today...'
FAILED tests/test_evals.py::test_the_adr_index_counting_prose_is_derived_from_the_table
```

The test derived nine-of-thirteen from the mutated 13-row table and demanded the prose say
it — proving the prose is enforced against the table rather than trusted. Restored,
re-run: **1 passed**. Pitfall 2 avoided: the targeted test was run immediately after the
index edit, not at the end.

### The OPERATIONS posture note

`### The free-tier posture, and the upgrade path`, exactly per P-04 (anchor
`#the-free-tier-posture-and-the-upgrade-path`), placed under `## Going stateless` **after**
"Why Supabase and not Neon" and **before** "The cutover, in order" — beside the argued
sibling, not inside the "Supabase specifics" runbook.

Every fact traces to an OPERATIONS passage or is labelled as unsourced. **None traces to
the README bullet being replaced.** The Pitfall-3 bar — the thing a careful reader did not
already have — is the argument and the path, not the numbers:

- **Why it is acceptable**: `PG_POOL_MAX_SIZE` bounds *connections* where `hard_limit`
  bounds *requests*, so the fleet holds 10 of Nano's 60 and would have to grow six-fold
  before the tier's ceiling binds; the `/health` store probes sit at 2.84/3.23/3.39 ms p50
  against a 3000 ms budget (~435× headroom at the worst sample), so a read replica would be
  relieving a primary that is not struggling; the free tier's ~7-day idle pause is
  *prevented* by the same probes that disqualified Neon, and is non-destructive anyway.
- **The closing thought** migrated from the README bullet nearly verbatim — "Fine at this
  traffic, and the first thing to look at if it isn't" — now with the argument behind it.
- **The upgrade path**: tier is a reversible toggle that raises the ceiling and puts a
  replica in reach; **region is not** — fixed at creation, so a move is a new project plus
  a data move, the shape the embedding-migration commands and the cutover order already
  rehearse. Naming what an upgrade does NOT fix is the part that makes it a path.
- **The A2 caveat, stated as a caveat**: no-read-replica is carried from the tier's
  published shape, not measured here, and if wrong it is wrong in the safe direction.

Gates: heading count 1, `read replica` appears 4× in OPERATIONS (0 before this plan),
upgrade/tier vocabulary 6× inside the section, ADR test green, ruff clean.

---

## Task 3 — the defect record and its derived-counts gate

**Commit `1937c8a`.** Test-first.

### The red was real, not manufactured — and it found something

The plan anticipated that 21.5 might have left the prose current, in which case the red
would have to be manufactured by the mutation. **21.5 had updated four of the five numbers,
and the fifth failed on the test's first run:**

```
E  AssertionError: the tree says 'seven are the machinery working';
   README's eval section does not: ... most refusals are the machinery working; two are
   a real defect ... and six are recordings that passed at record time ...
```

The prose said *"Most refusals are the machinery working"* with **no count**. Seven grader
refusals — the largest of the three kinds — were the one part of the split that had never
been stated as a number, in any surface, at any point in the milestone. The derived gate
caught an unquantified claim on its first execution, which is the strongest argument for
the pattern this plan could have produced.

### The test

`test_the_readme_eval_counts_are_derived_from_the_tree`, immediately after
`test_the_adr_index_counting_prose_is_derived_from_the_table`, in its exact spirit
(docstring names the 17-04 lesson). Everything derives through helpers the file already
has — `F.fixture_paths()`, `documented_refusals()`, `len(GOLDEN)`, `_SPELLED`. No parallel
loader, no literal count.

Two things it does that the plan's template list did not require, both deviations recorded
below:

1. **It holds the KIND LIST.** `assert set(kinds) <= set(phrases)` — a paid run surfacing a
   third defect category would leave both quoted counts correct and the paragraph silently
   incomplete. That is the one drift a per-number check cannot see, and it is exactly
   22-RESEARCH Open Question 1's failure mode, now automated instead of asked once.
2. **It implements the zero branch.** A kind that falls to zero must be dropped from the
   prose, not written as a zero, and the test asserts the phrase's absence across every
   spelling in `_SPELLED` for that branch. Nothing exercises it today (all three kinds are
   non-zero); it exists so that fixing a defect in a successor milestone forces the
   sentence out rather than leaving "zero are a real defect" behind.

Plus `assert sum(kinds.values()) == len(refusals)`, so the three-way decomposition must be
total.

Two mechanical notes: the section prose is **whitespace-collapsed** before matching,
because README is hard-wrapped and the divergence phrase straddles a newline — the claim is
the sentence, not its wrapping. And `_SPELLED` was **extended from twenty to forty**
(25 and 40 are now needed); the ADR test reads the same dict and is unaffected, which the
green run confirms.

### The prose

The three count-bearing passages re-derived, and the defect paragraph expanded per P-02
into the full known-defect record in OPERATIONS' "do not fix the five
`rls_enabled_no_policy` notices" voice — found, explicitly not fixed here, with the reason
why:

- **Seven are the machinery working** — a grader or the judge declined, which is what they
  are for; two of those entries were rewritten when the Opus 5 classifier removed their
  original cause, rather than left carrying a reason that no longer applies.
- **Two are a real defect** — the judge's verdict truncating against `max_tokens=1500`
  shared with adaptive thinking, predicted by `Judge.verdict`'s own docstring before any
  run had hit it, which is why it surfaces by name rather than as a malformed verdict.
  Not fixed here: ADR-0012 owns the judge's configuration and it does not move in a phase
  that is not about the judge.
- **Six are recordings that passed at record time and then failed replay** — five
  contested-topic cases whose pins want *proponents*/*critics* against recordings that
  argue both sides in different words, with the re-authoring **tried and reverted** because
  the same `must_mention` must also hold against `dataset.py`'s hand-authored reference
  reports; and the sixth, the hedged half-answer that admitted no source covered a forecast
  and supplied a reasoned estimate anyway — the thing the recorded-refusal grader's own
  docstring says it cannot catch, where *that record-time grading approved it at all* is
  the finding.
- A closing sentence separating defects from chosen limitations: found by a paid run,
  written down with per-case evidence rather than averaged into a pass rate.

`evals/REFUSALS.json`'s existing inline link is the only pointer (P-03). No Limitations
bullet was created (P-01).

**Mutation observed (named in the plan).** Popped `technical-version-numbers` (kind
`grader`) from `REFUSALS.json`:

```
derived-counts gate: AssertionError: the tree says 'the other fourteen are in';
                     README's eval section does not
union gate:          AssertionError: neither recorded nor documented as refused:
                     ['technical-version-numbers']
2 failed
```

**Two gates, two different axes** — one on prose drift, one on a case accounted nowhere —
which is what the mutation exists to prove. Restored with `git checkout --`
(byte-identical, `git status` clean), both green.

---

## Gates, at close

| Gate | Result |
|---|---|
| Full suite, keyless | **828 passed / 72 skipped** (Task 1 baseline 827 + exactly one test: `test_the_readme_eval_counts_are_derived_from_the_tree`) |
| Offline evals | **PASS 65/65**, real exit **0** |
| `ruff check .` | clean |
| `pytest tests/test_evals.py -k "adr or readme_eval"` | 2 passed |
| `pytest tests/test_evals.py` | 194 passed |
| Both named mutations | observed red, restored, re-run green |
| Limitations section | **byte-identical** to phase start — proven by diffing `git show HEAD:README.md`'s section against the working tree's, not by inspection |
| Spend | **$0.00** |

---

## Deviations from Plan

**1. [Rule 3 — Blocking] ADR number 0013 → 0014.**
- **Found during:** Task 1, step 5.
- **Issue:** Phase 21.5 landed `docs/adr/0013-classifier-on-its-own-model.md` between this
  plan being written and executing, so P-06's filename was taken.
- **Fix:** The plan's own step-5 contingency, applied — next free number, slug unchanged.
  Every Task 2 gate was slug-anchored (`*-cost-approximation-by-design.md`) and needed no
  edit, which is the checker's W2 note paying off.
- **Files:** `docs/adr/0014-cost-approximation-by-design.md`, `docs/adr/README.md`.
- **Impact on 22-02:** the README cost bullet must link **0014**.
- **Commit:** `b10b8d1`.

**2. [Rule 2 — Missing critical] The eval prose decomposes three kinds, not two.**
- **Found during:** Task 3, on the new test's first run.
- **Issue:** the plan's phrase-template list named the truncation and divergence counts.
  The `grader` count (7) was unstated anywhere — "Most refusals are the machinery working"
  carried no number — so the largest kind was the one thing the gate could not hold, and
  the three counts would not have been provably total.
- **Fix:** added `"{n} are the machinery working"` as a third derived phrase, plus
  `sum(kinds.values()) == len(refusals)`, plus the kind-list subset assertion. Consistent
  with P-02's "kinds kept as distinct in the prose as they are in the JSON."
- **Commit:** `1937c8a`.

**3. [Rule 1 — Correctness] ADR-0014's rejection reason 1 rests on different text than the
research quoted.**
- **Found during:** Task 2, re-glancing at the Admin-API docs as the plan instructs.
- **Issue:** the sentence 22-RESEARCH quoted is not on any of the three relevant doc pages
  today. Asserting the 2026-08-16 shape would have put a quote in an ADR that a reader
  cannot verify.
- **Fix:** the ADR states which fact reproduced, which did not, and rests the reason on the
  current no-selectable-scopes text — a stronger form of the same point. Recorded inside
  the record itself, not only here.
- **Commit:** `b10b8d1`.

**4. [Not a deviation, recorded for the verifier] `_SPELLED` extended 20 → 40.** Additive;
the ADR index test reads the same dict and is green.

No Rule 4 (architectural) situations arose. No authentication gates. No checkpoints — this
plan is fully autonomous, as its frontmatter states.

---

## What 22-02 needs

**Line numbers, current as of this commit.** `## Limitations` is at **README:326**. The
seven bullets, in order, with their dispositions:

| Line | Bullet (first sentence, verbatim) | Disposition |
|---|---|---|
| **:334** | `- **The eval judge shares the critic's model.**` | DELETE (Phase 18) |
| **:335** | `- **Only one of forty answers is recorded.**` | DELETE (Phase 21, amended) |
| **:336** | `- **Reported cost is an approximation, never the invoice.**` | SURVIVES → link **ADR-0014** |
| **:337** | `- **Identities are free to mint.**` | SURVIVES → already links ADR-0007; verify, do not author |
| **:338** | "- **`/health` checks that the API keys are *present*, not that they work.**" | DELETE (Phase 19) |
| **:339** | `- **The database is a single region on a free tier.**` | SURVIVES → link the OPERATIONS anchor |
| **:340** | `- **Notes are bounded by expiry alone.**` | DELETE (Phase 20) |

The intro is **:328–:332** (five lines, unchanged: *"Known, and deliberate for the scope.
**The v1.0 README listed nine limitations, and v1.1 has now closed all nine**…"*).

**The two exact link targets this plan locked:**
- cost bullet → `docs/adr/0014-cost-approximation-by-design.md` — **0014**, and the file
  exists on disk as of `b10b8d1`.
- database bullet → `docs/OPERATIONS.md#the-free-tier-posture-and-the-upgrade-path`. The
  heading text is load-bearing; renaming it breaks 22-02's link gate.

**Also true, and worth not re-deriving:**
- The four deletion candidates each grep **exactly once** in README, and each is
  byte-identical to what the phase that falsified it left behind. `Reported cost is an
  approximation`, `Identities are free to mint`, `The database is a single region on a free
  tier` likewise appear exactly once.
- Numbers for the intro's honest ledger: v1.2 **closed four**, **records three** by design,
  and its paid run **discovered three more things** — the classifier drift (fixed in 21.5),
  the judge truncation, and the record/replay divergence (both recorded here, neither
  fixed).
- The fenced block's `pytest # 827 tests` comment is now **stale by one** — the suite is
  **828** after this plan's test. That comment is 22-02's whole-file pass, deliberately
  untouched here.
- `REQ-limitations-recorded` is still `[ ]` at `.planning/REQUIREMENTS.md:88` with a
  `Pending` traceability cell at :121. `REQ-classifier-model` is already flipped —
  22-02 Task 3 verifies rather than flips it.
- 22-VALIDATION rows for `22-01 T1`, `22-01 T2` and `22-01 T3` are satisfied and can be
  moved off `pending` at reconciliation.

---

## Self-Check: PASSED

Files claimed created, verified on disk:
- `docs/adr/0014-cost-approximation-by-design.md` — FOUND
- `.planning/phases/22-limitations-recorded/22-01-SUMMARY.md` — FOUND

Files claimed modified, verified in the commits:
- `docs/adr/README.md`, `docs/OPERATIONS.md` — FOUND in `b10b8d1`
- `README.md`, `tests/test_evals.py` — FOUND in `1937c8a`

Commits claimed, verified in `git log`:
- `b10b8d1` — FOUND
- `1937c8a` — FOUND

Gates re-run at close: suite 828/72, evals 65/65 exit 0, ruff clean.
