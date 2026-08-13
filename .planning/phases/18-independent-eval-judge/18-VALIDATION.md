---
phase: 18
slug: independent-eval-judge
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-13
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
| 18-01.T2 | 18-01 | 1 | REQ-judge-independent-of-critic | `JUDGE_MODEL` defaults to `claude-opus-4-8`; independence pin asserts judge ≠ the DEPLOYED critic (fly.toml's parsed `[env]` `CRITIC_MODEL`, the tests/test_deploy_config.py:208 idiom — the 16-02 lesson: the neutral default is a blind spot, and `graph.critic_model()` in a keyless suite compares against `graph.MODEL` and proves nothing) | unit | `.venv/bin/pytest tests/test_evals.py -k "different_model or independen"`; mutation: flip the default back to `claude-opus-5` → independence pin must red while :606 stays green | pending |
| 18-01.T1 + 18-01.T2 | 18-01 | 1 | REQ-judge-independent-of-critic | `usage.PRICES` carries `claude-opus-4-8` at $5/$25 with cache rates 1.25×/0.1× of input; the two tests that price `G.JUDGE_MODEL` against the real table (:2359, :2398) stay green — **row and default flip share one commit** (research trap #1) | unit | `.venv/bin/pytest tests/test_usage.py` (direct pin, RED-first via `UnknownModelPricing`) + `-k "record_preview"`; mutation: delete the row → direct pin reds AND :2359/:2398 red with `UnknownModelPricing`, demonstrating the trap once | pending |
| 18-02.T1 + 18-02.T2 + 18-02.T3 | 18-02 | 2 | REQ-judge-independent-of-critic | A judge refusal (`stop_reason: "refusal"`, HTTP 200, empty/partial content) surfaces as a failed Grade with the contractual DECLINED-prefixed detail, reaching the recorder's failed-graders refusal branch — never `ValueError`, never "the run errored", never a recorded fixture (file absent) | unit + integration (fake-driven, keyless) | `.venv/bin/pytest tests/test_evals.py -k "refus or verdict or record"`; mutations: (a) refusal test observed red on CURRENT code's misleading ValueError before the guard exists; (b) guard deleted → refusal tests red ALONE (15-06 ungated-rule check); (c) recorder test reds on reason CONTENT when the guard is removed — a reason-blind assertion is green under both branches | pending |
| 18-02.T1 | 18-02 | 2 | REQ-judge-independent-of-critic | Malformed (non-refusal) judge output still raises — the guard narrows, it does not swallow; `FakeJudgeClient` extended with `stop_reason="end_turn"`/`stop_details=None` so :598 stays green rather than AttributeError-ing | unit | `.venv/bin/pytest tests/test_evals.py -k "unparseable"` stays green throughout | pending |
| 18-03.T1 + 18-03.T2 + 18-03.T3 | 18-03 | 3 | REQ-judge-independent-of-critic | ADR-0012 exists at `docs/adr/0012-judge-independent-of-the-critic.md`, supersedes ADR-0010's judge==critic acceptance only (critic-stronger-than-writer untouched), states the register reopens; ADR-0010 status line updated per convention (one-line diff); `test_evals.py:2560`'s assertion extended to the 0005→0010→0012 chain **in the same commit** (research trap #2) | unit + grep gate | `.venv/bin/pytest tests/test_evals.py -k "record_that_exists"`; mutations: revert 0010's status line → chain test reds; rename 0012 away → reds on existence | pending |
| 18-04.T1 | 18-04 | 4 | REQ-judge-independent-of-critic | The operator-facing collision warning's premise inverts (judge ≠ critic at shipped defaults): line and token-pinning tests re-derived — silent at new defaults (new twin), fires once on an operator-created collision with fact-not-fault wording pointing at ADR-0012 | unit | `.venv/bin/pytest tests/test_evals.py -k "collision"`; mutations: fire unconditionally → silent twin reds; pointer reverted to ADR-0010 → wording tests red. Fire case driven via `FakeJudge(model="claude-opus-5")` + `CRITIC_MODEL=claude-opus-5` (pitfall 4: `JUDGE_MODEL` binds at import, so an env-var monkeypatch proves nothing) | pending |
| 18-01.T3 (wave proof) + 18-04.T3 (phase proof) | 18-01, 18-04 | 1, 4 | REQ-judge-independent-of-critic | `grade_fixture_current` still compares pipeline + critic, never judge — the committed fixture does not stale; stated in both SUMMARYs, not folklore | integration | `.venv/bin/python -m evals` → 41/41 exit 0 immediately after the flip and again at phase close; :1896 boundary-docstring pin green — honest green, reason recorded (the gate never compared the judge by design) | pending |
| 18-03.T2 (index) + 18-04.T2 (DESIGN/OPERATIONS/README) | 18-03, 18-04 | 3, 4 | REQ-judge-independent-of-critic | Doc surfaces re-derived: ADR index counting prose agrees with the table BY DERIVATION (new checker — 17-04's unbuilt T3, built in 18-03; mutation: flip a table row's status, prose untouched → checker reds); DESIGN.md trailer extended to 0012; OPERATIONS record-mode paragraph rewritten; measured-baseline greps `judge and the critic share` (1→0) and `in production the judge and the critic run` (1→0); README test count measured and corrected; README :285 Limitations bullet UNTOUCHED (Phase 22's) | unit (checker) + grep gate + whole-file prose review | checker selector named at execution; baseline-anchored greps quoted before and after | pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| A real Opus 4.8 judge verdict round-trips | The offline suite fakes the client; only a paid call proves the live shape | Deferred to Phase 21's record run, which is the next paid judge exercise — record this deferral in the 18-04 SUMMARY rather than leaving it silent |

---

## Validation Sign-Off

- [ ] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [ ] Suite green plain; keyless invariant intact (`ANTHROPIC_API_KEY=""` throughout)
- [ ] Offline evals 41/41 exit 0 — the committed fixture must NOT stale
- [ ] `nyquist_compliant: true` set at reconciliation

**Approval:** pending execution.
