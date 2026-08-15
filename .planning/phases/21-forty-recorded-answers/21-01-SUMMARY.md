---
phase: 21-forty-recorded-answers
plan: 01
subsystem: evals
tags: [fixture-coverage, settled-judge, pre-spend-baseline, operator-runbook, keyless, zero-spend]

# Dependency graph
requires:
  - phase: 21-forty-recorded-answers
    plan: "research"
    provides: "Finding 6b — the grep-verified fact that nothing in the repo compares the committed fixture set to dataset.GOLDEN; Finding 2 — technical-figures.json's models.judge reads claude-opus-5, the judge ADR-0012 superseded; Finding 3 — nothing in the evals import chain loads a .env file since PR #28; Finding 4 — file-level resumability, command-level none"
  - phase: 18-independent-eval-judge
    plan: "*"
    provides: "DEFAULT_JUDGE_MODEL = 'claude-opus-4-8' as a constant distinct from JUDGE_MODEL, which is the whole basis of P-03's env-independent judge scan"
provides:
  - "tests/test_evals.py::fixture_coverage(directory=None) — (golden − recorded, recorded − golden) as sorted id lists, on file stems, defaulting to the real tree exactly as F.fixture_paths does"
  - "tests/test_evals.py::stale_judges(directory=None) — [(filename, judge)] for every fixture whose models.judge != G.DEFAULT_JUDGE_MODEL"
  - "five both-direction unit tests proving each helper fires on synthetic directories, every red assertion naming ids/files rather than counting them"
  - "the measured pre-spend baseline: 39 missing, 0 orphans, technical-figures.json the one stale judge (claude-opus-5)"
  - ".planning/phases/21-forty-recorded-answers/21-RECORD-RUNBOOK.md — env prep with the P-06 assertion, stage 1, four batch commands, resume recipe, refusal policy, batch integrity check"
  - ".planning/phases/21-forty-recorded-answers/record-quote-before.txt — the live pre-spend preview, real exit 2, $17.4812, basis '1 measured, 39 assumed'"
  - "the command-validated fact that A∪B∪C∪D plus technical-figures partitions GOLDEN exactly, 10/11/10/8/1, no duplicates"
  - "per-batch quoted sums derived from the quote's own per-case lines rather than from the plan's arithmetic: A $3.8900, B $4.2790, C $3.8900, D $5.0645"
affects: [21-02, 21-03]

# Tech tracking
tech-stack:
  added: []  # zero packages, in any ecosystem. 21-RESEARCH's Package Legitimacy Audit is N/A and stays N/A.
  patterns:
    - "A gate proven on synthetic directories two waves before its real-directory pin can land green is not a compromise — the pins call the SAME functions, so the both-direction reds transfer, and nothing is ever committed red."
    - "An env var read at import time cannot be mutated by monkeypatch.setenv inside a test. The faithful reproduction of 'a developer shell with the variable exported' is exporting it into the pytest process."
    - "Assert against the constant, not the process-resolved value: a claim about committed FILES must not change verdict because a developer exported an env var."
    - "A baseline assertion can be vacuously satisfied by today's tree (orphans is [] whether or not the orphan direction works) — which is precisely why the synthetic red is the evidence and the baseline is only a measurement."

key-files:
  created:
    - .planning/phases/21-forty-recorded-answers/21-RECORD-RUNBOOK.md
    - .planning/phases/21-forty-recorded-answers/record-quote-before.txt
  modified:
    - tests/test_evals.py

key-decisions:
  - "Mutation (b) as the plan literally specified it — 'run the judge tests with EVAL_JUDGE_MODEL monkeypatched to the stale value' — CANNOT work, and this was verified rather than assumed. `JUDGE_MODEL = os.environ.get('EVAL_JUDGE_MODEL', DEFAULT_JUDGE_MODEL)` executes once at graders.py import; a monkeypatch.setenv inside a test body runs long after that binding. The faithful form is exporting the variable into the pytest process, which IS the 'developer shell with EVAL_JUDGE_MODEL exported' P-03 argues about. Executed that way it produced the required red. Recorded as a plan correction, not silently substituted."
  - "The three-way control on mutation (b) is what makes it evidence rather than ceremony: unmutated + exported env var = GREEN (2 passed, with G.JUDGE_MODEL confirmed to have actually moved to claude-opus-5); mutated + exported env var = BOTH judge tests RED; mutated + NO env var = GREEN (2 passed). The middle row is the red the plan asked for; the third row proves the mutation is undetectable without the export, which is exactly why P-03 matters at all."
  - "The real-tree baseline command's `not orphans` assertion is VACUOUSLY satisfied today — the tree has 0 orphans whether or not the orphan direction of fixture_coverage works at all. Mutation (a) confirmed this: with orphans forced empty, the baseline command still passes. So the baseline is a measurement and the synthetic orphan test is the gate. Stated here because a reader could otherwise mistake the green baseline command for evidence that both directions bite."
  - "Committed as one commit per task rather than TDD's separate RED and GREEN commits, per the wave's explicit atomic-commit-per-task instruction. The RED was still observed and is recorded below (5 failed, NameError, before either helper existed) — the discipline was kept, only the commit granularity differs."
  - "P-04 honoured exactly: no test reading the real evals/fixtures/ directory was committed. Run against today's tree such a pin is red (39 missing), and every commit must stay green. The real-directory pins are 21-03's, in the tree state that makes them green."

# Metrics
duration: 40min
completed: 2026-08-15
status: complete

actuals:
  tokens: 7293     # chars/4 over the realized diff (29,170 chars across all three files)
  tasks: 2
  commits: 2
---

# Phase 21 Plan 01: Keyless machinery before the money moves Summary

**One-liner:** The two fixture-set gates REQ-forty-recorded-answers needs — coverage (missing AND orphan, on stems) and settled-judge (against the constant, not the env-resolved name) — built as callable helpers, proven red in both directions on synthetic directories, with the honest pre-spend baseline measured (39 missing, 0 orphans, one stale judge) and the operator runbook whose every command was tested keyless before the wave-2 checkpoints will run it.

**Zero spend. Nothing in this wave passed `--yes`.** Every evals invocation ran with `ANTHROPIC_API_KEY="" VOYAGE_API_KEY=""` explicitly prefixed. The one full-quote capture is spend-free by construction and that was re-verified against the source, not trusted (see below).

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| Full suite, keyless (`.venv/bin/pytest -p no:warnings`) | 799 passed / 72 skipped | **804 passed / 72 skipped** | **+5 passed**, +0 skipped |
| Collected items, keyless | 871 | **876** | +5 added, **0 removed**, 0 renamed |
| `tests/test_evals.py` alone | 179 passed | **184 passed** | +5 |
| Offline evals (`python -m evals --quiet`), real `$?` | 41/41, exit 0 | **41/41 (100% vs 90% required), exit 0** | unchanged — this wave adds no fixture |
| Offline evals wall clock | — | **0.95s / 0.97s / 0.98s** over three runs (suite-internal print: `0.1s`) | the row-7 "before" measurement |
| `.venv/bin/ruff check .` | clean | **clean** | — |
| Fixtures on disk | 1 | 1 | unchanged — the 39 are wave 2's |

Note the addopts caveat that cost time elsewhere: `pyproject.toml`'s addopts already carries `-q`, so a second `-q` **suppresses** the count line. Every count above was read with `-p no:warnings` and no extra `-q`.

### The +5, reconciled

The plan claimed "roughly +3 here" and "+5 for the phase across waves 1 and 3", explicitly flagged as a claim to check. **Measured: +5 in wave 1 alone.** The plan's own `<behavior>` block lists five bullets and offers "five tests, or four if the green judge half shares a test with the red half"; the file's local style is one claim per test, so five it is — the "+3" was the low end of a range the behavior spec had already outranged. 21-03's real-directory pins land on top of these five, so the phase total will exceed +5.

| # | Test | Direction proven | Task |
|---|------|------------------|------|
| 1 | `test_fixture_coverage_names_every_golden_case_that_has_no_fixture` | missing, named as a set — `sorted({c.id for c in GOLDEN} - {"followup-uses-prior-notes"})` | 1 |
| 2 | `test_fixture_coverage_names_a_fixture_no_golden_case_claims` | orphan, named — and asserts the missing set is *unchanged* by it | 1 |
| 3 | `test_fixture_coverage_on_a_never_created_directory_is_the_whole_dataset` | pre-recording state — all 40, the docstring stating why the real pin waits for 21-03 | 1 |
| 4 | `test_stale_judges_names_the_file_and_the_superseded_judge` | judge red — file AND value: `[("followup-uses-prior-notes.json", "claude-opus-5")]` | 1 |
| 5 | `test_stale_judges_says_nothing_about_a_fixture_on_the_settled_judge` | judge green — so the red half cannot be passing because everything looks stale | 1 |

871 + 5 = 876 collected; 876 − 72 = 804. Both sides close exactly.

## The pre-spend baseline — the honest red, measured not assumed

```
missing=39 orphans=[] stale=[('technical-figures.json', 'claude-opus-5')]
first five missing: ['budget-cap-is-labelled', 'chatty-label-falls-back',
                     'contested-monorepo-vs-polyrepo', 'contested-open-weight-models',
                     'contested-rag-versus-finetuning']
PRE-SPEND BASELINE CONFIRMED
```

This is P-04 in practice. Committed today, `test_every_golden_case_has_a_committed_fixture` would be **red** — 39 of 40 golden cases have no fixture. So wave 1 proves the logic on synthetic directories and records the real tree's state as a *measurement*; wave 3 commits the pins in the tree state that makes them green.

`technical-figures.json` reads `{'pipeline': 'claude-sonnet-5', 'judge': 'claude-opus-5'}` — the judge ADR-0012 superseded. `grade_fixture_current` cannot catch this and deliberately does not try (`harness.py:383-389`): an old verdict stays a true statement about what the old judge said. `stale_judges` is the narrower claim this phase's premise licenses.

## What shipped

### Task 1 — the tracer: `8915a0e`

**RED observed first**, before either helper existed: 5 failed, `NameError: name 'stale_judges' is not defined` / `name 'fixture_coverage' is not defined`. Then the two helpers, added to a new commented section at the end of the replay-CLI block (the `committed()` neighbourhood, as the plan specified):

- **`fixture_coverage(directory=None)`** → `(sorted(golden − recorded), sorted(recorded − golden))`, where `recorded` is `{p.stem for p in F.fixture_paths(directory)}`. Stems per P-02, because `write_fixture` names every file `{case_id}.json` (`fixtures.py:194`). The docstring carries Finding 6b's verified fact: nothing in the repo compared these two sets, and the closest thing (`assert len(GOLDEN) >= 40`) is about the dataset, not about what was recorded.
- **`stale_judges(directory=None)`** → `[(path.name, judge)]` for each fixture whose `models["judge"] != G.DEFAULT_JUDGE_MODEL`. Via `F.load_fixture`, never raw `json.loads`, so a truncated or hand-edited file raises loudly instead of scanning as vacuously clean. The docstring carries P-03's full argument and the deliberate divergence from `grade_fixture_current`.

Both take an optional directory mirroring `F.fixture_paths` exactly, so **21-03's pins call these same functions verbatim** — which is what makes proving them here worth doing two waves early.

The tracer's own gate was re-run end to end before Task 2 began, per the tracer contract: 5 passed scoped, 184 passed across the file, 804 passed across the suite, ruff clean.

### Task 2 — the evidence and the runbook: `8ee74fa`

Four measurements and one document, all keyless.

**The quote, captured spend-free.** The safety property was re-verified against today's source before running, not trusted: `evals/__main__.py:505-521` builds and prints the preview, then `if not args.yes: return 2` — entirely before `import anthropic` and `anthropic.Anthropic()` at `:524-528`. The plan's line citations still hold exactly. Captured with a **real exit code of 2** (no pipe):

```
  total          $17.4812
  basis          1 measured, 39 assumed — assumed tokens dominate this quote
  estimate — treat as an upper bound; run a one-case calibration first
```

**$17.4812 against the planning-time $17.4812 — zero drift**, to the cent. Rates resolved for 2026-08-15: `claude-sonnet-5 $2/$10 per MTok · claude-opus-4-8 $5/$25 per MTok · web search $0.01/request`.

One artifact quirk worth stating so nobody reads it as corruption: the `error: --yes is required to spend...` line appears at the **top** of `record-quote-before.txt`, before the preview it logically follows. That is stdout buffering under redirection — stderr is unbuffered, stdout is not. The file is the honest capture of both streams; only their interleaving is an artifact.

**The batch partition, validated by command against `dataset.GOLDEN`.** Not by eye:

```
OK: A10 + B11 + C10 + D8 + calibration1 = 40 ids partitioning all 40 golden cases, no duplicates
```

It checks four separate things — no duplicate id (a double spend), no uncovered golden case, no batch id the dataset does not claim, and the 10/11/10/8 shape.

**The per-batch sums, re-derived from the quote's own per-case lines** rather than copied from the plan:

| Batch | Cases | Derived | Plan claimed | |
|---|---|---|---|---|
| A | 10 | $3.8900 | $3.8900 | match |
| B | 11 | $4.2790 | $4.2790 | match |
| C | 10 | $3.8900 | $3.8900 | match |
| D | 8 | $5.0645 | $5.0645 | match |
| bulk subtotal | 39 | **$17.1235** | | |
| technical-figures | 1 | $0.3577 | | |
| total | 40 | **$17.4812** | $17.4812 | match |

All four plan figures survived contact with the live quote. $17.1235 + $0.3577 = $17.4812 exactly.

**The refusal machinery, re-run rather than re-written.** Per 21-RESEARCH Finding 5, no new refusal test was needed. `pytest tests/test_evals.py -k "refus"` → **22 passed**, keyless. The load-bearing ones for the record run:

- `test_a_refused_recording_fails_the_build_at_a_rate_that_would_pass` — one refusal among forty is 97.5%, over the 90% floor; the rate gate says pass, `summary["ok"] is True` explicitly, and the build exits 1 anyway. Also asserts no fixture file was left on disk and that the closing block prints `1 case(s) were NOT recorded`.
- `test_record_refuses_a_failing_case_and_continues` — the loop does not abort.
- `test_recorder_refuses_failed_judge`, `test_recorder_refuses_failed_deterministic_grade`, `test_recorder_refuses_a_run_that_errored` — the writer's three refusal reasons.
- `test_record_refuses_without_yes` — the money gate, with client construction made an error so "we exited before spending" and "we exited before building the thing that can spend" are distinguished.

**Verified by read, as the plan asked:** `record_suite`'s per-case loop continues past a refusal. The loop is at **`harness.py:712`** (`for case in cases:` → `record_case_to_fixture` → `outcomes.append(...)`, no break, no re-raise), and its docstring states why: *"A refused case does not stop the loop... stopping would waste the spend already made on the cases behind it, and hiding it would commit a partial recording set that looks complete."* The plan cited `harness.py:546-548` — that is the *docstring* on `record_case_to_fixture` ("one case among forty"), not the loop. Both are real and both say the same thing; the citation is corrected here.

**The runbook.** Six sections, every command tested in its keyless form while writing it. No key values anywhere — a `grep -nE "sk-ant-[A-Za-z0-9]|pa-[A-Za-z0-9]{10}"` over both artifacts returns nothing.

## Mutation probes — each observed red where named, then reverted

| # | Task | Mutation | Observed |
|---|------|----------|----------|
| a | 1 | `fixture_coverage` returns an empty orphan set unconditionally | **`test_fixture_coverage_names_a_fixture_no_golden_case_claims` only**: `AssertionError: assert [] == ['no-such-case']` — on the named-stem assertion. The missing-direction test stayed **green**. The two directions are independently gated. |
| b-control | 1 | none; `EVAL_JUDGE_MODEL=claude-opus-5` exported into pytest | **2 passed.** `G.JUDGE_MODEL` confirmed actually moved (`JUDGE_MODEL= claude-opus-5 \| DEFAULT_JUDGE_MODEL= claude-opus-4-8`) and the scan did not care. P-03 observed. |
| b | 1 | `stale_judges` compares `G.JUDGE_MODEL`, with `EVAL_JUDGE_MODEL=claude-opus-5` exported | **Both judge tests red.** Red-direction: `assert [] == [('followup-uses-prior-notes.json', 'claude-opus-5')]` — the stale fixture now reads as current, which is exactly the failure P-03 forbids. Green-direction also inverted: `assert [('followup-uses-prior-notes.json', 'claude-opus-4-8')] == []`. |
| b-null | 1 | same mutation, **no** env var exported | **2 passed** — the mutation is invisible without the export. This is why the export is the mutation, and why P-03 is a real decision rather than a style preference. |
| c | 2 | drop `general-defines-a-term` from batch C's list | `AssertionError: golden case(s) no batch records: ['general-defines-a-term']` — and it fires on the **GOLDEN comparison** at the third assertion, *before* the 10/11/10/8 length check ever runs. A check that merely counted to 39 would have stayed green. |

All restored. `git diff --stat` after restore reads `140 insertions(+)` with zero deletions — the test file is a pure addition, and `grep -c MUTATION tests/test_evals.py` reads 0 at both commits.

### Mutation (b) is the finding, not a formality

The plan specified "run the judge tests with `EVAL_JUDGE_MODEL` **monkeypatched** to the stale value." That cannot produce a red, and the reason is the same import-time binding the whole decision is about: `graders.py:46` executes `JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)` **once, at import**. A `monkeypatch.setenv` in a test body runs long after, and `G.JUDGE_MODEL` never moves — so a mutated scan comparing `G.JUDGE_MODEL` would compare against `claude-opus-4-8` anyway and the tests would pass, making the mutation look sound when it was merely unreached.

Exporting the variable into the pytest process is both the working form and the *more* faithful one: P-03's stated hazard is "a developer shell with `EVAL_JUDGE_MODEL` exported", and that is literally what was run. The three-row control table above is what turns it into evidence.

## The batch-partition and env commands the runbook landed on

**The P-06 assertion** — run after any `source .env`, before every `--yes`. All three paths exercised:

| Path | Result |
|---|---|
| placeholder keys, nothing poisoning | `env ready: keys present, CRITIC_MODEL and EVAL_JUDGE_MODEL unset`, exit 0 |
| `VOYAGE_API_KEY=""` | `AssertionError: missing key(s): ['VOYAGE_API_KEY'] -- the SDK raises AFTER the money-approval, not before it` |
| both poisoning vars set | `AssertionError: set, must be unset: ['CRITIC_MODEL', 'EVAL_JUDGE_MODEL'] -- fixtures recorded now go red in keyless CI` |

The runbook states *why each one poisons fixtures*: `CRITIC_MODEL` is written into the fixture by `record_case_to_fixture` and compared against `graph.critic_model()` at replay, and keyless CI never sets it — so such a fixture is stale-red **forever**, curable only by re-recording at full price. `EVAL_JUDGE_MODEL` moves `judge.model` into `models.judge`, recording verdicts under a judge ADR-0012 did not settle, which 21-03's pin reds. It also states that `source .env` is itself a way to set them, which is why the assertion runs *after* the sourcing.

Current shell state, checked: both are `<unset>`.

**The resume recipe** was tested against today's tree (batch A): `10 of 10 still unrecorded`, then paste-ready flags — `--case contested-viewpoints --case sparse-coverage ...`. It intersects `fixture_coverage()`'s missing set with the batch's ids, which is the only safe resume: `write_fixture` has **no skip-if-exists check**, so a blind re-run of a batch that died at case 7 of 11 pays for cases 1–6 twice.

## Plan claims checked against measurement

| Plan claim | Measured | |
|---|---|---|
| pre-spend: 39 missing, 0 orphans, `technical-figures.json` stale | identical | confirmed |
| quote total ≈ $17.4812 | $17.4812 | exact, zero drift |
| batch sums A/B/C/D $3.8900 / $4.2790 / $3.8900 / $5.0645 | identical | all four exact |
| batches partition the 39 as 10/11/10/8 | 10/11/10/8, no dupes, no uncovered | confirmed by command |
| suite delta "roughly +3 here" | **+5** | corrected |
| stage 1 costs "~$0.39" (21-CONTEXT) | **$0.3577** | corrected |
| refusal machinery already covered, no new test needed | 22 refusal tests green | confirmed |
| `harness.py:546-548` is the continuing loop | loop is at **`:712`**; `:546-548` is the docstring | citation corrected |
| the quote is capturable with no client built | re-verified at `__main__.py:505-521` vs `:524-528` | confirmed |

The stage-1 correction is worth a sentence rather than a row: `technical-figures` is the single case the preview prices from a *measured* fixture (`measured pipeline $0.2427 (fixture 2026-08-10) + assumed judge`) instead of assumed tokens, so its scoped quote is $0.3577. The $0.39 in 21-CONTEXT is the assumed-token price every *other* single-turn case carries. Both numbers are right about different things; the runbook states the one the operator will actually see.

## Deviations from Plan

**1. [Rule 3 — blocking] Mutation (b)'s specified mechanism could not fire; the faithful mechanism was substituted and both are recorded.**
- **Found during:** Task 1, mutation phase.
- **Issue:** `monkeypatch.setenv("EVAL_JUDGE_MODEL", ...)` cannot move `G.JUDGE_MODEL`, which is bound at import time. The mutation would have appeared sound while never being reached.
- **Fix:** exported `EVAL_JUDGE_MODEL=claude-opus-5` into the pytest process — the literal "developer shell with the variable exported" that P-03 argues about — and added two control runs (unmutated+exported, mutated+unexported) to prove the red is caused by the mutation and not by the export.
- **Files modified:** none (mutation applied and reverted).
- **Commit:** `8915a0e` (the observation is recorded in the commit message and above).

**2. [documentation] One commit per task rather than TDD's separate RED/GREEN commits.**
- **Reason:** the wave's execution instructions specify an atomic commit per task explicitly. The RED was observed and recorded (5 failed, `NameError`, before either helper existed); only the commit granularity differs from the `tdd="true"` default.

**3. [citation] `harness.py:546-548` corrected to `:712` for the continuing loop.** Both locations exist and agree; the plan pointed at the docstring rather than the code.

No architectural changes were needed. No Rule 4 checkpoint was reached. No package was installed in any ecosystem.

## Known Stubs

None. No placeholder values, no `TODO`/`FIXME`, no skipped tests added, no `<verify>` left unrun. Every command in the runbook was executed in its keyless form; the four `--yes` commands are the wave-2 operator's by design and were deliberately **not** run.

## What wave 2 needs from this

1. **Read `21-RECORD-RUNBOOK.md` and follow it verbatim.** Every command in it was tested.
2. **The env assertion is not optional and is not once-per-phase** — re-run it before each of the five `--yes` invocations. A slept laptop or a new terminal is a new environment.
3. **Checkpoint 1 shows $0.3577**, not $0.39, for the calibration case. The re-quote at checkpoint 2 supersedes every planning-time number in this file.
4. **After stage 1, check `models.judge` reads `claude-opus-4-8`** before spending on 39 more. That one `python -c` catches a poisoned shell at one case's cost instead of forty's.
5. **A batch exiting non-zero on a refusal is the machinery working.** Commit what was written, quote the `recordings[]` entry, pause. No retry in the same invocation, no `--force`, ever.
6. **Never re-run a full batch command to resume it** — `write_fixture` overwrites and the recorder re-spends. Use the runbook's resume recipe.

## Self-Check: PASSED

Files:
- `FOUND: tests/test_evals.py` (modified, +140 lines, 0 deletions)
- `FOUND: .planning/phases/21-forty-recorded-answers/21-RECORD-RUNBOOK.md`
- `FOUND: .planning/phases/21-forty-recorded-answers/record-quote-before.txt`

Commits:
- `FOUND: 8915a0e` — `test(21-01): the two fixture-set gates, red in both directions`
- `FOUND: 8ee74fa` — `docs(21-01): the operator runbook and the captured pre-spend quote`

Gates at close: suite **804 passed / 72 skipped**; `tests/test_evals.py` **184 passed**; offline evals **41/41, exit 0**; `ruff check .` **clean**; working tree clean; no key-shaped string in any committed artifact.
