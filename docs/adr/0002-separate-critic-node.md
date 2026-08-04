# ADR-0002 — The critic is a separate node with the research notes as sole source of truth

**Status:** Accepted
**Promoted from:** `docs/DESIGN.md` § The graph — "The critic is a separate node with its own rubric" (DEC-02)

## Context

The pipeline exists to stop ungrounded claims reaching the reader, so grounding has to be
checked against something. The cheap option is to ask the writer to self-assess: one call
that drafts the report and then rates its own grounding.

That fails in a specific and well-known way. A model asked to grade the text it just
produced reliably produces "looks good to me" — it has no independent view of what the
research actually supported, because the same context that generated the claim is what
would have to reject it.

## Decision

Drafting and grounding-checking are separate model calls. The critic is a distinct node
with its own rubric, and it is given the research notes as the **sole** source of truth
for that check.

Its verdict feeds the revision loop: a rejected draft goes back to the writer rather than
to the reader.

## Consequences

### Accepted

- Claims the writer introduced but the notes do not support get caught, because the critic
  is grading the draft *against the notes* rather than against its own recollection of
  having written it.
- The cost is a second model call per revision, and a longer path to a finished report.
- The critic can reject, which means the loop needs a bound and an honest report when the
  bound fires — otherwise a persistently-rejected draft has no exit.

### Rejected alternative

One model drafting and self-assessing in a single call. Cheaper by a call per revision,
and rejected because it "reliably produces 'looks good to me'" — a grounding check that
almost never fails is not a grounding check.

### Known limit

The critic shares the writer's model. It is independent in **rubric**, not in **model**,
so it inherits the writer's blind spots — good enough to catch claims the notes plainly do
not support, not an independent evaluator. The separate, stronger judge that this record
does *not* cover is [ADR-0005](0005-opus-5-eval-judge.md); the argument about model
independence belongs there, not here.
