---
phase: 17-followups-that-can-reach-for-new-information
plan: 03
subsystem: graph
tags: [sentinel-idiom, one-pass-bound, red-first, mutation-testing, vocabulary-sweep, leak-gate]

# Dependency graph
requires:
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "01"
    provides: "Followup.expect_research/.insufficiency/.research_notes, the ScriptedClient pop-lists, grade_followup_research_bounded + grade_followup_reach_traced"
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "02"
    provides: "notes_insufficient / followup_research_done state keys, supervisor row 5 (the consumer), append-not-replace, the trace event"
provides:
  - "responder_node's INSUFFICIENT: sentinel — one boolean gates the prompt branch AND the parse, the flag is set and the draft is left untouched, so the insufficiency window ships no answer"
  - "The one-pass bound proven in smoke: the honest refusal ships critic-reviewed WITH the attempt, and a post-research sentinel is an ordinary draft that cannot re-route"
  - "Row 5 is now reachable end to end — the README row wave 2 shipped describes a path an input can take"
  - "The three path-2 golden cases flipped per the settled directions (A1 honoured), with the final taxonomy shape in the same commit"
  - "no_prior_research is gone from every shipped code surface's stop vocabulary, with a source-reading gate that keeps it gone"
affects: [17-04]

# Tech tracking
tech-stack:
  added: []  # zero packages installed this phase
  patterns:
    - "Gate a parse and the prompt that invites it on the SAME boolean. Two conditions that agree today are a bug waiting for the day they don't: a parse that outlives its prompt reads routing input out of a response nobody asked for, and the probe shows it silently corrupting the shipped draft rather than erroring."
    - "A signal must be able to produce nothing. The sentinel path returns before `draft`, `reviewed`, `revision_count` and the usual trace entry are touched — so 'the window ships no answer' is a consequence of the control flow, not a promise the node makes and then keeps by convention."
    - "When a before-pin's condition can no longer be false, delete it and say why. The flip-tag test's before-half required a case awaiting its flip; there is none left, so a loop over zero cases would have gone on reporting green forever."
    - "Re-point a fixture when the case under it changes meaning. Three refusal-grader tests kept passing by returning 'not a refusal case' the moment their case became answerable — green, and grading nothing."

key-files:
  created: []
  modified:
    - src/research_agent/graph.py
    - src/research_agent/chat.py
    - src/research_agent/limits.py
    - docs/OPERATIONS.md
    - tests/test_graph_smoke.py
    - tests/test_supervisor_routing.py
    - evals/dataset.py
    - tests/test_evals.py
    - README.md

key-decisions:
  - "The mode-free gate was VERIFIED before it was used, not assumed. `pre_research = not state['followup_research_done']` has no `mode` check, which is safe only because `\"responder\"` is produced by exactly one expression in the table (`author`), and `author` is the responder only when mode is followup. That premise now has its own eight-case parametrized test — if a future row ever names the responder directly, a research run starts being prompted for a signal nothing in that mode consumes."
  - "A prompt-content pin was added beyond the plan's four. The parse's gating is observable from behaviour; the PROMPT branch is not — the fakes dispatch on 'follow-up question', so flipping the branch changes no test outcome. Probe P2 (the prompt never asks for the sentinel) reds only that pin, which means without it half of 'identical gating' shipped ungated."
  - "The flip-tag test's before-half was RETIRED, one wave after wave 2 deliberately kept it. It expired for real here: with all three refusal cases flipped, no case satisfies `not answerable and not expect_research`, so the half would loop over zero cases and assert nothing. Replaced by a counted after-pin (`len(reaching) == 4`) plus a `stranded` clause that reds if a case ever goes back to refusing without looking."
  - "`grep -c \"INSUFFICIENT:\" evals/dataset.py` is 4, not the plan's 3. The fourth is wave 1's field comment naming the sentinel. The three AUTHORED lines are `grep -c 'insufficiency=\"INSUFFICIENT:'` == 3; the tree wins and the criterion is met on the scoped grep."
  - "The plan's Task 3 item 2 (rewrite the supervisor docstring's 'the only thing mode changes') was already done in 17-02 as a Rule-1 deviation — the sentence sat inside the function that wave rewrote. Verified in the tree rather than re-edited."
  - "Three refusal-grader unit tests were re-pointed from `followup-admits-a-gap` to `followup-refuses-a-forecast` in the flip commit. Left alone they stayed GREEN and graded nothing: every assertion would have been answered by `not a refusal case`."

# Metrics
duration: 45min
completed: 2026-08-10
---

# Phase 17 Plan 03: The routing reversal, path 2 Summary

**One-liner:** A follow-up whose notes cannot answer the question now says so in the critic's own sentinel idiom, and that signal routes instead of shipping — the draft is left untouched so the insufficiency window produces no answer at all, one research pass is all it buys, and a post-research sentinel is an ordinary draft the critic judges; the three path-2 golden cases flipped with their taxonomy pins in one commit, and `no_prior_research` left the stop vocabulary of every shipped code surface with a source-reading gate to keep it out.

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| `.venv/bin/pytest` (plain) | 721 passed / 65 skipped | **735 passed / 65 skipped** | +14 passed, **zero new skips** |
| `DATABASE_URL=…:54329 LC_ALL=C .venv/bin/pytest` (armed) | 785 passed / 1 skipped | **799 passed / 1 skipped** | +14 passed, zero new skips |
| `env -u CRITIC_MODEL ANTHROPIC_API_KEY="" python -m evals` | 41/41 (100%) | **41/41 (100%)** | 0 — three cases flipped, the count did not |
| `tests/test_supervisor_routing.py` | 52 passed | **60 passed** | +8 |
| `tests/test_graph_smoke.py` | 37 passed | **43 passed** | +6 |
| `.venv/bin/ruff check .` | clean | clean | — |
| `git diff main -- .github/workflows/ci.yml` | — | **0 lines** | — |

**+14 accounted for exactly:**

| Where | Net | Why |
|-------|-----|-----|
| `test_graph_smoke.py` | +6 | 4 behaviour pins + the prompt-branch pin + the vocabulary gate |
| `test_supervisor_routing.py` | +8 | one parametrized test, eight states, pinning the responder is followup-only |
| `test_evals.py` | 0 | one test renamed and rewritten, three fixtures re-pointed; none added or dropped |

Every eval gate ran under `env -u CRITIC_MODEL ANTHROPIC_API_KEY=""`. Phase 16's fixture
gate compares `models.critic` against `graph.critic_model()`, so a CRITIC_MODEL-exporting
shell grades the one committed recording stale BY DESIGN and prints a spurious 40/41 that
looks exactly like a regression.

## RED first, quoted

The four behaviour pins were written and run against the shipped responder **before** any
implementation. `cb2e7a5` holds them red; `ba50cd8` is the fix.

```
$ .venv/bin/pytest tests/test_graph_smoke.py \
    -k "insufficiency_signal_routes or one_pass_bound or grounding_survives"

E   AssertionError: assert 'INSUFFICIENT...o such figure' == 'a grounded a...nlarged notes'
E   AssertionError: assert 'INSUFFICIENT...o such figure' == 'The research...efault value.'
E   AssertionError: assert 'INSUFFICIENT...o such figure' == 'INSUFFICIENT... lock_timeout'
E   AssertionError: assert ['responder', 'critic'] == ['responder', 'researcher', 'responder', 'critic']

4 failed, 37 deselected in 0.47s
```

The first three reds are one fact stated three ways and it is the threat this wave exists
to close: **today the sentinel text IS the shipped draft.** A responder that produced
`INSUFFICIENT: …` handed it to the critic, which approved it (it is grounded — it claims
nothing), and the caller received it as their answer.

## Task 1 — the sentinel, gated once (`cb2e7a5` red, `ba50cd8` green)

```python
pre_research = not state["followup_research_done"]
gap_instruction = (
    f"If the notes do not cover what was asked, respond with exactly "
    f"'{INSUFFICIENCY_SENTINEL} ' followed by one line naming what is "
    f"missing. Never answer from your own knowledge."
    if pre_research else
    "If the notes do not cover what was asked, say plainly "
    "that the research didn't cover it rather than guessing."
)
...
if pre_research and answer.strip().startswith(INSUFFICIENCY_SENTINEL):
    state["notes_insufficient"] = True
    state["trace"].append({"node": "responder", "insufficient": True})
    return state
```

One boolean, both branches. The signal path returns **before** `draft`, `reviewed`,
`revision_count` and the `answer_length` trace entry are touched, so "the window ships no
answer" is a property of the control flow rather than a promise kept by convention. The
post-research wording is the pre-17 sentence verbatim, because once looking has been tried,
saying so plainly IS the answer.

The `"The user is now asking a follow-up question:"` line survives both branches, asserted
by name — `harness.py` dispatches the responder on that substring, so rewriting it would
send every scripted follow-up case to the writer's reply.

**The mode-free gate, verified rather than assumed.** `"responder"` is produced by exactly
one expression in the routing table (`author`), and `author` is `"responder"` only when
`mode == "followup"`; every other `next_step` assignment is a literal. That premise now
has its own test (`test_the_responder_is_unreachable_outside_followup_mode`, eight
research-mode states), because it is what makes a `mode`-free `pre_research` safe.

### critic_node: zero diff at the function level (SC-3, ADR-0002)

```
$ git show main:src/research_agent/graph.py | sed -n '441,470p' > critic_main.py
$ sed -n '505,534p' src/research_agent/graph.py            > critic_now.py
$ diff critic_main.py critic_now.py && md5 -q critic_main.py critic_now.py
581b598b3081090c5ec0a5c2ced1997b
581b598b3081090c5ec0a5c2ced1997b
```

Identical bytes. Independently, no hunk in `git diff main -- src/research_agent/graph.py`
falls between main's `def critic_node` (:442) and `def supervisor_node` (:472) — the
nearest are `@@ -420,13` (the responder) and `@@ -473,13` (wave 2's supervisor docstring).

## Task 2 — the three flips, with their pins, in one commit (`028d13a`)

```
 evals/dataset.py    | 110 +++++++++++++++++++-----------
 tests/test_evals.py | 128 ++++++++++++++++++++++++++--------
 2 files changed, 162 insertions(+), 76 deletions(-)
```

| Case | After | What it now pins |
|------|-------|------------------|
| `followup-admits-a-gap` | research-then-**grounded** | the reach produces an answer: sentinel → a pass carrying Gartner's $4.2bn 2027 figure → an answer grounded in it |
| `followup-refuses-an-uncovered-figure` | honest-refusal-after-ONE-pass (**A1 decided**) | the pass returns more `statement_timeout` material and nothing on `lock_timeout`; the refusal ships WITH the attempt |
| `followup-refuses-a-forecast` | honest-refusal-after-one-pass | a 2028 market share is not findable; the pass adds a third pilot and no projections |

Measured through the real graph, not asserted (`run_case(capture_state=True)`):

```
== followup-admits-a-gap
  turn: What did Gartner forecast for agent memory spending in 2027?
   nodes: [supervisor, responder, supervisor, researcher, supervisor, responder, supervisor, critic, supervisor]
   reach: ['notes_insufficient'] | notes 240 -> 500 chars
      PASS followup_research_bounded  reached for new information exactly once
      PASS followup_reach_traced      notes_insufficient
      PASS followup_fact_checked      critic ran
```

Both refusal cases show the same node order with notes 241→468 and 229→440. **That is row
5 firing end to end** — the row wave 2 shipped as a consumer with no producer, and the
README row it flagged as describing a path no input could take. It can now.

The critic verdicts stayed `(APPROVED, APPROVED)` exactly as the plan predicted: the
sentinel pass never reaches the critic, so the follow-up's single critic call still pops
the second verdict. `_judge_calls_for` counts per follow-up TURN and is unaffected.

**Final taxonomy shape** — four shapes, each counted, plus the chain clause verbatim:

| Clause | Requires | Measured |
|--------|----------|----------|
| reaches and answers, no stop | ≥ 1 | 1 |
| reaches and still refuses, no stop | ≥ 2 | 2 |
| reaches and a guardrail stops it | ≥ 1 | 1 |
| answerable with no reach (the property Phase 17 KEPT) | ≥ 4 | 4 |
| a case with ≥ 2 follow-ups | present | yes |

The fourth clause is the one a rewrite loses first: it is the set
`grade_followup_research_bounded`'s False branch — the pre-17 check, verbatim — is applied
to, and at zero cases that branch grades nothing while looking green.

## Task 3 — the vocabulary sweep (`d0730d8`)

| Surface | Before | After |
|---------|--------|-------|
| `graph.py` module docstring | "Follow-ups skip classification and search entirely" | never classify; reach once when the notes cannot answer; the window ships nothing; critic unchanged |
| `graph.py` MAX_ITERATIONS comment | research worst case only | + the path-2 worst case is the same ten turns (signal+researcher replaces classifier+researcher) — **no formula change** |
| `chat.py` `print_result` | a special case explaining `no_prior_research` | one guardrail line for every reason; that run researches now |
| `chat.py` HELP | "`/ask` … using its notes -- no new web search" | answered from the run's notes, or from one fresh search when they can't cover it |
| `limits.py` `reserved_run_usd` | — | follow-ups joined the research cost class (~$0.21); **$0.20 stands, no resize**, 2026-09-01 threshold untouched |
| `docs/OPERATIONS.md` | — | the same paragraph in the operator's own document |

| Acceptance grep | Required | Measured |
|-----------------|----------|----------|
| `grep -c "no_prior_research" src/research_agent/chat.py` | 0 | **0** |
| `grep -c "no new web search" src/research_agent/chat.py` | 0 | **0** |
| `grep -v "^\s*#" src/research_agent/graph.py \| grep -c "skip classification and search"` | 0 | **0** |
| `grep -c "expect_research=True" evals/dataset.py` | 4 | **4** |
| `grep -c 'insufficiency="INSUFFICIENT:' evals/dataset.py` | 3 | **3** |

`test_no_prior_research_redefined_out_of_the_stop_vocabulary` reads both sources with
`pathlib` and asserts the name is absent from `chat.py` entirely, and appears in `graph.py`
exactly once outside a comment — as `followup_research = "no_prior_research"`, never as a
`forced_stop_reason`. Comment lines are stripped before counting, the grep-gate hygiene
rule: a gate that counts prose can be satisfied by deleting prose.

## Mutation log — thirteen probes, each red on the assertion that owns it

Applied from pristine scratchpad copies and restored from those copies (not from git,
since work was uncommitted — the 12-06 lesson); `md5` compared after every restore and
`git status --short` checked.

### The sentinel mechanism (Task 1)

| # | Mutation | Observed red |
|---|----------|--------------|
| P1 | `pre_research and` dropped from the parse — **the parse outlives its prompt** | `…post_research_sentinel_is_an_ordinary_draft` — *assert 'ANSWER: because of Rayleigh…' == 'INSUFFICIENT: still nothing…'*. The second sentinel sets the flag, row 5 refuses it (flag-gated), the turn falls through to the author, and the responder's fallback reply becomes the shipped answer. **The corruption is silent — no error anywhere.** T-17-08 mitigation |
| P2 | prompt branch never asks for the sentinel | `…the_sentinel_is_asked_for_only_before_the_pass` — the only test that can see it |
| P3 | the signal ALSO writes `draft` | **five** tests: all four behaviour pins plus the prompt pin. T-17-08 |
| P4 | the signal sets no flag | **five** tests — no route, no pass, wrong prompt on the second call |
| P5 | the signal's trace entry dropped | `…routes_to_researcher_and_ships_no_answer` and `…grounding_survives…` — T-17-09: the absence of `answer_length` is what proves nothing was generated, and it is asserted on an entry that has to exist |

### The dataset flip and its pins (Task 2)

| # | Mutation | Observed red |
|---|----------|--------------|
| Q1 | `admits-a-gap` stops expecting the reach | strata's grounded clause (*assert []*), the reaching-cases count, the real case's `followup_research_bounded` — **and the 41-case run drops to 40/41** |
| Q2 | `uncovered-figure` reverts to refusing without looking | strata's refuses-after-research clause (*['followup-refuses-a-forecast']* — one, needs two) + **40/41** |
| Q3 | the grounded case's `why` never says it reaches | `…reaching_cases_say_what_they_measure` — *followup-admits-a-gap reaches for new information but its why never says so* |
| Q4 | an answers-from-disk case starts expecting a reach | the kept-property clause (down to 3) + `followup_research_bounded` + `followup_reach_traced` on the real case + **40/41** |
| Q5 | a turn the notes cannot answer that neither reaches nor stops | the `stranded` clause — *['followup-admits-a-gap']* |

Q1, Q2 and Q4 each drop the **real** 41-case run, which is the evidence no dataset-only
assertion can give: these cases are graded by the suite that gates the phase. T-17-12
(dataset flipped without its taxonomy pins) is discharged by the same-commit stat above
plus Q1/Q3/Q5 observed red.

### The vocabulary gate (Task 3)

| # | Mutation | Observed red |
|---|----------|--------------|
| R1 | the REPL's no-notes special case comes back | the chat.py absence assertion |
| R2 | HELP promises "no new web search" again | the promise assertion |
| R3 | `no_prior_research` returns to the graph as a forced stop | the not-a-stop assertion |

**One honest note on R3.** The three graph-side clauses are a conjunction over a single
occurrence — it is not a stop, it IS the trace value, and there is exactly one of it — so
any mutation reds at least one of them and assertion ORDER decides which one reports. R3
first reported on the trace-value clause; the assertions were reordered so the strongest
claim reports first, and R3 was re-run and observed red on the not-a-stop clause. The
conjunction discriminates; which line names the regression was a choice, and it is now the
useful one.

## `--collect-only` on every selector shipped

Each run against the whole `tests/` tree (800 collected), not against the file under edit.

| Selector | Collected | Required |
|----------|-----------|----------|
| `tests/ -k insufficiency_signal_routes` | **1** | ≥ 1 (VALIDATION 17-03-T1a) |
| `tests/ -k one_pass_bound` | **3** | ≥ 3 (routing half from 17-02 + two here) |
| `tests/ -k grounding_survives_followup_research` | **1** | ≥ 1 (VALIDATION 17-03-T1c) |
| `tests/ -k sentinel_is_asked_for` | **1** | ≥ 1 (added this wave) |
| `tests/ -k responder_is_unreachable` | **8** | ≥ 1 (added this wave) |
| `tests/ -k no_prior_research_redefined` | **1** | ≥ 1 (VALIDATION 17-03-T3) |
| `tests/ -k taxonomy_followup_strata` | **1** | ≥ 1 |
| `tests/ -k reaching_cases_say_what_they_measure` | **1** | ≥ 1 |

## Acceptance criteria, measured

| Criterion | Measured |
|-----------|----------|
| RED-first evidence for the four behaviour pins | quoted above, commit `cb2e7a5` |
| `-k insufficiency_signal_routes` green | 1/1 |
| `-k one_pass_bound` collects ≥ 3, all green | 3/3 |
| `-k grounding_survives_followup_research` green | 1/1 |
| critic_node zero-diff vs main | `md5` identical, recorded above |
| Evals 41/41 after Task 1 (no case flipped yet) | **41/41 — honest green, stated** |
| Flip commit lists BOTH `evals/dataset.py` and `tests/test_evals.py` | yes (`028d13a`) |
| Evals exactly 41/41 after the flip | **41/41**, zero net-new cases |
| `grep -c "expect_research=True" evals/dataset.py` == 4 | **4** |
| Strata probe observed red, reverted | Q1 above; `md5` restore verified |
| `-k no_prior_research_redefined` green | 1/1 |
| Full suite + evals + ruff at plan end | **735/65**, **41/41**, clean |

## Deviations from plan

### [tree wins] `grep -c "INSUFFICIENT:"` is 4, not 3

**Found during:** Task 2. Wave 1's `Followup.insufficiency` field comment names the
sentinel (`# The \`INSUFFICIENT: ...\` line the responder emits *before* the research
pass`), so the line count includes it. The three AUTHORED lines are exactly three, on the
scoped grep `insufficiency="INSUFFICIENT:`. Nothing was changed to satisfy the number.

### [Rule 2 — the ungated half] A prompt-content pin beyond the plan's four

**Found during:** Task 1. The plan's four pins observe the PARSE. The fakes dispatch on
`"follow-up question"` and ignore the rest of the prompt, so flipping the prompt branch
changes no behaviour any of them can see — half of "identical gating" would have shipped
with no gate. `test_the_sentinel_is_asked_for_only_before_the_pass` reads both responder
prompts from one run and is the sole test P2 reds. It also carries the `key_links` pin:
the harness's dispatch substring survives both branches. **Commit:** `ba50cd8`.

### [Rule 2 — the premise under the gate] The responder-is-followup-only pin

**Found during:** Task 1. The plan (and the user's instruction) called for verifying rather
than assuming that a `mode`-free `pre_research` is safe. Verified by reading every
`next_step` assignment — and then pinned, because "verified once at implementation time" is
how a premise rots. Eight research-mode states, none of which may route to the responder.
**Files:** `tests/test_supervisor_routing.py`. **Commit:** `ba50cd8`.

### [Rule 1 — a fixture that outlived its case] Three refusal-grader tests re-pointed

**Found during:** Task 2. `refusal_turn()` built its state from
`followup-admits-a-gap`'s follow-up, which is now answerable — so
`grade_recorded_refusal` returned *"not a refusal case"* and three tests that exist to
catch a refusal that answers anyway, a refusal that never admits the gap, and a refusal
that says nothing **failed loudly** (they assert `not passed`). Re-pointed at
`followup-refuses-a-forecast`, which reaches and still cannot answer, with their
substituted answers rewritten to that case's subject and the invented figure re-picked so
`ungrounded()` still catches it (`40` against notes that contain only `2026`). Had these
tests been written as `assert passed`, they would have gone green and graded nothing.
**Commit:** `028d13a`.

### [Rule 2 — a before-pin whose condition can no longer be false] The flip-tag half retired

**Found during:** Task 2. Wave 2 deliberately KEPT the before-half ("a case still awaiting
its flip must say `Phase 17`") because three cases were still awaiting. After this wave no
case satisfies `not answerable and not expect_research` — the half would loop over zero
cases and pass forever. Replaced with a counted after-pin (`len(reaching) == 4`, so it
cannot grade an empty set) plus a `stranded` clause asserting no case has gone back to
refusing without looking. Renamed
`test_dataset_taxonomy_reaching_cases_say_what_they_measure`. Q3 and Q5 red each half.
**Commit:** `028d13a`.

### [already done in 17-02] The supervisor docstring

**Found during:** Task 3. The plan's item 2 asks for the "the only thing `mode` changes is
which node produces the text" sentence to be rewritten. Wave 2 already did it as a Rule-1
deviation — the sentence sat inside the function that wave rewrote. Verified in the tree
(it now names the two mode-gated reach rows and the caps precedence) and left alone.

### [standing instruction] README, whole-file pass

**Found during:** wave close. Two facts this wave falsifies, and only two:
- `721 tests` at lines 15 and 186 → **735**, measured, not arithmetic.
- Line 198 said offline evals grade "follow-up **isolation**" — that named
  `grade_followup_did_not_research`, retired in wave 1. Now "the one-pass bound on a
  follow-up that reaches for new notes", which is what the suite actually grades.

Deliberately **not** touched, as instructed: line 99's "no new search" API row and line 260's
follow-up limitation — wave 4's, and both still literally true of nothing now, which is
exactly why they are wave 4's whole-file pass and not a line edit here. **Commit:**
`d0ff064`.

## What shipped

| Task | What | Commit |
|------|------|--------|
| 1 (red) | four behaviour pins against code that fails them; FakeClient responder pop-list | `cb2e7a5` |
| 1 (green) | the sentinel: gated prompt branch + gated parse, docstring, prompt pin, followup-only pin | `ba50cd8` |
| 2 | three case flips + final taxonomy shape + re-pointed refusal fixtures, one commit | `028d13a` |
| 3 | vocabulary sweep across graph/chat/limits/OPERATIONS + the redefinition gate | `d0730d8` |
| — | README: what the evals grade, and the test count | `d0ff064` |

## Threat register — dispositions discharged

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-17-08 | mitigate | The sentinel is never written to `draft` (P3 reds five tests); the post-research sentinel is an ordinary draft (P1 shows the alternative silently corrupting the answer) |
| T-17-09 | mitigate | The signal path returns before any answer-shaped state is written; the pin asserts the trace entry exists AND carries no `answer_length` (P5) |
| T-17-10 | mitigate | One-pass bound in routing (17-02 P8), in smoke (`…ships_the_honest_refusal_with_the_attempt`, `…post_research_sentinel…`), and in grading (`followup_research_bounded` on three flipped cases) |
| T-17-11 | mitigate | `critic_node` byte-identical to main by `md5`, and no diff hunk falls inside its line range |
| T-17-12 | mitigate | Same-commit stat for `028d13a`; Q1/Q3/Q5 observed red; Q1/Q2/Q4 also drop the real suite to 40/41 |
| T-17-SC | accept | Zero packages installed |

No new security-relevant surface. The reach path was created in wave 2 and sits below the
budget and cap rows; this wave adds its second entrance and nothing else — no network
endpoint, auth path, file access pattern or schema changed. The one new trust boundary
(model output → routing flag) is the one the leak gate exists for, and it is closed on
both sides: the flag's only effect is a routing decision the supervisor makes on plain
state, and the text that produced it is discarded.

## Known stubs

None. Row 5, wave 2's deliberate half-build, now has its producer and is exercised end to
end by three golden cases and four smoke tests.

## What 17-04 inherits

- **The README row wave 2 flagged is now true**: `follow-up whose notes don't cover it,
  one pass unspent → researcher (traced notes_insufficient)` describes a path three golden
  cases take through the compiled graph.
- Untouched and still wave 4's: README line 99 ("no new search"), line 260 (the
  limitation, DELETE), `docs/DESIGN.md:21`, `docs/adr/0003-*` (status line only),
  `docs/adr/README.md` (index arithmetic), `service.py:701`'s docstring,
  `static/index.html` ×2 and the test pinning that placeholder copy.
- `evals/graders.py:186–219`'s "the notes are already on disk" docstrings were rewritten in
  wave 1; RESEARCH Q6 row 16 is already discharged.
- The README test count is **735** as of this wave; wave 4 adds tests and owns the next
  correction.
- ADR-0011 can now describe a shipped mechanism rather than a plan: sentinel idiom,
  identical gating, empty draft, one pass, honest tail. The ADR-0001 argument to record is
  the one the code makes — the supervisor routes on plain state; only the flag's ORIGIN is
  model output parsed by a fixed prefix, exactly as `approved` already is.

## Self-Check: PASSED

- `.planning/phases/17-followups-that-can-reach-for-new-information/17-03-SUMMARY.md` — FOUND
- `cb2e7a5` FOUND · `ba50cd8` FOUND · `028d13a` FOUND · `d0730d8` FOUND · `d0ff064` FOUND
- All nine modified files present; plain 735/65, armed 799/1, evals 41/41 keyless, routing
  60, smoke 43, `ruff` clean, CI diff 0 — all measured after the last probe restore, with
  `git status --short` clean of `src/` and `evals/`.
