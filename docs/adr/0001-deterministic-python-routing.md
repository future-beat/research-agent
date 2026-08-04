# ADR-0001 — Routing is a deterministic Python state machine, not an LLM prompt

**Status:** Accepted
**Promoted from:** `docs/DESIGN.md` § The graph — "Routing is a state machine, not a prompt" (DEC-01)

## Context

An agent graph has to decide what runs next after each step. The obvious option, and the
one most agent frameworks lead with, is to ask a model: hand the current state to an LLM
and let it name the next node. That makes the graph flexible — new nodes can be added and
the router will route to them without anyone rewriting a branch.

It also makes control flow non-reproducible. The same input can take a different path on a
second run, a routing bug can only be reproduced probabilistically, and every test of the
routing table needs an API key and a network call.

## Decision

`supervisor_node` is plain Python — a chain of `if` statements over `AgentState`. No model
call decides the next hop.

Control flow is therefore deterministic: identical inputs take an identical path, every
run. The LLM does the work; the graph decides the order.

This record covers routing only.

## Consequences

### Accepted

- The routing table is testable with no API keys and no network. This is a large part of
  why nothing in the graph is constructed at import time — a test can import the module,
  drive `supervisor_node` over hand-built states, and assert on the next hop.
- A routing bug is reproducible from its input alone, so it can be pinned by a test rather
  than observed and hoped about.
- Adding a node means editing the branch chain. That is deliberate friction: the set of
  reachable paths stays enumerable and reviewable.

### Rejected alternative

An LLM router choosing the next node. Rejected because it trades exactly the properties
above — reproducibility and offline testability — for flexibility this pipeline does not
need. The node set here is small, known in advance, and changes only when the design
changes.
