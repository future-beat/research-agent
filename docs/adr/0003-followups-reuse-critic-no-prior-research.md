# ADR-0003 — Follow-ups reuse the critic; a follow-up with no prior notes stops with `no_prior_research`

**Status:** Accepted
**Promoted from:** `docs/DESIGN.md` § The graph — "Follow-ups reuse the critic instead of bypassing it" (DEC-04)

## Context

A reader who already has a report will ask a second question about it. Answering that
question should not mean re-searching the web — the research has been done, the notes are
on hand, and paying for a fresh search on every follow-up would make the second turn cost
as much as the first.

But cheap and ungrounded are different things. The tempting shortcut is a separate,
uncritiqued follow-up path: the responder answers, the answer goes straight back. That
gives the follow-up a *lower standard of grounding* than the report it is about, in the
same conversation, with no signal to the reader that the bar moved.

The worse case is a follow-up issued with no prior notes at all. There is nothing to ground
against, and a model asked a question with no retrieved context will answer anyway — from
its own parametric knowledge, confidently, in the same voice as a researched report. That
is the single failure mode this whole pipeline exists to prevent.

## Decision

The responder writes into the same `draft` field the writer does.

Three things follow from that one choice:

- The critic grades a follow-up with the **same rubric and the same revision loop** as a
  report. A follow-up can be sent back for revision exactly like a draft can.
- The responder is told that "the research didn't cover that" is a **correct answer**. The
  critic is what makes that stick — an answer that reaches past the notes is a rejected
  answer, not a helpful one.
- A follow-up issued with no prior notes stops with `no_prior_research`. It does not answer
  from model knowledge.

## Consequences

### Accepted

- A follow-up costs a critic pass. The second turn is not free, and it is not meant to be:
  the grounding guarantee is the product, and it does not get suspended because the
  question was short.
- `no_prior_research` is a visible stop rather than a silent degradation. The caller learns
  the pipeline had nothing to work from, which is a more useful result than a plausible
  paragraph of unsourced text.
- The user-facing consequence is stated in `README.md` § Limitations: follow-ups cannot
  reach for new information. A follow-up needing a fresh search gets "the research didn't
  cover that" rather than an answer.

### Rejected alternatives

- **A cheaper, uncritiqued follow-up path.** Rejected because it applies a lower grounding
  standard to the follow-up than to the report, invisibly.
- **Answering from parametric knowledge when notes are absent.** Rejected outright — this
  is the exact failure the pipeline is built to make impossible, and permitting it in the
  follow-up path would permit it everywhere that matters.

### Expected reversal

Phase 17 (`REQ-followup-live-search`) is expected to supersede this record: it gives
follow-ups a live search path, which changes the `no_prior_research` position from "stop"
to "go find out". That reversal has not happened. This record is `Accepted` as written, and
the trade it names — grounding over reach — is the trade in force today.
