---
phase: 18
slug: independent-eval-judge
status: draft
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

*(Task IDs assigned at planning; rows below are the researched gate set — the planner
distributes them across plans and the executor fills Status with measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| TBD | TBD | TBD | REQ-judge-independent-of-critic | `JUDGE_MODEL` defaults to `claude-opus-4-8`; independence pin asserts judge ≠ `graph.critic_model()` under the neutral env (the 16-02 lesson: the neutral default is a blind spot — pin with env-driven twins, not just the default) | unit | pytest selector named at planning; mutation: flip the default back to `claude-opus-5` → independence pin must red | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | `usage.PRICES` carries `claude-opus-4-8` at $5/$25 with cache rates 1.25×/0.1× of input; the two tests that price `G.JUDGE_MODEL` against the real table stay green — **row and default flip share one commit** (research trap #1) | unit | existing cache-ratio pin + judge-leg pricing tests | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | A judge refusal (`stop_reason: "refusal"`, HTTP 200, empty/partial content) surfaces as a failed Grade reaching the recorder's failed-graders refusal branch — never `ValueError`, never a recorded fixture | unit | new tests with a fake client returning a refusal-shaped response; mutation: remove the `stop_reason` check → the refusal-path test must red on the misleading-ValueError route it exists to prevent | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | Malformed (non-refusal) judge output still raises — the guard narrows, it does not swallow | unit | existing unparseable-verdict test stays green with the fake extended to carry `stop_reason: "end_turn"` | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | ADR-0012 exists, supersedes ADR-0010's judge==critic acceptance only (critic-stronger-than-writer untouched), states the register reopens; ADR-0010 status line updated per convention; `test_evals.py:2560`'s supersession-chain assertion extended **in the same commit** (research trap #2) | unit + grep gate | the record-exists/status-agreement test family from 16-03, extended to the 0005→0010→0012 chain | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | The operator-facing collision warning's premise inverts (judge ≠ critic in production): the line and its token-pinning tests re-derived — fires only when models actually collide, wording stays property-statement not misconfig-blame | unit | 16-02's wording tests re-targeted; mutation: set `EVAL_JUDGE_MODEL=claude-opus-5` and observe the collision line fire with the new wording | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | `grade_fixture_current` still compares pipeline + critic, never judge — the committed fixture does not stale; stated by a pinned docstring/test, not folklore | unit | existing boundary test confirmed green; no new gate needed, but the plan must SAY so | pending |
| TBD | TBD | TBD | REQ-judge-independent-of-critic | Doc surfaces re-derived (DESIGN.md, OPERATIONS.md, ADR index counting: 12 records, 8 accepted, 4 supersessions, register reopened) — arithmetic checked against the tree, not the plan (the fifth-time lesson) | grep gate + prose review | baseline-anchored greps named at planning | pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| A real Opus 4.8 judge verdict round-trips | The offline suite fakes the client; only a paid call proves the live shape | Deferred to Phase 21's record run, which is the next paid judge exercise — record this deferral in the phase SUMMARY rather than leaving it silent |

---

## Validation Sign-Off

- [ ] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [ ] Suite green plain; keyless invariant intact (`ANTHROPIC_API_KEY=""` throughout)
- [ ] Offline evals 41/41 exit 0 — the committed fixture must NOT stale
- [ ] `nyquist_compliant: true` set at reconciliation

**Approval:** pending execution.
