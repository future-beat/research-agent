---
phase: 16-independent-critic-model
plan: 03
subsystem: docs
tags: [adr, supersession, stale-prose, readme-pass, record-integrity]

# Dependency graph
requires:
  - phase: 16-independent-critic-model
    plan: "01"
    provides: "graph.critic_model() and the four-site threading — the capability ADR-0010 records the rationale for"
  - phase: 16-independent-critic-model
    plan: "02"
    provides: "the record-mode collision line that names ADR-0010, and the model-aware-reservation rejection that 0010's consequences carry"
  - phase: 16-independent-critic-model
    plan: "research"
    provides: "Finding 4 (the judge re-derivation drafted) and Finding 6 (the grep-verified stale-prose inventory)"
provides:
  - "docs/adr/0010-judge-rederived-for-an-independent-critic.md — the four-leg re-derivation, the user's verbatim rationale, and the judge==critic acceptance"
  - "ADR-0005 superseded by status line only; the index's rows and its counting prose"
  - "README with the critic limitation DELETED and a residual that states the new reality"
  - "evals/graders.py and docs/DESIGN.md:74 no longer asserting the dead premise as current rationale"
  - "test_judge_critic_collision_warning_points_at_a_record_that_exists — the supersession's only permanent gate"
affects: [16-04, VALIDATION rows 8, 9, 10]

# Tech tracking
tech-stack:
  added: []  # nothing installed; this plan is prose plus one test
  patterns:
    - "A grep inventory finds the phrasings it was given. The dead premise also lived as '-- the same limitation the in-graph critic already has', which no grep in the plan, the research or the validation matrix could see. Read the neighbourhood of every site the grep DOES find."
    - "When an operator-facing message names a document, something must check the document exists. A pinned string is not a resolved link, and a dangling pointer in an operator message spends the reader's trust and then their time."
    - "A one-line-diff gate that lives in a plan's verify block stops running the moment the plan closes. If the invariant should hold forever, it needs a test — the same lesson 16-02 drew about the reservation prose."
    - "A whole-file pass means counting. Two `663 tests` claims in the README were falsified by this phase's own two prior waves, and neither is anywhere near the section the plan pointed at."

key-files:
  created:
    - docs/adr/0010-judge-rederived-for-an-independent-critic.md
  modified:
    - docs/adr/0005-opus-5-eval-judge.md
    - docs/adr/README.md
    - evals/graders.py
    - docs/DESIGN.md
    - README.md
    - tests/test_evals.py

key-decisions:
  - "The index reads 'Eight of the ten records are Accepted', not the plan's 'nine of ten'. With two supersessions (0006 and 0005) eight of ten remain Accepted; the plan's number contradicted its own next clause. The tree's arithmetic wins."
  - "The index's 'Reading a superseded record' paragraph was extended too. It was written as a reading guide for the only superseded record there was; with a second one it either teaches the convention for both or reads as a note about 0006. Not in the plan's stale-prose list, same class as the two that were."
  - "The README residual is a bullet titled by the limitation that now exists — 'The eval judge shares the critic's model' — rather than a softened version of the deleted one. The deleted bullet's subject was the critic's weakness; that is not a limitation any more, and the honest limitation left is the judge's narrowed independence."
  - "DESIGN.md's narrative kept the phrase, with the supersession appended as current fact. The ADR README says DESIGN stays as it is; the passage now reads as the argument as it stood, which is what a superseded-but-preserved narrative should read like. One line, one hunk."
  - "The test docstring above the :464 pin was corrected, the assertion was not. It ended '-- the same limitation the in-graph critic already has', which is the dead premise, sitting directly above the assertion that outlives it. The replacement is deliberately the same two lines so the assert stays at :464, which ADR-0010 and both prior summaries cite by number."
  - "No README content pins added. 16-02's rule — documented-not-enforced prose deserves a content pin — was weighed and declined here: limits.py's docstring is attached to a live function, while the README has no code coupling and no test in this repo reads it. The one place a runtime message points at a document DID get a gate."

# Metrics
duration: 35min
completed: 2026-08-10
---

# Phase 16 Plan 03: The record catches up with the reversal Summary

**One-liner:** ADR-0010 answers from scratch the question ADR-0005 could no longer answer — with an independent critic, what is the judge *for*? — on four legs, two of which are positions rather than deductions: the critic runs on a more capable model than the writer because Hesam said so, quoted verbatim, and the judge deliberately shares that model, which is recorded as an accepted narrowing of ADR-0005's independence claim rather than left for someone to notice later; the supersession is a one-line edit on 0005 with 0002 untouched, and every live document that still asserted the dead premise — the README bullet (deleted, not rewritten), `graders.py`'s docstring, `DESIGN.md:74`'s forward reference, and one test docstring the greps could not see — now says what is true.

## What was built

### Task 1 — ADR-0010 and the supersession mechanics (commit `3af3d42`)

**`docs/adr/0010-judge-rederived-for-an-independent-critic.md`**, `**Status:** Accepted — supersedes ADR-0005`, `**Source:** Phase 16 (2026-08-10), REQ-independent-critic-model` (not `Promoted from:` — it originates here, the 0006–0009 precedent).

The four legs, each written to survive being read alone:

**(a) The different job.** The critic gates *drafts* against *notes*, inline, once per draft, and its verdict feeds the revision loop. The judge grades *finished answers* against the *question and a rubric*, retrospectively, never on user traffic — and its verdicts are the refusal gate for recordings and, once recorded, the replayed assertions of every keyless CI run. The record states the consequence plainly: removing the shared-model premise removed a reason the judge had to be **stronger**, not a reason the judge **exists** — *"If the two had been doing the same job, the honest move after this phase would have been to delete the judge, not to re-justify it."*

**(b) The critic outranks the writer — the user's position, quoted.** Blockquoted verbatim, attributed by name and date, and explicitly marked as *his rationale, not an inference*: the research recommended shipping the capability with a neutral default and deferring the flip, and that recommendation was overruled. The record names the inversion: ADR-0005 justified a **strong judge by a weak critic**; this position wants the **gate itself stronger than the thing it gates**.

**(c) Independence, re-targeted and narrowed.** Hard requirement: judge ≠ the **writer's** model, pinned at `tests/test_evals.py:464`, which survives. Judge-vs-critic independence is recorded as **accepted as lost** — *"not an oversight, and not merely a configuration an operator could reach: it is the configuration being shipped, chosen with the consequence in view"* — with the honest statement of what a verdict is now worth: independent of the writer's model, **not** independent of the critic's family. Plus the honesty ADR-0005 also never claimed: Opus 5 and Sonnet 5 are the same vendor and family, so even judge ≠ writer buys family-level independence and no more.

**(d) "Stronger" demoted.** A defensible default for a discrimination task at eval-time-only cost — a **preference**, and an operator moving `EVAL_JUDGE_MODEL` is trading sharpness for money, not violating the record. *"Strength survives as a reason in exactly one place in this record — the critic, above."*

**Conclusion:** no judge flip; the flip is the critic's, via `fly.toml [env]`, in 16-04. **Carried forward from ADR-0005** (the ADR-0007 section shape): the structured-verdict half, plus `EVAL_JUDGE_MODEL` as the override and judging costing more per case.

**Consequences** carry the six accepted items (including ADR-0002 deliberately unedited, with the one-line residual — *independence is configuration, and production configures the critic above the writer*) and five rejected alternatives (deleting the judge; flipping the judge instead; forbidding the collision in code; the model-aware reservation rejected for the second time per 16-02; and shipping the capability without the flip).

**The mechanics, verbatim per the convention:** 0005's status line and nothing else; both index rows; and the counting prose.

### Task 2 — graders.py and DESIGN.md:74 (commit `99dee9a`)

`evals/graders.py`'s third docstring paragraph stated the dead premise as a fact about the running system. It now says the judge differs from the **writer** (`JUDGE_MODEL` against `graph.MODEL`) because a judge on the writer's own model inherits the blind spots it exists to find; that the critic has had its own model since Phase 16 (`CRITIC_MODEL`, unset means the writer's, production sets `claude-opus-5`); and that judge and critic therefore share a model in production — *"accepted rather than accidental, and recorded with the judge's re-derived rationale in ADR-0010."* Seven lines against the old four.

`docs/DESIGN.md:74`: one line, one hunk, closing sentence only.

### Task 3 — the README whole-file pass (commit `6d615ec`)

Six edits, five of them found by the pass rather than named by the plan. Full audit below.

### Beyond the plan — the supersession's only permanent gate (commit `4a5dd4f`) and the docstring the greps missed (commit `66f66d2`)

Both are deviations; see below.

## Gate discipline

### The pin-grep results the plan asked to be recorded

| Grep | Result |
|---|---|
| `grep -rn "graders" tests/test_evals.py \| grep -i "doc\|__doc__"` | **no matches** (exit 1) |
| `grep -rn "G.__doc__\|graders.__doc__\|inspect.getdoc" tests/ evals/` | **no matches** (exit 1) |
| `grep -rn "decent proofreader\|shares the writer" tests/ evals/` | **one match**, `evals/graders.py:14` — the line being rewritten |
| `grep -rn "__doc__" tests/` (widened, because the plan's grep would have missed a differently-worded pin) | four hits: `test_limits.py:721` (`reserved_run_usd.__doc__`), `test_evals.py:1452`/`:1471` (walk **callables'** docstrings for `"Cannot catch:"`, over `vars(G)`), `test_evals.py:1655` (`grade_fixture_current.__doc__`, 16-02's) |

**No test reads the graders module docstring.** The two nearby `__doc__` pins iterate grader *functions*, so a module-level edit is invisible to them — verified by reading `quality_graders_defined_in_the_module` at :1442 rather than by inferring from the names. Nothing needed updating alongside the prose.

### `--collect-only` against the whole `tests/` tree

Every selector, run as `pytest tests/ --collect-only -k <selector>` — the whole tree, because 16-02 found two of its own plan's selectors collecting zero.

| Selector | Collected | Note |
|---|---|---|
| `judge` (Task 1's verify) | **15 / 755** | non-vacuous |
| `collision_warning` | **5 / 756** | 4 from 16-02 + the one added here |
| `points_at_a_record` (the new test) | **1 / 756** | |

### Measured suite deltas

| Leg | Baseline entering (16-02) | After this plan | Delta |
|---|---|---|---|
| Plain (`.venv/bin/pytest`) | 690 passed / 65 skipped | **691 passed / 65 skipped** | +1 passed, **0 new skips** |
| Armed (`DATABASE_URL` → local PG :54329) | 754 passed / 1 skipped | **755 passed / 1 skipped** | +1 passed, **0 new skips** |
| Offline evals (`ANTHROPIC_API_KEY=""`, `env -u CRITIC_MODEL`) | 41/41 keyless | **41/41 keyless**, exit 0 | unchanged |
| `.venv/bin/ruff check .` | clean | clean | — |

All three baselines were **measured before any edit**, not taken from the prior summary: 690/65, 754/1, 41/41. Every leg run with `env | grep -c CRITIC_MODEL` → 0.

### The supersession gates

| Gate | Result |
|---|---|
| `ls docs/adr/00*.md \| wc -l` | **10** |
| `git diff main --numstat -- docs/adr/0005-opus-5-eval-judge.md` | **`1 1`** — exactly one line added, one removed, against **main** (post-commit the working-tree diff is empty and would pass vacuously) |
| `git diff main -- docs/adr/0002-separate-critic-node.md` | **empty** (0 lines) |
| `git diff main --numstat -- docs/DESIGN.md` | **`1 1`**, and `git diff main` shows **one** `@@` hunk |
| `tests/test_evals.py:464` | still `assert G.JUDGE_MODEL != graph.MODEL`, at line 464, green |

### Mutation probes on the one test this plan adds

Each mutates one file, runs `-k "collision_warning or fixture_critic_gate or claim_boundary"`, restores. `git status` clean after the run; probe artefacts in the scratchpad, not the repo.

| # | Mutation | Reds | Verdict |
|---|---|---|---|
| A | ADR-0010 renamed away | `points_at_a_record` **only** (1 failed, 11 passed) | **The gap, measured.** All four collision tests — which assert the string `"ADR-0010"` appears in the stderr line — stay **green** with the record gone. The operator message can point at nothing and nothing else in the tree notices. |
| B | 0005's status reverted to `**Status:** Accepted` | `points_at_a_record` **only** | **Exactly one.** The supersession is a two-file claim and this is the only thing holding both halves. |
| C | 0010's `supersedes ADR-0005` removed | `points_at_a_record` **only** | **Exactly one.** |

## The README whole-file pass

Read in full (263 lines). The grep audit ran **first**, per the standing instruction, and its output is recorded here rather than summarised:

```
$ grep -n "stronger model" README.md
32:- [x] **6 — Evals.** … plus an LLM judge on a stronger model. …
252:- **The critic shares the writer's model.** … precisely because of this.

$ grep -n -i "judge" README.md
32, 181 (the --live CLI comment), 213 (the recorder's refusal), 252
```

**The audit's finding:** the only load-bearing fact inside the deleted bullet — *the judge runs on a stronger model* — survives independently at **:32**, where the reason is not stated, so nothing had to be relocated. The bullet's other content (the critic is "not a genuinely independent evaluator", and the causal "precisely because of this") is what this phase reversed, not a fact to preserve. Re-verified against the tree, not taken from RESEARCH Finding 6.

| # | Location | Falsified by | Action |
|---|---|---|---|
| 1 | **:252 Limitations** | this plan | **DELETED.** Residual is one sentence: *"**The eval judge shares the critic's model.** Production runs the critic on Opus 5 — a more capable model than the Sonnet 5 writer it gates — and the judge on Opus 5 too, so a recorded verdict is independent of the writer's model and not of the critic's ([ADR-0010](...))."* States reality, not the old "configuration, not default" hypothetical. Placed in the deleted bullet's slot so the list's reading order is unchanged. |
| 2 | **:46 Status v1.1** | — | **Added**, `[x]`, matching 13–15's marking: *"**16 — Independent critic.** `CRITIC_MODEL` gives the critic its own model, priced per node at every place a model is named, and production pins it to Opus 5 — the gate now runs on a more capable model than the writer it checks. The eval judge's rationale is re-derived rather than inherited, including what the choice costs in independence (ADR-0010)."* Names **both** the capability and the flip. |
| 3 | **:15 and :179 — "663 tests"** | **waves 1 and 2 of this phase** (+15, +12) | **Fixed → 690** in both places. Found by the pass, named by nothing: neither is in Limitations, the ADR trail or the evals section. `~25s` → `~30s` (measured 26.8–29.5s across four runs today). |
| 4 | **:21 Stack line** | the cutover | *"Claude Sonnet 5"* → *"Claude Sonnet 5 (Opus 5 critic)"*. The line named one model where production now runs two, in the place a reader looks first. |
| 5 | **:238 Deployment config paragraph** | 16-02 (OPERATIONS gained `CRITIC_MODEL`) | **Added**, deliberately **after** the `/pricing` sentence rather than inside its list: `/pricing` does **not** surface the critic model — 16-02 deferred that with a 501-contract reason — so putting `CRITIC_MODEL` in the list would have widened a claim by placement. |
| 6 | **:32 Status, phase 6** | — | **Untouched.** "LLM judge on a stronger model" is factually true (Opus default vs Sonnet) and states no reason. This is the fact the deletion could have lost. |

**Checked and verified still true — no edit:**

- The **evals section** (192–215) does **not** describe the model-staleness gate at all (that description lives in `DESIGN.md:72`), so the plan's conditional clause about the gate now watching the critic was **not** owed and was not added. The caveat's "date, model, commit and age" is still accurate — the recorder did not change what it prints.
- "**One case of forty is recorded**" — still true; re-recording stays deferred.
- The `$0.14` figures in the REPL transcript (:75) and the SSE example (:115) are output from a real pre-flip run. Left alone deliberately: an Opus critic puts a typical run near $0.18, but that is an **estimate**, and pasting an estimated number into a transcript would be inventing a run that never happened. Flagged for 16-04, whose live verification produces a real measured figure.
- The remaining Limitations bullets (reported cost, identities, single-region database, bounded notes) and the whole Architecture/API sections — nothing this phase touches.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-16-07 | mitigate | **Closed.** `git diff main --numstat` on 0005 is `1 1`, measured against **main** rather than the working tree. And it is closed *permanently* rather than for the duration of the plan: probe B shows the new test reds when 0005's status line is reverted. |
| T-16-08 | mitigate | **Closed.** The grep audit ran before the deletion and its output is recorded above; the one surviving fact is at :32, pinned by the plan's acceptance grep (`judge on a stronger model`, present). |
| T-16-09 | mitigate | **Closed.** `git diff main -- docs/adr/0002-separate-critic-node.md` is empty. ADR-0010 carries 0002's residual in prose instead. |
| T-16-SC | accept | Re-verified: nothing installed. `pyproject.toml` untouched; no package-manager invocation in this plan. |

**New threat surface: none.** No endpoint, no auth path, no schema change. The only executable change is one test.

## Deviations from Plan

### Additions beyond the plan (Rule 2 — missing critical verification)

**1. [Rule 2] `test_judge_critic_collision_warning_points_at_a_record_that_exists` (commit `4a5dd4f`).** The carry-in instruction was to ask of every gate here whether a probe exists. One had none, and it is the gate that faces an operator: three tests from 16-02 pin the *string* `"ADR-0010"` inside a stderr line someone reads while deciding whether to trust a recording, and nothing checked the string resolves to a record. Probe A measures it — rename the file away and all four collision tests stay green. The test holds both halves of the two-file supersession claim (0010 exists and says it supersedes 0005; 0005's status line agrees), which also converts the plan's one-line-diff gate from a command inside a closing plan into something the suite runs. Directly the lesson 16-02 drew about the reservation prose, applied to the artefact this plan creates.

**2. [Rule 1] The test docstring above the `:464` pin (commit `66f66d2`).** It read *"...inherits the blind spots it exists to find -- the same limitation the in-graph critic already has."* That is the dead premise, stated as current fact, in the docstring of the test that pins the independence claim ADR-0010 re-targets. **No grep in the plan, the research or the validation matrix could see it** — the wording is not "shares the writer's model". The assertion is byte-identical and still at **:464**, and the replacement docstring is deliberately the same two lines so nothing below it moves; ADR-0010 and both prior summaries cite that line number. Flagged prominently because the plan says "do not touch" the pin: the pin is untouched, only the prose above it changed, and a reviewer who disagrees can revert one line.

**3. [Rule 2] The index's "Reading a superseded record" paragraph.** Not in the plan's list of prose that goes stale with a tenth record. It was written as a reading guide when 0006 was the only superseded record; with a second one it either teaches the convention for both or degrades into a note about 0006. Extended to name 0005 and point at ADR-0010's carry-forward section — same class as the two paragraphs the plan did list.

### Corrections to the plan's stated content

**4. [Rule 1] The index reads "Eight of the ten records", not the plan's "nine of ten".** The plan asked for *"'Eight of the nine records' → nine of ten"* while in the same breath asking for *"'One supersession has actually happened' → two"*. Both cannot hold: with 0006 and 0005 superseded, **eight** of ten remain `Accepted`. The plan's arithmetic was internally inconsistent and the tree's is what shipped. Same family as the plan-arithmetic corrections in 13-05, 14-02 and 15-03 — *a plan's stated numbers are a claim to check*.

**5. The residual bullet is titled for the limitation that now exists.** The plan allowed "a slim new bullet or attached where it fits". It is a bullet, and its bold lead is **"The eval judge shares the critic's model"** rather than a softened restatement of the deleted one, because the deleted bullet's subject — the critic's weakness — is not a limitation any more. The body is a single sentence, as instructed.

### Adjustments the plan left to discretion

**6. No README content pins added.** 16-02's rule ("documented-not-enforced prose deserves a content pin") was weighed and declined for the README: `limits.py`'s docstring is attached to a live function that a test already imports, while nothing in this repo's suite reads `README.md`, and building that would be new infrastructure rather than a probe. The one place where a *runtime message* points at a document did get a gate — deviation 1.

**7. `DESIGN.md`'s narrative keeps the dead phrase, with the supersession appended.** Explicitly permitted by SC ("DESIGN.md:74's narrative may retain the phrase with the supersession note appended as current fact"). The appended clause makes the paragraph read as the argument *as it stood*, which is how a preserved-but-superseded narrative should read.

### TDD Gate Compliance

**Not applicable and stated rather than skipped.** No task in this plan carries `tdd="true"`; the plan is prose with one test added under Rule 2, which was green on first run (the record it checks already existed). The substitute evidence is the three probes, each redding exactly that test and nothing else, plus the negative control in probe A: the four pre-existing collision tests stay green with the record deleted, which is the entire reason the test was written.

## README and stale prose

Full audit in the section above. **Repo-wide grep for the dead premise after this plan**, across live prose (`README.md docs/DESIGN.md evals/ src/ tests/`):

- `docs/DESIGN.md:74` — the narrative, with the supersession appended. **Permitted by SC.**
- `docs/adr/0002:45` and `docs/adr/0005:9` — **frozen records**, never edited by convention. 0005 now carries a `Superseded by` status line and 0002's residual is stated in ADR-0010.
- `src/research_agent.egg-info/PKG-INFO:252` — a **build artefact** carrying a stale copy of the README. Untracked and `.gitignore`d (`.gitignore:33`, `*.egg-info/`); it regenerates from `README.md` on the next editable install. Recorded so nobody greps it and thinks the deletion failed.
- `.planning/**` — planning history and codebase snapshots (`codebase/ARCHITECTURE.md:211`, `codebase/TESTING.md:384`, `intel/*`, `PROJECT.md:128` which already carries `⚠️ Revisit — premise falsified by REQ-independent-critic-model`). Records of what was known when, not current claims, and out of this plan's scope.

**No live document states the dead premise as current fact.**

## Requirements

`REQ-independent-critic-model` stays **Pending**, consistent with waves 1 and 2. This plan closes **SC-4** (ADR-0010, superseding ADR-0005, with the mechanics exact) and **SC-5** (the README sentence and its bullet). All five success criteria are now closed *in the repo* — and the production cutover that makes any of them observable is 16-04's, and per the USER DECISION the flip **is** this phase's deliverable. Checking the box before `CRITIC_MODEL` is set on Fly would assert that the critic runs on an independent model when the deployed service still runs it on the writer's.

`roadmap.update-plan-progress 16` was run and, as expected for the third time, **blanked the notes cell**; the prior value (waves 1 and 2) was restored by hand and the wave-3 paragraph appended. The tool's full effect was reviewed: two lines, the checklist tick and the progress row, nothing else.

## Known Stubs

None. One piece of not-yet-observable behaviour, stated rather than hidden:

- **ADR-0010 describes a production configuration that does not exist yet.** `fly.toml` has no `CRITIC_MODEL` entry until 16-04. The record says "production pins" in the present tense throughout because it is the record of the decision and the cutover is the same phase's next wave — but between this commit and 16-04's deploy, the deployed critic still runs on the writer's model. If 16-04 does not land, ADR-0010's tense is the thing to fix.

## Deferred Issues

- **The `$0.14` figures in the README's REPL transcript and SSE example** are pre-flip measurements. 16-04's live verification run produces a real post-flip number; replacing them is a one-line edit *then*, and inventing one now would be worse than leaving them.
- **`.planning/codebase/ARCHITECTURE.md:211` and `TESTING.md:384`** still describe the shared critic model. They are codebase snapshots from ingest, not current claims, and rewriting mapping artefacts is a separate concern from the doc-correctness sweep this plan owns.
- Carried, unchanged: `evals/__main__.py`'s preview still under-quotes against the deployed critic (16-02), and the `/pricing` critic block stays deferred.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `3af3d42` | docs | ADR-0010 + the supersession mechanics on 0005 and the index |
| `99dee9a` | docs | graders.py's docstring and DESIGN.md:74's forward reference |
| `6d615ec` | docs | README whole-file pass: limitation deleted, residual, status entry, two falsified counts |
| `4a5dd4f` | test | The ADR that record mode points an operator at has to exist |
| `66f66d2` | docs | The last sentence in the tree that stated the dead premise as fact |

## Self-Check: PASSED

- `docs/adr/0010-judge-rederived-for-an-independent-critic.md` — FOUND (created; `supersedes ADR-0005` ×1, `more capable than the writer` ×2, `Carried forward from ADR-0005` ×1)
- `docs/adr/0005-opus-5-eval-judge.md` — FOUND (modified; `1 1` numstat against main)
- `docs/adr/README.md` — FOUND (modified; 0010 row present, 0005 row reads Superseded, counting prose updated)
- `evals/graders.py` — FOUND (modified; `decent proofreader` ×0, `shares the writer's model` ×0, `ADR-0010` ×1)
- `docs/DESIGN.md` — FOUND (modified; `0010-judge` ×1, one hunk)
- `README.md` — FOUND (modified; `precisely because of this` ×0, `The critic shares the writer's model` ×0, `judge on a stronger model` ×1, `CRITIC_MODEL` ×1, `16 — ` ×1)
- `tests/test_evals.py` — FOUND (modified; `points_at_a_record` ×1, `assert G.JUDGE_MODEL != graph.MODEL` still at :464)
- `.planning/phases/16-independent-critic-model/16-03-SUMMARY.md` — FOUND (created)
- Commits `3af3d42`, `99dee9a`, `6d615ec`, `4a5dd4f`, `66f66d2` — all resolve in `git log`
- `docs/adr/0002-separate-critic-node.md` — zero diff against main
