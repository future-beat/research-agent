# Phase 16: Independent critic model - Research

**Researched:** 2026-08-10
**Domain:** Per-node model configuration, per-model cost attribution, ADR supersession, eval fixture staleness
**Confidence:** HIGH (nearly everything verified by reading the code in this tree; pricing verified against the live docs page)

## Summary

The phase is smaller in code than it looks and larger in verification than it looks. The
entire model path runs through one function — `graph.call_model` — which names the model
in **four places** (the API call, the span, the cost `record()`, the log line), all four
reading the module constant `MODEL`. Adding a `critic_model()` accessor and a `model`
parameter to `call_model` is the whole implementation seam. But the phase's central claim
to verify was wrong: CONTEXT says cost accounting "already prices by the model named in
the response." **It does not.** `CallUsage.from_response` never reads `response.model`;
the model name is a passed-in constant at `graph.py:103`. Only `inference_geo` is
response-observed. So per-node threading must carry the model into `record()` explicitly,
and the discriminating test for silent misbilling is: set `CRITIC_MODEL` to an unpriced
name, run the graph with fakes, and assert `pricing_unknown` flips — it can only flip if
the threaded model actually reached `record()`.

Everything downstream is already built for this phase. `PRICES` carries rows for
`claude-opus-5` ($5/$25) and `claude-haiku-4-5` ($1/$5) — both verified against the live
pricing page today, both single undated windows (which makes exact-arithmetic tests
date-safe). The fixture `models` map was made a map *specifically* so `critic` could be
added without a schema bump, and `grade_fixture_current`'s docstring names the three
things this phase must do (per-node entry, gate extension, recording disposition). The
reservation arithmetic says an Opus-class critic keeps a *typical* run under the $0.20
estimate through August — and reveals that the 2026-09-01 Sonnet boundary breaks the
estimate *on its own*, critic or no critic. The judge re-derivation has a clean shape:
the "different job" argument survives on its own legs, "independence from the writer"
survives with a changed target, "stronger" survives only as a preference, and the
compensating-control framing dies with ADR-0005.

**Primary recommendation:** thread `model` through `call_model` as a parameter defaulting
to `MODEL`, read `CRITIC_MODEL` per call (the `sessions_token` idiom), prove attribution
with an unpriced-critic test, extend the fixture gate with backfill semantics
(`models.get("critic", models["pipeline"])`), keep the flat $0.20 reservation with a
documented threshold, and draft ADR-0010 around "different job, re-targeted
independence, strength as preference."

<user_constraints>
## User Constraints (from CONTEXT.md)

**Provenance note:** 16-CONTEXT.md records *orchestrator calls under the standing
"proceed without a question round" preference* — revisable at plan review, not
user-ratified. Treated as locked for research scope.

### Locked Decisions

- **`CRITIC_MODEL` env var, defaulting to the writer's model.** Unset → the critic runs
  on `MODEL` exactly as today — a neutral default; deploying this phase changes nothing
  until an operator sets it. The production flip (setting it on Fly) is an operator
  decision at execution time; live verification may demonstrate on a scratch basis if
  cheap, or defer — the plans must state which happened.
- **Per-node model threading.** `call_model` (or its call sites) carries the model per
  node. The critic call site reads `critic_model()`; every other node reads `MODEL`
  unchanged. Model *selection* at the call site; cost attribution stays in
  `CallUsage.cost_usd` (Phase 14's single multiplication point). Verify that per-call
  model attribution genuinely flows through rather than assuming. `pricing_unknown`
  fires for a critic model with no price row (DEC-12).
- **The judge, re-derived (ADR-0010's core).** Answer from scratch: with an independent
  critic, what is the judge FOR? ADR-0010 supersedes ADR-0005 per the convention
  (status-line edit on 0005; carry-forward of whatever survives). The README sentence
  dies with the premise — the "critic shares the writer's model" limitation is
  **deleted**, not rewritten; any genuine residual gets one short sentence.
- **Phase 15's fixture gate must be extended, not discovered.** The models map gains a
  `critic` entry; `grade_fixture_current` compares it; the disposition of the one
  recorded fixture (re-record vs. gate-reports-stale) must be decided in-plan, not
  improvised.
- **Spend cap accounting.** Re-check the $0.20 reservation arithmetic against a costlier
  critic (revisions multiply critic calls); confirm the estimate stays honest or make it
  model-aware. Global cap semantics do not change.

### Claude's Discretion

- Env var parsing/validation idiom (match `usage.py`/`limits.py` conventions); how the
  critic model surfaces in `/health` or `/pricing` if at all; test structure.

### Deferred Ideas (OUT OF SCOPE)

- Actually setting `CRITIC_MODEL` in production (operator flip).
- The full 40-case record run (deferred from Phase 15; re-recording the calibration case
  with the extended models map may happen here if the gate design requires it).
- Follow-up live search (Phase 17). No writer-model change, no default model flip. Judge
  model changes beyond re-deriving the rationale (if the re-derivation concludes the
  judge should change, record it as the ADR's consequence and defer the flip).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-independent-critic-model SC-1 | Critic's model configurable independently of writer/researcher | Finding 1 (the exact four-site seam in `call_model`); Pattern 1 (`critic_model()` accessor, per-call env read) |
| SC-2 | Cost accounting prices each node's model correctly, or `pricing_unknown` fires | Finding 1 (attribution is a passed-in constant — must be threaded); Finding 2 (PRICES coverage verified); the unpriced-critic discriminating test |
| SC-3 | Per-run spend cap accounts for a pricier critic path | Finding 3 (worst-case arithmetic, break-even, Sept-boundary discovery); recommendation: flat estimate + documented threshold |
| SC-4 | Eval-judge choice stated fresh, superseding ADR-0005 | Finding 4 (the argument drafted with what survives/dies); supersession mechanics from docs/adr/README.md verified |
| SC-5 | README no longer says "runs on a stronger model precisely because of this" | Finding 6 (exact locations: README.md:252, plus graders.py docstring, DESIGN.md:74, harness.py docstring — the full inventory of stale prose) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Owner | Secondary | Rationale |
|------------|--------------|-----------|-----------|
| Model selection per node | `graph.py` (`critic_model()` + `call_model` param) | — | The one choke point already exists; selection is call-site config, not accounting |
| Cost attribution | `usage.py` `CallUsage.cost_usd` via `record(totals, call, model)` | `graph.call_model` threads the name | Phase 14's single multiplication point; unchanged — only the *name passed in* changes |
| `pricing_unknown` | `usage.py` `record()` | — | Already fires for any unpriced name; needs zero code, only a test proving the critic path reaches it |
| Reservation estimate | `limits.py` `reserved_run_usd()` + docstring + OPERATIONS | — | Deliberately decoupled from the price table; keep it that way (Finding 3) |
| Fixture staleness gate | `evals/harness.py` `grade_fixture_current` | `evals/fixtures.py` (map already accepts extra roles) | The gate reads the graph; fixtures.py stays graph-free by design |
| Fixture recording | `evals/harness.py` `record_case_to_fixture` models map | — | The only writer of the map; one added entry |
| Surfacing | `service.py` `/pricing` (additive block) | — | `/pricing` already imports graph and prices models; `/health` has no model info today |
| The record | `docs/adr/0010-*.md` + status-line edit on 0005 + index | README/DESIGN/graders prose | Convention verified in docs/adr/README.md |

## Standard Stack

**No new dependencies.** This phase installs nothing. It is pure Python within the
existing tree: `os.environ` reads, one function parameter, dict entries, markdown.

### Core (already in the tree, verified by reading)
| Component | Where | Role in this phase |
|-----------|-------|--------------------|
| `graph.call_model` | `src/research_agent/graph.py:84-121` | The seam. Model named at lines 96 (span), 99 (API), 103 (record), 111 (log) — all four read `MODEL` today |
| `usage.record` / `CallUsage.cost_usd` | `src/research_agent/usage.py:390-403, 329-352` | Attribution target; takes `model: str` as an argument — no change needed, only correct threading |
| `usage.PRICES` | `src/research_agent/usage.py:83-100` | Rows: `claude-sonnet-5` (two dated windows), `claude-opus-5`, `claude-haiku-4-5` (each one undated window) |
| `limits.reserved_run_usd` | `src/research_agent/limits.py:114-130` | The reservation, `DEMO_RESERVED_RUN_USD` env, default $0.20; docstring carries Phase 14's cap-note idiom to extend |
| `evals/fixtures.py` | `REQUIRED_MODEL_ROLES = ("pipeline", "judge")`, extra roles kept verbatim | The map takes `critic` with zero schema change (docstring at lines 26-33 says so explicitly) |
| `evals/harness.py` | `grade_fixture_current:331`, `record_case_to_fixture:512` | Gate to extend; map-writer to extend |
| `docs/adr/README.md` | Supersession convention, verbatim 3-step | ADR-0010 mechanics |

### Package Legitimacy Audit

Not applicable — no packages are installed by this phase. `pip`/`npm` untouched;
`pyproject.toml` untouched.

## Key Findings

### Finding 1 — The model path, exactly (HIGH confidence; read from source)

`call_model` (graph.py:84) is the only place any node touches the API. The model name
appears at exactly four sites, all reading the module constant:

```python
with span(f"node.{node}", ..., model=MODEL, ...):          # line 96  — telemetry
    response = client().messages.create(model=MODEL, **kwargs)  # line 99  — the API call
...
cost = usage_accounting.record(state["usage"], call, MODEL)     # line 103 — cost attribution
log.info("model call", extra={..., "model": MODEL, ...})        # line 111 — the log line
```

**The correction that matters for planning:** `CallUsage.from_response` (usage.py:285)
reads token counts and `inference_geo` from the response — it does **not** read
`response.model`. The Phase 14 phrase "prices by the model named in the response" is
true of the *geo* dimension only. The model name is a passed-in constant. Therefore:

- Per-node threading must carry the model into **all four** sites, or attribution/telemetry
  silently disagree with the bill. A critic on Opus recorded as Sonnet under-reports
  every critic call by 2.5x with no error anywhere.
- The right test is behavioural: with `CRITIC_MODEL` set to a name with no PRICES row,
  a full fake-client graph run must end with `usage["pricing_unknown"] is True` while a
  run with `CRITIC_MODEL` unset ends `False`. That can only pass if the threaded name
  reached `record()` — it is the discriminating mutation test for "someone threads the
  API call but leaves `record(…, MODEL)` behind."
- The positive twin: `CRITIC_MODEL=claude-haiku-4-5` (undated window — date-safe) with
  `FakeClient`'s fixed 1000-in/100-out per call gives exact arithmetic:
  critic call = $(1000×1 + 100×5)/1M = $0.0015$ vs. a Sonnet call's $0.003/0.0045
  (intro/standard — avoid Sonnet in exact assertions; `call_model` prices at *today's*
  date and the 2026-08-31 boundary is three weeks away. Use haiku/opus rows, or assert
  relative: opus-critic run > sonnet-critic run).
- API-call threading is separately provable by capturing `kwargs["model"]` in the fake
  client per node — `FakeClient.create(**kwargs)` already receives it and currently
  ignores it (test_graph_smoke.py:62).

**Design recommendation** (matches the locked decision "per-node model at the call
site"):

```python
# graph.py — read per call, not cached at import; the sessions_token idiom
# (limits.py:530: "Read per call ... tests flip it with monkeypatch.setenv")
def critic_model() -> str:
    """The critic's model. CRITIC_MODEL unset/blank means the writer's model —
    the neutral default that makes deploying this phase a no-op."""
    return os.environ.get("CRITIC_MODEL", "").strip() or MODEL

def call_model(state: AgentState, node: str, *, model: str | None = None, **kwargs):
    model = model or MODEL
    # ... use `model` at all four sites ...

# critic_node — the only call site that changes:
response = call_model(state, "critic", model=critic_model(), max_tokens=2000, ...)
```

Keyword-only `model=` keeps every other call site byte-identical. `graph.py` does not
import `os` today — add it. An alternative (critic_node computes the model and
`call_model` takes it positionally) is equivalent; the keyword default is less churn.

**Rejected alternative — attribute from `response.model`:** the API does echo the model,
but every fake in the tree (`FakeClient`, `ScriptedClient`, `_Response`) lacks the
attribute, the retry/offline paths would need defensive reads, and configuration *knows*
the model (unlike geo, which only the response knows — the asymmetry is the point of
usage.py's `_geo_factor` docstring). Keep the passed-in constant; it is the established
idiom and the fakes stay untouched.

### Finding 2 — Candidate critic models and their price rows (HIGH; verified against live docs 2026-08-10)

Verified today against https://platform.claude.com/docs/en/about-claude/pricing
[CITED: platform.claude.com/docs/en/about-claude/pricing]:

| Model | Published (in/out per MTok) | PRICES row in repo | Match |
|-------|------------------------------|--------------------|-------|
| claude-sonnet-5 | $2/$10 through 2026-08-31; $3/$15 from 09-01 | two dated windows, same numbers | ✓ exact |
| claude-opus-5 | $5/$25 (cache write 5m $6.25, read $0.50) | single undated window, same | ✓ exact |
| claude-haiku-4-5 | $1/$5 (cache write $1.25, read $0.10) | single undated window, same | ✓ exact |
| claude-opus-4-8 / 4-7 / 4-6 | $5/$25 | **no row** | `pricing_unknown` fires — correct per DEC-12 |
| claude-fable-5 | $10/$50 | **no row** | `pricing_unknown` fires |

So the two *plausible* critic candidates (a stronger critic: `claude-opus-5`; a cheaper
one: `claude-haiku-4-5`) are already priced — SC-2's "the table carries a row for
whatever the critic runs on" is already true for the realistic set, and the
`pricing_unknown` path covers everything else with zero new code. **No PRICES additions
are required** unless the plan wants a row for a specific candidate outside these
(adding one is a two-line PriceWindow plus the cache-multiple pin in
`test_cache_rates_are_multiples_of_the_input_rate`, which already loops over all rows).

Web search fee $10/1,000 and the 1.1x `inference_geo: "us"` multiplier both re-verified
unchanged.

### Finding 3 — The reservation arithmetic (HIGH on the numbers; the recommendation is a judgement call)

Inputs, all from the tree: `DEMO_RESERVED_RUN_USD` default $0.20; observed run ≈ $0.15
(limits.py:117, "runs land around $0.15"); the critic call is bounded at
`max_tokens=2000` output with input ≈ notes + draft + rubric ≈ 3–5K tokens; the routing
walk gives **at most 3 critic calls** per run (initial review + one per revision until
`revision_count > MAX_REVISIONS(2)` stops the loop after the 4th writer call — the
graph.py:41-47 comment's arithmetic, re-verified against `supervisor_node`).

Per-critic-call cost at ~4K in / 1K out (a generous middle; typical critic output is far
under the 2000 cap because "APPROVED" is one token):

| Critic model | Per call | vs. Sonnet-intro critic | 3-call worst-case premium |
|---|---|---|---|
| claude-sonnet-5 (intro, today) | ~$0.018 | — | — |
| claude-sonnet-5 (from 09-01) | ~$0.027 | +$0.009 | +$0.027 |
| claude-opus-5 | ~$0.045 | +$0.027 | +$0.081 |
| claude-haiku-4-5 | ~$0.009 | −$0.009 | −$0.027 |

Consequences:

- **Typical run (1 critic call), Opus critic, August rates:** ~$0.15 + $0.027 ≈ $0.18.
  The $0.20 estimate **stays honest**.
- **Worst case (3 critic calls, max-length feedback), Opus critic:** the premium can
  reach ~$0.13 (2K-output feedback calls at $0.07 each) → run ≈ $0.28. Over the
  estimate — but the reservation is sized on the *typical* run by explicit design
  (limits.py docstring: "Sized on observation, not on the per-run hard cap"), the
  per-run cap ($1.00) bounds the tail, and `settle()` replaces the estimate with the
  real figure at run end. Overshoot is bounded by concurrency exactly as before.
- **The discovered orthogonal problem:** from **2026-09-01** the Sonnet boundary lifts a
  typical *unchanged* run to ≈ $0.21–0.22 (token share $0.13 × 1.5 + $0.02 flat search
  fees). The $0.20 estimate goes quietly dishonest three weeks from now **with no
  critic change at all**. The reserved_run_usd docstring analyzed the multipliers
  (Phase 14) but not the price boundary. Worth one sentence in the same docstring and
  OPERATIONS, whatever this phase decides about the critic.

**Recommendation: keep the flat estimate; document the threshold; do not make
`reserved_run_usd()` model-aware.** Reasons: (a) `limits.py` deliberately imports
neither `usage` nor `graph` — coupling the money store to the price table and graph
config to correct a ≤$0.10 admission estimate buys little (the estimate only gates
admission; settlement is always real); (b) the operator knob already exists
(`DEMO_RESERVED_RUN_USD`); (c) the honest form is exactly Phase 14's cap-note idiom —
extend the docstring: *"An Opus-class critic adds ~$0.03 to a typical run and up to
~$0.08–0.13 to a fully-revised one; from 2026-09-01 the Sonnet standard rate alone
lifts a typical run past $0.20. Raise DEMO_RESERVED_RUN_USD to ~$0.30 when setting
CRITIC_MODEL to a model pricier than the writer's"* — and pair the operator-flip
runbook step (set `CRITIC_MODEL`) with the reservation step (review
`DEMO_RESERVED_RUN_USD`) in OPERATIONS. The rejected model-aware alternative
(`reserved = base + critic_premium()`) belongs in the plan/ADR as considered-and-
rejected, with the coupling argument.

### Finding 4 — The judge re-derivation: ADR-0010's argument, drafted (MEDIUM-HIGH; the mechanics are verified, the argument is reasoning)

**What the record being superseded actually says** (read in full): ADR-0005's decision
has two halves — (1) Opus 5 judge vs. Sonnet 5 pipeline, (2) structured verdict. Its
Consequences state plainly: *"The judge is a compensating control for the shared critic
model, not an independent design choice. It is only load-bearing because ADR-0002's
known limit exists."* And it pre-names this phase in "Expected reversal." The index
(docs/adr/README.md) forecasts 0005 → Phase 16.

**The honest evaluation of the three candidate reasons:**

(a) **Different job — survives, and is the primary answer.** The critic gates *drafts*
against *notes*, inline, shaping what ships; the judge grades *final answers* against
*question + rubric*, retrospectively, across the golden set — and its verdicts are the
refusal gate for recordings (`record_case_to_fixture` raises without a judge) and the
replayed assertions in every keyless CI run. That distinction is true whatever models
either runs on. The judge is what makes "quality" a claim rather than a hope; the
critic is what makes any single answer grounded. Removing the shared-model premise
removes a *reason the judge had to be stronger*, not a reason the judge exists.

(b) **Independence — survives with a re-targeted constraint.** The old constraint was
"judge ≠ pipeline model" where pipeline meant everything. The new precise statement:
the judge audits the **writer's** output, so `JUDGE_MODEL ≠ MODEL` (the writer's model)
remains the hard requirement — and it is already pinned by
`tests/test_evals.py:464` (`assert G.JUDGE_MODEL != graph.MODEL`), which survives
unchanged. Judge-vs-**critic** independence is a second, weaker desideratum: if judge
and critic share a model, the eval's grounding verdict correlates with the gate it
audits (a blind spot the critic waved through is likelier invisible to the judge). Does
the argument "hold water" when an operator sets `CRITIC_MODEL=claude-opus-5` with
`JUDGE_MODEL=claude-opus-5`? Partially: judge-writer independence — the load-bearing
one — survives; judge-critic independence is lost. That configuration is legal (both
env vars are operator-controlled) and cannot be hard-forbidden without inventing
policy; record it as a **known limit** in ADR-0010, optionally surfaced as a stderr
warning in record mode when `judge.model == graph.critic_model()`. Note honestly:
Opus 5 and Sonnet 5 are the same vendor and family — cross-family judging would be
stronger independence, but the harness is Anthropic-SDK-only and that is out of scope;
ADR-0005 never claimed cross-family independence either.

(c) **"Stronger" — survives as preference only.** Grading grounding across arbitrary
domains is a discrimination task where the strongest available priced model is a
defensible default; but "stronger *because the critic is weak*" is dead. The ADR must
say "stronger, as a preference, at eval-time-only cost" — not as the reason.

**What survives untouched:** the structured-verdict half of ADR-0005, verbatim (carry
forward, ADR-0007's "Carried forward from" section is the precedent shape).

**Expected conclusion:** `JUDGE_MODEL` stays `claude-opus-5` by default; **no flip**
(and per CONTEXT, if the re-derivation had concluded otherwise, the flip would be
recorded as a consequence and deferred). The decision becomes: *the judge exists for a
different job than the critic; it must not share the writer's model; it should not
share the critic's; Opus 5 is retained as the strongest priced option, now as a fresh
choice rather than a compensation.*

**Supersession mechanics** (verbatim from docs/adr/README.md, verified):
1. ADR-0005 status line → `**Status:** Superseded by ADR-0010 (Phase 16)` — *only* the
   status line; Context/Decision/Consequences are never edited.
2. ADR-0010 status line → `**Status:** Accepted — supersedes ADR-0005`; carries
   `**Source:**` (not `**Promoted from:**` — it originates in this phase, the
   0006-0009 precedent).
3. Index: update both rows' Status/Superseded-by cells; the pre-named forecast on the
   0005 row lands.
4. **Do not edit ADR-0002.** Its decision (separate node, notes as sole truth) stands;
   its "Known limit" prose ("The critic shares the writer's model") becomes
   configuration-dependent, but 0002 is not superseded and the convention forbids
   editing content — ADR-0010's prose notes that 0002's known limit is now
   configuration ("independence is configuration, not default" — CONTEXT's suggested
   one-sentence residual), and the 0002→0005 link chain resolves through 0005's new
   status line. Flag for the planner: this is the correct convention reading, not an
   omission.

### Finding 5 — The fixture gate extension (HIGH; every relevant line read)

Current state: `models = {"pipeline": ..., "judge": ...}` written at harness.py:512;
`REQUIRED_MODEL_ROLES = ("pipeline", "judge")`; extra roles kept verbatim by
`build_fixture`; the one fixture `technical-figures.json` has
`{"pipeline": "claude-sonnet-5", "judge": "claude-opus-5"}`, cost $0.2427, recorded
2026-08-10 at 225b06b, 1 turn. `grade_fixture_current` compares `models["pipeline"]`
against `graph.MODEL` and nothing else — its own docstring names this gap and names the
three-part fix (per-node entry, gate extension, re-record).

**There is no `critic_model()` accessor today** — the gate has nothing to compare
against until graph gains one (Finding 1's accessor serves both consumers).

**Recommendation: option (a), backfill semantics — and in the gate, not the loader.**

```python
# harness.py grade_fixture_current — extended comparison
recorded_pipeline = fixture.get("models", {}).get("pipeline")
recorded_critic = fixture.get("models", {}).get("critic") or recorded_pipeline
if recorded_pipeline == graph.MODEL and recorded_critic == graph.critic_model():
    return G.Grade(name, True, ...)
```

Reasoning:
- **The backfill is honest, not a convenience.** At record time (2026-08-10, commit
  225b06b) the code had no critic seam — the critic *ran on* `graph.MODEL` by
  construction, verifiable from this git history. `critic → pipeline when absent`
  encodes a fact about the recording, not a guess.
- **Behaviour is exactly the designed staleness:** with `CRITIC_MODEL` unset (CI,
  today's production), `critic_model() == MODEL == "claude-sonnet-5"` and the fixture
  stays green — offline stays 41/41 keyless, untouched. The moment an operator sets
  `CRITIC_MODEL` in the environment the suite runs in, the fixture goes stale with a
  message naming the critic — which is precisely "the recording describes a pipeline
  that no longer exists."
- **The hard-stale alternative** (add `"critic"` to `REQUIRED_MODEL_ROLES`, existing
  fixture fails at *load*) destroys a $0.24 fixture for zero informational gain and
  converts a graded red into a load error — the wrong failure shape (load errors are
  for malformed files, per fixtures.py's own docstrings). Rejected.
- **Residual risk accepted:** a *future* recording made with `CRITIC_MODEL` set whose
  `critic` key is then hand-deleted would backfill wrongly. Mitigated: from this phase
  on, `record_case_to_fixture` always writes `"critic": graph.critic_model()`, so
  absence means pre-16 — and the pre-16 population is exactly one file, which the
  deferred full record run will eventually replace. State this in the gate's docstring.
- **Re-record of the calibration case is optional, not required** (~$0.25 — Phase 15
  measured $0.2427 + judge). If the plan wants the `critic` key present in the
  committed fixture rather than backfilled, bundle the re-record with the phase's live
  leg; otherwise defer with the full record run. Either is honest; the gate handles
  both.

Also touched, additive: `record_suite`/`run_suite` report dicts carry
`"model": graph.MODEL` — a `"critic_model"` key can be added additively (do not rename
`"model"`; test_service.py pins `/pricing`'s `"model"` key and evals `__main__` reads
`f["models"]["pipeline"]`). The record cost preview (`evals/__main__.py`
`_assumed_pipeline_cost`) lumps the whole pipeline turn into one synthetic call at
`graph.MODEL` — with a pricier critic this under-quotes; Phase 15 already corrected one
35% under-quote, so at minimum note the assumption in the preview's constants comment,
or add the critic's share as a second `_call_cost` line at `graph.critic_model()`.

### Finding 6 — Surfacing, and the full stale-prose inventory (HIGH)

**Surfacing recommendation (discretionary): one additive block on `/pricing`, nothing
on `/health`.** `/pricing` already imports `graph`, prices `graph.MODEL`, and has the
`"embedding"` sub-block as the exact precedent shape. Add, additively (limits.status's
"ADDITIVE ONLY" rule is the house style for payloads a live page may hold open):

```python
"critic": {
    "model": critic,                     # graph.critic_model(), read at request time
    "independent": critic != graph.MODEL,
    # usd_per_mtok if priced; if unpriced, report it honestly rather than 501ing
    # the whole endpoint — the writer's pricing is still valid and /pricing going
    # dark because of a critic typo helps nobody. "unpriced": true mirrors what
    # cost accounting will do (pricing_unknown), and /health stays model-free.
}
```

Note the current endpoint 501s on any `UnknownModelPricing` — an unpriced *critic*
should not take that path (the 501 contract is "this service cannot say what its own
core calls cost"; the critic being unpriced is exactly what `pricing_unknown` exists to
report per run). Catch it separately.

**Every location where the old premise lives** (grep-verified — the standing
instruction says grep for facts that live only in deleted prose *before* deleting):

| Location | Text | Action |
|---|---|---|
| `README.md:252` | "**The critic shares the writer's model.** … The eval judge runs on a stronger model precisely because of this." | **DELETE** the bullet (SC-5; standing instruction: deleted, not rewritten). Residual, if any, is one sentence: independence is configuration, not default |
| `README.md:32` | "…LLM judge on a stronger model." | Survives — factually true (Opus default vs Sonnet); the *reason* isn't stated here |
| `evals/graders.py:13-17` (module docstring) | "The critic inside the graph shares the writer's model, which makes it a decent proofreader…" | Rewrite — this is code prose, not the README limitation; it states the dead premise as fact |
| `docs/DESIGN.md:74` | "The in-graph critic shares the writer's model … so it runs on Opus 5 against Sonnet 5 … Recorded as ADR-0005." | Planner decision: DESIGN is "the readable argument" the ADR README says stays as-is, but Phase 10 edited DESIGN where verifiably false. Minimum: the forward-link must point at 0010 (or at 0005-whose-status-line-redirects). Recommend a one-line update of the forward reference, leaving the narrative |
| `evals/harness.py:331-353` (`grade_fixture_current` docstring) | The "Cannot catch" paragraph describing exactly this phase's gap | Rewrite once the gate compares critic — **and note** `tests/test_evals.py:1655` asserts `"graph.MODEL" in doc`, and :1652 reads the docstring; docstring edits can fail tests |
| `docs/adr/0005` | status line only | Per convention |
| `docs/adr/README.md` index | 0005 row + new 0010 row | Per convention |
| `docs/adr/0002` | "Known limit" prose | **Not edited** (Finding 4) |
| `docs/OPERATIONS.md` | reservation guidance | Gains the CRITIC_MODEL/DEMO_RESERVED_RUN_USD pairing (Finding 3) |

## Architecture Patterns

### The flow after the change

```
supervisor ──routes──▶ critic_node
                          │  model = critic_model()          (env read, per call)
                          ▼
                       call_model(state, "critic", model=…)
                          │
            ┌─────────────┼──────────────┬───────────────┐
            ▼             ▼              ▼               ▼
        span(model=m)  messages.create  record(usage,   log extra
                       (model=m)        call, m)        model=m
                                          │
                                          ▼
                              CallUsage.cost_usd(m, today)
                              → PRICES[m] window, or
                                pricing_unknown=True (no row)
                                          │
                                          ▼
                          state.usage.cost_usd ─▶ supervisor budget check
                                               ─▶ metrics / settle / /metrics
every other node: call_model(state, node)  →  model defaults to MODEL, byte-identical
```

### Pattern 1: env read per call, clamped toward the safe direction
**What:** `critic_model()` reads `os.environ` on every call; blank/whitespace → `MODEL`.
**Why this idiom:** `sessions_token()` (limits.py:549: "Read per call, not cached in a
module constant: tests flip it with monkeypatch.setenv") and `cost_discount_factor()`
both read per call. A module-level read would freeze the value at import and break the
monkeypatch test idiom used everywhere in this suite. No validation beyond strip-or-
default: an unknown-but-real model must be *allowed* (that is the feature) and an
unpriced one is `pricing_unknown`'s job, not the accessor's.

### Pattern 2: one choke point per concern (do not blur them)
Model **selection** = call site (`critic_node` passes it). Cost **computation** =
`CallUsage.cost_usd` only. Reservation **estimate** = `limits.py`, decoupled from both.
The phase adds a parameter; it must not add a second multiplication site, a second
model-resolution site, or a `usage`→`graph` import.

### Anti-patterns to avoid
- **Threading the API call but not `record()`** — the silent misbilling this phase's
  central test exists to catch (Finding 1).
- **`CRITIC_MODEL` read at import** (`CRITIC_MODEL = os.environ.get(...)` at module
  scope) — breaks monkeypatch tests and the "operator changes config, process reports
  new number" property usage.py documents.
- **Exact-dollar assertions on `claude-sonnet-5` at today's date** — `call_model` prices
  at wall-clock today and the intro window closes 2026-08-31; a test written this week
  against $2/$10 goes red on a date nobody chose. Use the undated rows (opus/haiku) for
  exact arithmetic, exactly as `test_usage.py` pins dates for everything else.
- **Renaming/reshaping existing payload keys** (`"model"` in reports and `/pricing`) —
  additive only.
- **501ing `/pricing` on an unpriced critic** — takes down pricing for the writer too.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Unpriced-model handling | A validation list of allowed CRITIC_MODEL values | `pricing_unknown` via `record()` | Already built, tested, and is DEC-12's designed shape; a whitelist would need maintaining against every model release |
| Fixture schema change | schema_version bump / migration | The models map's extra-role tolerance + gate-side backfill | fixtures.py was designed for exactly this (its docstring says "Phase 16" by name) |
| Model-aware reservation | `reserved_run_usd()` importing the price table | Flat estimate + docstring threshold + OPERATIONS pairing | Coupling money-store to pricing for a ≤$0.10 admission estimate; settle() is already real-cost (Finding 3) |
| Judge/critic collision enforcement | A hard error when JUDGE_MODEL == critic_model() | ADR-0010 known-limit prose (+ optional record-mode stderr warning) | Both are legitimate operator knobs; policy belongs in the record, not a crash |

## Common Pitfalls

### Pitfall 1: the Sonnet date boundary inside cost tests
**What goes wrong:** graph-level cost assertions written against $2/$10 pass until
2026-08-31 and fail on 2026-09-01, because `call_model` → `record()` prices at today.
**Avoid:** exact arithmetic only on undated-window models (opus, haiku); relative
assertions otherwise. `test_usage.py`'s FIXED_AUGUST idiom is for unit level where `on=`
is passable; `call_model` has no `on=` (and should not grow one for tests).

### Pitfall 2: docstring-pinned tests
`tests/test_evals.py:1652-1655` asserts the *content* of `grade_fixture_current.__doc__`
(including the literal string `"graph.MODEL"`). Rewriting the docstring (required —
Finding 6) will fail this pin unless updated together. Grep for other doc pins before
editing prose in harness/graders.

### Pitfall 3: the fakes don't know about `model`
`FakeClient.create(**kwargs)` and `ScriptedClient.create(**kwargs)` ignore
`kwargs["model"]` — everything keeps working with `CRITIC_MODEL` set to *anything*,
which is correct for the neutral-default proof but means **no existing test can catch
mis-threading**. The two new discriminating tests (kwargs capture; unpriced-critic →
`pricing_unknown`) are the coverage, and both are cheap.

### Pitfall 4: CI must never see CRITIC_MODEL
The offline 41/41 keyless invariant and the fixture's green replay both depend on
`critic_model() == MODEL` in CI. Nothing sets it today; assert the neutral default
explicitly in a test (`monkeypatch.delenv("CRITIC_MODEL")` → identical behaviour) so a
future workflow edit that exports it is caught as a red, not a mystery-stale fixture.

### Pitfall 5: API-compat of arbitrary critic models [ASSUMED]
`critic_node` sends `thinking={"type": "adaptive"}` and `output_config={"effort":
"medium"}`. The plausible candidates (opus-5, haiku-4-5) accept these; an operator
pointing `CRITIC_MODEL` at an older model that rejects the params gets a 400 →
`retry_node` retries → run fails. The service validates pricing (via
`pricing_unknown`), not API compatibility — acceptable, but say so in OPERATIONS'
flip runbook ("supported: current-generation models").

### Pitfall 6: the README delete
Standing instruction (corrected twice per CONTEXT): the limitation bullet is DELETED,
whole-file pass, and **grep first** for facts living only in the deleted prose. The
Finding 6 table is that grep's result; nothing in the bullet is load-bearing elsewhere
except the "stronger model" fact, which survives at README.md:32 independently.

## Code Examples

### The attribution proof (the phase's most important test)
```python
def test_critic_model_reaches_cost_attribution_not_just_the_api(fake_client, monkeypatch):
    """If someone threads messages.create but leaves record(…, MODEL), this is
    the only red. pricing_unknown can flip ONLY if the threaded name reached
    record() — an unpriced name at the API call alone changes nothing."""
    monkeypatch.setenv("CRITIC_MODEL", "some-unpriced-model")
    fake_client()
    result = app.invoke(initial_state("why is the sky blue?"))
    assert result["usage"]["pricing_unknown"] is True   # critic call unpriced
    assert result["usage"]["cost_usd"] > 0              # writer/researcher still priced

def test_unset_critic_model_is_byte_identical_to_today(fake_client, monkeypatch):
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    fake_client()
    result = app.invoke(initial_state("why?"))
    assert result["usage"]["pricing_unknown"] is False

def test_every_node_sends_its_own_model(fake_client, monkeypatch):
    monkeypatch.setenv("CRITIC_MODEL", "claude-haiku-4-5")
    client = fake_client()
    app.invoke(initial_state("why?"))
    models_by_node = {node: kw["model"] for node, kw in client.calls_with_kwargs}
    assert models_by_node["critic"] == "claude-haiku-4-5"
    assert models_by_node["writer"] == graph.MODEL       # unchanged, byte-identical
```
(FakeClient needs a two-line change to also record kwargs — or capture
`kwargs["model"]` alongside the prompt in `self.calls`.)

### Exact per-node arithmetic, date-safe (undated windows only)
```python
def test_critic_priced_at_its_own_rate(fake_client, monkeypatch):
    # FakeClient: 1000 in / 100 out per call; haiku $1/$5 — undated, no boundary risk
    monkeypatch.setenv("CRITIC_MODEL", "claude-haiku-4-5")
    ...
    # critic call: (1000*1 + 100*5)/1e6 = $0.0015; sonnet writer differs — assert the sum
```

### The gate, extended with backfill
```python
recorded_critic = fixture.get("models", {}).get("critic") or recorded_pipeline
# absent critic key == pre-Phase-16 recording == critic ran on the pipeline model,
# by construction of the code at record time. From this phase on the recorder
# always writes the key, so absence is a statement, not a gap.
```
Tests: unset env → technical-figures green (41/41 preserved); `CRITIC_MODEL=x` set →
stale, detail names the critic; synthetic fixture *with* a critic key → compared
directly, backfill not consulted.

## State of the Art

| Old (today's tree) | New (this phase) | What it means |
|---|---|---|
| `MODEL` constant at all 4 sites in `call_model` | `model` param, default `MODEL`; critic passes `critic_model()` | SC-1; neutral default |
| Attribution: constant passed to `record()` | Same mechanism, threaded name | SC-2; the "response-observed" belief is corrected — only geo is observed |
| `models = {pipeline, judge}` | `+ critic` (recorder); gate compares with backfill | SC-designed extension lands |
| ADR-0005 Accepted (forecasting its own reversal) | Superseded by ADR-0010; structured-verdict half carried forward | SC-4 |
| README:252 limitation bullet | Deleted | SC-5 |
| $0.20 reservation, multiplier-only analysis | Same default + documented critic threshold + Sept-boundary note | SC-3 |

## Environment Availability

Code/docs/tests phase; no new external dependencies. From repo evidence (ROADMAP
progress table, suites run 2026-08-09/10): python3 + pytest working (663/65 plain,
727/1 armed), ruff clean, git present, local PG on :54329 for the armed leg. The only
external need is the **optional** live leg: one real run with `CRITIC_MODEL` set
requires `ANTHROPIC_API_KEY` + `VOYAGE_API_KEY` on the operator's machine — cost ≈
$0.15–0.19 (haiku or opus critic; Finding 3), affordable as a scratch demonstration via
the REPL/CLI with the env var exported, **no Fly deploy and no fly secrets** (the
production flip stays deferred per CONTEXT). Plans must state whether the scratch
demonstration happened or was deferred.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing; config in pyproject.toml) |
| Quick run | `python3 -m pytest tests/test_graph_smoke.py tests/test_usage.py -q` |
| Full suite | `python3 -m pytest -q` (baseline 663 passed / 65 skipped plain; 727/1 armed) |
| Offline evals | `python -m evals` with `ANTHROPIC_API_KEY=""` — baseline **41/41 keyless**, must be preserved |

### Phase Requirements → Test Map
| Req | Behavior | Test type | Automated command | File exists? |
|-----|----------|-----------|-------------------|--------------|
| SC-1 | critic model threads to API call per node; others unchanged | unit (fakes) | `pytest tests/test_graph_smoke.py -k critic -x` | ❌ new tests in existing file |
| SC-1 | neutral default: unset → identical behaviour | unit | same selector + entire existing suite green unchanged | ✅ (suite) + ❌ explicit pin |
| SC-2 | threaded model reaches `record()` (pricing_unknown flips) | unit (fakes) | `pytest tests/test_graph_smoke.py -k pricing_unknown -x` | ❌ new |
| SC-2 | critic priced at own rate (exact, undated models) | unit | `pytest tests/test_graph_smoke.py -k "critic and rate" -x` | ❌ new |
| SC-3 | reservation docstring/OPERATIONS threshold | docs + (optional) doc-pin test | grep in verify; no behaviour change to test | manual |
| SC-4 | ADR-0010 exists; 0005 status line; index rows | docs | grep `Superseded by ADR-0010` in verify | manual |
| SC-5 | README bullet gone; graders/DESIGN/harness prose updated | docs | `grep -c "precisely because of this" README.md` == 0 | manual |
| Gate ext. | fixture green unset / stale when set / direct compare when key present | unit | `pytest tests/test_evals.py -k fixture_current -x` | ✅ file, ❌ new cases |
| Recorder | models map writes critic entry | unit (fakes) | `pytest tests/test_evals.py -k "record and models" -x` | ✅ file (test at :2062 pins the map — must be updated, a designed red) |

### Sampling Rate
- **Per task commit:** the quick-run selector for the touched area, `--collect-only`
  first on every new selector (SIXTEEN vacuous gates across seven phases — the standing
  warning).
- **Per wave merge:** full plain suite + `python -m evals` keyless (41/41).
- **Phase gate:** full plain + armed suites, ruff, offline evals, zero
  `.github/workflows/ci.yml` diffs.

### Discriminating mutations to demand of the new tests
1. Thread API call, leave `record(…, MODEL)` → only the pricing_unknown test reds.
2. Thread `record`, leave `messages.create(model=MODEL)` → only the kwargs-capture reds.
3. Gate compares pipeline only (today's code) → only the set-CRITIC_MODEL-stale test reds.
4. `critic_model()` cached at import → only the monkeypatch-flip test reds.
5. Recorder omits critic key → only the models-map pin reds.

### Wave 0 Gaps
None structural — all new tests land in existing files (`test_graph_smoke.py`,
`test_usage.py` if any unit-level additions, `test_evals.py`). One **designed red**:
`test_evals.py:2062` pins the exact two-role models map and must change with the
recorder. No framework installs.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | `thinking: adaptive` / `output_config.effort` accepted by any current-gen model an operator might set (verified only implicitly for sonnet-5 in production; opus-5 used by the Judge with same params) | Pitfall 5 | An exotic CRITIC_MODEL 400s at runtime; mitigated by runbook note, not code |
| A2 | Typical critic call ≈ 4K in / ≤1K out (derived from prompt shapes + max_tokens, not measured per-node) | Finding 3 | Reservation threshold numbers shift ±30%; conclusion (flat + documented threshold) is robust to that |
| A3 | The scratch live demonstration at ~$0.15–0.19 is acceptable spend (mirrors Phase 13's scratch-leg precedent) | Environment | Defer the live leg; plans state which happened — CONTEXT explicitly allows either |

## Open Questions (RESOLVED)

All three resolved by the plans: Q1 → DESIGN.md:74 gets a one-line forward reference
(16-03 Task 2). Q2 → backfill semantics; re-record deferred to the full record run
(16-02). Q3 → yes, the stderr collision warning ships (16-02 Task 3).


1. **Does DESIGN.md:74 get a forward-link edit?** The ADR README says DESIGN "stays as
   it is," but Phase 10 edited DESIGN where verifiably false, and after this phase the
   passage states a dead rationale as current fact. Recommendation: one-line forward
   reference to ADR-0010; leave the narrative. Planner/plan-review call.
2. **Re-record `technical-figures` now (~$0.25) or leave backfilled?** Both honest
   (Finding 5). Recommendation: leave backfilled; bundle the re-record with the
   deferred full record run — unless the live leg runs anyway and the marginal cost is
   accepted.
3. **stderr warning in record mode when `judge.model == critic_model()`?** Cheap, honest,
   discretionary. Recommendation: yes, one line in `record_case_to_fixture` or the CLI.

## Sources

### Primary (HIGH)
- This tree, read in full: `src/research_agent/graph.py`, `usage.py`, `limits.py`,
  `service.py` (/health, /pricing), `evals/{graders,fixtures,harness,__main__}.py`,
  `tests/{test_usage,test_graph_smoke,test_evals(.grep)}.py`,
  `docs/adr/{0002,0005,README}.md`, `evals/fixtures/technical-figures.json`,
  `.planning/{ROADMAP,REQUIREMENTS}.md`, `16-CONTEXT.md`, `README.md:32,252`,
  `docs/DESIGN.md:74`.
- https://platform.claude.com/docs/en/about-claude/pricing — fetched 2026-08-10; opus-5
  $5/$25, haiku-4-5 $1/$5, sonnet-5 boundary, $10/1K web search, 1.1x `inference_geo:
  "us"` — all matching the repo's PRICES exactly.

### Secondary / Tertiary
None needed — no ecosystem discovery in this phase.

## Metadata

**Confidence breakdown:**
- Model path & attribution seam: HIGH — read line-by-line; the CONTEXT correction is a fact, not an inference
- Pricing rows & rates: HIGH — repo table cross-checked against the live docs page today
- Reservation arithmetic: HIGH on math, MEDIUM on per-call token assumptions (A2); recommendation robust
- ADR-0010 argument: MEDIUM-HIGH — mechanics verified; the argument itself is reasoning the plan/ADR must own
- Fixture gate: HIGH — every consumer of the models map located

**Research date:** 2026-08-10
**Valid until:** 2026-08-31 (the Sonnet boundary changes the reservation numbers and any
exact-cost test written against intro rates; everything else is stable)
