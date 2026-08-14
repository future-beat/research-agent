---
phase: 18-independent-eval-judge
plan: 04
subsystem: evals/docs
tags: [premise-inversion, operator-wording, measured-baseline-greps, whole-file-pass, phase-close, deferred-manual]
status: complete

# Dependency graph
requires:
  - phase: 18-independent-eval-judge
    plan: "01"
    provides: "the judge on claude-opus-4-8 — the flip that inverted this plan's premise"
  - phase: 18-independent-eval-judge
    plan: "02"
    provides: "the refusal guard, and the second-fake lesson"
  - phase: 18-independent-eval-judge
    plan: "03"
    provides: "ADR-0012 on disk and the 0005->0010->0012 chain test, which is what lets the collision line point at 0012 without creating a dangling pointer"
provides:
  - "evals/harness.py _state_judge_critic_relation: mechanism untouched, premise re-derived, pointer at ADR-0012"
  - "graders.DEFAULT_JUDGE_MODEL — the shipped default as a name, because JUDGE_MODEL is what THIS process resolved"
  - "test_judge_critic_collision_warning_is_silent_at_the_shipped_defaults — the twin proving a production-shaped record run is now silent"
  - "evals/graders.py, docs/OPERATIONS.md, docs/DESIGN.md: every judge==critic surface re-derived except README :285"
  - "docs/OPERATIONS.md: EVAL_JUDGE_MODEL documented as an evals-CLI knob, deliberately not a service env var"
  - "README test count measured and corrected at both sites (740 -> 749)"
  - "the phase gate, and the record of what Phase 18 deliberately did not do"
affects: [21, 22]

# Tech tracking
tech-stack:
  added: []  # zero packages installed
  patterns:
    - "When a premise inverts, the mechanism usually survives — separate the two before editing. The equality check, the once-per-run placement and the None guard were all still correct; only the docstring and the printed sentence were false."
    - "A wording gate must red on a stale premise that carries a CORRECT citation. Pinning only the ADR string tests the footnote, not the sentence."
    - "A constant that names a DEFAULT cannot be the constant that resolved the ENV. `JUDGE_MODEL` is what this process got; `DEFAULT_JUDGE_MODEL` is what ships — the note has to report one while naming the other."
    - "Correct a stale number by measuring, or by deleting the claim. The one thing not to do is derive it from the delta of another measurement — that is the plan-stated-arithmetic failure with extra steps."

key-files:
  created: []
  modified:
    - evals/harness.py
    - evals/graders.py
    - tests/test_evals.py
    - docs/OPERATIONS.md
    - docs/DESIGN.md
    - README.md
    - .planning/PROJECT.md
    - .planning/phases/18-independent-eval-judge/18-VALIDATION.md
    - .planning/phases/18-independent-eval-judge/deferred-items.md

key-decisions:
  - "The wording test's non-vacuity needed a THIRD mutation the plan did not specify, and it is the one that justifies the token set. Mutations 1 and 2 (fire unconditionally; pointer back to ADR-0010) both red, as predicted — but neither shows the new tokens doing any work, because mutation 2 reds on the ADR string alone. Probe 3 restores the stale 'This is the deployed configuration and it is accepted' sentence while leaving the pointer correctly at ADR-0012: the wording test still reds, on `shipped default`. Without that probe the honest claim would only have been 'the line cites ADR-0012', not 'the line says something true'."
  - "The plan's `:1896` anchor for the boundary-docstring test is wrong; it is at `:2074`. Fourth wave in this phase family where a plan-stated line anchor had drifted — located by name, verified green, and recorded rather than silently followed."
  - "`.planning/PROJECT.md`'s with-Postgres count was DELETED rather than corrected, and that is the honest move. The pair read '737 keyless / 801 with Postgres'. The keyless half is measured (749). The Postgres half is not measurable here — no Docker daemon, no running server — and `801 + 12 = 813` is precisely the plan-stated-arithmetic move this project has caught seven times. The sentence now states measured facts (749 keyless, 67 Postgres-gated skips, 816 collected) and stops quoting a number nobody has run."
  - "The three `.planning/codebase/` maps asserting a `claude-opus-5` judge were logged, not fixed. They are `/gsd-map-codebase` output — a dated snapshot regenerated wholesale — and patching three lines would leave the rest equally stale while hiding that it needs a re-map. `STACK.md:98` was ALREADY stale entering Phase 18 ('the only place Opus appears' died in Phase 16), so this is drift the sweep surfaced rather than drift the phase created."
  - "The `evals/__main__.py` console-announce gap that 18-02 deferred was NOT fixed, deliberately. The plan does not assign it; it is a change to operator-facing announcements, which this project treats as a deliberate deliverable rather than a side effect (16-02); and `test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines` pins its ABSENCE, so fixing it reds a test and gets made on purpose. Stated here rather than done silently, per the execution fence."

# Metrics
duration: 38min
completed: 2026-08-14
---

# Phase 18 Plan 04: The collision line's inverted premise, and the phase gate Summary

**One-liner:** The operator-facing collision line kept its mechanism and lost its premise —
it is now silent on a production-shaped record run (proven by a new twin), fires once on an
operator-created collision, and states what those verdicts stop being able to claim while
pointing at ADR-0012; every other judge==critic surface is re-derived, README's count is
measured rather than asserted, and Phase 18 closes at 749/67 with 41/41 offline evals.

## Measured baselines and deltas

| Gate | Before (post-18-03) | After | Delta |
|------|---------------------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:cacheprovider`) | 748 passed / 67 skipped | **749 passed / 67 skipped**, exit 0 | **+1 passed, +0 skipped** — the silence twin, and nothing else |
| `tests/test_evals.py` | 178 passed | **179 passed** | +1 (four collision tests re-derived in place, not duplicated) |
| Offline evals (`ANTHROPIC_API_KEY="" .venv/bin/python -m evals`) | 41/41 exit 0 | **41/41 (100% vs 90% required)**, real `$?` = 0 | unchanged — the phase stales nothing |
| `.venv/bin/ruff check .` and `… src tests evals` | clean | clean, both forms | — |
| `judge and the critic share` in `docs/` | **1** (`OPERATIONS.md:803`) | **0** | the measured 1 → 0 |
| `in production the judge and the critic run` in `evals/` | **1** (`graders.py:17`) | **0** | the measured 1 → 0 |
| `README.md:15` / `:199` test count | 740 (both, stale) | **749** (both, measured) | corrected from a run |

**Phase delta, every test accounted for:** 740 → **749** is **+9** — 18-01 +2, 18-02 +5,
18-03 +1, 18-04 +1. **Skips are 67 at all five measurements**, and all 67 are Postgres-gated
(66 `DATABASE_URL is not set`, 1 `REQUIRE_POSTGRES is not set`), verified by skip reason at
phase close. No test was quietly disabled to make a gate green.

## What shipped

### Task 1 — `2f213a3`, the line re-derived

The mechanism is **untouched**: the None guard, the `judge.model != critic` early return and
the once-per-run placement before the loop all survive (18-RESEARCH Finding 3 — logic
survives, premise inverts). What changed is the docstring and the printed sentence.

The line now names the shared model, says what colliding verdicts stop being able to claim
(independence of the critic's model — what one waves through the other is likelier to wave
through), states that the **shipped default separates them** and names it, attributes the
pairing to the operator rather than to a mistake, and points at **ADR-0012**.

`graders.DEFAULT_JUDGE_MODEL` is new and load-bearing. `JUDGE_MODEL` is what *this process*
resolved, so an operator who exported `EVAL_JUDGE_MODEL` has already moved it — and the note's
whole content is reporting a non-default configuration while naming the default.

Tests: the new twin `test_judge_critic_collision_warning_is_silent_at_the_shipped_defaults`
drives `FakeJudge(model=G.JUDGE_MODEL)` against `CRITIC_MODEL=claude-opus-5` and asserts no
line, plus a non-vacuity assertion so it cannot silently stop describing a production-shaped
run. The fire case arranges its collision through `FakeJudge`'s model — `Judge.__init__` binds
`JUDGE_MODEL` at import, so an env-var monkeypatch would prove nothing (pitfall 4) — and its
docstring was rewritten honestly: this IS a contrived configuration now. The wording test keeps
all six fault words and retires `accepted`/`deployed` for `shipped default`,
`G.DEFAULT_JUDGE_MODEL` (derived from the constant) and `operator`.

### Task 2 — `7a1f9f4`, the doc surfaces

Baselines measured **immediately before editing**, both at 1, both 0 after.

- **`evals/graders.py` module docstring** — the surviving half is kept verbatim in substance
  (a judge on the writer's own model inherits the blind spots it exists to find); the inverted
  half is re-derived. A verdict is now independent of the writer **and** of the critic's model
  *identity* — explicitly **not** its *family*, carrying ADR-0012's own honesty rather than
  softening it. Pointer moved to ADR-0012.
- **`docs/OPERATIONS.md`** — the record-mode paragraph split in two. The staleness sentences
  stay (still true) and now say out loud what the gate compares: pipeline and critic, never the
  judge. The collision sentence became conditional on an operator-created collision, worded as
  a property statement. One line documents `EVAL_JUDGE_MODEL` as the evals-CLI override —
  deliberately **not** in the `:645` service env table, `fly.toml` or `.env.example` (Open
  Question 3, taken minimally; both files verified to carry no such key).
- **`docs/DESIGN.md`** — trailer extended to 0005 → 0010 (Phase 16) → 0012 (Phase 18). The
  paragraph above stays the argument as it stood; what is new is that the judge no longer runs
  on Opus 5 at all.
- **`README.md`** — the suite was run, reported 749, and both sites were edited from that
  number. Never from arithmetic.

**Whole-file passes with nothing found, stated rather than left silent** (pitfall 7 — the grep
locates neighbourhoods, it does not enumerate the sentences):

| File | Read | Found |
|------|------|-------|
| `evals/__main__.py` | entire (729 lines) | **Nothing.** Every reference is to `G.JUDGE_MODEL`/`G.JUDGE_GRADERS`; the preview comments discuss the critic's *rate* against the writer's and assert no relation between judge and critic |
| `docs/adr/README.md` | entire, re-read post-18-03 | **Nothing.** Its one shared-model mention (`:101`) is ADR-0005's historical premise inside the *Reading a superseded record* prose — correct as written |
| `docs/OPERATIONS.md` § Configuration + § `CRITIC_MODEL` | `:615`–`:838` | The env table documents `CRITIC_MODEL` only; correct, and left that way |
| `README.md` | entire (297 lines) | Two stale counts (fixed); `:32`/`:47` phase-log bullets historical and true as written (left, per the 16-03 convention); `:21` stack line names no judge; `:285` untouched |

## Mutation probes — each observed red, then reverted

**Every probe below was run in THIS session against the shipping tree**, not inherited from
Task 1's commit message. The house rule is that a prior wave's claim is a claim to check.

### Probe 1 — `_state_judge_critic_relation` prints unconditionally

```
FAILED tests/test_evals.py::test_judge_critic_collision_warning_is_silent_at_the_shipped_defaults
FAILED tests/test_evals.py::test_judge_critic_collision_warning_is_silent_when_they_differ
2 failed, 4 passed, 173 deselected
```

Both silence tests red — the new twin and the pre-existing one.

### Probe 2 — pointer reverted to ADR-0010

```
>       assert "ADR-0012" in err
E       AssertionError: assert 'ADR-0012' in 'note: … recorded in ADR-0010.\n'
FAILED tests/test_evals.py::test_judge_critic_collision_warning_fires_once_per_run
FAILED tests/test_evals.py::test_judge_critic_collision_warning_states_a_fact_not_a_fault
```

### Probe 3 — the one the plan did not specify, and the one that earns the token set

Restore the stale *"This is the deployed configuration and it is accepted"* sentence while
leaving the pointer **correctly** at ADR-0012:

```
E       AssertionError: assert 'shipped default' in 'note: … this is the deployed
        configuration and it is accepted, recorded in adr-0012.\n'
FAILED tests/test_evals.py::test_judge_critic_collision_warning_states_a_fact_not_a_fault
1 failed, 5 passed
```

**Without this probe the honest claim would only have been "the line cites ADR-0012."** Probes
1 and 2 red on the mechanism and the citation; neither shows the new tokens doing any work. A
wording gate that only pins the footnote would pass a sentence whose every factual claim is
false, provided it ended with the right ADR number. That is the failure this probe closes.

Tree verified clean of all three (`git status --short` empty).

## The phase gate

```
ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:cacheprovider
  -> 749 passed, 67 skipped, exit 0

ANTHROPIC_API_KEY="" .venv/bin/python -m evals
  -> PASS  41/41 cases (100% vs 90% required)
     $2.3440 · 0.1s
     REAL EXIT CODE: 0

.venv/bin/ruff check .              -> All checks passed!
.venv/bin/ruff check src tests evals -> All checks passed!
```

## What this phase deliberately did not do — the five statements

**1. The judge flip does not stale the committed fixture, and here is the reason rather than
the folklore.** `grade_fixture_current` compares `models.get("pipeline")` against `graph.MODEL`
and `models.get("critic") or pipeline` against `graph.critic_model()`. **The judge role is
recorded and deliberately never compared** — its Cannot-catch paragraph says so, and
`test_the_replay_model_gate_states_its_claim_boundary` pins that boundary. Verified in the code
this session, not restated from 18-01. **The plan cites this test at `:1896`; it is at `:2074`.**
`evals/fixtures/technical-figures.json:7` still carries `"judge": "claude-opus-5"` — fixed
replay data recording which model produced those verdicts on 2026-08-10, not a comparison
input, and correct as written. 41/41 exit 0 at phase close is the phase-level proof.

**2. `README.md:285` still says the judge shares the critic's model — a deliberate transient.**
Phase 22 deletes that bullet; deleting it here would strand Phase 22 with nothing to do and
break the milestone's own sequencing. So between now and then the README's Limitations list
contradicts the tree **on purpose**, and this is the record of it. Every *other* doc surface
now agrees with the tree — verified by a broad sweep, not just the two anchored greps.

**3. A real Opus 4.8 judge verdict has never round-tripped. Deferred to Phase 21, not silent.**
Every judge path in this phase is exercised through fakes (`FakeJudge`, `FakeJudgeClient`,
`RefusingJudgeClient`, `RecordingFakeClient._Response`), which is what makes the suite keyless
and free — and exactly why it cannot speak to the live shape: whether Opus 4.8 returns the
expected verdict JSON, and whether its refusal classifiers behave as 18-02's guard assumes. The
one-verdict probe costs **~$0.06** at the assumed 4K-in/1.5K-out leg (both constants labelled
UNMEASURED in `evals/__main__.py`). Phase 21's record run is the next paid judge exercise.

**4. Nothing deploys this phase.** The evals are an operator-invoked CLI and are not in the
production image (`src/` layout keeps `evals/` outside the package entirely). `fly.toml`
carries no `EVAL_JUDGE_MODEL` — verified, along with `.env.example` — and `CRITIC_MODEL` did
not move. Nothing live changes.

**5. The consolidated mutation ledger** — thirteen mutations across four waves, plus three
honest greens with their reasons and one gate found decorative — is in `18-VALIDATION.md` at
the sign-off block rather than duplicated here.

## Deviations from plan

### [Rule 2 — a gate that would have been decorative] A third mutation, beyond the two specified

Detailed above. The plan specified two probes; both passed and neither exercised the new
required tokens. Probe 3 was added because a wording test is the deliverable of this task, and
"reds when the citation is wrong" is a much weaker property than "reds when the sentence is
false." Recorded rather than folded in silently.

### [Rule 1 — a false claim in a shipped artifact] The OPERATIONS ADR link was written wrong and caught before commit

The first draft of the collision paragraph linked
`[ADR-0012](../docs/adr/0012-…md)` — a path that resolves outside the repo from
`docs/OPERATIONS.md`. The file's own convention is `adr/…` (`:449` links ADR-0008 that way).
Caught by grepping the file's existing links rather than by assuming, and corrected before the
commit. A dangling pointer in operator-facing documentation is the exact failure 16-03 built
the chain test to prevent, arriving through a relative path instead of a missing record.

### [out of scope, logged not fixed] The codebase maps still describe a `claude-opus-5` judge

`.planning/codebase/STACK.md:98`, `INTEGRATIONS.md:131` and `TESTING.md:382` all assert the
judge's model as current fact, and all three are stale. Not fixed: they are
`/gsd-map-codebase` output, regenerated wholesale rather than hand-patched, and they are
`.planning/` state rather than a shipped doc surface. **`STACK.md:98` was already stale
entering Phase 18** — "this is the only place Opus appears" died in Phase 16 when production
pinned the critic to Opus 5 — so this is drift the sweep surfaced, not drift the phase created.
Logged in `deferred-items.md` with a candidate owner.

### [correction, not arithmetic] PROJECT.md's with-Postgres count was removed rather than derived

`PROJECT.md:31` read "737 keyless / 801 with Postgres". The keyless half is measured and
corrected to 749. The Postgres half could not be measured here (no Docker daemon, no running
server; standing one up to produce a single number is outside a doc-correction plan). Deriving
`801 + 12 = 813` is the plan-stated-arithmetic move this project has now caught seven times, so
the sentence was rewritten to state what was measured — 749 keyless, 67 Postgres-gated skips,
816 collected — and to stop quoting a second number nobody has run. Logged with its owner.

### [execution fence honoured, stated explicitly] The `evals/__main__.py` announce gap

18-02 deferred the fact that record mode's console prints grader names and not the DECLINED
detail. **Not fixed here, and the reasoning is stated rather than the silence left:** this plan
does not assign it; changing an operator-facing announcement is a deliberate deliverable in
this project (16-02), not a side effect of a docs pass; and
`test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines` pins its
**absence**, so a later fix reds a test and gets made on purpose. It stays in
`deferred-items.md` with Phase 21 as candidate owner.

### [not a deviation, stated to be explicit] What was not touched

`README.md:285` (Phase 22's), `README.md:32`/`:47` (historical phase-log bullets, true as
written), the critic, `fly.toml [env]`, `.env.example`, `evals/fixtures/`, `evals/__main__.py`
and `evals/fixtures.py` — zero lines each. No packages installed. The collision *mechanism* in
`_state_judge_critic_relation` is byte-identical to what 18-03 left.

## Success criteria, measured

| Criterion | Evidence |
|-----------|----------|
| A production-shaped record run prints no collision line | The silence twin, green; probe 1 is its red |
| An operator-created collision prints one honest line pointing at a record that exists | Fire case: exactly 1 line for 2 cases, names ADR-0012; the record's existence and status held by 18-03's chain test, extended not duplicated |
| The wording states a fact, not a fault | Six fault words forbidden; three new fact tokens required; probe 3 shows they gate independently of the citation |
| No surface outside README :285 asserts judge == critic | Both anchored greps 1 → 0, plus a broad sweep whose only shipped-tree hits are :285, historical prose and the contrived-collision test |
| README's count matches the measured post-phase count | Suite run → 749 → both sites edited |
| ROADMAP SC-1 … SC-4 all hold with a measured gate | SC-1 the flip + the fly.toml-anchored independence pin (18-01); SC-2 the refusal guard, probed red alone (18-02); SC-3 ADR-0012 with the chain test (18-03); SC-4 the price row, red under deletion (18-01) |

## Threat register — dispositions discharged

| Threat ID | Disposition | Discharged by |
|-----------|-------------|---------------|
| T-18-08 (repudiation, collision line wording) | mitigate | Token-pinned tests: six fault words forbidden, three new facts required, ADR-0012 pointer whose resolution is held by the chain test. Probes 1–3 each observed red; probe 3 specifically shows the fact tokens gate without the citation |
| T-18-09 (repudiation, doc surfaces) | mitigate | Measured-baseline greps 1 → 0 (non-vacuity from the measured nonzero baseline, the 14-03 rule) plus four whole-file passes with findings recorded, including the two that found nothing |
| T-18-SC (tampering, package installs) | accept | Zero packages installed this phase |

## Self-Check: PASSED

- `evals/harness.py` `_state_judge_critic_relation` at `:632`, message pointing at ADR-0012 at
  `:676`. Present, and byte-identical to its committed state after three reverted mutations.
- `evals/graders.py` — `DEFAULT_JUDGE_MODEL` at `:38`(pre-edit)/`:45`(post-edit), module
  docstring re-derived. Present.
- `tests/test_evals.py` — the silence twin at `:2807`, five collision tests total, 179 passing.
- `docs/OPERATIONS.md` (`:797`–`:823`), `docs/DESIGN.md` (`:76`), `README.md` (`:15`, `:199`) —
  present and modified as claimed; `README.md:285` verified unmodified.
- `.planning/phases/18-independent-eval-judge/18-04-SUMMARY.md` — this file.
- Commits `2f213a3` and `7a1f9f4` exist on `gsd/phase-18-independent-eval-judge`.
- Working tree clean after every mutation probe (`git status --short` empty).
