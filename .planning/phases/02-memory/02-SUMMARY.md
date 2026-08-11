---
phase: 2
slug: memory
milestone: v1.0
status: complete
executed: 2026-07-29
remastered: 2026-08-12
---

# Phase 2: Memory — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** Notes persist and are recalled by similarity, not by growing the prompt.

**Shipped in:** `5f20aa2` (2026-07-29) — the same initial commit as Phase 1. This phase is
`vector_memory.py` (79 lines at birth) plus the researcher's use of it; the JSON persistence
file (`agent_memory_store.json`) still sits in the repo root as the artifact of those first
runs.

## What shipped

- **Vector retrieval with a relevance floor, not a growing prompt** (DEC-07). Notes are
  embedded with `voyage-3.5` and retrieved by cosine similarity above a `min_similarity`
  floor (default `0.3`), so an unrelated past task cannot leak into the current one.
- **Memory as coverage-expander, not echo.** The researcher is told to *prefer information
  not already covered* by recalled notes — recall widens the search rather than replacing
  it.
- **Persistence across runs** via a JSON store: what the agent learned answering one
  question is available to the next.

## What this phase deliberately was not

The 79-line store was a single implementation, brute-force cosine over everything. The
`MemoryStore`/`Embedder` seam split (DEC-08) is Phase 3's work; the O(n) scan's
replacement by pgvector/HNSW (DEC-09) is Phase 8's; the rule that migration copies
embeddings rather than re-embedding (DEC-10) was recorded at ingest and reshaped in v1.1.

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| DEC-07 relevance floor over prompt growth | Never reversed; the floor survives in every backend, including pgvector |
| Embeddings are Voyage's, separate from the LLM | Made independently migratable in Phase 13 ([ADR-0008](../../../docs/adr/0008-embedding-migration-two-commands.md)): copy a corpus unchanged, or re-embed it with the cost quoted first |
| Unbounded note growth accepted for scope | Named a limitation in the v1.0 README; closed by Phase 12 (owner-scoped notes, 7-day TTL) |

## Where it lives today

`src/research_agent/memory.py` — four `MemoryStore` backends (json, memory, chroma,
pgvector) behind the four-method seam Phase 3 formalised, with owner scoping and TTL from
Phase 12 and the migration tooling from Phase 13 beside it.
