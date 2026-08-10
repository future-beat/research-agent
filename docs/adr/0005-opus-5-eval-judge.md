# ADR-0005 — The eval judge runs on a stronger model than the pipeline and returns a structured verdict

**Status:** Superseded by ADR-0010 (Phase 16)
**Promoted from:** `docs/DESIGN.md` § Testing — "The judge runs on a different, stronger model than the pipeline" (DEC-22)

## Context

The in-graph critic established in [ADR-0002](0002-separate-critic-node.md) is independent
in **rubric** but not in **model** — it shares the writer's. That is good enough to catch
claims the notes plainly do not support, and it is not an independent evaluator; the
`README.md` § Limitations has said so since Phase 1.

That caveat is the premise of this record. A judge grading the pipeline's output on the
*same* model the pipeline runs on would inherit exactly the blind spots it exists to find:
where the writer and critic agree wrongly, the judge agrees too, and the eval reports a
clean sheet for the failure it was built to surface.

There is a second, separate hazard. A scoring harness parses whatever the judge emits. If
the verdict is a text convention, a judge that phrases itself unexpectedly is mis-parsed —
and a mis-parsed verdict does not fail loudly, it produces a confident wrong number.

## Decision

The judge runs on **Opus 5** — `JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL",
"claude-opus-5")` in `evals/graders.py`, overridable by `EVAL_JUDGE_MODEL` — against a
**Sonnet 5** pipeline (`MODEL = "claude-sonnet-5"` in `src/research_agent/graph.py`).

It returns a **structured verdict** rather than a text convention the harness has to
interpret.

## Consequences

### Accepted

- Judging costs more per case than the pipeline it grades. That is the price of an
  evaluator that does not share the evaluated system's blind spots, and it is paid on eval
  runs only, not on user traffic.
- The judge is a *compensating control* for the shared critic model, not an independent
  design choice. It is only load-bearing because ADR-0002's known limit exists.

### Rejected alternatives

- **A same-model judge.** Cheaper, and rejected because it inherits the blind spots it
  exists to find.
- **A text verdict.** Rejected because a harness that mis-parses reports a confident wrong
  number, which is worse than crashing — a crash is noticed, a wrong score is trusted.

### Expected reversal

Phase 16 (`REQ-independent-critic-model`) is expected to supersede this record. It gives
the in-graph critic its own model, which removes this record's premise: with an independent
critic, the rationale for a stronger judge has to be **re-derived rather than inherited**.
Nothing about that is settled today; this record is `Accepted` as written.
