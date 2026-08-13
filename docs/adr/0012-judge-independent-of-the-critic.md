# ADR-0012 — The eval judge is independent of the critic by model identity, and the family residual is stated rather than solved

**Status:** Accepted — supersedes ADR-0010
**Source:** Phase 18 (2026-08-13), `REQ-judge-independent-of-critic`

## Context

[ADR-0010](0010-judge-rederived-for-an-independent-critic.md) answered "with an independent
critic, what is the judge for?" and recorded two positions that are separable. This record
overturns exactly one of them.

**The position being superseded.** ADR-0010 accepted judge-versus-critic independence as
lost, in its own words: *"In production both run on `claude-opus-5`. That is not an
oversight, and it is not merely a configuration an operator could reach: it is the
configuration being shipped, chosen with the consequence in view."* It then stated the
honest consequence — recorded verdicts are independent of the writer's model and not
independent of the critic's — and had record mode print that fact once per run. The
acceptance was correctly reasoned for the options in front of it, and it is the acceptance
this record ends.

**The position left standing.** ADR-0010 also recorded the project owner's stance that the
critic runs on a more capable model than the writer it gates, quoted verbatim there and not
restated here. **Nothing in this record is a judgement about the critic.** `CRITIC_MODEL`
stays `claude-opus-5` in `fly.toml [env]`, Phase 16's cutover is untouched, and the graph is
not edited by the phase that produced this record. A reader who takes this record as
reopening the critic's model has read one leg of ADR-0010 as though it were both.

What changed is not evidence. No measurement here shows ADR-0010's acceptance to have cost
the project a verdict. What changed is that an option exists which the acceptance was the
price of not having: a model the critic does not run on, at least as strong as the writer it
grades, at a rate identical to the judge's current one to every token class. Once the
residual costs nothing, accepting it is no longer a trade.

**This supersession was not forecast.** The three before it were — ADR-0005, ADR-0003 and
ADR-0006 each named the phase that would overturn them in an *Expected reversal* section.
ADR-0010 carries none, because it was written into a register the project was closing. v1.1
closed the reversal register as **spent**; [`docs/adr/README.md`](README.md) said the
remaining expected supersessions described an empty set. **This record reopens that register,
deliberately, and says so here rather than leaving it to be inferred from a table that
quietly grew a row.** The register is this project's mechanism for reversing a stated
position with a record instead of contradicting a paragraph; a reversal that reopened it
silently would defeat the mechanism it used. What a forecast would have supplied in advance —
the reason, the date, and whose decision it was — this record supplies after the fact.

## Decision

**The eval judge runs on `claude-opus-4-8`, a model the critic does not run on. Independence
here means model *identity*, and the family residual is accepted and stated, not solved.**

`JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-4-8")` in `evals/graders.py`,
against a `claude-opus-5` critic and a `claude-sonnet-5` writer. The model that moves in this
phase is the judge's, and only the judge's.

### The residual, in this record's own voice

`claude-opus-4-8` and `claude-opus-5` are the same vendor and the same family. **The
independence bought here is model identity and no more.** A skeptic who argues that two
models of one family share training lineage, and therefore blind spots, still has his
argument after this record, and nothing measured in this project refutes it. Where the critic
waves a blind spot through, a same-family judge may still wave it through.

That is precisely the narrowing ADR-0010 made for the writer — *"Opus 5 and Sonnet 5 are the
same vendor and the same family, so even judge ≠ writer buys family-level independence and no
more"* — and it is repeated here with the same honesty rather than buried under the word
*independent* in this record's title. The title claims model identity because that is what
was bought. Cross-vendor judging would be stronger independence; the harness is
Anthropic-SDK-only, and that stays out of scope for this phase as it was for Phase 16.

The narrowing is now one step tighter than ADR-0010's, and the exact sentence matters: a
verdict recorded after this record is **independent of the writer's model, independent of the
critic's model, and not independent of the critic's family.**

### `claude-fable-5` was offered and declined — the decision, and whose it is

The candidate strictly more capable than the critic was `claude-fable-5`. It was presented at
milestone questioning on **2026-08-13** and **declined by the project owner**, who gave three
reasons:

1. **Roughly twice the judge leg.** $10/$50 per MTok against Opus 4.8's $5/$25 — checked
   against the published price table on 2026-08-13, so the 2× is arithmetic rather than an
   impression.
2. **A 30-day retention requirement** attached to its use.
3. **Hotter refusal classifiers**, so more judge calls would be declined outright.

Reason 1 is verified in this repo's own price table. **Reasons 2 and 3 are recorded as the
decision context he stated, not as measurements this project made.** No Fable judge has ever
run here and no refusal-rate comparison exists in this tree. They are why the decision was
taken, attributed and dated; a later reader who measures them is testing a claim, not
contradicting a finding. This distinction is kept deliberately, because a record that
laundered an attributed reason into an asserted one would be a worse record than one that
gave no reason at all.

`claude-opus-4-8` was chosen instead: independent of the critic by identity, stronger than
the Sonnet writer it grades, and free.

### Zero cost change, and *exactly* zero

| Model | Input | 5m cache write | Cache read | Output |
|-------|-------|----------------|------------|--------|
| `claude-opus-4-8` (the judge, from this record) | $5 | $6.25 | $0.50 | $25 |
| `claude-opus-5` (the judge until this record; still the critic) | $5 | $6.25 | $0.50 | $25 |

Verified against the published pricing page on 2026-08-13. The rows are identical in every
token class, so "zero cost change" is exact rather than approximate, and the standing 40-case
record-run quote is not staled by this record. `usage.PRICES` carries the row, because DEC-12
says an unpriced model fails loud and a judge run landing on `pricing_unknown` would report a
cost that is missing a whole leg.

### The refusal guard is part of the same decision

`Judge.verdict` reads `stop_reason` **before** it reads a single content block. A safety
classifier's refusal is a normal HTTP 200 with `stop_reason: "refusal"` and empty or partial
content; before the guard it surfaced as `ValueError: Judge returned unparseable verdict: ''`
and, through `run_case`'s blanket `except`, as *"the run errored"* — blaming a successful,
paid pipeline run for a decision the judge made. A decline is now a failed grade carrying a
reason that names the judge, flowing into the recorder's existing refusal path, so a fixture
whose judge declined is refused for the right reason and no file is written. Malformed output
still raises; truncation now says so by name.

This belongs in this record rather than beside it, because it is **not a property of which
model the judge runs on**. It was a latent defect while the judge was on Opus 5, it is a
latent defect on Opus 4.8, and it would have been loudest on the declined candidate. Choosing
a judge and leaving its declines mislabelled would have been choosing where to be wrong.

### Carried forward from ADR-0010

Superseding 0010 must not silently discard the parts of it that never depended on which model
the judge ran. These survive in full:

- **The different job.** The critic gates *drafts* against *notes*, inline, inside the graph,
  shaping what ships. The judge grades *finished answers* against the *question and a rubric*,
  retrospectively, across the golden set, never on user traffic. That distinction holds
  whatever either one runs on, and it — not any model choice — is why the judge exists.
- **The judge must not run on the *writer's* model.** ADR-0010's hard requirement, pinned by
  a test, and untouched: `claude-opus-4-8` ≠ `claude-sonnet-5`. This record tightens a
  preference; it does not relax a requirement.
- **The critic above the writer.** The owner's position and Phase 16's production cutover,
  both intact. This record's phase edits neither `fly.toml` nor the graph.
- **The structured verdict, and the fail-loud parse.** A harness that mis-parses a verdict
  does not crash, it produces a confident wrong number, and a wrong score is trusted where a
  crash is noticed. This record extends that argument rather than touching it: the refusal
  guard closes the one remaining path where a decline could be scored as a malformation.
- **`EVAL_JUDGE_MODEL` remains the operator override**, and "stronger" remains a *preference*
  for the judge rather than a requirement. An operator pointing it somewhere cheaper trades
  grading sharpness for money and violates nothing.
- **ADR-0010's own supersession of ADR-0005 stands.** 0005 is still superseded by 0010, and
  what survived of 0005 is still recorded in 0010's *Carried forward from ADR-0005* section.
  This record does not reach past 0010.

Per the convention in [`README.md`](README.md), only ADR-0010's status line changes. Its
Context, Decision and Consequences stay exactly as written, including the acceptance this
record ends — that is the point of keeping it.

## Consequences

### Accepted

- **A recorded verdict is independent of the critic's model and still not independent of its
  family.** Stated above, and true of every fixture recorded after this record. Anyone reading
  a green replay should read it as *"the pipeline said this, and a different-model,
  same-family judge accepted it"* — better than what ADR-0010 could offer, and still not an
  outside opinion.
- **The reversal register is no longer spent.** `.planning/ROADMAP.md` carries the reopening
  as a row and `docs/adr/README.md`'s counting prose is re-derived in the same commit as this
  record, so no surface is left claiming an empty set. A future reader counting supersessions
  finds four, one of them unforecast and saying so.
- **Verdicts recorded before and after this record come from two different judges.** The one
  committed fixture's verdicts were produced by `claude-opus-5` on 2026-08-10 and the 40-case
  record run will be produced by `claude-opus-4-8`. The full run is sequenced after this phase
  for exactly that reason: the recorded set should be made under the settled judge, not
  straddle the change.
- **The committed fixture does not stale, and the reason is structural rather than lucky.**
  `grade_fixture_current` compares the pipeline and critic roles and deliberately never the
  judge — recorded verdicts are fixed data replayed as recorded grades, so re-pointing the
  judge invalidates nothing the old judge already said. `evals/fixtures/technical-figures.json`
  still records `"judge": "claude-opus-5"`; that is a true record of which model produced
  those verdicts, correct as written, and must not be "fixed". Offline evals stayed 41/41
  across the flip.
- **An operator can still put the two models back on one name.** `EVAL_JUDGE_MODEL` or
  `CRITIC_MODEL` reaches the arrangement ADR-0010 shipped, and nothing here forbids it. What
  inverts is the *premise* of the record-mode line that states the collision: at the shipped
  defaults there is no collision to state, so the line now describes a configuration the
  operator created rather than the one the project deployed.
- **Zero cost change.** By the price identity above, no cost estimate, reservation or quote
  moves because of this record.

### Rejected alternatives

- **`claude-fable-5`.** The strictly-more-capable option, which would have bought independence
  from the critic's *family* as well as its identity. Presented and declined by the project
  owner on 2026-08-13 for the three reasons above, one verified and two attributed. Recorded
  as his decision, not as a conclusion the evidence forced — the evidence assembled for this
  phase did not force either answer.
- **Leaving the judge on the critic's model and stating the correlation harder.** ADR-0010's
  move, and the right one while the residual was the price of something. It stopped being the
  right one when an equally strong, identically priced model the critic does not run on was
  available: at that point the acceptance buys nothing and narrows the one claim the eval
  suite exists to make.
- **Forbidding the collision in code.** Rejected again, and for ADR-0010's reason, restated
  because the flip makes it newly tempting: both models are operator-controlled environment
  variables, and refusing to run would invent policy and take a legal configuration away from
  the operator. Record mode states the fact instead.
- **Re-recording the one committed fixture under the new judge as part of this phase.**
  Rejected: the staleness gate never compared the judge role, the recorded verdicts are not a
  comparison input, and spending a paid run to change a model name in data nothing reads that
  way would buy nothing. Recording is deferred to the full 40-case run.
- **Cross-vendor judging.** The strongest independence available and out of scope: the harness
  is Anthropic-SDK-only. Named here so the family residual has a known price rather than
  looking like an oversight — especially in a record whose title claims independence.
