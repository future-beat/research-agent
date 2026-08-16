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

Ten of the fourteen records are `Accepted` today. Four supersessions have actually
happened — ADR-0007 overturned ADR-0006 in Phase 12, ADR-0010 overturned ADR-0005 in
Phase 16, ADR-0011 overturned ADR-0003 in Phase 17, and ADR-0012 overturned ADR-0010 in
Phase 18. **Three of the four were forecast by the record they overturned; the fourth was
not.** ADR-0005, ADR-0003 and ADR-0006 each named the phase that would supersede them in an
*Expected reversal* section. ADR-0010 carries no such section, because it was written into a
register the project was closing: with Phase 17 the reversal register in
`.planning/ROADMAP.md` was declared **spent**, every supersession in the table below a fact
and no row carrying an *expected* one. Phase 18 reopened that register once, deliberately,
by moving the eval judge off the critic's model — and [ADR-0012](0012-judge-independent-of-the-critic.md)
states the reopening in its own text rather than letting the table quietly grow a row. So
the honest reading of the table today is: no supersession here is *pending*, and the
register is no longer closed. The two newest records supersede nothing: ADR-0013 adds a
second per-node model rather than reversing the first, and ADR-0014 states a cost position
no earlier record had argued.

| # | Record | Title | Status | Superseded by |
|---|--------|-------|--------|---------------|
| 0001 | [0001-deterministic-python-routing.md](0001-deterministic-python-routing.md) | Routing is a deterministic Python state machine, not an LLM prompt | Accepted | — |
| 0002 | [0002-separate-critic-node.md](0002-separate-critic-node.md) | The critic is a separate node with the research notes as sole source of truth | Accepted | — |
| 0003 | [0003-followups-reuse-critic-no-prior-research.md](0003-followups-reuse-critic-no-prior-research.md) | Follow-ups reuse the critic; no prior notes stops with `no_prior_research` | Superseded | [ADR-0011](0011-followups-reach-for-new-information.md) (Phase 17) |
| 0004 | [0004-sessions-in-sqlite-not-langgraph-checkpointer.md](0004-sessions-in-sqlite-not-langgraph-checkpointer.md) | Sessions store completed runs in SQLite, deliberately not LangGraph's checkpointer | Accepted | — |
| 0005 | [0005-opus-5-eval-judge.md](0005-opus-5-eval-judge.md) | The eval judge runs on a stronger model than the pipeline and returns a structured verdict | Superseded | [ADR-0010](0010-judge-rederived-for-an-independent-critic.md) (Phase 16) |
| 0006 | [0006-separate-sessions-token-fails-closed.md](0006-separate-sessions-token-fails-closed.md) | A separate `SESSIONS_TOKEN`, and the session endpoints fail closed | Superseded | [ADR-0007](0007-anonymous-identity-fairness-global-cap.md) (Phase 12) |
| 0007 | [0007-anonymous-identity-fairness-global-cap.md](0007-anonymous-identity-fairness-global-cap.md) | Fairness keys on an auto-issued anonymous identity; the global cap bounds the bill | Accepted — supersedes [ADR-0006](0006-separate-sessions-token-fails-closed.md) | — |
| 0008 | [0008-embedding-migration-two-commands.md](0008-embedding-migration-two-commands.md) | Embedding migration is two commands: copy-only preserved, re-embed measured | Accepted | — |
| 0009 | [0009-recorded-answer-quality-evals.md](0009-recorded-answer-quality-evals.md) | Answer quality is graded from recorded runs, and never claimed of the current model | Accepted | — |
| 0010 | [0010-judge-rederived-for-an-independent-critic.md](0010-judge-rederived-for-an-independent-critic.md) | The judge is re-derived for an independent critic: a different job, not a compensating control | Superseded | [ADR-0012](0012-judge-independent-of-the-critic.md) (Phase 18) |
| 0011 | [0011-followups-reach-for-new-information.md](0011-followups-reach-for-new-information.md) | Follow-ups reach for new information; grounding means sole source of truth, not no new search | Accepted — supersedes [ADR-0003](0003-followups-reuse-critic-no-prior-research.md) | — |
| 0012 | [0012-judge-independent-of-the-critic.md](0012-judge-independent-of-the-critic.md) | The eval judge is independent of the critic by model identity, and the family residual is stated rather than solved | Accepted — supersedes [ADR-0010](0010-judge-rederived-for-an-independent-critic.md) | — |
| 0013 | [0013-classifier-on-its-own-model.md](0013-classifier-on-its-own-model.md) | The classifier runs on its own model, and its default is the upgrade rather than a neutral | Accepted | — |
| 0014 | [0014-cost-approximation-by-design.md](0014-cost-approximation-by-design.md) | Reported cost is an estimate by design, and invoice reconciliation is rejected | Accepted | — |

**ADR-0006 onward are the odd ones out.** Records 0001–0005 are promotions of
existing `docs/DESIGN.md` passages and carry a `**Promoted from:**` line. ADR-0006 originates
in the Phase 10.5 hotfix that closed the live endpoint exposure, ADR-0007 in Phase 12's
identity work, ADR-0008 in Phase 13's embedding migration, ADR-0009 in Phase 15's
answer-quality evals, ADR-0010 in Phase 16's independent critic model, ADR-0011 in
Phase 17's follow-up reach, ADR-0012 in Phase 18's independent eval judge, ADR-0013 in
Phase 21.5's classifier model, and ADR-0014 in Phase 22's close-out — there is no
`docs/DESIGN.md` passage behind any of the nine, so all nine carry `**Source:**` instead.
Do not go looking for one.

ADR-0014 is worth one extra word here, because `docs/DESIGN.md` *does* have a Cost section
and a reader may reasonably expect a promotion. That section covers the spend cap,
effective-dating, and unpriced-model handling; it never argues that the reported figure is
an estimate rather than the invoice. The position was operationally true and undocumented,
which is why the record carries `**Source:**` like the eight before it.

ADR-0011 is the one that could mislead, because the decision it reverses *did* come from
`docs/DESIGN.md`: ADR-0003 was promoted from DEC-04. But a record's provenance line names
where its own argument came from, and 0011's did not come from a passage — it overturns the
record that was promoted from one, and the DESIGN paragraph was then rewritten to follow the
new decision. The passage is downstream of 0011, not behind it.

**ADR-0008 and ADR-0009 supersede nothing, deliberately.** Each reverses the *scope* of a
`DEC-NN` in `.planning/intel/decisions.md` — `DEC-10` and `DEC-20` respectively — that was
never promoted to a numbered record, so by the convention above there is no status line to
change and no `Accepted — supersedes ADR-000M` form to use. What survives of the DEC and what
is new are recorded in the new record's prose instead. 0009 follows 0008's shape on purpose:
DEC-20's caveat is carried forward and *upgraded* rather than deleted, exactly as DEC-10's
copy-only guarantee was preserved as a named command rather than dropped.

**Reading a superseded record.** ADR-0006 stays exactly as it was written, including the
claims Phase 12 overturned; that is the point of keeping it. Which of its parts survived is
recorded in ADR-0007's *Carried forward from ADR-0006* section, not by editing 0006. ADR-0005
is read the same way: its premise — that the in-graph critic shares the writer's model — was
true when it was written and Phase 16 removed it, so what survives is in ADR-0010's *Carried
forward from ADR-0005* section and 0005 itself is untouched below its status line.

ADR-0010 is now read that way too, and it is the one case where the chain runs three deep.
It carries the surviving half of ADR-0005 *and* has a surviving half of its own, recorded in
ADR-0012's *Carried forward from ADR-0010* section — so a reader tracing the eval judge's
rationale reads 0012 for what is current, 0010 for what survived 0005, and 0005 for the
original argument. Two things in 0010 deserve naming here, because a `Superseded` status
invites the assumption that everything under it is dead. Only one of its two positions was
overturned: the eval judge deliberately running on the critic's own model, which ADR-0012
ends. Its other position — the in-graph critic runs on a more capable model than the writer
it gates — is untouched, still deployed, and still has no successor record. Nothing below
0010's status line was edited when 0012 landed.

ADR-0003 is the sharpest case of the rule, and the one most likely to look like an oversight.
Its *Expected reversal* section ends "That reversal has not happened" — a sentence Phase 17
made false, sitting in a record Phase 17 superseded. It stays exactly as written. It was true
on the day it was written, it is now a record of what the project believed and forecast at
that point, and editing it would replace history with a tidier fiction. What survives of
ADR-0003 — the shared critic, the shared revision loop, and "the research didn't cover that"
as a correct answer — is in ADR-0011's *Carried forward from ADR-0003* section.
