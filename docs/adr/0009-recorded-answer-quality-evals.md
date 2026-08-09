# ADR-0009 — Answer quality is graded from recorded runs, and never claimed of the current model

**Status:** Accepted
**Source:** Phase 15 (2026-08-10), `REQ-offline-eval-quality`; supersedes the scope of
`DEC-20` in [`.planning/intel/decisions.md`](../../.planning/intel/decisions.md)

## Context

**DEC-20 said the offline suite may not speak to answer quality, and made the CLI print that
under every run.** The decision is quoted in [`docs/DESIGN.md`](../DESIGN.md) § Testing and its
argument is the part worth preserving: offline runs replace the API with a scripted client
whose output is *authored in the dataset*, so a green suite says the graph routed correctly,
both guardrails fired, follow-ups stayed isolated and an unapproved draft was never returned
as approved — and says nothing whatsoever about the model. Hence the rule it closed with:
**"a green suite that quietly implies 'the model is good' is worse than no suite."**

That was true because the answers were ours. `REQ-offline-eval-quality` asks for a measure of
answer quality that does not bill every push, which forces the question DEC-20 never had to
answer: *whose* answers is the suite grading, and what may it claim about them?

The mechanism this phase built is recording. A deliberate, paid, operator-triggered run drives
the **shipped graph** against a real API, captures each turn's final `AgentState`, has the live
judge grade it, and — only if every grader and every judge verdict passed — writes a committed
JSON fixture. Every push then replays those fixtures keylessly and grades them again with
deterministic rubrics. The answers are no longer ours. They are the pipeline's, from a stated
date, on a stated model, at a stated commit.

That does not make DEC-20 wrong. It makes DEC-20's claim *narrower than it needs to be* and its
caveat *less precise than it can now afford to be*. The suite still cannot say the current model
is good. It can now say, deterministically and for free, that the answers the pipeline actually
produced on 2026-08-10 were grounded in their own notes, on the question asked, shaped like
reports, and honest when they had to refuse. Those are different sentences, and the whole point
of this record is to keep them apart.

**Honest scale note.** One case of forty is recorded as this ships. The machinery is proven end
to end by real spend, not by fakes; the coverage is not. What that means for each claim is
stated in Consequences rather than left for a reader to assume.

## Decision

**Offline runs grade recorded answers, and every claim they make is stamped with the recording's
date, model and commit.** Recording is an operator act; replay is automatic, keyless and free.

### What survives of DEC-20

**The caveat still prints on every offline run — upgraded, never removed.** With no recordings
it prints DEC-20's own line verbatim, because a run that graded no answers must not hint that it
graded some:

> offline mode grades the pipeline, not the model — run with `--live` to measure answer quality

With recordings it prints what was graded and how old it is:

> offline mode grades the pipeline, plus answers recorded {date} on {model} ({sha}, {age} days
> ago) — that grades what the pipeline said then, **not what the current model would say**; run
> with `--live` to measure that

**The suite still never claims the current model is good.** The clause carrying that is not
decoration; it is the exact boundary this record exists to draw.

**Free, deterministic, keyless on every push is untouched.** `ANTHROPIC_API_KEY: ""` remains a CI
invariant and `.github/workflows/ci.yml` has zero diffs across this phase. The replay path
constructs no client, opens no store and reads no clock for any verdict.

**The judge stays live-only.** Its verdicts on a recording are captured as fixture metadata and
replayed as fixed data; no judge call happens offline, ever. Phase 16 owns the judge's rationale
and this record deliberately says nothing more about it.

### What is new

**The suite may now claim, of RECORDED answers only, that they are grounded, on-question,
well-formed and honest about refusals.** Each of those words is a specific mechanical check with
a specific blind spot, and both columns are load-bearing. They are reproduced here from the
graders' own docstrings, which a test asserts exist — the claim boundary is machine-checked, not
a promise made in a document.

| Grader | What it can claim | Cannot catch |
|--------|-------------------|--------------|
| `recorded_grounding` | every figure in the answer — money, percentages, decimals, large counts, years, ISO dates — appears in that run's notes or in the question | paraphrased fabrications; negation flips ("X does not support Y" when the notes say it does); misattribution between two entities both in the notes; wrong causal claims assembled from grounded nouns; bare counts of ten or less; factual wrongness of the notes themselves. **And a figure reused in another role** — see below |
| `recorded_coverage` | at least 40% of the question's content words appear in the answer, so the report is about what was asked | an on-topic non-answer; a report *about* the question rather than an answer to it; an answer that covers the subject and gets it wrong. Word overlap is not comprehension |
| `recorded_structure` | the answer opens with a markdown heading and occupies 200–8000 characters | well-formed nonsense. Every failure this phase exists for — fabrication, evasion, confident wrongness — arrives correctly shaped |
| `recorded_refusal` | an unanswerable follow-up admits the gap in so many words **and** introduces no figure the notes never had | a novel refusal phrasing, which fails until `REFUSAL_PATTERNS` grows; a hedged half-answer whose fabrications are not token-shaped ("industry consensus expects rapid growth") |
| `case_pins` | the hand-authored `must_mention` / `must_not_claim` substrings hold — the only deterministic hook for "presents disagreement as disagreement" or "the injection payload never reached the answer" | anything nobody wrote down; and by design it over-fits the recording it was authored against |

**"A figure reused in another role" is the sharpest of these, and only a real recording could
have found it.** Grounding is set containment, and normalisation deliberately erases the form
that carried a figure's role. Measured on the first real recording (`technical-figures`,
2026-08-10): one aside in the notes mentions "the earlier 3.x/4.0 model generations", `4.0`
normalises to `4`, and that grounds a draft restating Sonnet 5's `$2` introductory input price
as `$4`. A fabricated price, green, because a version number three paragraphs away was the same
digit. The gap is **role, not magnitude** — the same recording reds immediately on
73.3% → 81.9% and 1M → 3M, figures the notes carry in no role at all. A document mixing
versions, prices, percentages and years has a dense number space, and every collision in it is a
fabrication this grader passes. It is pinned by a test asserting both directions, so a future
change that closes it must come back to this record and say so.

### The staleness mechanism

A recording describes a pipeline that existed once. Two different questions follow from that,
and they get two different mechanisms on purpose.

**Model mismatch GATES.** `grade_fixture_current` compares the fixture's `models.pipeline`
against `graph.MODEL`; a mismatch fails replay, and the exit rule makes any red or errored
replay result exit non-zero regardless of the shared pass rate. It fires exactly when a code
change invalidates the recordings, and never otherwise.

**Age PRINTS and never grades.** An age-based failing grader would make the same commit pass in
August and fail in October — nondeterministic by calendar, which is the property the whole
offline leg is built on. Age lives in the caveat and in the report, never in a `Grade`. A test
replays a fixture dated 2019 against a fresh one and asserts byte-identical grades.

**The recorder refuses a red recording.** A fixture whose own graders or judge verdicts failed is
not written (`--force` writes it and stamps `forced: true`). So a fixture in the repo is by
construction one the graders and the judge approved, which is what makes replay's later assertion
a gate rather than a restatement of whatever happened to be recorded.

### The staleness gate's own claim boundary

The graders carry "Cannot catch:" lines; the gate deserves one too, and it is not the line the
mechanism's name suggests.

**`grade_fixture_current` cannot catch a change to any model the map does not compare.** It reads
`models["pipeline"]` against `graph.MODEL` — the writer/researcher model — and nothing else.
Phase 16 makes the **critic's** model configurable *independently of* `graph.MODEL`, so a
critic-model change **will not fire this gate**: the recordings stay green, describing a pipeline
that no longer exists, with only the printed recording date hinting at it. Closing that needs
three things together — a per-node entry in the fixture's `models` map, the gate extended to
compare it, and the fixtures re-recorded. The map is a map rather than a flat model string
precisely so that extension is additive instead of a schema bump.

## Consequences

### Accepted

- **The fixture set's coverage is a spend decision, not an architectural one.** One case of forty
  is recorded as this ships; the other thirty-nine cases run offline against authored answers, as
  they always did. The replay leg grades whatever exists and zero fixtures is a legal, green
  state — so the README states the count rather than implying the benchmark is recorded. Nothing
  in this record changes if that count moves.
- **The quality thresholds have met exactly one real report.** `COVERAGE_THRESHOLD = 0.4` and
  `REPORT_MIN_CHARS = 200` were set against scripted two-sentence stubs, then measured against the
  first real recording: coverage 75%, length 2,594 characters, grounding clean across 28 extracted
  figures. Comfortable margins on one sample. Neither number has been moved, and neither has been
  validated across the taxonomy.
- **A recorded fixture is a claim about a moment, and pins authored against it inherit that.**
  `case_pins` over-fits by design. Re-recording without re-reading the pins leaves assertions
  about a run that no longer exists — stated in the grader's own docstring, where the cost is
  paid.
- **`REFUSAL_PATTERNS` is a maintenance cost with a name.** An honestly-refusing answer worded
  outside the list fails until the list grows. Deliberate: a pattern that matched anything would
  pass a refusal that never came.
- **Recording spends real money and is never automated.** The preview quotes from the same
  effective-dated rate tables the invoice uses, `--yes` is required before an API client is even
  constructed, and no scheduled job exists. The quote is an estimate calibrated against one
  measured case, and it says so.

### Rejected alternatives

**A scheduled live job that grades the current model.** It is the direct answer to "is the model
good today", and it is rejected on two grounds the Out of Scope table already carries: it spends
money unattended, and it fails on provider outages CI cannot control. A red build that means
"Anthropic had a bad afternoon" teaches people to ignore red builds.

**Judge-only grading.** The judge is the strongest evaluator here and it is not deterministic:
the same commit could pass and fail on consecutive pushes. Determinism is the property that makes
an every-push gate worth having, so the judge grades once, at recording time, and its verdict is
replayed as fixed data.

**Reference answers to compare against.** Written once and rotting from the moment a model
changes, they measure resemblance to a stale ideal. A *recorded* answer is exactly what the
pipeline said, so grading it measures the pipeline's real output — and when it goes stale the
model-mismatch gate says so out loud instead of leaving a slowly-drifting similarity score to be
interpreted.
