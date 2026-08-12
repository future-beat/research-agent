---
phase: 2
slug: memory
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 2 — Validation (retroactive)

> **Remastered record.** No validation contract existed when this phase executed
> (2026-07-29); the phase shipped with no tests. Criteria reconstructed at remaster;
> all measurements are against the 2026-08-12 tree (737 passed / 65 skipped keyless).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| Recall is cosine-over-embeddings with a `min_similarity` floor; an unrelated note stays out | `tests/test_memory_stores.py` | **31 collected** |
| Every backend honours the same store contract (add/query/len/describe, floor semantics, deletion, owner scoping) | `tests/test_store_contract.py` — one file, four arms | **102 collected** (pgvector arm among the 65 keyless skips; runs armed and in CI) |
| The graph reaches the store only through the four-method seam | seam-reach test added with DEC-08 (Phase 3) | Present in the suite; the seam has held through three new backends |
| Notes persist across process restarts | contract suite persistence cases | Covered per backend |

## What execution-time verification actually was

Manual REPL runs against the JSON store — ask, restart, ask a related question, watch
`recalled N note(s)` in the trace. The store-contract suite that now guards this began
in Phase 3 (202 lines), was generalised across backends in Phase 8 (452 lines), and
grew its fourth arm and ownership/TTL semantics in v1.1 (Phase 12).

## Honest gaps

- The relevance floor's default (`0.3`) was chosen by feel, not measurement, and was
  never revisited in v1.0. It later proved marginal in an unexpected place: Phase 15
  measured that a one-word-overlap seeded note recalls 17/60 process seeds under the
  hash embedder, and pinned heavy-overlap seeds into the eval dataset as a consequence.
- Recall *quality* had no measure at all until Phase 13 built the golden recall set to
  separate a model change from an infrastructure change.
