---
phase: 9
slug: demo-and-guardrails
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 9 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-02).
> Criteria reconstructed at remaster; measurements against the 2026-08-12 tree
> (737 passed / 65 skipped keyless).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| The rolling daily cap refuses runs past the day's budget | `tests/test_limits.py` | **57 collected** (now covering the Phase 12 reservation semantics that superseded the original arithmetic) |
| The rate limit bounds per-visitor request volume | `test_limits.py` + service tests | Covered; keys on identity rather than IP since Phase 12 |
| `DEMO_TOKEN` set gates the research routes; unset leaves the demo open | `test_limits.py` credential cases | Covered, including Phase 10.5's fail-closed `SESSIONS_TOKEN` and the `DEMO_TOKEN` fallback |
| Deploy config matches the declared topology | `tests/test_deploy_config.py` | **13 collected** |
| A stranger reaches a working demo with zero setup | live check | Standing criterion, re-verified at every v1.1 cutover (last: Fly v12, 2026-08-11) |

## What execution-time verification actually was

291 same-commit test lines on the guardrails, plus live use of the deployed page.
The guardrails were the most consequential thing v1.0 shipped untested-in-anger:
they held, but v1.1 later *measured* two real weaknesses — the cap's concurrency
overshoot (~3×, closed by Phase 12's reservations) and the reservation constant
itself (an estimate; resized on two live runs at the audit).

## Honest gaps

- The guardrails bounded spend but identified nobody, and the session surface behind
  the demo was open (Phase 4's omission, still unclosed here — v1.0 shipped with it).
  Both were named limitations; both closed in v1.1 (10.5, 12).
- `TRUST_FORWARDED_FOR` was load-bearing for fairness — a header-shaped trust
  decision. Phase 12 removed that load (identity keys the limits), which is the
  stronger fix than hardening the header parse would have been.
- No CSP header on the demo page — noted in Phase 12's deferred items and still open
  at the v1.1 close; carried on the project's open-items list.
