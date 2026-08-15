# Phase 21: Forty recorded answers - Research

**Researched:** 2026-08-15
**Domain:** Eval-fixture recording (Python CLI, no new libraries) — the `evals/` package's
`--record` leg, the replay leg that grades committed fixtures, and the CI gate that consumes both
**Confidence:** HIGH — every claim below was checked by reading the actual source (`evals/*.py`,
`tests/test_evals.py`, `README.md`, `.github/workflows/ci.yml`, `docs/adr/*`) in this session, not
inferred from training data. No new external package is introduced by this phase, so the package
legitimacy protocol and most of the Standard Stack section are not load-bearing here.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**The paid run is a mid-execution checkpoint — user-ratified today**

- The phase plan includes the record run as a task with a `checkpoint` before any spend.
  Execution PAUSES, shows the fresh quote, and NOTHING runs `--yes` until the user approves
  in that prompt. The recorder's own refuse-without-`--yes` gate stays the enforcement.
- Money context measured at planning (2026-08-15): the live quote is **$17.4812** for
  40 cases / 11 follow-up turns / 91 judge calls, within a cent of the $17.48 quoted
  2026-08-13 — expected, since Sonnet 5's $2/$10 is now permanent and the judge's rates
  are unchanged. Basis: **1 measured, 39 assumed** — assumed tokens dominate.

**The spend is staged: calibrate, re-quote, checkpoint again — user-ratified today**

- Stage 1: record ONE case (~$0.39 quoted), which converts the quote's basis for every
  later case sharing its shape. Stage 2: re-quote the remaining cases from the measured
  basis and present the tighter number at a second checkpoint before the bulk run.
- Two small approvals instead of one blind one. The recorder's own output recommends
  exactly this ("run a one-case calibration first"); the phase makes it the plan rather
  than a suggestion.

**Refusals are findings**

- Per REQ-forty-recorded-answers verbatim: a case the recorder refuses is surfaced in the
  record run's output as a finding, not silently retried or dropped. The SUMMARY carries
  the refusal list (possibly empty) as a result either way.
- No auto-retry loops around the recorder. If a refusal looks transient (network, rate
  limit) the decision to re-run that case is the operator's, at the checkpoint, with the
  incremental cost stated.

### Claude's Discretion (researcher questions first, then planner) — ANSWERED BELOW

- The stale fixture question — answered definitively in Finding 2.
- How keys reach a record run now that PR #28 removed `chat.py`'s import-time
  `load_dotenv()` — answered in Finding 3.
- What "all 40 replayed keylessly on every push" does to the offline eval denominator and to
  `--min-pass-rate` semantics — answered in Finding 6.
- Whether the record run is resumable — answered in Finding 4.

### Deferred Ideas (OUT OF SCOPE)

- README Limitations rewrite — Phase 22, which now has three knowingly-false bullets
  waiting plus the recorded-answers one this phase falsifies.
- Any judge or grader evolution — a NEW milestone; ADR-0012 is settled.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-forty-recorded-answers | All 40 golden cases carry recorded real answers, replayed and graded keylessly on every push. The record run is a paid operator checkpoint (quoted $17.48, re-quoted at run time), sequenced after the judge settles. A case the recorder refuses is surfaced as a finding, not retried into silence. | Findings 1–8 below cover the full recorder/replay mechanics, the stale-fixture ruling, the key-loading gap, calibration/resumability mechanics, refusal surfacing, the denominator consequence, repo mechanics, and the **missing completeness gate** (Finding 6b) the plan must add to make "all 40" actually enforced by CI rather than merely true by convention. |

</phase_requirements>

## Summary

The recorder (`evals/__main__.py --record`), the fixture writer/loader (`evals/fixtures.py`),
and the replay grader (`evals/harness.py::replay_case`) are all already built, tested, and shipped
— this phase's *engineering* surface is small: run the recorder 40 times (staged, per CONTEXT),
commit 40 fixture files, and close one real gap the research found in the shipped code. That gap
is not cosmetic: **nothing in the repo today asserts that every golden case has a committed
fixture.** `evals/__main__.py`'s exit rule (`ok = summary["ok"] and not replay_failures and not
ungraded and not refused`) is all-must-pass over whatever fixtures happen to be on disk — it has
no term comparing the fixture set against `dataset.GOLDEN`. A checkout with 39 of 40 fixtures
passes CI exactly as green as one with 40. REQ-forty-recorded-answers says "all 40 golden cases
carry recorded real answers... on every push" — satisfying that honestly requires a **new**
completeness test, not just 40 new JSON files. This is the single most important planning input
from this research (Finding 6b).

The second load-bearing finding is that the one fixture already in the repo,
`evals/fixtures/technical-figures.json`, is unambiguously stale under the sense that matters:
its `models.judge` field reads `"claude-opus-5"` — the judge Phase 18 (ADR-0012) superseded.
Verdicts are recorded once, under the settled judge; this fixture's two judge verdicts
(`judge_grounding`, `judge_answers_the_question`) were produced by the judge Phase 18 replaced.
It must be re-recorded, not kept. Practically this is free: it does not change the $17.4812
arithmetic (that quote already assumes zero fixtures exist and prices all 40 from scratch — see
Finding 2), and it is the natural pick for the calibration stage CONTEXT ratified, since it is
already the plain, no-followup, no-guardrail case the project used for calibration in Phase 15.

Third: `python -m evals --record --yes` loads no `.env` file anywhere in its call chain. PR #28
removed the only `load_dotenv()` call in the codebase (it lived in `chat.py`'s `main()`, not at
import time, and evals never imported `chat`). The operator must export `ANTHROPIC_API_KEY` and
`VOYAGE_API_KEY` into the shell before invoking the recorder, or it fails or runs keyless in a
confusing way. This is a checkpoint-instruction detail, not a code fix — see Finding 3 for the
exact command.

**Primary recommendation:** stage the 40-case record run in three parts exactly as CONTEXT
ratified — (1) calibrate on `technical-figures` alone via `--case technical-figures`, which also
retires the stale fixture; (2) re-quote and record the remaining 39 in one or more `--case`-scoped
batches (resumable by construction, since each case writes its fixture as soon as it is recorded —
see Finding 4); (3) add the missing completeness gate (a new test asserting `{f.stem for f in
fixture_paths()} == {c.id for c in GOLDEN}`, or equivalent enforcement wired into the CLI's exit
rule) before declaring the requirement met. Update the two now-false counts in `README.md`
("Tests and evals" section, not the Limitations bullet) to state the new denominator honestly.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Recording a real answer (paid, live pipeline + judge) | Local operator CLI (`evals/__main__.py --record`) | — | Runs `graph.app.invoke` directly against a real `anthropic.Anthropic()` client built in the CLI process; never goes through the FastAPI service (`src/research_agent/app.py`), so the service's spend cap / reservation guard (`src/research_agent/limits.py`) is structurally not in this path — confirmed by grep: `limits.py`'s `reserved_run_usd`/`daily_cap_usd`/`check_and_reserve` are referenced nowhere in `evals/harness.py` or `evals/__main__.py`. |
| Committing/loading a fixture (schema, validation, refusal-on-fail) | `evals/fixtures.py` | — | Pure file I/O + validation; no network, no service dependency. |
| Grading a fixture (deterministic + recorded judge verdicts + staleness) | `evals/harness.py::replay_case` | — | Runs entirely off the fixture's own `state` dicts; no client, no memory store, no key. |
| CI gate / exit-code decision | `evals/__main__.py::main` | `.github/workflows/ci.yml:73` (`--min-pass-rate 0.9`) | The CLI computes `ok`; CI merely runs the command and reads its exit code — no gate logic lives in the workflow file itself. |
| Cost preview / quote-vs-actual reporting | `evals/__main__.py::record_preview` (quote) + `evals/harness.py::record_suite`/`RecordOutcome` (actual) | `src/research_agent/usage.py` (rate tables) | The quote and the invoice both resolve through `usage.CallUsage.cost_usd`/`usage.price_for`, so they can never structurally disagree about a rate — only about assumed vs. measured tokens. |
| Completeness enforcement ("all 40 have fixtures") | **Does not exist yet — this phase's gap to close** | `tests/test_evals.py` (new test) or `evals/__main__.py` (new CLI check) | See Finding 6b. Neither tier currently owns this responsibility. |

## Standard Stack

No new external packages. This phase writes data (JSON fixtures) and one new test/gate using the
existing stack: Python 3.14, `pytest`, the already-vendored `anthropic` and `voyageai` SDKs (both
already dependencies — used live only when `--record`/`--live` is passed), and the existing
`evals/` package. `python-dotenv==1.2.2` is present as a dependency (`chat.py`'s optional import)
but is **not** wired into the eval CLI (Finding 3) — this phase does not need to change that; the
operator exports the keys directly. **[VERIFIED: pyproject.toml/egg-info, read this session]**

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Exporting keys manually before `--record` | Wiring `load_dotenv()` into `evals/__main__.py` | Out of scope per CONTEXT (no code change requested for key-loading; the phase's job is to state the working invocation). Also reopens the exact leak PR #28 just closed if done carelessly (import-time side effects) — see Pitfall 3. |
| A per-case `--record --case <id>` loop for the bulk stage | A single `--record --yes` over all 40 at once | The staged/checkpointed plan CONTEXT ratified requires per-case or per-batch control anyway; scoping bulk recording into a few `--case ... --case ...` invocations also buys resumability for free (Finding 4) at zero extra engineering cost. |

## Package Legitimacy Audit

Not applicable. This phase installs no new package in any ecosystem — it invokes the existing
`anthropic` and `voyageai` clients (already present, already used by `--live`) and writes JSON
files. **Packages removed due to [SLOP] verdict:** none. **Packages flagged as suspicious [SUS]:**
none.

## Architecture Patterns

### System Architecture Diagram

```
operator shell (keys exported)
        │
        │  python -m evals --record [--case ID ...] [--yes]
        ▼
┌─────────────────────────────────────────────────────────────┐
│ evals/__main__.py : main()                                  │
│                                                               │
│  1. select(cases)              -- dataset.GOLDEN, filtered   │
│  2. record_preview(cases, existing_fixtures)                 │
│        │  reads usage.price_for() at CALL TIME (not hard-    │
│        │  coded) -- quote re-prices itself automatically     │
│        └──> prints preview; refuses (exit 2) if not --yes,   │
│             BEFORE constructing any API client                │
│  3. (only if --yes) anthropic.Anthropic()  -- reads          │
│     ANTHROPIC_API_KEY from process env directly, no dotenv   │
│  4. G.Judge(client)             -- mandatory for record mode │
└───────────────────────┬───────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ evals/harness.py : record_suite() -> record_case_to_fixture()│
│                                                               │
│  for each case:                                               │
│    run_case(case, capture_state=True)  -- SAME driver as     │
│      the live suite; drives graph.app.invoke directly,       │
│      NOT through the FastAPI service (no spend-cap/          │
│      reservation guard in this path)                          │
│        │                                                       │
│        ├─ per-case fresh InMemoryStore (VoyageEmbedder,       │
│        │  reads VOYAGE_API_KEY from process env)               │
│        ├─ judge.verdict() per JUDGE_GRADERS + per follow-up   │
│        │      stop_reason checked BEFORE content (Phase 18)   │
│        │      refusal -> False, not an exception               │
│        ▼                                                       │
│    F.build_fixture(...) -> F.write_fixture(...)                │
│        │  refuses (raises FixtureError) if ANY grade failed   │
│        │  -- writes fixture file to disk IMMEDIATELY,          │
│        │  per case, inside the loop (resumability: Finding 4) │
│        ▼                                                       │
│    RecordOutcome{written | refusal}  -- collected per case     │
└───────────────────────┬───────────────────────────────────────┘
                         ▼
              evals/fixtures/<case_id>.json   (committed to git)
                         │
                         │  every future push, keyless:
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ evals/__main__.py : main()  (offline mode, no --record)       │
│                                                                 │
│  behavioural leg: run_suite(GOLDEN)  -- ScriptedClient,        │
│    routing/guardrail checks only, rate-governed (>=90%)        │
│                          +                                     │
│  replay leg: _replay_fixtures(fixture_paths())  -- ALL-MUST-   │
│    PASS regardless of rate: grade_fixture_current (staleness), │
│    RECORDED_GRADERS (deterministic), recorded judge verdicts   │
│    replayed as fixed data (judged=False)                       │
│                          │                                     │
│                          ▼                                     │
│  ok = behavioural.ok AND not replay_failures AND not ungraded  │
│       AND not refused   <-- NO term compares fixture set to    │
│                              GOLDEN. Finding 6b: this phase     │
│                              must add one.                      │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

No new files or directories. This phase adds:
```
evals/fixtures/
├── technical-figures.json          # RE-RECORDED (stale judge — Finding 2)
├── contested-viewpoints.json       # NEW
├── ... (37 more, one per evals.dataset.GOLDEN case_id)
└── followups-chain-of-three.json   # NEW — carries 4 turns (1 research + 3 follow-up)
tests/test_evals.py                 # +1 new test: fixture-set completeness (Finding 6b)
README.md                           # counts updated (":200", ":221" — NOT ":286", Phase 22's)
```

### Pattern 1: Fixture schema (quoted verbatim from `evals/fixtures/technical-figures.json`)

**What:** One JSON file per case, holding every turn's full final `AgentState` plus recording
metadata. This IS the schema the planner should treat as canonical — quoted, not paraphrased, per
the in-repo value provenance rule.
**Source:** `evals/fixtures/technical-figures.json:1-11` (top-level keys) and `:86-99` (judge
block shape). **[VERIFIED: evals/fixtures/technical-figures.json:1-11,86-99, read this session]**

```json
{
  "schema_version": 1,
  "case_id": "technical-figures",
  "recorded_at": "2026-08-10T01:30:28+0800",
  "models": {
    "pipeline": "claude-sonnet-5",
    "judge": "claude-opus-5"
  },
  "git_sha": "225b06b",
  "pipeline_cost_usd": 0.242717,
  "turns": [
    {
      "label": "research",
      "state": { "...": "full AgentState dict, ~9KB for this case" },
      "judge": [
        {
          "grader": "judge_grounding",
          "passed": true,
          "detail": "All substantive claims trace to the notes: ...",
          "judged": true
        },
        {
          "grader": "judge_answers_the_question",
          "passed": true,
          "detail": "The report directly answers the question, ...",
          "judged": true
        }
      ]
    }
  ]
}
```

**Note on `models`:** this fixture has **no `"critic"` key** — it predates Phase 16's
independently-configurable critic and is read via `grade_fixture_current`'s documented backfill
(`models.get("critic") or recorded`, `evals/harness.py:399`). Every fixture recorded during this
phase will carry all three roles explicitly (`record_case_to_fixture` at `evals/harness.py:578-582`
always writes `{"pipeline": graph.MODEL, "judge": judge.model, "critic": graph.critic_model()}`),
so the backfill branch stops applying to any fixture this phase produces — including the
re-recorded `technical-figures.json` itself.

**What the loader enforces (`evals/fixtures.py::load_fixture`)** — total, not best-effort:
`schema_version` must equal `1`; `_REQUIRED_KEYS` (`schema_version`, `case_id`, `recorded_at`,
`models`, `git_sha`, `pipeline_cost_usd`, `turns`) must all be present and correctly typed
(`fixtures.py:58-66`); `models` must be non-empty and contain `pipeline` and `judge`
(`fixtures.py:56,278-280`); `turns` must be non-empty and each turn must carry `label`/`state`/
`judge` (`fixtures.py:251-264`). Any violation raises `FixtureError` naming the exact key —
nothing loads as a "partial" fixture.

### Pattern 2: Staged recording via `--case` (calibration → bulk)

**What:** `--record --case <id>` records exactly one case (confirmed by
`tests/test_evals.py:3163`, `test_record_refuses_without_yes`'s use of `--case technical-figures`,
and `cli_record`'s helper at `tests/test_evals.py:3248-3263` which drives the full CLI with a
single `--case`). Repeating `--case` is additive (`argparse` `action="append"`,
`evals/__main__.py:454-459`), so a batch of N specific cases is `--case a --case b --case c ...`.
**Source:** `evals/__main__.py:454-459` (flag definition), `evals/dataset.py:1011` (`select`).

```bash
# Stage 1 — calibration (also re-records the stale fixture, Finding 2)
python -m evals --record --case technical-figures            # quote only, no --yes
python -m evals --record --case technical-figures --yes      # spends ~$0.39 (quoted)

# Stage 2 — re-quote the remaining 39 from the measured basis, at the checkpoint
python -m evals --record --case contested-viewpoints --case sparse-coverage ...  # (39 ids)

# Stage 2 (after approval) — the bulk run, --yes appended
python -m evals --record --case contested-viewpoints --case sparse-coverage ... --yes
```

**When to use:** exactly the shape CONTEXT ratified — one case first, re-quote, then the rest.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Driving the pipeline to capture a fixture | A parallel recording script that calls `graph.app.invoke` directly | `evals.harness.run_case(..., capture_state=True)` via `record_case_to_fixture` | Already the exact driver the live suite uses — budget scoping, per-case memory isolation, follow-up chaining, and error isolation are all correct there by construction; a parallel loop would drift from the shipped graph (explicit design note, `evals/harness.py:275-281`). |
| Checking "is every golden case recorded" | A one-off shell script (`ls evals/fixtures | wc -l`) run manually before each PR | A pytest test comparing `{f.stem for f in fixtures.fixture_paths()}` to `{c.id for c in dataset.GOLDEN}` (or equivalent logic wired into `evals/__main__.py`'s exit rule) | A manual check is not a CI gate — it can be forgotten, and it does not run "on every push" as REQ-forty-recorded-answers requires. This is the single new piece of logic this phase needs (Finding 6b). |
| Pricing the record run | A hardcoded dollar literal | `record_preview()` (`evals/__main__.py:347-427`), which resolves every rate through `usage.price_for()` at call time | Already built to re-price itself automatically when rate tables move (this is exactly the property that made the 2026-08-13 → 2026-08-15 quote drift by less than a cent — the Sonnet 5 rate step became permanent, not a re-quote bug). |

**Key insight:** every mechanism this REQ needs already exists and is tested — except the
completeness gate. Resist the temptation to also touch grading logic, judge wiring, or the golden
dataset; CONTEXT explicitly rules that out ("any change to graders, the judge, the golden cases'
definitions, or recall semantics" is not in this phase).

## Common Pitfalls

### Pitfall 1: Treating `technical-figures.json` as "already done" and skipping it

**What goes wrong:** A plan that records the 39 never-recorded cases and leaves the existing
fixture untouched ships 40 fixtures but one of them (`technical-figures`) carries verdicts from a
superseded judge (`"judge": "claude-opus-5"`, `evals/fixtures/technical-figures.json:7`) —
verdicts Phase 18/ADR-0012 explicitly reopened the register to move away from.
**Why it happens:** the file already exists and already passes `grade_fixture_current` (its
`models.pipeline` still matches `graph.MODEL`, so the *pipeline* staleness gate is silent — that
gate does not compare the judge at all; see `evals/harness.py:383-389`, "Cannot catch: ... The
JUDGE's is recorded and deliberately not checked").
**How to avoid:** re-record `technical-figures` as part of this phase (ideally as the calibration
case — see Pattern 2). No code change needed; the staleness gate correctly has no mechanism to
catch this on its own, by design, so the fix is operational (re-run the recorder), not a code fix.
**Warning signs:** any plan phrase like "39 remaining cases" instead of "40 cases, one of which
re-records an existing stale fixture."

### Pitfall 2: Believing "all 40 recorded" is enforced once the files exist

**What goes wrong:** committing 40 fixture files and declaring the requirement met, when nothing
in CI actually asserts the count. A later PR that accidentally deletes or fails to add one fixture
(e.g., a bad rebase) would still show CI green.
**Why it happens:** the exit rule (`evals/__main__.py:649`, `ok = summary["ok"] and not
replay_failures and not ungraded and not refused`) is all-must-pass over whatever fixtures are
*present*, not a check that the right *set* is present. `ungraded` (`evals/__main__.py:639`)
compares `len(matched) - len(replay_results)` — matched is `fixtures.fixture_paths()` filtered by
`--case` if given, not `dataset.GOLDEN`.
**How to avoid:** add a completeness assertion — either a new pytest test (simplest, keyless,
runs on every push via the existing `pytest -q` CI step) or a check inside `evals/__main__.py`
itself that fails loud when `{fixture case_ids} != {GOLDEN case ids}` (stronger — enforced by the
`python -m evals` gate CI already runs, not merely by `pytest`).
**Warning signs:** a plan whose verification step is "committed 40 files and offline evals still
exit 0" without a step asserting *which* 40.

### Pitfall 3: Re-adding a module-level `load_dotenv()` to make key-loading "convenient"

**What goes wrong:** PR #28 removed `chat.py`'s import-time `load_dotenv()` specifically because
it silently injected the developer's real keys into every keyless test that later imported
`chat` — verified in `tests/test_graph_smoke.py:434-441`
(`test_importing_chat_does_not_mutate_the_environment`). Adding a similar call anywhere at
`evals/` import time (even conditionally) reopens that exact hole for the keyless CI evals step
(`.github/workflows/ci.yml:73`, which explicitly sets `ANTHROPIC_API_KEY: ""` and expects that to
stay empty).
**Why it happens:** the operator-convenience motive is real and CONTEXT explicitly asks the
researcher to "state the exact invocation" rather than to change code.
**How to avoid:** the plan's checkpoint task states the export command in the prompt text (e.g.
`export ANTHROPIC_API_KEY=... VOYAGE_API_KEY=...` or `set -a; source .env; set +a`), and does not
touch `evals/__main__.py`'s import section.
**Warning signs:** any diff touching `evals/__main__.py`'s top-level imports or adding a
`dotenv` import inside `main()`.

### Pitfall 4: Assuming the record run inherits the service's spend cap

**What goes wrong:** treating the $17.4812 quote as bounded by `AGENT_MAX_RUN_COST_USD` or the
daily cap the deployed service enforces via `src/research_agent/limits.py`
(`reserved_run_usd`/`daily_cap_usd`/`RunLimiter.check_and_reserve`), and therefore under-preparing
the checkpoint prompt (e.g. assuming a runaway case would be capped automatically at the service's
$1.00 ceiling).
**Why it happens:** the two mechanisms share a name-adjacent concept (spend limiting) and the
harness *does* use `AGENT_MAX_RUN_COST_USD` for a different purpose — `evals/harness.py:239-258`'s
`_budget` context manager temporarily overrides it for the two guardrail cases in the dataset
(`budget-cap-is-labelled`, `followup-with-no-prior-research`), which is a per-case *test fixture*
override, not the service's admission-control reservation system.
**How to avoid:** confirmed by grep — `limits.py`'s reservation/cap functions are referenced
nowhere in `evals/harness.py` or `evals/__main__.py`. The record run's only spend control is the
quote-then-`--yes` gate; there is no runtime circuit breaker once a case starts running.
**Warning signs:** a plan step that says "the service will stop it if it goes over."

## Code Examples

### Refusal path — what the operator sees, and what remains on disk

**Source:** `evals/fixtures.py:199-211` (`_refuse_failing`), `evals/harness.py:564-587`
(`record_case_to_fixture`'s try/except), `evals/__main__.py:552-564` (`announce_recording`).

```python
# evals/fixtures.py:199-211
def _refuse_failing(case_id: str, result: CaseResult) -> None:
    if result.error:
        raise FixtureError(
            f"refusing to record {case_id!r}: the run errored ({result.error}). "
            "Pass force=True to record it anyway."
        )
    failed = [g.grader for g in result.failures]
    if failed:
        raise FixtureError(
            f"refusing to record {case_id!r}: {', '.join(failed)} failed. "
            "A committed fixture is one the graders and the judge approved; "
            "pass force=True to record it anyway (it will be stamped forced)."
        )
```

A refusal is caught in `record_case_to_fixture` (`evals/harness.py:566-586`) and turned into a
`RecordOutcome` with `path=None`, `refusal=<message>` — **never an exception that stops the loop**
(the docstring is explicit: "A refusal is NOT an exception ... one case among forty, and the
remaining thirty-nine are still worth their money"). The CLI prints it live via
`announce_recording` (`evals/__main__.py:562-564`, `SKIP  <case_id>  $<cost>` then the refusal
text), and again in the closing summary (`evals/__main__.py:675-690`, a red `"N case(s) were NOT
recorded:"` block naming each refused case and its reason). The full structured record is
`report["recordings"]` — a list of `{"case_id", "written", "path", "refusal", "cost_usd"}` dicts
(`RecordOutcome.as_dict`, `evals/harness.py:518-525`) — written to disk when `--report <path>` is
passed. **No partial fixture file is ever left** for a refused case: `write_fixture` either writes
the complete validated JSON or raises before touching disk.

### The quote-vs-actual line the record run prints

**Source:** `evals/__main__.py:662-674`.

```
recorded 40/40 case(s) · previewed $17.4812 · measured pipeline $X.XXXX + 91 judge call(s),
which bill separately and are not metered here
```

This is the SUMMARY's per-stage evidence source CONTEXT's "Specific Ideas" section asks for:
capture this line (or its `--report` JSON equivalent) at each stage — calibration, re-quote,
bulk — rather than re-deriving spend numbers by arithmetic.

## Findings (numbered against the researcher questions in the task)

### Finding 1 — the recorder end to end

Covered fully above (Architecture Patterns, Pattern 1 and 2; Code Examples). One detail worth
isolating: **grading a fixture differs from grading a live answer** in exactly two ways —
(a) the judge verdicts are *replayed as fixed data* (`_recorded_judge_grades`,
`evals/harness.py:428-442`, `judged=False` — "nothing was asked of a model to produce these"), and
(b) an additional deterministic staleness gate runs (`grade_fixture_current`) that has no live-run
equivalent. The `RECORDED_GRADERS`/`RECORDED_FOLLOWUP_GRADERS` registries
(`evals/graders.py:704-713`) are a *separate* set of deterministic quality graders from the live
leg's `DETERMINISTIC_GRADERS`/`FOLLOWUP_GRADERS` — replay runs both the shared deterministic
graders and the recorded-only ones (`evals/harness.py:475-476,480-481`).

### Finding 2 — the stale-fixture question, answered definitively

**`technical-figures.json` must be re-recorded.** Read directly: `evals/fixtures/technical-figures.json:7`
reads `"judge": "claude-opus-5"`. `evals/graders.py:45` reads `DEFAULT_JUDGE_MODEL =
"claude-opus-4-8"` — the Phase 18/ADR-0012 judge. The fixture's two judge verdicts
(`judge_grounding` at `:88-92`, `judge_answers_the_question` at `:94-98`) were therefore produced
by the superseded judge. Per CONTEXT's own framing ("verdicts are recorded once — under the
settled judge, which is the entire reason for the phase ordering"), this fixture is in scope for
re-recording. **Cost consequence: none.** `record_preview` (`evals/__main__.py:373-391`) prices
EVERY case from scratch unless a fixture already exists for it (`fixtures_by_case_id.get(case.id)`
at `:379`) — and the $17.4812 quote at planning time was computed against a checkout with **only**
`technical-figures.json` present, so it already assumed that ONE case would be priced from its
*measured* `pipeline_cost_usd` ($0.242717) rather than from assumed tokens, and the other 39 from
assumed tokens. Re-recording `technical-figures` does not add a 41st case to the arithmetic — it
is one of the 40 already priced in, and it happens to be the one case whose price the quote
already knows precisely (basis line: "1 measured, 39 assumed"). Recording it again produces a
fresh fixture with a new `recorded_at` and a `critic` key it previously lacked (Finding-2 note
above) — it does not change the total.

### Finding 3 — how keys reach the recorder

**Neither `evals/__main__.py` nor anything it imports calls `load_dotenv()` anywhere.** Confirmed
by grep across `evals/`, `src/`, and the import chain: the only `load_dotenv()` call in the
codebase is `src/research_agent/chat.py:163`, inside `chat.py`'s `main()` function — never at
import time, and `evals/__main__.py` never imports `research_agent.chat`. `evals/__main__.py:528`
constructs `anthropic.Anthropic()` with no arguments, which means the Anthropic SDK reads
`ANTHROPIC_API_KEY` from `os.environ` itself (standard SDK behaviour, not something this repo
wires). The live memory factory (`evals/harness.py:811-818`, `live_memory_factory`) builds a bare
`InMemoryStore()`, which defaults its embedder to `VoyageEmbedder()`
(`src/research_agent/memory.py:298,434,588`), which reads `VOYAGE_API_KEY` from the environment at
first use (`memory.py:154`, `voyageai.Client()`). **Both keys are required and neither is loaded
from a file by anything in this path.** The exact working invocation:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export VOYAGE_API_KEY="pa-..."
python -m evals --record --case technical-figures            # quote-only sanity check first
python -m evals --record --case technical-figures --yes      # spends
```

or, if the operator keeps a `.env` file (as `chat.py`'s REPL does):

```bash
set -a; source .env; set +a
python -m evals --record --case technical-figures --yes
```

If the operator runs `--record --yes` with no keys exported, `anthropic.Anthropic()` raises
immediately with the SDK's own "no api_key" error (there is no silent keyless fallback in the
record path — offline mode uses `offline_client_factory`/`offline_memory_factory` instead, and
`--record` always takes the `if args.live or args.record:` branch at `evals/__main__.py:524` which
unconditionally builds the real client). The checkpoint task instructions must therefore lead with
the export step, or the first thing the operator sees after approving the quote is an SDK auth
error, not a graceful refusal.

### Finding 4 — calibration mechanics

`--record --case <id>` records exactly one case — confirmed structurally (`select()` filters
`GOLDEN` by the `--case` list, `evals/dataset.py:1011`) and by test
(`tests/test_evals.py:3163,3248-3263`). After it lands, the next `--record` quote (run without
`--case`, over all 40) will show a tighter basis for `technical-figures` specifically — its line
in the preview switches from `"assumed tokens at <date> rates"` to `"measured pipeline $0.XXXX
(fixture <date>) + assumed judge"` (`evals/__main__.py:380-388`) — but **not** for the other 39,
since `record_preview` only substitutes the measured basis case-by-case, per
`fixtures_by_case_id.get(case.id)` (`:379`); it does not extrapolate one measured case's shape onto
others. CONTEXT's "converts the quote's basis for every later case sharing its shape" describes
the *comment-level calibration constants* (`ASSUMED_RESEARCH_INPUT_TOKENS` etc.,
`evals/__main__.py:260-266`) getting hand-corrected by whoever reads the calibration's actual
measured tokens — those constants are **not** re-derived automatically; they are named constants
maintained by comment, and the file's own header states the correction rule ("raise what the
measurement exceeded, keep what it did not", `:222`). If the operator wants the *preview text* to
reflect a broadly tighter number after calibration, editing those constants is a manual step the
plan should call out, distinct from the fixture-basis substitution that happens automatically.

**Best calibration pick:** `technical-figures` — no follow-ups (`case.followups == ()`), no
`budget_usd` override (`evals/dataset.py:197-208`, no `budget_usd=` kwarg), and it is the same
case Phase 15 originally calibrated against, so its already-known measured shape
(`evals/__main__.py:217-224`, "CALIBRATED 2026-08-10 against the first real recording") gives the
plan a sanity check: a second recording should land close to the first ($0.2427) if the pipeline
is otherwise unchanged. It is also the case that must be re-recorded regardless (Finding 2), so
using it for calibration spends no extra money beyond what the phase needed to spend anyway.

**Resumability: yes, at the file level; no, at the command level.** `record_case_to_fixture`
writes each fixture to disk **inside the per-case loop** in `record_suite`
(`evals/harness.py:711-724`, the loop calls `record_case_to_fixture` then immediately appends the
outcome) — there is no batching or deferred write. If the process dies at case 23 (network drop,
Ctrl-C, laptop sleep), cases 1–22's fixture files are already on disk and safe; nothing rolls them
back. **But** a naive re-run of the same `--record --yes` command with no `--case` filter would
select all 40 cases again via `select(None)` (`evals/dataset.py:1011`, `select` with `ids=None`
returns the full `GOLDEN` tuple) and **re-record cases 1–22 a second time**, overwriting their
fixtures and re-spending on them — `write_fixture` (`evals/fixtures.py:159-196`) has no
"skip if exists" check; it unconditionally writes to `target_dir / f"{fixture['case_id']}.json"`.
The re-quote at Stage 2's checkpoint (Finding 4's premise) already partially covers this, since
recording `technical-figures` first will show it priced from its measured fixture on the next
preview — but the *bulk stage itself* should be planned as one or more `--case`-scoped batches
(e.g. chunks of 8–10 explicit case IDs) rather than a single unqualified `--record --yes` over all
40, specifically so a mid-batch failure can be resumed by re-running only the unrecorded remainder
(`ls evals/fixtures/*.json` diffed against `dataset.GOLDEN` ids tells the operator exactly which
IDs remain). This is a planning decision (task granularity), not a code change.

### Finding 5 — refusal surfacing

Covered fully in Code Examples above. Summary: refusal is caught per-case in
`record_case_to_fixture`'s `try`/`except F.FixtureError` (`evals/harness.py:566-586`), surfaced
live via `announce_recording`'s `SKIP` line (`evals/__main__.py:562-564`), aggregated in the
closing summary's red `"N case(s) were NOT recorded:"` block (`evals/__main__.py:675-690`), and
available structurally in `report["recordings"]` (list of dicts with `written`/`refusal` fields)
when `--report <path>.json` is passed (`evals/__main__.py:720-723`). **A refused case leaves no
partial fixture file** — `write_fixture` either succeeds completely or raises before any disk
write (`fixtures.py:172-196`, the `_refuse_failing` check happens before `json.dumps`/`path.write_text`).
The plan should have the checkpoint task pass `--report <path>.json` so the SUMMARY can quote the
refusal list (or its absence) as structured evidence rather than terminal-scrollback prose.

### Finding 6 — the keyless-CI consequence (denominator)

Today: `report["cases"]` = 40 behavioural (offline, `ScriptedClient`) + N replayed fixtures
(currently 1) = **41**, matching `README.md:200,221` ("40 golden cases + every recording" / "a run
now grades 41 cases"). After 40 fixtures exist, assuming 1:1 (one fixture per golden case, no
duplication): `report["cases"]` = 40 behavioural + 40 replayed = **80**. **The denominator is
additive, not a replacement** — the behavioural leg (routing/guardrail checks against the
*scripted* dataset answer) and the replay leg (quality checks against the *real recorded* answer)
grade the same case_id for structurally different reasons and are suffixed differently
(`<id>` vs `<id>@recorded`, `evals/harness.py:458`) — this is deliberate design, not accidental
double-counting, and is exactly the "one shared denominator" the existing test at
`tests/test_evals.py:2258` names in its comment. **CI runtime:** the replay leg is pure
in-process file I/O and grading with no network calls (no client, no memory store, per the
`replay_case` docstring) — 40 replays add negligible wall-clock time versus the 40 offline
behavioural cases, which already run the real (scripted) graph. **`--min-pass-rate 0.9`
semantics:** unaffected in principle — the replay leg is already **all-must-pass regardless of
rate** (`evals/__main__.py:626-632`, explicit design comment: "Left there, every hard replay gate
would be decorative"), so growing from 1 to 40 replayed cases does not change how the rate
threshold applies to them; it changes only how many all-must-pass checks exist. **Are the graders
deterministic over fixtures, so the gate does not get flakier over time?** Yes, by construction and
by explicit design note: `RECORDED_GRADERS`/`RECORDED_FOLLOWUP_GRADERS` and the recorded judge
verdicts are pure functions of the fixture's own stored `state` dict — replay never re-calls a
model (`harness.py`'s replay section header, `:342-350`: "No client, no memory, no network, no
key, no spend"), and `grade_fixture_current` explicitly avoids the calendar
(`harness.py:356-358`: "age prints in the caveat but never grades, because a grader that fails on
the calendar makes the same commit pass in August and fail in October"). **40 dated recordings do
not make the gate flakier over time** — the only way a replay case goes red later is a genuine
tree change (the pipeline model, the critic model, or the dataset's case shape moving), which is
the staleness gate working as designed, not flakiness. **DEC-13 honest denominators:** the phase
must update `README.md:200,221` from "41 cases" language to the new count once fixtures land (NOT
`:286`, the Limitations bullet, which Phase 22 owns per CONTEXT and 18-VERIFICATION's explicit
note that it must stay byte-identical).

### Finding 6b — the completeness gap (new, not asked directly but load-bearing)

No code anywhere — not `evals/__main__.py`'s exit rule, not `evals/harness.py`, not any test in
`tests/test_evals.py` — asserts that the set of committed fixture `case_id`s equals
`{c.id for c in dataset.GOLDEN}`. Verified by reading `evals/__main__.py:626-650` (the full exit
rule) and grepping `tests/test_evals.py` for any set-comparison against `GOLDEN`'s ids (none
found; the closest hits are `assert len(GOLDEN) >= 40` at `:145`, a lower-bound sanity check on
the *dataset*, unrelated to fixture coverage). Today this is invisible because the gap between
"cases with fixtures" (1) and "golden cases" (40) is large and README already states the honest
number of recordings prose-side. Once this phase ships fixtures for all 40 and the numbers happen
to match, that gap becomes silent — a future PR that drops a fixture (bad merge, accidental
deletion, a case ID rename in the dataset that orphans its fixture per `evals/__main__.py:108-124`)
would not fail CI, because the `ungraded` check only compares "matched paths" to "graded results,"
never to "how many *should* exist." **This phase should add exactly one new gate** — the simplest
form is a pytest test:

```python
def test_every_golden_case_has_a_committed_fixture():
    """REQ-forty-recorded-answers: 'all 40' means CI enforces it, not merely that
    someone once ran the recorder 40 times."""
    recorded = {p.stem for p in F.fixture_paths()}
    golden = {c.id for c in GOLDEN}
    missing = golden - recorded
    assert not missing, f"{len(missing)} golden case(s) have no recorded fixture: {sorted(missing)}"
```

This runs keylessly under the existing `pytest -q` CI step (no change to `ci.yml` needed) and
directly encodes "all 40 golden cases carry recorded real answers... on every push." A stronger
(but not required) alternative is wiring the same check into `evals/__main__.py`'s exit rule so
`python -m evals` itself fails loud, not just the test suite — the planner should decide based on
whether REQ-forty-recorded-answers's "graded keylessly on every push" is read as "the test suite
enforces it" (sufficient — `pytest -q` already runs on every push per `ci.yml`) or "the eval CLI
itself enforces it" (stronger, mirrors the existing `ungraded`/`refused` all-must-pass pattern).

### Finding 7 — repo mechanics

**Fixture size:** the one existing fixture (`technical-figures.json`, no follow-ups) is **10,097
bytes**. Cases with follow-up turns will be proportionally larger — `followups-chain-of-three`
carries 4 turns (1 research + 3 follow-ups) and could reasonably run 2.5–4× a single-turn fixture
before hitting `fixtures.py`'s own `WARN_BYTES = 100_000` / `MAX_BYTES = 250_000` limits
(`fixtures.py:71-72`), well within bounds for any case in the dataset (research-turn states run "a
few tens of KB" per the module docstring, `fixtures.py:68`). **Total estimate for 40 fixtures:**
32 single-turn cases × ~10KB + 8 multi-turn cases (the follow-up-bearing ones,
`evals/dataset.py`'s `followups=` entries) averaging perhaps 20–35KB each ≈ 320KB + 200KB ≈
**roughly 500KB–600KB added to the repo.** No `.gitignore` entry excludes `evals/fixtures/`
(confirmed: `.gitignore` only lists `evals-report.json`), and no `.gitattributes` file exists in
the repo at all — **no LFS concern** at this size; git handles half a megabyte of JSON trivially.
**`tests/test_evals.py` fixture-count pins:** none tie a literal count to the *real* committed
directory. The one place `len(GOLDEN) + 1` appears (`tests/test_evals.py:2258`,
`test_replay_is_automatic_and_keyless`) is scoped to a `tmp_path` fixtures directory the test
itself populates with exactly one fixture via the `committed()` helper — it is not reading the
real `evals/fixtures/` directory and needs **no edit** for this phase. (This directly answers
whether a `== 1` becomes `== 40` anywhere: no, because the existing tests are all built against
synthetic `tmp_path` fixture sets, not the shipped directory — the gap this leaves is exactly
Finding 6b.)

### Finding 8 — Validation Architecture

See the dedicated section below.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Fixture size for the 8 follow-up-bearing cases will land in the 20–35KB range (used to estimate total repo growth at ~500–600KB) | Finding 7 | Low — even a 4x miss stays far under `MAX_BYTES` per file and is a trivial total repo-size delta either way; not a planning blocker. |
| A2 | The stronger completeness-gate option (wiring the check into `evals/__main__.py`'s exit rule rather than only a pytest test) is left as a planner decision rather than mandated | Finding 6b | Low — either satisfies REQ-forty-recorded-answers's "keylessly on every push" reading since `pytest -q` already runs on every push per `ci.yml`; the choice affects only which command surfaces the failure, not whether CI catches it. |

## Open Questions

1. **Exact per-batch chunking for the bulk 39-case stage.** *(RESOLVED by P-05, plan
   21-02: four batches by case family, follow-ups last — 10+11+10+8.)*
   - What we know: the recorder is resumable at the file level (Finding 4), and `--case` accepts
     repeats, so any chunking scheme works mechanically.
   - What's unclear: whether the plan should use one `--case`-enumerated command for all 39
     remaining cases, or split into smaller batches (e.g. by dataset category —
     `technical-*`, `contested-*`, `sparse-*`, `general-*`, `followup*`) for easier
     mid-run inspection at the checkpoint.
   - Recommendation: leave to the planner; either satisfies CONTEXT's staging requirement. A
     per-category split makes a partial-failure re-run trivially expressible ("re-run the
     `followup-*` batch") without needing to diff `evals/fixtures/` against `dataset.GOLDEN` by hand.

2. **Whether the new completeness gate belongs in `tests/test_evals.py` or `evals/__main__.py`.**
   *(RESOLVED by P-01, plan 21-01: pytest repo-state pin; the CLI's zero-fixtures-is-legal
   property is load-bearing shipped design pinned by existing tests, so the exit rule stays.)*
   - What we know: both satisfy "graded keylessly on every push" per `ci.yml`'s existing steps.
   - What's unclear: which reading of REQ-forty-recorded-answers's "replayed and graded keylessly
     on every push" the planner should treat as binding — the requirement text does not
     distinguish "the eval CLI enforces it" from "the test suite enforces it."
   - Recommendation: implement the pytest form at minimum (Finding 6b's example); consider the
     stronger `evals/__main__.py` wiring as a stretch task if scope allows, since it mirrors the
     existing `ungraded`/`refused` all-must-pass pattern the codebase already uses for structurally
     identical "silent gap" risks.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `ANTHROPIC_API_KEY` (exported, not dotenv-loaded) | `--record --yes` (all 40 cases + judge) | Operator-provided at checkpoint time — not present in the research session | — | None — this is the paid checkpoint itself; no fallback exists by design (CONTEXT: "nothing runs `--yes` until the user approves") |
| `VOYAGE_API_KEY` (exported, not dotenv-loaded) | `--record --yes` (live embeddings via `VoyageEmbedder`) | Same as above | — | None — `live_memory_factory` has no keyless path; offline mode uses a different factory entirely |
| `anthropic` Python SDK | judge + pipeline live calls | ✓ already a project dependency, used by `--live` today | (pinned in `pyproject.toml`, not re-verified this session — no version change needed) | — |
| `voyageai` Python SDK | live embeddings | ✓ already a project dependency | same | — |
| git | fixture `git_sha()` metadata | ✓ (repo is git-managed; `git rev-parse --short HEAD` works from this session's context) | — | `fixtures.py:84-100` already falls back to `"unknown"` if git is unavailable — non-blocking either way |

**Missing dependencies with no fallback:** the two API keys — expected, since the paid checkpoint
is the point where the operator supplies them; this is a plan-time gate, not a code gap.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (existing, `tests/test_evals.py` already covers the recorder/fixture/replay machinery extensively) |
| Config file | `pyproject.toml` (`pytest` section — pre-existing, no change needed) |
| Quick run command | `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -k evals -q` |
| Full suite command | `ANTHROPIC_API_KEY="" .venv/bin/pytest -q` (keyless, ~30s per README) |
| Eval CLI command (separate from pytest, also keyless) | `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --report evals-report.json --min-pass-rate 0.9` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-forty-recorded-answers (fixture completeness) | Every golden case has a committed, loadable fixture | unit | `pytest tests/test_evals.py::test_every_golden_case_has_a_committed_fixture -x` | ❌ Wave 0 — new test, per Finding 6b |
| REQ-forty-recorded-answers (keyless replay, all-must-pass) | All 40 fixtures grade green under the existing replay leg | integration (keyless CLI) | `python -m evals --min-pass-rate 0.9` (exit 0 required) | ✅ mechanism exists (`evals/__main__.py`); needs the 40 fixture files themselves |
| REQ-forty-recorded-answers (stale-fixture handling) | `technical-figures.json` re-recorded under the settled judge, not merely kept | manual-checkpoint | `--record --case technical-figures --yes` then `jq .models.judge evals/fixtures/technical-figures.json` == `"claude-opus-4-8"` | ❌ requires the paid checkpoint to have run |
| REQ-forty-recorded-answers (refusals as findings) | A refused case appears in `report["recordings"]` with `written: false` and a stated `refusal`, and the run still exits based on whether ANY refusal occurred | unit (existing) | `pytest tests/test_evals.py -k refus -q` | ✅ `test_a_refused_recording_fails_the_build_at_a_rate_that_would_pass` and neighbours already cover this mechanism; no new test needed unless the plan changes refusal wording |
| DEC-13 honest denominators | README's "41 cases" language becomes the true post-recording count | manual/doc | `grep -n "cases" README.md` around lines 199-223, cross-checked against a real `python -m evals` run's printed `N/N cases` line | ❌ doc update, not currently automated — recommend a simple grep-gate test asserting the printed count in README matches a freshly-computed `len(GOLDEN) * 2` (or the actual formula chosen) |

### Sampling Rate

- **Per task commit (each `--case` batch recorded):** re-run `python -m evals --min-pass-rate 0.9`
  keylessly to confirm the newly-committed fixtures replay green before moving to the next batch.
- **Per wave merge:** full `pytest -q` (keyless) + `python -m evals --report evals-report.json`.
- **Phase gate:** both green, plus the new completeness test (Finding 6b) green, before
  `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_evals.py::test_every_golden_case_has_a_committed_fixture` (or equivalent) —
  covers REQ-forty-recorded-answers's "all 40" clause structurally, not just by convention
  (Finding 6b).
- [ ] No fixture or conftest changes needed — `tests/test_evals.py` already imports
  `fixtures as F` and `GOLDEN` from `evals.dataset`, so the new test needs no new imports.
- [ ] Framework install: none — `pytest` already present.

**Mutation to prove the replay gate (per the task's Q8):** delete one committed fixture (e.g.
`evals/fixtures/contested-viewpoints.json`) after this phase ships all 40 →
`test_every_golden_case_has_a_committed_fixture` should go **RED** naming the missing case_id, and
(if the stronger CLI-level gate is also implemented) `python -m evals` should also fail loud rather
than silently reporting fewer replayed cases as still green.

**Mutation to prove refusal surfacing:** force a grader to fail during a scoped `--record --case`
run against a fake/offline harness path (as the existing test suite already does at
`tests/test_evals.py:3282` `test_a_refused_recording_fails_the_build_at_a_rate_that_would_pass`) —
this mutation already exists and passes; no new mutation needed unless the plan changes the
refusal-reporting code.

**The paid run itself — Manual-Only checkpoint, evidence it must leave:**
- The console output of each `--record --yes` invocation (quote line, per-case `REC`/`SKIP` lines,
  the closing "recorded N/N case(s) · previewed $X · measured pipeline $Y" line) — capture this
  verbatim in the phase SUMMARY, per stage.
- `--report <path>.json` from at least the final bulk-stage invocation, so `recordings[]` and
  `summary.cost_usd` are machine-checkable evidence rather than transcript-only.
- The final `git diff --stat -- evals/fixtures/` showing exactly 40 files changed/added (39 new +
  1 re-recorded), which verification can check without re-spending a cent.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | The recorder is a local operator CLI invocation, not a user-facing auth surface; no new endpoint or session is introduced. |
| V3 Session Management | No | Same reasoning — no session state is created or consumed by this phase. |
| V4 Access Control | No | No new access-controlled resource. |
| V5 Input Validation | Marginal — already handled | `evals/fixtures.py::load_fixture` already validates every fixture totally (schema version, required keys, types, non-empty turns) and raises `FixtureError` naming the exact violation rather than degrading gracefully — this is the existing control and this phase does not need to add to it, only produce fixtures that pass it. |
| V6 Cryptography | No | No cryptographic operation is introduced; API keys are read from process env by the vendor SDKs exactly as `--live` already does today. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Real API keys leaking into a keyless CI run via an accidental `load_dotenv()`/import-time env mutation | Information Disclosure | Already the exact failure PR #28 fixed for `chat.py` (Pitfall 3). This phase must not reintroduce it in `evals/__main__.py`. |
| A committed fixture carrying operator-identifiable data (real notes recalled from the operator's own persistent store) | Information Disclosure | Already mitigated structurally: `_per_case_memory` (`evals/harness.py:591-629`) raises `RuntimeError` if the memory factory ever hands back the process's own store or reuses a store across cases — verified present and unchanged by this phase's scope. |
| A hand-edited or `--force`d fixture silently graded as if it were judge-approved | Tampering | `write_fixture` stamps `forced: true` when `force=True` is used (`fixtures.py:172-175`), and replay's recorded-judge-grade path (`_recorded_judge_grades`) will show a red for any grade that is actually `false` in the file — a red replay of a `forced` fixture is the intended signal, not a bug to suppress. |

## Sources

### Primary (HIGH confidence — read directly this session)

- `evals/__main__.py` (full file, 729 lines) — CLI flags, `record_preview`, exit rule, replay wiring
- `evals/harness.py` (full file, 818 lines) — `run_case`, `replay_case`, `record_suite`,
  `record_case_to_fixture`, `grade_fixture_current`, `_state_judge_critic_relation`
- `evals/fixtures.py` (full file, 298 lines) — schema, `load_fixture`, `write_fixture`, `_refuse_failing`
- `evals/graders.py` (lines 1-60, 690-870) — `JUDGE_MODEL`/`DEFAULT_JUDGE_MODEL`,
  `RECORDED_GRADERS`, `Judge.verdict`, `stop_reason` guard
- `evals/dataset.py` (grep + `GOLDEN` count verified live via `python -c "from evals.dataset import GOLDEN"`) — 40 cases, 11 follow-up turns, 8 follow-up-bearing case IDs, guardrail `budget_usd` overrides
- `evals/fixtures/technical-figures.json` (full file, quoted verbatim) — the only existing fixture, its stale `judge` field
- `tests/test_evals.py` (targeted reads: lines 88-272, 1378-1391, 2080-2140, 2220-2379, 3130-3300) —
  fixture-count test scoping, `--case`/`--yes`/`--force` CLI tests, refusal tests, staleness gate tests
- `.github/workflows/ci.yml` (full file) — `--min-pass-rate 0.9`, keyless env vars, no dotenv anywhere
- `src/research_agent/chat.py:140-180` — the removed-then-relocated `load_dotenv()` call
- `tests/test_graph_smoke.py:434-460` — the regression test proving `import research_agent.chat` no longer mutates env
- `src/research_agent/memory.py:1-160,290-300,420-440,580-590` — `VoyageEmbedder`, `VOYAGE_API_KEY` requirement, `InMemoryStore` default embedder
- `src/research_agent/limits.py` (grep for `reserved_run_usd`/`daily_cap_usd`/`check_and_reserve`) —
  confirmed absent from `evals/harness.py`/`evals/__main__.py`
- `src/research_agent/usage.py` (grep for `claude-opus-4-8`/`claude-sonnet-5` price rows) — price
  table entries backing the quote arithmetic
- `README.md:194-229,280-291` — "Tests and evals" section (editable) vs. Limitations `:286` (Phase 22's, untouched)
- `.planning/phases/18-independent-eval-judge/18-VERIFICATION.md` (full file) — confirms ADR-0012,
  the settled judge, and that `README.md:285`/`:286` was verified untouched by Phase 18
- `.planning/phases/21-forty-recorded-answers/21-CONTEXT.md` — locked decisions and discretion areas
- `.planning/REQUIREMENTS.md` — REQ-forty-recorded-answers verbatim text and traceability table
- git log (`ccbc7b2 Merge pull request #28 from future-beat/fix/chat-dotenv-import-leak`) — confirms PR #28's identity and date-adjacent placement in history

### Secondary (MEDIUM confidence)

None used — every claim above traces to a primary source read in this session.

### Tertiary (LOW confidence)

None.

## Metadata

**Confidence breakdown:**
- Recorder/fixture/replay mechanics: HIGH — every code path cited was read in full this session, and cross-checked against the existing test suite's own assertions about that code.
- Stale-fixture ruling: HIGH — the fixture's `judge` field and `graders.py`'s `DEFAULT_JUDGE_MODEL` were both read directly and quoted verbatim; the conclusion follows deductively.
- Key-loading mechanics: HIGH — confirmed by grep across the entire `evals/`+`src/` tree for `dotenv`/`load_dotenv`, plus a direct read of `chat.py`'s relocated call and its regression test.
- Denominator/CI-runtime claims: HIGH for the arithmetic (read `evals/__main__.py`'s report-assembly code directly); MEDIUM for the CI-runtime estimate (no benchmark was run this session — reasoned from the code's structure: no network calls in replay).
- Completeness-gap finding (6b): HIGH — an actual grep across the entire `evals/`+`tests/` surface for any such check, confirmed absent.
- Repo-size estimate: MEDIUM — extrapolated from one real fixture's measured size (10,097 bytes) plus the known turn-count distribution of the dataset; not independently benchmarked against any of the 39 not-yet-recorded cases.

**Research date:** 2026-08-15
**Valid until:** this research is tied to the exact state of `evals/` at commit-time of this
session; it should be treated as valid until the recorder, fixture schema, or judge wiring changes
again (no fixed day-count — this is code-state-bound, not calendar-bound, matching the project's
own stated preference for staleness gates that do not depend on the clock).
