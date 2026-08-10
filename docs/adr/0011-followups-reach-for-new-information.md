# ADR-0011 — Follow-ups reach for new information; grounding means sole source of truth, not no new search

**Status:** Accepted — supersedes ADR-0003
**Source:** Phase 17 (2026-08-10), `REQ-followup-live-search` — the reversal ADR-0003 named
in its own *Expected reversal* section.

## Context

[ADR-0003](0003-followups-reuse-critic-no-prior-research.md) bought grounding by refusing to
search. With no new notes possible after a session started, a follow-up answer came from the
notes on hand or it did not come at all, and the second half of that sentence was the whole
enforcement mechanism.

That conflated two guarantees which are not the same guarantee:

1. **No answer from parametric knowledge.** This is the point of the pipeline, and it is
   [ADR-0002](0002-separate-critic-node.md)'s notes-as-sole-source-of-truth. Reaffirmed here,
   by citation, with that record untouched and zero-diff.
2. **No searches after session start.** This was never the point. It was the cheapest
   available way to enforce the point — if nothing can be fetched, nothing unreviewed can be
   smuggled in.

This record drops the second and keeps the first.

### What writing the test first found, and why it is the argument

The design case for the reversal is the paragraph above. The *evidence* is stronger than the
design case, and it was not visible until Phase 17's wave 3 wrote its behaviour pins against
the shipped responder before building anything. Three of the four reds said one thing three
ways:

> **Under ADR-0003, the refusal text WAS the shipped draft.**

A responder that concluded the notes could not answer wrote exactly that conclusion into
`state["draft"]`. The critic then graded it — and approved it, correctly, by its own rubric,
because a sentence that asserts nothing cannot be an unsupported assertion. The caller
received "the research didn't cover that" as their answer, stamped `approved: true`, having
passed a grounding gate that had nothing to grade.

So the pipeline's one quality gate was at its most vacuous precisely where the reader most
needed it. ADR-0003's guarantee did hold; it held by shipping a non-answer that the gate was
structurally unable to distinguish from a good one. A guarantee enforced that way is worth
replacing rather than defending, and no amount of tuning the critic would have found it —
which is also the measured reason critic-as-detector is rejected below.

### Provenance, because this record does not look like ADR-0003's

ADR-0003 was *promoted from* `docs/DESIGN.md` § The graph (DEC-04). This record carries
**Source:** instead. It does not restate a `docs/DESIGN.md` passage — it overturns the record
that did, and the passage was rewritten afterwards to follow this decision rather than the
other way round. Do not go looking for the DESIGN paragraph behind it; the DESIGN paragraph
is downstream.

## Decision

**A follow-up whose notes cannot answer the question reaches for new notes — once — and the
critic still grades whatever ships against notes and nothing else.**

### What survives

**The window between "these notes cannot answer" and "new notes have arrived" produces no
answer at all.** This is the replacement guarantee, and it is a property of control flow
rather than a promise kept by convention: the insufficiency path in `responder_node` returns
before `draft`, `reviewed`, `revision_count` and the answer-length trace entry are written.
There is no state in which an unsupported question has produced text.

The responder still has exactly two alternatives and neither is guessing: answer from the
notes, or signal that the notes do not cover the question. What changed is where the second
one goes. **The signal routes; it never generates.** The failure ADR-0003 feared — a model
improvising once the notes run out — remains structurally impossible for the same reason it
always was, and now it is impossible without also being useless.

### What dies

The refusal. `no_prior_research` stops being an end state; the row that produced it keeps its
position in the supervisor table and changes its destination. `README.md`'s "Follow-ups can't
reach for new information" limitation is deleted rather than rewritten — it was the last
surviving entry of the original nine-item v1.0 limitations list.

### Two trigger paths, one mechanism

1. **No prior notes at all.** The supervisor routes the follow-up straight to the researcher.
   No model judgment is involved: a question with nothing behind it cannot be answered from
   nothing, so going to look is the only honest move. Trace reason `no_prior_research`.
2. **Notes exist and do not cover the question.** The responder emits a structured
   insufficiency sentinel — `INSUFFICIENT: ` followed by one line naming what is missing —
   parsed in the node by fixed prefix, exactly as the critic's `APPROVED` / `REVISE:` verdicts
   have always been parsed. The parse sets `notes_insufficient`, leaves the draft untouched,
   and returns. The supervisor reads plain state. Trace reason `notes_insufficient`.

Both rows sit **below** the iteration, revision and budget rows and **above** the classifier
row. Below the guardrails, because a capped or over-budget follow-up must still end with its
own reason and never trigger a spend; above the classifier, because that position is what
keeps "a follow-up never classifies" a property of the routing table rather than of how
`followup_state` happens to be assembled.

### ADR-0001 is intact

[ADR-0001](0001-deterministic-python-routing.md) says routing is deterministic Python over
state, never a model's choice, and it survives this record unchanged. The supervisor branches
on two booleans. The only model output anywhere in the path is the *origin* of one of them —
a fixed-prefix parse of a response — which is exactly what `approved` has been since ADR-0002
was written. If a sentinel-derived flag made routing non-deterministic, so did `approved`, and
it never did: the model contributes a fact about its own output, and Python decides what
happens next.

Two supporting properties, both pinned: the prompt that asks for the sentinel and the parse
that reads it are gated on the **same boolean**, so a parse can never outlive its prompt and
turn text the model was never asked for into a routing input; and the responder is reachable
only in follow-up mode, so the gate needs no `mode` check of its own.

### The one-pass bound is this record's own deliberate limit

A follow-up gets **one** research pass, supervisor-enforced by `followup_research_done`. It
cannot loop research → insufficient → research. After the pass, the responder is prompted for
plain prose instead of the sentinel and a stray post-research `INSUFFICIENT:` is an ordinary
draft the critic judges like any other — it cannot buy a second pass.

This is stated as a limit, in the record that creates it, rather than left for a reader to
discover: a follow-up needing two rounds of research to answer gets one round and an honest
report of the gap. The honest tail is pinned by a golden case chosen for exactly that branch —
the follow-up reaches, the pass comes back with more of what it already had and nothing on the
figure that was asked for, and the refusal ships **critic-reviewed, with the attempt visible in
the trace**. A reversal is most tempted to leave untested the case where the new capability
finds nothing, so that case is the one with a name.

### `no_prior_research` is redefined, not retired

It moves from the forced-stop vocabulary to the trace: not "the run gave up", but "this is why
this follow-up went looking". It is gone from the stop vocabulary of every shipped code
surface, with a source-reading test keeping it out. Nothing migrates and no metrics code
changes — `/metrics` groups dynamically over whatever reasons the runs table holds — so
historical rows keep meaning what they meant when they were written, which is honest.

Without the trace event, a reach the design intended and a reach caused by a routing row moving
by accident look identical, and both look green. That is why the event is graded rather than
merely emitted.

### New notes enlarge the set; they do not replace it

`researcher_node` assigned `state["research_notes"] = notes`. That was correct for fifteen
phases because only one research pass had ever existed per run, and it was invisible rather
than safe: the critic grades whatever note set it is handed, so a swapped set and an enlarged
set produce equally green runs. On a follow-up pass it would have silently discarded the
session's own research. Notes now append. Attribution is unchanged — task prefix, owner, and
the turn's trace — so the note store's schema does not move.

### Carried forward from ADR-0003

Superseding a record must not silently discard the parts of it that were right. These survive
in full:

- **The responder writes into the same `draft` field the writer does**, so the critic grades a
  follow-up answer with the same rubric and the same revision loop as a report. A follow-up can
  be sent back for revision exactly like a draft can. Untouched by this record.
- **"The research didn't cover that" is still a correct answer.** It is now the answer *after*
  looking rather than *instead of* looking, and the critic is still what makes it stick.
- **A cheaper, uncritiqued follow-up path stays rejected** — it would apply a lower grounding
  standard to the follow-up than to the report it is about, invisibly.
- **Answering from parametric knowledge when notes are absent stays rejected outright.**

What ADR-0003 got wrong was not the standard. It was the enforcement.

Per the convention in [`README.md`](README.md), only ADR-0003's status line changes. Its
*Expected reversal* section still reads "That reversal has not happened" — true when written,
now history, and left exactly as it is.

## Consequences

### Accepted

- **A research-triggering follow-up costs like a research run** (≈ $0.21 at current rates)
  rather than pennies. The ask routes already reserve before admitting, so the spend is covered
  by the guardrail that already existed; the flat $0.20 reservation stands, with its documented
  `2026-09-01` review threshold untouched. The eval cost preview prices a reaching follow-up
  turn at the research constants, including its web searches, rather than discovering the gap
  on an invoice.
- **A follow-up is no longer cheap by construction.** It reaches only when its notes cannot
  answer, so most follow-ups still cost a responder and a critic call — but a reader who
  assumed the second turn is always trivial is now sometimes wrong, and that is a real change
  to the product's cost shape rather than an implementation detail.
- **The caps bound the expanded path with the same worst case as research mode**: ten supervisor
  turns against `MAX_ITERATIONS = 12`, because the path-2 turn substitutes signal + researcher
  for classifier + researcher. No cap formula changed, and the revision cap remains the
  reachable backstop. Guardrails outrank both reach rows, pinned by tests over every
  cap-versus-reach pair.
- **A budget stop can now land after the researcher has spent and before any draft exists.**
  The turn reports `budget_exceeded` honestly and ships no answer — and the notes that pass
  gathered are written to the store *before* the supervisor sees the cost, so they survive the
  stop and are there for the next turn. This asymmetry was measured, not predicted: the
  deterministic notes-stored grader runs on a case's research turn, and in the phase's own
  golden case that turn was stopped before the researcher ever ran, while the follow-up's pass
  stored a note anyway. Recorded here rather than tidied away, because a reader comparing "the
  run was stopped" against "the store grew" deserves to find the explanation written down.
- **The eval before-measures flip.** Four golden cases changed direction and one grader was
  retired by being scoped: the property "a follow-up must not search" is still checked, verbatim,
  on the cases where it is still true. The pre-reversal behaviour lives in git history and in
  ADR-0003, not in living tests.

### Rejected alternatives

- **Critic-as-detector** — letting the critic's verdict signal that the notes were insufficient.
  Rejected on measurement, not taste: an honest refusal is `APPROVED`, because it claims nothing.
  The verdict is structurally blind to the condition it would have been asked to detect.
- **The responder answering directly once the notes run out.** The exact failure the pipeline
  exists to make impossible. Permitting it in the follow-up path would permit it everywhere that
  matters.
- **Multi-pass research within one follow-up.** Unbounded cost for marginal reach. The one-pass
  bound is named above as this record's own limit rather than presented as a complete solution.
- **A turn or session column on the note store.** Four backends and a contract suite would move
  for zero functional gain; task prefix, owner and the turn's trace already attribute a note to
  the question that caused it.
- **Regex refusal-detection as the router** — reusing the eval graders' refusal patterns to spot
  insufficiency in ordinary prose. Rejected: it imports a grader's maintenance cost into the
  routing path, and it decides on the shape of a sentence where the sentinel decides on a
  contract the model was explicitly asked to honour.
