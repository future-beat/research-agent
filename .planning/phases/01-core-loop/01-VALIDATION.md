---
phase: 1
slug: core-loop
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 1 — Validation (retroactive)

> **Remastered record.** No validation contract existed when this phase executed
> (2026-07-29) — the phase shipped with no tests at all; the suite arrived in Phase 3.
> The criteria below are reconstructed, and every measurement is against the
> 2026-08-12 tree (737 passed / 65 skipped keyless, measured this date). No mutation
> probe is claimed for execution time; the v1.1 phases (12, 15, 16, 17) probed this
> routing table extensively and their VALIDATION files carry those records.

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| Routing is a deterministic function of state — no model call decides the next hop | `tests/test_supervisor_routing.py` | **60 collected**; the file drives `supervisor_node` directly with no API client constructed |
| The full loop runs keylessly end to end (classifier → researcher → writer → critic) | `tests/test_graph_smoke.py` | **43 collected**, scripted client, no keys |
| Caps fire and report honestly (`forced_stop_reason`, never a silent unapproved draft) | routing tests + eval graders (`evals/graders.py` forced-stop family) | Covered in both suites; the eval invariant "an unapproved draft is never returned as if approved" runs on every push |
| The revision cap is *reachable* (`MAX_ITERATIONS` derived from `MAX_REVISIONS`) | pinned by test per DEC-21 | This criterion was **false as shipped** — see below |

## What execution-time verification actually was

Manual REPL runs. The phase shipped zero tests; `pytest` enters in Phase 3 and the
routing table's first 267 test lines land there. That gap had a real cost, found in
Phase 6: with `MAX_ITERATIONS=8` / `MAX_REVISIONS=2` the revision cap was unreachable
in research mode — the backstop always fired first and reported
`max_iterations_exceeded` (reads like an internal fault) instead of
`max_revisions_exceeded` (the truth). Each cap was correct in isolation; the evals
caught the composition (DEC-21). The fix derives the backstop from the cap (`2` → `12`)
and a test pins the relationship.

## Honest gaps

- Nothing here was tested at execution time; the criteria above are enforced by tests
  written in Phases 3–6 and hardened through v1.1.
- The routing table validated here had seven rows; today's has ten (spend cap row from
  Phase 5, two follow-up research rows from Phase 17). The measurements above are of
  today's table, which subsumes — not reproduces — the Phase 1 shape.
