# Architecture decision records

This directory holds the load-bearing architectural decisions as numbered,
status-bearing records. Each one is promoted from the narrative in
[`docs/DESIGN.md`](../DESIGN.md), which stays as it is — the readable argument for why the
system is shaped this way. The records exist so that a later phase reversing a decision
supersedes something explicit instead of quietly contradicting a paragraph.


## Record shape

Records use the [Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
form. Numbering is sequential and zero-padded (`0001`, `0002`, …) and files are named
`NNNN-slug.md`. Every record carries:

- a title line: `# ADR-000N — <Title>`
- a `**Status:**` line
- a provenance line — `**Promoted from:**` naming the `docs/DESIGN.md` section and the
  `DEC-NN` id it came from, or `**Source:**` for a record that did not come from
  `docs/DESIGN.md`
- `## Context`, `## Decision`, `## Consequences` — `##` headings, in that order

`## Consequences` may split into `### Accepted` and `### Rejected alternative`
subsections where that reads better; the three top-level headings are the contract.


## Supersession convention

When a later decision overturns a record, follow this verbatim:

1. In the **overturned** record, change only the status line to:
   `**Status:** Superseded by ADR-000N (Phase NN)` — the superseding record's number and
   the phase that made the change, on the same line.
2. In the **new** record, the status line reads:
   `**Status:** Accepted — supersedes ADR-000M`.
3. Update the `Status` and `Superseded by` cells for both records in the index below.

**The Context, Decision and Consequences of a superseded record are never edited.** The
record stays exactly as it was written, including claims that are no longer true — that is
the point of keeping it. Only the status line changes. If the reasoning needs correcting
rather than reversing, that is a new record too.


## Index

Six of the seven records are `Accepted` today. One supersession has actually
happened — ADR-0007 overturned ADR-0006 in Phase 12, which ADR-0006 had itself
forecast. The remaining *expected* supersessions come from the reversal register
in `.planning/ROADMAP.md` and are forecasts, not facts.

| # | Record | Title | Status | Superseded by |
|---|--------|-------|--------|---------------|
| 0001 | [0001-deterministic-python-routing.md](0001-deterministic-python-routing.md) | Routing is a deterministic Python state machine, not an LLM prompt | Accepted | — |
| 0002 | [0002-separate-critic-node.md](0002-separate-critic-node.md) | The critic is a separate node with the research notes as sole source of truth | Accepted | — |
| 0003 | [0003-followups-reuse-critic-no-prior-research.md](0003-followups-reuse-critic-no-prior-research.md) | Follow-ups reuse the critic; no prior notes stops with `no_prior_research` | Accepted | *expected:* Phase 17 (REQ-followup-live-search) |
| 0004 | [0004-sessions-in-sqlite-not-langgraph-checkpointer.md](0004-sessions-in-sqlite-not-langgraph-checkpointer.md) | Sessions store completed runs in SQLite, deliberately not LangGraph's checkpointer | Accepted | — |
| 0005 | [0005-opus-5-eval-judge.md](0005-opus-5-eval-judge.md) | The eval judge runs on a stronger model than the pipeline and returns a structured verdict | Accepted | *expected:* Phase 16 (REQ-independent-critic-model) |
| 0006 | [0006-separate-sessions-token-fails-closed.md](0006-separate-sessions-token-fails-closed.md) | A separate `SESSIONS_TOKEN`, and the session endpoints fail closed | Superseded | [ADR-0007](0007-anonymous-identity-fairness-global-cap.md) (Phase 12) |
| 0007 | [0007-anonymous-identity-fairness-global-cap.md](0007-anonymous-identity-fairness-global-cap.md) | Fairness keys on an auto-issued anonymous identity; the global cap bounds the bill | Accepted — supersedes [ADR-0006](0006-separate-sessions-token-fails-closed.md) | — |

**ADR-0006 and ADR-0007 are the odd ones out.** Records 0001–0005 are promotions of existing
`docs/DESIGN.md` passages and carry a `**Promoted from:**` line. ADR-0006 originates in the
Phase 10.5 hotfix that closed the live endpoint exposure and ADR-0007 in Phase 12's identity
work — there is no `docs/DESIGN.md` passage behind either, so both carry `**Source:**`
instead. Do not go looking for one.

**Reading a superseded record.** ADR-0006 stays exactly as it was written, including the
claims Phase 12 overturned; that is the point of keeping it. Which of its parts survived is
recorded in ADR-0007's *Carried forward from ADR-0006* section, not by editing 0006.
