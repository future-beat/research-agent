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

**Resolved by 18-04:** `README.md:15` and `:199` corrected 740 → **749** from a
measured run. `.planning/PROJECT.md:31` handled in the same pass — see below for
why its second number could not be measured.

## The codebase maps still describe the pre-Phase-16 judge (found in 18-04)

**Measured, 18-04 Task 2's broad sweep.** Three `.planning/codebase/` artifacts
assert the judge's model as current fact, and all three are stale:

| Site | Says | Measured 2026-08-14 |
|------|------|---------------------|
| `.planning/codebase/STACK.md:98` | "**Eval judge:** `claude-opus-5` … **This is the only place Opus appears**" | judge is `claude-opus-4-8`; Opus also appears as the production critic |
| `.planning/codebase/INTEGRATIONS.md:131` | "`EVAL_JUDGE_MODEL` (default `claude-opus-5`)" | default is `claude-opus-4-8` |
| `.planning/codebase/TESTING.md:382` | `JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")` | the literal is `"claude-opus-4-8"` |

**Why not fixed here:** these are `/gsd-map-codebase` output — a dated snapshot of
the tree, regenerated wholesale rather than hand-patched, and they are `.planning/`
state rather than a shipped doc surface. 18-04's scope is the four surfaces the
plan names (`evals/graders.py`, `docs/OPERATIONS.md`, `docs/DESIGN.md`,
`README.md`). Hand-editing three lines of a generated artifact would leave the
rest of the snapshot equally stale and disguise that it needs regenerating.

**Note that STACK.md:98 was ALREADY stale entering this phase** — "the only place
Opus appears" stopped being true in Phase 16, when production pinned the critic to
`claude-opus-5`. So this is not drift Phase 18 created; it is drift Phase 18's
sweep surfaced.

**Candidate owner:** a `/gsd-map-codebase` re-run, or Phase 22's doc pass.

## `.planning/PROJECT.md`'s with-Postgres count could not be measured (18-04)

`PROJECT.md:31` read "737 tests pass with no API keys; 801 with Postgres armed."
The keyless half is measured and corrected to **749**. The with-Postgres half was
**not measurable in this session**: no Docker daemon and no running Postgres, and
standing up a server to produce one number is outside a doc-correction plan's
remit. What IS measured: all **67** skips are Postgres-gated (66 `DATABASE_URL is
not set`, 1 `REQUIRE_POSTGRES is not set`), so 816 tests are collected keyless.

Rather than infer `801 + 12 = 813` — the exact plan-stated-arithmetic move this
project keeps catching — the sentence was rewritten to state the measured facts
and stop quoting a second number nobody has run recently.

**Candidate owner:** whoever next runs the suite with `DATABASE_URL` set (CI does
this on every push; the number is in the CI log).
