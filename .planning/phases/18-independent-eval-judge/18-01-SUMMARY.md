---
phase: 18-independent-eval-judge
plan: 01
subsystem: evals
tags: [judge-independence, price-table, deployed-pin, ordering-trap, gate-discipline]

# Dependency graph
requires:
  - phase: 18-independent-eval-judge
    plan: "research"
    provides: "Finding 3 (the seams), Finding 4 (the test inventory), Finding 6 (the verified rates), traps 1 and 5"
  - phase: 16-independent-critic-model
    plan: "02"
    provides: "the neutral-default blind spot lesson the independence pin is written against"
provides:
  - "evals/graders.py JUDGE_MODEL defaults to claude-opus-4-8 — the judge no longer shares the critic's model"
  - "usage.PRICES carries claude-opus-4-8 ($5/$25, 6.25/0.50), single undated window"
  - "test_the_eval_judges_model_is_priced — the direct four-rate pin the table-wide loops cannot supply"
  - "test_the_judge_runs_on_a_different_model_than_the_deployed_critic — independence measured against fly.toml's parsed [env], not the suite's neutral default"
  - "the measured fact that the record preview DEGRADES rather than dies on an unpriced judge (evals/__main__.py:287, :342)"
affects: [18-02, 18-03, 18-04, 21]

# Tech tracking
tech-stack:
  added: []  # zero packages installed (18-RESEARCH § Package Legitimacy Audit: nothing to audit)
  patterns:
    - "Pin an independence claim against the DEPLOYED value, never against a code default the suite neutralises. `graph.critic_model()` returns the writer's model in a keyless suite, so the obvious comparison is green forever and guards nothing about production."
    - "A pin that reads a config key must fail loud when the key is absent. `!= None` is true, so a regenerated fly.toml would silently convert this gate into a tautology."
    - "Two edits share one commit when the intermediate state has no loud failure to protect it — which is a claim to MEASURE, not to inherit from the research."

key-files:
  created: []
  modified:
    - src/research_agent/usage.py
    - evals/graders.py
    - tests/test_usage.py
    - tests/test_evals.py

key-decisions:
  - "The ordering trap is real but its stated mechanism was false, and the correction is the more alarming half. RESEARCH and the plan both say a flip landing before the row makes 'every real --live/--record run die on preview'. Measured: it does not. `_call_cost` and `_rate_line` catch UnknownModelPricing by design (15-05 — 'a traceback instead of a quote would be the worst of both'), so a --record run with the row missing quotes a $12.28 FLOOR with 'UNPRICED claude-opus-4-8' in the text and proceeds. The trap's real teeth are in the SUITE (test_evals.py:2392 prices G.JUDGE_MODEL in its own body and raises), and the real risk of the wrong order is a silently degraded quote missing an entire leg — worse to ship than a crash, and the stronger reason for one commit."
  - "test_record_preview_lands_in_the_researched_range is NOT a gate on the ordering trap. Under the deleted-row mutation it stays green at $12.28, comfortably inside its own 8.0–20.0 window. The plan and 18-VALIDATION both predict it reds; it does not, and a range assertion over a total that has lost a leg is exactly the kind of gate this project keeps discovering is decorative. Recorded rather than quietly dropped — 18-04's phase proof should not re-inherit the claim."
  - "The independence pin asserts the CONSTANT G.JUDGE_MODEL, never a Judge instance's model attribute. `Judge.__init__`'s `model: str = JUDGE_MODEL` default binds at class-definition time (pitfall 4), so a monkeypatched read would pin what a test arranged rather than what an import gets."
  - "The pin fails loud on a missing fly.toml as well as on a missing key, diverging from tests/test_deploy_config.py's module-level skip. That file is a check ON the deploy config and has nothing to say without it; this is a check on the judge's independence, which becomes unverifiable rather than merely unchecked — and an unverifiable independence claim that reports green is the failure mode the phase exists to remove."
  - "`import tomllib` sits in the third-party block, matching tests/test_deploy_config.py. Not a mistake: `target-version = \"py310\"` and tomllib is stdlib only from 3.11, so ruff's isort classifies it that way. Commented at the import so the next reader amends a stated reason instead of 'fixing' it."

# Metrics
duration: 22min
completed: 2026-08-13
---

# Phase 18 Plan 01: The judge's model, flipped and priced Summary

**One-liner:** `EVAL_JUDGE_MODEL` now defaults to `claude-opus-4-8` with its price row in the same commit, and the new independence is pinned against fly.toml's deployed `CRITIC_MODEL` rather than the suite's neutral default — the judge is independent of the critic by model identity, at a rate-identical cost, with the committed fixture demonstrably not staled (41/41 exit 0).

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:cacheprovider`) | 740 passed / 67 skipped | **742 passed / 67 skipped**, exit 0 | +2 passed, **+0 skipped** — exactly the two tests this wave added, no unexplained skip |
| `tests/test_usage.py` | 44 passed | 45 passed | +1 (the direct price pin) |
| `tests/test_evals.py` | 171 passed | 172 passed | +1 (the deployed-critic independence pin) |
| Offline evals (`ANTHROPIC_API_KEY="" .venv/bin/python -m evals`) | 41/41, exit 0 | **41/41 (100% vs 90% required), exit 0** | unchanged — the flip stales nothing |
| `.venv/bin/ruff check .` | clean | clean | — (two errors introduced and fixed inside the wave; see Deviations) |
| `price_for("claude-opus-4-8")` | `UnknownModelPricing` | `Price(5.0, 25.0, 6.25, 0.50)` | the row |

`.venv/bin/ruff check src tests evals` (the execution context's form) and `.venv/bin/ruff check .` (the plan's) were both run; both clean.

## What shipped

### Tasks 1 + 2 — one commit, `06140a4`

Deliberately one commit: `src/research_agent/usage.py` and `evals/graders.py` appear together in `git show --stat`, which is validation contract row 2.

```
06140a4 feat(18-01): judge defaults to claude-opus-4-8, priced in the same commit
 evals/graders.py            |  2 +-
 src/research_agent/usage.py |  9 +++++++++
 tests/test_evals.py         | 42 ++++++++++++++++++++++++++++++++++++++++++
 tests/test_usage.py         | 15 +++++++++++++++
```

- **`usage.PRICES` gains `claude-opus-4-8`** — a single undated `PriceWindow(Price(input=5.0, output=25.0, cache_write_5m=6.25, cache_read=0.50))`, structurally identical to the `claude-opus-5` row above it. No dated window; the Sonnet introductory window stays permanently gone. The comment states what the row is for and that the rate identity is what makes "zero cost change" exact rather than approximate.
- **`evals/graders.py:33`** — the default literal becomes `"claude-opus-4-8"`. Nothing else in that file changed; `EVAL_JUDGE_MODEL` still overrides, unchanged.
- **`test_the_eval_judges_model_is_priced`** (tests/test_usage.py) — reads all four rates directly off an undated `price_for`. The four table-wide loops pass by construction with the row absent, so this is the phase's own gate.
- **`test_the_judge_runs_on_a_different_model_than_the_deployed_critic`** (tests/test_evals.py) — parses `fly.toml` with `tomllib`, asserts `[env].CRITIC_MODEL` is present, then asserts the judge differs from it.

The synthetic `fixture-two-window-model` table (tests/test_usage.py:105–123) was not touched. The four table loops were run, not assumed: green, unmodified.

### Task 3 — the wave gate

Full suite, offline evals and ruff as above. Every test the plan predicted would move was verified by name rather than by aggregate:

```
PASSED test_the_judge_runs_on_a_different_model_than_the_pipeline
PASSED test_the_judge_runs_on_a_different_model_than_the_deployed_critic
PASSED test_record_preview_requotes_itself_when_the_rate_window_flips
PASSED test_record_preview_lands_in_the_researched_range
PASSED test_record_preview_names_a_model_it_cannot_price
PASSED test_record_writes_a_fixture_per_case_with_fakes
PASSED test_judge_critic_collision_warning_fires_once_per_run
PASSED test_judge_critic_collision_warning_is_silent_when_they_differ
PASSED test_judge_critic_collision_warning_states_a_fact_not_a_fault
PASSED test_judge_critic_collision_warning_points_at_a_record_that_exists
PASSED test_judge_critic_collision_warning_leaves_the_judgeless_refusal_intact
PASSED test_the_replay_model_gate_states_its_claim_boundary
```

Nothing outside the two new tests moved, as the inventory said.

## Mutation probes — each observed red, then reverted

### Probe 1 — flip the default back to `claude-opus-5`

```
FAILED tests/test_evals.py::test_the_judge_runs_on_a_different_model_than_the_deployed_critic
E   AssertionError: the eval judge and the deployed critic both run on 'claude-opus-5'.
    A recorded verdict is then independent of the writer's model and not of the
    critic's -- the arrangement ADR-0010 accepted and Phase 18 supersedes.
E   assert 'claude-opus-5' != 'claude-opus-5'
E    +  where 'claude-opus-5' = G.JUDGE_MODEL
PASSED tests/test_evals.py::test_the_judge_runs_on_a_different_model_than_the_pipeline
```

`:606` stays green under the mutation, which is the point: it never guarded critic-independence, and a phase that read its green as coverage would have shipped the flip ungated.

**Probe 1 was run twice.** Ruff's SIM300 required the comparison be rewritten as `deployed_critic != G.JUDGE_MODEL`, and a gate whose assertion has been re-typed is a gate that has not been observed red in the form it ships. Re-run against the reworded pin: same red, `:606` still green.

### Probe 2 — delete the `claude-opus-4-8` PRICES row

```
FAILED tests/test_usage.py::test_the_eval_judges_model_is_priced
E   research_agent.usage.UnknownModelPricing: No price for 'claude-opus-4-8' on 2026-08-13.
FAILED tests/test_evals.py::test_record_preview_requotes_itself_when_the_rate_window_flips
E   research_agent.usage.UnknownModelPricing: No price for 'claude-opus-4-8' on 2026-08-31.
PASSED tests/test_evals.py::test_record_preview_lands_in_the_researched_range
```

Two of the three predicted reds. The third is a finding, below.

## The ordering trap, measured — and half of its stated mechanism is false

The plan, 18-VALIDATION row 2 and 18-RESEARCH pitfall 1 all assert that a flip landing before the row makes "every real `--live`/`--record` run die on preview". **It does not.** `evals/__main__.py:287` (`_call_cost`) and `:342` (`_rate_line`) both catch `UnknownModelPricing` deliberately — 15-05's design, whose comment reads "A traceback instead of a quote would be the worst of both: no preview, and no idea why."

Measured with the row deleted and the flip in place:

```
total under the deleted row: 12.28
UNPRICED in text: True
FLOOR in text: True
```

So the honest statement of the trap is:

1. **In the suite** it is real and loud: `test_evals.py:2392` calls `usage.price_for(G.JUDGE_MODEL, …)` in its own body and raises, as does the new direct pin. Two reds, quoted above.
2. **In a real record run** it is real and *quiet*: the operator gets a $12.28 FLOOR that is silently missing an entire leg, with `UNPRICED claude-opus-4-8` printed further up. A degraded quote nobody reads as degraded is worse to ship than a crash — which strengthens the one-commit rule rather than weakening it.
3. **`test_record_preview_lands_in_the_researched_range` is not a gate on this at all.** Its window is `8.0 < total < 20.0`; the leg-less $12.28 sits comfortably inside it. It stays green under the mutation.
4. The judge leg is priced **nowhere but the preview** — `grep` for `price_for`/`cost_usd`/`UnknownModelPricing` across `evals/` finds no judge-side pricing outside `evals/__main__.py`; only pipeline spend flows through `usage.record`. There is no third consumer to fail loud.

Fifth-plus occurrence of the house rule: **a plan's stated arithmetic — and its stated failure modes — are claims to check against the tree.**

## The committed fixture did not stale — the reason, not the folklore

Validation row 7, measured: **offline evals 41/41, exit 0, immediately after the flip.**

The reason, read out of the code rather than restated from the plan: `grade_fixture_current` (evals/harness.py) compares `models.get("pipeline")` against `graph.MODEL` and `models.get("critic") or pipeline` against `graph.critic_model()`. It never reads the judge role. Its docstring says so in its own Cannot-catch paragraph — *"The JUDGE's is recorded and deliberately not checked — its verdicts are fixed data in the fixture, replayed as `recorded_*` grades, so pointing `JUDGE_MODEL` somewhere new does not invalidate a word of what the old judge already said; it changes only what a fresh recording would claim"* — and `test_the_replay_model_gate_states_its_claim_boundary` pins that boundary. It is green in the full run.

`evals/fixtures/technical-figures.json` still carries `"judge": "claude-opus-5"` at line 7. That is a recording of which model produced those verdicts on 2026-08-10, not a comparison input. It is correct as written and must not be "fixed".

## Deviations from plan

### [Rule 3 — blocking] Two ruff errors in the new test, fixed inside the wave

`.venv/bin/ruff check .` failed on the new code with `I001` (import block unsorted) and `SIM300` (Yoda condition). Both are in `tests/test_evals.py`, both introduced by this wave, both fixed:

- `import tomllib` moved into the third-party block to match `tests/test_deploy_config.py`, with a comment stating why (`target-version = "py310"`; tomllib is stdlib only from 3.11).
- The assertion rewritten as `deployed_critic != G.JUDGE_MODEL`, and **probe 1 re-run against the new form** rather than the red being carried over from the old one.

The fix was folded into `06140a4` by amend (unpushed, remote branch still at `0da3da5`), so the plan's one-commit requirement stays intact rather than being satisfied by a commit that then needed a follow-up.

### [Rule 1 — the record must not carry a false claim] The commit message was corrected

The first draft of `06140a4`'s message repeated the plan's "every real `--live`/`--record` run would die at the preview". Having measured that false, the message was rewritten in the same amend to state what actually happens ($12.28 FLOOR, silently missing a leg) and why that is the stronger argument for one commit. A commit message is a record; shipping a measured-false claim in one is the failure this project's discipline exists to prevent.

### [line anchors] The plan's line numbers had drifted; the real ones were used

The plan cites the two live-table preview tests as `:2359` and `:2398`; in the tree they are **`:2392`** (`test_record_preview_requotes_itself_when_the_rate_window_flips`) and **`:2398`** (`test_record_preview_lands_in_the_researched_range`) — 18-RESEARCH's `:2392`/`:2404` was closer but also off by one test. The plan's `:2483`/`:2485` for `test_record_writes_a_fixture_per_case_with_fakes` likewise disagree with each other. Located by name, not by number; all verified green.

### [not a deviation, stated to be explicit] Nothing else was touched

README's Limitations bullet (`:285`, Phase 22's), the critic, `fly.toml`'s `[env]`, and `graders.py` beyond line 33 are all unmodified. No packages were installed. Plans 18-02/03/04 were not started.

## Open transients this wave deliberately leaves

Each is owned by a later plan; none is a defect introduced here, all are premises that inverted the moment the default flipped:

| Transient | Where | Owner |
|-----------|-------|-------|
| Module docstring still says "in production the judge and the critic run on the same model… recorded in ADR-0010" | `evals/graders.py:13-19` | 18-04 |
| Collision docstring and stderr message still assert judge == critic is "the deployed configuration" and "accepted" | `evals/harness.py` `_state_judge_critic_relation` | 18-04 |
| `test_judge_critic_collision_warning_fires_once_per_run` / `…states_a_fact_not_a_fault` — mechanically green off `FakeJudge`'s hardcoded `claude-opus-5`, but their "deployed configuration" prose is now contrived | tests/test_evals.py | 18-04 |
| OPERATIONS.md record-mode paragraph and DESIGN.md's supersession trailer still state the shared model | `docs/OPERATIONS.md`, `docs/DESIGN.md` | 18-04 |
| ADR-0012 not yet written; ADR-0010 still reads `Accepted`; the reversal register still reads "spent" | `docs/adr/` | 18-03 |
| README Limitations bullet still says the judge shares the critic's model | `README.md:285` | **Phase 22**, by milestone scope — not 18-04 |
| A real Opus 4.8 verdict has never round-tripped; only fakes have | — | Phase 21's record run (18-VALIDATION manual-only) |

## Acceptance criteria, measured

| Criterion | Evidence |
|-----------|----------|
| `evals/graders.py:33` default is `"claude-opus-4-8"`; `EVAL_JUDGE_MODEL` still overrides | line read post-commit; `test_record_preview_names_a_model_it_cannot_price` (which repoints the constant) green |
| `price_for("claude-opus-4-8")` returns 5.0/25.0/6.25/0.50; every usage loop green | `tests/test_usage.py` 45/45 |
| New pin: judge != deployed `CRITIC_MODEL`, fly.toml-anchored, observed red before the flip | red quoted above (pre-flip **and** re-observed under probe 1) |
| Offline evals 41/41 — fixture demonstrably not staled | `41/41 (100% vs 90% required)`, exit 0 |
| Row and flip share one commit | `git show --stat 06140a4` lists both files |
| Both mutations observed red and reverted | quoted above; `git status --short` clean after each |

## Threat register — dispositions discharged

| Threat ID | Disposition | Discharged by |
|-----------|-------------|---------------|
| T-18-01 (tampering, PRICES row) | mitigate | The direct four-rate pin reds on a wrong rate; the cache-ratio loop reds on a wrong multiple; an absent row raises `UnknownModelPricing` and never costs $0 — all three observed, the third under probe 2. **Narrowed by measurement:** the fail-loud path does not reach the record preview, which degrades to a FLOOR by design; the suite is where it is loud. |
| T-18-02 (repudiation, independence pin) | mitigate | The pin asserts `CRITIC_MODEL` is present before comparing, so a regenerated `fly.toml` reds on the presence assertion rather than silently comparing against `None`. |
| T-18-SC (package installs) | accept | Zero packages installed; nothing to audit. |

## What wave 2 inherits

- A judge on `claude-opus-4-8`, priced, with independence pinned against the deployed critic.
- `FakeJudgeClient` (tests/test_evals.py:570) still has a `Response` with **only** `.content` — the moment 18-02's guard reads `response.stop_reason`, every test built on it AttributeErrors. Untouched here on purpose; it is 18-02's first job (pitfall 3).
- `test_judge_raises_on_an_unparseable_verdict` green and unmodified — the discriminator 18-02's guard must narrow without swallowing.
- The correction above: do not re-inherit "the preview dies on an unpriced model", and do not count `test_record_preview_lands_in_the_researched_range` as a gate on anything but the size of the quote.

## Self-Check: PASSED

- `src/research_agent/usage.py`, `evals/graders.py`, `tests/test_usage.py`, `tests/test_evals.py` — all present and modified as claimed.
- `.planning/phases/18-independent-eval-judge/18-01-SUMMARY.md` — this file.
- Commit `06140a4` exists on `gsd/phase-18-independent-eval-judge` and contains both `usage.py` and `graders.py`.
- Working tree clean after both mutation probes were reverted.
