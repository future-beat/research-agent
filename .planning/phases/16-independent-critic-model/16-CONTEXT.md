# Phase 16: Independent critic model - Context

**Gathered:** 2026-08-10
**Status:** Ready for research
**Source:** Routine orchestrator calls (standing "proceed without a question round"
preference). Revisable at plan review; not user-ratified.

<domain>
## Phase Boundary

The critic becomes separately configurable from the writer/researcher model, cost
accounting prices each node's model correctly, the spend cap accounts for a costlier
critic path, and the eval-judge choice is **re-derived from scratch** — superseding
ADR-0005 rather than inheriting "Opus 5 because the critic is weak."

**Second-strongest reversal in the milestone.** The shared critic model was not
accidental: it is the explicit justification for the stronger eval judge (ADR-0005, and
the README sentence "The eval judge runs on a stronger model precisely because of this").
Removing the premise removes the reason — so the judge decision must be answered fresh:
with an independent critic, what is the judge *for*?

</domain>

<decisions>
## Implementation Decisions (orchestrator calls — confirm at plan review)

### `CRITIC_MODEL`, defaulting to the writer's model

- New env var `CRITIC_MODEL`; when unset, the critic runs on `MODEL` exactly as today —
  a **neutral default**, so deploying this phase changes nothing until an operator sets
  it. Setting it is the operator act that makes the critic independent.
- Rationale: the phase's deliverable is the *capability* and its accounting, not a forced
  model flip. This mirrors Phase 13 (the path, not the migration) and keeps the demo's
  cost profile unchanged until deliberately changed.
- The production flip (actually setting `CRITIC_MODEL` on Fly) is an operator decision at
  execution time — the live verification can demonstrate it on a scratch basis if cheap,
  or defer; the plans must state which happened.

### Per-node model threading

- `call_model` (or its call sites) carries the model per node. The critic call site reads
  `critic_model()`; every other node reads `MODEL` unchanged. One choke point per concern:
  model *selection* happens at the call site, cost attribution stays in
  `CallUsage.cost_usd` (Phase 14's single multiplication point) — which already prices by
  the model named in the response, so verify that per-call model attribution genuinely
  flows through rather than assuming.
- `pricing_unknown` fires for a critic model with no price row (DEC-12; Phase 14's SC-2
  wording anticipated exactly this).

### The judge, re-derived (ADR-0010's core)

- The question to answer from scratch: with an independent critic, what is the judge FOR?
  The researcher must draft the candidate answers with evidence (e.g.: the judge grades
  *answers* against a rubric while the critic gates *drafts* against notes — different
  jobs regardless of models; independence from BOTH pipeline models still matters so the
  judge isn't grading its own family's output; "stronger" may survive as a preference but
  cannot survive as the *reason*).
- ADR-0010 supersedes ADR-0005 per the convention (status-line edit on 0005; carry-forward
  of whatever survives). The index's pre-named forecast (Phase 16 → ADR-0005) lands here.
- The README sentence dies with the premise — and per the standing instruction, the
  "critic shares the writer's model" limitation is **deleted**, not rewritten; any genuine
  residual (e.g. "independence is configuration, not default") gets one short sentence.

### Phase 15's fixture gate must be extended, not discovered

- Fixtures record a models MAP precisely because this phase was coming. The map gains a
  `critic` entry; `grade_fixture_current` compares it; the one recorded fixture becomes
  stale by construction when the gate extends — **that is the designed behaviour**, and
  the honest handling (re-record the calibration case, or the gate reports it stale) must
  be decided in-plan, not improvised.

### Spend cap accounting

- The $0.20 reservation estimate assumed a uniform-model run. With a costlier critic the
  researcher must re-check the arithmetic (revisions multiply critic calls) and either
  confirm the estimate stays honest or make it model-aware. The global cap semantics do
  not change.

### Post-research calls (2026-08-10, researcher findings adopted)

- **CONTEXT's attribution premise was FALSE — corrected.** `CallUsage.from_response` never
  reads `response.model`; `call_model` passes the module constant `MODEL` into `record()`
  (graph.py:103). Only `inference_geo` is response-observed. The model name must be
  threaded through FOUR sites (span :96, API call :99, record :103, log :111) or a
  mis-threaded critic silently misbills. The discriminating test: `CRITIC_MODEL` set to an
  unpriced name fires `pricing_unknown` ONLY if the threaded name reached `record()`.
- **No PRICES additions needed:** `claude-opus-5` ($5/$25) and `claude-haiku-4-5` ($1/$5)
  already have rows, verified against live docs. Both are UNDATED windows — use them in
  exact-cost tests; Sonnet's 2026-08-31 boundary makes it unusable for exact assertions.
- **Reservation: keep flat $0.20 + documented threshold** (Phase 14's cap-note idiom).
  Opus-critic typical run ≈ $0.18; 3-critic-call worst case ~$0.28 is by-design outside the
  estimate (settle is real-cost; the per-run cap bounds the tail). Orthogonal finding: the
  Sept-1 Sonnet boundary ALONE lifts a typical run to ~$0.21–0.22 — the estimate breaks
  with no critic change; document that with the threshold.
- **Fixture gate: backfill semantics** — `models.get("critic") or models["pipeline"]` in the
  gate, honest because the one fixture's critic ran on `graph.MODEL` by construction.
  Offline stays 41/41 keyless with CRITIC_MODEL unset; goes stale correctly the moment an
  operator sets it. New `graph.critic_model()` accessor serves both the node and the gate.
  Re-recording the calibration fixture is DEFERRED to the full record run.
- **ADR-0010 shape:** "different job" survives on its own legs; independence re-targets to
  "judge ≠ writer's model" (already pinned at test_evals.py:464) with judge-vs-critic as a
  recorded known limit; "stronger" survives as preference only; the structured-verdict half
  of ADR-0005 carries forward. Do NOT edit ADR-0002. DESIGN.md:74 gets a one-line forward
  reference. A stderr warning fires in record mode when `judge.model == critic_model()`.
- Stale-prose inventory to fix in-phase: README:252 (delete the limitation), graders.py:13-17,
  DESIGN.md:74, the harness docstring (which has a content-pinning test at test_evals.py:1655).

### USER DECISION (2026-08-10) — the critic runs on Opus. This supersedes the deferral.

- **Hesam's call, verbatim rationale: "Use Opus as the critic's model since it has to be
  more capable than the writer's model."** `CRITIC_MODEL=claude-opus-5` in production.
- **Code default stays neutral** (unset → writer's model) so tests, CI and keyless contexts
  are unchanged; production sets `CRITIC_MODEL = 'claude-opus-5'` in `fly.toml [env]` — it
  is configuration, not a secret, and committing it makes the stance visible.
- **The production flip IS this phase's deliverable now.** It requires a deploy; that deploy
  is the first since v9 and therefore carries phases 13–15's pending changes — one cutover,
  planned as the wave-4 checkpoint, with the post-deploy smoke phases 14–15 booked.
- **Consequences to record rather than discover:**
  - `judge.model == critic_model()` — the collision warning fires on the CHOSEN config.
    Keep the warning but word it as stating a fact, not implying a mistake; ADR-0010
    records the acceptance: the judge is independent of the WRITER, and deliberately
    shares the critic's model — its verdicts are not independent of the critic's family.
  - The critic-stronger-than-writer stance is a NEW design position ADR-0010 must state
    (it is Hesam's rationale, not an inference).
  - Cost: Opus-critic typical run ≈ $0.18 (reservation $0.20 still honest; the documented
    thresholds stand). The demo's per-run cost rises deliberately.
  - The live demonstration uses **Opus** (the real config), not haiku; haiku remains in
    unit tests for the undated-row arithmetic.
  - Replay/evals stay green: CI runs keyless with CRITIC_MODEL unset; the recorded
    fixture's backfilled critic matches. The caveat already prints the recording's models.

### Out of scope — explicitly

- Follow-up live search (Phase 17).
- Changing the WRITER's model, or any default model flip.
- Judge model changes beyond re-deriving the rationale (if the re-derivation concludes the
  judge should change, record it as the ADR's consequence and defer the flip).

### Claude's Discretion

- Env var parsing/validation idiom (match `usage.py`/`limits.py` conventions); how the
  critic model surfaces in `/health` or `/pricing` if at all; test structure.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` § Phase 16 — five criteria, the reversal note
- `.planning/REQUIREMENTS.md` — REQ-independent-critic-model
- `docs/adr/0005-opus-5-eval-judge.md` — the record being superseded; `docs/adr/0002-…`
  (critic node) links to it; `docs/adr/README.md` — the convention and the pre-named
  forecast
- `src/research_agent/graph.py` — `MODEL`, `call_model`, the critic node, per-node
  thinking/output config
- `src/research_agent/usage.py` — `CallUsage.cost_usd`, PRICES (does it carry rows for
  candidate critic models?), Phase 14's multipliers
- `src/research_agent/limits.py` — `DEMO_RESERVED_RUN_USD` and the reservation math
- `evals/graders.py` — `JUDGE_MODEL`; `evals/fixtures.py` — the models map;
  `evals/harness.py` — replay's `grade_fixture_current`
- `evals/fixtures/*.json` — the one recorded fixture that goes stale when the gate extends

</canonical_refs>

<specifics>
## Specific Ideas

- State of the world: main past PR #10; suites plain 663/65, armed 727/1, offline evals
  41/41 keyless; release v9 live (phases 13–15 ship with the next deploy); local PG on
  :54329 (restart with `LC_ALL=C` if down).
- **Gate discipline: SIXTEEN vacuous gates across seven phases.** `--collect-only` every
  selector; measured baselines; discriminating mutations or honest green with the reason.
  Every wave of 15 found a mutation the tests couldn't discriminate — keep asking.
- README: whole-file pass, and the addressed limitation is DELETED (standing instruction,
  corrected twice — grep for facts that live only in deleted prose first).
- One PR for the whole phase; execute all waves in one go (standing instruction).

</specifics>

<deferred>
## Deferred Ideas

- The full 40-case record run (still deferred from Phase 15; re-recording the calibration
  case with the extended models map may happen here if the gate design requires it).

</deferred>

---

*Phase: 16-independent-critic-model*
*Context recorded: 2026-08-10 — orchestrator calls, to be confirmed at plan review*
