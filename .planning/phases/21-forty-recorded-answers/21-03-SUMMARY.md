# Phase 21 — Wave 3 Summary (closure)

> **RECONSTRUCTED 2026-08-17 from committed evidence, not written at execution time.**
> Same cause as `21-02-SUMMARY.md`: wave 3 was executed inline by the orchestrator
> immediately after the paid stages, and its record was never written. Every claim below
> is re-derived from commit `5c38735`, from `evals/REFUSALS.json`, and from the gates in
> `tests/test_evals.py` as they stand — not from memory.

**Executed:** 2026-08-15 · **Plan:** 21-03

---

## What landed

**The completeness gate the research found missing.** Before this phase, *nothing* in the
tree asserted that the committed fixture set matched `dataset.GOLDEN` — the replay leg
graded whatever files happened to exist. Two gates now hold it:

- `test_every_golden_case_is_recorded_or_documented_as_refused` — the union of
  `evals/fixtures/` and `evals/REFUSALS.json` must be **total** over the 40 golden cases,
  with three separate arms: nothing unaccounted, nothing in **both** sets, no refusal
  naming a case that does not exist.
- `test_documented_refusals_say_why_and_distinguish_defect_from_judgement` — every refusal
  carries a `kind` and a non-empty `detail`, and `judge_truncated` is asserted present and
  kept distinct from `grader`, so an operational failure of the judge harness can never
  read as the machinery working.

**Three mutations, each observed red before the gates were trusted:** a dropped refusal
(case in neither set) → `unaccounted` reds naming it; a stale refusal left behind for a
case that was later recorded (case in **both**) → `overlap` reds; the truncation defect
reclassified as an ordinary grader refusal → the kind assertion reds. All restored, all
re-run green.

**The overlap arm is the load-bearing one** and its purpose is easy to miss: it is what
forces a successful re-record to *remove* the refusal entry in the same commit. Without
it, the refusal list would rot into fiction while still summing to forty. Phase 21.5's
re-record depended on exactly that property.

## The honest closure

Six fixtures recorded successfully at record time and then **failed replay**, which is its
own finding about the two grading paths disagreeing: `grade_case_pins` runs only on the
replay path.

- **Five contested cases.** Their `must_mention` pins demand `proponents`/`critics`;
  the new recordings argue both sides at length in other words. Re-authoring the pins was
  **tried and reverted** — the same pins must also satisfy each case's hand-authored
  reference report in `dataset.py`, which *is* written in that vocabulary, so every
  replacement collapsed to a weaker word than the one it replaced.
  `test_dataset_taxonomy_authored_reports_satisfy_their_own_pins` caught the attempt.
  **`dataset.py` ended the phase unmodified.**
- **One hedged half-answer.** `followup-refuses-a-forecast` admits no source covers the
  forecast and then supplies "a reasoned estimate built from adjacent proxy data" anyway —
  precisely what `grade_recorded_refusal`'s docstring names as the thing it cannot catch.
  Widening `REFUSAL_PATTERNS` would have taught the suite to accept the failure the
  pipeline exists to prevent, so the fixture was **not kept**. That record-time grading and
  the judge both approved it is itself the finding.

All six are documented in `REFUSALS.json` under `recorded_then_failed_replay` with their
reasons, rather than quietly dropped.

## A section this reconstruction wrongly claimed

> **Correction, 2026-08-17.** This file originally credited Phase 21 with finding and
> fixing `test_cli_writes_the_report`'s stale `len(cases) == 1` literal. **That is Phase
> 21.5's work** (`60c93e9`). When Phase 21 closed, `general-summary` was still *refused*,
> so the literal was still true and nothing had gone stale. `git log -S` on both the old
> and the new assertion returns only 21.5's commit. Removed rather than reworded — a
> reconstruction that annexes a later phase's finding is worse than one that omits it.

## Gates at close

**59/59 offline evals, real exit 0** — denominator grown honestly from 41 to 59
(40 behavioural + 19 replayed). **806 passed / 72 skipped** keyless. `ruff check .` clean.
README and OPERATIONS re-derived by measurement, and README's Limitations section left
byte-untouched for Phase 22.

Final split at this phase's close: **19 recorded / 21 documented refusals = 40**, overlap
empty. (Phase 21.5 later moved it to 25/15 by re-recording six under the fixed classifier.)
