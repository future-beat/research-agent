---
phase: 5
slug: cost-and-observability
milestone: v1.0
status: complete
executed: 2026-08-01
remastered: 2026-08-12
---

# Phase 5: Cost & observability — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** Every run reports what it cost, and a spend cap stops runaway runs.

**Shipped in:** `b42c9c9` (2026-08-01) — `usage.py` (203 lines), `metrics.py` (247),
`observability.py` (120), and 940 new test lines across five files.

## What shipped

- **The spend cap as a routing rule, not a wrapper** (DEC-11). Every node folds usage
  into `state["usage"]` before returning, so the supervisor reads running cost on its
  next hop — budget is one more row in the same routing table, with the same
  `forced_stop_reason` machinery as the iteration and revision caps. Consequence stated
  at the time: cost is only knowable after a call returns, so a run can overshoot by at
  most one node, never unboundedly.
- **Effective-dated prices; unknown models fail loud** (DEC-12). `price_for()` resolves
  a rate for a date — Sonnet 5's introductory $2/$10 window through 2026-08-31 and the
  $3/$15 rate from 2026-09-01 are both in the table, pinned by tests with fixed run
  dates. A model with no row still has tokens counted, but `cost_usd` becomes a floor
  and `pricing_unknown` goes true: costing unknown calls at zero "would quietly disable
  the budget guardrail — a cost control that fails open without saying so is worse than
  none."
- **Honest denominators** (DEC-13). Failed runs stay in the `/metrics` denominator — a
  failed run opened no session but still burned tokens and still happened. Rates with a
  zero denominator return `null`, not `0.0`: "no runs yet" and "nothing was approved"
  are different facts. Latency percentiles cover completed runs only, because mixing in
  time-to-failure "makes an outage look like a speed-up."
- **Structured JSON logs** (`observability.py`) and the `/metrics` endpoint.

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| DEC-11 cap as routing rule | Never reversed; Phase 12 added *reservation* against in-flight runs (the cap survives concurrency), Phase 17 bounded the follow-up research pass with the same machinery |
| DEC-12 effective-dated prices, fail-loud | Never reversed; Phase 14 extended it — discount and response-observed `inference_geo` multipliers at one choke point, Voyage priced for the first time. "Approximates the invoice" replaced "shape of the bill" |
| DEC-13 honest denominators | Never reversed; the v1.1 audit's W1 fix (a persisted-write failure could lose a completed run from the ledger) is this decision defended at a seam nobody had looked at |

## Where it lives today

`src/research_agent/usage.py`, `metrics.py`, `observability.py`. Tests measured
2026-08-12: `test_usage.py` **43**, `test_metrics.py` **21**, `test_observability.py`
**13** collected. `/pricing` (Phase 14) is the live rate source; planning documents no
longer quote a rate as if permanent.
