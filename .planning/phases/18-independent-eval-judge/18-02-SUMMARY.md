---
phase: 18-independent-eval-judge
plan: 02
subsystem: evals
tags: [refusal-guard, response-boundary, recorder-refusal, red-first, ungated-rule-probe, second-fake]

# Dependency graph
requires:
  - phase: 18-independent-eval-judge
    plan: "01"
    provides: "the judge on claude-opus-4-8, priced; and the standing note that FakeJudgeClient's Response carries only .content"
  - phase: 18-independent-eval-judge
    plan: "research"
    provides: "Finding 2 (refusal semantics), Finding 3 (the traced propagation into result.error), pitfalls 3 and 8"
  - phase: 15-independent-eval-suite
    plan: "01"
    provides: "the recorder's single refusal path, and the rule that a refused write leaves no file"
provides:
  - "evals/graders.py Judge.verdict:770 — stop_reason is read before any content block; a refusal returns a FAILED verdict"
  - "evals/graders.py _refusal_detail:785 — the contractual 'the judge DECLINED to grade this case (stop_reason=refusal, category=...): ...' string"
  - "evals/graders.py:773 — max_tokens truncation raises TRUNCATED rather than masquerading as malformation (Open Question 2, taken)"
  - "tests/test_evals.py RefusingJudgeClient / RefusalStopDetails — the refusal-shaped fake, reusable by 18-04 and Phase 21"
  - "the measured fact that record mode's console prints grader names and NOT grade details (announce is never called under --record)"
affects: [18-04, 21]

# Tech tracking
tech-stack:
  added: []  # zero packages installed
  patterns:
    - "Read WHY a response stopped before reading WHAT it said. A refusal is a normal HTTP 200 with empty content, so a parse-first boundary reports the model's DECISION as the parser's failure — and, through a blanket except, as the paid run's failure."
    - "A guard that raises where the caller has a blanket except is a guard that changes the error's wording, not its blame. Surface it as data (a failed Grade) if the honest branch is downstream."
    - "A pitfall that names one fake is a claim about a class of fakes. `grep` for every object that stands in for the response type, not for the name the research happened to write down."
    - "Assert the ABSENCE that bounds a claim. `assert 'DECLINED' not in out` converts 'the console does not carry the detail' from folklore into a measured, falsifiable fact."

key-files:
  created: []
  modified:
    - evals/graders.py
    - tests/test_evals.py

key-decisions:
  - "The refusal is a failed Grade, never an exception — and the reason is measurable, not stylistic. With the guard deleted, the recorder's message is verbatim `refusing to record 'technical-figures': the run errored (ValueError: Judge returned unparseable verdict: '')`. That sentence blames a successful, paid pipeline run for a decision the judge made. The graded-finding shape puts the same event in `_refuse_failing`'s second branch, naming `judge_grounding`, with zero changes to evals/fixtures.py or evals/__main__.py."
  - "18-RESEARCH's pitfall 3 named ONE fake; there are TWO. `RecordingFakeClient._Response` (tests/test_evals.py:3060 neighbourhood) is also handed to the real `Judge.verdict`, and its missing `stop_reason` did not merely break a test — it DEMONSTRATED the bug: the AttributeError was swallowed by run_case's blanket except and surfaced as 'the run errored'. The plan's inventory located a neighbourhood, not the set (the 16-03 corollary, again)."
  - "Open Question 2 (max_tokens) was TAKEN, at one branch and one test. Truncation stays in the raise family — it is an operational failure, not a graded finding — but it says TRUNCATED and quotes the partial JSON, so the 1500-token budget shared with adaptive thinking is named instead of a prompt or schema being blamed. Probed red alone."
  - "`_refusal_detail` reads every `stop_details` field through `getattr`. Deleting only the `is None` early return therefore yields `category=None` rather than an AttributeError — which is why the None-variant test asserts `'category' not in detail` rather than merely that it does not crash. A crash-shaped assertion would have gone green on a lie."
  - "The record console's limit is pinned, not fixed. In record mode `main` wires `announce_recording` (grader names) and never `announce` (grade details), so the operator sees WHICH grader refused and the word DECLINED rides `--report` only. Fixing it means editing evals/__main__.py, which this plan's own success criterion holds at zero changes. Recorded in deferred-items.md and pinned by an absence assertion so a later fix is deliberate."

# Metrics
duration: 34min
completed: 2026-08-13
---

# Phase 18 Plan 02: The judge's response boundary, made honest Summary

**One-liner:** `Judge.verdict` now reads `stop_reason` before it reads a single content
block, so a safety-classifier refusal becomes a FAILED verdict saying *the judge DECLINED
to grade this case* and flows into the recorder's existing failed-graders branch — while
malformed output still raises and truncation now says so by name; every gate observed red
first, including the one that proves the rule is gated at all.

## Measured baselines and deltas

| Gate | Before (post-18-01) | After | Delta |
|------|---------------------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:cacheprovider`) | 742 passed / 67 skipped | **747 passed / 67 skipped**, exit 0 | **+5 passed, +0 skipped** — exactly the five tests this wave added, no unexplained skip |
| `tests/test_evals.py` | 172 passed | 177 passed | +5 |
| Offline evals (`ANTHROPIC_API_KEY="" .venv/bin/python -m evals`) | 41/41 exit 0 | **41/41 (100% vs 90% required), exit 0** (verified as a real `$?`, not a pipeline's) | unchanged — the guard stales nothing |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | clean, both forms | — (no lint errors introduced) |
| `evals/fixtures.py`, `evals/__main__.py` | — | **0 lines changed** | success criterion 3, by `git show --stat` |

The five tests: two refusal tests, one truncation test, and two recorder-flow tests.

## What shipped

### Tasks 1 + 2 — one commit, `dd7b2e8`

The tests could not land before the guard (they were red on purpose) and the guard could
not land before the tests (a pin written after a fix says nothing — the 17-02 lesson), so
both are in one commit.

```
dd7b2e8 feat(18-02): judge refusals are graded findings, not parse errors
 evals/graders.py    |  51 ++++++++++++++++++
 tests/test_evals.py | 146 +++++++++++++++++++++++++++++++++++++++++++++++++++-
```

**`evals/graders.py:770`** — the boundary, in the order that matters:

```python
if response.stop_reason == "refusal":
    return False, _refusal_detail(response)
text = "".join(b.text for b in response.content if b.type == "text")
if response.stop_reason == "max_tokens":
    raise ValueError("Judge verdict was TRUNCATED at max_tokens ... not malformed: ...")
try:
    parsed = json.loads(text)
    ...
except (json.JSONDecodeError, KeyError, TypeError) as exc:
    raise ValueError(f"Judge returned unparseable verdict: {text[:200]!r}") from exc
```

Three outcomes, deliberately apart because they call for three different actions —
refused (nothing was graded), truncated (the token budget), malformed (the parse or the
prompt). The stop reason is read off the **typed field**; nothing is inferred from the
text (Don't Hand-Roll: text-sniffing an empty body is the mis-parse-into-a-confident-
wrong-number failure ADR-0010 carries forward).

**`evals/graders.py:785`, `_refusal_detail`** — builds the contractual string and
None-guards every `stop_details` read. `stop_details` is typed `RefusalStopDetails | None`
in SDK 0.120.0 (verified by introspection this session, alongside the `StopReason` literal
containing `"refusal"`), and an AttributeError here would land the refusal straight back
in the run-errored branch the guard exists to escape.

The `verdict` docstring now states the boundary and the three outcomes, including *why*
the refusal returns rather than raises. **The module docstring at `:13-19` was not
touched** — it still says judge and critic share a model, which is 18-04's known transient.

**`tests/test_evals.py`** — `FakeJudgeClient` gains `stop_reason="end_turn"` (settable,
which is what the truncation test uses) and `stop_details=None`; `RefusalStopDetails`
(:610) and `RefusingJudgeClient` (:620) are the refusal-shaped twin. The twin is a
sibling class rather than a flag because it never runs out of payloads — a recording
calls the judge once per judge grader per turn, and a client that popped from a list
would fail on the second call for reasons that have nothing to do with refusals.

### Task 3 — the recorder flow, `ca59b62`

```
ca59b62 test(18-02): a judge refusal reaches the recorder's failed-graders branch
 .../deferred-items.md | 37 ++++++++++++
 tests/test_evals.py   | 92 ++++++++++++++++++++++++++++++-
```

`test_a_judge_refusal_reaches_the_recorders_failed_graders_branch` (:2642) drives
`record_suite` with the **real** `G.Judge` over `RefusingJudgeClient` — `FakeJudge`
(:2616) has no client and its `verdict` never reaches the guard, so a test built on it
would exercise none of this. All three facts asserted:

| Fact | Assertion | Measured |
|------|-----------|----------|
| (a) failed-graders branch, not run-errored | `"judge_grounding" in refusal`, `"the run errored" not in refusal`, `case["error"] == ""` | `refusing to record 'technical-figures': judge_grounding, judge_answers_the_question failed.` |
| (b) refusal-shaped reason CONTENT | every failed grade `.startswith("the judge DECLINED to grade")`, carries `stop_reason=refusal` and the explanation, `judged is True`; and the failed set is **exactly** the two judge graders | `the judge DECLINED to grade this case (stop_reason=refusal, category=general_harms): declined by the safety classifier` |
| (c) a refused write leaves no file | `list(tmp_path.iterdir()) == []` | empty |

`test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines` (:2701)
drives `main` end to end through `cli_record` with a refusing judge arm added to
`RecordingFakeClient`: exit 1, no fixture, console says `1 case(s) were NOT recorded` and
names `judge_grounding`, never says "the run errored".

## The plan's seam claim, checked against the tree

The plan said: *"if the FixtureError message carries only grader names, assert the detail
through the announce path that prints failed grades."* **Checked: in record mode there is
no such path to assert through.** `evals/__main__.py` passes `on_outcome=announce_recording`
to `record_suite`; `announce` — the closure that prints `f"{grade.grader}: {grade.detail}"` —
is wired only into `run_suite`'s `collect` and into `_replay_fixtures`. Under `--record` it
is never called.

So the surfaces divide like this, measured:

| Surface | Carries | Where |
|---------|---------|-------|
| Console, record mode | the grader names, via the `FixtureError` | `announce_recording`, and the "N case(s) were NOT recorded" block |
| `--report` JSON | the DECLINED detail | `cases[].turns[].grades[].detail` |
| `result.failures` (in-process) | the DECLINED detail | what `announce` would print, if record mode called it |

The CLI test pins this **including the absence** (`assert "DECLINED" not in out`), so the
statement is falsifiable rather than folklore, and a later improvement reds it and gets
made on purpose. Not repaired here: the repair is in `evals/__main__.py`, which this
plan's own success criterion holds at zero changes, and operator-facing announcements are
a deliberate deliverable in this project (16-02), not a side effect of a guard. Logged in
`.planning/phases/18-independent-eval-judge/deferred-items.md` with the reasoning, because
"judge_grounding failed" invites the reading *the report is ungrounded* — the one
conclusion a refusal does not support.

## Mutation probes — each observed red, then reverted

### Probe 1 (validation row 3a) — the RED-first refusal test, on CURRENT code

Both refusal tests, run against the unguarded `verdict` before the guard existed:

```
FAILED tests/test_evals.py::test_judge_refusal_is_a_graded_finding_not_a_parse_error
FAILED tests/test_evals.py::test_judge_refusal_without_details_still_names_the_refusal
E   ValueError: Judge returned unparseable verdict: ''
evals/graders.py:748: ValueError
2 failed, 19 passed, 153 deselected
```

The misleading path IS the recorded red — reported at `graders.py:748`, the parse's
`except`, for a response that never contained anything to parse. The 19 green in the same
selector are the pre-existing `refus`-matching tests (the refusal *graders*), untouched.

### Probe 2 (validation row 3b, the 15-06 ungated-rule check) — delete the `stop_reason` check

Whole file, guard removed:

```
..............................................FF........................ [ 41%]
FAILED tests/test_evals.py::test_judge_refusal_is_a_graded_finding_not_a_parse_error
FAILED tests/test_evals.py::test_judge_refusal_without_details_still_names_the_refusal
(2 failed, 173 passed)
```

**The two refusal tests red ALONE.** Nothing else in the file moves, so no other test was
leaning on the guard by accident and the rule ships gated rather than incidentally covered.

### Probe 3 (validation row 3c) — the recorder flow, guard removed

```
E   assert 'judge_grounding' in "refusing to record 'technical-figures': the run errored
    (ValueError: Judge returned unparseable verdict: ''). Pass force=True to record it anyway."
FAILED tests/test_evals.py::test_a_judge_refusal_reaches_the_recorders_failed_graders_branch
FAILED tests/test_evals.py::test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines
```

Both red on the reason's **content**. This is the probe the plan cared most about: under
the mutation `written` is still `False` and the fixture file is still absent, so a
reason-blind assertion (`assert not written`) is green under both branches and gates
nothing. The only thing that changes is who gets blamed — and that is the whole phase.

### Probe 4 (discretionary branch) — delete the `max_tokens` raise

```
FAILED tests/test_evals.py::test_judge_says_truncated_rather_than_unparseable_when_it_ran_out_of_tokens
E   Regex pattern did not match. Actual message: 'Judge returned unparseable verdict: \'{"passed": true, "rea\''
```

Red alone, and the actual message is exactly the misdiagnosis the branch exists to prevent:
cut-off JSON reported as malformed.

### Probe 5 (the None-guard) — delete `_refusal_detail`'s `is None` early return

```
FAILED tests/test_evals.py::test_judge_refusal_without_details_still_names_the_refusal
E   assert 'category' not in 'the judge D...tegory=None)'
```

Red alone, and **the shape of this red is the point**: because every `stop_details` field
is read through `getattr`, deleting the early return produces `category=None` rather than
an AttributeError. A test asserting only "does not crash" would have gone green on a
verdict detail that reports a category the API never sent. The assertion is
`"category" not in detail` for exactly that reason.

## Deviations from plan

### [Rule 3 — blocking] A SECOND judge-shaped fake the research inventory never named

`RecordingFakeClient._Response` (tests/test_evals.py, the `cli_record` neighbourhood) is
handed to the real `Judge.verdict` for every judge-model call and had only `.content` and
`.usage`. The moment the guard read `response.stop_reason`,
`test_a_refused_recording_fails_the_build_at_a_rate_that_would_pass` failed:

```
E   AssertionError: assert 'judge_grounding' in 'cost preview\n  recording      1 case(s)...'
```

**The failure mode is the finding.** The AttributeError did not surface as an
AttributeError: it was raised inside a judge grader, swallowed by `run_case`'s blanket
`except` (harness.py:334), and surfaced as *"the run errored"* — the identical
mislabelling this plan exists to remove, arriving through a fake instead of through a
refusal. Fixed by giving `_Response` `stop_reason="end_turn"` and `stop_details=None`,
with a comment stating what it demonstrated.

18-RESEARCH pitfall 3 and the plan both named `FakeJudgeClient` at `:570` and only that.
Every object standing in for the response type had to be found by grep
(`grep -rn "self.content = \|content = \["` across `tests/` and `evals/`), which returned
five: the two judge fakes, the new refusal twin, `test_graph_smoke.py`'s `Response` (graph
only, never reaches `Judge`) and `evals/harness.py`'s `_Response` (the pipeline's
`ScriptedClient`, never reaches `Judge`). **The 16-03 corollary again: an inventory locates
neighbourhoods, it does not enumerate the set.**

### [discretion taken] Open Question 2 — `max_tokens` got its own honest message

Taken, at one branch and one test, and probed red alone. `max_tokens=1500` is shared with
adaptive thinking, so the plausible way a real verdict fails to parse is that the model
deliberated at length and the object ended mid-string. Truncation stays in the **raise**
family — it is an operational failure, not a graded finding — but it names TRUNCATED and
quotes the partial JSON as evidence. The guard-deletion probe is unaffected by it (a
separate branch, a separate test), so it did not weaken probe 2.

### [seam claim corrected] The announce path the plan pointed at does not run in record mode

Detailed above. The plan's instruction was conditional ("if the FixtureError message
carries only grader names… assert the detail through the announce path") and the condition
held, but the named alternative does not exist under `--record`. Asserted on the surfaces
that do exist, and the absent one is pinned as an absence.

### [not a deviation, stated to be explicit] What was not touched

`evals/fixtures.py` and `evals/__main__.py`: zero lines. `graders.py`'s module docstring
(:13-19) and `harness.py`'s `_state_judge_critic_relation` — 18-04's known transients,
left as wave 1 left them. README's Limitations bullet (Phase 22), the critic, `fly.toml`.
No ADR written (18-03's). No packages installed.

## Success criteria, measured

| Criterion | Evidence |
|-----------|----------|
| ROADMAP SC-2: a refused judge response is a graded finding, not a parse error | `judge.verdict()` returns `(False, "the judge DECLINED to grade this case (stop_reason=refusal, category=general_harms): ...")`; probe 1's red is the behaviour it replaced |
| Refusal / malformation / truncation are three distinguishable outcomes | three tests, three messages, three probes each red alone; `test_judge_raises_on_an_unparseable_verdict` unmodified and green throughout |
| Zero changes in `evals/fixtures.py` and `evals/__main__.py` | `git show --stat dd7b2e8 ca59b62` lists neither |
| A refusal reaches the failed-graders branch, leaves no file | probe 3's contrast, plus `list(tmp_path.iterdir()) == []` |
| Keyless invariant; offline evals not staled | every command run with `ANTHROPIC_API_KEY=""`; 41/41 exit 0 |

## Threat register — dispositions discharged

| Threat ID | Disposition | Discharged by |
|-----------|-------------|---------------|
| T-18-03 (tampering, `Judge.verdict` parse) | mitigate | The typed `stop_reason` field is checked before any content is read; nothing sniffs the text. Probe 2 shows the check is load-bearing and nothing else covers it. Malformed output still raises, so a mis-parse can never be scored. |
| T-18-04 (repudiation, recorder refusal path) | mitigate | The refusal reaches the ONE existing refusal path with a named grader and a refusal-shaped reason (probe 3's contrast is the evidence); the refused write leaves no file. Residual, recorded rather than hidden: the console prints the grader name and not the detail — see deferred-items.md. |
| T-18-05 (elevation, judge grades injected text) | accept | Unchanged by this plan. |
| T-18-SC (package installs) | accept | Zero packages installed. |

## What wave 3 inherits

- A judge boundary that distinguishes declined / truncated / malformed, with all three
  probed.
- `RefusingJudgeClient` and `RefusalStopDetails` in `tests/test_evals.py`, reusable for
  18-04's collision work and Phase 21's record run.
- The measured console limitation in `deferred-items.md` — not 18-03's job (that is
  ADR-0012), but it should not be rediscovered from scratch.
- Unchanged and still owed: `graders.py`'s module docstring, `_state_judge_critic_relation`,
  the ADR chain, and the never-yet-round-tripped real Opus 4.8 verdict (Phase 21).

## Self-Check: PASSED

- `evals/graders.py` — `verdict` at :731, refusal check at :770, truncation at :773,
  `_refusal_detail` at :785. Present.
- `tests/test_evals.py` — `RefusalStopDetails` :610, `RefusingJudgeClient` :620, the five
  new tests at :676, :697, :731, :2642, :2701. Present.
- `.planning/phases/18-independent-eval-judge/deferred-items.md` — present.
- Commits `dd7b2e8` and `ca59b62` exist on `gsd/phase-18-independent-eval-judge`.
- Working tree clean after all five mutation probes were reverted
  (`git status --short` empty; `git checkout evals/graders.py` after each).
