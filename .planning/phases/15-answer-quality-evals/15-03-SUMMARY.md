---
phase: 15-answer-quality-evals
plan: 03
subsystem: evals
tags: [replay, exit-rule, staleness-gate, caveat, vacuous-gates, mutation-testing]

# Dependency graph
requires:
  - phase: 15-answer-quality-evals
    plan: "01"
    provides: "evals/fixtures.py (fixture_paths / load_fixture / FixtureError / FIXTURES_DIR), the models MAP, run_case(capture_state=True)"
  - phase: 15-answer-quality-evals
    plan: "02"
    provides: "RECORDED_GRADERS and RECORDED_FOLLOWUP_GRADERS — the grading vocabulary replay applies to a recorded state"
provides:
  - "evals/harness.py replay_case(case, fixture) -> CaseResult — behavioural + quality graders + staleness gate + recorded judge verdicts over a recorded state"
  - "grade_fixture_current — models.pipeline vs graph.MODEL, with its own 'Cannot catch:' line"
  - "Automatic replay in offline mode: the CI command is unchanged and still keyless"
  - "THE EXIT RULE: any red or errored replay CaseResult exits non-zero, whatever the shared pass rate says"
  - "The vacuous-replay guard (fixtures matched but never graded ⇒ exit 1) and the orphaned/broken-fixture reds"
  - "report['fixtures'] = {count, models, recorded_at_oldest, git_shas}"
  - "SC-4's caveat rewrite: date / model / sha / age, and 'not what the current model would say'"
affects: [15-04, 15-05, 15-06, VALIDATION rows 15-03-T1 and 15-03-T2 (x2)]

# Tech tracking
tech-stack:
  added: []  # stdlib only: datetime, pathlib
  patterns:
    - "A rate gate and an all-must-pass gate are different gates, and a leg whose every red is absorbed by a 90% average is decorative — the split has to be proven in ONE test: pass_rate >= floor AND exit 1"
    - "A guard against a silent SKIP cannot be observed through the code that never skips; simulating the future edit (a stubbed replayer returning nothing) is the only thing that can distinguish the guard from its absence"
    - "A staleness gate states which model it compares, because the next phase moves a different one"
    - "Clock-independence is pinned by replaying a five-year-old recording and asserting byte-identical grades — not by running the same input twice"
    - "The headline verdict must follow the exit code, not the pass rate: a run printing PASS at the top and exiting 1 teaches people to read neither"

key-files:
  created: []
  modified:
    - evals/harness.py
    - evals/__main__.py
    - tests/test_evals.py
    - README.md

key-decisions:
  - "The exit rule is computed BEFORE the headline verdict is printed, not just before the return, because the first run against a deliberately stale fixture printed 'PASS 13/14 cases (93% vs 90% required)' and exited 1."
  - "Replay CaseResults join the same report and the same 0.9 denominator (CONTEXT's settled call), and additionally carry their own all-must-pass overlay. Both halves are asserted in one test."
  - "The `--case` selection filters fixtures by FILE STEM, not by loaded case_id: an unreadable file has no case_id to match on, and matching on the stem keeps the vacuous-replay count exact."
  - "A fixture captured from the scripted client CANNOT replay green — wave 2 measured it: scripted reports are 37–183 chars against a 200-char floor, and cover 17% of the question's terms against a 40% floor. The test helper writes a report-shaped draft over the recorded research state and says why."
  - "grade_fixture_current lives in harness.py, not graders.py, so graders.py still imports nothing from research_agent.graph (verified: 0 occurrences)."

# Metrics
duration: 30min
completed: 2026-08-09
---

# Phase 15 Plan 03: Replay wiring, the exit rule, and the caveat rewrite Summary

**One-liner:** An offline run now replays whatever recordings are committed — the same command, the same empty keys — grades them with the whole vocabulary at once, and **fails the build on any single red among them regardless of the pass rate**, which is the difference between a hard gate and a decorative one.

## What was built

### Task 1 — `replay_case` (commit `91002cb`)

`replay_case(case, fixture) -> CaseResult` in `evals/harness.py`. No client, no memory, no
network, no key, no spend. Turn 0 is research, turns 1..n map to `case.followups` in order.

| Turn | Grades applied |
|------|----------------|
| research | 9 × `DETERMINISTIC_GRADERS` + 4 × `RECORDED_GRADERS` + `fixture_current` + the turn's recorded judge verdicts |
| follow-up | 3 × `FOLLOWUP_GRADERS` + 1 × `RECORDED_FOLLOWUP_GRADERS` + the turn's recorded judge verdicts |

- **`grade_fixture_current`** passes iff `fixture["models"]["pipeline"] == graph.MODEL`; the
  failure names both models and says re-record. It lives in `harness.py` rather than
  `graders.py` so the rubrics stay pure functions of a recorded state and `graders.py` never
  imports the graph (`grep` for `research_agent.graph` in `evals/graders.py`: **0**).
- **Its "Cannot catch:" line is the sharpest one in the phase, and it is not the line the
  plan folklore expects.** The gate reads `models["pipeline"]` against `graph.MODEL` — the
  writer/researcher model — and nothing else. Phase 16 makes the **critic's** model
  configurable *independently of* `graph.MODEL`, so a critic-model change **will not fire
  this gate**: the recordings stay green with only the printed date hinting at staleness.
  Closing it needs three things together — a per-node entry in the `models` map, the gate
  extended to compare it, and the fixtures re-recorded. The docstring says exactly that, and
  a test asserts the docstring says it.
- **Recorded judge verdicts** replay as `Grade(f"recorded_{grader}", passed, reason,
  judged=False)` — fixed data now, so nothing is `judged`. Since `write_fixture` refuses a
  failing recording, a red here means a hand-edited or `--force`d fixture.
- **Age appears nowhere in this file.** A turn-count mismatch and a malformed recorded state
  are loud per-case `error`s, isolated exactly the way `run_case` isolates a crashing case.

### Task 2 — the wiring, the exit rule, the caveat (commits `1dfa02b`, `5f0572d`)

Offline runs load `fixtures.fixture_paths()` (filtered by `--case` when given), replay each,
announce each, fold the results into the same `report["cases"]` and the same
`summarise(..., 0.9)` denominator, and add
`report["fixtures"] = {count, models, recorded_at_oldest, git_shas}` — present in offline
mode always, zeros and `None` before anything is recorded.

**THE EXIT RULE, which is what this wave is for.** `summarise`'s `ok` is a pass rate and
nothing else (`harness.py:291-318`): errored results count in `errored` but never move `ok`,
and one red among twelve greens is 92.3%. Left there, every hard gate in this phase would be
decorative. So:

```python
replay_failures = [r for r in replay_results if r.error or not r.passed]
ungraded        = len(matched) - len(replay_results)
ok              = summary["ok"] and not replay_failures and not ungraded
```

The behavioural leg stays rate-governed at 0.9; the replay leg is all-must-pass. Demonstrated
end to end, not only in tests:

```
FAIL  13/14 cases (93% vs 90% required)
  offline mode grades the pipeline, plus answers recorded 2026-08-09 on
  claude-sonnet-4+claude-sonnet-5 (df1ef1b, 0 days ago) — that grades what the pipeline
  said then, not what the current model would say; run with --live to measure that

  1 recorded case(s) failed replay:
    followups-chain@recorded: fixture_current: recorded on 'claude-sonnet-4' but this tree
      runs 'claude-sonnet-5' -- the recording describes a pipeline that no longer exists;
      re-record
  replay is all-must-pass: a committed fixture was known-good at record time
exit: 1
```

**Loud reds, never tracebacks.** An unreadable fixture becomes an errored CaseResult naming
the file; an **orphaned** fixture (a `case_id` no longer in `GOLDEN`) is caught out of
`by_id`'s `KeyError` and becomes an errored CaseResult naming the path and the missing id.
Both exit non-zero under the rule above.

**Zero fixtures is still green**, pinned by its own test: with no replay results there are no
replay failures, so the rule never fires vacuously red. That is today's state of the repo.

**SC-4, the caveat.** With no recordings the original line prints verbatim. With recordings
it prints the oldest recording's date, the pipeline model(s), the sha(s), and the age in
whole days computed at print time — and the clause that carries the claim: *"that grades what
the pipeline said then, **not what the current model would say**; run with `--live` to measure
that."* Age lives here and in the report only; never in a `Grade`.

## Gate discipline: every selector collected first, 18 mutations, 18 red

| Selector | Collected | Required |
|----------|-----------|----------|
| `-k "replay or model_mismatch"` (Task 1) | **7** | ≥ 5 |
| `-k "caveat or replay or keyless or prerecording or orphaned"` (Task 2) | **16** | non-empty |
| VALIDATION `-k "replay or orphaned"` | **13** | non-empty |
| VALIDATION `-k model_mismatch_gates` | **1** | non-empty |
| VALIDATION `-k caveat_wording` | **2** | non-empty |

**Task 1 — `replay_case`**

| # | Mutation | Result | Test that went red |
|---|----------|--------|--------------------|
| A | model gate always passes | RED | `model_mismatch_gates_replay` |
| B | recorded judge verdicts never emitted | RED | `replay_grades_a_recorded_case_green`, `a_recorded_failed_judge_verdict_gates_replay` |
| C | turn-count check removed | RED | `replay_turn_count_mismatch_is_an_error` |
| D | per-case error isolation removed (`except ZeroDivisionError`) | RED | `a_malformed_recorded_state_fails_the_replay_loudly` |
| E | quality graders not applied on replay | RED | `replay_grades_a_recorded_case_green` |
| F | **an age gate added to replay** (the anti-pattern) | RED | `replay_never_reads_the_clock_for_a_verdict` |
| G | recorded verdicts forced green | RED | `a_recorded_failed_judge_verdict_gates_replay` |

**Task 2 — the CLI**

| # | Mutation | Result | Test(s) that went red |
|---|----------|--------|------------------------|
| H | **the exit rule is rate-only** (the checker's blocker) | RED ×4 | the split, broken-fixture, orphaned-fixture, vacuous-guard |
| I | vacuous-replay guard removed | RED | `a_fixture_the_replay_leg_never_graded_is_not_a_green_build` |
| J | caveat never rewritten | RED | `caveat_wording_with_fixtures_prints_date_model_sha_age` |
| K | replay never runs at all | RED ×7 | every CLI replay test |
| L | orphaned `case_id` not wrapped | RED | `an_orphaned_fixture_is_a_loud_red_not_a_traceback` |
| M | unreadable fixture not wrapped | RED | `a_broken_fixture_file_is_a_loud_replay_red` |
| N | replay excluded from the shared denominator | RED | `replay_is_automatic_and_keyless` (13 cases → 12) |
| O | `--case` selection ignored by replay | RED | `replay_honours_the_case_selection` |
| P | headline verdict ignores the replay leg | RED | the split test's headline assertion |

**Mutation H is the one this wave exists for, and its failure line is the whole argument.**
Under a rate-only verdict the split test fails on:

```
        assert report["summary"]["pass_rate"] >= 0.9  # the rate gate alone says pass
        assert report["summary"]["ok"] is True        # ... explicitly
>       assert code == 1                              # and the run fails regardless
E       assert 0 == 1
```

Both the rate assertion and `ok is True` **pass** while the return code is 0 — i.e. the
measured baseline the plan states (12 green + 1 red replay = 92.3% ≥ 90% ⇒ exit 0) is real,
observed, and now closed.

Mutations were applied to a scratch copy and reverted by file write, never `git checkout`
(12-06's lesson); both source files were confirmed byte-identical to their committed state
after each batch.

### The carry-in question: can the test actually discriminate?

Waves 1 and 2 each shipped a "guard" no test could tell from its absence. Asked of every
guard here:

- **The clock test** would have been vacuous as "run the same replay twice and compare" —
  identical input, identical output, invariant under an age gate. It replays a fixture dated
  **2019** against a fresh one and compares grades *including details*, so both an age gate
  and an age leaking into a reason go red (mutation F).
- **The vacuous-replay guard is the one that cannot be observed through the shipped code**,
  and this is stated rather than papered over: every fixture path produces exactly one
  CaseResult, so nothing in the real code path can skip. The guard defends against a *future*
  edit that skips, and the only way to distinguish it from its absence is to fake that edit —
  the test stubs `_replay_fixtures` to return nothing while two fixtures sit on disk. It is a
  guard proven against a simulated future, and the test's docstring says exactly that.
- **The `--case` filter** had no test at all in the plan's list; without one, replaying every
  fixture on a single-case run is indistinguishable from filtering (it stays green either
  way). `test_replay_honours_the_case_selection` asserts the report contains *only* the
  selected case and its `@recorded` twin (mutation O).

## Verification

| Check | Baseline (measured on this tree) | After |
|-------|----------------------------------|-------|
| Full suite, plain (`.venv/bin/pytest`) | 615 passed / 65 skipped | **630 passed / 65 skipped** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 679 passed / 1 skipped | **694 passed / 1 skipped** |
| Offline evals, keyless, exact CI command | 12/12, exit 0 | **12/12, exit 0** (unchanged output, byte for byte) |
| `tests/test_evals.py` | 99 passed | **114 passed** |
| `grep -c 'ANTHROPIC_API_KEY: ""' .github/workflows/ci.yml` | 1 | **1** (file has zero diffs this phase) |
| `git diff --name-only` contains `.github/workflows/ci.yml` | — | **no** |
| `grep -c "research_agent.graph" evals/graders.py` | 0 | **0** |
| `.venv/bin/ruff check .` | clean | clean |

**Delta fully explained: +15 in both arms, +0 skipped in either.** 7 replay tests (Task 1)
+ 9 CLI tests (Task 2) − 1 removed (`test_cli_says_offline_mode_does_not_measure_the_model`,
rewritten into the two `caveat_wording` tests as the plan specifies) = +15. None needs
Postgres or a key, which is why plain and armed moved by the same number. **Zero new skips,
so nothing to justify.**

The exact CI command still exits 0 and still prints the original caveat verbatim, because
**no fixture has been recorded yet** — which is the honest pre-recording state and the
`zero_fixtures_is_still_green_prerecording` test's whole point.

**VALIDATION rows exercised** (left `⬜ pending` in `15-VALIDATION.md`, following waves 1–2's
precedent that phase close marks them):

| Row | Command | Result |
|-----|---------|--------|
| 15-03-T2 (replay automatic, all-must-pass) | `pytest tests/ -k "replay or orphaned"` + keyless CLI | 13 collected, 13 passed; CLI exit 0 |
| 15-03-T1 (model-mismatch gate) | `pytest tests/ -k model_mismatch_gates` | 1 collected, 1 passed |
| 15-03-T2 (caveat rewrite) | `pytest tests/ -k caveat_wording` | 2 collected, 2 passed |

## Deviations from Plan

### The headline verdict was printing PASS on a failing run [Rule 1 — bug, commit `5f0572d`]

Running the finished CLI against a deliberately stale recording printed
`PASS  13/14 cases (93% vs 90% required)` at the top and exited 1. The rate line is honest
and stays; the mark in front of it now follows the exit code, because a run that prints PASS
and fails the build teaches people to read neither — the exact "decorative gate" failure
this plan is about, in presentation form. Pinned by the split test reading the *headline*
line rather than any `FAIL` in the output (mutation P).

### A fixture captured from the scripted client cannot replay green, and the test helper says so

The plan's Task 1 tests assume "capture golden case `followup-uses-prior-notes` offline →
replay green". Measured on this tree, the captured research state fails **two** quality
graders:

```
recorded_coverage  False  only 17% of the question's terms appear in the answer (floor 40%)
recorded_structure False  171 chars is a stub, not a report (floor 200)
```

which is wave 2's calibration table arriving exactly where it said it would. The helper
therefore writes a report-shaped draft over the recorded research state, with a comment
carrying the measured numbers and the reason. Everything else in the fixture is a real state
from the real graph. **Code wins over plan-stated detail; the plan's stated arithmetic is a
claim to check.**

### `test_replay_never_reads_the_clock_for_a_verdict` compares an ancient recording, not two identical runs

The plan says "freeze/monkeypatch date and rerun the green replay a second time — identical
grades". Two runs over identical input are identical whatever the code does, including under
an age gate. The test replays a fixture dated `2019-01-01` against a fresh one, which is what
an age gate can actually fail (mutation F red).

### Three tests beyond the plan's list

`test_a_malformed_recorded_state_fails_the_replay_loudly` (the plan specifies the behaviour
but lists no test for it), `test_the_replay_model_gate_states_its_claim_boundary` (the
acceptance criterion asks for the docstring line; without a test it is a comment, and wave 2
established that claim boundaries are machine-checked), and
`test_replay_honours_the_case_selection` (the `--case` filter had no gate at all).

### `replayable()` returns the `CaseResult` as well

Task 2's CLI fixtures are written with plan 01's real `write_fixture`, which needs the result
to run its refusal check. The helper's Task 1 call sites were updated in the same commit.

### `report["fixtures"]["count"]` counts LOADED fixtures, not matched files

A file that cannot be read has no metadata to report. The count is the number of recordings
whose metadata is in `models`/`git_shas`; broken and orphaned files are visible as errored
`@recorded` cases and in the exit code, not in this count.

### Requirements not marked complete

`REQ-offline-eval-quality` stays **Pending**. The machinery is now live end to end, but the
dataset is still 12 cases and **nothing has been recorded**, so no answer has been graded.
Phase close owns it.

### README

**Updated in-wave, two falsified facts.** The test count (615 → 630, in two places), and the
evals paragraph, which said offline evals "cannot grade answer quality, because the answers
are authored in the dataset" — true of the scripted answers, now incomplete as a description
of the command. It gains what became true (replay of committed recordings, all-must-pass) and
what is still true and easy to skip past (nothing is recorded yet, so the printed caveat has
not moved). **The limitation at line ~203** — *"Offline evals can't measure answer quality,
and twelve live cases are a smoke test, not a benchmark"* — is **untouched and still true**:
zero fixtures exist, so zero answers are graded. Wave 6 owns that sentence.

### STATE.md hand-edited

Per the execution instruction, `state.advance-plan` and `state.update-progress` were not run;
STATE.md was edited by hand. `roadmap.update-plan-progress 15` was run. Nothing pushed.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-15-08 | mitigate | **Closed as far as it can honestly be closed.** `fixture_current` hard-gates on `models.pipeline` and, via the exit rule, exits non-zero; the caveat prints date/model/sha/age on every offline run that graded anything. The residue is written down rather than implied: the gate compares `graph.MODEL` only, so Phase 16's independent critic model passes straight through it until the map, the gate and the recordings all move together. |
| T-15-09 | mitigate | **Closed.** ANY red or errored replay CaseResult exits 1 (mutation H red on four tests); fixtures-matched-but-never-graded exits 1 (mutation I); broken and orphaned fixtures are per-case error reds (mutations M, L); zero-fixtures-prerecording is pinned green by its own test so the rule cannot fire vacuously red. |
| T-15-10 | mitigate | **Closed.** The `anthropic` import stays inside the `--live` branch; the replay path constructs no client and touches no store. `test_replay_is_automatic_and_keyless` runs with `ANTHROPIC_API_KEY`/`VOYAGE_API_KEY`/`DATABASE_URL` all `""`, and the exact CI command was run by hand at the same emptiness. `.github/workflows/ci.yml` has zero diffs. |
| T-15-11 | mitigate | **Closed.** Recorded judge verdicts replay as gates; a flipped verdict is a red CaseResult and a non-zero exit (mutations B and G). |

**New threat surface: none.** No endpoint, no auth path, no schema change. The one new file
read is `evals/fixtures/*.json` — repo-controlled, validated by plan 01's loader, and
unreadable content is a verdict rather than an exception.

## Known Stubs

- **`evals/fixtures/` does not exist.** Every replay path in this wave is proven against
  fixtures built in tests from real graph states; no fixture has been produced by a paid run,
  and the directory CI would read is absent. That is plan 05/06's boundary, and the reason
  `zero_fixtures_is_still_green_prerecording` exists.
- **`grade_case_pins` still cannot fail** (all twelve cases pin nothing) — carried from wave
  2, and now it runs inside replay too, contributing "not asserted for this case" to every
  recorded research turn. Plan 04 authors the pins.
- **The quality thresholds still have not met a real report.** This wave's test fixtures
  route around `REPORT_MIN_CHARS`/`COVERAGE_THRESHOLD` by writing a report-shaped draft; the
  scripted corpus fails both. Wave 6's calibration recording is where the numbers get
  evidence.

## Deferred Issues

- **A fixture whose `label`s no longer match the case's follow-up questions is not detected.**
  Replay maps turns by index and grades a follow-up state against `case.followups[i]`. Turn
  *count* is checked; the question text is not, so a case whose follow-ups were reworded
  in place would replay against the wrong `Followup`. Plan 04 rewrites the dataset — worth
  a label-match check there, where the churn actually happens.
- **The all-must-pass rule and the vacuous guard both exit 1 with no way to distinguish which
  fired from the exit code alone.** They print differently (stdout block vs stderr line),
  which is enough for a human reading CI logs and not enough for a machine. Nobody needs the
  distinction yet.
- **`--min-pass-rate` now governs a denominator that mixes two populations.** With 40 cases
  and 40 recordings, a behavioural regression is diluted twice as far as it is today. The
  replay half cannot hide (all-must-pass), but the behavioural half can, and plan 04 doubles
  the denominator. Worth revisiting the floor when the dataset lands.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `91002cb` | feat | A recorded run can be graded again, for free |
| `1dfa02b` | feat | A red recording fails the build, whatever the rate says |
| `df1ef1b` | docs | The suite is 630 tests, and offline can replay recordings |
| `5f0572d` | fix | The headline verdict is the exit code, not the pass rate |

## Self-Check: PASSED

- `evals/harness.py` — FOUND (modified; `replay_case`, `grade_fixture_current`, `_recorded_judge_grades`)
- `evals/__main__.py` — FOUND (modified; `_replay_fixtures`, `_caveat`, `_fixture_metadata`, the exit rule)
- `tests/test_evals.py` — FOUND (modified, 99 → 114 tests)
- `README.md` — FOUND (modified)
- `.planning/phases/15-answer-quality-evals/15-03-SUMMARY.md` — FOUND (created)
- Commits `91002cb`, `1dfa02b`, `df1ef1b`, `5f0572d` — all four resolve in `git log`
- `.github/workflows/ci.yml` — NOT in `git diff --name-only` (verified)
- Working tree clean apart from this summary and the state files it updates
