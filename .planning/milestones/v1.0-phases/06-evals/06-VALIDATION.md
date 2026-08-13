---
phase: 6
slug: evals
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 6 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-01).
> Criteria reconstructed at remaster; measurements against the 2026-08-12 tree
> (737 passed / 65 skipped keyless; offline evals 41/41 on every push).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| Offline evals run the real compiled graph, keyless, deterministic, on every push | CI (`ANTHROPIC_API_KEY=""` invariant) + `python -m evals` | 41 cases, exit 0, keyless — a CI gate since Phase 7 |
| The invariant: an unapproved draft is never returned as if approved | eval graders + harness tests | Pinned; Phase 17 extended it to the insufficiency window ("ships no answer" asserted structurally) |
| The judge returns a structured verdict; a mis-parse crashes rather than mis-reports | `evals/graders.py` + `tests/test_evals.py` | **171 collected** in the test file |
| The caveat printed matches what the suite can claim | pinned by test since Phase 15 | The caveat now prints the recording's date, model, commit, and age — DEC-20's honesty rule, made more specific |
| The revision cap is reachable; the backstop derives from it | pinned test (DEC-21) | Present since this phase's fix |

## What execution-time verification actually was

The harness verified the pipeline — and, on its first run, the pipeline's guardrail
composition failed it (the unreachable revision cap). That catch is the phase's own
validation: the tool demonstrably found what unit tests structurally could not. The
harness itself was tested by `test_evals.py` from the same commit.

## Honest gaps

- Twelve cases was a smoke test, not a benchmark, and the v1.0 README said so as a
  limitation. Phase 15 grew the set to 40 across a taxonomy with dataset property
  pins, and added recorded-answer replay.
- The offline leg's inability to grade answer *quality* was stated but unmeasured —
  there was no mechanism at all until Phase 15's recorded fixtures (1 of 40 recorded;
  the rest an explicit, priced deferral).
- v1.1 later found the *gate* could be decorative: a red replay absorbed by the pass
  rate (15-03), graders passing unit tests while never wired into the registry
  (17-01). None of those failure modes was probed in v1.0.
