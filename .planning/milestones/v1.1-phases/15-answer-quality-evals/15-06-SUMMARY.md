---
phase: 15-answer-quality-evals
plan: 06
subsystem: evals + docs
tags: [adr, claim-boundary, calibration, first-live-recording, cost-preview, deferral, mutation-testing]

# Dependency graph
requires:
  - phase: 15-answer-quality-evals
    plan: "02"
    provides: "the five quality graders and their 'Cannot catch:' docstrings — the source ADR-0009's claim table is assembled from"
  - phase: 15-answer-quality-evals
    plan: "03"
    provides: "replay, the all-must-pass exit rule, grade_fixture_current and its own claim boundary, the caveat rewrite"
  - phase: 15-answer-quality-evals
    plan: "05"
    provides: "the --record CLI, its runtime cost preview, and the assumed-token constants this wave calibrated"
provides:
  - "docs/adr/0009-recorded-answer-quality-evals.md — the replacement guarantee for DEC-20's scope"
  - "evals/fixtures/technical-figures.json — the first real recording, $0.2427 of measured spend, replaying green keyless"
  - "The measured claim boundary: grounding is role-blind, and the counter-example that shows it"
  - "Preview token constants corrected against a measurement, with the still-unmeasured ones labelled"
  - "An explicit, recorded DEFERRAL of the full 40-case record run"
affects: [16, 17, 15-VALIDATION all rows, README, docs/DESIGN.md, docs/adr/README.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "An estimate can be an upper bound in total and a 35% under-quote in the half that matters — decompose an aggregate before trusting its direction"
    - "A test can be green because a directory is empty; the first artefact in it runs code the test never reached"
    - "A documented blind spot is pinned with BOTH directions, or it passes equally against the check having stopped working"
    - "The staleness gate gets a cannot-catch line like the rubrics do, because a gate that cannot fire is worse than none — it is believed"
    - "A deferral stated is a phase outcome; a deferral unstated is a gap somebody discovers later"

key-files:
  created:
    - docs/adr/0009-recorded-answer-quality-evals.md
    - evals/fixtures/technical-figures.json
  modified:
    - docs/adr/README.md
    - docs/DESIGN.md
    - README.md
    - evals/__main__.py
    - evals/graders.py
    - tests/test_evals.py

key-decisions:
  - "The calibration ran BEFORE the docs, inverting the plan's task order. The README bullet has to state the fixture count and the ADR quotes the shipped thresholds; writing either before the recording existed would have committed a knowingly-provisional claim and then amended it."
  - "The preview constants were corrected, because a 35% under-quote on the pipeline half is 'badly off' by the plan's own test. Rule applied: raise what the measurement exceeded, keep what it did not — so the quote stays an upper bound for the topology measured rather than a point estimate fitted to one run. The full-run quote moves $12.78 → $16.51."
  - "Grounding's role-blindness was NOT fixed. The fix that motivated the finding does not close it (the collision survives), and closing it properly means positional or role-aware grounding — a far larger surface with false positives of its own. It is documented and pinned instead, which is what a claim boundary is for."
  - "The bolded-list-ordinal gap (`**4. Item` is not stripped) was found and deliberately left alone: it does not change any verdict here, and making the extractor stricter risks new false positives across 28 authored reports on the strength of one observation."
  - "REQ-offline-eval-quality is marked Complete with its coverage stated — 1 of 40 answers measured — rather than left Pending. The requirement asks that quality become measurable; it has, and the honest qualifier belongs in the traceability cell, not in an unticked box."

# Metrics
duration: 62min
completed: 2026-08-10
---

# Phase 15 Plan 06: ADR-0009, the README claim, and the first real recording Summary

**One-liner:** The recorder ran against a real API for the first time — one case, $0.2427, committed and replaying green keylessly on every push — and the three things that only a real run could find are now in the code, the pins and the record: a cost preview that was quietly under-quoting by 35%, a CLI test that had been passing because a directory was empty, and a grounding grader that will pass a fabricated price if a version number elsewhere in the notes happens to be the same digit.

## The full-run outcome, stated because the phase requires it

**DEFERRED.** The 40-case record run was not executed. The operator authorised the calibration case and explicitly did not authorise the full run.

- Quote at the time of the decision: **$16.51** (post-calibration; it was $12.78 before the constants were corrected), and **$21.06** from 2026-09-01 when Sonnet 5's introductory window closes. Recording before September is the only time-sensitive argument, and it is an argument about price, not about readiness.
- **The machinery is proven, not assumed.** The calibration case exercised preview → refusal → real spend → judge → refusal-check → write → keyless replay, end to end, against the real API. Nothing about the record path is unexercised.
- **Deferral does not block phase closure.** The replay leg grades whatever fixtures exist, and zero-or-few is a legal green state pinned by `test_zero_fixtures_is_still_green_prerecording`. CI is green either way.
- **What it defers with it:** Phase 17's before-evidence on the four tagged follow-up cases, and any claim broader than "one recorded answer". The README says *fixtures exist for 1 of 40* rather than implying a recorded benchmark.

Recorded in five places so it cannot be lost: this SUMMARY, `15-VALIDATION.md`'s full-run row, `ROADMAP.md`'s phase notes, `REQUIREMENTS.md`'s traceability cell, and the README bullet.

## Task 2 (run first) — the calibration: the recorder's first live execution

### It worked, first time

```
  cost preview
  technical-figures  $0.2950  assumed tokens at 2026-08-09 rates
  total          $0.2950
  basis          0 measured, 1 assumed — assumed tokens dominate this quote

  REC   technical-figures  $0.2427  -> evals/fixtures/technical-figures.json
  PASS  1/1 cases (100% vs 90% required)
  recorded 1/1 case(s) · previewed $0.2950 · measured pipeline $0.2427 + 2 judge call(s)
```

Verified against the artefact rather than the console:

| Checked | Result |
|---------|--------|
| Preview without `--yes` | exit **2**, nothing run, no client built |
| `models` map | `{"pipeline": "claude-sonnet-5", "judge": "claude-opus-5"}` |
| Judge verdicts | `judge_grounding` ✓, `judge_answers_the_question` ✓ — both recorded, both passed |
| `git_sha` | `225b06b` — matches `git rev-parse --short HEAD` |
| `pipeline_cost_usd` | `0.242717` (RESEARCH predicted $0.15–0.25) |
| Fixture size | **10,097 bytes** (RESEARCH assumption A5: 5–25 KB) |
| `forced` stamp | absent — the recording passed on its own merits |
| Secrets scan | no `sk-ant`, `pa-`, `api_key`, `Bearer`, or DSN anywhere in the file; `owner` is `""` |
| Keyless replay | **41/41, exit 0**, all 16 grades green, caveat prints date/model/sha/age |

The recorded run took the cheapest path the graph has: 4 calls, 0 revisions, `topic_type=technical`, `approved=True`, notes 3,225 chars, draft 2,594 chars.

### Calibration proper: the thresholds needed no tuning, and here is why that is a real result

Wave 2 shipped `COVERAGE_THRESHOLD = 0.4` and `REPORT_MIN_CHARS = 200` having measured them only against two-sentence routing stubs. Against the first real report:

| Grader | Result | Margin |
|--------|--------|--------|
| `recorded_grounding` | pass | **28 extracted figures, every one traced to the notes** — not a vacuous pass |
| `recorded_coverage` | pass | **75%** against a 40% floor |
| `recorded_structure` | pass | **2,594 chars** in a 200–8,000 range, opens with `# ` |
| `case_pins` | n/a | not asserted for this case |

**Neither threshold was moved**, and this time that is evidence rather than deferral. The 28 figures include `$1`, `$2`, `$3`, `$5`, `$10`, `$15` — bare integers ≤ 10 that survive only because wave 2 refused the plan's "strip `$` then drop small numbers" rule. That deviation earned its keep on real output today.

**The known spelled-out-figure false positive did not occur:** draft and notes both used `1M` and `128K`, never "one million". Recorded as *not observed*, not as *disproved*.

### The finding: grounding is role-blind, measured on the real transcript

Mutating the recorded draft to see whether the graders bite:

| Mutation on the real recording | grounding | coverage | structure |
|-------------------------------|-----------|----------|-----------|
| `73.3%` → `81.9%` (invented benchmark) | **RED** | pass | pass |
| `1M tokens` → `3M tokens` | **RED** | pass | pass |
| off-topic draft | pass | **RED** (0%) | pass |
| truncated to 150 chars | pass | pass | **RED** |
| **`$2 (intro` → `$4 (intro` (a quietly fabricated price)** | **GREEN** | pass | pass |

The last row is the finding. Traced to its cause rather than guessed at: the notes contain one aside — *"the earlier 3.x/4.0 model generations"* — and `4.0` normalises to `4`. Containment is a **set** test, so a `4` anywhere in the notes grounds a `$4` anywhere in the draft, whatever either place meant by it. Normalisation, which exists so paraphrase of *form* is not read as fabrication of *fact*, is the same mechanism that erases the form carrying the role.

**The gap is role, not magnitude** — the same recording reds immediately on figures the notes carry in no role at all.

**Not fixed, and the reasoning is on the record.** The obvious repair (also strip list ordinals inside bold markup, `**4. Item`, which the extractor misses) does *not* close this: `4` is still grounded by the `4.0` aside. Real closure means positional or role-aware grounding, a far larger surface with false positives of its own. So it is written into the grader's docstring, reproduced in ADR-0009's cannot-catch column, and **pinned by a test**.

The pin asserts both directions in one test on purpose. A green alone would pass equally against a grounding grader that had stopped working, and the test would then document a blind spot that no longer described the code. The second half is the same edit to a figure the notes never carry (`$7`), which must still be red.

### The finding: the preview was under-quoting by 35%, and the total hid it

$0.2950 previewed, $0.2427 measured — which reads as a conservative estimate and is not one:

| Half | Assumed | Measured |
|------|---------|----------|
| Pipeline | $0.1800 | **$0.2427** (+35%) |
| Judge | $0.1150 | not measured (the judge holds its own client; its tokens never reach a run's usage totals) |
| Total | $0.2950 | — |

The total looked safe only because the judge assumption was generous. Corrected by the rule **"raise what the measurement exceeded, keep what it did not"**:

| Constant | Was | Now | Basis |
|----------|-----|-----|-------|
| `ASSUMED_RESEARCH_INPUT_TOKENS` | 40,000 | **72,000** | measured 71,333 |
| `WEB_SEARCHES_PER_RESEARCH_TURN` | 2 | **5** | measured 5 |
| `ASSUMED_RESEARCH_OUTPUT_TOKENS` | 8,000 | 8,000 | measured 5,000 — the higher figure kept as headroom |
| follow-up ×2, judge ×2 | unchanged | unchanged | **labelled `# unmeasured` in the file** — this case has no follow-ups, and nothing here measured the judge |

The comment also states that the measured turn took the cheapest topology (4 calls, 0 revisions), so a case whose critic sends the draft back exceeds every number there. **The full-run quote moves $12.78 → $16.51** ($21.06 from 2026-09-01), and the basis line now reads `1 measured, 39 assumed`, exactly as wave 5 predicted it would.

No test changed: wave 5 derived its expectations *from* these constants precisely so a calibration could edit numbers instead of tests.

### The finding: a test that was green because a directory was empty

Committing the first fixture turned `test_cli_exits_nonzero_when_the_threshold_is_not_met` red with `KeyError: 'cases'`. That is a fact about the fake, not the CLI: the test stubs `run_suite` with a dict carrying only `summary` and `judge_calls`, while the real function always returns a `cases` list — and the CLI line that merges replay results into it **had never executed in this test**, because `evals/fixtures/` was empty and there was nothing to merge.

Two fixes, and the second is the load-bearing one:

1. The stub carries the key its contract carries.
2. `FIXTURES_DIR` is redirected to an empty directory. Without it the recorded case's *green* replay recomputes `report["summary"]` from `behavioural + replay_results` — and since `run_suite` is stubbed, `behavioural` is empty, so the test's failing summary is discarded and it asserts nothing at all. It would have gone green for the wrong reason.

The replay section's comment ("every test here monkeypatches `FIXTURES_DIR`: the repo has no recordings yet") was hygiene and is now a requirement; it says so.

## Task 1 — ADR-0009, the index, DESIGN, README

**`docs/adr/0009-recorded-answer-quality-evals.md`**, on the 0008 precedent exactly: `**Status:** Accepted`, a `**Source:**` line, no supersession — DEC-20 was never promoted, so what survives and what is new are argued in prose.

- **What survives of DEC-20:** the caveat prints on every run (both shipped forms quoted verbatim from `evals/__main__.py`); the suite still never claims the current model is good; free/deterministic/keyless every-push untouched; the judge stays live-only.
- **What is new:** a per-grader table with **both** columns — what each rubric may claim and what it cannot catch — copied from the docstrings a test already enforces, plus the role-collision finding above.
- **The staleness mechanism:** model mismatch gates, age prints and never grades, the recorder refuses a red recording.
- **The gate's own claim boundary**, in its own section: `fixture_current` reads `models["pipeline"]` against `graph.MODEL` and nothing else, so **Phase 16's independently configurable critic will not fire it**; closing that needs a per-node map entry, the gate extended, and a re-record — all three together.
- **Rejected alternatives** with the CONTEXT rationale: scheduled live job (unattended spend, provider outages), judge-only (not deterministic), reference answers (rot as models change).
- **One line on the judge**, and no more: verdicts are recorded as fixture metadata. `grep -c "DEC-22"` in the ADR is **0**.

**`docs/adr/README.md`** — the 0009 index row, count 8 → 9, the odd-ones-out paragraph now covering 0006–0009, and the supersedes-nothing paragraph generalised to both 0008 and 0009 with the parallel spelled out: DEC-20's caveat is carried forward and *upgraded*, exactly as DEC-10's copy-only guarantee was preserved as a named command.

**`docs/DESIGN.md` § Testing** — the original argument is untouched (0009's Context quotes it) and gains a forward link.

**`README.md` § Limitations** — the bullet that survived four waves. It now says what the offline suite measures (recorded answers, deterministically, all-must-pass), what it cannot (that the *current* model produces them; and that a *critic*-model change won't even trip the staleness gate), the graders' blind spots including the measured price/version collision, and **fixtures exist for 1 of 40 cases**. Also corrected in-wave: the test count (662 → 663, two places), the eval CLI comment, and the two paragraphs that still said nothing had been recorded.

## Gate discipline

**Every selector `--collect-only` first.** All eleven VALIDATION selectors were collected and run at phase close:

| Selector | Collected | Passed |
|----------|----------:|-------:|
| `recorder_captures_schema` / `recorder_refuses_failed_judge` / `fixture_roundtrip` | 1 each | 1 each |
| `quality_grader` | 26 | 26 |
| `claim_boundary` | 2 | 2 |
| `replay or orphaned` | 13 | 13 |
| `model_mismatch_gates` | 1 | 1 |
| `caveat_wording` | 2 | 2 |
| `dataset_taxonomy` | 7 | 7 |
| `record_preview` | 6 | 6 |
| `reused_in_another_role` (new) | 1 | 1 |

**Mutations: 4 run, 4 red.**

| # | Mutation | Result | What went red |
|---|----------|--------|---------------|
| A | `grade_recorded_grounding` can never fail | RED ×3 | including the **second half** of the new blind-spot test — so the documented green is a gap in reach, not a gap in function |
| B | the `"." in digits` marker dropped (a decimal no longer marks a figure) | RED ×1 | **only** `..._cannot_see_a_figure_reused_in_another_role` — that rule had shipped with no test able to tell it from its absence |
| C | the **committed fixture's** `models.pipeline` → `claude-sonnet-4` | RED | the keyless CLI exits **1** with `fixture_current: recorded on 'claude-sonnet-4' but this tree runs 'claude-sonnet-5'`; restored, exits 0. The staleness gate exercised against a real artefact for the first time |
| D | `return 0 if ok else 1` → `return 0` | RED | `test_cli_exits_nonzero_when_the_threshold_is_not_met` — the repaired test still discriminates |

Mutation B is this wave's instance of the phase-long lesson, and it landed on a rule wave 2 shipped: **the assertion that looks like the gate often is not the gate, and only the mutation says which.**

All mutations were applied to a scratch copy and reverted by file write, never `git checkout` (12-06's lesson); every touched file was confirmed byte-identical to its committed state afterwards, and the fixture's restoration was confirmed by `git diff --stat` being empty.

**Prose grep gates, honest-green form with measured baselines:**

| Gate | Baseline (measured) | After |
|------|--------------------|-------|
| `docs/adr/0009-*.md` exists | absent | present |
| `grep -c "**Status:** Accepted"` in it | — | **1** |
| `grep -c "Source:"` in it | — | **1** |
| `grep -ci "cannot catch"` in it | — | **3** (per-grader column, the gate's own section, the register line) |
| `grep -c "0009" docs/adr/README.md` | **0** | **5** |
| `grep -c "0009" docs/DESIGN.md` | **0** | **1** |
| `grep -c "Offline evals can't measure answer quality" README.md` | **1** | **0** |
| `grep -c "DEC-22"` in the ADR | — | **0** |
| ADR records | 8 | **9** |
| `grep -c 'ANTHROPIC_API_KEY: ""' .github/workflows/ci.yml` | **1** | **1** (zero diffs, whole phase) |

All four markdown files were link-checked; zero broken relative links.

## Verification

| Check | Baseline (measured on this tree) | After |
|-------|----------------------------------|-------|
| Full suite, plain | 662 passed / 65 skipped | **663 / 65** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 726 passed / 1 skipped | **727 / 1** |
| Offline evals, keyless, `--min-pass-rate 0.9` | 40/40, exit 0 | **41/41, exit 0** |
| `tests/test_evals.py` | 146 | **147** |
| `evals/fixtures/*.json` | **0** | **1** |
| `.venv/bin/ruff check .` | clean | clean |
| `.github/workflows/ci.yml` in `git diff` | — | **no** |

**Delta fully explained: +1 in both arms, +0 skipped in either.** The one test is `test_quality_grader_grounding_cannot_see_a_figure_reused_in_another_role`; it needs neither Postgres nor a key, which is why both arms moved identically. One existing test was edited (`test_cli_exits_nonzero_when_the_threshold_is_not_met`) — forced by the first fixture, documented above. **Zero new skips, so nothing to justify.**

The eval run gained one case (40 → 41) because the replay leg now has something to grade.

## Deviations from Plan

### The calibration ran before the docs, inverting Tasks 1 and 2 [Rule 3 — blocking-adjacent]

The plan orders ADR/README first. The README bullet must state the fixture count, and the ADR quotes the shipped thresholds — both of which the recording could change. Writing them first would have committed a knowingly-provisional claim and then amended it in the same wave. The plan's own Task 2 step 4 authorises grader tuning at calibration time, which is a further reason the docs cannot lead. Nothing else about task content moved.

### The plan's README grep gate was vacuous, and the honest one is recorded instead

`grep -c "twelve live cases are a smoke test" README.md` was stated as baseline **1**; it measured **0**, because wave 4 had already removed that clause when it corrected the case count. The gate would have passed without any edit. The honest gate is on the claim the wave actually owns — `Offline evals can't measure answer quality`, measured baseline **1**, now **0**. Recorded in `15-VALIDATION.md` as the phase's vacuous gate. **A plan's stated baseline is a claim to check** — fifth time in this phase family.

### The preview constants were corrected [Rule 1 — the estimate was wrong in the direction that matters]

Authorised by the plan's Task 2 step 4 ("if the assumed-token preview constants were badly off the measured cost, correct the constants now"). 35% under on the pipeline half qualifies. Detail above; the still-unmeasured constants are labelled rather than silently kept.

### An existing test was edited, and it was not optional

`test_cli_exits_nonzero_when_the_threshold_is_not_met` cannot pass with a fixture on disk. Detail above. This is the only existing test edited in this wave.

### The grounding blind spot was documented and pinned, not fixed

Reasoning above. A related smaller gap was also found and deliberately left: the extractor strips line-leading list ordinals (`1. `, `2) `) but not ones inside emphasis (`**4. Item`), so a bolded list number is read as a figure. It does not change any verdict here — `4` is grounded by the `4.0` aside regardless — and making the extractor stricter on the strength of one observation risks new false positives across the 28 authored reports. Logged here rather than acted on.

### `REQ-offline-eval-quality` is marked Complete, with its coverage stated

Five waves deferred it to phase close on the grounds that nothing had been recorded. Something has. All three clauses hold: quality is measurable without billing every push (proven by a paid run and graded free on every push since), the case count is 40 across a stated taxonomy, and `ANTHROPIC_API_KEY=""` never moved. The traceability cell states **1 of 40 answers measured** and links ADR-0009, so the box being ticked does not overstate the coverage.

### `roadmap.update-plan-progress 15` was NOT run, and the notes cell was restored by hand

The carry-in warning was accurate: commit `225b06b` shows the phase-15 notes cell **blanked** by a previous run of that command (it also left the count stuck at 4/6 after wave 5 completed). The row was rewritten by hand — 6/6, `Executed — awaiting verify + PR`, and a notes cell covering all six waves.

The top-level `- [ ] **Phase 15**` checkbox in the roadmap's phase list was left unticked, matching phases 13 and 14 which are complete and also unticked; that list appears to be ticked at merge, not at execution. Flagged rather than changed unilaterally.

### STATE.md hand-edited

Per the execution instruction, `state.advance-plan` and `state.update-progress` were not run. STATE.md was stale at wave 4 (wave 5's executor was interrupted before updating it), so this wave's edit carries waves 5 and 6 together.

### Nothing pushed

Branch `gsd/phase-15-answer-quality-evals`, unpushed, as instructed.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-15-19 | mitigate | **Closed.** Every claim in ADR-0009's table is copied from a docstring a test enforces, the staleness gate has its own cannot-catch section, and the README states `fixtures exist for 1 of 40 cases` rather than implying a recorded benchmark. The one claim written from measurement rather than docstring — the role collision — was measured on the real recording and pinned by a test. |
| T-15-20 | mitigate | **Closed.** Both spending acts were operator-gated. The preview printed and exited 2 before any client was constructed; the calibration was authorised at one case and cost $0.2427; the full run was **not** authorised and is a recorded deferral rather than a silence. Total spend this wave: **$0.2427** plus 2 judge calls billed separately. |
| T-15-21 | mitigate | **Closed, and the ordering paid off.** Calibrating before the full run is exactly what surfaced the role collision and the 35% under-quote — both invisible to the 28-report authored corpus, because authored reports do not contain a stray `4.0` in an aside and do not consume 71,333 tokens. Thresholds were not moved; the two things that were wrong were a *constant* and a *claim*, which is the outcome a calibration step exists to produce. |

**New threat surface: none.** No endpoint, no auth path, no schema change. One new committed file is read by CI — `evals/fixtures/technical-figures.json` — repo-controlled, validated by plan 01's loader, scanned for credentials before commit (`owner` is `""`, no key material, no DSN), and unreadable content is a verdict rather than an exception.

## Known Stubs

- **39 of 40 cases still grade authored answers.** The behavioural leg is unchanged and measures the pipeline only. The README, ADR and requirements cell all say `1 of 40`.
- **The quality thresholds have met exactly one real report.** Comfortable margins on one sample is evidence they are not absurd; it is not validation across the taxonomy, and the ADR says so in Consequences.
- **`case_pins` still contributes nothing to any verdict.** The one recorded case pins nothing (`technical-figures` has no `must_mention`/`must_not_claim`), so the grader returns "not asserted for this case" on the only leg that runs it. The seven cases that *do* pin something have no recordings.
- **The judge's token cost is still an assumption.** It bills separately, holds its own client, and nothing in this recording measured it — labelled `# unmeasured` in the constants rather than implied measured by proximity to the ones that are.
- **Offline, the injection cases still prove plumbing and pins, not resistance.** Carried from wave 4 and unchanged: neither adversarial case is recorded, so whether a real writer resists a poisoned note remains untested.

## Deferred Issues

- **The full 40-case record run.** Stated above. $16.51 now, $21.06 from 2026-09-01.
- **The follow-up label-match check** — deferred through waves 3, 4 and 5 and still open. A fixture whose turn labels no longer match `case.followups[i]` replays against the wrong `Followup`; only turn *count* is checked. Now marginally more real than before, since fixtures exist.
- **The bolded-list-ordinal gap in `risky_tokens`.** `**4. Item` is read as the figure 4. Found here, deliberately not acted on (reasoning above).
- **`--min-pass-rate 0.9` over a mixed denominator.** 41 cases now; four behavioural reds is still ~90% and exits 0. The replay leg cannot hide; the behavioural leg can. Carried from wave 3, unchanged by this wave, and worth revisiting when the fixture count grows.
- **Grounding's role-blindness itself.** Documented and pinned rather than closed. Anyone who closes it must red `test_quality_grader_grounding_cannot_see_a_figure_reused_in_another_role` and update ADR-0009 — which is the mechanism, not an oversight.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `2174e4c` | feat | The first answer this repo ever graded is a real one |
| `28f41cf` | fix | The preview's token assumptions, corrected by a measurement |
| `807f088` | test | A test that only passed because nothing had been recorded |
| `c294c08` | docs | What the first real recording showed grounding cannot see |
| `78ae41a` | docs | ADR-0009 — what a green offline run is now allowed to mean |

## Self-Check: PASSED

- `docs/adr/0009-recorded-answer-quality-evals.md` — FOUND (created)
- `evals/fixtures/technical-figures.json` — FOUND (created, 10,097 bytes, replays green keyless)
- `docs/adr/README.md` — FOUND (modified; 0009 row, count 8 → 9, both convention paragraphs)
- `docs/DESIGN.md` — FOUND (modified; § Testing forward-linked, original argument intact)
- `README.md` — FOUND (modified; Limitations bullet rewritten, counts corrected)
- `evals/__main__.py` — FOUND (modified; calibrated constants)
- `evals/graders.py` — FOUND (modified; grounding's measured claim boundary)
- `tests/test_evals.py` — FOUND (modified, 146 → 147)
- `.planning/phases/15-answer-quality-evals/15-06-SUMMARY.md` — FOUND (created)
- Commits `2174e4c`, `28f41cf`, `807f088`, `c294c08`, `78ae41a` — all five resolve in `git log`
- `.github/workflows/ci.yml` — NOT in this phase's diff (verified)
- Working tree clean apart from this summary and the planning files it updates
