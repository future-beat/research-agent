# Phase 15: Answer-quality evals - Context

**Gathered:** 2026-08-06
**Status:** Ready for research
**Source:** Routine orchestrator calls (standing "proceed without a question round"
preference). Revisable at plan review; not user-ratified.

<domain>
## Phase Boundary

Answer quality becomes measurable without billing every push, and the live case set grows
past 12 to a size defensible as a benchmark. The every-push CI gate stays offline,
deterministic, and keyless.

**Reversal in tension with DEC-20.** DESIGN.md argues offline evals *should not* claim to
grade quality, and prints that caveat every run, because "a green suite that quietly implies
'the model is good' is worse than no suite." The replacement guarantee this phase must
decide and record (new ADR — DEC-20 was never promoted, so `Status: Accepted` + `Source:`
line, the 0008 precedent): **what the suite is now allowed to claim, and how the caveat
changes to stay honest.**

Ordered before Phases 16 and 17 on purpose: those change what the pipeline *says*; without
a quality measure first, their effect is unobservable.

</domain>

<decisions>
## Implementation Decisions (orchestrator calls — confirm at plan review)

### The quality mechanism: recorded-response replay, graded deterministically

- **Record real pipeline runs once (a deliberate, paid, operator-triggered act), commit the
  recorded transcripts as fixtures, and grade answer quality offline against them** —
  deterministic quality graders (grounding-against-notes, citation presence, structure,
  question-coverage) that run free on every push.
- Why this over the alternatives: a scheduled live job spends money unattended and fails on
  provider outages CI can't control (the Out of Scope table already rejects live-key CI); a
  judge-only approach isn't deterministic; reference answers rot as models change, but
  *recorded* answers are exactly what the pipeline actually said, so grading them measures
  the pipeline's real output rather than resemblance to a stale ideal.
- **What this can and cannot claim** (the ADR's core): the offline suite measures the
  quality of *recorded* answers — grounding, structure, coverage — deterministically. It
  cannot claim the CURRENT model produces those answers; only a fresh live run can. The
  caveat rewrites to say exactly that, and the recording's date/model must print with every
  offline grade so staleness is visible, not implied away.
- **The LLM judge stays live-only** (Opus 5, `EVAL_JUDGE_MODEL`), still the stronger-model
  backstop for the live run. Phase 16 will re-derive its rationale; do not pre-empt that
  here — but the judge's verdicts on recorded answers MAY be recorded alongside them as
  fixture metadata (graded once, replayable free).

### The live set grows to a defensible benchmark

- **Target: 40 live cases** (from 12). Defensible means: covers the routing taxonomy
  (technical / contested / ambiguous / low-info at minimum), includes follow-up cases (the
  Phase 17 change needs before/after evidence), includes adversarial/injection cases (the
  Phase 12 note-scoping lesson), and each case states what it exists to catch.
- The researcher should propose the taxonomy split and confirm 40 is affordable as an
  operator-triggered run (~cost estimate printed before the run, per the Phase 13/14
  preview idiom).

### CI invariants that must not move

- `ANTHROPIC_API_KEY=""` stays a CI invariant — the offline suite runs keyless,
  deterministic, free, on every push. Breaking that is the reversal DEC-20 warns about.
- The existing 12 offline behavioural cases keep passing; quality grading is additive.

### Post-research calls (2026-08-06, researcher recommendations adopted)

- **Replay is automatic in offline mode** — the CI command stays unchanged; recorded-answer
  quality grading simply joins the keyless run.
- **Replay shares `--min-pass-rate 0.9`** with the behavioural cases.
- **Recorded judge verdicts are a HARD replay gate** — the recorder refuses to write a
  fixture whose live judge verdict failed, so a fixture in the repo is by construction one
  the judge approved; replay asserting that stays true is deterministic.
- **Staleness: age PRINTS, model-mismatch GATES.** An age-based failing grader would make
  the same commit pass in August and fail in October — nondeterministic by calendar. The
  caveat prints recording date/model/sha/age; the hard deterministic gate is
  `fixture.model != graph.MODEL`, which fires exactly when a code change invalidates the
  recordings (including Phase 16's model change — deliberate, and a feature).
- **Dataset gap confirmed:** no golden case exercises `no_prior_research` today. The 40-case
  split closes it; adversarial cases use a `seeded_notes` mechanism (poisoned note
  pre-loaded into the case's own store, per Phase 12's lesson).
- **Recording cost is real money: ~$10–16 at intro pricing (~$14–22 from 2026-09-01)**,
  verified against usage.py. Mandatory one-case calibration run first; runtime preview via
  `price_for()`; never a hardcoded figure. The full 40-case record run is an operator
  decision at execution time.

### Out of scope — explicitly

- Changing the judge model or the critic (Phase 16).
- Follow-up live search (Phase 17) — but the benchmark must include follow-up cases so 17
  has a before/after measure.
- Any CI step that needs a live API key (standing Out of Scope table entry).

### Claude's Discretion

- Fixture format and location; how recordings are versioned and refreshed; grader rubric
  details; how the cost preview composes with the existing eval harness CLI.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` § Phase 15 — four success criteria, the DEC-20 tension
- `.planning/REQUIREMENTS.md` — REQ-offline-eval-quality
- `.planning/intel/decisions.md` — DEC-20 (and DEC-22, the judge — do not pre-empt Phase 16)
- `evals/` — `dataset.py` (the 12 cases), `graders.py` (deterministic + judge), `harness.py`,
  `__main__.py` (the CLI and the printed caveat)
- `src/research_agent/graph.py` — what a run's state carries (notes, draft, trace) — the
  recording must capture enough to grade grounding
- `docs/adr/README.md` — ADR convention; ADR-0009 lands here
- `.github/workflows/ci.yml` — the evals job and its `ANTHROPIC_API_KEY=""` invariant

</canonical_refs>

<specifics>
## Specific Ideas

- State of the world: main at PR #8 merge; suites plain 563/65, armed 627/1; local PG on
  :54329 running; release v9 live (phases 13–14 ship with the next deploy).
- **Gate discipline: SIXTEEN vacuous gates across seven phases.** Run `--collect-only` on
  every selector before trusting it. Measured baselines + mutations observed red (or honest
  green with the reason). Plan-specified arithmetic and file paths have been wrong three
  times in one phase — executors trust the code and say so.
- README is a per-phase deliverable: the "Offline evals can't measure answer quality, and
  twelve live cases are a smoke test, not a benchmark" limitation is this phase's to
  rewrite honestly. No `model=` overrides on spawned agents.
- One PR for the whole phase.

</specifics>

<deferred>
## Deferred Ideas

- Invoice reconciliation, `/health` validity probe, CSP header (standing deferred list).
- Automated periodic re-recording of fixtures (an operator act for now).

</deferred>

---

*Phase: 15-answer-quality-evals*
*Context recorded: 2026-08-06 — orchestrator calls, to be confirmed at plan review*
