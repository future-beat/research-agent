# Phase 18: Independent eval judge - Research

**Researched:** 2026-08-13
**Domain:** Anthropic Messages API (judge call shape, refusal semantics), the evals judge/recorder seam, the price table, ADR ceremony
**Confidence:** HIGH (every load-bearing claim verified against the tree, the pinned SDK, or platform.claude.com today)

<user_constraints>
## User Constraints (from 18-CONTEXT.md)

### Locked Decisions

- **The judge model is `claude-opus-4-8` — decided, not open.** Chosen over Fable 5
  explicitly: independent of the Opus 5 critic, stronger than the Sonnet 5 writer it
  grades, zero cost change ($5/$25 per MTok, same as today's judge). The Fable option was
  presented and declined. The known residual is accepted and must be stated in ADR-0012:
  Opus 4.8 is the critic's model *family*; a family-correlation skeptic's argument
  survives. Independence here means model identity — the same narrowing ADR-0010 made for
  the critic, stated with the same honesty.
- **The refusal guard is in scope regardless of model.** `Judge.verdict()`
  (evals/graders.py:731) reads `response.content` without checking `stop_reason`. A
  safety-classifier refusal is HTTP 200 + `stop_reason: "refusal"` + empty or partial
  content — today that surfaces as `ValueError: Judge returned unparseable verdict`. A
  latent bug on Opus 5 now, not a Fable-only concern. A refused verdict must be
  distinguishable from a malformed one downstream; a refusal flows into the recorder's
  existing refusal path with an honest reason, never retried into silence.
- **ADR-0012 supersedes ADR-0010, with ceremony.** v1.1 closed the reversal register as
  spent; this phase deliberately reopens it and ADR-0012 must say so plainly. ADR-0010's
  two positions are handled separately: "critic stronger than writer" is untouched;
  "judge == critic is an acceptance" is the part superseded. ADR-0010's body is not
  edited (records are history).
- **Price table:** `usage.PRICES` gains a `claude-opus-4-8` row ($5/$25; cache rates the
  documented 1.25×/0.1× of base input, consistent with the cache-rate pin test). Without
  it a judge run lands on `pricing_unknown` — DEC-12 fails loud, which would fail every
  `--live`/`--record` run the day the default flips.

### Claude's Discretion

- Whether the refusal guard returns a structured refusal object or raises a typed
  exception — pick what composes best with the existing grader/recorder refusal path.
- Test structure and mutation-probe selection, per house discipline (every gate observed
  red before trusted).
- Whether `EVAL_JUDGE_MODEL` env override behavior needs additional pinning.

### Deferred Ideas (OUT OF SCOPE)

- Recording the 40 cases — Phase 21, by roadmap dependency.
- Any critic-side change — out of milestone scope entirely (`CRITIC_MODEL` stays
  `claude-opus-5` in production).
- The README Limitations bullet deletion — Phase 22 owns it (this phase updates every
  *other* doc surface so Phase 22's pass finds no contradictions).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-judge-independent-of-critic | Judge defaults to `claude-opus-4-8` (not the critic's model, stronger than the writer, zero cost change); `stop_reason` checked before content is read; PRICES carries an Opus 4.8 row; ADR-0012 records the supersession of ADR-0010 and the reopening of the reversal register | Findings 1–7 below: exact seams mapped (graders.py:33/:731, harness.py:633, fixtures/recorder path), Opus 4.8 API compatibility verified against the pinned SDK and official docs, refusal semantics verified, the full test/doc inventory enumerated, and the two ordering traps (PRICES-before-flip, the :2560 status-line test) identified |
</phase_requirements>

## Summary

This phase is a default flip, a five-line guard, a two-line price row, and a record —
sitting inside the densest test coverage in the repo. The code changes are small and
fully determined: `JUDGE_MODEL`'s default string at `evals/graders.py:33`, a
`stop_reason` check at the top of `Judge.verdict()` (graders.py:731–748), a
`claude-opus-4-8` entry in `usage.PRICES` (src/research_agent/usage.py:88), ADR-0012 plus
the index arithmetic, and the doc surfaces that assert judge == critic. Everything hard
about the phase is in the *consequences*: which of the ~30 judge-adjacent tests move,
which docstrings state a premise that inverts, and one committed test that goes red the
moment the supersession convention is applied to ADR-0010's status line.

External compatibility is settled. Verified today against platform.claude.com and the
pinned `anthropic==0.120.0` SDK: `claude-opus-4-8` is a live API model ID (not retired),
supports `thinking={"type": "adaptive"}` (on 4.8 thinking is *off unless* that exact
value is sent — which the code already sends), supports the full `output_config` effort
ladder including `"high"`, and is on the GA structured-outputs model list for
`output_config.format` json_schema. Pricing is $5 in / $25 out / $6.25 cache-write-5m /
$0.50 cache-read — identical to Opus 5's row, so "zero cost change" is exact, and both
models are post-4.7 tokenizer, so even token counts are comparable. The SDK's `Message`
model carries `stop_reason` (literal includes `"refusal"`) and `stop_details`
(`RefusalStopDetails` with `type`, `category`, `explanation`), so the guard needs no SDK
upgrade.

The refusal path today: a `Judge.verdict()` exception propagates through
`_grade_research` into `run_case`'s blanket `except` (harness.py:334), lands in
`result.error`, and the recorder refuses with *"the run errored"* — blaming a paid,
successful pipeline run for the judge's decline. The honest fix surfaces the refusal as a
**failed Grade** ("a graded finding", per the success criterion) so it flows into
`_refuse_failing`'s *failed-graders* branch with the grader's name and a refusal-shaped
detail, keeping "the judge declined to look" distinguishable from both "the answer is
bad" and "the verdict was malformed" (which keeps raising).

**Primary recommendation:** land the PRICES row and the default flip in the same commit
(two live-table tests price `G.JUDGE_MODEL` and will raise `UnknownModelPricing` if the
flip lands first); implement the refusal guard as a refusal-shaped failed Grade returned
from `Judge.verdict`'s boundary; and treat the tests at `tests/test_evals.py:2516–2596`
plus the `_state_judge_critic_relation` wording as deliverables whose premise inverts,
not collateral.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Judge model default + override | evals layer (`evals/graders.py`) | — | `JUDGE_MODEL` is read once at import from `EVAL_JUDGE_MODEL`; the graph never sees it |
| Refusal guard | evals layer (`Judge.verdict`, graders.py:731) | recorder (`evals/fixtures.py::_refuse_failing`) | The guard lives at the one response boundary; the recorder already refuses failed grades — compose, don't duplicate |
| Judge-run pricing | `src/research_agent/usage.py` (PRICES) | evals preview (`evals/__main__.py::_assumed_judge_cost`) | One table, read at call time; the preview resolves `price_for(G.JUDGE_MODEL, day)` per run |
| Collision statement | `evals/harness.py::_state_judge_critic_relation` | — | Fires on model equality, once per record run; logic survives the flip, wording/premise does not |
| The record | `docs/adr/` (ADR-0012, index, 0010 status line) | DESIGN.md / OPERATIONS.md / graders.py docstring | Supersession convention is verbatim three-step in docs/adr/README.md |

## Standard Stack

### Core

No new libraries. The phase runs entirely on what is pinned:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.120.0 (pinned, pyproject.toml:14) | The judge's client; `Message.stop_reason` / `stop_details` already in this version | [VERIFIED: local SDK introspection — `Message.model_fields` includes `stop_details`, `stop_reason`; `StopReason` literal includes `"refusal"`; `RefusalStopDetails(type, category, explanation)` exists] |
| pytest | in `.venv` | Test framework | Existing; `.venv/bin/pytest` (bare `pytest`/`ruff` are not on PATH — Phase 10-05 lesson) |

**Installation:** none. No `pip install`, no version bumps.

## Package Legitimacy Audit

No packages are installed by this phase. **Packages removed due to slopcheck: none.
Packages flagged: none.** (Audit protocol not run — nothing to audit.)

## Finding 1 — Opus 4.8 API compatibility for the exact judge call shape (HIGH)

The judge's call (graders.py:733–741) sends: `model`, `max_tokens=1500`,
`thinking={"type": "adaptive"}`, `output_config={"effort": "high", "format":
{"type": "json_schema", "schema": VERDICT_SCHEMA}}`, one user message. Against
`claude-opus-4-8`, every parameter is supported:

- **`thinking: {"type": "adaptive"}`** — on Opus 4.8, requests run *without* thinking
  unless this exact value is set; the code sets it. (On Opus 5 the same value is valid
  and equivalent to the default.) [CITED: platform.claude.com/docs/en/about-claude/models/whats-new-opus-5 § "Thinking on by default"]
- **`output_config.effort: "high"`** — Opus 4.8 supports the five-level ladder
  (low/medium/high/xhigh/max), `high` the default. [CITED: same page § "Effort matters more"; corroborated by the Opus 4.8 effort tutorials surfaced in search]
- **`output_config.format` json_schema** — structured outputs are **GA, no beta
  header**, and `claude-opus-4-8` is on the supported-models list explicitly. [CITED: platform.claude.com/docs/en/build-with-claude/structured-outputs]
- **Model availability** — "Claude Opus 4.8 remains available on all of these
  platforms"; the migration guide shows `model = "claude-opus-4-8"` as the literal API
  ID. It is *not* on the retired list (Opus 4.1/4, Sonnet 4, Haiku 3.5 are). [CITED: whats-new-opus-5 § Availability; pricing page retirement annotations]
- **SDK** — `anthropic==0.120.0` sends `output_config`/`thinking` today against Opus 5
  in this very code; the model string is just a string. `stop_reason`/`stop_details` are
  parsed by this SDK version (verified by local introspection).
- **Tokenizer parity** — "Claude 4.7 and later models use a newer tokenizer" (~30% more
  tokens for the same text); Opus 4.8 and Opus 5 are both post-4.7, so the judge-leg
  token assumptions (`ASSUMED_JUDGE_INPUT_TOKENS=4000`, `OUTPUT=1500`, both labelled
  unmeasured) remain equally (in)valid — no constant needs touching. [CITED: pricing page tokenizer note]

**The call will not 400 on the new model.** The one behavior difference worth a sentence
in the plan: on Opus 4.8, adaptive thinking triggers *only when the model decides the
turn needs it*, so some verdicts will spend zero thinking tokens where Opus 5 (thinking
on by default) would think — a cost floor, not a compatibility risk.

## Finding 2 — Refusal semantics, verified (HIGH on the contract; MEDIUM on per-model rates)

- A safety-classifier refusal is a **normal HTTP 200** with `stop_reason: "refusal"`.
  `stop_details` is non-null **only** for refusals and identifies the trigger; in SDK
  0.120.0 it is `RefusalStopDetails(type="refusal", category ∈ {cyber, bio,
  frontier_llm, reasoning_extraction, general_harms} | None, explanation: str | None)`.
  [CITED: platform.claude.com/docs/en/build-with-claude/handling-stop-reasons; VERIFIED: SDK introspection]
- On refusal, `response.content` is **empty or minimal**. The current code's
  `"".join(b.text for b in response.content if b.type == "text")` yields `""`, and
  `json.loads("")` raises `JSONDecodeError` → today's misleading
  `ValueError: Judge returned unparseable verdict: ''`. That is the exact bug named in
  the requirement, confirmed by reading the code path.
- **Structured outputs do not survive a refusal.** The structured-outputs docs do not
  promise schema conformance on refusal, and empty content trivially cannot conform —
  so the schema guarantee is conditional on a non-refusal stop. The guard must run
  *before* any parse. [CITED: structured-outputs page (gap noted); handling-stop-reasons (content empty)] — the conditional-guarantee framing is [ASSUMED] in its generality but entailed by "content is empty".
- Full `stop_reason` vocabulary in SDK 0.120.0: `end_turn`, `max_tokens`,
  `stop_sequence`, `tool_use`, `pause_turn`, `refusal`,
  `model_context_window_exceeded`. [VERIFIED: SDK `StopReason` literal]
- Per-model refusal *rates* (CONTEXT's "hotter refusal classifiers" on Fable) are not
  documented per model; the guard is model-independent by design, so this does not
  matter for correctness. [ASSUMED for rates; irrelevant to the mechanism]

## Finding 3 — The code seams, exactly (HIGH; all read this session)

| Seam | Location | What changes |
|------|----------|--------------|
| Default | `evals/graders.py:33` — `JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")` | The literal becomes `"claude-opus-4-8"` |
| Guard | `evals/graders.py:731–748` — `Judge.verdict()` | Check `response.stop_reason` before joining `response.content` |
| Module docstring | `evals/graders.py:13–19` | States "in production the judge and the critic run on the same model. That is accepted… recorded… in ADR-0010" — premise inverts; rewrite and point at ADR-0012 |
| Collision line | `evals/harness.py:633–667` — `_state_judge_critic_relation` | Logic (fires on `judge.model == graph.critic_model()`, once per record run, None-guarded) **survives**; the docstring's "this is the deployed configuration" and the message's "accepted… ADR-0010" **invert** — at the new defaults production no longer collides. Message and ADR pointer need re-derivation |
| Recorder refusal path | `evals/fixtures.py:199–211` — `_refuse_failing` | Two branches: `result.error` ("the run errored") and failed grades (named graders). **No change needed if the guard emits a failed Grade** — the refusal flows into the second branch with the grader's name |
| Error isolation | `evals/harness.py:334` — `run_case`'s blanket `except` | Why a raised guard is the wrong shape: any exception becomes `result.error`, and the recorder blames the *run* |
| Price table | `src/research_agent/usage.py:88–103` — `PRICES` | Add `"claude-opus-4-8": [PriceWindow(Price(input=5.0, output=25.0, cache_write_5m=6.25, cache_read=0.50))]` — single undated window, same shape as opus-5's row |
| Preview | `evals/__main__.py:264–265, 325–335, 404` | `_assumed_judge_cost` resolves `price_for(G.JUDGE_MODEL, day)` at run time; `_rate_line(G.JUDGE_MODEL, day)` prints the judge's rate. No code change — but both **raise `UnknownModelPricing`** if the default flips before the row lands |
| Staleness gate | `evals/harness.py:355–425` — `grade_fixture_current` | **Confirmed by reading: compares `models["pipeline"]` vs `graph.MODEL` and `models.get("critic") or pipeline` vs `graph.critic_model()` — never the judge.** The docstring says so and `tests/test_evals.py:1896` (`test_the_replay_model_gate_states_its_claim_boundary`) pins `"JUDGE"` appearing in that docstring as the stated boundary. A judge flip does not stale `evals/fixtures/technical-figures.json` — state this in the phase records, not folklore |
| `/pricing` | `src/research_agent/service.py:900` | Reports `graph.MODEL` (+ embedding) only; a new PRICES row changes nothing there. "Zero cost change against /pricing" is satisfied by rate identity ($5/$25 both) |

**How a refusal propagates today (traced, not assumed):** `Judge.verdict` raises
`ValueError` → `_grade_research` (harness.py:223) is inside `run_case`'s `try` →
`result.error = "ValueError: Judge returned unparseable verdict: ''"` → in `--record`,
`_refuse_failing` raises `FixtureError("refusing to record X: the run errored (…)")`;
in `--live`, the case is an errored CaseResult. Both blame the wrong actor.

**Recommended guard shape (discretionary, with reasoning):** a refusal-shaped
**failed verdict** returned from `Judge.verdict`, not a typed exception. Three reasons:
(1) the success criterion's own words — "surfaced as a **graded finding**"; (2) an
exception is swallowed by run_case:334 into `result.error`, which is the *run errored*
refusal branch — dishonest, the run succeeded; a failed Grade reaches the
*failed-graders* branch, which names the grader and prints the detail through the
existing announce path; (3) zero changes in fixtures.py or __main__.py. Make the detail
unmistakably a refusal, e.g. `("the judge DECLINED to grade (stop_reason=refusal,
category=…): …explanation…")` — distinguishable downstream from both a genuine fail and
from malformed output, which **keeps raising** `ValueError` (a crash is noticed; a wrong
score is trusted — ADR-0010's carried-forward argument). The cleanest implementation:
`verdict()` returns a third shape or the graders check a sentinel — but the smallest
honest one is `verdict()` returning `(False, "the judge declined …")` with the refusal
prefix contractual and pinned by test. Whether `max_tokens` (truncated JSON → also
"unparseable" today) gets its own honest message is discretionary; if cheap, guard it
with a distinct detail rather than letting truncation masquerade as malformation.

## Finding 4 — The test inventory (HIGH; every entry read this session)

All in `tests/test_evals.py` unless noted. Baseline: the 16 `-k judge` tests pass today
(run this session); full suites 735/65 plain, 799/1 armed; offline evals 41/41 keyless.

**Red or wrong after a naive flip — the plan must own each:**

| Test / seam | Line | What happens |
|-------------|------|--------------|
| `test_judge_critic_collision_warning_points_at_a_record_that_exists` | :2560 | **REDS when the supersession convention is applied.** It asserts `"supersedes ADR-0005" in` ADR-0010's text — that phrase lives only in 0010's status line (`**Status:** Accepted — supersedes ADR-0005`), which convention step 1 *replaces* with `Superseded by ADR-0012 (Phase 18)`. Extend the test to hold the full chain (0005 → 0010 → 0012, each status line agreeing) in the same commit as the status flip — this is the 16-03 lesson's test; it must keep holding both halves of every supersession it names |
| `test_judge_critic_collision_warning_fires_once_per_run` | :2516 | Stays mechanically green (`FakeJudge(model="claude-opus-5")` hardcoded + `CRITIC_MODEL=claude-opus-5` monkeypatched) but its docstring claim "this is the DEPLOYED configuration, not a contrived one" becomes **false** — after the flip it *is* contrived. Keep the mechanism test; fix the prose; add the silent-at-new-defaults twin (below) |
| `test_judge_critic_collision_warning_states_a_fact_not_a_fault` | :2540 | Same inversion, sharper: it *requires* the words `"accepted"` and `"deployed"` in the stderr line. A collision is no longer the deployed configuration — the honest wording changes, so this test's required tokens change with it. Per 16-02, the wording is the deliverable: decide what the line now says (an operator-created collision, still legal, still not a fault) and where it points (ADR-0010 is about to be superseded — pointing an operator at a superseded record from a live warning needs a deliberate decision; the natural pointer is ADR-0012) |
| Preview tests priced off the real table | :2392 (`test_record_preview_requotes_itself_when_the_rate_window_flips` computes `judge_leg(case, usage.price_for(G.JUDGE_MODEL, …))`), :2404 (`test_record_preview_lands_in_the_researched_range`) | **Raise `UnknownModelPricing` if the default flips before the PRICES row exists.** Same-commit ordering: row + flip together (or row first) |
| `FakeJudgeClient` | :570 | Its `Response` has only `.content`. The moment `verdict` reads `response.stop_reason`, every test built on it **AttributeErrors**. It must grow `stop_reason="end_turn"` (and `stop_details=None`), plus a refusal-shaped twin for the new guard tests |
| `test_the_judge_runs_on_a_different_model_than_the_pipeline` | :606 | Stays green (`claude-opus-4-8` ≠ `claude-sonnet-5`). The phase owes a **sibling pin for the new independence**: judge ≠ the *production* critic. Beware the 16-02 neutral-default blind spot — comparing `G.JUDGE_MODEL != graph.critic_model()` in a suite that never sets `CRITIC_MODEL` compares against `graph.MODEL` and proves nothing about production. The honest comparison is against the deployed pin: fly.toml's parsed `[env]` `CRITIC_MODEL` (the idiom of `tests/test_deploy_config.py:208`, `CRITIC_MODEL_PIN = "claude-opus-5"`). Flip-the-default-back is the mutation that must red it |
| `test_judge_raises_on_an_unparseable_verdict` | :598 | Must stay green — malformed-with-normal-stop still raises. It is the discriminator between refusal and malformation |

**Value-agnostic — will follow the constant without edits (verify, don't touch):**
`MODELS = {"pipeline": graph.MODEL, "judge": G.JUDGE_MODEL}` (:1027); missing-role
fixtures (:1126, :1177); `fake_price_for` keyed on `G.JUDGE_MODEL` (:2221);
`test_record_preview_names_a_model_it_cannot_price` (:2411 — monkeypatches
`G.JUDGE_MODEL` to `claude-opus-9`); the live-shaped record test (:2775, :2808 —
compares `kwargs["model"] == G.JUDGE_MODEL` and `fixture["models"]["judge"] ==
G.JUDGE_MODEL`). Note: `test_record_writes_a_fixture_per_case_with_fakes` (:2485)
asserts `"judge": "claude-opus-5"` — that is **FakeJudge's hardcoded model**, not
`JUDGE_MODEL`, so it stays green; updating FakeJudge's default to something
obviously-fake or to `G.JUDGE_MODEL` is discretionary hygiene.

**tests/test_usage.py — the new row passes everything as specified, nothing else moves:**
`test_cache_rates_are_multiples_of_the_input_rate` (:67) loops all PRICES rows —
6.25 = 5×1.25, 0.50 = 5×0.1 ✓; `test_no_model_has_overlapping_or_gapped_windows` (:57),
`test_window_for_reports_every_real_model_as_open_ended` (:142),
`test_next_window_is_none_for_every_shipped_model` (:170) all loop the table — a single
undated window satisfies all three. **The synthetic `fixture-two-window-model` table
(:105–123, installed per-test by the `dated_model` fixture, added 2026-08-12 when
Sonnet's introductory rate became permanent) is untouched by a new real row — do not
disturb it.** A direct pin (`price_for("claude-opus-4-8")` → 5.0/25.0/6.25/0.50) is the
phase's own gate; the loops alone would pass with the row absent.

**tests/test_deploy_config.py:208** (`test_the_critic_model_pin_is_intact`) — critic
only, untouched. Its failure message cites "docs/adr/0010-… supersedes", which remains a
true historical statement.

## Finding 5 — The doc/prose inventory asserting judge == critic (HIGH)

Per the 16-03 corollary: this grep inventory **locates neighbourhoods, it does not
enumerate sentences** — the plan must mandate whole-file reads of each named file, and
the 17-04 rule (grep the ADR index for every sentence that *counts, forecasts or
enumerates*) applies to docs/adr/README.md.

| Surface | Location | What inverts |
|---------|----------|--------------|
| `evals/graders.py` module docstring | :13–19 | "in production the judge and the critic run on the same model. That is accepted rather than accidental, and recorded… in ADR-0010" — rewrite for judge ≠ critic, point at ADR-0012 |
| `evals/harness.py` `_state_judge_critic_relation` | :633–667 | Docstring: "JUDGE_MODEL defaults to claude-opus-5 and Phase 16's cutover pins CRITIC_MODEL to claude-opus-5 too… Every record run made against production's configuration sees this line" — all false after the flip. Message body: "This is the deployed configuration and it is accepted, recorded in ADR-0010" — re-derive |
| `docs/OPERATIONS.md` | :798–806 | "A record run made against production's configuration also prints one line noting that the judge and the critic share `claude-opus-5`; that is a statement… accepted one (ADR-0010)" — the premise inverts: at the new defaults no line fires on a production-shaped record run. Rewrite the paragraph. (The env table at :645 documents `CRITIC_MODEL` only; whether `EVAL_JUDGE_MODEL` earns a row is discretionary — it is an evals-CLI knob, not a service env var, and no doc surface currently documents it outside the ADRs) |
| `docs/DESIGN.md` | :76 | Historical paragraph already framed as "the argument as it stood", with a supersession trailer ending at ADR-0010 ("the judge's rationale is re-derived there"). Extend the trailer to ADR-0012 — the judge no longer "runs on Opus 5", and the rationale's home moves |
| `docs/adr/README.md` | :44–49 + index rows | Three stale paragraphs minimum (17-04 lesson — a supersession stales *counting, forecasting and enumerating* prose): "Eight of the eleven records are `Accepted`" → twelve records, still eight accepted (+0012 accepted, −0010 flipped); "Three supersessions have actually happened" → four; "**each was forecast by the record it overturned**" → false for this one (ADR-0010 carries no Expected-reversal section — the register was closed as spent); "the reversal register in `.planning/ROADMAP.md` is spent: every supersession in the table below is now a fact, and no row carries an *expected* one any more" → rewritten: the register was reopened, deliberately, by ADR-0012, which says so. Also the *Reading a superseded record* prose if it enumerates records by name (17-04 found it does). Index rows: new 0012 row; 0010's Status and Superseded-by cells |
| `docs/adr/0010-…md` | :3 | Status line only: `**Status:** Superseded by ADR-0012 (Phase 18)` — body never edited. **This is the edit that reds tests/test_evals.py:2560** (Finding 4). ADR-0005 untouched (`Superseded by ADR-0010 (Phase 16)` stays) |
| `README.md` | :285 | The Limitations bullet — **Phase 22 deletes it; this phase does not touch it.** Note the transient contradiction for the phase records: between 18 and 22 the README bullet says "the eval judge shares the critic's model" while the tree says otherwise. :32 and :47 are historical phase-log bullets (true as written at their time — the 16-03 convention tolerates these); :21's stack line names no judge |
| `evals/__main__.py` | :227–242 | Preview comments reference judge constants and the critic quote correction — read the neighbourhood; nothing found asserting judge == critic, but the whole-file rule applies |

**ADR-0012 content requirements (from CONTEXT + REQUIREMENTS, assembled):** supersedes
ADR-0010's *judge == critic is an acceptance* position only; states that
*critic stronger than writer* stands untouched; states plainly that it **reopens the
reversal register v1.1 closed as spent**; states the accepted residual in the record's
own voice — Opus 4.8 is the critic's model *family*, so independence is model-identity,
the same honest narrowing ADR-0010 made; carries a `### Carried forward` section
(12-06 convention) for what survives of 0010 (the different-job leg, judge ≠ writer,
structured verdict, `EVAL_JUDGE_MODEL` as the override, the critic's flip untouched);
records why Fable 5 was declined (presented and declined: ~2× judge leg, 30-day
retention requirement, hotter refusal classifiers — [ASSUMED: the retention/classifier
characterization is the user's stated reasoning from milestone questioning, not
re-verified here]); and zero cost change stated against the verified price identity.

## Finding 6 — Pricing, verified today (HIGH)

[CITED: platform.claude.com/docs/en/about-claude/pricing, fetched 2026-08-13]

| Model | Input | 5m cache write | Cache read | Output |
|-------|-------|----------------|------------|--------|
| claude-opus-4-8 | $5 | $6.25 | $0.50 | $25 |
| claude-opus-5 (today's judge) | $5 | $6.25 | $0.50 | $25 |
| claude-sonnet-5 (writer) | $2 | $2.50 | $0.20 | $10 |
| claude-fable-5 (declined) | $10 | $12.50 | $1 | $50 |

- Zero cost change is **exact**, to every token class — and the "~2× judge leg" figure
  for the declined Fable option is confirmed by the table.
- The new row: `PriceWindow(Price(input=5.0, output=25.0, cache_write_5m=6.25,
  cache_read=0.50))`, single, undated — byte-identical in shape to opus-5's row. It
  satisfies the cache-multiple pin (1.25×/0.1×) by construction.
- The Sonnet-introductory note is re-confirmed permanent ("the previously scheduled
  increase… will not occur") — the usage.py comment at :89–92 remains correct.
- Web search fee $10/1,000 re-confirmed; matches `WEB_SEARCH_USD_PER_REQUEST`.
- The 40-case quote is unchanged by the flip (same judge rate), so REQUIREMENTS'
  "$17.48 quoted 2026-08-13; re-quote at run time" is not staled by this phase.

## Runtime State Inventory

This is a default-flip phase; the grep-finds-files trap applies. All five categories
answered explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `evals/fixtures/technical-figures.json` — `models: {"pipeline": "claude-sonnet-5", "judge": "claude-opus-5"}`, recorded 2026-08-10 at `225b06b` (verified by loading it this session). The old judge name is *committed data* | **None, by design** — `grade_fixture_current` never compares the judge role (Finding 3), the recorded verdicts replay as fixed data, and ADR-0010's Accepted list plus the harness docstring (pinned by test :1896) state exactly this. The plan states it in the phase records rather than leaving it folklore |
| Live service config | fly.toml `[env]`: `CRITIC_MODEL=claude-opus-5` only — **no** `EVAL_JUDGE_MODEL` anywhere in fly.toml, `.env.example`, or `.github/` (grepped this session). The evals CLI never runs in the deployed container | None — there is no deployed judge configuration to migrate |
| OS-registered state | None — the evals are an operator-invoked CLI; no scheduled tasks, no services (verified: nothing in the repo registers them) | None |
| Secrets/env vars | `EVAL_JUDGE_MODEL` is set nowhere in the tree or CI; operators may have it exported in a shell, in which case it overrides the new default — which is the documented contract, not a migration | None; discretionary extra pinning of the override behavior is the CONTEXT's third discretion item |
| Build artifacts | None — no compiled artifacts carry the model name | None |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Refusal detection | Sniffing empty `content` or matching refusal phrasings in text | `response.stop_reason == "refusal"` + `response.stop_details` | The API states the fact in a typed field; text-sniffing is exactly the mis-parse-into-confident-wrong-number failure ADR-0010 carries forward |
| Judge-run costing | Any constant or arithmetic outside usage.py | A PRICES row + `price_for` | DEC-12: unpriced fails loud; effective-dating and multipliers already live there; the preview already resolves at run time |
| A second recorder refusal path | A new refusal channel for judge refusals | `_refuse_failing`'s failed-grades branch via a failed Grade | 15-01: the recorder's refusal is one code path, deterministic or judge; a parallel path is a second source of truth |
| Supersession mechanics | Any bespoke record-editing | docs/adr/README.md's verbatim three-step convention | The convention is itself pinned by tests and by the 17-04 index-checker discipline |

**Key insight:** every mechanism this phase needs already exists — the phase is pointing
existing machinery at a new model name and making one response boundary honest.

## Common Pitfalls

### Pitfall 1: The PRICES row must not land after the flip
**What goes wrong:** `tests/test_evals.py:2392` and `:2404` price `G.JUDGE_MODEL`
against the real table; the flip without the row raises `UnknownModelPricing` in the
suite, and every real `--live`/`--record` run dies on preview.
**How to avoid:** row and flip in the same commit, or row first. **Warning sign:** any
plan wave that touches graders.py:33 without touching usage.py.

### Pitfall 2: The :2560 test reds on the ADR-0010 status-line edit
**What goes wrong:** the supersession convention replaces 0010's status line, deleting
the only occurrence of `"supersedes ADR-0005"` in that file;
`test_judge_critic_collision_warning_points_at_a_record_that_exists` asserts it.
**How to avoid:** extend the test to hold the three-record chain in the same commit as
the status flip. This is also the phase's chance to apply the test's own lesson to
ADR-0012: whatever operator-facing line ends up naming ADR-0012 needs the
record-exists/status-agrees assertion extended, not duplicated.

### Pitfall 3: `FakeJudgeClient` has no `stop_reason`
**What goes wrong:** the guard reads `response.stop_reason`; the fake's `Response` has
only `.content` → AttributeError across every existing verdict test.
**How to avoid:** give the fake `stop_reason="end_turn"`, `stop_details=None` as part of
the guard's wave; add the refusal twin (`stop_reason="refusal"`, `content=[]`,
`stop_details` with category/explanation) for the new tests.

### Pitfall 4: `Judge.__init__`'s default binds `JUDGE_MODEL` at class-definition time
**What goes wrong:** `def __init__(self, client, model: str = JUDGE_MODEL)` freezes the
default when the module loads; a test that monkeypatches `G.JUDGE_MODEL` and then
constructs `Judge(client)` gets the *old* string. Existing tests dodge this (they patch
module attribute reads like `_assumed_judge_cost`, or pass fakes), but a new
independence pin written naively against a monkeypatch would assert nothing.
**How to avoid:** pin the default at the constant (`G.JUDGE_MODEL == "claude-opus-4-8"`
…or better, the fly.toml-comparison shape below) and test override behavior through the
env var at import seam only if the discretionary pinning is taken up.

### Pitfall 5: The neutral-default blind spot on the new independence pin
**What goes wrong:** `assert G.JUDGE_MODEL != graph.critic_model()` in a keyless suite
compares against `graph.MODEL` (CRITIC_MODEL unset) — green forever, guarding nothing
about production. 16-02's exact lesson.
**How to avoid:** compare against the deployed pin — parse fly.toml `[env]`
`CRITIC_MODEL` (idiom exists at tests/test_deploy_config.py:208) — and observe the pin
red by flipping the default back to `claude-opus-5`.

### Pitfall 6: The collision-warning wording tests pin words whose truth inverts
**What goes wrong:** `:2540` *requires* "accepted" and "deployed" in the stderr line;
after the flip a collision is neither. Leaving the tests green-by-hardcoded-fake while
the wording stays would ship a line that misinforms the operator on the one run they
read it.
**How to avoid:** treat the message as a deliverable (16-02): re-derive what a collision
now means (operator-created, legal, not the shipped default), decide the ADR pointer
(0012), rewrite the wording tests to require the new facts, and add the
silent-at-new-defaults twin: `FakeJudge(model=G.JUDGE_MODEL)` +
`CRITIC_MODEL=claude-opus-5` → no line.

### Pitfall 7: Grep inventories under-count; whole-file passes mean counting
**What goes wrong:** 16-03 grep-audited the dead premise three times and still missed a
docstring phrasing; 17-04 found stale spelled-out counts nobody had reason to grep for.
**How to avoid:** the plan mandates whole-file reads of graders.py's header,
harness.py:520–700, OPERATIONS' evals/record section, DESIGN.md § Testing, and the
entire ADR index — and greps the index for number words and for every sentence that
counts, forecasts, or enumerates. Plan-stated arithmetic (twelve records, eight
accepted, four supersessions) is a claim to check against the table, not a spec.

### Pitfall 8: A refusal guard that raises gets mislabelled as a run error
**What goes wrong:** any exception from grading lands in `run_case`'s blanket `except`
(harness.py:334) → `result.error` → the recorder's "the run errored" branch — blaming a
successful paid run and burying the refusal.
**How to avoid:** surface the refusal as a failed Grade (Finding 3's recommendation);
keep `ValueError` for genuinely malformed output.

## Code Examples

### The guard (shape verified against SDK 0.120.0 field names)

```python
# evals/graders.py — inside Judge.verdict, before reading content
response = self.client.messages.create(...)
if response.stop_reason == "refusal":
    details = getattr(response, "stop_details", None)
    reason = "the judge DECLINED to grade this case (stop_reason=refusal"
    if details is not None:
        reason += f", category={details.category}"
        if details.explanation:
            reason += f"): {details.explanation}"
        else:
            reason += ")"
    else:
        reason += ")"
    return False, reason   # a graded finding; NOT a ValueError
text = "".join(b.text for b in response.content if b.type == "text")
# ... existing parse; malformed output still raises ValueError
```

(Exact composition — tuple vs. richer return — is Claude's discretion; the contract to
pin is: refusal → failed verdict with a detail that names the refusal; malformed →
still raises; `end_turn` + valid JSON → unchanged.)

### The price row

```python
# src/research_agent/usage.py, in PRICES — verified against
# platform.claude.com/docs/en/about-claude/pricing, 2026-08-13
"claude-opus-4-8": [
    PriceWindow(Price(input=5.0, output=25.0, cache_write_5m=6.25, cache_read=0.50)),
],
```

### The refusal-shaped fake (for tests)

```python
class Block:
    type = "text"
    def __init__(self, text): self.text = text

class RefusedResponse:
    content = []                      # empty on refusal — the documented shape
    stop_reason = "refusal"
    class stop_details:
        type = "refusal"
        category = "general_harms"
        explanation = "declined by safety classifier"
# and every non-refusal fake gains: stop_reason = "end_turn"; stop_details = None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `output_format` beta param + `structured-outputs-2025-11-13` header | `output_config.format`, GA, no header | pre-2026-08 (transition period ongoing) | The code already uses the GA shape; nothing to migrate |
| Judge == critic (`claude-opus-5` both), accepted in ADR-0010 | Judge on `claude-opus-4-8`, independent by model identity | This phase | The whole inventory above |
| Sonnet-5 introductory pricing expiring 2026-09-01 | Permanent (announced 2026-08-12) | Already absorbed by the tree (usage.py comment, synthetic two-window test table) | No dated windows anywhere; do not reintroduce one |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project `.venv`; bare `pytest`/`ruff` not on PATH) |
| Config file | none dedicated; suite under `tests/`, evals CLI under `evals/` |
| Quick run command | `.venv/bin/pytest tests/test_evals.py -q` |
| Full suite command | `.venv/bin/pytest -q` (baseline 735 passed / 65 skipped plain) + `.venv/bin/python -m evals` (41/41, keyless) + `.venv/bin/ruff check .` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-judge… (default) | `JUDGE_MODEL` defaults to `claude-opus-4-8`, ≠ fly.toml's `CRITIC_MODEL` pin, ≠ `graph.MODEL` | unit | `.venv/bin/pytest tests/test_evals.py -k "different_model or independen" -q` | ❌ new pin needed (existing :606 stays; critic-independence sibling is Wave 0/plan work) |
| REQ-judge… (guard) | refusal → failed Grade with refusal-shaped detail; malformed → still raises; end_turn → unchanged | unit | `.venv/bin/pytest tests/test_evals.py -k "verdict or refus" -q` | ❌ refusal tests new; :592/:598 exist and must stay green |
| REQ-judge… (recorder flow) | a judge refusal reaches `_refuse_failing`'s failed-grades branch (named grader, honest reason), not "the run errored" | integration (fake-driven, keyless) | `.venv/bin/pytest tests/test_evals.py -k "record" -q` | ❌ new; record_with_fakes idiom exists |
| REQ-judge… (price row) | `price_for("claude-opus-4-8")` = 5/25/6.25/0.50; table invariants hold | unit | `.venv/bin/pytest tests/test_usage.py -q` | ❌ direct pin new; loops exist and pass by construction |
| REQ-judge… (ADR-0012) | record exists; chain 0005→0010→0012 status lines agree; index arithmetic derived from the table | unit (doc-shaped) | `.venv/bin/pytest tests/test_evals.py -k "points_at_a_record" -q` + index checker | ⚠️ :2560 exists and REDS on the status flip — extended, not new; index checker per 17-04 (derive from table, never grep the typed string) |
| REQ-judge… (collision line) | silent at new defaults; fires + honest wording on operator-created collision | unit | `.venv/bin/pytest tests/test_evals.py -k "collision" -q` | ⚠️ 5 tests exist; wording tests change deliberately; silent-at-new-defaults twin is new |
| REQ-judge… (fixture not staled) | offline suite stays 41/41; `grade_fixture_current` boundary docstring still pinned | integration | `.venv/bin/python -m evals` | ✅ exists (suite + :1896) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_evals.py tests/test_usage.py -q`
- **Per wave merge:** `.venv/bin/pytest -q` + `.venv/bin/python -m evals` + `.venv/bin/ruff check .`
- **Phase gate:** full suite + offline evals green (41/41), zero skip-delta unexplained, before `/gsd:verify-work`

### Mutation Probes (each gate observed red before trusted)
1. **Refusal guard, RED-first:** write the refusal test, run it against *current* code —
   observe it fail with `ValueError: … unparseable … ''` (the misleading path is the
   recorded red). Then implement; green. Then delete the `stop_reason` check — the test
   reds again on the ValueError, and *nothing else in the file* should red (the 15-06
   ungated-rule check).
2. **Independence pin:** flip graders.py:33 back to `"claude-opus-5"` — the new pin
   reds on the fly.toml comparison; :606 stays green (it never guarded this).
3. **Price row:** delete the `claude-opus-4-8` row — the direct pin reds; ALSO observe
   :2392/:2404 red with `UnknownModelPricing` (proves the ordering trap is real, once).
4. **Recorder flow:** drive `record_with_fakes` with a refusal-shaped judge — outcome is
   `written=False` with the refusal-named reason in `outcome.refusal`, file absent
   (15-01: a refused write leaves no file); mutate the guard away — the refusal case
   becomes "the run errored", which the test must distinguish (assert on the reason's
   content, not just `not written` — a reason-blind assertion is green under both).
5. **Collision silence:** `FakeJudge(model=G.JUDGE_MODEL)` + `CRITIC_MODEL=claude-opus-5`
   → stderr carries no collision line; mutate `_state_judge_critic_relation` to fire
   unconditionally — reds.
6. **Index checker:** per 17-04 probe A5 — move/edit a table row, leave prose alone; the
   checker (derived counts) reds where literal greps stay green.
7. **Doc gates:** measured baselines before every prose grep (14-03/13-04 lessons): the
   dead phrasings ("share `claude-opus-5`", "both run on claude-opus-5" in docs, "in
   production the judge and the critic run on the same model") measured >0 before the
   edit → 0 after; sentence-shaped, not word-shaped.

### Wave 0 Gaps
- [ ] Refusal-shaped fake responses (`FakeJudgeClient` gains `stop_reason`/`stop_details`; refusal twin) — covers the guard tests
- [ ] Critic-independence pin comparing against parsed fly.toml — covers the default flip
- [ ] `price_for("claude-opus-4-8")` direct pin — covers the row
- Framework install: none — everything runs on the existing `.venv`

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | evals CLI is operator-local; keys via env, unchanged |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (narrow) | The guard is response-boundary validation: typed `stop_reason` field, never text-sniffing; malformed JSON still fails loud (never scored) |
| V6 Cryptography | no | — |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Mis-parsed model output scored as a verdict | Tampering/Repudiation | Structured outputs + fail-loud parse (existing, ADR-0010 carried forward); refusal guard closes the remaining silent-ish path |
| Judge grades the same untrusted text the pipeline handled | Elevation (prompt injection) | Out of scope here; unchanged by the model flip — the injection-reads-critic finding remains an open STATE.md item owned elsewhere |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/pytest` | all gates | ✓ (16 judge tests ran green this session) | project venv | — |
| `anthropic` SDK | guard fields | ✓ | 0.120.0 (pinned; `stop_reason`/`stop_details` verified present) | — |
| `.venv/bin/ruff` | lint gate | ✓ (per Phase 10-05 record) | project venv | — |
| `.venv/bin/python -m evals` | offline suite | ✓ (keyless by design) | — | — |
| `ANTHROPIC_API_KEY` (operator) | optional live probe only | n/a for the phase | — | The phase is provable entirely offline; an **optional** one-verdict live probe (~$0.06 at 4K in/1.5K out) would convert Finding 1 from CITED to measured — the plan may offer it as a cheap operator checkpoint, defer-first-class per the Phase 15 record-run style |

**Missing dependencies with no fallback:** none.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A refused response never conforms to the requested json_schema (docs don't state it; entailed by "content empty or minimal") | Finding 2 | None for correctness — the guard runs before the parse either way |
| A2 | Per-model refusal-classifier rates (Fable "hotter" than Opus 4.8) — the user's stated reasoning at milestone questioning, not re-verified | Finding 5 (ADR-0012 content) | ADR-0012 should attribute this as the decision context, not assert it as measured fact |
| A3 | Opus 4.8 emits `stop_reason: "refusal"` in practice (the API contract includes it for all current models; docs foreground Fable/Opus 5) | Finding 2 | The guard is model-independent; if 4.8 never refuses, the guard simply never fires and the tests prove it via fakes |
| A4 | No operator shell or CI secret sets `EVAL_JUDGE_MODEL` (verified for the tree and `.github/`; a laptop shell cannot be grepped) | Runtime State Inventory | An exported override would mask the new default locally — the documented contract, worth one line in OPERATIONS if the discretionary pinning is taken up |

**Everything else in this document is [VERIFIED] against the tree/SDK this session or
[CITED] to platform.claude.com pages fetched 2026-08-13.**

## Open Questions

1. **Where does the collision line point after ADR-0010 is superseded?**
   - What we know: the line must keep naming a record that exists and whose status
     agrees (:2560's whole reason to exist); ADR-0010 will read "Superseded".
   - What's unclear: whether an operator-facing pointer to a superseded record is
     acceptable when the *fact being stated* (what colliding verdicts can claim) now
     lives in ADR-0012.
   - Recommendation: point at ADR-0012 and extend the record-exists test to the new
     target; planner decides final wording with the fact-not-fault constraints
     re-derived (the "accepted"/"deployed" required tokens change).
2. **Does `max_tokens` truncation get its own honest message?**
   - What we know: truncated JSON currently raises the same "unparseable" ValueError;
     adaptive thinking shares the 1500-token budget with the response on both old and
     new judge.
   - Recommendation: cheap to add a distinct detail alongside the refusal guard; purely
     discretionary — do not let it grow the phase.
3. **Should `EVAL_JUDGE_MODEL` gain a documented row anywhere?**
   - What we know: it is documented only inside ADRs today; it is an evals-CLI knob,
     not a service env var (fly.toml/`.env.example` correctly silent).
   - Recommendation: at most one line in OPERATIONS' record-run section while it is
     being rewritten anyway; not a requirement.

## Sources

### Primary (HIGH confidence)
- The tree itself, read this session: `evals/graders.py`, `evals/harness.py`,
  `evals/fixtures.py`, `evals/__main__.py`, `src/research_agent/usage.py`,
  `src/research_agent/service.py:900` (/pricing), `tests/test_evals.py` (all judge
  neighbourhoods), `tests/test_usage.py:30–180`, `tests/test_deploy_config.py:198–238`,
  `docs/adr/0010`, `docs/adr/0005` (status), `docs/adr/README.md`, `docs/OPERATIONS.md:770–830`,
  `docs/DESIGN.md:76`, `README.md`, `evals/fixtures/technical-figures.json` (loaded)
- Local SDK introspection, `anthropic==0.120.0` in the project venv: `Message` fields,
  `StopReason` literal, `RefusalStopDetails` fields
- platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-8 (redirects to
  whats-new-opus-5, which specifies Opus 4.8 behavior as its baseline): adaptive
  thinking on 4.8, effort ladder, availability, migration IDs, price parity
- platform.claude.com/docs/en/build-with-claude/structured-outputs: GA status,
  `output_config.format`, `claude-opus-4-8` on the model list
- platform.claude.com/docs/en/build-with-claude/handling-stop-reasons: refusal = HTTP
  200, empty/minimal content, `stop_details` refusal-only, full stop_reason table
- platform.claude.com/docs/en/about-claude/pricing: full model table (Opus 4.8 row),
  cache multipliers, web-search fee, Sonnet-permanent note, tokenizer note
- `.planning/milestones/v1.1-phases/16-independent-critic-model/16-RESEARCH.md`
  Finding 2 (prior verification of the same price row, 2026-08-10 — corroborating)

### Secondary (MEDIUM confidence)
- WebSearch corroboration of Opus 4.8 effort/adaptive-thinking support (DataCamp
  tutorial, LiteLLM day-0 post) — consistent with the official pages above

### Tertiary (LOW confidence)
- None relied upon.

## Metadata

**Confidence breakdown:**
- API compatibility & refusal semantics: HIGH — official docs + pinned-SDK introspection agree
- Seam/test/doc inventory: HIGH — every entry read this session, with line numbers; but per the 16-03 corollary the inventory *locates neighbourhoods* — the plan must still mandate whole-file passes
- Guard design recommendation: HIGH on the constraint analysis (traced propagation), discretionary on the final shape by CONTEXT's own terms
- ADR-0012 content list: HIGH on requirements assembly; the Fable-decline rationale is attributed, not re-verified (A2)

**Research date:** 2026-08-13
**Valid until:** ~2026-09-12 for API/pricing claims (stable, GA surfaces); the tree
claims are valid until the next merge touching evals/ or docs/adr/
