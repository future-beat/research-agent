---
phase: 1
slug: core-loop
milestone: v1.0
status: complete
executed: 2026-07-29
remastered: 2026-08-12
---

# Phase 1: Core loop — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** A question routes through a supervisor to workers and returns a grounded report.

**Shipped in:** `5f20aa2` (2026-07-29) — the initial commit, which carried Phases 1 *and* 2
together. The phase split is the roadmap's framing of that commit, not two separate landings:
`capstone_research_agent.py` (266 lines — the graph) and `chat.py` (207 lines — the REPL)
are this phase; `vector_memory.py` is Phase 2's.

## What shipped

- **The supervisor pattern.** A LangGraph graph where every worker returns to a central
  supervisor that re-reads state and picks the next hop: classifier → researcher → writer →
  critic. Routing is a chain of `if` statements over `AgentState` — a deterministic function
  of state, never a model call (DEC-01). The rejected alternative is on the record: an LLM
  router choosing the next node.
- **The critic as a separate node** with the research notes as its *sole* source of truth
  (DEC-02). One model drafting and self-assessing was rejected because it "reliably produces
  'looks good to me.'" This node is the project's core value made structural: the pipeline
  never answers from model knowledge when it should be answering from research.
- **Bounded loops with honest forced stops** (DEC-03). `MAX_REVISIONS` caps the
  critic↔writer cycle, `MAX_ITERATIONS` backstops total supervisor turns, and a fired cap
  propagates `forced_stop_reason` to output — "a silent unapproved draft would be worse
  than no draft."
- **Per-node inference settings** (DEC-05): the classifier runs thinking-disabled under a
  20-token ceiling (one word from a fixed set); researcher/writer/critic run adaptive
  thinking at `effort: "medium"`.
- **A trace** (DEC-06): each node appends routing decisions, recall counts, draft lengths,
  and critic verdicts to `state["trace"]`.
- **A terminal REPL** (`chat.py`) so the loop was demonstrable from day one.

## Decisions made here that later phases leaned on

| Decision | Fate |
|---|---|
| DEC-01 deterministic Python routing | Promoted to [ADR-0001](../../../docs/adr/0001-deterministic-python-routing.md) in Phase 10; never reversed |
| DEC-02 separate critic node | Promoted to [ADR-0002](../../../docs/adr/0002-separate-critic-node.md); never reversed — Phase 16 made the critic *more capable* than the writer |
| DEC-03 bounded loops, honest stops | Never reversed; the same `forced_stop_reason` machinery carried the spend cap (Phase 5) and the follow-up research bound (Phase 17) |
| DEC-05 per-node inference settings | Extended by Phase 16's `CRITIC_MODEL` — per-node became per-model |
| DEC-06 trace | Became `/trace` (Phase 4) and the eval graders' primary witness (Phases 6, 15, 17) |

## Where it lives today

`src/research_agent/graph.py` (the file was `capstone_research_agent.py`, renamed
`research_agent.py` the same night in `c96b4bc`, packaged under `src/` in Phase 9.1).
The routing table is still `supervisor_node`, still deterministic, now ten rows — the
README's Architecture section prints it verbatim.
