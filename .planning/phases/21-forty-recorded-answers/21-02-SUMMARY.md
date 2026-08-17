# Phase 21 — Wave 2 Summary (the paid stages)

> **RECONSTRUCTED 2026-08-17 from committed evidence, not written at execution time.**
> Wave 2's two plans were executed inline by the orchestrator rather than by an executor
> subagent, because both stages sit behind blocking spend checkpoints that only the
> orchestrator can obtain from the user — and the summaries were never written afterwards.
> The ROADMAP ticked both plans `[x]` while these files did not exist, so for a day the
> record was ahead of the evidence. Every number below is re-derived from the five report
> JSONs in this directory and from the commits named, never from memory. The v1.0 remaster
> set the precedent for reconstructing a record and labelling it as reconstructed.

**Executed:** 2026-08-15 · **Plan:** 21-02 · **Both checkpoints user-approved**

---

## Checkpoint 1 — calibration

Approved at a fresh keyless quote of **$0.3577** for one case, after the P-06 assertions
(`CRITIC_MODEL`, `EVAL_JUDGE_MODEL`, `VECTOR_STORE`, `DATABASE_URL` all unset) passed.

`technical-figures` re-recorded: **$0.2496 measured pipeline, 2 judge calls**
(`stage1-report.json`). It was the mandatory first pick — its committed fixture carried
`models.judge: claude-opus-5`, the judge ADR-0012 superseded, so it was stale before the
run began and re-recording it retired that staleness.

**The correction that mattered.** The metered $0.2496 against a $0.3577 quote reads as 30%
under, and reporting it that way would have been wrong: the recorder states that judge
calls "bill separately and are not metered here". Adding the quote's own assumed judge
share puts the true figure at roughly **$0.365 against $0.3577 — on target, possibly a
hair over**. The flattering number was an artefact of reading one field.

**The staging assumption also failed, and was reported rather than smoothed.** The plan
expected calibration to re-base the remaining quote; it did not. The re-quote still read
`0 measured, 39 assumed`, because a case's measured basis comes only from its own fixture.
That is why checkpoint 2 was presented as an unvalidated upper bound.

---

## Checkpoint 2 — the bulk, four batches

Approved for **batch A only** first, deliberately: the calibration could not validate the
assumed-token model for never-recorded cases, so batch A bought that basis. Batches B–D
followed under the ratified "record what passes" decision.

| batch | quoted | actual (metered pipeline) | recorded | refused | judge calls |
|---|---|---|---|---|---|
| calibration | $0.3577 | **$0.2496** | 1 | 0 | 2 |
| A (10) | $3.8900 | **$1.9011** | 7 | 3 | 17 |
| B (11) | $4.2790 | **$2.1556** | 9 | 2 | 22 |
| C (10) | $3.8900 | **$2.2025** | 4 | 6 | 20 |
| D (8, follow-ups) | $5.0645 | **$3.3932** | 4 | 4 | 24 |
| **total** | **$17.4812** | **$9.9019 — 56.6%** | **25** | **15** | **85** |

Metered pipeline only; the 85 judge calls bill separately and the recorder does not meter
them, which is stated rather than folded into a better-looking total.

---

## The criterion amendment, user-ratified mid-run

Batch A refused 3 of 10 and made the requirement's two halves visibly incompatible on the
real pipeline: *all forty recorded* versus *only grader-and-judge-approved fixtures get
committed*. The ratified resolution — recorded in full in `21-VALIDATION.md` — is that
**every case is either recorded or carries a documented refusal**, with `--force` refused
outright, because buying the number forty by stamping fixtures `forced` would discard the
property that makes a fixture worth grading.

## The findings the run bought

**One systematic cause, not eleven scattered ones.** Of the refusals, six were the
identical mismatch — `topic_type expected 'general', got 'technical'` — hitting every
`general-*` case. The keyless suite is structurally blind to this: it stubs the classifier,
so drift between the shipped pipeline and what the golden cases assert cannot surface
until something pays to run it. This finding became Phase 21.5, which fixed it.

**A judge-harness defect, distinct in kind.** Two cases died on
`ValueError: Judge verdict was TRUNCATED at max_tokens` — the 1500-token budget shared with
adaptive thinking, exactly as `evals/graders.py`'s own comment predicted. Recorded under a
separate `kind` so it never reads as a quality refusal.

**Three grader-quality refusals** (`max_revisions_exceeded`) and **two `judge_grounding`
catches** of genuine overstatement complete the set.

## Discipline held

`--case`-explicit invocation throughout; the P-06 env assertions in front of every `--yes`;
no auto-retry of any refusal; report JSONs archived to this directory as they were produced.
Commits: `6bdd4c4` (calibration + batch A), `47dd8d3` (batches B and C), `5c38735` (batch D,
the union gates, and the refusal record).
