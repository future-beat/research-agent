---
phase: 16-independent-critic-model
plan: 01
subsystem: graph
tags: [per-node-model, cost-attribution, env-config, neutral-default, gate-discipline]

# Dependency graph
requires:
  - phase: 16-independent-critic-model
    plan: "research"
    provides: "Finding 1 — the four naming sites in call_model, and the correction that attribution is a passed constant rather than a response echo"
provides:
  - "graph.critic_model() — CRITIC_MODEL read per call, unset/blank means graph.MODEL"
  - "call_model(state, node, *, model=None, **kwargs) — keyword-only, resolved once, used at all four naming sites (span, API call, record, log)"
  - "critic_node passing model=critic_model(); every other node's call site byte-identical"
  - "FakeClient.calls_with_kwargs — the full request payload per call, so a mis-threaded model is observable at all"
  - "The misbilling discriminator: an unpriced CRITIC_MODEL fires pricing_unknown only if the threaded name reached record()"
affects: [16-02, 16-03, 16-04, VALIDATION rows 1-4]

# Tech tracking
tech-stack:
  added: []  # no packages installed (RESEARCH Package Legitimacy Audit: not applicable)
  patterns:
    - "Read operator config per call, never cached at module scope — the sessions_token idiom. A module-level read freezes the value at import, so an operator changing configuration would not change what the process does."
    - "When a value is named at N sites inside one function, resolve it once at the top and assert each of the N sites separately. Threading N-1 of them is a silent-wrong-answer bug, not a crash."
    - "Prove a neutral default with payload equality against the same value set explicitly, not with prose. Unset and set-to-the-same-value must produce identical requests."
    - "Exact-dollar assertions only against UNDATED price rows, and measured as a difference between two runs so the dated remainder cancels."
    - "When the fakes ignore the field under test, the probe that matters is: does the whole pre-existing suite stay green under the mutation? Here all twenty did."

key-files:
  created: []
  modified:
    - src/research_agent/graph.py
    - tests/test_graph_smoke.py

key-decisions:
  - "critic_model() lives beside MODEL (graph.py:51), above the client builders, not next to critic_node. The accessor is configuration, and 16-02's fixture gate is its second consumer — burying it in the node section would read as node-local."
  - "The record-site assertion is measured against an UNPRICED critic rather than against an unset one. An unpriced critic contributes exactly $0.00 (record() catches UnknownModelPricing and returns 0.0), so the gap between the two runs is the critic call and nothing else — no Sonnet rate enters the arithmetic. Comparing against unset would have put a dated rate in the subtraction."
  - "The log-site test turns propagation on for the duration (monkeypatch.setattr(graph.log, 'propagate', True)) rather than replacing graph.log with a recorder. The agent logger sets propagate=False deliberately, and a fake logger would test that call_model calls something, not that the real log line carries the right model."
  - "Six mutation probes were run, not the plan's three. The plan named record/create/cached-accessor; the span and log sites had no probe, and a threading test whose mutation is never observed is exactly the vacuous-gate failure this project has hit sixteen times. Probes 4 and 5 each red exactly one test."
  - "No RED gate commit. Task 2 is marked tdd=\"true\" but the plan sequences implementation (Task 1) before tests (Task 2), so all fifteen tests were green on first run. The mutation probes are the substitute evidence and are stronger: each names the exact line whose reversion reds it."

# Metrics
duration: 38min
completed: 2026-08-10
---

# Phase 16 Plan 01: The critic's own model, threaded through all four naming sites Summary

**One-liner:** `graph.critic_model()` reads `CRITIC_MODEL` per call and `call_model` now resolves a keyword-only `model` once and uses it at every one of the four places it names a model — the span, the API request, the cost record and the log line — proven by six mutation probes in which reverting any single site reds exactly the tests that site owns, and by the fact that all twenty pre-existing smoke tests stay green under every one of them.

## What was built

### Task 1 — `critic_model()` and the four-site threading (commit `aec6491`)

`import os` added (`graph.py` had no use for it before). `critic_model()` at **graph.py:51**, beside `MODEL`:

```python
return os.environ.get("CRITIC_MODEL", "").strip() or MODEL
```

Read on every call. No validation past strip-or-default — an unknown-but-real model must be *allowed*, because pointing the critic at any model is the feature; a model with no price row is `pricing_unknown`'s job (DEC-12), not the accessor's. A whitelist would need maintaining against every model release and would refuse runs it has no business refusing.

`call_model` becomes `call_model(state, node, *, model: str | None = None, **kwargs)`. Keyword-only, so all four other call sites (`classifier`, `researcher`, `writer`, `responder`) are textually unchanged. `model = model or MODEL` resolves once at the top; the local is then used at all four sites. `critic_node` passes `model=critic_model()` and is the only call site that changed.

**The premise this rests on, restated because it is the whole reason the threading is four-way and not one-way:** cost attribution here is a *passed constant*. `CallUsage.from_response` never reads `response.model` — only `inference_geo` is response-observed. So `record(state["usage"], call, MODEL)` left behind would have billed an Opus critic at Sonnet rates, 2.5× under, with no error, no warning and no failing test anywhere in the tree.

### Task 2 — the four discriminating families (commit `f677152`)

`FakeClient` gained `calls_with_kwargs` — the full `create()` kwargs per call, two lines, no behaviour change; `self.calls` is untouched so the twenty existing tests never see it.

Fifteen new tests in four families. Every run uses a **fresh `FakeClient` and a fresh `InMemoryStore`** (helper `_run`), because a second run against the same store recalls the first run's notes, which changes the researcher's prompt — a payload-equality test would then fail for a reason that has nothing to do with the model.

## Line-number drift from the plan

The plan named the four sites at their pre-change lines (span :96, API :99, record :103, log :111). Adding `import os` and the 21-line accessor shifted everything. **The tree wins; recorded here:**

| Site | Plan | Actual |
|------|------|--------|
| `def critic_model` | — | graph.py:51 |
| `def call_model` | :84 | graph.py:106 |
| `model = model or MODEL` | — | graph.py:125 |
| span | :96 | graph.py:128 |
| `messages.create` | :99 | graph.py:131 |
| `record()` | :103 | graph.py:135 |
| log extra | :111 | graph.py:143 |
| `model=critic_model()` in critic_node | :409ff | graph.py:447 |

## Gate discipline

### `--collect-only` per selector — every one of the four collects

Run as `pytest tests/ --collect-only -q -k <selector>` (the whole `tests/` tree, not just the one file, so a selector that silently matched nothing elsewhere would still be visible):

| Selector (VALIDATION row) | Collected |
|---|---|
| `critic_model_accessor` (row 1) | **5** |
| `critic_threading_four_sites` (row 2) | **4** |
| `critic_misbilling_discriminator` (row 3) | **3** |
| `per_node_attribution` (row 4) | **3** |

15 new tests. All 15 pass.

### Measured suite deltas

| Leg | Baseline (2026-08-10) | After this plan | Delta |
|---|---|---|---|
| Plain (`.venv/bin/pytest`) | 663 passed / 65 skipped | **678 passed / 65 skipped** | +15 passed, **0 new skips** |
| Armed (`DATABASE_URL` → local PG :54329) | 727 passed / 1 skipped | **742 passed / 1 skipped** | +15 passed, **0 new skips** |
| Offline evals (`ANTHROPIC_API_KEY=""`, `CRITIC_MODEL` unset) | 41/41 keyless | **41/41 keyless** | unchanged |
| `ruff check src/ tests/` | clean | clean | — |

Every new test is a pass; **no skip was added and none needs justifying**. The evals leg was run with `env -u CRITIC_MODEL` to make the keyless invariant's precondition explicit rather than assumed.

### Mutation probes — six, not three

Each probe reverts exactly one line, runs the four families, then runs the twenty pre-existing tests in the same file, then reverts.

| # | Mutation | Families redded | Verdict |
|---|---|---|---|
| 1 | `record(..., model)` → `record(..., MODEL)` | `four_sites_c_reaches_the_cost_record`; `misbilling_discriminator` ×2; `per_node_attribution` ×2 | **Correct and informative.** Every cost-bearing assertion reds and no telemetry assertion does. The API, span and log tests stay green — which is the point: they cannot substitute for the cost one. |
| 2 | `messages.create(model=model)` → `model=MODEL` | `four_sites_a_reaches_the_api_payload`; `per_node_attribution_leaves_every_other_node_on_the_writers_model` | **Clean.** Only the two payload assertions. Cost, span and log stay green — so the API test is not redundant with the cost tests either. This is the "threads `record` but not `create`" bug, caught by nothing else. |
| 3 | accessor cached at module scope (`_CRITIC_CACHED = os.environ.get(...)`) | `accessor_returns_the_configured_model`; `accessor_reads_the_environment_on_every_call`; plus all of B, C's two set-env tests, and D | **Correct, with a wide blast radius that is itself the finding.** Caching freezes the accessor at `MODEL` for the process, so every test that sets the env var reds. The two accessor tests that expect `MODEL` (unset, blank) and the byte-identity test stay **green** — they are the neutral-default path, which caching does not break. That is the discrimination the plan asked for. |
| 4 | span `model=model` → `model=MODEL` | `four_sites_b_reaches_the_span` **only** | **Exactly one test.** |
| 5 | log `"model": model` → `"model": MODEL` | `four_sites_d_reaches_the_log_line` **only** | **Exactly one test.** |
| 6 | `critic_node` stops passing `model=critic_model()` | all four `four_sites_*`; `misbilling_discriminator` ×2; `per_node_attribution` ×3 | **Correct.** Removing the call-site pass is removing the feature; everything that observes it reds, and the neutral-default tests stay green because that is precisely the state this mutation restores. |

**The probe that says the most:** under probes 1, 2, 4 and 5, **all twenty pre-existing tests in `test_graph_smoke.py` stayed green.** RESEARCH Pitfall 3 said the fakes ignore `kwargs["model"]` so no existing test could catch mis-threading; that is now measured, not asserted. These fifteen tests are the entire coverage of the seam.

`git status` after the probe script: `src/research_agent/graph.py` clean, no probe leftovers. The probe script lives in the scratchpad, not the repo.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-16-01 | mitigate | **Closed.** `critic_misbilling_discriminator` ×3: unpriced critic → `pricing_unknown` True with `cost_usd` still > 0 and `calls == 4` (the call is counted, just not costed); unset → False; and the priced-vs-unpriced difference is exactly the critic call. Probe 1 reds all of it. `pricing_unknown` can flip only if the threaded name reached `record()` — the fakes ignore the model, so threading `messages.create` alone changes nothing here. |
| T-16-02 | mitigate | **Closed.** Four separate assertions, four separate probes, probes 4 and 5 each redding exactly one test. The span and the log line now agree with the invoice; telemetry that disagrees with the invoice is worse than no telemetry. |
| T-16-03 | mitigate | **Closed.** `accessor_unset_is_byte_identical_to_setting_it` compares the **full per-call kwargs dicts** — not just the model key, so the default path growing an extra kwarg would also red — between an unset run and a run with `CRITIC_MODEL` set to `graph.MODEL`, each against a fresh store. Plus the untouched 663-test baseline: 678 = 663 + 15, zero existing tests edited, zero new skips. |
| T-16-SC | accept | Re-verified: nothing installed. `pyproject.toml` untouched, no `pip`/`npm` invocation in this plan. |

**New threat surface: none.** No endpoint, no auth path, no schema change, no file access. `CRITIC_MODEL` is operator-to-billing input and is the boundary already registered as T-16-01/02.

## Deviations from Plan

### Additions beyond the plan (Rule 2 — missing critical verification)

**1. [Rule 2] Three extra mutation probes (4, 5, 6).** The plan's verification block named three probes: `record`, `messages.create`, and the cached accessor. The **span and log sites had no probe** — so two of the four site assertions this plan exists to make would have shipped with their mutations unobserved, which is precisely the vacuous-gate shape this project has hit sixteen times across seven phases. Probes 4 and 5 were added and each reds exactly one test. Probe 6 (the call site stops passing the model) was added because it is the mutation an author is most likely to make by reverting a merge conflict, and no listed probe covered it.

**2. [Rule 2] The "pre-existing tests stay green" leg of every probe.** Not in the plan. Without it, a probe redding the new tests is ambiguous — it might be redding them through some unrelated route, or an existing test might have been covering the seam all along, making a new test redundant. Measured: all twenty stayed green under probes 1, 2, 4 and 5.

**3. [Rule 2] Evals run with `env -u CRITIC_MODEL`.** Pitfall 4 says the keyless 41/41 invariant depends on `critic_model() == MODEL` in CI. Running the evals in a shell that merely happens not to export the variable proves less than running it in one where the variable is provably absent.

### Adjustments the plan left to discretion

**4. Probe 1 reds more than "only the misbilling family."** The plan anticipated this ("and possibly D's arithmetic"). Recorded honestly: it reds five tests across three families — every assertion that reads a dollar figure. That is correct behaviour, not over-broad coverage: `record()` is the only site that produces dollars, so a cost assertion that did *not* red under this probe would be the thing worth worrying about.

**5. `ruff` C416 on the span probe's dict comprehension.** Fixed inline (`dict(spans)`) before commit; caught by the repo's own lint, not shipped.

### TDD Gate Compliance

**Warning: no RED gate commit exists for this plan.** Task 2 carries `tdd="true"`, but the plan sequences the implementation (Task 1) before the tests (Task 2), so all fifteen tests were green the first time they ran — there was never a red to observe. The plan's own `<verify>` block anticipates this by demanding mutation probes instead, and those were performed: six probes, each naming the exact line whose reversion reds it, plus the negative control that no pre-existing test can. That is stronger evidence than a RED commit, which only shows a test failing before code exists; a probe shows *which* test fails for *which* line, after. Commits are `feat` then `test` rather than `test` then `feat`, and the gate sequence check will not find a `test(...)` commit preceding a `feat(...)` one.

## README and stale prose

**Nothing this wave falsifies.** Checked rather than assumed: `grep -rn "call_model\|CRITIC_MODEL" README.md docs/` returns **zero** hits — no prose anywhere names the function whose signature changed or the variable introduced. The README limitation at ~line 252 ("The critic shares the writer's model") remains **literally true of the deployed default**, which is the whole point of the neutral default, and its deletion is wave 3's per the standing instruction. No README pass was owed here and none was made.

## Requirements

`REQ-independent-critic-model` stays **Pending** in `REQUIREMENTS.md`. It carries five success criteria and this plan closes two of them (SC-1 configurability with a neutral default, SC-2 per-node attribution). SC-3 (the reservation threshold), SC-4 (ADR-0010 superseding 0005) and SC-5 (the README sentence) belong to waves 2–3, and the production cutover that makes any of it observable is wave 4. Checking the box here would make the traceability table assert a capability that is real in code and absent from the record and from production.

`roadmap.update-plan-progress 16` was run and, as expected, **blanked the notes cell**. The prior value was `-` so nothing was lost; the cell has been written by hand with wave 1's outcome. It also left `In Progress|` with no space before the pipe — repaired. Full diff of the tool's effect reviewed: two lines, the checklist tick at ROADMAP:312 and the progress row at :368, nothing else.

## Known Stubs

None. Two pieces of not-yet-exercised behaviour, stated rather than hidden:

- **No real model has ever been called with a `CRITIC_MODEL` set.** Everything here runs against `FakeClient`, which ignores the model it is handed — deliberately, since that is what makes the payload-capture test necessary. RESEARCH Pitfall 5 [ASSUMED] notes that `critic_node` sends `thinking={"type": "adaptive"}` and `output_config={"effort": "medium"}`, and an operator pointing `CRITIC_MODEL` at a model that rejects those gets a 400 → `retry_node` → failed run. This plan validates *pricing*, not *API compatibility*; the runbook note is 16-02's and the live proof is wave 4's.
- **`critic_model()` has exactly one consumer so far.** 16-02's fixture gate is its second, by design (RESEARCH Finding 5: "there is no `critic_model()` accessor today — the gate has nothing to compare against until graph gains one"). Nothing is stubbed; the second caller simply does not exist yet.

## Deferred Issues

- **`STATE.md`'s carry-into-execution list contradicted itself** and was corrected in this plan's state edit. One bullet read "Wave 4: one live run with `CRITIC_MODEL=claude-haiku-4-5` … production flip is NOT this phase's" — a pre-USER-DECISION line sitting directly beneath the USER DECISION that supersedes it (`CRITIC_MODEL = 'claude-opus-5'` in `fly.toml`, the flip IS the deliverable, haiku confined to unit tests). Left alone it was a landmine for whoever executes wave 4. Corrected to match 16-CONTEXT § USER DECISION and 16-VALIDATION rows 11–12.
- **`FakeClient` now records every payload for every test, not just the new ones.** Four dicts per run, discarded at teardown — immaterial, and noted only so the next person to touch the fake knows `calls_with_kwargs` is populated unconditionally rather than behind a flag.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `aec6491` | feat | The critic can run on its own model, named at all four sites |
| `f677152` | test | Four families that can tell the four naming sites apart |

## Self-Check: PASSED

- `src/research_agent/graph.py` — FOUND (modified; `def critic_model` ×1, `model=critic_model()` ×1, `model=MODEL` ×0)
- `tests/test_graph_smoke.py` — FOUND (modified; `critic_misbilling_discriminator` present ×3)
- `.planning/phases/16-independent-critic-model/16-01-SUMMARY.md` — FOUND (created)
- Commit `aec6491` — resolves in `git log`
- Commit `f677152` — resolves in `git log`
- Working tree clean apart from this summary and the state files it updates
