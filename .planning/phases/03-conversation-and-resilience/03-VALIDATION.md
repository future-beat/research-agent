---
phase: 3
slug: conversation-and-resilience
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 3 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-01),
> but this is the phase where verification stopped being manual: the first 886 test lines
> landed in the same commit as the behaviour they pin. Criteria reconstructed at remaster;
> measurements against the 2026-08-12 tree (737 passed / 65 skipped keyless).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| A follow-up runs through the same critic and revision loop as a fresh question | `tests/test_supervisor_routing.py` follow-up rows | **60 collected** in the file; the follow-up rows were re-pinned with eight precedence pairs in Phase 17 |
| A follow-up with no prior notes never answers from model knowledge | routing tests + eval refusal graders | The *stop* this phase shipped was reversed by Phase 17 — the guarantee is now "researches, one pass, and ships nothing in the window"; `no_prior_research` names a row that reaches, not a stop reason |
| Store backends are interchangeable behind the four-method seam | `tests/test_memory_stores.py` + `tests/test_store_contract.py` | **31** + **102 collected**, four arms |
| Retries: retryable statuses only, jittered backoff, `retry-after` honoured, attempts traced | `tests/test_retry.py` | **29 collected**, injectable sleep/rng, exact-delay assertions |

## What execution-time verification actually was

The suite itself — this phase created it. Routing, retry, and store behaviour were
pinned the day they shipped, keylessly, which is why every later phase could refactor
against them. What did *not* exist: any eval-level check that the composition of caps
was sane (Phase 6 found the unreachable revision cap), or any probe that the tests
could fail (mutation discipline arrived with GSD in v1.1).

## Honest gaps

- DEC-04's refusal behaviour was validated as *correct* here and stood for fourteen
  phases; Phase 17 measured that the refusal sentinel could ship as the answer text
  itself (critic-approved, because it claims nothing) — the strongest argument that a
  green suite validates the design you have, not the design you should have.
- The Chroma backend's tests ran only where `chromadb` was installed; it joined the
  dev extra and CI as a mandatory arm in Phase 12.
