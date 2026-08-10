---
phase: 16-independent-critic-model
plan: 02
subsystem: evals
tags: [fixture-staleness, backfill-semantics, record-mode, spend-reservation, gate-discipline]

# Dependency graph
requires:
  - phase: 16-independent-critic-model
    plan: "01"
    provides: "graph.critic_model() — the accessor both the critic node and this plan's gate read"
  - phase: 16-independent-critic-model
    plan: "research"
    provides: "Finding 3 (reservation arithmetic + the Sept-1 discovery), Finding 5 (backfill semantics, hard-stale rejected)"
provides:
  - "grade_fixture_current comparing TWO roles — pipeline and critic — with backfill: models.get('critic') or pipeline, falsy read as absent"
  - "record_case_to_fixture writing the third role from critic_model(), so an absent key means pre-16 by construction"
  - "record_suite's once-per-run stderr line stating the judge/critic relation as fact, naming the shared model and ADR-0010"
  - "reserved_run_usd's documented threshold: Opus-critic typical ~$0.18, revised tail ~$0.28 outside by design, the 2026-09-01 Sonnet boundary"
  - "OPERATIONS: the CRITIC_MODEL config row and the CRITIC_MODEL/DEMO_RESERVED_RUN_USD pairing"
affects: [16-03, 16-04, VALIDATION rows 5, 6, 7, and row 9's harness half]

# Tech tracking
tech-stack:
  added: []  # nothing installed; `import sys` in harness.py is stdlib
  patterns:
    - "Backfill on a missing key is honest only when absence is a STATEMENT. It is here because the recorder now always writes the key, so absence means pre-16 by construction and the pre-16 population is exactly one file."
    - "Falsy-as-absent at both ends of a config seam: critic_model() reads a blank CRITIC_MODEL as unset, and the gate reads a blank recorded critic as pre-16. A blank names no model, so the same reading is the only honest one on both sides."
    - "A pin that runs at the neutral default cannot see a mutation that produces the neutral default. The models-map pin passes whether the recorder writes critic_model() or graph.MODEL, because with CRITIC_MODEL unset they are the same string; only an env-driven twin discriminates."
    - "When an operator line fires on the CHOSEN configuration, word it as a property statement. A line that calls the operator's own decision a misconfiguration every run teaches them to skip the line."
    - "Documented-not-enforced prose deserves a content pin. The reservation threshold had no automated gate at all — only a grep in a plan's verify block, which nothing runs again after the plan closes."

key-files:
  created: []
  modified:
    - evals/harness.py
    - evals/__main__.py
    - tests/test_evals.py
    - src/research_agent/limits.py
    - tests/test_limits.py
    - docs/OPERATIONS.md

key-decisions:
  - "Both designed reds resolved in Task 1's commit, not Task 2's. The plan originally split the docstring/recorder change from its two pins; that split is a commit that knowingly leaves the suite red, which this repo does not make. Task 2 then holds only NEW tests."
  - "The models-map pin reads graph.critic_model() rather than a literal, and a second env-driven test was added beside it. Probe 5 proves why: a recorder writing graph.MODEL into the critic slot satisfies the pin (unset env makes them the same string) and misrecords every fixture made from a real record shell."
  - "The gate's stale detail branches: the critic branch names the CRITIC role and CRITIC_MODEL, the pipeline branch does not mention the critic at all. Probes 6 and 7 make each branch's wording load-bearing — an operator's first question is which model moved."
  - "A fifth gate test (`still_fires_on_the_pipeline_model`) was added beyond the plan's three cases: the first role must not have become decorative, and probe 7 shows nothing else covers the pipeline branch's wording."
  - "The collision line is prefixed `note:` and never `warning:`. Per the USER DECISION it fires on the deployed configuration; three forbidden-word assertions plus positive pins on 'accepted' and 'deployed' hold the wording."
  - "Two tests added for gates that had NO probe: the None-judge guard on the new stderr site (it dereferences judge.model upstream of the existing judgeless refusal) and the reservation docstring's content."
  - "reserved_run_usd stays model-unaware and the rejection is now pinned by a test that greps limits.py's own source for a usage/graph import. The argument was made twice; the second time it got a gate."
  - "/pricing and /health surfacing DEFERRED (CONTEXT left it 'if at all'). The critic model already surfaces in the fixture map, the log lines, the span and pricing_unknown; an additive /pricing block is real work with a 501-contract subtlety and no consumer asking for it yet."

# Metrics
duration: 47min
completed: 2026-08-10
---

# Phase 16 Plan 02: The gate learns the critic, and the reservation says what would break it Summary

**One-liner:** `grade_fixture_current` now grades two roles instead of one — pipeline against `graph.MODEL`, critic against `graph.critic_model()`, backfilling a missing key to the pipeline because at record time the code had no critic seam — the recorder writes the third entry from now on so that backfill keeps being a statement rather than a guess, record mode says once per run when the judge and the critic are the same model (which they are, deliberately, in production), and the $0.20 reservation stays flat with the arithmetic that would move it written down in two places and pinned by a test.

## What was built

### Task 1 — the gate, the recorder, the docstring and BOTH pins (commit `edca5bd`)

`grade_fixture_current` (harness.py:331) reads two roles:

```python
recorded_critic = models.get("critic") or recorded
current_critic = graph.critic_model()
```

and returns three distinguishable outcomes rather than two: pipeline-stale (wording unchanged, so `test_model_mismatch_gates_replay` is untouched), critic-stale (names the **CRITIC** role and `CRITIC_MODEL`), and green (names both models).

The docstring was rewritten around the new boundary. What it now says, and each sentence is load-bearing somewhere:

- **The backfill is a fact, not a convenience.** `technical-figures.json` was recorded 2026-08-10 at `225b06b`, when `call_model` had no `model` parameter at all — its critic ran on `graph.MODEL` *by construction*, verifiable from this tree's history.
- **Falsy is absent.** Key missing, `null`, or `""` all read as pre-16, for the same reason `critic_model()` reads a blank `CRITIC_MODEL` as unset: a blank names no model, so the pre-16 reading is the only one available. Stated in the docstring because it is a judgement, not an obvious consequence.
- **The consequence of the chosen production config, stated rather than discovered:** the committed fixture predates the Opus critic, so any suite run in an environment that sets `CRITIC_MODEL` grades it **stale**. That verdict is the designed staleness and is exactly what tells the story until the deferred full record run re-records under the new critic. CI and keyless contexts never set the variable, which is what preserves 41/41.
- **The new "Cannot catch":** the JUDGE's model, deliberately — its verdicts are fixed data replayed as `recorded_*` grades, so pointing `JUDGE_MODEL` somewhere new does not invalidate a word of what the old judge already said.

`record_case_to_fixture` writes `{"pipeline", "judge", "critic"}`, the critic from `critic_model()` at record time. `evals/__main__.py` gained the honest note that the preview lumps the whole pipeline turn at `graph.MODEL` and therefore under-quotes against the deployed config — comment only, because splitting the turn per node is a re-calibration and its honest input is the deferred record run's measurements, not another estimate.

**Both designed reds were resolved in this same commit** — see Deviations.

### Task 2 — five gate tests and the recorder's anti-vacuity twin (commit `2a37176`)

`-k fixture_critic_gate` collects **5** (baseline 0): backfill green, blank-as-absent green, stale-when-the-critic-moves (driven through `replay_case`, so the wiring is proven), recorded-critic-beats-backfill, and pipeline-still-fires. Plus `test_record_writes_the_models_map_critic_from_the_environment`.

### Task 3 — the collision line and the reservation prose (commit `53ee909`)

`_state_judge_critic_relation(judge)` runs once at the top of `record_suite`, before the memory guards and the loop. On collision it prints to stderr:

> `note: the judge and the in-graph critic both run on claude-opus-5. These recorded verdicts are independent of the writer's model and not of the critic's -- what one waves through, the other is likelier to wave through. This is the deployed configuration and it is accepted, recorded in ADR-0010.`

`reserved_run_usd`'s docstring gained the threshold in Phase 14's cap-note idiom, and its **body is unchanged**. OPERATIONS gained the `CRITIC_MODEL` config row and a block beside the Phase 14 cap-note (`grep -c CRITIC_MODEL docs/OPERATIONS.md`: **0 → 6**).

## Gate discipline

### `--collect-only` per selector, against the whole `tests/` tree

| Selector (VALIDATION row) | Collected | Baseline |
|---|---|---|
| `fixture_critic_gate` (row 6) | **5** | 0 |
| `judge_critic_collision_warning` (row 7) | **4** | 0 |
| `reservation_threshold` (row 5) | **2** | 0 |
| `record and models` | 2 | 1 |
| `record_writes` | 2 | 1 |

**Two of the plan's own verify selectors were vacuous, and the first probe run reported a wrong result because of it.** `-k docstring` (Task 1's verify) collects **0** — the docstring pin is named `test_the_replay_model_gate_states_its_claim_boundary`. `-k "record and models"` (Task 2's verify) does **not** collect the models-map pin, whose name contains neither word. The first pass of probes 4 and 5 therefore reported "reds one test" when probe 4 reds two. Selectors corrected to `fixture or claim_boundary` and `... or record_writes`; probes re-run. This is the sixteen-vacuous-gates failure in miniature, inside a plan written to prevent it.

### Measured suite deltas

| Leg | Baseline entering | After this plan | Delta |
|---|---|---|---|
| Plain (`.venv/bin/pytest`) | 678 passed / 65 skipped | **690 passed / 65 skipped** | +12 passed, **0 new skips** |
| Armed (`DATABASE_URL` → local PG :54329) | 742 passed / 1 skipped | **754 passed / 1 skipped** | +12 passed, **0 new skips** |
| Offline evals (`ANTHROPIC_API_KEY=""`, `env -u CRITIC_MODEL`) | 41/41 keyless | **41/41 keyless**, exit 0 | unchanged |
| `ruff check src/ tests/ evals/` | clean | clean | — |

12 new tests, 12 new passes, **no skip added — none to justify**. Every leg run under `env -u CRITIC_MODEL` (`env | grep -c CRITIC_MODEL` → 0), because the keyless invariant's precondition is the variable being provably absent, not merely unexported by habit.

Zero diffs in `evals/fixtures.py`, `evals/fixtures/` and `.github/workflows/ci.yml` — verified with `git diff --stat 1730d6d..HEAD -- …` (0 lines). `REQUIRED_MODEL_ROLES` stays `("pipeline", "judge")`: hard-stale was rejected in RESEARCH Finding 5 because it converts a graded red into a load error and destroys a $0.24 recording.

### Mutation probes — fifteen, where the plan named two

Each reverts one line in `evals/harness.py` or `limits.py`, runs the affected families **plus** the pre-existing replay/record tests, and restores the whole file. `git status` clean after each run; both probe scripts live in the scratchpad, not the repo.

| # | Mutation | Reds | Verdict |
|---|---|---|---|
| 1 | gate compares pipeline only (VALIDATION mutation 3) | `goes_stale_when_the_critic_moves`, `prefers_a_recorded_critic_to_the_backfill` | **Correct.** Exactly the two tests that assert the critic comparison; the backfill and blank tests stay green because pipeline-only *is* the backfill for a pre-16 fixture. |
| 2 | always backfill — never read a present `critic` key | `prefers_a_recorded_critic_to_the_backfill` **only** | **T-16-04 closed.** A recording that says which critic it used is never second-guessed. |
| 3 | `"critic" in models` instead of truthiness | `reads_a_blank_critic_as_absent` **only** | **Exactly one.** The falsy-edge decision is real behaviour, not a docstring claim. |
| 4 | recorder omits the critic entry (VALIDATION mutation 5) | `record_writes_a_fixture_per_case_with_fakes`, `record_writes_the_models_map_critic_from_the_environment` | **Correct** — and two, not the plan's predicted one, because of the twin below. |
| 5 | recorder writes `graph.MODEL` into the critic slot | `record_writes_the_models_map_critic_from_the_environment` **only** | **The probe that justifies the extra test.** The map pin runs with `CRITIC_MODEL` unset, where `critic_model() == graph.MODEL`, so it cannot see this at all — and this is the mutation that silently misrecords every fixture made from a real record shell. |
| 6 | critic-stale detail loses the role name | both stale tests | **Correct.** The wording is the operator's diagnosis, so it is asserted, not assumed. |
| 7 | pipeline branch borrows the critic wording | `still_fires_on_the_pipeline_model` **only** | **Exactly one.** Justifies the fifth gate test: nothing else covers the pipeline branch's message. |
| 8 | pre-16 docstring restored wholesale | `the_replay_model_gate_states_its_claim_boundary` **only** | **Exactly one**, and it reds three ways (two positive pins plus the negative pin on the dead sentence). |
| 9 | collision line never printed | `fires_once_per_run`, `states_a_fact_not_a_fault` | **Correct.** The silent twin stays green, which is what makes it a twin. |
| 10 | printed once per **case** instead of per run | `fires_once_per_run` **only** | **Exactly one.** Two cases, one line — a forty-line banner is a line nobody reads. |
| 11 | printed unconditionally (collision check dropped) | `is_silent_when_they_differ` **only** | **Exactly one.** Without this the fires-once test would prove only that the recorder prints *something*. |
| 12 | `judge is None` guard dropped | `leaves_the_judgeless_refusal_intact` **only** | **The gate that had no probe.** Without the added test this reds nothing and turns a stated programming error into an `AttributeError` from a line that only exists to print a note. |
| 13 | reworded as "misconfigured judge/critic pair" | `states_a_fact_not_a_fault` **only** | **Exactly one.** The USER DECISION's wording constraint is executable, not advisory. |
| 14 | reservation docstring's Phase-16 block deleted | `docstring_names_what_would_break_it` **only** | **The second gate that had no probe.** The plan's gate for this row was a grep in a verify block — which nothing runs again once the plan closes. |
| 15 | `reserved_run_usd` made model-aware (`+ premium if CRITIC_MODEL`) | `stays_flat_and_model_unaware` **only** | **Exactly one.** The rejected alternative now reds if someone builds it. |

**The negative control on every probe:** the pre-existing replay, record and `/demo` status tests stayed green under all fifteen except where listed. No probe redded anything by an unrelated route, and probe 14's first attempt redded *nothing* — the mutation had replaced text inside the docstring while leaving all four pinned strings intact. Recorded because a probe that reds nothing is either a vacuous test or a bad probe, and the difference matters: it was the probe. Re-run against the whole block deleted, it reds exactly one test.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-16-04 | mitigate | **Closed.** Probe 2: a present `critic` key is compared directly and the backfill is not consulted — the tampering shape (hand-delete the key to make a stale recording grade green) survives only for pre-16 files, of which there is exactly one, and the deferred record run replaces it. |
| T-16-05 | mitigate | **Closed, and wider than planned.** The `:2062` pin now requires the critic entry (probe 4) — but the pin alone is vacuous against probe 5, so repudiation ("this recording doesn't say which critic ran") is closed by the env-driven twin, not by the pin. |
| T-16-06 | mitigate | **Closed.** The stderr line fires on collision (probe 9), only on collision (probe 11), once per run (probe 10), never crashes (probe 12), and cannot be reworded into an accusation (probe 13). ADR-0010's recorded acceptance is 16-03's. |
| T-16-SC | accept | Re-verified: nothing installed. `pyproject.toml` untouched; `import sys` is stdlib. |

**New threat surface: none.** No endpoint, no auth path, no schema change. The one new output is a line on stderr in a mode that only runs from an operator's shell.

## Deviations from Plan

### Structural change to the plan's task split (checker blocker, applied)

**1. Both designed reds resolved in Task 1's commit.** The plan's Task 1 rewrote the docstring and the recorder while Task 2 held their pins — a commit that knowingly leaves the suite red. Task 1 now carries both pin updates; Task 2 holds only new tests. `edca5bd` is green on the full plain suite (678/65, unchanged at that point), and so is every commit after it.

### Additions beyond the plan (Rule 2 — missing critical verification)

**2. [Rule 2] `test_record_writes_the_models_map_critic_from_the_environment`.** The plan's case (d) updated the map pin and stopped. Probe 5 shows that pin cannot distinguish `critic_model()` from `graph.MODEL`, because the suite runs with `CRITIC_MODEL` unset and they are then the same string. The mutation it misses is the one that matters: every fixture recorded from an operator shell would name the wrong critic, and the gate reading them would then compare a lie against the truth.

**3. [Rule 2] `test_fixture_critic_gate_reads_a_blank_critic_as_absent`.** The plan told the docstring to state the falsy edge and gave the behaviour no test. Probe 3 reds it alone.

**4. [Rule 2] `test_fixture_critic_gate_still_fires_on_the_pipeline_model`.** The plan's three cases all exercise the critic role; nothing checked that the first role survived the change with its own wording. Probe 7 reds it alone.

**5. [Rule 2] `test_judge_critic_collision_warning_leaves_the_judgeless_refusal_intact`.** The new stderr site dereferences `judge.model` **upstream** of `record_case_to_fixture`'s judgeless `ValueError`. The existing judgeless test drives `record_case_to_fixture` directly and cannot see `record_suite`'s new first line. Probe 12 reds it alone.

**6. [Rule 2] Two reservation tests in `tests/test_limits.py`.** VALIDATION row 5's gate was "grep gate + prose review" — a manual command in a plan that closes. `reservation_threshold_docstring_names_what_would_break_it` pins the four facts (`CRITIC_MODEL`/`claude-opus-5`, `0.18`, `0.28`, `2026-09-01`, `0.30`); `reservation_threshold_stays_flat_and_model_unaware` pins that the *function* did not learn about models, including a source-level check that `limits.py` still imports neither `usage` nor `graph`. Probes 14 and 15.

**7. [Rule 2] Twelve mutation probes beyond the plan's two.** Carry-in from wave 1, applied as instructed: every gate this wave adds was asked whether a probe exists for it. Two did not (probes 12 and 14) and both gained a test; two more (probes 6, 7) turned prose assertions into observed behaviour.

### Adjustments the plan left to discretion

**8. `/pricing` and `/health` surfacing deferred** (CONTEXT: "how the critic model surfaces in `/health` or `/pricing` **if at all**"). The critic model already surfaces where it is load-bearing: the fixture `models` map, the span, the log line, and `pricing_unknown`. RESEARCH Finding 6 notes the additive `/pricing` block carries a real subtlety — the endpoint currently 501s on any `UnknownModelPricing`, and an unpriced *critic* must not take down pricing for the writer. That is a change worth its own tests and no consumer is asking for it. Recorded as deferred rather than done quietly.

**9. Model-aware reservation rejected, for the record and for ADR-0010's consequences.** `reserved = base + critic_premium()` would make `limits.py` import the price table and the graph's configuration to sharpen an *admission* estimate by at most $0.13, when `settle()` already replaces it with the real cost at run end and `AGENT_MAX_RUN_COST_USD` already bounds the tail. The operator knob exists; what was missing was the sentence saying when to turn it, which is now in two places and pinned.

**10. The gate's green detail changed wording** (now names both models: "recorded on X with the critic on Y, which is what this tree runs"). Checked before changing: no test and no doc pinned the old string.

### TDD Gate Compliance

**Warning: no RED gate commit exists for this plan.** Task 2 carries `tdd="true"`, but the plan sequences implementation (Task 1) before tests (Task 2), so the new tests were green on first run. Commits are `feat` → `test` → `feat` rather than `test` → `feat`, and a gate-sequence check will not find a `test(...)` commit preceding the first `feat(...)`. The substitute evidence is the fifteen probes, each naming the exact line whose reversion reds it — which is the stronger artefact: a RED commit shows a test failing before code exists, a probe shows *which* test fails for *which* line, after.

## README and stale prose

**Whole-file README pass made; nothing this wave falsifies.** Checked rather than assumed:

- `grep -n "0\.20\|reserv\|CRITIC\|fixture" README.md` — line 43 ("the spend cap reserves against in-flight runs") is still true; no dollar figure for a run appears anywhere in the README, so the reservation arithmetic falsifies nothing there.
- The evals section (lines 195–213) describes the caveat printing "that recording's date, model, commit and age" — still accurate; the caveat prints `models["pipeline"]` and the recorder did not change what it prints.
- The record-preview paragraph claims the quote is computed at run time from the same effective-dated tables the service bills against, and that "it is an estimate and says so". Still true. The per-node under-quote this wave documented is a sharpening of an estimate the README already labels an estimate — it is noted in `evals/__main__.py` where the constants live, which is where someone acting on it would look.
- **README:252's critic limitation is untouched**, as instructed: it is wave 3's deletion.

**`docs/adr/0009` lines 126 and 147** describe the Phase-15 gate as unable to catch a critic-model change. Correctly **not edited**: ADRs are records of what was decided when, and the convention forbids editing their content. ADR-0010 (16-03) is where this change enters the record.

## Requirements

`REQ-independent-critic-model` stays **Pending**. This plan closes **SC-3** (the reservation threshold, documented in `limits.py` and OPERATIONS and pinned by two tests) and the fixture leg of SC-2. **SC-4** (ADR-0010) and **SC-5** (the README sentence) are 16-03's; the production cutover that makes any of it observable is 16-04's. Checking the box here would assert a capability that is real in code and absent from both the record and production.

## Known Stubs

None. Two pieces of not-yet-exercised behaviour, stated rather than hidden:

- **No fixture on disk carries a `critic` key.** The one committed recording predates the seam; the recorder writes the key from now on, and the re-record is deferred to the full 40-case record run per CONTEXT. Until then the gate's backfill is what makes it grade, and the moment production's `CRITIC_MODEL` is present in a suite's environment that fixture grades stale — correctly, and by design.
- **The collision line has never printed outside a test.** It fires from `record_suite`, which only runs under `--record --yes`, and the last record run predates this commit.

## Deferred Issues

- **`evals/__main__.py`'s preview still under-quotes** against the deployed critic. Noted in the constants comment, not corrected: the correction is a per-node split of the assumed turn, and its honest input is the deferred record run's measurements.
- **`/pricing` critic block** — deferred with the reasoning above; the 501-contract subtlety is the part that needs care if it is ever built.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `edca5bd` | feat | The staleness gate compares the critic too, and the recorder names it (both designed reds resolved here) |
| `2a37176` | test | Six tests that can tell the critic gate's four decisions apart |
| `53ee909` | feat | Record mode states the judge/critic relation; the reservation says what would break it |

## Self-Check: PASSED

- `evals/harness.py` — FOUND (modified; backfill expression ×1, `"critic": graph.critic_model()` ×1, `_state_judge_critic_relation` ×2)
- `evals/__main__.py` — FOUND (modified; preview under-quote note present)
- `src/research_agent/limits.py` — FOUND (modified; `CRITIC_MODEL` ×1, `2026-09-01` ×1, function body unchanged)
- `docs/OPERATIONS.md` — FOUND (modified; `grep -c CRITIC_MODEL` → 6, baseline 0)
- `tests/test_evals.py`, `tests/test_limits.py` — FOUND (modified; `fixture_critic_gate` ×5, `judge_critic_collision_warning` ×4, `reservation_threshold` ×2)
- `.planning/phases/16-independent-critic-model/16-02-SUMMARY.md` — FOUND (created)
- Commits `edca5bd`, `2a37176`, `53ee909` — all resolve in `git log`
- `git diff` on `evals/fixtures.py`, `evals/fixtures/`, `.github/workflows/ci.yml` — empty
