---
phase: 18
slug: independent-eval-judge
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-13
reconciled: 2026-08-14
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_evals.py tests/test_usage.py` |
| **Full suite command** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Estimated runtime** | ~30 seconds full; ~5 seconds quick |

**Measured baseline entering this phase (2026-08-13):** 740 passed / 67 skipped keyless;
offline evals 41/41 exit 0.

**After wave 1 (18-01, `06140a4`):** 742 passed / 67 skipped keyless — +2, exactly the two
tests that wave added, zero skip delta; offline evals 41/41 exit 0; ruff clean.

**After wave 2 (18-02, `dd7b2e8` + `ca59b62`):** 747 passed / 67 skipped keyless — +5,
exactly the five tests that wave added (two refusal, one truncation, two recorder-flow),
zero skip delta; `tests/test_evals.py` 172 → 177; offline evals 41/41 exit 0 (verified as
a real `$?`); ruff clean in both `.` and `src tests evals` forms.

**After wave 3 (18-03, `bc7cf40`):** 748 passed / 67 skipped keyless — +1, exactly the one
test that wave added (the derived-counts index checker; the chain test was extended in place,
not duplicated), zero skip delta; `tests/test_evals.py` 177 → 178; offline evals 41/41 exit 0
(real `$?`); ruff clean in both forms. `docs/adr/` goes 11 → 12 records, 8 → 8 `Accepted`,
3 → 4 supersessions.

**After wave 4 (18-04, `2f213a3` + `7a1f9f4`) — PHASE CLOSE:** **749 passed / 67 skipped**
keyless, exit 0 — +1, exactly the one test this wave added (the silent-at-the-shipped-defaults
twin; the four pre-existing collision tests were re-derived in place, not duplicated), zero
skip delta; `tests/test_evals.py` 178 → **179**; offline evals **41/41 (100% vs 90% required),
real `$?` = 0**; ruff clean in both `.` and `src tests evals` forms.

**Phase delta reconciled, every test accounted for:** 740 → 749 is **+9**, and each is named —
18-01 **+2** (the direct four-rate price pin, the deployed-critic independence pin), 18-02 **+5**
(two refusal, one truncation, two recorder-flow), 18-03 **+1** (the derived-counts index checker),
18-04 **+1** (the silent-at-the-shipped-defaults twin). **Skips are 67 at every one of the five
measurements — zero unexplained skips across the phase.** All 67 are Postgres-gated (66
`DATABASE_URL is not set`, 1 `REQUIRE_POSTGRES is not set`), verified by skip reason at phase
close, so no test was quietly disabled to make a gate green.

---

## Sampling Rate

- **After every task commit:** Run the quick command
- **After every plan wave:** Run the full suite, keyless
- **Before `/gsd:verify-work`:** Full suite green plain; offline evals 41/41 exit 0
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

*(Task IDs assigned at planning 2026-08-13 — four plans, four waves, sequential by shared
`tests/test_evals.py`/`evals/graders.py` ownership. The executor fills Status with
measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| 18-01.T2 | 18-01 | 1 | REQ-judge-independent-of-critic | `JUDGE_MODEL` defaults to `claude-opus-4-8`; independence pin asserts judge ≠ the DEPLOYED critic (fly.toml's parsed `[env]` `CRITIC_MODEL`, the tests/test_deploy_config.py:208 idiom — the 16-02 lesson: the neutral default is a blind spot, and `graph.critic_model()` in a keyless suite compares against `graph.MODEL` and proves nothing) | unit | `.venv/bin/pytest tests/test_evals.py -k "different_model or independen"`; mutation: flip the default back to `claude-opus-5` → independence pin must red while :606 stays green | **PASS (18-01, `06140a4`)** — `test_the_judge_runs_on_a_different_model_than_the_deployed_critic` parses `fly.toml` with tomllib, asserts `[env].CRITIC_MODEL` present, then compares. Observed RED before the flip: `assert 'claude-opus-5' != 'claude-opus-5' where 'claude-opus-5' = G.JUDGE_MODEL`. Mutation run: pin RED, `:606` GREEN — confirming `:606` never guarded this. Probe re-run after ruff's SIM300 forced the comparison to be re-typed, so the red was observed in the form that ships |
| 18-01.T1 + 18-01.T2 | 18-01 | 1 | REQ-judge-independent-of-critic | `usage.PRICES` carries `claude-opus-4-8` at $5/$25 with cache rates 1.25×/0.1× of input; the two tests that price `G.JUDGE_MODEL` against the real table (:2359, :2398) stay green — **row and default flip share one commit** (research trap #1) | unit | `.venv/bin/pytest tests/test_usage.py` (direct pin, RED-first via `UnknownModelPricing`) + `-k "record_preview"`; mutation: delete the row → direct pin reds AND :2359/:2398 red with `UnknownModelPricing`, demonstrating the trap once | **PASS with a correction (18-01, `06140a4`)** — row + flip verified in ONE commit by `git show --stat`. `test_the_eval_judges_model_is_priced` observed RED before the row (`UnknownModelPricing: No price for 'claude-opus-4-8' on 2026-08-13`), green after; `tests/test_usage.py` 44→45. Mutation: the direct pin reds AND `test_record_preview_requotes_itself_when_the_rate_window_flips` (the real line is **:2392**, not :2359) reds with `UnknownModelPricing`. **This row's third prediction is false and is corrected rather than banked:** `test_record_preview_lands_in_the_researched_range` (:2398) stays GREEN under the mutation — `evals/__main__.py:287/:342` catch `UnknownModelPricing` by design (15-05), so the preview degrades to a `$12.28` FLOOR that still sits inside its `8.0 < total < 20.0` window. The trap is loud in the SUITE and QUIET in a real record run; see 18-01-SUMMARY § "The ordering trap, measured" |
| 18-02.T1 + 18-02.T2 + 18-02.T3 | 18-02 | 2 | REQ-judge-independent-of-critic | A judge refusal (`stop_reason: "refusal"`, HTTP 200, empty/partial content) surfaces as a failed Grade with the contractual DECLINED-prefixed detail, reaching the recorder's failed-graders refusal branch — never `ValueError`, never "the run errored", never a recorded fixture (file absent) | unit + integration (fake-driven, keyless) | `.venv/bin/pytest tests/test_evals.py -k "refus or verdict or record"`; mutations: (a) refusal test observed red on CURRENT code's misleading ValueError before the guard exists; (b) guard deleted → refusal tests red ALONE (15-06 ungated-rule check); (c) recorder test reds on reason CONTENT when the guard is removed — a reason-blind assertion is green under both branches | **PASS, all three mutations (18-02, `dd7b2e8` + `ca59b62`)** — (a) both refusal tests observed RED on the unguarded code: `ValueError: Judge returned unparseable verdict: ''` raised at `graders.py:748`, the parse's own except, for a response that never contained anything to parse. (b) Guard deleted, whole file: **2 failed / 173 passed — the refusal tests red ALONE**, nothing else leans on it. (c) Guard deleted, recorder flow: `assert 'judge_grounding' in "refusing to record 'technical-figures': the run errored (ValueError: Judge returned unparseable verdict: '')"` — both recorder tests red on the reason CONTENT, while `written=False` and the absent file stay identical under both branches, which is exactly why the content assertions are the gate. **Seam correction:** the plan's fallback ("assert the detail through the announce path") has no path to assert through — under `--record`, `main` wires `announce_recording` (grader names) and never calls `announce` (grade details), so the DECLINED detail reaches the operator via `--report` JSON only. Asserted on the surfaces that exist and pinned as an ABSENCE (`"DECLINED" not in out`); see 18-02-SUMMARY § "The plan's seam claim, checked against the tree" and `deferred-items.md` |
| 18-02.T1 | 18-02 | 2 | REQ-judge-independent-of-critic | Malformed (non-refusal) judge output still raises — the guard narrows, it does not swallow; `FakeJudgeClient` extended with `stop_reason="end_turn"`/`stop_details=None` so :598 stays green rather than AttributeError-ing | unit | `.venv/bin/pytest tests/test_evals.py -k "unparseable"` stays green throughout | **PASS (18-02)** — `test_judge_raises_on_an_unparseable_verdict` unmodified and green at every gate, including under all five mutation probes. **Pitfall 3 was under-counted: there are TWO judge-shaped fakes, not one.** `RecordingFakeClient._Response` is also handed to the real `Judge.verdict` and had only `.content`/`.usage`; its AttributeError was swallowed by `run_case`'s blanket except and surfaced as *"the run errored"* — the bug demonstrated rather than merely tripped over. Both fakes now carry `stop_reason`/`stop_details`; the full set was found by grepping for every stand-in response object, not by the name the research wrote down. **Discretionary branch taken (Open Question 2):** `stop_reason=max_tokens` raises TRUNCATED with the partial JSON quoted, probed red alone (`Regex pattern did not match. Actual message: 'Judge returned unparseable verdict: \'{"passed": true, "rea\''`) |
| 18-03.T1 + 18-03.T2 + 18-03.T3 | 18-03 | 3 | REQ-judge-independent-of-critic | ADR-0012 exists at `docs/adr/0012-judge-independent-of-the-critic.md`, supersedes ADR-0010's judge==critic acceptance only (critic-stronger-than-writer untouched), states the register reopens; ADR-0010 status line updated per convention (one-line diff); `test_evals.py:2560`'s assertion extended to the 0005→0010→0012 chain **in the same commit** (research trap #2) | unit + grep gate | `.venv/bin/pytest tests/test_evals.py -k "record_that_exists"`; mutations: revert 0010's status line → chain test reds; rename 0012 away → reds on existence | **PASS, both mutations (18-03, `bc7cf40`)** — ONE commit verified by `git show --stat`: `docs/adr/0012-judge-independent-of-the-critic.md` (new), `0010-…md` (**1 insertion, 1 deletion** — the status line and nothing else), `docs/adr/README.md`, `README.md`, `tests/test_evals.py`. **Trap #2 observed before it was closed**, with Tasks 1–2 in the tree and Task 3 unwritten: `assert "supersedes ADR-0005" in record.read_text()` → `AssertionError` at `tests/test_evals.py:2859` — the argument for one commit, demonstrated rather than inherited. The extended test now holds three records and four status facts (0005 exists + says `Superseded by ADR-0010`; 0010 exists + says `Superseded by ADR-0012`; 0012 exists + says `supersedes ADR-0010`), extended in place rather than duplicated. Mutation (a) status reverted: `assert 'Superseded by ADR-0012' in '# ADR-0010 — The judge is re-derived …'` RED. Mutation (b) 0012 renamed away: `AssertionError: the record trail names ADR-0012; 0012-judge-independent-of-the-critic.md is not on disk` RED — **and the new index checker reds too**, on the dangling index link. ADR-0012 supersedes the judge==critic acceptance ONLY: `CRITIC_MODEL` unmoved, the critic-above-writer position named as still-deployed in both the record and the index. Register reopening stated in § Context and in `### Accepted`. Phrasing fence honoured: `judge and the critic share` appears **0** times in ADR-0012, leaving 18-04's gate anchored at its single `docs/OPERATIONS.md:803` baseline |
| 18-04.T1 | 18-04 | 4 | REQ-judge-independent-of-critic | The operator-facing collision warning's premise inverts (judge ≠ critic at shipped defaults): line and token-pinning tests re-derived — silent at new defaults (new twin), fires once on an operator-created collision with fact-not-fault wording pointing at ADR-0012 | unit | `.venv/bin/pytest tests/test_evals.py -k "collision"`; mutations: fire unconditionally → silent twin reds; pointer reverted to ADR-0010 → wording tests red. Fire case driven via `FakeJudge(model="claude-opus-5")` + `CRITIC_MODEL=claude-opus-5` (pitfall 4: `JUDGE_MODEL` binds at import, so an env-var monkeypatch proves nothing) | **PASS, three mutations — all re-observed at phase close rather than inherited (18-04, `2f213a3`)** — the collision family is now **five** tests, 179 in the file. The mechanism was NOT touched: None guard, equality early-return, once-per-run placement before the loop all survive; the docstring and the printed message are what inverted. New twin `test_judge_critic_collision_warning_is_silent_at_the_shipped_defaults` drives `FakeJudge(model=G.JUDGE_MODEL)` against `CRITIC_MODEL=claude-opus-5` (production's pin) → **no line**, and carries a non-vacuity assertion (`G.JUDGE_MODEL != "claude-opus-5"`) so the test cannot silently stop describing a production-shaped run. Fire case drives the collision through `FakeJudge(model="claude-opus-5")` per pitfall 4, and its docstring was rewritten honestly — this IS a contrived configuration now, arranged on purpose. **Mutation 1** (drop the equality early-return, print unconditionally): `test_..._is_silent_at_the_shipped_defaults` AND `test_..._is_silent_when_they_differ` both RED, 2 failed / 4 passed. **Mutation 2** (pointer reverted to ADR-0010): `test_..._fires_once_per_run` AND `test_..._states_a_fact_not_a_fault` both RED on `assert "ADR-0012" in err`. **Mutation 3, beyond the plan and the one that matters most for non-vacuity** — restore the stale *"This is the deployed configuration and it is accepted"* sentence while leaving the pointer correctly at ADR-0012: the wording test **still REDs**, on `assert 'shipped default' in …`. So the new required tokens gate on their own rather than riding the ADR string, which is the difference between pinning the wording and pinning a citation. All six fault words (`misconfig`, `error`, `invalid`, `should not`, `must not`, `fix`) still forbidden; `accepted`/`deployed` retired as required tokens and replaced by `shipped default`, `G.DEFAULT_JUDGE_MODEL` (derived from the constant, not typed) and `operator`. **`graders.DEFAULT_JUDGE_MODEL` is new and load-bearing:** `JUDGE_MODEL` is what *this process* resolved, so an operator who exported `EVAL_JUDGE_MODEL` has moved it — the note must name the default while reporting a non-default configuration |
| 18-01.T3 (wave proof) + 18-04.T3 (phase proof) | 18-01, 18-04 | 1, 4 | REQ-judge-independent-of-critic | `grade_fixture_current` still compares pipeline + critic, never judge — the committed fixture does not stale; stated in both SUMMARYs, not folklore | integration | `.venv/bin/python -m evals` → 41/41 exit 0 immediately after the flip and again at phase close; :1896 boundary-docstring pin green — honest green, reason recorded (the gate never compared the judge by design) | **18-01 wave proof PASS** — `ANTHROPIC_API_KEY="" .venv/bin/python -m evals` → `PASS 41/41 cases (100% vs 90% required)`, **exit 0**, immediately after the flip. `test_the_replay_model_gate_states_its_claim_boundary` green in the full run. Honest green, reason read out of the code not restated: `grade_fixture_current` compares `models.get("pipeline")` vs `graph.MODEL` and `models.get("critic") or pipeline` vs `graph.critic_model()` — the judge role is recorded and deliberately never compared, as its Cannot-catch paragraph says. `evals/fixtures/technical-figures.json:7`'s `"judge": "claude-opus-5"` is fixed replay data and correct as written. **18-04.T3 PHASE PROOF PASS (2026-08-14)** — `ANTHROPIC_API_KEY="" .venv/bin/python -m evals` → `PASS 41/41 cases (100% vs 90% required)`, real `$?` = **0**, at phase close with all four waves landed. **The committed fixture survived the entire phase unstaled** — the phase-level statement of this row, not a per-wave one. Re-verified in the code rather than restated from 18-01: `grade_fixture_current` reads `models.get("pipeline")` against `graph.MODEL` and `models.get("critic") or pipeline` against `graph.critic_model()`, and the judge role appears in the docstring's Cannot-catch paragraph only — it is recorded and deliberately never compared. **Line-anchor drift corrected:** this row cites the boundary test at `:1896`; it is at **`:2074`** (`test_the_replay_model_gate_states_its_claim_boundary`), located by name and green in the full run. Fourth wave running where a plan-stated line anchor had moved |
| 18-03.T2 (index) + 18-04.T2 (DESIGN/OPERATIONS/README) | 18-03, 18-04 | 3, 4 | REQ-judge-independent-of-critic | Doc surfaces re-derived: ADR index counting prose agrees with the table BY DERIVATION (new checker — 17-04's unbuilt T3, built in 18-03; mutation: flip a table row's status, prose untouched → checker reds); DESIGN.md trailer extended to 0012; OPERATIONS record-mode paragraph rewritten; measured-baseline greps `judge and the critic share` (1→0) and `in production the judge and the critic run` (1→0); README test count measured and corrected; README :285 Limitations bullet UNTOUCHED (Phase 22's) | unit (checker) + grep gate + whole-file prose review | checker selector named at execution; baseline-anchored greps quoted before and after | **18-03 half PASS (`bc7cf40`); 18-04 half pending** — checker is `test_the_adr_index_counting_prose_is_derived_from_the_table`, selected alone by `-k "index"` (that selector collected **0** tests before this wave). It parses the `\| NNNN \|` rows and derives 12 records / 8 Accepted / 4 Superseded from the Status cells. **Probe A5 reproduced exactly:** flip `0009`'s Status to `Superseded`, prose untouched → `grep -c "Eight of the twelve records"` = **1** and `grep -c "Four supersessions"` = **1** (a literal-grep gate stays GREEN) while the checker reds with `assert 'seven of the twelve records' in '…eight of the twelve records…'`. Whole-file pass corrected four prose sites, not two: the counting sentence; the forecasting claim (**"each was forecast by the record it overturned" is FALSE for this one** — verified by file, `### Expected reversal` present in 0005/0003/0006 and absent from 0010 — rewritten to "three of the four … the fourth was not", with the reason); the spent-register paragraph (empty-set claim removed); and the ENUMERATING paragraph the plan did not name — "no `docs/DESIGN.md` passage behind any of the **six**… all **six** carry `**Source:**`" → **seven**. Plus a new *Reading a superseded record* paragraph, because ADR-0010 is the first **partial** supersession and the first three-deep chain. **Plan arithmetic CHECKED and correct for the first time in this lesson family** (twelve/eight/four, derived cell by cell before typing). Checker extended beyond spec: every `Superseded by` cell must name a file on disk that claims the record the index credits it with — and **the first version of that clause red on correct code**, revealing that the convention's status-line edit deletes a middle-of-chain record's own `supersedes` claim; re-targeted at `Carried forward from ADR-NNNN`, which no supersession may edit. Also corrected in the same commit: `README.md:40`'s ADR count (eleven/three → twelve/four), falsified by this commit. **README `:285` UNTOUCHED.** Stale README/PROJECT **test** counts (740/737 vs measured 748) logged to `deferred-items.md` for 18-04. **18-04 half now PASS (`7a1f9f4`)** — both prose gates measured **1 → 0** with the baselines taken immediately before editing (the 14-03 rule; a prose gate's non-vacuity IS the measured nonzero baseline, since deleting the sentence to watch it red would test `grep`, not the document): `judge and the critic share` at `docs/OPERATIONS.md:803` → **0** in all of `docs/`; `in production the judge and the critic run` at `evals/graders.py:17` → **0** in all of `evals/`. `graders.py`'s module docstring keeps the surviving half (a judge on the writer's model inherits the blind spots it exists to find) and re-derives the inverted half: independence of the critic's model **identity**, explicitly **not** its family, pointing at ADR-0012. OPERATIONS' record-mode paragraph split in two — the staleness sentences stay and now say out loud what the gate compares (pipeline and critic, never the judge), and the collision sentence became conditional on an operator-created collision. One line documents `EVAL_JUDGE_MODEL` as the evals-CLI override, deliberately **not** added to the `:645` service env table, `fly.toml` or `.env.example` (Open Question 3 taken minimally; verified absent from both files). DESIGN.md's trailer extended to 0005 → 0010 (Phase 16) → 0012 (Phase 18). **README counts MEASURED then edited, never derived:** the suite was run, reported **749**, and `:15` and `:199` went 740 → **749**. **README `:285` UNTOUCHED**, verified post-commit — the transient contradiction is deliberate and recorded in the SUMMARY. Whole-file passes with **nothing found, stated rather than silent**: `evals/__main__.py` (entire — references `G.JUDGE_MODEL` throughout, asserts no relation to the critic) and `docs/adr/README.md` (re-read post-18-03; its one shared-model mention is ADR-0005's historical premise, correct as written). **New finding, logged not fixed:** three `.planning/codebase/` maps (`STACK.md:98`, `INTEGRATIONS.md:131`, `TESTING.md:382`) still assert the judge runs on `claude-opus-5` as current fact — generated `/gsd-map-codebase` output, out of this plan's four named surfaces, and `STACK.md:98` was already stale entering Phase 18 |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| A real Opus 4.8 judge verdict round-trips | The offline suite fakes the client; only a paid call proves the live shape | **DEFERRED to Phase 21's record run — recorded, not silent (18-04-SUMMARY § "What this phase deliberately did not do", statement 3).** Nothing in Phase 18 asked a real Opus 4.8 judge for a verdict. Every judge path is exercised through fakes (`FakeJudge`, `FakeJudgeClient`, `RefusingJudgeClient`, `RecordingFakeClient._Response`), which is what makes the suite keyless and free — and is exactly why it cannot speak to the live shape: whether Opus 4.8 returns the expected verdict JSON, and whether its refusal classifiers behave as 18-02's guard assumes. Estimated cost of the one-verdict probe: **~$0.06** at the assumed 4K-in/1.5K-out leg (`ASSUMED_JUDGE_INPUT_TOKENS`/`ASSUMED_JUDGE_OUTPUT_TOKENS`, both labelled UNMEASURED in `evals/__main__.py`). Phase 21's record run is the next paid judge exercise and the natural place to spend it |

---

## Validation Sign-Off

- [x] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [x] Suite green plain; keyless invariant intact (`ANTHROPIC_API_KEY=""` throughout)
- [x] Offline evals 41/41 exit 0 — the committed fixture must NOT stale
- [x] `nyquist_compliant: true` set at reconciliation

### Consolidated mutation ledger — every gate this phase trusts

| # | Wave | Gate | Mutation | Observed |
|---|------|------|----------|----------|
| 1 | 18-01 | `test_the_judge_runs_on_a_different_model_than_the_deployed_critic` | flip the default back to `claude-opus-5` | **RED** — `assert 'claude-opus-5' != 'claude-opus-5'`. Re-run after ruff's SIM300 forced the comparison to be re-typed, so the red was seen in the form that ships. `:606` stayed GREEN, proving it never guarded this |
| 2 | 18-01 | `test_the_eval_judges_model_is_priced` | delete the `claude-opus-4-8` PRICES row | **RED** — `UnknownModelPricing`. Also red: `test_record_preview_requotes_itself_when_the_rate_window_flips`. **Third predicted red did NOT occur** and was corrected rather than banked: `test_record_preview_lands_in_the_researched_range` stays green at a leg-less $12.28, inside its own 8.0–20.0 window |
| 3 | 18-02 | the two refusal tests | run RED-first against the unguarded `verdict` | **RED** — `ValueError: Judge returned unparseable verdict: ''` at `graders.py:748`, the parse's own except, for a response with nothing to parse |
| 4 | 18-02 | the refusal guard (15-06 ungated-rule check) | delete the `stop_reason` check, run the whole file | **RED, and red ALONE** — 2 failed / 173 passed; nothing else leaned on the guard |
| 5 | 18-02 | the two recorder-flow tests | guard removed | **RED on the reason's CONTENT** — `assert 'judge_grounding' in "…the run errored (ValueError…)"`. `written=False` and the absent file are identical under both branches, which is why a reason-blind assertion would have gated nothing |
| 6 | 18-02 | the `max_tokens` branch | delete the TRUNCATED raise | **RED alone** — the message reverts to the misdiagnosis the branch prevents |
| 7 | 18-02 | `_refusal_detail`'s None guard | delete the `is None` early return | **RED alone**, and its SHAPE is the point: `getattr` reads yield `category=None`, not an AttributeError, so a crash-shaped assertion would have gone green on a lie |
| 8 | 18-03 | the derived-counts index checker (17-04's probe A5) | flip a table row's Status, leave the prose alone | **RED**, while `grep -c "Eight of the twelve records"` = 1 and `grep -c "Four supersessions"` = 1 — the literal-grep gates stay GREEN under the mutation that matters |
| 9 | 18-03 | the 0005→0010→0012 chain test | revert ADR-0010's status line | **RED** — the chain breaks at 0010 → 0012 and the test says so |
| 10 | 18-03 | chain test + index checker | rename ADR-0012 away | **BOTH RED**, on different grounds — the operator-message pointer and the index link |
| 11 | 18-04 | both silence tests | `_state_judge_critic_relation` prints unconditionally | **RED** — the new twin AND `is_silent_when_they_differ`, 2 failed / 4 passed |
| 12 | 18-04 | both wording tests | pointer reverted to ADR-0010 | **RED** — `assert "ADR-0012" in err` on `fires_once_per_run` and `states_a_fact_not_a_fault` |
| 13 | 18-04 | the wording test's NEW tokens | restore the stale "deployed / accepted" sentence, pointer left correct at ADR-0012 | **RED** on `assert 'shipped default' in …` — the new tokens gate on their own rather than riding the ADR citation |

**Honest greens, each with its reason recorded rather than counted as a red:**

| Gate | Why no mutation red | Non-vacuity comes from |
|------|---------------------|------------------------|
| The two prose greps (18-04.T2) | Deleting the sentence to watch it red tests `grep`, not the document (the 14-03 rule) | A **measured nonzero baseline** — both at 1 immediately before editing, both 0 after |
| Offline evals 41/41 (validation row 7) | The gate is that a judge change does NOT fire the staleness comparison — there is no mutation that should red it | The reason read out of `grade_fixture_current`'s own code: it compares pipeline and critic and never the judge, pinned by the boundary-docstring test at `:2074` |
| `test_judge_raises_on_an_unparseable_verdict` (18-02) | It must stay green — it is the discriminator the refusal guard had to narrow without swallowing | Verified green under all five of 18-02's probes, not merely at the end |

**Gates this phase found to be DECORATIVE and recorded rather than trusted:**
`test_record_preview_lands_in_the_researched_range` is not a gate on the ordering trap
(mutation 2). A range assertion over a total that has lost an entire leg stays green — and
the trap's real behaviour in a record run is a **quiet $12.28 FLOOR**, not the crash the plan,
18-RESEARCH and this contract all predicted. Corrected in row 2 rather than banked, so no
later phase re-inherits the claim.

**Approval:** ✅ **Phase 18 complete, 2026-08-14.** Four waves, four plans, six commits
(`06140a4`, `dd7b2e8`, `ca59b62`, `bc7cf40`, `2f213a3`, `7a1f9f4`) plus per-wave metadata.
Final gate, keyless throughout: **749 passed / 67 skipped** exit 0; offline evals **41/41
(100% vs 90% required)** real `$?` = 0; **ruff clean** in both forms. Every ROADMAP success
criterion holds with a measured gate; the one manual-only verification is deferred to Phase 21
and recorded above rather than left silent.
