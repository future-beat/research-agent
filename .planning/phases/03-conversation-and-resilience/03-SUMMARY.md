---
phase: 3
slug: conversation-and-resilience
milestone: v1.0
status: complete
executed: 2026-08-01
remastered: 2026-08-12
---

# Phase 3: Conversation & resilience — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** Follow-ups work over prior notes; stores are pluggable; transient failures retry.

**Shipped in:** `b517710` (2026-08-01) — 1,739 insertions: the responder and follow-up
mode, the `MemoryStore` ABC with three backends, `retry.py` (165 lines), and **the
project's first test suite** — four files, 886 test lines, `pytest.ini`,
`requirements-dev.txt`.

## What shipped

- **Follow-up conversations that reuse the critic** (DEC-04). The responder writes into
  the same `draft` field as the writer, so a follow-up is graded by the same rubric and
  revision loop — no cheaper uncritiqued path. The responder is told "the research didn't
  cover that" is a *correct* answer, and a follow-up with no prior notes stopped with
  `no_prior_research` rather than answering from model knowledge — described at the time
  as refusing "the single failure mode this whole pipeline exists to prevent."
- **Pluggable stores** (DEC-08). `vector_memory.py` grew 79 → 302 lines: a `MemoryStore`
  ABC (`add`, `query`, `len`, `describe`) with JSON, in-memory, and Chroma backends, and
  `Embedder` as a separate seam so switching stores can never silently switch embedding
  models — "that would invalidate every vector already written." A reach test asserts the
  graph never uses more than those four methods.
- **Retry at the node boundary** (DEC-17). Only retryable statuses (connection errors,
  408/429/5xx — never 400/401); exponential backoff with equal jitter; a server's
  `retry-after` wins when longer ("our curve is a guess and the header isn't"); every
  attempt recorded in the trace; `sleep` and `rng` injectable so the tests run in
  milliseconds and assert exact delays.
- **The first tests**: `test_supervisor_routing.py` (267 lines), `test_retry.py` (218),
  `test_memory_stores.py` (202), `test_graph_smoke.py` (199). The deterministic routing
  decision (DEC-01) paid off here — the whole table became unit-testable with no keys.

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| DEC-04 follow-ups reuse the critic; `no_prior_research` stops | The critic-reuse half survives untouched. The refusal half is v1.0's most consequential call: named a README limitation at ship, promoted to [ADR-0003](../../../docs/adr/0003-followups-reuse-critic-no-prior-research.md) in Phase 10, **reversed by Phase 17** ([ADR-0011](../../../docs/adr/0011-followups-reach-for-new-information.md)) — an unsupported follow-up now researches, one pass, and grounding survived because it never meant "no new search" |
| DEC-08 store/embedder seams | Held through pgvector (Phase 8) and owner/TTL scoping (Phase 12) |
| DEC-17 node-boundary retry | Never reversed; `PoolTimeout` was explicitly *excluded* from it in Phase 11 |

## Where it lives today

Follow-up mode in `src/research_agent/graph.py` (the responder is the "author" of
follow-up mode); stores in `memory.py`; `retry.py` unchanged in role. Tests measured
2026-08-12: `test_retry.py` **29**, `test_memory_stores.py` **31**,
`test_supervisor_routing.py` **60**, `test_graph_smoke.py` **43** collected.
