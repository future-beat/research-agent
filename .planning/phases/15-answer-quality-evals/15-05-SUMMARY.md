# 15-05 — The record CLI and its cost preview

**Status:** Complete
**Plan:** `15-05-PLAN.md` · Wave 5
**Completed:** 2026-08-10

> **Provenance note.** The executing agent was cut off by an API error immediately after its
> README commit, before writing this SUMMARY. All three task commits and the README commit
> had landed. This file was reconstructed by the orchestrator from the commits and from
> re-running every gate — it records what was **verified**, not what was claimed. Anything the
> executor knew and did not commit is lost; where this file cannot vouch for something, it
> says so.

## Commits

| Hash | Type | What |
|------|------|------|
| `3fff6a4` | feat | What a recording will cost, quoted from the rate table at runtime |
| `1cd88ce` | feat | A record command that prices itself, refuses itself, and refuses a red recording |
| `7f5cb62` | docs | README: the suite is 662 tests, and there is now a command that spends money |

## Verified by the orchestrator after the interruption

| Gate | Result |
|------|--------|
| Suite, plain | **662 passed / 65 skipped** (from 645/65 — +17, zero new skips) |
| Suite, armed (:54329) | **726 passed / 1 skipped** (from 709/1 — +17, identical delta) |
| Offline evals, keyless | **40/40 at pass-rate 1.0**, exit 0, caveat printed |
| `ruff check .` | clean |

The +17 moved identically in both arms, so none of the new tests needs Postgres or a key —
consistent with the plan's fake-driven requirement.

## The preview, run for real

```
  total          $12.7845
  basis          0 measured, 40 assumed — assumed tokens dominate this quote
  estimate — treat as an upper bound; run a one-case calibration first
```

Three things this demonstrates, each checked rather than assumed:

- **Priced at runtime, not hardcoded.** `grep -nE '\$1[0-9]|\$[0-9]+\.[0-9]{2}' evals/__main__.py`
  returns one hit and it is a *comment* explaining the estimate's origin, not a constant in the
  code path. The figure moves when `usage.py`'s tables move — including across the
  2026-09-01 Sonnet boundary.
- **The basis is stated, not implied.** "0 measured, 40 assumed" tells the operator the quote
  rests entirely on assumption today. After wave 6's calibration it should read "1 measured,
  39 assumed" and the number should shift.
- **`--record` without `--yes` stops at the quote.** It prints and does not spend.

## What this wave did NOT prove

- **No recording has been made.** `evals/fixtures/` is still empty; the replay leg has nothing
  to grade, which is why offline evals still report 40/40 behavioural-only. Wave 6's
  calibration is the first real execution of the record path end to end.
- **The $12.78 quote is an upper bound built from assumptions**, not a measurement. Wave 6
  exists partly to replace one of those 40 assumptions with a measured case and see how far
  the quote moves.
- **Mutation evidence for this wave is not recorded.** The executor's mutation table, if it ran
  one, was lost with the interruption. This file will not claim mutations that cannot be shown.
  The gates themselves were re-run and are green; that is a weaker claim than "observed red
  under mutation", and it is the honest one.

## Carry-forward

- Wave 6 owns: ADR-0009, the README claim rewrite ("offline evals can't measure answer
  quality" is still there and still untouched), the calibration recording (~$0.25), and the
  record-now-vs-defer decision on the full run.
- The quote to beat: **$12.78** at intro pricing. After 2026-09-01 the same run reprices ~50%
  higher, which is the only time-sensitive argument for recording now rather than later.

---
*Phase: 15-answer-quality-evals*
*Reconstructed: 2026-08-10*
