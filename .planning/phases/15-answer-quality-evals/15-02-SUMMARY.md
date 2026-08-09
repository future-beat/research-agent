---
phase: 15-answer-quality-evals
plan: 02
subsystem: evals
tags: [quality-graders, grounding, claim-boundary, registries, mutation-testing, determinism]

# Dependency graph
requires:
  - phase: 15-answer-quality-evals
    plan: "01"
    provides: "the recorded state dict these graders are pure functions of (TurnResult.state, run_case(capture_state=True), evals/fixtures.py)"
  - phase: 15-answer-quality-evals
    plan: "research"
    provides: "Pattern 4 (the five rubrics and their claim boundaries), Pitfall 2 (calibrate before pinning), Pitfall 3 (vacuous gates)"
provides:
  - "risky_tokens / ungrounded — the shared figure-extraction core, with scale-word and currency normalisation"
  - "grade_recorded_grounding, grade_recorded_coverage, grade_recorded_structure, grade_recorded_refusal, grade_case_pins"
  - "RECORDED_GRADERS (research-turn shaped) and RECORDED_FOLLOWUP_GRADERS (follow-up shaped)"
  - "Case.must_mention / Case.must_not_claim — per-case pins, empty by default"
  - "COVERAGE_THRESHOLD / REPORT_MIN_CHARS / REPORT_MAX_CHARS / REFUSAL_PATTERNS / PROSE_COUNT_CUTOFF as named calibration knobs"
  - "A 'Cannot catch:' line on every quality grader, asserted by test — ADR-0009's claim table, machine-checked"
affects: [15-03, 15-04, 15-06, VALIDATION rows 15-02-T1+T2 and 15-02-T2]

# Tech tracking
tech-stack:
  added: []  # stdlib only: re, decimal
  patterns:
    - "A grader ships with the synthetic state it fails, and the failing test asserts on the detail string — so the red is the grader's own assertion firing, not any red at all"
    - "A registry test that fails in BOTH directions: a grader dropped from the registry, and a grader defined but never registered. One direction alone lets a check quietly stop being a check"
    - "Normalise the FORM of a figure (1M / 1 million / 1,000,000) before comparing, or a grounding rule fails honest answers for paraphrase and gets ignored"
    - "Currency survives normalisation as a marker rather than being stripped: '3 things' is prose, '$3' is a price, and the difference is what the grader exists to see"
    - "A design detail with no test that can distinguish it from its absence is not a guard — found again here by mutating the rule and watching nothing go red"

key-files:
  created: []
  modified:
    - evals/graders.py
    - evals/dataset.py
    - tests/test_evals.py
    - README.md

key-decisions:
  - "Currency is a marker, not noise to strip. The plan specified stripping '$' and then ignoring integers ≤ 10; that rule is blind to the flagship case's own $2/$10 per-MTok pricing, so a draft quietly saying $3/$9 would grade green. A number carrying a unit — currency, percent, a scale word, a decimal point — is kept whatever its size; a bare integer ≤ 10 is dropped as prose. '$2,000' still normalises to '2000', as the plan's own extractor test requires."
  - "An ISO date also yields its year, so notes dated 2026-08-31 ground a draft that says 'in 2026' while a draft inventing the exact date the notes never gave stays ungrounded. Not in the plan; without it the extractor manufactures false failures on the most common date paraphrase there is."
  - "The refusal grader counts the follow-up's own question as a source, and that rule was ungated until a mutation said so — the scripted refusal quotes no figure, so no test in the file could tell the rule from its absence. Same family as wave 1's aliasing capture."
  - "COVERAGE_THRESHOLD 0.4 and REPORT_MIN_CHARS 200 are the plan's numbers, kept unchanged and explicitly uncalibrated: measured against the only draft-shaped corpus in the repo (the twelve scripted reports) they would fail 6 and 12 of 12 respectively. Scripted reports are two sentences written to exercise routing, not reports — but that means these thresholds have never met a real one, and wave 6 is where they do."
  - "grade_case_pins currently cannot fail in the suite, because all twelve cases pin nothing. That is stated rather than hidden: the pins are authored against recordings in plan 04, and until then the grader's fail path exists only in its unit tests."
  - "DETERMINISTIC_GRADERS and FOLLOWUP_GRADERS are untouched, and a test types out their nine and three member names so 'additive' is asserted rather than asserted-in-prose."

# Metrics
duration: 41min
completed: 2026-08-09
---

# Phase 15 Plan 02: The quality graders and their claim boundaries Summary

**One-liner:** Five deterministic rubrics that grade a recorded answer — is every figure in it one the research actually found, is it about what was asked, does it look like a report, does an unanswerable follow-up admit the gap without filling it, and does it say the things this case was recorded to say — each shipped with a synthetic state it passes and one it fails, each carrying a written "Cannot catch:" line that a test enforces, and every one of them observed red on its own assertion under mutation.

## What was built

### Task 1 — figure extraction and the grounding grader (commit `61eeb90`)

`risky_tokens(text)` pulls the figures out of a piece of prose — money, percentages, decimals, large counts, years, ISO dates — and normalises them so paraphrase of *form* is not read as fabrication of *fact*:

| Input | Tokens | Why |
|-------|--------|-----|
| `1M` / `1 million` | `{1000000}` | a five-entry scale table (k/thousand, m/million, b/bn/billion, t/trillion), not a parsing library |
| `$2,000` / `2000` / `2 thousand` | `{2000}` | commas stripped, `Decimal` arithmetic so 4.5B is exactly 4500000000 |
| `5%` / `5 percent` | `{5}` | kept despite being ≤ 10 — it carries a unit |
| `two camps and 3 things about GPT-4` | `{}` | prose counts and version suffixes are not claims about the world |
| `it costs $2/$10 per MTok` | `{2, 10}` | prices are exactly what this exists to hold to the notes |
| `1. first\n2. second\n12. twelfth` | `{}` | line-leading list markers stripped before extraction |
| `through 2026-08-31` | `{2026-08-31, 2026}` | the date and its year, so "in 2026" is grounded and an invented exact date is not |

`ungrounded(draft, notes, task)` is the containment: figures in the answer that neither the notes nor the question supplied. `grade_recorded_grounding` fails on any, naming them; an empty draft is `grade_answer_present`'s business, not double-counted here.

`Case` gained `must_mention` / `must_not_claim`, both empty tuples, so all twelve existing cases construct unchanged.

**Two figures the plan's stated rule would have missed.** Strip `$` and then drop everything ≤ 10 — the plan's text, and the RESEARCH sketch's — and `$2/$10 per MTok` silently becoming `$3/$9` grades **green**. That is the flagship grounding case's own pricing, and the subtlest ungrounded claim there is: right shape, wrong source. Keeping the unit as a marker (while still normalising `$2,000` to `2000`, which the plan's extractor test requires) makes it red, and a test says so.

### Task 2 — coverage, structure, refusal, pins, and the registries (commit `34b7ce3`)

- **`grade_recorded_coverage`** — the question's content words minus a stoplist must mostly appear in the draft; `COVERAGE_THRESHOLD = 0.4`. Catches the report that wandered off (a retrieval bug swapping the topic produces fluent prose every other grader here passes).
- **`grade_recorded_structure`** — a research answer opens with `# ` and occupies 200–8000 chars. Catches the stub-as-report, the missing heading, the runaway draft. An empty draft with a `forced_stop_reason` is fine, explained — failing it would turn one guardrail firing correctly into two red graders.
- **`grade_recorded_refusal`** *(follow-up shaped)* — for `answerable=False` turns, both halves are required: the answer matches `REFUSAL_PATTERNS` **and** introduces no figure the notes never had. This is the deterministic mirror of the live judge's rule — *"if it supplies figures, forecasts, or facts not in the notes — even correct ones — that is a failure"* — and the one grader that checks two things, because "I can't answer that, but analysts put it at $4.5B by 2027" is the failure the whole pipeline exists to prevent.
- **`grade_case_pins`** — hand-authored `must_mention` / `must_not_claim` substrings. The only deterministic hook that can exist for "presents disagreement as disagreement" or "the injection payload never reached the answer".
- **`RECORDED_GRADERS`** (grounding, coverage, structure, pins) and **`RECORDED_FOLLOWUP_GRADERS`** (refusal) for plan 03's replay. `DETERMINISTIC_GRADERS` and `FOLLOWUP_GRADERS` are untouched, and a test types out their twelve member names so "additive" is a gate rather than a claim.

## Gate discipline: 23 mutations, 22 red — and the one green found a real gap

Sixteen vacuous gates across seven phases. Every selector was run under `--collect-only` **before** being trusted, and every grader was mutated rather than reasoned about.

| Selector | Collected | Required |
|----------|-----------|----------|
| `-k "quality_grader or risky or ungrounded"` | **11** | ≥ 5 |
| `-k "quality_grader or claim_boundary"` | **25** | ≥ 12 |
| `-k dataset` | **3** | acceptance criterion |

**Task 1 — the extractor and grounding**

| # | Mutation | Result | Test that went red |
|---|----------|--------|--------------------|
| M1 | scale words ignored (`1M` ≠ `1 million`) | RED | `risky_tokens_reads_a_scale_word_as_the_number_it_means` |
| M2 | currency marker dropped (the plan's rule) | RED | `risky_tokens_drops_prose_counts_but_never_prices` |
| M3 | list ordinals not stripped | RED | `risky_tokens_ignores_list_ordinals` |
| M4 | ISO date's year not emitted | RED | `risky_tokens_keeps_a_date_and_its_year` |
| M5 | the question not counted as a source | RED | `grounding_counts_the_question_as_a_source` |
| M6 | grounding can never fail | RED | `grounding_catches_an_invented_figure` |

**Task 2 — the four graders and the registries**

| # | Mutation | Result | Test that went red |
|---|----------|--------|--------------------|
| N1 | coverage can never fail | RED | `coverage_catches_an_answer_about_something_else` |
| N2 | `COVERAGE_THRESHOLD = 0.0` | RED | same — the threshold carries the gate, not the stoplist |
| N3 | heading unchecked | RED | `structure_catches_a_stub_returned_as_a_report` |
| N4 | `REPORT_MIN_CHARS = 0` | RED | same test, its other branch |
| N5 | ceiling removed | RED | `structure_catches_a_runaway_draft` |
| N6 | explained empty draft graded red | RED | `structure_accepts_an_empty_draft_a_guardrail_explains` |
| N7 | refusal phrasing unchecked | RED | `refusal_catches_an_answer_that_never_admits_the_gap` |
| N8 | refusal's grounding half unchecked | RED | `refusal_catches_an_admission_that_answers_anyway` |
| N9 | refusal can never fail | RED | all three refusal failure tests |
| N10 | `must_not_claim` ignored | RED | `case_pins_catch_a_forbidden_claim` |
| N11 | `must_mention` ignored | RED | `case_pins_catch_a_missing_mention` |
| N12 | a grader dropped from a registry | RED | `every_quality_grader_is_registered` |
| N13 | a "Cannot catch:" line deleted | RED | `every_quality_grader_states_its_claim_boundary` |
| N14 | a grader defined but never registered | RED | `every_quality_grader_is_registered` |
| P1 | coverage always scores 0 (pass direction) | RED | `coverage_passes_an_answer_about_the_question` |
| P2 | a grader consults the calendar | RED | `no_quality_grader_reads_the_clock` |
| P3 | refusal ignores the question as a source | **GREEN — see below** | then RED on a new test |

**P3 is the one worth reading, and it is wave 1's lesson arriving on schedule.** The refusal grader passes `fu.question` into `ungrounded` so an answer may repeat a figure the asker supplied. Deleting that rule broke nothing: the dataset's scripted refusal — *"The research didn't cover Gartner forecasts or spending projections"* — quotes no figure at all, so every test in the file was invariant under the change. The rule was defence with no gate on it, dressed as a gate. Fixed by a test whose refusal *does* echo the question's year (*"didn't cover Gartner's 2027 forecast"*), which passes with the rule and fails without it. Same shape as 15-01's aliasing capture, 13-05's `FrozenQueryEmbedder`, 14-01's ratio assertion: **the assertion that looks like the gate often is not the gate, and only the mutation says which.**

Mutations were applied to a scratch copy of `evals/graders.py` and reverted by file write, never `git checkout` (12-06's lesson); the file was confirmed byte-identical to its committed state after every batch.

## Verification

| Check | Baseline (measured on this tree) | After |
|-------|----------------------------------|-------|
| Full suite, plain | 584 passed / 65 skipped | **615 passed / 65 skipped** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 648 passed / 1 skipped | **679 passed / 1 skipped** |
| Offline evals, keyless | 12/12, exit 0 | **12/12, exit 0** |
| `tests/test_evals.py` | 68 passed | **99 passed** |
| `grep -c "Cannot catch:" evals/graders.py` | 0 | **6** (five graders + the section contract) |
| `grep -cE "datetime\.now\|date\.today" evals/graders.py` | 0 | **0** |
| `ruff check .` | clean | clean |

**Delta fully explained: +31 in both arms, +0 skipped in either.** The 31 are exactly the 31 tests appended to `tests/test_evals.py` (11 extraction + grounding, 20 coverage/structure/refusal/pins/registries). None needs Postgres or a key, which is why both arms moved by the same number. **Zero new skips, so nothing to justify.** No existing test was edited: every change to the file is an append plus one `import pathlib`. The offline eval CLI output is byte-identical — correct, because nothing here is wired into a run yet.

## Calibration: the thresholds have never met a real report

The only draft-shaped corpus in the repo is the twelve scripted reports, and they are two-sentence stubs written to exercise routing rather than reports. Graded anyway, as the only evidence available:

| Grader | Result on the 12 scripted reports |
|--------|-----------------------------------|
| grounding | **12/12 pass** — no false positives on the one corpus that exists |
| structure (heading) | **12/12 pass** — every scripted report opens with `# ` |
| structure (200-char floor) | **0/12 pass** — they run 37–183 chars |
| coverage (0.4) | **6/12 pass** — the misses are 38%, 22% and four at 17% |

Neither threshold was moved. `COVERAGE_THRESHOLD = 0.4` and `REPORT_MIN_CHARS = 200` are the plan's numbers, and replacing an unvalidated guess with a differently unvalidated guess fitted to stub text would be worse — a real recorded report is a thousand-plus characters and restates the question's terms, which is precisely the material these were designed against and have not yet seen. Both are named module constants with a comment saying they are calibration knobs, RESEARCH Pitfall 2 sequences the calibration recording before the full run, and **wave 6 is where these numbers meet real output.** Recorded here so nobody has to rediscover it from a wall of red at recording time.

## Deviations from Plan

### Currency is a marker, not noise to strip [Rule 2 — missing critical functionality]

The plan and the RESEARCH sketch both say `_normalise` strips `$` and `risky_tokens` then drops bare integers ≤ 10. Composed, those two rules make the grader blind to every dollar figure under $10 — including the `$2/$10 per MTok` that the flagship grounding case is *about*. A draft quietly restating it as `$3/$9` grades green under the plan's rule and red under the shipped one (`test_quality_grader_grounding_catches_a_quietly_changed_price`, and mutation M2 which restores the plan's rule and goes red). `$2,000` still normalises to `2000`, so the plan's own extractor test holds.

### `_normalise` returns `(text, marked)`, not `str`

The keep/drop decision needs to know whether a token carried a unit, and re-parsing to find out would put the same rule in two places. The plan names the function but not its return type; `risky_tokens` is the surface the tests and the other graders use.

### An ISO date also emits its year

Not in the plan. Without it, notes dated `2026-08-31` do not ground a draft that says "in 2026" — the most common date paraphrase there is — and the grader manufactures a false failure on honest output. The asymmetry still holds in the direction that matters: a draft inventing the exact date from a bare year in the notes stays ungrounded (asserted both ways in `test_risky_tokens_keeps_a_date_and_its_year`).

### Six tests beyond the plan's list

`refusal_lets_the_answer_repeat_the_questions_own_figure` (mutation P3 found the rule ungated), `every_quality_grader_is_registered` (the anti-dropout gate, red in both directions), `quality_grading_is_additive_to_the_behavioural_graders` (types out the nine + three existing grader names so "untouched" is checked), `no_quality_grader_reads_the_clock` (T-15-07's grep, as a test), `structure_catches_a_runaway_draft` and `refusal_catches_silence` (the branches the plan's list skipped).

### `STOPWORDS` is a prose block split at import

`ruff`'s SIM905 rejects `"...".split()` on a literal. Sixty quoted strings is not more readable than a paragraph of words, so the text is named first and split from the name, with a comment saying why.

### Requirements not marked complete

`REQ-offline-eval-quality` stays **Pending**. It spans all six plans; the grading vocabulary now exists but nothing has been recorded or replayed, and no answer has been graded. Phase close owns it.

### README

**Updated in-wave, one falsified fact.** The stated test count (584, in two places) is now 615. The evals limitation — *"Offline evals can't measure answer quality, and twelve live cases are a smoke test, not a benchmark"* — is **untouched and still true**: these graders are not wired into any run, and wave 6 owns that sentence per the standing instruction.

### STATE.md hand-edited

Per the execution instruction, `state.advance-plan` and `state.update-progress` were not run; STATE.md was edited by hand. `roadmap.update-plan-progress 15` was run.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-15-05 | mitigate | **Closed.** Every one of the five graders has a synthetic state it fails, and every failing test asserts on the `detail` string so the red is that grader's own assertion rather than any red at all. Twenty-three mutations run; twenty-two red on the intended test, the twenty-third green and repaired. `test_every_quality_grader_is_registered` fails in both directions — a grader removed from a registry, and a grader defined but never registered — which is the drop-out threat the register names. |
| T-15-06 | mitigate | **Closed.** Five "Cannot catch:" lines, asserted by `test_every_quality_grader_states_its_claim_boundary` over the registries rather than by grep, so a rubric cannot reach ADR-0009's table with its limits unwritten. Each names concrete blind spots (paraphrased fabrication, negation flips, on-topic non-answers, well-formed nonsense, novel refusal phrasings, hedged half-answers) plus, for grounding, its known *false positive* — a figure the notes spell out in words. |
| T-15-07 | mitigate | **Closed.** No clock in any grader; `grep -cE "datetime\.now\|date\.today" evals/graders.py` is 0, and the check is a test that reads the module source (mutation P2 red). |

**New threat surface: none.** No endpoint, no auth path, no schema change. `evals/graders.py` gained pure functions over dicts and imports nothing beyond `re` and `decimal`.

## Known Stubs

- **Nothing consumes `RECORDED_GRADERS` yet.** The registries exist and are tested; plan 03 wires them into replay. Until then these graders run only in their unit tests, which is the plan's stated boundary ("additive only").
- **`grade_case_pins` cannot fail in the suite today**, because all twelve cases pin nothing and it correctly returns "not asserted for this case". Its fail path is proven in unit tests only; plan 04 authors real pins against recordings, and until it does, this grader contributes nothing to any verdict. Stated rather than hidden — a grader that always passes is the exact shape of a vacuous gate, and this one is that shape *by design and temporarily*.
- **No grader has met a real recorded answer.** Every synthetic state here is authored or scripted. See the calibration table above for what that leaves unknown.

## Deferred Issues

- **`COVERAGE_THRESHOLD` and `REPORT_MIN_CHARS` are unvalidated against real output** — see the calibration section. Wave 6's calibration recording is where they get their first real evidence; plan 03 should expect that a fixture recorded from a terse answer may red on coverage before the numbers are tuned.
- **`REFUSAL_PATTERNS` is a maintenance cost with a name.** An honestly-refusing answer phrased outside the list fails until the list grows. Deliberate — a pattern that matched anything would pass a refusal that never came — and named in the grader's own docstring so the trade is visible where it is paid. Both apostrophe forms (`'` and `’`) are handled, because recorded prose uses whichever the model typed.
- **Spelled-out figures are a false-positive source.** Notes saying "one million" do not ground a draft saying "1M": the extractor only ever sees digits. Documented as a known false positive in the grounding docstring rather than solved, because a word-to-number parser is a much larger surface than the five-entry scale table, and no real recording has yet shown it happening.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `61eeb90` | feat | An invented figure is one the notes never gave |
| `34b7ce3` | feat | Four more rubrics that can each be shown to bite |
| `2f05af3` | docs | The suite is 615 tests |

## Self-Check: PASSED

- `evals/graders.py` — FOUND (modified, +~300 lines; 5 quality graders, 2 registries)
- `evals/dataset.py` — FOUND (modified, `must_mention` / `must_not_claim`)
- `tests/test_evals.py` — FOUND (modified, 68 → 99 tests)
- `README.md` — FOUND (modified, 584 → 615)
- `.planning/phases/15-answer-quality-evals/15-02-SUMMARY.md` — FOUND (created)
- Commits `61eeb90`, `34b7ce3`, `2f05af3` — all three resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
