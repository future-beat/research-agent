---
phase: 17-followups-that-can-reach-for-new-information
plan: 02
subsystem: graph
tags: [routing-reversal, side-effect-pinning, mutation-testing, append-not-replace, red-first]

# Dependency graph
requires:
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "01"
    provides: "grade_followup_research_bounded / grade_followup_reach_traced + FOLLOWUP_RESEARCH_REASONS, Followup.expect_research, the ScriptedClient pop-lists"
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "research"
    provides: "Q1's AFTER table and the eight precedence pairs; Q3's append fix; Q5's case-by-case flip table"
provides:
  - "AgentState.notes_insufficient / .followup_research_done — both False per run, so per follow-up TURN"
  - "Routing row 4 flipped in place: a no-notes follow-up routes to the researcher, spends the turn's pass, and records `followup_research: no_prior_research` on the supervisor's own trace entry"
  - "Routing row 5 (supervisor half): notes_insufficient and no pass spent -> researcher; consumes the flag; trace reason `notes_insufficient`. Nothing sets the flag until 17-03"
  - "researcher_node APPENDS to research_notes instead of replacing them"
  - "Twelve precedence tests pinned by side effect, five row mutations observed red"
  - "`followup-with-no-prior-research` flipped to the route-then-guardrail end-to-end pin"
affects: [17-03, 17-04]

# Tech tracking
tech-stack:
  added: []  # zero packages installed this phase
  patterns:
    - "When a flip is destination-invisible, the destination is not the pin. Row 4 and the generic no-notes row route to the same node; every test here asserts the trace reason, the spent pass, the empty forced stop, or the classifier the row's position skips — and each was observed red under the row move it exists to catch."
    - "A green-from-the-start pin proves nothing about a silent bug. The append pin was written and run against the REPLACE first, and its red is quoted in this summary; a suite that was green before and after would have said the same thing about a note set that was being swapped."
    - "Probe the prose gate too. The `why` after-pin looked green under its first probe because the word it asserts appeared elsewhere in the same sentence — the probe was wrong, not the gate, and only re-running it against a why with no form of the word proved the gate discriminates."
    - "One golden case can pin a route and the guardrail that outranks it, because the guardrail fires on real accumulated cost that no routing-table test can produce."

key-files:
  created: []
  modified:
    - src/research_agent/graph.py
    - tests/test_supervisor_routing.py
    - tests/test_graph_smoke.py
    - evals/dataset.py
    - tests/test_evals.py
    - README.md

key-decisions:
  - "The flip-tag test was NOT replaced wholesale. The plan said its purpose expires with the flip; it expires only for the case that flipped. The three refusal cases flip in 17-03, so the test now carries both halves — a case that reaches must say so, and a case still awaiting its flip must still say `Phase 17`. Replacing it outright would have left wave 3's before-measures untagged for a wave, which is Pitfall 4 with the sign reversed."
  - "`expect_notes_stored` stays False on the flipped case, against the plan's 'likely True'. Measured: `grade_notes_stored` is a DETERMINISTIC grader, so it runs on the RESEARCH turn only — and that turn is budget-stopped before the researcher. The follow-up's pass does store a 40-char note (probe P11 shows both facts), which is the ADR-0011 consequence: notes gathered by a turn the budget then stops outlive the stop."
  - "The follow-up's researcher output is deliberately unscripted. `ScriptedClient.researcher_notes` is `[case.notes] + [fu.research_notes …]`, which assumes the session's own pass ran; on this case it did not, so a `research_notes` script would be popped second and never used. Nothing grades the text (the turn stops before the responder), and authoring a transcript the run does not produce would be worse than leaving it."
  - "README's routing-table row was rewritten this wave, not deferred. The user's split puts the 'no new search' promise and the follow-up limitation in wave 4 — both are still true of the responder as shipped. The routing table is a different claim: the README says it IS `supervisor_node`, in order, and this wave changed the order's meaning."

# Metrics
duration: 35min
completed: 2026-08-10
---

# Phase 17 Plan 02: The routing reversal, path 1 Summary

**One-liner:** A follow-up with no notes behind it now routes to the researcher instead of
ending with `no_prior_research`, the researcher enlarges the session's note set instead of
swapping it, and both changes are pinned by side effects rather than destinations — the two
behaviour pins were observed RED against today's code before the fix, and all five row
mutations plus five extra probes were observed red on the assertion that owns them.

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| `.venv/bin/pytest` (plain) | 705 passed / 65 skipped | **721 passed / 65 skipped** | +16 passed, **zero new skips** |
| `DATABASE_URL=…:54329 LC_ALL=C .venv/bin/pytest` (armed) | 769 passed / 1 skipped | **785 passed / 1 skipped** | +16 passed, zero new skips |
| `env -u CRITIC_MODEL ANTHROPIC_API_KEY="" python -m evals` | 41/41 (100%) | **41/41 (100%)** | 0 — the case flipped, the count did not |
| `tests/test_supervisor_routing.py` | 38 passed | **52 passed** | **+14** |
| `.venv/bin/ruff check .` | clean | clean | — |

**+16 accounted for exactly, and no skip was introduced, so there is no new skip to justify:**

| Where | Net | Why |
|-------|-----|-----|
| `test_supervisor_routing.py` | +14 | 1 flipped in place (net 0), 2 per-turn default pins, 6 guardrail pairs, 6 precedence pairs |
| `test_graph_smoke.py` | +2 | 1 flipped in place (net 0), the append pin, the store-attribution pin |
| `test_evals.py` | 0 | three tests rewritten in place, none added or dropped |

Routing suite 38 → 52 is `+2 per-turn defaults +12 precedence`; the row-4 test was renamed
and rewritten, not added.

Every eval gate ran under `env -u CRITIC_MODEL ANTHROPIC_API_KEY=""` — Phase 16's fixture
gate compares `models.critic` against `graph.critic_model()`, so a CRITIC_MODEL-exporting
shell grades the one committed recording stale BY DESIGN.

## RED first, quoted — the point of the exercise

Both behaviour pins were written and run **before** any implementation. Commit `1b06bc6`
contains them red; `826049a` is the fix.

```
$ .venv/bin/pytest tests/test_supervisor_routing.py tests/test_graph_smoke.py \
    -k "notes_append_not_replace or followup_no_notes_routes_to_researcher or researches_instead_of_refusing"

_________________ test_followup_no_notes_routes_to_researcher __________________
tests/test_supervisor_routing.py:135: in test_followup_no_notes_routes_to_researcher
    assert result["next_step"] == "researcher"
E   AssertionError: assert 'done' == 'researcher'

______ test_a_followup_with_no_prior_notes_researches_instead_of_refusing ______
tests/test_graph_smoke.py:217: in ...
    assert client.nodes_called() == ["researcher", "responder", "critic"]
E   AssertionError: assert [] == ['researcher'...er', 'critic']

_______________ test_notes_append_not_replace_on_a_followup_pass _______________
tests/test_graph_smoke.py:247: in test_notes_append_not_replace_on_a_followup_pass
    assert result["research_notes"].startswith(SENTINEL_NOTES)
E   AssertionError: assert False
E    +  where False = <built-in method startswith of str object at 0x10d876830>('PRIOR NOTES MUST SURVIVE')
E    +    where <...> = 'FACTS: the sky scatters blue light.'.startswith

3 failed, 1 passed in 0.52s
```

The third is the one this discipline exists for. `state["research_notes"] = notes` had been
green through fifteen phases because the critic grades the draft against whatever
`research_notes` holds — a swapped note set and an enlarged one produce identical, equally
green runs, and the only turn that could tell is a later one nobody had written yet.

The 1 passed is `test_a_followup_pass_files_its_notes_under_the_followup_question` — the
SC-2 attribution pin, green from the start because `store.add`'s task prefix was already
correct. Green-from-the-start is not evidence, so it was probed separately (P6).

## What shipped

| Task | What | Commit |
|------|------|--------|
| 1 (red) | the three pins, against code that fails them | `1b06bc6` |
| 1 (green) | state keys, row 4 flipped in place, row 5, append-not-replace, per-turn pins | `826049a` |
| 2 | twelve precedence pairs, five mutations observed red | `5e19175` |
| 3 | golden case + its three dependent pins, one commit | `d436984` |
| — | README's routing table and test count | `c938453` |

### The table, after

Rows 1–3 (caps, budget) are byte-identical and still on top. Row 4 keeps its POSITION and
changes its destination — position is the load-bearing half, because above the classifier
row is what keeps "a follow-up never classifies" a property of the table rather than of how
`followup_state` happens to be built. Row 5 is new, flag-gated, and unreachable until the
responder learns to set the flag in 17-03.

`grep -c "no_prior_research" src/research_agent/graph.py` → **2**, and neither is a stop:

| Line | Role |
|------|------|
| 547 | `followup_research = "no_prior_research"` — the trace event, row 4's branch |
| 576 | comment stating the redefinition (was a stop reason, is now a reach reason) |

**Zero** `forced_stop_reason` assignments of it anywhere in `src/`.

### The append

```python
existing = state["research_notes"]
state["research_notes"] = f"{existing}\n\n{notes}" if existing else notes
```

Unconditional, no mode check: in research mode `existing` is always empty at researcher
time, because the only row that routes there requires it. `store.add` is unchanged, so SC-2
attribution is task-prefix + owner + turn trace exactly as RESEARCH Q3.3 defined it — no
schema change, and the store pin proves the prefix is the follow-up question.

## Mutation log — ten probes, each red on the assertion that owns it

Applied to `src/research_agent/graph.py` from a pristine scratchpad copy and restored from
that copy (not from git, since work was uncommitted — the 12-06 lesson). `git status
--short` was checked clean of `src/` after every restore.

| # | Mutation | Discriminating test observed red |
|---|----------|----------------------------------|
| M1 | row 4 deleted | `test_precedence_the_no_notes_followup_never_classifies` — *assert 'classifier' == 'researcher'* (the row-delete discriminator; +3 others) |
| M2 | row 4 moved below the generic `not research_notes` row | `test_precedence_the_no_notes_row_decides_before_the_generic_researcher_row` — *assert False is True* on `followup_research_done`. **`next_step` stayed "researcher" throughout** — this is the mutation a destination assertion cannot see |
| M3 | row 4 keeps its destination, loses `followup_research_done = True` | same test, same flag assertion — routing identical, one-pass bound gone |
| M4 | row 5 moved below the author row | `test_precedence_insufficient_notes_outranks_the_author` — *assert 'responder' == 'researcher'* |
| M5 | row 5 moved above the cap rows | all three `…_on_thin_notes_…` guardrail tests — *assert 'researcher' == 'done'* |
| P6 | `store.add(f"[{task}] {notes}")` → `store.add(notes)` | `test_a_followup_pass_files_its_notes_under_the_followup_question` — the green-from-the-start pin, shown to discriminate |
| P7 | row 5's `mode == "followup"` guard removed | `test_precedence_the_insufficiency_row_is_followup_only` — *assert 'researcher' == 'writer'* |
| P8 | row 5's `not followup_research_done` gate removed | `test_precedence_one_pass_bound_sends_a_second_signal_to_the_author` — *assert 'researcher' == 'responder'* |
| P9 | row 5 stops clearing `notes_insufficient` | `test_precedence_insufficient_notes_outranks_the_author` — *assert True is False* |
| P10 | the append reverted to the REPLACE | `test_notes_append_not_replace_on_a_followup_pass` |

M1–M5 are the plan's five. P6–P10 close the branches no row move can reach: the mode guard,
the flag gate, the flag clear, the store prefix and the append itself each own a line that
M1–M5 leave untouched, and a line whose mutation is never observed is the vacuous gate this
milestone has hit sixteen times.

### Eval-side probes — including the one that proves the graders are reached

| # | Mutation | Observed red |
|---|----------|--------------|
| P11 | flipped case's `expect_notes_stored` → True | `notes_stored`: *"the researcher stored no notes"* — proof the grader runs on the RESEARCH turn, which decided the field's value |
| P12 | flipped case's `expect_research` → False | `test_dataset_taxonomy_followup_strata` (*"no case reaches and is then stopped"*), `followup_research_bounded` on the real case, **and the offline run drops to 40/40 cases** |
| P13 | the flipped case's `why` never mentions reaching | `test_dataset_taxonomy_phase17_cases_say_which_side_of_the_flip_they_are_on` — *"reaches for new information but its why never says so"* |
| P14 | a refusal case's `why` drops `Phase 17` | same test, before-half — *"followup-refuses-a-forecast flips in Phase 17 but does not say so"* |
| P15 | the supervisor stops writing `followup_research` onto its trace entry | `test_a_followup_with_no_prior_notes_reaches_then_hits_the_guardrail`, 4 routing pins, **and the real 41-case run drops to 40/41** with `followup_reach_traced`: *"the turn reached for new information and the trace never says why"* |

**P13's first attempt did not red, and the probe was the thing at fault**, not the gate: the
replacement prose still contained "reaches" later in the same `why`. Re-run against a `why`
with no form of the word at all, the gate fires. A probe that passes is a result to
investigate before it is a gate to trust.

**P15 is the wave-1 inheritance discharged.** 17-01 warned that the supervisor owes
`{"node": "supervisor", "followup_research": …}` or every flipped case reds. P15 removes
exactly that and the shipped 41-case suite drops to 40/41 — so the trace event is not
decoration, it is graded by the run that gates this phase.

## `--collect-only` on every selector shipped

Each run against the whole `tests/` tree (786 collected), not against the file under edit.

| Selector | Collected | Required |
|----------|-----------|----------|
| `tests/ -k notes_append_not_replace` | **1** | ≥ 1 (VALIDATION 17-02-T1a) |
| `tests/ -k followup_no_notes_routes_to_researcher` | **1** | ≥ 1 (VALIDATION 17-02-T1b) |
| `tests/test_supervisor_routing.py -k precedence` | **6** | ≥ 5 |
| `tests/ -k guardrails_outrank_followup_research` | **6** | ≥ 6 (3 caps × 2 reach rows) |
| `tests/ -k one_pass_bound` | **1** | ≥ 1 (routing half; 17-03 adds the responder half) |
| `-k "precedence or guardrails_outrank_followup_research or one_pass_bound"` | **12** | ≥ 10 |

## The path-1 golden case, measured before it was believed

RESEARCH A2 called the exact stop LOW-risk but unverified end to end. Run alone before the
test was written, the tree agreed with it:

```
--- research
  stop: budget_exceeded | draft: '' | approved: False
  trace: [supervisor->classifier, classifier, supervisor->done]
--- Which of those is the most widely deployed?
  stop: budget_exceeded | draft: '' | approved: False
  trace: [supervisor->researcher (no_prior_research), researcher, supervisor->done]
    PASS followup_research_bounded  reached for new information exactly once
    PASS followup_reach_traced      no_prior_research
    PASS followup_fact_checked      stopped before the critic, as expected: budget_exceeded
    PASS followup_approval
    PASS followup_forced_stop       budget_exceeded
```

Turn 1 has fresh usage (a follow-up is its own run), so the budget row does not fire and row
4 sends it to the researcher; the researcher's folded usage then blows the case's 1e-7
budget and turn 2 ENDs honestly. One case, both halves: the route, and the guardrail that
outranks it — through the compiled graph, where "the caps win" is a claim about accumulated
cost that no routing-table test can make.

**Same-commit contract (`d436984`):** `evals/dataset.py` **and** `tests/test_evals.py`,
29 + 89 lines. `grep -c "no_prior_research" evals/dataset.py` → **0**, including prose.

## Deviations from plan

### [Rule 2 — the before-pin that had not expired] The flip-tag test kept its old half

**Found during:** Task 3. The plan says `test_dataset_taxonomy_phase17_flip_cases_are_tagged`
"expires with the flip; replace with the after-pin". It expires for the case that flipped.
The three refusal cases (`followup-admits-a-gap`, `followup-refuses-an-uncovered-figure`,
`followup-refuses-a-forecast`) do not flip until 17-03, and replacing the test outright
would have left them untagged for a wave — the same failure as flipping a dataset without
its pins, with the sign reversed. The test now carries both halves and is renamed
`test_dataset_taxonomy_phase17_cases_say_which_side_of_the_flip_they_are_on`; P13 and P14
show each half reds independently. **Files:** `tests/test_evals.py`. **Commit:** `d436984`.

### [measured, against the plan's guess] `expect_notes_stored` stays False

**Found during:** Task 3. The plan expected "likely True now". `grade_notes_stored` is in
`DETERMINISTIC_GRADERS`, which `run_case` applies to the research turn only — and this
case's research turn is budget-stopped before the researcher. P11 confirms both directions:
set True it reds with *"the researcher stored no notes"*, and the follow-up turn's trace
shows `notes_length: 40`, so the note IS written, by the pass the budget then stops. That
asymmetry is ADR-0011 consequence material and is now stated in the case's own comment.

### [Rule 1 — a docstring falsified by the edit under it] The supervisor's own docstring

**Found during:** Task 1. `supervisor_node`'s docstring claimed the substitution of author
node was "the *only* thing `mode` changes" — false the moment two mode-gated rows exist,
and it sits inside the function this plan rewrites. Corrected in place, with the caps
precedence stated. The `mode`-related prose OUTSIDE the supervisor (the module docstring's
"Follow-ups skip classification and search entirely", `responder_node`'s "it never
searches") was deliberately left: those are 17-03/17-04 surfaces by the plan's
file-ownership rule and by the standing instruction. **Commit:** `826049a`.

### [standing instruction] README routing table + test count

**Found during:** wave close. Line 155 stated `follow-up with no prior notes → END
(no_prior_research)` under a sentence promising "The routing table *is* `supervisor_node`,
in order" — falsified by this wave's own commit, and neither the limitation (line 254) nor
the "no new search" promise (line 99) that the user assigned to wave 4. Rewritten with both
reach rows and a paragraph on what the ORDER buys. Count 705 → **721**, measured.
**Commit:** `c938453`.

**One thing for 17-03/17-04 to confirm:** the README now lists row 5, which exists in the
shipped table but cannot fire until the responder sets `notes_insufficient` in 17-03. The
phase ships as one PR, so the merged state is accurate — but if 17-03 slips, that row
describes a path no input can take.

## Known stubs

Row 5 is deliberately half-built and is the plan's design: the supervisor consumes
`notes_insufficient`, and nothing sets it until 17-03 wires the responder's `INSUFFICIENT:`
sentinel. It is fully unit-tested from hand-built state (four tests), which is how this
suite works, and `test_precedence_one_pass_bound_sends_a_second_signal_to_the_author` is the
routing half of VALIDATION's one-pass row. No stub reaches a user-visible surface.

## Threat register — dispositions discharged

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-17-04 | mitigate | Append pin observed RED against the REPLACE and quoted above; P10 reds it again on demand |
| T-17-05 | mitigate | M1–M5 each red on a side-effect assertion; M2 leaves `next_step` unchanged, which is the whole argument |
| T-17-06 | mitigate | Six caps-vs-reach tests; M5 reds three of them |
| T-17-07 | mitigate | Golden case + its three pins flipped in one commit; wave gate is the full suite and 41/41 |
| T-17-SC | accept | Zero packages installed |

No new security-relevant surface. The reach rows sit below the budget and cap rows, so the
new spend path is bounded by the guardrails that already existed — and that is the property
six of these tests exist to assert.

## What 17-03 inherits

- `notes_insufficient` and `followup_research_done` exist, default False per turn, and are
  never read off `previous` — 17-03 sets the first from the responder's sentinel and reads
  neither anywhere else.
- Row 5 is live and pinned; 17-03 owns only the flag's PRODUCER, plus the post-research
  prompt branch and the responder-side one-pass test.
- The three refusal golden cases are still before-measures and still tagged `Phase 17` by a
  test that will red if 17-03 flips one without saying so in its `why`.
- `ScriptedClient.researcher_notes` is `[case.notes] + [fu.research_notes …]`: correct for
  path-2 cases, whose research turn DOES run the researcher. Any future case whose research
  turn is stopped before the researcher pops the head of that list on its follow-up pass.
- README lines 99 and 254 ("no new search", the follow-up limitation) are untouched and are
  wave 4's, as is the module docstring at `graph.py:15` and `responder_node`'s at `:423`.

## Self-Check: PASSED

- `.planning/phases/17-followups-that-can-reach-for-new-information/17-02-SUMMARY.md` — FOUND
- `1b06bc6` FOUND · `826049a` FOUND · `5e19175` FOUND · `d436984` FOUND · `c938453` FOUND
- All six modified files present; `ruff check .` clean; plain 721/65, armed 785/1, evals
  41/41 keyless, routing 52 — all measured after the last restore, with `git status --short`
  clean.
