---
phase: 5
slug: cost-and-observability
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 5 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-01).
> Criteria reconstructed at remaster; measurements against the 2026-08-12 tree
> (737 passed / 65 skipped keyless).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| Prices resolve by run date; both Sonnet 5 windows pinned with fixed dates, never `today()` | `tests/test_usage.py` | **43 collected**; Phase 14's contract additionally measured `grep -c "date.today()\|datetime.now()"` = **0** in the file |
| An unpriced model fails loud (`pricing_unknown`), never zero | `test_usage.py` + Phase 14's Probe C record | Pinned; the probe (unknown-geo `raise` → `return 1.0`) was observed RED in 14-VALIDATION |
| Cache rates are asserted as documented ratios (1.25× / 0.1× of base input), not typed-in numbers | `test_usage.py` | Pinned |
| The budget row ENDs a run over cost with `budget_exceeded`; overshoot bounded to one node | `tests/test_supervisor_routing.py` budget rows | Covered; precedence of the cap rows over the follow-up rows re-pinned in Phase 17 |
| Failed runs count in denominators; zero-denominator rates are `null`; both metrics backends agree byte-identically | `tests/test_metrics.py` (+ contract suite since Phase 8) | **21 collected**; the byte-identical assertion is DEC-16's, guarded since Phase 8 |

## What execution-time verification actually was

The suite, same-commit (940 test lines). The `Decimal` war story is this phase's
sibling: Postgres returns `SUM(BIGINT)` as `Decimal`, which isn't JSON-serialisable
and would have 500'd `/metrics` on the first recorded run — caught in Phase 8 by the
byte-identical cross-backend assertion, i.e. by a test this phase's design made
possible.

## Honest gaps

- v1.0's cost figure was list price only — "the shape of the bill." That was a stated
  limitation, not a bug; Phase 14 closed it and the README now calls the figure an
  approximation with the telemetry caveat measured live (Voyage reported 25 tokens
  where the tokenizer counted 40).
- Embedding spend was accounted **nowhere** in v1.0 — a whole provider missing from
  the bill, known since the Phase 10 codebase mapping, closed in Phase 14
  (`embedding_usd` non-zero in production, Fly v10).
