---
phase: 17-followups-that-can-reach-for-new-information
plan: 01
subsystem: evals
tags: [grader-redesign, scripted-client, cost-preview, zero-behaviour-change, gate-discipline]

# Dependency graph
requires:
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "research"
    provides: "Q5 — the four flipping cases, the grader table, the scripting mechanics, and Pitfalls 5 and 7"
provides:
  - "Followup.expect_research / .insufficiency / .research_notes — the script and the expectation a reaching follow-up needs, all defaulting to today's behaviour"
  - "ScriptedClient.researcher_notes — per-call researcher outputs (pop-list, verdicts idiom), so the second research pass finds something the first did not"
  - "ScriptedClient.answers interleaved — the INSUFFICIENT sentinel then the post-research answer, two responder outputs in one turn"
  - "grade_followup_research_bounded — expectation-keyed: False is the old unconditional check verbatim; True demands exactly one researcher pass and zero classifier passes"
  - "grade_followup_reach_traced + FOLLOWUP_RESEARCH_REASONS — SC-4's trace event graded rather than asserted"
  - "_assumed_pipeline_cost prices expect_research follow-up turns at the research constants with their five web searches"
affects: [17-02, 17-03, 17-04]

# Tech tracking
tech-stack:
  added: []  # zero packages installed (RESEARCH § Package Legitimacy Audit: not applicable)
  patterns:
    - "Retire a grader by scoping it, not by deleting it: the expect_research=False branch is the old body verbatim, so the surviving property is provably the same check rather than a re-derivation that happens to look similar."
    - "A new grader is not trusted until a mutation shows it firing in the real suite, not only in its unit test. Two probes here dropped the 41-case run to 33/41 — that is the proof the registry actually reaches it."
    - "Bound a count on BOTH sides. `researched != 1` reds zero (the reach never happened) as well as two (the one-pass bound broke); `> 1` would have shipped the silent half ungated."
    - "Fix a cost assumption when the topology changes, not when the invoice arrives. Phase 15 paid $0.24 to learn its quote read 35% low; the same failure was structurally available here and cost nothing to close."
    - "Pop-list script exhaustion falls back rather than raising: an unscripted extra call should be something the graders describe, not a traceback that ends the run before anything is graded."

key-files:
  created: []
  modified:
    - evals/dataset.py
    - evals/harness.py
    - evals/graders.py
    - evals/__main__.py
    - tests/test_evals.py
    - README.md

key-decisions:
  - "grade_followup_reach_traced rejects an UNRECOGNISED reason, not merely a missing one. The plan asked for 'contains no_prior_research or notes_insufficient'; a grader that only checks presence would accept `followup_research: 'because'` from a future refactor and still call SC-4 graded. FOLLOWUP_RESEARCH_REASONS is the named vocabulary and probe P8 reds a value outside it."
  - "The `no_prior_research` literal was swapped for `budget_exceeded` in the synthetic-state tests, and the contrasting wrong-stop became `max_revisions_exceeded`. The old contrast pair was (no_prior_research, budget_exceeded); reusing budget_exceeded on both sides would have made the discrimination vacuous."
  - "`hand_computed` in the preview tests now picks its turn class by `fu.expect_research` too. It is still written independently of `_assumed_pipeline_cost`'s expression — it restates the RULE, not the code — and this keeps wave 2's dataset flip from reddening preview arithmetic that is already correct."
  - "Ten mutation probes were run against the plan's three. The plan named one probe per task; the bounded grader has four discriminating branches and reach_traced three, and a branch whose mutation is never observed is exactly the vacuous-gate failure this milestone has hit sixteen times."
  - "README's test count (690, at lines 15 and 180) was corrected to 705 from a measured run. It was already two behind before this wave and thirteen behind after — the only README fact wave 1 falsifies. The 'no new search' promise at line 99 and the limitation at line 254 are NOT touched: they are still true of the shipped graph today, and waves 2/4 own them."

# Metrics
duration: 30min
completed: 2026-08-10
---

# Phase 17 Plan 01: The eval mechanics the flip will land on Summary

**One-liner:** The offline evals gained everything Phase 17's behaviour flips need — per-call scripted researcher outputs, an interleaved insufficiency sentinel, an expectation-keyed research-bounds grader, a trace-event grader for the redefined `no_prior_research`, and a cost preview that prices a reaching follow-up as the research turn it is — with every default preserving today's grading, proven by 41/41 keyless evals before and after and by ten mutation probes each observed red on the assertion that owns it.

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| `.venv/bin/pytest` (plain) | 692 passed / 65 skipped | **705 passed / 65 skipped** | +13 passed, **zero new skips** |
| `DATABASE_URL=…:54329 LC_ALL=C .venv/bin/pytest` (armed) | 756 passed / 1 skipped | **769 passed / 1 skipped** | +13 passed, zero new skips |
| `env -u CRITIC_MODEL ANTHROPIC_API_KEY="" python -m evals` | 41/41 (100%) | **41/41 (100%)** | **zero** — the plan's whole point |
| `tests/test_supervisor_routing.py` | 38 passed | **38 passed** | 0 (untouched this wave) |
| `.venv/bin/ruff check .` | clean | clean | — |

+13 is exactly the thirteen tests added (4 + 8 + 1) and nothing else. No skip was
introduced, so there is no new skip to justify.

Every eval gate ran under `env -u CRITIC_MODEL ANTHROPIC_API_KEY=""`. Phase 16's fixture
gate compares `models.critic` against `graph.critic_model()`, so a CRITIC_MODEL-exporting
shell grades the one committed recording stale BY DESIGN and would have printed a
spurious 40/41 that looks exactly like a real regression.

## `--collect-only` on every selector shipped

| Selector | Collected | Required |
|----------|-----------|----------|
| `tests/test_evals.py -k scripted_client` | **5** | ≥ 3 |
| `tests/test_evals.py -k "followup_research_bounded or followup_reach_traced"` | **8** | ≥ 6 |
| `tests/test_evals.py -k record_preview` | **7** | ≥ 1 |

Each was collected against the whole `tests/` tree before its result was believed.

## What shipped

| Task | What | Commit |
|------|------|--------|
| 1 | `Followup` script/expectation fields + `ScriptedClient` pop-lists + 4 tests | `48b2739` |
| 2 | Grader redesign (1 retired, 2 added), stop-vocabulary sweep, 8 tests | `cf5f814` |
| 3 | Cost preview prices reaching follow-ups as research turns, 1 test | `ba3ac46` |
| — | README test count (the one fact this wave falsifies) | `371f086` |

### Task 1 — the script can tell the two researcher calls apart (`48b2739`)

`ScriptedClient` returned `case.notes` for **every** `"Search the web"` prompt
(Pitfall 5). A follow-up that reaches would therefore "find" the notes it already had,
and wave 2's grounded-answer case would ground on nothing new — green for the wrong
reason. Now:

```python
self.researcher_notes = [case.notes] + [
    fu.research_notes for fu in case.followups if fu.research_notes
]
```

popped per call, falling back to `case.notes` on exhaustion (the `verdicts` idiom — an
unscripted extra pass is something the graders should describe, not an `IndexError`).
`self.answers` interleaves `fu.insufficiency` ahead of `fu.answer` when authored, so one
follow-up turn can speak twice.

`Followup` gained `expect_research: bool = False`, `insufficiency: str = ""`,
`research_notes: str = ""` — all no-change defaults, so no existing case's script moved.
The `expect_forced_stop` docstring stopped claiming *"today only `no_prior_research`"*;
this phase falsifies that, and the field is now described generically.

**Backward compatibility as a property, not a diff:**
`test_scripted_client_scripts_a_case_without_the_new_fields_as_before` asserts a
pre-17 case gets `researcher_notes == [case.notes]` and one answer per follow-up.

### Task 2 — what a follow-up may reach for, keyed to what its case says (`cf5f814`)

`grade_followup_did_not_research` (`followup_reuses_notes`) is **retired BY DESIGN**.
Replaced by `grade_followup_research_bounded` (`followup_research_bounded`):

- `expect_research=False` → **the old body verbatim**. A follow-up whose notes cover its
  question must still never search. Scoping a property to the cases it is true of is not
  softening it; deleting it would have been.
- `expect_research=True` → exactly one `researcher` trace entry (zero means the reach
  never happened and the answer came from somewhere nobody authorised; two means the
  one-pass bound broke) and zero `classifier` entries.

New `grade_followup_reach_traced` (`followup_reach_traced`) reads the reason off a
supervisor trace entry and checks it against the named `FOLLOWUP_RESEARCH_REASONS`
(`no_prior_research`, `notes_insufficient`). SC-4 redefines `no_prior_research` from stop
reason to trace event, and a redefinition nobody grades is a rename.

Registry is now five, exact-membership pin updated in the same commit. The retired grade
name string `followup_reuses_notes` has **zero** occurrences tree-wide; the only surviving
mention of the old function name is a comment stating the history.

Untouched, as RESEARCH Q5 requires: `grade_recorded_refusal`, `REFUSAL_PATTERNS`,
`grade_followup_was_checked`, `grade_followup_approval`, `grade_followup_forced_stop`
(docstring sweep only).

### Task 3 — a reaching follow-up is priced like the research turn it is (`ba3ac46`)

`_assumed_pipeline_cost` quoted every follow-up at 6K-in / 2K-out with **zero web
searches**. Since this phase a reaching follow-up runs a research pass, so it is now
priced at `ASSUMED_RESEARCH_*` with `WEB_SEARCHES_PER_RESEARCH_TURN`. Phase 15 paid
$0.24 to learn its quote read 35% low; the identical failure was structurally available
here and cost nothing to close before a record run rather than after one. The calibration
comment now states which class each constant covers and that **both remain unmeasured** —
and that a reaching follow-up carries the session transcript on top of what it finds, so
if the research constants are wrong for it, they are wrong low.

**`grep -rn "16.51" . --exclude-dir=.planning --exclude-dir=.git` → 0 hits.** No shipped
prose quotes the old total, so nothing needed re-quoting (the plan's verification agreed
with the tree).

## Mutation probes — ten, each observed red on the assertion that owns it

Every probe was applied to a file copy in the scratchpad and restored from that copy, not
from git, while work was uncommitted (the 12-06 lesson).

| # | Mutation | Observed red |
|---|----------|--------------|
| P1 | `"Search the web"` branch reverted to always return `case.notes` | `test_scripted_client_gives_each_researcher_call_its_own_notes` — *assert "FACTS: the session's own notes." == "FACTS: the 2027 figure is $4.2bn."* |
| P2 | `self.answers` reverted to one entry per follow-up | `test_scripted_client_interleaves_the_insufficiency_signal_before_the_answer` — the sentinel never arrives |
| P3 | pop-list exhaustion guard removed | `test_scripted_client_falls_back_when_the_researcher_script_runs_out` — `IndexError: pop from empty list` |
| P4 | bounded/False branch returns `_ok` unconditionally | `test_a_followup_that_researched_again_is_caught` — **T-17-01 mitigation: the surviving no-research property cannot be silently weakened** |
| P5 | `researched != 1` → `researched > 2` | **two** tests: `…catches_a_reach_that_never_happened` AND `…catches_a_second_research_pass` — the bound is proven on both sides |
| P6 | classifier ban disabled in the reaching branch | `test_followup_research_bounded_still_forbids_classifying_when_reaching` |
| P7 | reach_traced returns ok whatever the trace holds | **two** tests: `…catches_a_reach_the_trace_never_explains` AND `…rejects_a_reason_the_design_does_not_know` — **T-17-03 mitigation** |
| P8 | reach_traced's `expect_research=False` early return disabled | `test_followup_reach_traced_is_silent_on_a_case_that_does_not_reach`, `test_a_clean_followup_passes_every_grader`, `test_a_followup_with_no_prior_notes_stops_honestly` — **and the offline evals drop to 33/41**, which is the proof the new grader is actually reached by the 41-case suite rather than being dead registry weight |
| P9 | bounded/False `_ok` → `_fail` | **offline evals 33/41** — same proof for the bounded grader; both new graders are live on all eight follow-up cases |
| P10 | `if followup.expect_research:` → `if False:` in `_assumed_pipeline_cost` | `test_record_preview_prices_research_triggering_followups` — *assert 0.228 > 0.228* — **T-17-02 mitigation** |

`git status --short` was empty of unintended modifications after every restore; the three
suites were re-run green after the last one.

## The scoped `no_prior_research` grep — before-pins intact

The plan's acceptance grep excludes six line numbers owned by wave 2 (17-02-T3). Adding
Task 2's grader tests above them drifted the three end-to-end lines by +173
(`626/649/664` → `799/822/837`); the strata and flip-tag lines at `173/175/222` did not
move. Re-located by content, which is what the plan instructs when line numbers drift:

| Line | Owning test | Status |
|------|-------------|--------|
| 173, 175 | `test_dataset_taxonomy_followup_strata` | **before-pin, untouched** (wave 2 rewrites it) |
| 222 | `test_dataset_taxonomy_phase17_flip_cases_are_tagged` | **before-pin, untouched** |
| 799, 822, 837 | `test_a_followup_with_no_prior_notes_stops_honestly` | **before-pin, untouched** |
| 404 | `grade_followup_reach_traced` unit-test docstring | history-stating prose ("became a trace event in Phase 17") |
| 450 | comment above `STOPPED` | history-stating prose ("left the vocabulary in Phase 17") |

**Zero** hits remain as a stop-name literal in a synthetic state. Weakening the three
before-pins a wave early is Pitfall 4 — it would make the dataset flip ungated — and they
survive this wave intact.

## Acceptance criteria, measured

| Criterion | Measured |
|-----------|----------|
| `grep -c "expect_research" evals/dataset.py` ≥ 2 | **2** |
| `grep -c "today only" evals/dataset.py` == 0 | **0** |
| `grep -c "def grade_followup_did_not_research" evals/graders.py` == 0 | **0** |
| `grep -c "def grade_followup_research_bounded" evals/graders.py` == 1 | **1** |
| `grep -c "def grade_followup_reach_traced" evals/graders.py` == 1 | **1** |
| `grep -c "expect_research" evals/__main__.py` ≥ 1 | **2** |
| `grep -rn "16.51"` outside `.planning`/`.git` | **0 hits** |
| `git diff main -- .github/workflows/ci.yml` | **empty (0 lines)** |
| Full suite plain ≥ 692 | **705** |
| Evals exactly 41/41 keyless | **41/41** |

## Deviations from plan

### [Rule 2 — forward-correctness] `hand_computed` branches on `expect_research`

**Found during:** Task 3. The preview's independently-written arithmetic helper priced
every follow-up at the follow-up constants. Left alone it stays green this wave (no case
sets the field) and reds in wave 2 for a reason that is not wave 2's bug. Refactored into
`research_turn()` / `followup_turn()` helpers and made to pick the class by the same rule
the preview does — restating the RULE, not the code, so it remains an independent check.
**Files:** `tests/test_evals.py`. **Commit:** `ba3ac46`.

### [Rule 2 — non-vacuity] Ten probes against the plan's three

**Found during:** Tasks 1–3. The plan named one probe per task. The bounded grader has
four discriminating branches and reach_traced three; a branch whose mutation is never
observed is the vacuous-gate failure this milestone has hit sixteen times, and three
consecutive Phase 16 waves shipped gates with no probe at all. P8 and P9 also answer a
question no unit test can: *is the new grader reached by the real suite?* — both drop the
run to 33/41, so yes, on all eight follow-up cases.

### [standing instruction] README test count

`690` at lines 15 and 180 was already two behind before this wave. Corrected to `705`
from a measured plain run, not by arithmetic on the old number (`371f086`). Deliberately
**not** touched: line 99's "no new search", line 155's routing row and line 254's
limitation — all still true of the shipped graph, all owned by waves 2 and 4.

## Threat register — dispositions discharged

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-17-01 | mitigate | False branch is the old body verbatim; P4 reds it against a researcher visit |
| T-17-02 | mitigate | Research constants applied to `expect_research` turns; P10 reds the discriminating test |
| T-17-03 | mitigate | P7 reds a trace with no `followup_research` key AND one with an unrecognised reason |
| T-17-SC | accept | Zero packages installed |

No new security-relevant surface: this wave touches only `evals/` and its tests. No
network endpoint, auth path, file access pattern or schema changed.

## What wave 2 inherits

- `Followup.expect_research` / `.insufficiency` / `.research_notes` exist and are scripted
  end to end — the four flipping cases can be authored without touching the harness.
- `FOLLOWUP_GRADERS` already grades the after-behaviour, so the graph flip can land with
  case + graph + pins in one green commit.
- The three before-pins (`test_dataset_taxonomy_followup_strata`,
  `test_dataset_taxonomy_phase17_flip_cases_are_tagged`,
  `test_a_followup_with_no_prior_notes_stops_honestly`) are intact and are wave 2's to
  rewrite, same-commit with the dataset.
- The supervisor must emit `followup_research` on a supervisor trace entry with a value in
  `FOLLOWUP_RESEARCH_REASONS`, or `grade_followup_reach_traced` reds every flipped case.
- Preview arithmetic is already correct for reaching cases; wave 2 should not need to
  touch `evals/__main__.py`.

## Self-Check: PASSED

- `.planning/phases/17-followups-that-can-reach-for-new-information/17-01-SUMMARY.md` — FOUND
- `48b2739` FOUND · `cf5f814` FOUND · `ba3ac46` FOUND · `371f086` FOUND
- All five modified source files present and green under `ruff` and the full suite.
