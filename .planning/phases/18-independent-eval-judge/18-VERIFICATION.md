---
phase: 18-independent-eval-judge
verified: 2026-08-14T02:21:41Z
status: passed
score: 4/4 roadmap success criteria verified
method: goal-backward — every criterion re-proven by a mutation performed and observed by the verifier, then reverted
verifier_mutations: 7  # 6 of the ledger's 13 reproduced independently, plus 1 the ledger does not carry
overrides_applied: 0
re_verification: false

# The measured gates, re-run by the verifier rather than read from a SUMMARY
gates:
  full_suite: "749 passed / 67 skipped, exit 0, 27.45s, ANTHROPIC_API_KEY=''"
  offline_evals: "PASS 41/41 cases (100% vs 90% required), real $? = 0"
  ruff: "All checks passed! (`.venv/bin/ruff check .`)"
  working_tree: "clean at start and at end — every mutation reverted"

# Not gaps. Recorded so a later phase inherits the fact, not the silence.
human_verification:
  - test: "A real `claude-opus-4-8` judge verdict round-trips: the live response shape parses, and a live refusal carries `stop_reason=\"refusal\"` as 18-02's guard assumes"
    expected: "One paid judge call returns the verdict JSON the schema declares; a refused call reaches the recorder's failed-graders branch, not the run-errored one"
    why_human: "Every judge path in this phase is fake-driven (FakeJudge, FakeJudgeClient, RefusingJudgeClient, RecordingFakeClient._Response). That is what makes the suite keyless and free, and exactly why it cannot speak to the live shape. Costs ~$0.06."
    owner: "Phase 21's record run — RECORDED, not silent (ROADMAP:234-237, 18-VALIDATION Manual-Only, 18-04-SUMMARY statement 3). Verified present in all three."

# Non-blocking. Neither is one of the four criteria; neither is a new user-facing limitation.
warnings:
  - finding: "`.planning/REQUIREMENTS.md` was never updated at phase close"
    evidence: "REQ-judge-independent-of-critic is still `- [ ]` at :30 and `Pending` in the traceability table at :96, while ROADMAP:140 marks Phase 18 `[x]` and ROADMAP:231 says COMPLETE. `git diff c00980b..HEAD --stat` does not list REQUIREMENTS.md at all."
    why_it_counts: "The project's own v1.1 convention flips it at phase close — `git show a61897a -- .planning/REQUIREMENTS.md` is a phase-close commit doing exactly that (`- [ ] REQ-offline-eval-quality` → `- [x]`). No Phase 18 plan declared it as a deliverable, so this is convention drift rather than a broken commitment."
    fix: "One line in REQUIREMENTS.md:30 and one cell at :96, in the next phase's or the milestone-close commit."
  - finding: "Two of the three stale `.planning/codebase/` map sites were staled BY this phase"
    evidence: "`INTEGRATIONS.md:131` ('`EVAL_JUDGE_MODEL` (default `claude-opus-5`)') and `TESTING.md:382` (the literal `os.environ.get(\"EVAL_JUDGE_MODEL\", \"claude-opus-5\")`) — both verified stale against the tree. `STACK.md:98` was already stale entering the phase (Phase 16 pinned the production critic to Opus 5, killing 'the only place Opus appears'), so the phase's claim that this is drift the sweep surfaced is only two-thirds true."
    why_it_counts: "Generated `/gsd-map-codebase` output and `.planning/` state, not a shipped doc surface — so it is not a README limitation. Logged in deferred-items.md with a candidate owner, so it is recorded rather than silent."
    fix: "A `/gsd-map-codebase` re-run, or Phase 22's doc pass."

# Documentation nits found by the verifier. Neither changes a verdict.
notes:
  - "18-VALIDATION row 18-04.T1 says 'the collision family is now five tests'. `-k collision` collects SIX — the sixth, `test_judge_critic_collision_warning_leaves_the_judgeless_refusal_intact` at tests/test_evals.py:3021, dates to Phase 16 (`git log -S`, commit 53ee909) and lives in a different section. The five-in-the-section count is right; the family count is off by one."
  - "ADR-0012:50 quotes the code as `JUDGE_MODEL = os.environ.get(\"EVAL_JUDGE_MODEL\", \"claude-opus-4-8\")`. The shipped line is `os.environ.get(\"EVAL_JUDGE_MODEL\", DEFAULT_JUDGE_MODEL)` (graders.py:46), with the literal one line above. Semantically identical; the quote is a paraphrase of a line the same phase deliberately split in two."
---

# Phase 18: Independent eval judge — Verification Report

**Phase Goal:** The eval judge grades every case on a model independent of the critic, and a
judge refusal surfaces as a finding rather than a misleading parse error.

**Verified:** 2026-08-14T02:21:41Z
**Status:** passed — 4/4 roadmap success criteria
**Method:** goal-backward. SUMMARY.md and 18-VALIDATION.md were read as *claims*. Every
criterion below was re-proven by a mutation the verifier performed, observed red, and reverted.
Working tree confirmed clean before the first mutation and after the last.

---

## Goal Achievement

### Success Criteria (the ROADMAP contract)

| # | Criterion | Status | Evidence the verifier observed |
|---|-----------|--------|--------------------------------|
| 1 | `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8` — not the critic's model, stronger than the writer, zero cost change | ✓ VERIFIED | `evals/graders.py:45-46`. Resolved at runtime: judge `claude-opus-4-8`, writer `graph.MODEL = claude-sonnet-5`, deployed critic `fly.toml:58 CRITIC_MODEL = 'claude-opus-5'`. Price identity exact to every token class (below). **Mutation 1** proved the pin. |
| 2 | A judge response the safety classifier refuses is surfaced as a graded finding, because `graders.py` checks `stop_reason` before reading content | ✓ VERIFIED | `evals/graders.py:783-784` — `if response.stop_reason == "refusal": return False, _refusal_detail(response)`, placed **before** the `"".join(b.text ...)` content join at :785. **Mutation 3** proved it reaches the recorder's failed-graders branch. |
| 3 | ADR-0012 exists, records the supersession of ADR-0010, and states plainly that this reopens the reversal register v1.1 closed as spent | ✓ VERIFIED | `docs/adr/0012-judge-independent-of-the-critic.md` (209 lines). Status line :3. Register reopening stated twice, in its own paragraph (:34-43) and as an accepted consequence (:163-166). **Mutations 4, 5, 6** proved the chain and the index. |
| 4 | The price table carries an Opus 4.8 row, so a judge run's cost is reported rather than landing on `pricing_unknown` | ✓ VERIFIED | `src/research_agent/usage.py:105-107`. Rendered live: `record_preview(GOLDEN)` quotes **$17.5125** with a priced judge leg and `_rate_line` returns `claude-opus-4-8 $5/$25 per MTok`. **Mutation 2** proved the row. |

**Score: 4/4.** No criterion rests on symbol presence alone — each has a mutation behind it.

---

## Mutations Performed by the Verifier

Seven. Six reproduce ledger entries; the seventh is not in the ledger. Each was applied,
observed, and reverted; `git status --porcelain` returned empty after the last.

| # | Ledger | Mutation | Observed | Verdict |
|---|--------|----------|----------|---------|
| 1 | #1 | `DEFAULT_JUDGE_MODEL` → `"claude-opus-5"` | `test_the_judge_runs_on_a_different_model_than_the_deployed_critic` **RED**: `assert 'claude-opus-5' != 'claude-opus-5'`. `..._than_the_pipeline` **GREEN** (1 failed, 1 passed). | Reproduced exactly |
| 1b | — | *(same mutation, wider blast radius the ledger does not claim)* | `test_judge_critic_collision_warning_is_silent_at_the_shipped_defaults` **also RED** — a production-shaped run printed the collision note. The silent twin is load-bearing on the default, not just on the mechanism. | Stronger than claimed |
| 2 | #2 | Delete the `claude-opus-4-8` PRICES row | `test_the_eval_judges_model_is_priced` **RED** (`UnknownModelPricing: No price for 'claude-opus-4-8' on 2026-08-14`); `test_record_preview_requotes_itself_when_the_rate_window_flips` **RED**; `test_record_preview_states_its_basis_and_uncertainty` **RED**. | Reproduced, +1 red the ledger does not name |
| 2b | #2's correction | *(same mutation)* | `test_record_preview_lands_in_the_researched_range` **stayed GREEN** — `1 passed`. | **The ledger's self-correction is honest.** The row that says a predicted red did not occur and was "corrected rather than banked" is itself correct. |
| 3 | #4, #5 | Delete the two-line `stop_reason == "refusal"` guard | **4 failed / 175 passed** in `tests/test_evals.py`: both refusal tests, `test_a_judge_refusal_reaches_the_recorders_failed_graders_branch`, `test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines`. The recorder message reverts to `refusing to record 'technical-figures': the run errored (ValueError: Judge returned unparseable verdict: '')` — the misdiagnosis, reproduced. `test_judge_raises_on_an_unparseable_verdict` **stayed GREEN**. | Reproduced; the ledger's "2 failed / 173 passed" was measured mid-wave 2, before the recorder tests landed |
| 4 | #10 | `mv docs/adr/0012-….md /tmp` | **BOTH RED, on different grounds**: chain test — `the record trail names ADR-0012; …is not on disk`; index checker — `index points at a missing record`. | Reproduced exactly |
| 5 | #9 | Revert ADR-0010's status line to `Accepted — supersedes ADR-0005` | Chain test **RED**: `assert 'Superseded by ADR-0012' in '# ADR-0010 — …'`. | Reproduced exactly |
| 6 | #8 | Flip `docs/adr/README.md`'s 0009 row to `Superseded`, prose untouched | Checker **RED**: `the table says 7 of 12 records are Accepted; the counting prose does not say so`. Meanwhile `grep -c "Eight of the twelve records"` = **1** and `grep -c "Four supersessions"` = **1** — the literal-grep gates stay green under the mutation that matters. | Reproduced exactly, including the negative half |
| 7 | **not in the ledger** | Delete `CRITIC_MODEL` from `fly.toml [env]` | Pin **fails loud**, not silently green: `fly.toml's [env] no longer pins CRITIC_MODEL. The deployed critic falls back to the writer's model and this pin has nothing to compare the judge against`. | New — closes the pin's last vacuity hole |

---

## The Independence Pin: Meaningful, Not Vacuous

The pin compares against `fly.toml`'s parsed `[env] CRITIC_MODEL` rather than
`graph.critic_model()`. Three properties were checked, not assumed:

1. **It discriminates.** Mutation 1: flip the default back and it reds on the real values
   (`'claude-opus-5' != 'claude-opus-5'`). The writer-independence pin
   (`test_the_judge_runs_on_a_different_model_than_the_pipeline`) stayed green under the same
   mutation — confirming it never guarded this axis.
2. **The alternative would have been vacuous.** In a keyless suite `CRITIC_MODEL` is unset, so
   `graph.critic_model()` returns `graph.MODEL` = `claude-sonnet-5`. Comparing the judge
   against that is green forever and says nothing about the deployed configuration — verified
   at runtime, not read from the docstring.
3. **It cannot pass on a missing value.** Mutation 7: with the key removed the pin asserts on
   `deployed_critic` being falsy *before* the comparison, so `!= None` never gets a chance to
   report independence from nothing. This is the failure mode Fly's UI regeneration would have
   produced, and it is closed.

**Verdict: meaningful.** The pin reads the file that states what production runs, fails loud on
absence, and reds on the flip.

---

## The Refusal Guard: Reaches the Branch, Not Merely Present

The claim under audit was that the guard reaches the recorder's **failed-graders** branch
rather than only appearing to. Confirmed structurally and by mutation:

- `evals/fixtures.py:199-211` has two branches that blame different actors — `result.error` →
  *"the run errored"*; `result.failures` → *"…failed"* naming the graders.
- `test_a_judge_refusal_reaches_the_recorders_failed_graders_branch` (`tests/test_evals.py:2649`)
  drives the **real** `G.Judge` over `RefusingJudgeClient` through `record_suite`, and asserts
  the reason's **content**: `"judge_grounding" in recording["refusal"]`,
  `"the run errored" not in recording["refusal"]`, `case["error"] == ""`, and every failed grade
  detail starting `the judge DECLINED to grade` with `stop_reason=refusal` in it.
- Wave 2's claim that a second fake response object was required is confirmed in the tree:
  `RecordingFakeClient` (:3192) is also handed to the real `Judge.verdict`, and both it and
  `FakeJudgeClient` (:575) now carry `stop_reason`/`stop_details`.
- Mutation 3 shows the branch actually swaps: without the guard the same test reds on
  `assert 'judge_grounding' in "refusing to record 'technical-figures': the run errored
  (ValueError: Judge returned unparseable verdict: '')"`. `written=False` and the absent file
  are identical under both branches — which is precisely why the content assertion is the gate
  and a reason-blind one would have gated nothing.

---

## ADR-0012 Against CONTEXT's Four Requirements

| CONTEXT requirement | Status | Where |
|---|---|---|
| Supersedes ONLY the judge==critic acceptance | ✓ | :12-19 names the superseded position and quotes ADR-0010 verbatim; :21-26 fences the other — *"Nothing in this record is a judgement about the critic"*; :137-138 lists "The critic above the writer" under *Carried forward*. Confirmed in the tree: `CRITIC_MODEL` unmoved in `fly.toml`, and the Phase 18 diff touches neither `fly.toml` nor `src/research_agent/graph.py`. |
| States the reversal register reopens | ✓ | :34-43 as its own headed paragraph (*"This record reopens that register, deliberately, and says so here rather than leaving it to be inferred from a table that quietly grew a row"*), and again at :163-166 as an accepted consequence. `docs/adr/README.md:52-58` carries the matching prose. |
| States the Opus-4.8-is-the-critic's-family residual honestly | ✓ | :54-71, a headed section *"The residual, in this record's own voice"*: *"A skeptic who argues that two models of one family share training lineage, and therefore blind spots, still has his argument after this record, and nothing measured in this project refutes it."* And the exact sentence at :69-71 — independent of the writer's model, independent of the critic's model, **not** independent of the critic's family. Not papered over. |
| Attributes the Fable-5 decline to the user | ✓ | :73-91. *"presented at milestone questioning on 2026-08-13 and declined by the project owner"*, with the three reasons — and :85-91 separates them: reason 1 (2× price) is verified in this repo's price table; reasons 2 and 3 (retention, hotter classifiers) are *"recorded as the decision context he stated, not as measurements this project made."* |

ADR-0010's status line is a **one-line diff** (`git show bc7cf40 --stat`: 1 insertion, 1 deletion),
per the 16-02 records-are-history convention. Trap #2 closed: ADR-0012, 0010's status line and
the extended chain test all landed in one commit.

---

## Independently Re-Run Gates

| Gate | Command | Result |
|------|---------|--------|
| Full suite, keyless | `ANTHROPIC_API_KEY="" .venv/bin/pytest` | **749 passed, 67 skipped**, exit 0, 27.45s |
| Offline evals | `ANTHROPIC_API_KEY="" .venv/bin/python -m evals` | **PASS 41/41 (100% vs 90% required)**, real `$?` = **0** |
| Lint | `.venv/bin/ruff check .` | All checks passed! |
| Price identity | `usage.price_for(...)` for both models | `claude-opus-4-8` and `claude-opus-5` both **5.0 / 6.25 / 0.50 / 25.0** — zero cost change is exact, not approximate |
| Record preview | `record_preview(D.GOLDEN, {})` | **$17.5125**, judge leg priced, no `UNPRICED` marker |
| Prose gate 1 | `grep -rc "judge and the critic share" docs/` | **0** across all of `docs/` |
| Prose gate 2 | `grep -rn "in production the judge and the critic run" evals/` | **0** |
| README `:285` | `git diff c00980b..HEAD -- README.md` | Bullet **untouched**. The only README changes are `:15`, `:40`, `:199`. The deliberate contradiction is intact and Phase 22 still has something to delete. |
| README test count | `README.md:15`, `:199` | **749** — matches the count measured above, not inherited |
| Traps closed in one commit | `git show 06140a4 --stat`, `git show bc7cf40 --stat` | Row + flip together; ADR-0012 + 0010 status + chain test together |
| Blast radius | `git diff c00980b..HEAD --stat` | `evals/__main__.py`, `evals/fixtures.py`, `fly.toml`, `.env.example`, `evals/fixtures/` — **all absent**. The phase changed nothing it said it would not. |

---

## The Milestone Acceptance Bar — Explicit Ruling

> **"No new bullet is born."** (`.planning/REQUIREMENTS.md:14`)

**RULING: the bar HOLDS. Phase 18 created no new README limitation.** Three candidates were
examined; each is ruled below rather than waved through.

### 1. The `evals/__main__.py` console-announce gap — **an internal nicety, not a new limitation**

The gap: in record mode `main` wires `announce_recording` (which prints the `FixtureError` —
grader names) and never calls `announce` (which prints `grade.detail`), so a declining judge
reads to the operator as `judge_grounding … failed` while the word DECLINED travels only in
`--report` JSON.

Ruled a nicety, on four grounds the verifier checked rather than accepted:

1. **It is not new.** `evals/__main__.py` has **zero lines changed** in this phase
   (`git diff c00980b..HEAD --stat`). The `announce_recording`/`announce` split predates
   Phase 18 entirely. The phase did not create this surface's shape.
2. **The phase strictly improved this surface.** The verifier observed the pre-Phase-18
   behaviour directly under mutation 3: the console said *"the run errored (ValueError: Judge
   returned unparseable verdict: '')"* — blaming a successful, paid pipeline run for the
   judge's decision. It now names `judge_grounding`, which is **true**. A change that replaces
   a false statement with an incomplete one has not born a limitation; it has closed a worse one.
3. **It is not a capability gap a README bullet would list.** The README's Limitations section
   describes what the *system* cannot claim (verdict independence, one-of-forty recordings,
   cost approximation). This is the verbosity of one console line in a paid, operator-invoked
   CLI mode, where the complete information is already in the report the same command writes.
4. **It is pinned as an absence, not merely noted.**
   `test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines` asserts
   `"DECLINED" not in out` (`tests/test_evals.py:2742`), so a later fix reds a test and gets
   made on purpose — the 16-02 discipline for operator-facing wording.

**No README bullet is warranted. Correctly deferred.**

### 2. The same-family residual — **a narrowing of an existing limitation, and it has a record**

Opus 4.8 and Opus 5 are relatives, so family-correlation survives. This is not new: the
identical residual already stood in the tree on the *writer* axis, stated by ADR-0010 (*"Opus 5
and Sonnet 5 are the same vendor and the same family, so even judge ≠ writer buys family-level
independence and no more"*) and it was never a README bullet then. Phase 18 moves the judge
strictly toward independence and states the remainder in ADR-0012's own voice rather than
under the word *independent* in its title. The milestone's declared pattern for a residual
that cannot close honestly is *"they get records"* — it has one. **No bullet born.**

### 3. No real `claude-opus-4-8` verdict has ever round-tripped — **real, subsumed, and recorded**

This is the one genuinely new epistemic gap: the shipped judge model has produced no verdict in
this project, whereas the previous judge had (`evals/fixtures/technical-figures.json:7` records
`"judge": "claude-opus-5"` from 2026-08-10). It is subsumed by the standing bullet *"Only one of
forty answers is recorded"*, which Phase 21 closes and which will produce the first real Opus
4.8 verdicts by roadmap sequencing. **Verified RECORDED, not silent, in all three places the
phase claims:** `ROADMAP.md:234-237`, `18-VALIDATION.md` Manual-Only table, and `18-04-SUMMARY.md`
statement 3 — each carrying the ~$0.06 probe cost and Phase 21 as owner. Carried forward as the
single human-verification item above. **No bullet born.**

---

## Requirements Coverage

| Requirement | Source | Status | Evidence |
|---|---|---|---|
| REQ-judge-independent-of-critic | REQUIREMENTS.md:30-35 | ✓ **SATISFIED in code, NOT marked in the tracker** | All five clauses hold: default `claude-opus-4-8` ✓, not the critic's ✓, stronger than the writer ✓, zero cost change ✓ (price identity exact), `stop_reason` checked before content ✓, Opus 4.8 price row ✓, ADR-0012 records the supersession and the register reopening ✓. **But** the checkbox at :30 is still `- [ ]` and the traceability cell at :96 still reads `Pending`. See Warning 1. |

No orphaned requirements: REQUIREMENTS.md maps exactly one REQ to Phase 18, and every plan in
the phase claims it.

---

## Anti-Pattern Scan

Files modified by this phase: `evals/graders.py`, `evals/harness.py`, `src/research_agent/usage.py`,
`tests/test_evals.py`, `tests/test_usage.py`, `README.md`, `docs/DESIGN.md`, `docs/OPERATIONS.md`,
`docs/adr/README.md`, `docs/adr/0010-….md`, `docs/adr/0012-….md`.

| Check | Result |
|---|---|
| Debt markers (`TBD`, `FIXME`, `XXX`) in phase-modified source | **None** |
| Stub returns / empty implementations | **None** — every new branch returns real values or raises with a diagnostic |
| Hardcoded data reaching output | **None** — `ASSUMED_JUDGE_INPUT_TOKENS`/`OUTPUT_TOKENS` are constants but are labelled `# unmeasured` at `evals/__main__.py:264-265` and surfaced to the operator as *"assumed tokens"* in the preview, which is the honest handling, not a stub |
| Lint | `ruff check .` clean |

**No blockers.**

---

## Gaps Summary

**There are no gaps against the four success criteria.** The phase goal is achieved and each
criterion is backed by a mutation the verifier performed rather than read.

Two hygiene findings sit outside the contract and are recorded as warnings, not gaps:

1. **REQUIREMENTS.md was never updated at phase close.** ROADMAP says `[x]` / COMPLETE;
   REQUIREMENTS says `- [ ]` / `Pending`. The v1.1 convention (verified at commit `a61897a`)
   flips these in the phase-close commit. No Phase 18 plan declared it, so this is convention
   drift, not a broken commitment — a two-line fix in the next commit that touches `.planning/`.
2. **Two of the three stale codebase-map sites were staled by this phase**, not merely surfaced
   by it. The phase's own framing ("drift the sweep surfaced, not drift the phase created") is
   accurate for `STACK.md:98` and generous for the other two. Both are generated `.planning/`
   snapshots, so neither is a shipped-doc contradiction, and both are logged in
   `deferred-items.md` with an owner.

One deferred verification — the live Opus 4.8 round-trip — is confirmed **recorded in three
places rather than silent**, and is carried forward to Phase 21 above.

**The 18-VALIDATION record survives audit.** Its most load-bearing property is not the count of
reds: it is that the one row where a predicted red **did not occur**
(`test_record_preview_lands_in_the_researched_range`) was corrected rather than banked. The
verifier re-ran that mutation and the test is green exactly as the ledger says. A record that
publishes its own falsified prediction is the reason the other twelve rows are credible.

---

## Notes for the Next Phase

- **Phase 22** still owns `README.md:285`. Verified untouched. Do not let a doc pass tidy it early.
- **Phase 21** owns the first real Opus 4.8 verdict and, per `deferred-items.md`, is a candidate
  owner for the console-announce nicety. If it fixes that,
  `test_the_record_console_names_the_judge_not_the_run_when_the_judge_declines` will red on
  `assert "DECLINED" not in out` — that is the pin working, not a regression.
- **A `/gsd-map-codebase` re-run** clears three stale judge-model assertions in `.planning/codebase/`.

---

_Verified: 2026-08-14T02:21:41Z_
_Verifier: Claude (gsd-verifier) — goal-backward, 7 mutations performed and reverted, working tree clean_
_First VERIFICATION.md in this project. The v1.1 audit's standing P1 was that no phase carried one._
