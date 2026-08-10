# ADR-0010 — The judge is re-derived for an independent critic: a different job, not a compensating control

**Status:** Accepted — supersedes ADR-0005
**Source:** Phase 16 (2026-08-10), `REQ-independent-critic-model`

## Context

[ADR-0005](0005-opus-5-eval-judge.md) said its own premise out loud: *"The judge is a
compensating control for the shared critic model, not an independent design choice. It is
only load-bearing because ADR-0002's known limit exists."* It also pre-named this phase in
its *Expected reversal* section, and said the rationale would have to be **re-derived rather
than inherited**.

This phase removes the premise. `graph.critic_model()` reads `CRITIC_MODEL` on every call;
unset or blank means the writer's model, so the *code* default is neutral and deploying the
capability alone changes nothing. Production is deliberately not neutral: `CRITIC_MODEL =
'claude-opus-5'` in `fly.toml [env]` — committed as configuration rather than set as a
secret, because the point of the stance is that it is visible. The cutover is this phase's
own deliverable, executed in 16-04 after the phase PR merges.

So the compensating control has nothing left to compensate for, and the question this record
answers from scratch is: **with an independent critic, what is the judge for?**

Two of the things recorded below are not deductions from the old record. One is a new design
position — the project owner's, stated in his own words at plan review, and it is the reason
the production flip happens at all. The other is a property of the chosen configuration that
would otherwise be discovered months later by whoever first noticed that two model names in
this repo are the same string.

## Decision

**The judge exists for a different job than the critic; it must not share the *writer's*
model; it deliberately *does* share the critic's; and "stronger" survives as a preference for
the judge and as a reason only for the critic.**

`JUDGE_MODEL` stays `claude-opus-5` (`os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")` in
`evals/graders.py`). The model that moves in this phase is the critic's.

### The different job — this leg stands on its own legs

The **critic** gates *drafts* against *notes*. It runs inline, inside the graph, once per
draft, and its verdict feeds the revision loop — it shapes what ships, and by the time a
reader sees an answer the critic has already had its say or the run reported why it stopped.

The **judge** grades *finished answers* against the *question and a rubric*. It runs
retrospectively, across the golden set, never on user traffic. Its verdicts are the refusal
gate for recordings (`record_case_to_fixture` raises without a judge, so a recording whose own
judge failed is never committed) and, once recorded, they are the replayed assertions of every
keyless CI run.

Those are different questions asked of different artefacts at different times, and the
distinction holds whatever models either one runs on. Removing the shared-model premise
removed a reason the judge had to be **stronger**; it did not remove a reason the judge
**exists**. If the two had been doing the same job, the honest move after this phase would
have been to delete the judge, not to re-justify it.

### The critic runs on a more capable model than the writer — the owner's position, in his words

> "Use Opus as the critic's model since it has to be more capable than the writer's model."

— Hesam, 2026-08-10, at plan review for this phase.

This is recorded as **his rationale, not an inference**. The research for this phase
recommended shipping the capability with a neutral default and deferring any production flip;
that recommendation was overruled by the position above, and the flip became the phase's
deliverable.

It is also a genuinely new design position rather than a restatement of ADR-0005, and it
points the other way. ADR-0005 justified a **strong judge by a weak critic** — the gate was
accepted as weak and something downstream compensated. This position wants the **gate itself
stronger than the thing it gates**: a critic no more capable than the writer can only catch
the errors its own blind spots permit, and asking it to police a draft produced under the same
limits is asking for agreement. Hence `CRITIC_MODEL=claude-opus-5` in production against a
`claude-sonnet-5` writer.

The code default stays neutral on purpose. Tests, CI and every keyless context run with
`CRITIC_MODEL` unset, where `critic_model() == MODEL` and the pipeline behaves exactly as it
did before this phase. The stance lives in the deployment, where it costs money and can be
turned off by one variable.

### Independence, re-targeted — and honestly narrowed

The hard requirement is **judge ≠ the writer's model**. The judge audits the writer's output,
and a judge sharing the writer's model inherits precisely the blind spots it exists to find.
That constraint is already pinned — `assert G.JUDGE_MODEL != graph.MODEL`,
`tests/test_evals.py:464` — and it survives this record unchanged.

**Judge-versus-critic independence is accepted as lost.** In production both run on
`claude-opus-5`. That is not an oversight, and it is not merely a configuration an operator
*could* reach: it is the configuration being shipped, chosen with the consequence in view. So
the honest statement of what the eval judge's verdicts are worth is narrower than ADR-0005's:
**they are independent of the writer's model and they are not independent of the critic's
family.** Where the critic waves a blind spot through, the judge is likelier to wave it
through as well, and a recorded grounding verdict correlates with the gate it audits.

That narrowing is stated here rather than left to be found. Record mode says the same thing
out loud once per run on stderr when `judge.model == graph.critic_model()`, worded as a
property of the deployed configuration and never as an accusation — a line that calls the
operator's own decision a misconfiguration on every run is a line the operator learns to skip.

One further honesty, which ADR-0005 also never claimed: Opus 5 and Sonnet 5 are the same
vendor and the same family, so even judge ≠ writer buys family-level independence and no more.
Cross-vendor judging would be stronger independence; the harness is Anthropic-SDK-only and
that is out of scope for this phase.

### "Stronger", for the judge, is a preference now

Grading grounding, coverage, structure and refusal honesty across arbitrary domains is a
discrimination task, and the strongest priced model available is a defensible default for one
— at a cost paid on eval runs only, never on user traffic. That is enough to keep the judge
where it is, and it is a **preference**, not a requirement: an operator pointing
`EVAL_JUDGE_MODEL` at something cheaper is trading grading sharpness for money, not violating
this record.

"Stronger *because the critic is weak*" is dead with its premise. Strength survives as a
**reason** in exactly one place in this record — the critic, above, where it is the owner's
position about the gate rather than a compensation for it.

### The conclusion

**No judge flip.** `JUDGE_MODEL` stays `claude-opus-5`, now as a fresh choice with the four
legs above rather than as an inherited compensation. **The flip in this phase is the
critic's** — Sonnet to Opus, via `CRITIC_MODEL` in `fly.toml [env]`, executed in 16-04. Had
this re-derivation concluded that the *judge* should change, that flip would have been
recorded here as a consequence and deferred rather than performed inside the record.

### Carried forward from ADR-0005

Superseding 0005 must not silently discard the half of it that never depended on which model
anything ran on. Restated here, in substance verbatim:

**The judge returns a structured verdict, not a text convention.** A scoring harness parses
whatever the judge emits. If the verdict is a phrasing convention, a judge that phrases itself
unexpectedly is mis-parsed — and a mis-parsed verdict does not fail loudly, it produces a
confident wrong number. That is worse than crashing: a crash is noticed, a wrong score is
trusted. Re-deriving the model half of ADR-0005 leaves this argument untouched.

Two smaller carries: `EVAL_JUDGE_MODEL` remains the operator override for the judge, and
judging still costs more per case than the pipeline it grades — paid on eval runs only.

## Consequences

### Accepted

- **Recorded eval verdicts are not independent of the critic's family.** Stated above as the
  narrowing of ADR-0005's claim, printed by record mode, and true of every fixture recorded
  after the cutover. Anyone reading a green replay should read it as "the pipeline said this
  and a same-family judge accepted it", not as an outside opinion.
- **[ADR-0002](0002-separate-critic-node.md) is deliberately not edited.** Its *Known limit* —
  "The critic shares the writer's model" — was true of every configuration that existed when
  it was written, and is now configuration-dependent. The convention in
  [`docs/adr/README.md`](README.md) offers exactly two moves, status-line supersession or a new
  record, and 0002's decision (separate node, notes as sole source of truth) is untouched by
  this phase, so there is nothing to supersede. The one-line residual lives here instead:
  **independence is configuration, and production configures the critic above the writer.**
- **The demo's per-run cost rises on purpose.** An Opus critic puts a typical run at ≈ $0.18
  against the $0.20 admission reservation, which stays flat and stays honest; the revised
  three-critic-call tail at ≈ $0.28 is outside the estimate by design, because `settle()`
  charges the real cost at run end and `AGENT_MAX_RUN_COST_USD` bounds the tail. The thresholds
  that would move the reservation — including `2026-09-01`, when Sonnet's introductory window
  closes and a typical *unchanged* run already reaches $0.21–0.22 — are written in
  `reserved_run_usd`'s docstring and in `docs/OPERATIONS.md`, and pinned by tests.
- **The one committed fixture grades stale in any environment that sets `CRITIC_MODEL`.** The
  replay gate compares the critic role from this phase onward, and `technical-figures.json`
  predates the seam. That is the designed staleness, not a regression; CI is keyless and never
  sets the variable, so offline evals stay 41/41. Re-recording is deferred to the full 40-case
  record run.
- **The judge's own model stays outside the replay staleness gate.** Recorded verdicts are
  fixed data replayed as recorded grades, so pointing `EVAL_JUDGE_MODEL` somewhere new
  invalidates nothing the old judge already said.
- **Either variable restores judge-critic independence.** An operator who wants it back moves
  `EVAL_JUDGE_MODEL` or `CRITIC_MODEL`; nothing here forbids or enforces the collision.

### Rejected alternatives

- **Deleting the judge.** The cheapest answer to "what is the judge for" once its stated
  premise dies. Rejected by the different-job leg: the critic never grades a finished answer
  against the question, and without the judge no recording could ever be refused and no
  replayed assertion would exist.
- **Flipping the judge instead, to preserve judge-critic independence.** Rejected: every
  candidate at or above Opus 5's grading strength is in the same vendor family, so the
  independence bought is nominal, while re-pointing the judge makes future live grades
  incomparable with the recorded ones for no measured gain. Per the phase's own rule, a
  concluded judge change would have been recorded and deferred, not performed here.
- **Forbidding `judge.model == critic_model()` in code.** Rejected: both are operator-controlled
  environment variables and the collision *is* the chosen production configuration. Refusing to
  run would be inventing policy and taking a legal configuration away from the operator; record
  mode states the fact on stderr instead.
- **A model-aware spend reservation** (`reserved = base + critic_premium()`). Considered while
  pricing the Opus critic and rejected: it would make `limits.py` import the price table and the
  graph's configuration in order to sharpen an *admission* estimate by at most $0.13, when
  `settle()` already replaces that estimate with the real cost and the per-run cap already bounds
  the tail. The knob (`DEMO_RESERVED_RUN_USD`) already existed; what was missing was the sentence
  saying when to turn it, which is now written down in two places and pinned by a test.
- **Shipping the capability and deferring the flip.** The research recommendation, and the
  original phase plan. Overruled by the owner's position above: the capability without the flip
  would leave this milestone's second-strongest reversal true only in code, with production
  still running the arrangement the record says was wrong.
