# Phase 18 — deferred items

Discovered during execution, deliberately not fixed in the plan that found them.

## The record console does not print the refusal's reason (found in 18-02)

**Measured, 18-02 Task 3.** In record mode `evals/__main__.py` wires
`announce_recording` (prints `outcome.refusal` — the `FixtureError`, which names
the failed graders) and never calls `announce` (the function that prints
`grade.detail`). So when a judge declines, the operator's console reads:

```
  SKIP  technical-figures  $0.0520
        refusing to record 'technical-figures': judge_grounding,
        judge_answers_the_question failed. A committed fixture is one the
        graders and the judge approved; pass force=True to record it anyway.
```

The word DECLINED — and with it the fact that **nothing was graded at all** —
travels only in the `--report` JSON (`cases[].turns[].grades[].detail`).

**Why it reads wrong:** "judge_grounding failed" invites the reading "the report
is ungrounded", which is exactly the conclusion a refusal does *not* support. An
operator could re-run or `--force` a case whose answer was never assessed.

**Why 18-02 did not fix it:** the fix is in `evals/__main__.py`, and 18-02's
success criterion is *zero changes* to `evals/__main__.py` and `evals/fixtures.py`
— the refusal composes with the existing paths rather than growing a second one.
Changing an operator-facing announcement is also a deliberate act in this project
(the 16-02 lesson), not a side effect of a guard.

**Pinned, not just noted:** `test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines`
asserts the console names the grader, never says "the run errored", and does NOT
contain DECLINED — so if this is later fixed, the test reds and the change is
made on purpose.

**Candidate owner:** Phase 21's record run (the next time a real judge is asked
anything) or a follow-up to 18-04, which already owns operator-facing wording in
this phase.

## Stale test counts in prose (found in 18-03)

**Measured, 18-03 Task 2's whole-file pass.** Greping the tree for spelled-out and
digit counts to re-derive the ADR arithmetic turned up two test counts that are
stale, neither of them falsified by this plan:

| Site | Says | Measured 2026-08-13 |
|------|------|---------------------|
| `.planning/PROJECT.md:31` | 737 keyless / 801 with Postgres | **748** keyless (67 skipped) |
| `README.md:15` and `README.md:199` | 740 (both sites) | **748** |

`PROJECT.md`'s number was already stale entering Phase 18 (the measured baseline
at phase start was 740), so it is not this wave's to correct alone, and the same
count in `README.md` is explicitly **18-04's** deliverable per `18-VALIDATION.md`
row 7 ("README test count measured and corrected"). Fixing one of the two here
would leave the pair disagreeing.

**What 18-03 did fix**, because its own commit falsified them: the ADR counts in
`README.md:40` (eleven/three → twelve/four) and `.planning/PROJECT.md` § Current
State and § Key Decisions.

**Candidate owner:** 18-04, in the same pass that corrects the README count —
both numbers come from one `pytest` run.

**The house lesson this is the seventh instance of:** a whole-file pass means
counting, and a plan's stated arithmetic is a claim to check. Here the plan's
arithmetic (twelve records, eight Accepted, four supersessions) was **correct** —
verified cell by cell against the index table before it was typed — which is the
first time in this family it has been. The drift was elsewhere in the same files.
