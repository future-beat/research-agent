---
phase: 6
slug: evals
milestone: v1.0
status: complete
executed: 2026-08-01
remastered: 2026-08-12
---

# Phase 6: Evals — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** The pipeline's behaviour is checkable against a golden set.

**Shipped in:** `b118e57` (2026-08-01) — the `evals/` package (`dataset.py` 279 lines,
`graders.py` 323, `harness.py` 367, `__main__.py` 148) and `test_evals.py` (486 lines).

## What shipped

- **A twelve-case golden set with an offline/live split** (DEC-20). Offline runs drive
  the real compiled graph with a scripted client whose output is authored in the
  dataset — free, deterministic, safe on every push. It checks routing, both guardrails,
  follow-up isolation, and the invariant that an unapproved draft is never returned as
  if approved. It *cannot* speak to answer quality, and the CLI printed that caveat
  under every offline run: "a green suite that quietly implies 'the model is good' is
  worse than no suite."
- **Deterministic graders plus an LLM judge on a stronger model** (DEC-22). The judge
  runs on Opus 5 against a Sonnet 5 pipeline and returns a structured verdict, not a
  text convention — a harness that mis-parses a text verdict "reports a confident wrong
  number, which is worse than crashing." The rationale, as recorded then: the in-graph
  critic shares the writer's model, so a judge on that same model "would inherit exactly
  the blind spots it exists to find."
- **It found a real bug on its first run** (DEC-21). With `MAX_ITERATIONS=8` /
  `MAX_REVISIONS=2`, the revision cap was unreachable in research mode — the backstop
  always fired first and reported `max_iterations_exceeded` (reads like an internal
  fault) instead of `max_revisions_exceeded` (the truth: the draft never got grounded).
  Each cap was correct in isolation and unit-tested as such; only a whole-pipeline run
  saw the composition. The fix derives the backstop from the cap (`2` → `12`), pinned.

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| DEC-20 offline evals grade the pipeline only | Reshaped by Phase 15 ([ADR-0009](../../../docs/adr/0009-recorded-answer-quality-evals.md)): the suite also replays *recorded* real answers — graded keylessly, never claimed of the current model, staleness-gated on purpose. The caveat got more specific, not weaker |
| DEC-22 judge on a stronger model | Its premise (a weak critic) was **removed by Phase 16**; the judge was re-derived rather than inherited ([ADR-0010](../../../docs/adr/0010-judge-rederived-for-an-independent-critic.md) supersedes 0005). Judge == critic (both Opus 5) is recorded as an acceptance, not an oversight |
| DEC-21 derived backstop | Never reversed; the war story is quoted in DESIGN.md as the argument for eval-level testing |

## Where it lives today

`evals/` — grown from 12 authored cases to 40 plus recorded-fixture replay (41 graded
per push), with the recorder, fixture schema, and staleness gates from Phase 15.
`tests/test_evals.py` measured 2026-08-12: **171 collected** — the largest test file in
the tree, which is what an eval harness trusted to gate releases should cost.
