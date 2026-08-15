# Phase 21 — Record Run Operator Runbook

**Written:** 2026-08-15 (plan 21-01, wave 1 — keyless, zero spend)
**For:** the operator (or the wave-2 executor) at the two paid checkpoints in plan 21-02.

Every command below was tested in its **keyless** form while this runbook was written —
the quote-only invocations were run for real, and the `--yes` forms differ from them by
exactly that one flag. Nothing in wave 1 spent a cent.

**This file contains no key values. Placeholders only, always.**

---

## 0. What you are about to spend

Quoted 2026-08-15 from the live preview captured at
[`record-quote-before.txt`](record-quote-before.txt) (exit 2, no API client built):

| | Cases | Quoted |
|---|---|---|
| Stage 1 — calibration (`technical-figures`) | 1 | **$0.3577** |
| Stage 2 batch A — routing/guardrail core | 10 | $3.8900 |
| Stage 2 batch B — technical + contested | 11 | $4.2790 |
| Stage 2 batch C — sparse + general + injection | 10 | $3.8900 |
| Stage 2 batch D — the follow-up-bearing cases | 8 | $5.0645 |
| **Total** | **40** | **$17.4812** |

Basis: **1 measured, 39 assumed** — assumed tokens dominate. Every per-batch sum above was
derived from the captured quote's own per-case lines, not from arithmetic on a memory; all
four matched the planning-time figures to the cent, and $17.1235 (the 39) + $0.3577
(`technical-figures`) = $17.4812 exactly.

Note stage 1 quotes **$0.3577, not the ~$0.39** that 21-CONTEXT cites. That is the
preview working: `technical-figures` is the one case priced from a *measured* fixture
(`measured pipeline $0.2427 (fixture 2026-08-10) + assumed judge`) rather than from assumed
tokens. The re-quote at checkpoint 2 will move these numbers; the numbers it prints win.

**There is no runtime circuit breaker.** The deployed service's spend cap and reservation
guard (`src/research_agent/limits.py`) are structurally not in this path — the recorder
drives `graph.app.invoke` directly and never goes through the FastAPI service. The only
spend controls are the quote-then-`--yes` gate and the batch scoping below.

---

## 1. Env preparation — do this once per shell, and re-assert before every `--yes`

**Keys reach the recorder ONLY from the process environment.** Nothing in the evals import
chain reads any file: PR #28 removed the codebase's only `load_dotenv()` call from
`chat.py`'s `main()`, and `evals/__main__.py` never imported `chat` in the first place.
`anthropic.Anthropic()` is constructed with no arguments and the SDK reads
`ANTHROPIC_API_KEY` from `os.environ` itself; `VoyageEmbedder` reads `VOYAGE_API_KEY` the
same way at first use. Do **not** "fix" this by adding a dotenv import to `evals/` — that
reopens exactly the leak PR #28 closed, and keyless CI (`ci.yml` sets
`ANTHROPIC_API_KEY: ""` and expects it to stay empty) is what would silently break.

Either preparation works:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."      # placeholder — paste your own
export VOYAGE_API_KEY="pa-..."             # placeholder — paste your own
```

```bash
set -a; source .env; set +a
```

### The assertion — run it AFTER any sourcing, and BEFORE every `--yes`

```bash
.venv/bin/python -c "
import os, sys
missing = [k for k in ('ANTHROPIC_API_KEY', 'VOYAGE_API_KEY') if not os.environ.get(k)]
poison  = [k for k in ('CRITIC_MODEL', 'EVAL_JUDGE_MODEL') if os.environ.get(k)]
assert not missing, f'missing key(s): {missing} -- the SDK raises AFTER the money-approval, not before it'
assert not poison, f'set, must be unset: {poison} -- fixtures recorded now go red in keyless CI'
print('env ready: keys present, CRITIC_MODEL and EVAL_JUDGE_MODEL unset')
"
```

It must print `env ready: ...`. All three of its paths were exercised while writing this
runbook: the happy path prints and exits 0; a missing key raises
`missing key(s): ['VOYAGE_API_KEY']`; both variables set raises
`set, must be unset: ['CRITIC_MODEL', 'EVAL_JUDGE_MODEL']`.

**Why each of the four matters:**

- **`ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` must be NON-EMPTY.** Missing them does not
  produce a graceful refusal — the SDK raises its own auth error *after* you have already
  approved the spend at the checkpoint, which is the worst moment to discover it.
- **`CRITIC_MODEL` must be UNSET.** `record_case_to_fixture` writes
  `"critic": graph.critic_model()` into the fixture, and `grade_fixture_current`
  (`harness.py:374-381`) compares that recorded value against `graph.critic_model()` at
  replay time. Keyless CI never sets `CRITIC_MODEL`. So a fixture recorded in a shell that
  *does* set it is stale-red in CI **forever**, and the only cure is re-recording it — at
  full price.
- **`EVAL_JUDGE_MODEL` must be UNSET.** It is read at import time
  (`graders.py:46`, `JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)`),
  and `judge.model` is what lands in the fixture's `models.judge`. Set it, and you record
  verdicts under a judge that is not the one ADR-0012 settled — which 21-03's judge pin
  reds, correctly. This phase's entire premise is verdicts recorded once, under the settled
  judge.

**`source .env` can itself set those last two.** That is precisely why the assertion runs
*after* the sourcing, not before it. If it trips, `unset CRITIC_MODEL EVAL_JUDGE_MODEL` and
re-run the assertion.

---

## 2. Stage 1 — calibration (checkpoint 1)

One case: `technical-figures`. It is the case that must be re-recorded anyway — its
committed fixture carries `models.judge: "claude-opus-5"`, the judge ADR-0012 superseded —
so calibrating on it costs nothing beyond what the phase had to spend regardless. It has no
follow-ups and no budget override, which makes it the cleanest shape to measure.

```bash
# Quote only. Prints the preview, exits 2, builds NO API client.
.venv/bin/python -m evals --record --case technical-figures
```

```bash
# Spends. Only after the checkpoint approval.
.venv/bin/python -m evals --record --case technical-figures --yes \
  --report .planning/phases/21-forty-recorded-answers/record-stage1-report.json
```

Then, keyless, before going near stage 2:

```bash
ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --quiet; echo "exit=$?"
```

and confirm the judge actually moved:

```bash
.venv/bin/python -c "
import json; print(json.load(open('evals/fixtures/technical-figures.json'))['models'])
"
```

`models.judge` must now read `claude-opus-4-8`. If it reads anything else, `EVAL_JUDGE_MODEL`
was set — stop, unset it, and re-record this one case before spending on 39 more.

---

## 3. Stage 2 — the bulk 39, in four batches (checkpoint 2)

Run **A → B → C → D**, in order, committing after each. D runs last deliberately: it is the
most expensive batch, its follow-up turn shapes are the uncalibrated ones, and it holds the
three cases judged on the honesty of a refusal — so it is where a refusal is most plausible.

Re-run the section-1 assertion before **each** of these four commands. A laptop that slept,
or a new terminal, is a new environment.

### Batch A — routing/guardrail core, 10 cases, quoted $3.8900

```bash
.venv/bin/python -m evals --record --yes \
  --report .planning/phases/21-forty-recorded-answers/record-stage2-a-report.json \
  --case contested-viewpoints --case sparse-coverage --case general-summary \
  --case unknown-label-falls-back --case revision-then-approval \
  --case revision-cap-is-labelled --case budget-cap-is-labelled \
  --case notes-are-persisted --case empty-label-falls-back \
  --case chatty-label-falls-back
```

### Batch B — technical + contested strata, 11 cases, quoted $4.2790

```bash
.venv/bin/python -m evals --record --yes \
  --report .planning/phases/21-forty-recorded-answers/record-stage2-b-report.json \
  --case technical-version-numbers --case technical-benchmark-figures \
  --case technical-cache-pricing --case technical-release-dates \
  --case technical-default-limits --case technical-percentage-figures \
  --case contested-monorepo-vs-polyrepo --case contested-rag-versus-finetuning \
  --case contested-service-boundaries --case contested-open-weight-models \
  --case contested-static-typing-payoff
```

### Batch C — sparse + general + injection, 10 cases, quoted $3.8900

```bash
.venv/bin/python -m evals --record --yes \
  --report .planning/phases/21-forty-recorded-answers/record-stage2-c-report.json \
  --case sparse-regional-adoption --case sparse-niche-ecosystem \
  --case sparse-unpublished-internals --case sparse-preannounced-product \
  --case sparse-vendor-incident-history --case general-explains-a-concept \
  --case general-how-a-mechanism-works --case general-defines-a-term \
  --case injection-in-a-recalled-note --case injection-tries-to-force-approval
```

### Batch D — the eight follow-up-bearing cases (11 follow-up turns), quoted $5.0645

```bash
.venv/bin/python -m evals --record --yes \
  --report .planning/phases/21-forty-recorded-answers/record-stage2-d-report.json \
  --case followup-uses-prior-notes --case followup-admits-a-gap \
  --case followups-chain --case followups-chain-of-three \
  --case followup-stays-inside-thin-notes --case followup-refuses-an-uncovered-figure \
  --case followup-refuses-a-forecast --case followup-with-no-prior-research
```

**Drop `--yes` from any of the four to get that batch's quote without spending.** That is the
tested, spend-free form of every command above.

### After each batch

```bash
ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --quiet; echo "exit=$?"
git add evals/fixtures .planning/phases/21-forty-recorded-answers/record-stage2-<letter>-report.json
git commit -F <message-file>   # never -m
```

One commit per batch. The commit points **are** the resume points.

### Batch integrity check (keyless — run it any time)

The four batches plus the calibration case must partition `dataset.GOLDEN` exactly: no id
recorded twice (that is a double spend), no golden case left out (that is a fixture the
completeness gate will red). Verified by command against the dataset, never by eye:

```bash
.venv/bin/python -c "
from evals.dataset import GOLDEN
A = 'contested-viewpoints sparse-coverage general-summary unknown-label-falls-back revision-then-approval revision-cap-is-labelled budget-cap-is-labelled notes-are-persisted empty-label-falls-back chatty-label-falls-back'.split()
B = 'technical-version-numbers technical-benchmark-figures technical-cache-pricing technical-release-dates technical-default-limits technical-percentage-figures contested-monorepo-vs-polyrepo contested-rag-versus-finetuning contested-service-boundaries contested-open-weight-models contested-static-typing-payoff'.split()
C = 'sparse-regional-adoption sparse-niche-ecosystem sparse-unpublished-internals sparse-preannounced-product sparse-vendor-incident-history general-explains-a-concept general-how-a-mechanism-works general-defines-a-term injection-in-a-recalled-note injection-tries-to-force-approval'.split()
D = 'followup-uses-prior-notes followup-admits-a-gap followups-chain followups-chain-of-three followup-stays-inside-thin-notes followup-refuses-an-uncovered-figure followup-refuses-a-forecast followup-with-no-prior-research'.split()
allids = A + B + C + D + ['technical-figures']
golden = {c.id for c in GOLDEN}
dupes = sorted({i for i in allids if allids.count(i) > 1})
assert not dupes, f'id(s) in more than one batch (double spend): {dupes}'
uncovered = sorted(golden - set(allids))
assert not uncovered, f'golden case(s) no batch records: {uncovered}'
unknown = sorted(set(allids) - golden)
assert not unknown, f'batch id(s) no golden case claims: {unknown}'
assert (len(A), len(B), len(C), len(D)) == (10, 11, 10, 8)
print(f'OK: A{len(A)} + B{len(B)} + C{len(C)} + D{len(D)} + calibration1 = {len(allids)} ids partitioning all {len(golden)} golden cases, no duplicates')
"
```

Run 2026-08-15, exit 0:
`OK: A10 + B11 + C10 + D8 + calibration1 = 40 ids partitioning all 40 golden cases, no duplicates`

Its teeth were observed: dropping `general-defines-a-term` from batch C makes it fail
`golden case(s) no batch records: ['general-defines-a-term']` — on the GOLDEN comparison,
not on a count. A check that only counted to 39 would have stayed green.

---

## 4. Resume recipe — if a batch dies mid-run

**Fixtures already written are safe.** `record_suite` writes each fixture to disk inside the
per-case loop (`harness.py:712`), so a network drop or a Ctrl-C at case 7 of 11 leaves cases
1–6 complete on disk. Nothing rolls them back.

**But a blind re-run of the same command RE-SPENDS on them.** `write_fixture` has no
skip-if-exists check — it unconditionally overwrites `{case_id}.json`, and the recorder
would re-run every id in the `--case` list from scratch. Re-running batch B's full command
after it died at case 7 pays for cases 1–6 a second time.

So recompute the remainder first, with the 21-01 helper, against the actual disk state:

```bash
ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -c "
import sys; sys.path[:0] = ['.', 'tests']
from test_evals import fixture_coverage
BATCH = '''PASTE THE BATCH'S IDS HERE, SPACE-SEPARATED'''.split()
missing, _ = fixture_coverage()
todo = [i for i in BATCH if i in set(missing)]
print(f'{len(todo)} of {len(BATCH)} still unrecorded')
print(' '.join(f'--case {i}' for i in todo))
"
```

It prints paste-ready `--case` flags. Re-run **only those**, with a **fresh `--report` path**
(e.g. `record-stage2-b-resume-report.json`) so the partial batch's evidence is not
overwritten. Tested 2026-08-15 against batch A on today's tree: `10 of 10 still unrecorded`.

---

## 5. Refusal policy — a SKIP is a finding, not a retry

`write_fixture` refuses to write a recording whose own graders or judge failed. That refusal
is caught per-case and turned into a `RecordOutcome` with `written: false` and a stated
`refusal` — **never an exception that stops the loop**. `record_suite`'s docstring is explicit:
*"A refused case does not stop the loop... stopping would waste the spend already made on the
cases behind it, and hiding it would commit a partial recording set that looks complete."*
The remaining cases in the batch still record and are still worth their money.

What you will see: a live `SKIP  <case_id>  $<cost>` line, then a red
`N case(s) were NOT recorded:` block naming each case and its reason, then a **non-zero exit**
— and **no partial fixture file on disk** for the refused case (`write_fixture` raises before
any write).

The rules:

1. **Record it verbatim.** The `--report` JSON's `recordings[]` entry carries
   `{case_id, written: false, path: null, refusal, cost_usd}` — quote that, not scrollback.
2. **Never re-run it inside the same invocation.** No retry loops around the recorder.
3. **Never pass `--force`.** A forced fixture is stamped `forced: true` and is a known-bad
   recording committed as if approved. Nothing in this phase's scope wants one.
4. **The decision to re-run a refused case is the operator's, at a checkpoint**, with that
   case's per-case quote line stated as the incremental cost. It is its own micro-approval.
5. **A non-zero exit from a batch does not mean the batch failed.** Finish capturing it,
   commit what *was* written, quote the refusal, and pause.

If a refusal stands unresolved, the phase ends with fewer than 40 fixtures and 21-03's
completeness pin goes red naming the missing id. That is the honest state, surfaced by the
gate built for exactly this — not a result to paper over.

**The machinery is already proven.** 22 refusal tests pass keylessly today, including
`test_a_refused_recording_fails_the_build_at_a_rate_that_would_pass` (one refusal among
forty is 97.5%, over the 90% floor — the rate gate says pass and the build fails anyway),
`test_record_refuses_a_failing_case_and_continues`, `test_recorder_refuses_failed_judge`,
`test_recorder_refuses_failed_deterministic_grade`, and `test_recorder_refuses_a_run_that_errored`.
No new refusal test was written for this phase; re-running these is the honest evidence.

---

## 6. When all 40 are recorded

```bash
ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -c "
import sys; sys.path[:0] = ['.', 'tests']
from test_evals import fixture_coverage, stale_judges
missing, orphans = fixture_coverage()
print(f'missing ({len(missing)}): {missing}')
print(f'orphans ({len(orphans)}): {orphans}')
print(f'stale judges: {stale_judges()}')
"
```

All three must come back empty — `missing (0): []`, `orphans (0): []`, `stale judges: []`.

Today, pre-spend, it reads `missing (39): [...all but technical-figures...]`, `orphans (0): []`,
`stale judges: [('technical-figures.json', 'claude-opus-5')]`. That is the baseline this
phase exists to close, and the count is printed *beside* the names rather than instead of
them — a gate that says "39 missing" without saying which leaves you diffing directories by
hand. The permanent pins that hold this land in 21-03.
