---
phase: 15-answer-quality-evals
plan: 01
subsystem: evals
tags: [fixtures, recorder, schema-validation, models-map, seam, gate-discipline]

# Dependency graph
requires:
  - phase: 15-answer-quality-evals
    plan: "research"
    provides: "Pattern 1 (the recorder is a seam in run_case) and Pattern 2 (fixture = final state per turn + metadata)"
provides:
  - "evals/fixtures.py — SCHEMA_VERSION 1, FixtureError, build_fixture / write_fixture / load_fixture / fixture_paths / git_sha"
  - "The models MAP ({pipeline, judge}, extensible to per-node roles) as the recorded staleness surface"
  - "write_fixture's refusal of any recording whose own grades failed, and the forced: true stamp when overridden"
  - "load_fixture's total validation — a malformed fixture raises rather than grading vacuously green"
  - "TurnResult.state, excluded from as_dict()"
  - "run_case(capture_state=True) — the recorder seam"
affects: [15-02, 15-03, 15-05, VALIDATION rows 15-01-T1 (x2) and 15-01-T2]

# Tech tracking
tech-stack:
  added: []  # no packages installed (RESEARCH Package Legitimacy Audit: none to check)
  patterns:
    - "A recorder is a seam in the existing driver, not a second driver — budget scoping, per-case memory, follow-up chaining and error isolation are already correct in run_case, and a parallel loop would drift from the shipped graph in exactly the way the harness exists to prevent"
    - "A committed fixture is refused unless the recording passed, so the later assertion that its judge verdicts still hold is a gate rather than a restatement of whatever was recorded"
    - "Record a MAP of role → model, never a flat model string, when a future phase will make one role's model configurable independently of another's"
    - "A defence-in-depth copy that no test against the real dependency can distinguish from an alias needs a fake dependency built to distinguish it, or the guard is unproven"

key-files:
  created:
    - evals/fixtures.py
  modified:
    - evals/harness.py
    - tests/test_evals.py
    - README.md

key-decisions:
  - "TurnResult.state was added in Task 1, not Task 2 as the plan sequenced it: build_fixture reads turn.state, so the field is part of the fixture layer's contract and Task 1's tests cannot exist without it. Task 2 kept the run_case plumbing that fills it."
  - "Judge verdicts are recorded per turn; deterministic grades are not. Deterministic graders are pure functions of the recorded state and replay recomputes them, so storing them would create a second source of truth that could disagree with the state it was derived from. Judge verdicts cannot be recomputed without spending money, which is exactly why they are metadata."
  - "load_fixture validates bools out of the int/float fields explicitly, because `True == 1` in Python — a fixture with `schema_version: true` passes the version comparison and would otherwise load."
  - "write_fixture copies the fixture before stamping `forced: true` rather than mutating the caller's dict. The recorder CLI (plan 05) will hold that dict; a write that silently rewrites its argument is a surprise nobody needs at the point money has already been spent."
  - "The size guard runs before the file is written, so a refused oversize fixture leaves nothing behind — asserted, because a half-written 300 KB file is worse than none."
  - "REQ-offline-eval-quality was NOT marked complete. It spans six plans (quality graders, replay, the 40-case dataset, the recording act); checking it off after the first would make REQUIREMENTS.md claim a measure that does not yet exist."

# Metrics
duration: 22min
completed: 2026-08-09
---

# Phase 15 Plan 01: The recorder seam and the fixture layer Summary

**One-liner:** `run_case(capture_state=True)` now keeps each turn's final `AgentState` instead of discarding it, and `evals/fixtures.py` turns that into a committed JSON fixture that the writer refuses to produce from a failed recording and the loader refuses to read when malformed — the whole recording mechanism proven end to end against the scripted client, with no network, no key and no spend.

## What was built

### Task 1 — `evals/fixtures.py` (commit `45bbe86`)

`SCHEMA_VERSION = 1`. One file per case, `<case_id>.json`, `json.dumps(..., indent=2)` — never minified, because the diff is the review surface for a file that becomes CI's pass/fail input.

```jsonc
{
  "schema_version": 1,
  "case_id": "followup-uses-prior-notes",
  "recorded_at": "2026-08-09T23:07:41+0100",   // run_suite's generated_at idiom
  "models": {"pipeline": "claude-sonnet-5", "judge": "claude-opus-5"},
  "git_sha": "45bbe86",
  "pipeline_cost_usd": 0.7,
  "turns": [{"label": "research", "state": { /* final AgentState */ }, "judge": [ /* verdicts */ ]}]
}
```

**`models` is a MAP, and that is the plan's sharpest correction to itself.** A flat `"model"` string would keep matching `graph.MODEL` after Phase 16 makes the critic's model configurable independently of it, and the recordings would go stale invisibly — a staleness gate that cannot fire is worse than none, because it is believed. The map takes `"critic"` or any future per-node role without a schema bump; both halves of that claim are pinned by `test_a_fixture_records_a_models_map_not_a_flat_model_string`, which round-trips a three-role map **and** asserts no top-level `"model"` key exists to be read by mistake.

**`write_fixture` refuses**, naming the failing graders, when `result.error` is set or any grade in any turn failed — deterministic or judge, one code path, because "the judge said no" and "the run never terminated" are equally disqualifying for something about to be committed as known-good. `force=True` writes anyway and stamps `"forced": true`. This refusal is what makes plan 03's recorded-verdict replay a real gate: a fixture in the repo could not have been recorded red, so a red replay means a hand-edit, a forced write, or a genuine regression.

**`load_fixture` validates totally** — `schema_version` exact match, every required top-level key present and correctly typed, `models` a non-empty `str → str` map containing `pipeline` and `judge`, `turns` non-empty, and every turn carrying `label` (str) / `state` (dict) / `judge` (list). Every violation raises `FixtureError` naming the path and the offending key. The threat is not a hostile file, it is a plausible one: a truncated write that loads as a half-empty dict and grades green over missing data.

**Size guards** on the encoded bytes, checked *before* writing: warn to stderr above 100 KB, `FixtureError` above 250 KB. **`git_sha()`** falls back to `"unknown"` on `OSError` or empty stdout — metadata, never a gate. **`fixture_paths()`** returns `[]` for a missing directory, which is the pre-recording state of the repo, not an error.

### Task 2 — the `capture_state` seam (commit `65a6bc8`)

`TurnResult.state: dict | None = None`, deliberately absent from `as_dict()`; `run_case(..., capture_state: bool = False)` appends `state=dict(state)` per turn when on. Off — every existing caller — the grades, the costs and the report shape are what they were, and the whole diff to the default path is one conditional expression evaluated to `None`.

The copy is taken at append time so a later turn cannot alias an earlier one's record.

## Gate discipline: nine mutations, nine red

Sixteen vacuous gates across seven phases. Both selectors were run under `--collect-only` **before** being trusted, and the two guards that reason talked me into believing were checked by mutation instead — one of which was in fact unproven and had to be fixed.

| Selector | Collected | Required |
|----------|-----------|----------|
| `-k "fixture or recorder_refuses"` | **14** | ≥ 6 |
| `-k "capture"` | **6** | ≥ 2 |
| `-k "recorder_captures_schema"` | **1** | VALIDATION row |

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| A | `write_fixture` never calls `_refuse_failing` | **RED** | `recorder_refuses_failed_judge`, `..._failed_deterministic_grade`, `..._a_run_that_errored` — all three DID NOT RAISE |
| B | `load_fixture` skips the `schema_version` comparison | **RED** | `a_malformed_fixture_fails_loudly` on the `future-schema` variant |
| C | `load_fixture` skips the required-key loop | **RED** | same test, via `KeyError` on the `missing-models` variant |
| D | `_validate_models` returns before the required-role check | **RED** | same test, `no-pipeline-role` variant |
| E | `load_fixture` accepts empty `turns` | **RED** | same test, `empty-turns` variant |
| F | `load_fixture` skips per-turn type checks | **RED** | same test, `state-is-a-string` variant |
| G | size guard removed | **RED** | `fixture_size_guard_rejects_a_runaway_draft` DID NOT RAISE (the 100 KB warning still printed — 301,607 bytes) |
| H | `state=None` always / `state=dict(state)` always | **RED** both ways | `recorder_captures_schema` (+2) on the first; `capture_state_default_leaves_results_unchanged` on the second |
| I | `state=state` (alias, not copy) | **first attempt GREEN — see below** | then **RED** on `a_captured_state_survives_a_driver_that_reuses_one_dict` |

**Mutation I is the one worth reading.** `state=state if capture_state else None` passed the entire capture suite. The test I had written for it — distinct `id()`s and distinct drafts across turns — cannot fail, because `graph.app.invoke` returns a **fresh dict per call**, so an alias and a copy are indistinguishable through the real graph. The copy was defence in depth with no gate on it, dressed as a gate. Fixed by faking a driver that reuses one dict across both turns; an aliasing capture then records the last turn's answer for every turn, which is exactly the silent corruption — a fixture that looks complete and is one answer repeated — and the mutation goes red on it. Same family as 13-05's `FrozenQueryEmbedder` and 14-01's ratio assertion: **the assertion that looks like the gate often is not the gate, and only the mutation says which.**

Each mutation was applied to a scratch copy and reverted by file copy, never `git checkout` (12-06's lesson: an uncommitted edit is discarded that way). Both source files were confirmed byte-identical to their committed state afterwards.

## Verification

| Check | Baseline (measured on this tree) | After |
|-------|----------------------------------|-------|
| Full suite, plain (`.venv/bin/pytest`) | 563 passed / 65 skipped | **584 passed / 65 skipped** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 627 passed / 1 skipped | **648 passed / 1 skipped** |
| Offline evals, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" DATABASE_URL=""`) | 12/12, exit 0 | **12/12, exit 0** |
| `tests/test_evals.py` | 47 passed | **68 passed** |
| `grep -c "capture_state" evals/harness.py` | 0 | **5** |
| `import evals.fixtures` under `ANTHROPIC_API_KEY=""` | n/a | succeeds (no eager client, no import beyond stdlib) |
| `.venv/bin/ruff check .` | clean | clean |

**Delta fully explained: +21 passed in both arms, +0 skipped in either.** The 21 are exactly the 21 tests added to `tests/test_evals.py` (14 fixture-layer, 5 recorder-seam, 2 git-sha). None is gated on Postgres or a key, which is why plain and armed moved by the same number. **Zero new skips, so nothing to justify.** No existing test was edited — every change to `tests/test_evals.py` is an append plus one import line, and `test_the_whole_offline_suite_passes` and `test_running_a_case_grades_every_turn` pass unmodified, which is the "zero behaviour change on every existing code path" success criterion stated by the tests that would have noticed.

The offline eval CLI output is byte-identical, caveat included — correct, since the caveat rewrite is wave 3's.

## Deviations from Plan

### `TurnResult.state` moved from Task 2 into Task 1 [Rule 3 — blocking]

The plan assigns the field to Task 2, but Task 1's own specified tests build "a fake CaseResult whose TurnResult carries `state=finished()`" and `build_fixture` reads `turn.state`. Task 1 is unimplementable without it. The field landed in Task 1's commit; Task 2 kept the `run_case` plumbing, which is the part that actually changes behaviour. The plan's key_link ("build_fixture reads captured turn states") already implied this ownership.

### `test_capture_state_default_leaves_results_unchanged` compares `as_dict()` minus `duration_ms`

The plan says the two `as_dict()` outputs are identical. They cannot be: `duration_ms` is wall-clock, rounded to 0.1 ms, and differs between any two runs. Everything else — labels, `passed`, `cost_usd`, and every grade — is asserted equal, and the helper that strips the timing says why. **A plan's stated arithmetic is a claim to check.**

### One test added beyond the plan's list, for a guard the plan's tests could not see

`test_a_captured_state_survives_a_driver_that_reuses_one_dict` — see mutation I above. The plan specifies the copy (`dict(state)` "so later turns can't alias earlier ones") but no test it lists can distinguish a copy from an alias against the real graph.

### Requirements not marked complete

`REQ-offline-eval-quality` stays **Pending** in `REQUIREMENTS.md`. It spans all six plans of this phase; nothing about answer quality is measurable yet, and the dataset is still 12 cases. Marking it here would make the traceability table assert a measure that does not exist. Phase close owns it.

### README

**Updated in-wave, one falsified fact.** README stated "563 tests" in two places (lines 13 and 161); the plain suite is now 584. Both corrected. The evals limitation at line ~203 ("Offline evals can't measure answer quality, and twelve live cases are a smoke test, not a benchmark") is **untouched and still true** — nothing in this wave grades an answer, and wave 6 owns that sentence per the standing instruction.

### STATE.md hand-edited

Per the execution instruction, `state.advance-plan` and `state.update-progress` were not run; STATE.md was edited by hand. `roadmap.update-plan-progress 15` was run.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-15-01 | mitigate | **Closed for the fixture layer.** `load_fixture` validates schema version, every required key and type, the models map's required roles, non-empty turns, and per-turn key types. Five separate mutations (B–F) each observed red through the loader's own `FixtureError`, so no single guard is carrying the others. |
| T-15-02 | mitigate | **Closed.** `recorded_at`, the models map, `git_sha` and `pipeline_cost_usd` are stamped at build time; `forced: true` is stamped on any override and asserted present in the written file. |
| T-15-03 | mitigate | **Closed.** Refusal covers judge grades, deterministic grades and run errors; mutation A reds all three tests. A refused write is also asserted to leave **no file** — a partial artefact would be a fixture nobody chose to commit. |
| T-15-04 | accept | Re-verified: `AgentState`'s sixteen fields (graph.py:124-142) hold model text, tokens, costs, a run uuid and an owner string. No credentials. Fixtures strip nothing, as planned. |

**New threat surface: none.** No endpoint, no auth path, no schema change in the database sense. `evals/fixtures/` does not exist yet — nothing has been recorded, so nothing is committed to be tampered with until wave 6.

## Known Stubs

None. Two pieces of not-yet-exercised behaviour, stated rather than hidden:

- **No fixture has ever been written by a real recording.** Everything here is proven against `ScriptedClient` — which is the plan's explicit boundary ("no network, no keys, no spend in this plan") and the whole reason the calibration recording is wave 6's checkpoint. The state shapes are real (they come from `graph.app` through the real nodes); only the model text is scripted.
- **The 100 KB warning is exercised; the real-world size is not known.** RESEARCH assumption A5 puts a fixture at 5–25 KB, derived from `max_tokens` ceilings rather than measured. The scripted states here are far smaller than a live one will be. The guards fire on measured bytes either way, so a wrong estimate costs a warning, not a wrong result.

## Deferred Issues

- **`load_fixture` would raise `KeyError`, not `FixtureError`, if the required-key loop were ever weakened** — observed as mutation C's failure mode. The current code cannot reach it (the loop guarantees `models` exists before `_validate_models` reads it), so this is a note for whoever edits that function, not a bug: the two checks are ordered, and the order is load-bearing.
- **`fixture_paths` does not validate what it returns.** It lists `*.json`; a non-fixture JSON file dropped in the directory becomes a `FixtureError` at load time rather than being skipped. That is the right failure — a file in the fixtures directory that is not a fixture is a question, not a thing to ignore — but plan 03's replay leg is where "unreadable fixture ⇒ loud red CaseResult" has to actually be wired.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `45bbe86` | feat | A fixture is a recorded run the judge already approved |
| `65a6bc8` | feat | `run_case` can keep a turn's final state instead of discarding it |

## Self-Check: PASSED

- `evals/fixtures.py` — FOUND (created, 298 lines)
- `evals/harness.py` — FOUND (modified)
- `tests/test_evals.py` — FOUND (modified)
- `README.md` — FOUND (modified)
- `.planning/phases/15-answer-quality-evals/15-01-SUMMARY.md` — FOUND (created)
- Commits `45bbe86`, `65a6bc8` — both resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
