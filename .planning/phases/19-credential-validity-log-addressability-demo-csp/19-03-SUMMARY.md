---
phase: 19-credential-validity-log-addressability-demo-csp
plan: 03
subsystem: service
tags: [logging, addressability, run-finished, event-naming, doc-pass, phase-close, keyless-suite]

# Dependency graph
requires:
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "research"
    provides: "the empirical proof that LangGraph 1.2.9 silently drops undeclared AgentState keys — which is why the fix lives in service.py and why the graph-side workaround is not merely wrong but invisibly wrong"
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "01"
    provides: "the branch this builds on; the /health credential fields whose doc surface this plan owed OPERATIONS"
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "02"
    provides: "the CSP whose doc surface this plan checked (and found nothing to correct); the 766/67 baseline this wave's delta is measured against"
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "04"
    provides: "the wasted live run this requirement exists because of — a run completed and the logs could not say which session held it"
provides:
  - "service._finished_log() / _failed_log() — the two terminal log payloads, each shared by the blocking and streaming paths"
  - "a `run_finished` record carrying run_id + session_id + duration_ms on all four HTTP routes, exactly one per run"
  - "a `run_failed` record on BOTH terminal paths — the streaming half did not exist before this plan"
  - "graph.graph_finished — the terminal-state line, honestly named and asserted to carry no session identity"
  - "tests/test_service.py — the log-addressability section: _LogCapture, six test items, three mutation reds"
  - "docs/OPERATIONS.md, README.md, .planning/codebase/ARCHITECTURE.md — re-derived against measured greps"
  - "19-VALIDATION.md reconciled end to end: status complete, nyquist_compliant true, two Manual-Only rows marked OPEN"
affects: [20, 21, 22]

# Tech tracking
tech-stack:
  added: []  # zero packages; stdlib logging and the existing observability singleton
  patterns:
    - "Put the log line where the FACT is, not where the work happened. `session_id` is minted after the graph returns, so the graph cannot carry it — and the tempting workaround (thread it through state) fails silently rather than loudly."
    - "Assert the absence too. `graph_finished` is asserted to carry NO session_id, so a future attempt to thread the id through AgentState fails a test instead of quietly doing nothing."
    - "When a plan says a control 'already exists', that is the sentence to test FIRST. `_stream`'s failure arm was documented as untouched and emitted nothing at all."
    - "An event name is a schema an operator counts against. Two call sites sharing one name double-counts every run, and the count drifts silently — nothing fails, the number is just wrong."
    - "A gate that reds as an AttributeError/KeyError reads as a broken test rather than a missing field. Assert presence ahead of the comparison."

key-files:
  created: []
  modified:
    - src/research_agent/service.py
    - src/research_agent/graph.py
    - tests/test_service.py
    - docs/OPERATIONS.md
    - README.md
    - .planning/codebase/ARCHITECTURE.md
    - .planning/phases/19-credential-validity-log-addressability-demo-csp/19-VALIDATION.md

key-decisions:
  - "The plan's premise for its own mutation was false, and the RED is what found it. The plan states the failed-run path 'already emits run_failed (existing, untouched)'. True of `_execute`; FALSE of `_stream`, whose except arm swallows its exception to keep the SSE contract and logged NOTHING. A failed stream recorded its metrics row, settled its reservation, sent the caller an error event — and left no trace in the log stream. The demo page runs on the streaming routes, so that was every failed demo run: the Phase 17 'a run happened and I cannot find it' problem in its worst form, since there is not even a completion line to fail to find. Fixed under Rule 2; without it, P-08's 'every HTTP-initiated run emits exactly one of the two' was true of one path out of two, and the exactly-once gate would have been guarding half a claim."
  - "The plan offered two possible reds for the ordering mutation (a NameError, or a mismatched id) and asked which it was. It is the NameError (`UnboundLocalError`), and the OTHER IS UNREACHABLE: `_execute` takes no `session_id` parameter, so before `on_complete` resolves there is no such name in scope on ANY of the four routes — including the two follow-up routes where the caller knew the id all along. The ordering is not a matter of a stale value; there is no value. That is a stronger statement than the plan anticipated, and it is why the emission cannot be 'moved up a couple of lines' by accident."
  - "P-07's third claim was re-measured before anything was renamed, and it held exactly: `run_finished` occurred ONCE repo-wide outside `.planning/` (`graph.py:638`), with no test, doc, eval or dashboard reading it. The first wave this phase where a plan's arithmetic needed no correction — recorded because the two prior waves both found drift, and 'the plan was right' is only worth stating when it was checked."
  - "`_finished_record` was renamed to `_finished_log` one commit after it was introduced. It sits one screen from `_failed_record`, which returns a metrics ROW, not a log payload; two neighbouring helpers called 'record' meaning different artifacts is a collision waiting to be misread, and it was cheap to fix at two call sites rather than leave for the reader who adds the third."
  - "The README's `/health` Limitations bullet is now ACTIVELY FALSE and was deliberately left that way. It says `/health` 'checks that the API keys are present, not that they work' — which is precisely what this phase built. Phase 22 owns deleting it; removing it here would strand that phase, and the transient is the same one Phase 18 left at `:285`. Stated loudly here because a knowingly-false sentence in the portfolio's front door is worth a paragraph in a summary, not a silent tick."

# Metrics
duration: 40min
completed: 2026-08-14
status: complete

actuals:
  tokens: 5659     # chars/4 over the realized src+tests+docs+README diff (22,639 chars), measured
  tasks: 3
  commits: 6
---

# Phase 19 Plan 03: Log addressability and the doc pass Summary

**One-liner:** A completed run is now findable from one log line — `run_finished` carries the
`session_id` the caller was told, on all four routes, exactly once per run, emitted from the one
place in the codebase where that id exists — and the wave's most valuable find was its
complement: a failed *stream* had been emitting no log record at all, so every failed demo run
was invisible in `fly logs` while looking fine in the metrics table and to the caller.

## Measured baselines and deltas

| Gate | Entering wave 3 | After | Delta |
|------|-----------------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest`) | 766 passed / 67 skipped | **772 passed / 67 skipped**, exit 0 | **+6 passed, +0 skipped** |
| `tests/test_service.py` | 145 passed | 151 passed | +6 (every new test lives here) |
| Offline evals (`ANTHROPIC_API_KEY="" python -m evals --min-pass-rate 0.9`) | 41/41, exit 0 | **41/41 (100% vs 90% required)**, real `$?` = **0** | unchanged |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | clean | — (one `F821` introduced and caught inside the wave; see Deviations) |
| Suite warnings | 2 | 2 | unchanged — both pre-existing; this plan added none |
| `src/research_agent/static/index.html` | 0 modifications | **0 modifications** | **±0 — re-measured at close** |

### The +6, test by test

The plan named four tests. The measured delta is **six test items**, because the follow-up test
is parametrized over two routes — so the plan's four names produce five items, and the sixth is
the tracer's.

| # | Test | Task |
|---|------|------|
| 1 | `test_run_finished_carries_the_session_id_for_a_new_session` | 1 |
| 2 | `test_run_finished_carries_the_session_id_on_the_streaming_path` | 2 |
| 3 | `test_run_finished_carries_the_session_id_for_a_followup[ask]` | 2 |
| 4 | `test_run_finished_carries_the_session_id_for_a_followup[ask/stream]` | 2 |
| 5 | `test_exactly_one_run_finished_record_per_request` | 2 |
| 6 | `test_a_failed_run_emits_run_failed_and_no_run_finished` | 2 |

No test was deleted, none became skipped, and no existing test needed its assertions changed.

### The phase's +23, wave by wave

| Wave | Suite | Delta | What it bought |
|------|-------|-------|----------------|
| entering | 749 / 67 | — | baseline |
| 19-01 | 760 / 67 | +11 | the credential probe: six `/health` fields, the invalid-vs-unreachable split, the exclusion with its positive control, the TTL floor, the never-waits gate |
| 19-02 | 766 / 67 | +6 | the demo CSP: header shape, independent derivation, both block counts, attribute absence, attachment scope, SSE caching headers |
| 19-03 | **772 / 67** | **+6** | log addressability: four routes, exactly-once, and the failure complement on both paths |

+11 +6 +6 = +23, and 749 + 23 = 772. The arithmetic closes.

## What shipped

### Task 1 — the tracer: `7bc8295` (red), `462a898` (green)

**P-07 re-measured before anything was renamed.** The plan asks for this explicitly rather than
trusting its own sentence, since the whole free-rename argument rests on the count:

```
$ grep -rn "run_finished" . --exclude-dir=.git --exclude-dir=.venv \
    --exclude-dir=__pycache__ --exclude-dir=.planning
src/research_agent/graph.py:638:                "event": "run_finished",
$ ... | wc -l
       1
```

**Exactly one occurrence**, in `graph.py`, with no test, doc, eval or dashboard reading it. The
plan's claim held precisely — the first wave this phase where the plan's arithmetic needed no
correction. `graph_finished` was confirmed at zero occurrences before being introduced.

The RED went first and failed at the right place for the right reason:

```
E  AssertionError: the completion record carries no session_id
E  assert False
E   +  where False = hasattr(<LogRecord: graph, 20, .../graph.py, 635, "run finished">, 'session_id')
```

The record's own origin is in the failure text — `graph.py:635` — which is the finding stated as
a test: the line named `run_finished` is emitted by the module that cannot know a session.

GREEN then:

- **`graph.py`** — the event value and message renamed, nothing else about the call moved: same
  fields, same placement, same condition. A comment above it states what it now means (this graph
  reached its terminal state) and what it deliberately does not carry (a session identity, which
  is a store concept it has no access to and which, for a new run, does not exist yet at that
  moment), and names `service.py` as the module that emits the completion — so the next reader
  following the thread lands in the right file.
- **`service.py`** — `_finished_log()`, one helper rather than two copies of a twelve-key dict,
  emitted from both `_execute` and `_stream` immediately after `metrics.record(...)` and inside
  the `try`, per P-08. It reads with the same `.get()` defaulting `RunRecord.from_state` uses over
  the same state, so the log line and the runs row it accompanies cannot disagree about whether a
  field was there. `duration_ms` is included: already computed on both paths, and the field an
  operator reading a completion record wants next.

Per the tracer contract, the slice's own gate was re-run end to end — both automated verifies
green, mutation red — before any expansion task.

### Task 2 — the other three routes, and the finding: `6ff6b7e` (red), `114a28b` (green)

Five of the six new assertions passed on arrival. The sixth reds:

```
E  AssertionError: a failed stream left no trace in the log stream at all
E  assert 0 == 1
```

See **The finding** below. The fix is `_failed_log()`, shared by both terminal arms exactly as
`_finished_log()` is, carrying the exception **class** and never `str(exc)` — the SSE arm redacts
and truncates that message before putting it on a wire a browser reads, and a log sink is the
wider audience, not the narrower one.

`_LogCapture` gained `clear()`, so the follow-up tests assert over one request rather than over
their own setup — without it, "the record's session_id equals the path parameter" would pass with
two records, which is the exact shape of the double-count the plan is guarding against.

### Task 3 — the doc pass and the phase close: `9e4bb71`, `4fac670`

Every item below was measured, not recalled.

**1. OPERATIONS, the credentials paragraph.** `/health reports whether each key is *present*,
never its value` — the sentence this phase falsified. Grep count **1 → 0**. It now states presence
and validity as two facts and the value as neither, names the fields, names the Phase 11 outage
it exists for, and states the property that did *not* change: the check still never blocks on a
provider, so an outage reads `null` ("could not determine", which is also what an absent key
reads) rather than restarting a healthy container. `false` means the provider actually rejected
the key, and only that.

**2. OPERATIONS, the environment table.** `CREDENTIAL_PROBE_TTL` added beside
`HEALTH_PROBE_BUDGET`, default `300.0`, with the two distinguished in one clause — how **often** a
provider is asked anything versus how **long** one store probe may take — because that difference
is the entire reason it is a new variable rather than a reuse of the old one. The 30s floor is
named. **Grep count 0 → 2**, not 1: the row plus the prose paragraph that motivates it. The plan's
`<done>` predicted 1; the count is 2 and both occurrences are load-bearing.

**3. OPERATIONS, the 9s ceiling.** The arithmetic is untouched because it is still exactly right.
One paragraph now says *why* the credential probe changes nothing about it — it runs on a pool
thread the request never joins, so it contributes zero to the bound — plus the condition under
which the paragraph would stop being true (if `/health` ever *waits* for a verdict, Fly's 15s
check timeout becomes a provider's to spend). A reader who has just learned `/health` probes
providers will otherwise reasonably assume the ceiling grew.

**4. "Why Supabase and not Neon" — read, and NOT edited.** The plan asks for a decision with a
reason either way. The passage reasons entirely from **database** query volume: `/health` queries
all three stores, Fly runs it every 30s per machine, so the database sees ~4 queries a minute
forever, which is what disqualifies Neon's compute meter and what keeps Supabase from pausing.
The credential probe calls **Anthropic and Voyage** — it never touches Postgres — and it fires at
the TTL's rate rather than the check interval's. Not one number in that passage moves. Left
untouched.

**5. The CSP and the log rename — two documented absences.**

```
$ grep -rniE "content-security|csp|security header" docs/ README.md   →  0
$ grep -rn "run_finished" docs/ README.md                             →  0
```

Nothing in `docs/` or `README.md` claimed anything about security headers on the demo page, and
nothing outside `ARCHITECTURE.md` named the old event. So wave 2's header and this wave's rename
falsified **no** prose. No CSP note was added: the plan permits one only if an existing section is
its natural home, and reading OPERATIONS' full section list (23 headers) there is none — the
nearest are "Container" (deployment credentials) and "Configuration" (the env table), and neither
is where a reader would look for a page's response header. A documented absence is the result.

**6. `.planning/codebase/ARCHITECTURE.md`.** The structured-event list named an event that no
longer exists. Corrected to what the code emits, split by which module emits it, with one sentence
on why the split is deliberate. That line only — the map is stale in other ways Phase 18 already
recorded as deferred.

**7. README whole-file pass.** Read end to end. Both test counts (`:15` and `:199`) **749 → 772**,
measured from the keyless run in this task. The endpoint table's `/health` row was checked and is
**not** falsified — it describes status semantics ("Liveness (always 200)"), which the new fields
do not touch. Nothing else in the file was found false. The `/health` Limitations bullet at `:289`
is untouched: **grep count still 1**, and the whole-file diff against the merge base is exactly
two lines, both test counts.

**8. `19-VALIDATION.md`** — reconciled end to end (below).

## The finding: a failed stream left no trace at all

The plan's Task 2 mutation (b) presumes a `run_failed` line on the streaming path to be preserved.
It says so directly — the failed-run path "already emits `run_failed` (existing, untouched)".

It does not. `_execute`'s except arm logs `run_failed`. **`_stream`'s except arm logged nothing.**
It recorded the failure row, settled the reservation — the arm the code's own comment calls "THE
ARM THAT IS EASY TO FORGET" — redacted the message, and yielded an `error` SSE event to the
caller. No log record.

So before this plan, a failed streaming run:

- **was** in the metrics table, at its real cost;
- **was** visible to the caller, as an error card on the demo page;
- **was not** in `fly logs`. At all. The run's last trace is a `model_call` line, then silence.

The demo page runs entirely on `/research/stream` and `/sessions/{id}/ask/stream`. **That was
every failed demo run.** It is the Phase 17 complaint — a run happened and the logs cannot say
what became of it — in a worse form than the one this phase was chartered to fix, because there
is not even a mis-named completion line to find.

Fixed under Rule 2. `_failed_log()` is now emitted from both arms, which is what makes P-08's
claim — every HTTP-initiated run emits exactly one of `run_finished` / `run_failed` — true of both
paths rather than of one. Without it the exactly-once gate would have been guarding half a claim
while reading as though it guarded the whole one.

**How it was found:** by writing the test that asserts the complement before trusting the code,
rather than after. The plan directed a read of that exact arm ("that arm is why the streaming
failure case needs its own assertion rather than inheriting `_execute`'s") — the planner suspected
an asymmetry in the *assertions* and the asymmetry turned out to be in the *emissions*.

## Mutation probes — each observed red, then reverted

| # | Mutation | Observed red |
|---|----------|--------------|
| 1 | The emission hoisted above `session_id = on_complete(final_state)` | `UnboundLocalError: cannot access local variable 'session_id' where it is not associated with a value` |
| 2a | The graph's terminal line restored to `"event": "run_finished"` so two call sites share the name | `assert 2 == 1` — the predicted double-count |
| 2b | The emission moved out of the `try` into a `finally` | `AssertionError: a run that failed reported itself finished`, `assert 1 == 0` |

Three mutations for the three named. All reverted; the suite re-run green after each.

### Mutation 1: the plan offered two reds and one of them cannot happen

The plan asks which of two reds occurred — a `NameError` surfaced by the run, or a mismatched id —
"because they prove different things about the ordering". It is the first. The second is
**unreachable**: `_execute` takes no `session_id` parameter, so before `on_complete` resolves
there is no such name in scope on **any** of the four routes — including `/sessions/{id}/ask`,
where the caller knew the id before the request even started, because that id lives in the route
closure and never enters `_execute`.

That is stronger than "the value would be stale". There is no value. The ordering cannot be
violated by a careless edit that moves the line up two lines; it can only be violated by someone
who also plumbs a new parameter through, at which point they are looking straight at the
question.

### Mutation 2a: the double-count is silent, which is the point

Under 2a nothing errors, nothing 500s, no test outside the log section notices. The suite would
have gone green on a service that emits two completion records per run — and an operator counting
completions out of `fly logs` would simply have had a number that was twice reality, with nothing
anywhere saying so. That is the failure family this project keeps meeting (the v1.1 audit's blind
daily cap; the Phase 17 run nobody could find), and it is why the exactly-once gate counts rather
than checking membership.

## Deviations from plan

### [Rule 2 — missing critical functionality] `_stream`'s failure arm now logs

The finding above. One log call plus a shared helper. **Commit:** `114a28b`.

### [Rule 2 — missing gate strength] The tracer's gate asserts presence before comparing

Run as first written, the RED produced a bare `AttributeError` at the comparison line. Correct
cause, wrong shape — and wave 2 hit this exact failure mode with a `KeyError` and corrected it the
same way. A `hasattr` assertion ahead of the comparison was added **before** committing the RED,
so the gate reds as `AssertionError: the completion record carries no session_id`. Applying wave
2's lesson before the mutation rather than after it is the whole value of that lesson being
written down. **Commit:** `7bc8295`.

### [Rule 1 — clarity defect introduced by this plan] `_finished_record` → `_finished_log`

`_finished_record` returns a log payload; `_failed_record`, one screen above it, returns a metrics
`RunRecord`. Two neighbouring helpers named "record" meaning two different artifacts is a
collision waiting to be misread — and this task was adding a third function to that neighbourhood.
Renamed while it was one commit old with two call sites. **Commit:** `114a28b`.

### [Rule 1 — stale measured claim] OPERATIONS' CI line said "470 tests, 12 offline eval cases"

Both numbers were already stale entering this phase (470 against a real 749; 12 against a real
41), so this is a pre-existing defect rather than one this phase created. Fixed anyway, and the
reason is specific: this phase **moves** one of the two numbers, and I was measuring both in this
very task to correct README's copies of them. Leaving a number I had just measured as false, in a
runbook, while correcting the identical number two files over, is not a scope boundary — it is
threat **T-19-14** (docs claiming a posture the code does not have) committed knowingly. Now
"772 tests, 41 offline eval cases". **Commit:** `9e4bb71`.

### [Rule 3 — blocking] One `F821` introduced and caught inside the wave

The `_finished_record` → `_finished_log` rename missed the `_stream` call site. `ruff check src
tests evals` caught it as `F821 Undefined name '_finished_record'` before the commit — and the
test suite caught it independently as 9 failures. Fixed before the commit; both ruff forms clean.

### [plan arithmetic] The `CREDENTIAL_PROBE_TTL` grep count is 2, not the predicted 1

The plan's `<done>` says the TTL row is "present (count 1)". It is 2: the table row, plus the
prose paragraph that explains what the variable buys. Both are deliberate and neither is a
duplicate of the other. Recorded because the plan's numbers are checked here rather than assumed.

### [plan file list] Task 2 modified `service.py`, which its `<files>` listed as tests-only

Anticipated by the plan's own reversibility note ("unless a route turns out to be uncovered — in
which case the fix is inside the helper Task 1 already extracted"). The fix landed near that
helper rather than inside it, because the gap was in the failure arm, not the success one.
`service.py` is in the plan frontmatter's `files_modified`.

### [anchors] Plan anchors checked; the source anchors held, the route anchor had drifted

| Anchor as written | Actual | Note |
|-------------------|--------|------|
| `service.py:268-318` — `_execute` | `:268-318` | correct |
| `service.py:296-312` — the `run_failed` arm | `:296-312` | correct |
| `service.py:325-377` — `_stream` | `:325-377` | correct |
| `service.py:665-703` — the four routes | **`:895-997`** | ~230 lines low: wave 1 inserted ~150 lines of credential code and wave 2 ~11, both above this point |
| `graph.py:634-649` — the terminal line | `:634-649` | correct |
| `observability.py:61-81` — `LOGGER_NAME` / `get_logger` | `:61-81` | correct (`LOGGER_NAME = "graph"` is at `:28`) |
| `test_graph_smoke.py:800-818` — the caplog idiom | **`:822-843`** | ~22 lines low |
| `test_service.py:1174-1200` — the blocking-failure idiom | `:1176-1214` | close; the section is where described |
| `test_service.py:2035-2060` — the streaming-failure idiom | **`:2374-2392`** | ~330 lines low, same cause as wave 2's test-file drift |
| `OPERATIONS.md:20-30, :634-650, :664-682, :133-140` | all correct | the doc anchors were the accurate ones this time |

No anchor pointed at the wrong *thing* once found, and nothing was built on a stale one.

### [not a deviation, stated to be explicit] The two scope fences held, measured

```
$ git diff --stat "$(git merge-base main HEAD)" HEAD -- src/research_agent/static/index.html
$ git status --porcelain -- src/research_agent/static/index.html
$ grep -c "not that they work" README.md
1
```

`index.html`: **zero** modifications, still absent from the branch's full diffstat. README's
`/health` Limitations bullet: **untouched**, count still 1. The whole README diff for this plan is
two lines, both test counts.

## The README bullet that is now false on purpose

Worth stating plainly rather than leaving as a tick. README `:289` says:

> **`/health` checks that the API keys are *present*, not that they work.** … What is missing is
> the other signal…

**That is now false.** It describes exactly what this phase built. It stays because Phase 22 owns
the Limitations section and deletes the bullet there; removing it here would strand that phase
with nothing to delete, and the same deliberate transient exists at `:285` from Phase 18. The
consequence, stated so nobody discovers it as a surprise: **between this merge and Phase 22, the
portfolio's front door contains one sentence that the code contradicts.** OPERATIONS — the runbook
an operator actually reads — is correct as of this plan.

## 19-VALIDATION reconciled

`status: complete`, `nyquist_compliant: true`, `reconciled: 2026-08-14`, matching Phase 18's
frontmatter shape. Both 19-03 rows filled with measured evidence. The sign-off's four boxes are
ticked, and the approval line states exactly what that does and does not cover.

**Thirteen mutations across the phase for the twelve the plans named**, and three of them
corrected something rather than confirming it:

| Wave | The correction |
|------|----------------|
| 19-01 | The blocking mutation **deadlocks** against the refresh worker's own `finally`, reding as a 5s `TimeoutError` in a different test — the named gate was never exercised until it was re-run with the wait outside the lock |
| 19-02 | The header mutation reds as a `KeyError` until the test is strengthened — the plan asked for a property the test as written did not have |
| 19-03 | The `finally` mutation's premise was false: the streaming failure arm emitted **no** log line at all |

**Two Manual-Only rows are OPEN**, marked as such in the table rather than dropped, each now
stating what the automated side already proves so the gap is exact:

1. **The live page under the CSP header** — UI-SPEC acceptance checks 1–7 against the deployed
   page. Browser CSP enforcement cannot run in pytest. Check 2 reads "zero violations
   *attributable to page resources*" per the UI-checker's hedge, so a browser-initiated favicon
   probe cannot cosmetically fail it.
2. **A real provider probe round-trip** — `/health` reading `valid: true` with a fresh
   `checked_at` inside one TTL. The suite is keyless by invariant; a suite that needed a live key
   would break on forks and rotations.

Both need the deploy this repo does manually. Neither is blocked on code.

## Phase gate battery, at close

```
$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest
772 passed, 67 skipped, 2 warnings in 28.24s

$ ANTHROPIC_API_KEY="" .venv/bin/python -m evals --min-pass-rate 0.9
PASS  41/41 cases (100% vs 90% required)
$ echo $?
0

$ .venv/bin/ruff check .            → All checks passed!
$ .venv/bin/ruff check src tests evals → All checks passed!
```

## Acceptance criteria, measured

| # | Criterion | Result |
|---|-----------|--------|
| 1 | One `run_finished` per completed run on all four routes, carrying `run_id` + the correct `session_id` | ✅ six test items; the id compared against what the caller was told on each route (response body, `result` event, path parameter) |
| 2 | A failed run emits `run_failed` and no `run_finished`, blocking and streaming | ✅ pinned on both — and the streaming half had to be **built**, not just asserted |
| 3 | The graph's terminal line is honestly named and demonstrably carries no session identity | ✅ `graph_finished`, with the absence of `session_id` asserted so a silent future workaround fails a test |
| 4 | OPERATIONS describes what `/health` now reports and documents the TTL; the 9s ceiling explained | ✅ falsified sentence grep 1 → 0; TTL present (count 2); ceiling arithmetic unchanged with one paragraph on why |
| 5 | README's test count measured; the `/health` Limitations bullet untouched | ✅ 749 → 772 from this task's own run; bullet grep still 1, README diff is two lines |
| 6 | Every automated 19-VALIDATION row carries measured Status evidence | ✅ all nine rows; contract reconciled, two Manual-Only rows marked OPEN |

## Threat register — dispositions discharged

| Threat | Disposition | How |
|--------|-------------|-----|
| T-19-11 Information disclosure (the record's fields) | accept | Every field is an id, an enum, a bool or a number. No question text, no PII, no credential. `session_id` is an opaque UUID accepted on the same reasoning `run_id` already was |
| T-19-12 Repudiation (completion counting) | mitigate | P-07 gives each call site an honest distinct name; exactly-one pinned on success (mutation 2a → `assert 2 == 1`) and zero pinned on failure (mutation 2b → `assert 1 == 0`). **Strengthened beyond the register:** the failure half now exists on the streaming path, so the complement is complete rather than half-observable |
| T-19-13 Tampering (log injection via echoed text) | accept | No caller-controlled free text enters either record; the JSON formatter escapes regardless. `_failed_log` carries `type(exc).__name__`, never `str(exc)` |
| T-19-14 Repudiation (docs claiming a posture the code lacks) | mitigate | Each surface re-derived against a grep measured before and after; two absences recorded as results; one pre-existing stale count fixed rather than stepped around. **One knowingly-false README bullet survives by explicit phase assignment and is named in its own section above** |
| T-19-SC Package installs | accept | Zero installs. Stdlib `logging` and the existing observability singleton |

## Deferred, recorded rather than silent

- **The two Manual-Only verifications**, above — both awaiting the manual deploy.
- **Phase verification.** No `19-VERIFICATION.md` exists yet; this plan closed the phase's
  execution and its validation contract, not its verification pass.
- **README's Limitations bullets** — Phase 22's, deliberately, including the one this phase
  falsified.
- **`.planning/codebase/` maps** remain stale in the ways Phase 18 recorded in
  `deferred-items.md`; only the structured-event line was corrected here.

## Self-Check: PASSED

- `src/research_agent/service.py`, `src/research_agent/graph.py`, `tests/test_service.py`,
  `docs/OPERATIONS.md`, `README.md`, `.planning/codebase/ARCHITECTURE.md`, `19-VALIDATION.md` —
  all present and modified on this branch.
- Commits `7bc8295`, `462a898`, `6ff6b7e`, `114a28b`, `9e4bb71`, `4fac670` — all present in
  `git log`.
- No stubs, no TODO/FIXME, no skipped tests introduced. Every `<verify>` command in the plan was
  run; no gate is unrun. The one `<human-check>` is the two Manual-Only rows, which are recorded
  as OPEN rather than treated as satisfied.
