# Phase 18: Independent eval judge - Context

**Gathered:** 2026-08-13
**Status:** Ready for research
**Source:** Milestone-questioning decisions (user-ratified 2026-08-13 at v1.2 start) plus
the same-day code investigation. No separate discuss-phase round — the phase's open
questions were answered when the milestone was scoped, which is stronger sourcing than
orchestrator calls: the judge-model choice was an explicit AskUserQuestion answer.

<domain>
## Phase Boundary

The eval judge becomes independent of the critic: `EVAL_JUDGE_MODEL` defaults to a model
that is not the critic's, a judge refusal surfaces as a graded finding rather than a
misleading parse error, the price table can cost a judge run, and ADR-0012 records the
supersession of ADR-0010.

**Not in this phase:** recording the 40 cases (Phase 21 — sequenced after this phase
precisely so verdicts are recorded under the settled judge); any change to the critic
(`CRITIC_MODEL` stays `claude-opus-5` in production); any change to what the offline
suite claims (ADR-0009's boundaries are untouched).

</domain>

<decisions>
## Implementation Decisions (user-ratified at milestone questioning)

### The judge model is `claude-opus-4-8` — decided, not open

- Chosen over Fable 5 explicitly: independent of the Opus 5 critic, stronger than the
  Sonnet 5 writer it grades, **zero cost change** ($5/$25 per MTok, same as today's
  judge). The Fable option (strictly more capable than the critic, ~2× judge leg,
  30-day-retention requirement, hotter refusal classifiers) was presented and declined.
- The known residual is accepted and must be stated in ADR-0012 rather than papered
  over: Opus 4.8 is the critic's model *family*; a family-correlation skeptic's argument
  survives. Independence here means model identity, exactly the narrowing ADR-0010 made
  for the critic — the record must say so with the same honesty.

### The refusal guard is in scope regardless of model

- `Judge.verdict()` (evals/graders.py:733) reads `response.content` without checking
  `stop_reason`. A safety-classifier refusal is HTTP 200 + `stop_reason: "refusal"` +
  empty or partial content — today that surfaces as `ValueError: Judge returned
  unparseable verdict`, blaming the parse when the model declined. This is a latent bug
  on Opus 5 *now*, not a Fable-only concern.
- A refused verdict must be distinguishable from a malformed one downstream: the
  recorder already refuses fixtures whose judge failed; a refusal should flow into that
  same refusal path with an honest reason, never be retried into silence.

### ADR-0012 supersedes ADR-0010, with ceremony

- v1.1 closed the reversal register as **spent**. This phase deliberately reopens it,
  and ADR-0012 must state that plainly — the register convention is the project's
  mechanism for reversals-with-a-record, and reopening it quietly would defeat it.
- ADR-0010's two positions must be handled separately: "critic stronger than writer" is
  untouched (the critic doesn't change); "judge == critic is an acceptance" is the part
  being superseded. ADR-0010 itself is not edited (the 16-02 convention: records are
  history).

### Price table

- `usage.PRICES` gains a `claude-opus-4-8` row ($5/$25; cache rates as the documented
  1.25×/0.1× of base input, consistent with the existing cache-rate pin test). Without
  it a judge run lands on `pricing_unknown` — DEC-12 says that fails loud, which would
  make every `--live`/`--record` run fail loudly the day the default flips.

### Claude's Discretion

- Whether the refusal guard returns a structured refusal object or raises a typed
  exception — pick what composes best with the existing grader/recorder refusal path.
- Test structure and mutation-probe selection, per the house discipline (every gate
  observed red before trusted).
- Whether `EVAL_JUDGE_MODEL` env override behavior needs additional pinning beyond what
  exists.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The record being superseded
- `docs/adr/0010-judge-rederived-for-an-independent-critic.md` — the two positions, only
  one of which is superseded; the honesty conventions ADR-0012 must match
- `docs/adr/README.md` — the supersession convention and the reversal-register language
  ("remaining expected supersessions" currently describes an empty set — this changes)

### The surfaces being changed
- `evals/graders.py` — `JUDGE_MODEL` (line 33), `Judge.verdict()` (line ~733, the
  missing stop_reason guard)
- `src/research_agent/usage.py` — `PRICES` table; cache-rate relationship pinned in
  `tests/test_usage.py::test_cache_rates_are_multiples_of_the_input_rate`
- `evals/fixtures.py` / `evals/__main__.py` — the recorder's existing refusal path the
  guard must compose with; the record preview's judge-leg pricing

### Milestone framing
- `.planning/REQUIREMENTS.md` — REQ-judge-independent-of-critic and the framing section
  (ordering constraint, acceptance bar: no successor limitation)

</canonical_refs>

<specifics>
## Specific Ideas

- The README Limitations bullet ("The eval judge shares the critic's model") is deleted
  by Phase 22, not this phase — but this phase must update every *other* doc surface
  that asserts judge == critic (DESIGN.md, OPERATIONS.md's record-mode warning from
  16-02, the collision-warning stderr line and its tests) so Phase 22's pass finds no
  contradictions. The 16-02 lesson applies: the operator-facing collision warning fires
  on configuration, and judge ≠ critic in production means the warning's premise
  changes — check whether it still fires, and what it should now say.
- `grade_fixture_current` compares pipeline and critic models, NOT the judge — a judge
  change does not stale the one committed fixture. State this in the phase records
  rather than leaving it folklore (the 15-03/16-02 pattern).

</specifics>

<deferred>
## Deferred Ideas

- Recording the 40 cases — Phase 21, by roadmap dependency.
- Any critic-side change — out of milestone scope entirely.

</deferred>

---

*Phase: 18-independent-eval-judge*
*Context gathered: 2026-08-13 from milestone-questioning decisions + session investigation*
