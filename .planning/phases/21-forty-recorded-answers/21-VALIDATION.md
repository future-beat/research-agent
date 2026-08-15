---
phase: 21
slug: forty-recorded-answers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-15
---

# Phase 21 — Validation Strategy

> Per-phase validation contract. This phase is unusual: its central deliverable is DATA
> (40 fixtures) produced by a PAID run, so the gates split into keyless gates that CI can
> hold forever, and paid-run evidence that verification checks as a record without
> re-spending.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_evals.py` |
| **Full suite command** | `.venv/bin/pytest -p no:warnings 2>&1 \| tail -1` (addopts already carries `-q`; a second `-q` suppresses the count line) |
| **Evals command** | `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --quiet; echo $?` (real exit, never through a pipe) |
| **Estimated runtime** | ~30 seconds suite; evals runtime will GROW with 40 fixtures — measure and record |

**Measured baseline entering this phase (2026-08-15):** 799 passed / 72 skipped keyless;
offline evals **41/41 (100% vs 90% required)** exit 0; ruff clean; exactly **1 fixture**
(`technical-figures.json`, recorded 2026-08-10, `models.judge: claude-opus-5` — STALE, the
superseded judge; its re-recording is the calibration stage).

**Money baseline:** live quote 2026-08-15 **$17.4812** (40 cases, 11 follow-up turns,
91 judge calls; basis 1 measured / 39 assumed). The user ratified: mid-execution
checkpoints, calibrate-first staging. NOTHING passes `--yes` except at a checkpoint the
user approved in that prompt.

---

## Sampling Rate

- **After every task commit:** quick command + keyless evals
- **After each paid stage:** the stage's report JSON captured to the phase dir, actual
  vs quote recorded immediately (not reconstructed later)
- **Before verification:** full suite green; keyless evals green with the NEW denominator;
  ruff clean

---

## Per-Task Verification Map

*(Planner assigns Task IDs/Plan/Wave; executor fills Status with measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command / Mutation | Status |
|---------|------|------|-------------|-----------|-----------|------------------------------|--------|
| 21-01 T1 (logic) → 21-03 T1 (pin) | 01, 03 | 1, 3 | REQ-forty-recorded-answers | **Completeness gate exists and bites:** the set of committed fixtures equals the 40 golden case IDs — the researched gap: today NOTHING asserts this; replay grades whatever exists. New keyless gate (pytest and/or the CLI exit rule) | unit/structural | mutation: delete one fixture → the gate reds naming the missing case id; add a fixture for a nonexistent case id → reds too (both directions, or the gate only half-bites) | pending |
| 21-01 T1 (logic) → 21-03 T1 (pin) | 01, 03 | 1, 3 | REQ-forty-recorded-answers | Every fixture carries the SETTLED judge's verdict: `models.judge == "claude-opus-4-8"` for all 40 — which also proves the stale 2026-08-10 fixture was re-recorded, not grandfathered | unit | keyless scan over fixture JSONs; mutation: flip one fixture's judge field → red naming the file | pending |
| 21-03 T2 | 03 | 3 | REQ-forty-recorded-answers | All 40 replay and grade keylessly: `python -m evals` with empty keys grades 40 golden + 40 recorded = **80** checks (researched denominator), exit 0, honest print of the new denominator (DEC-13) | integration (keyless) | run with keys explicitly emptied; capture the count line; mutation: corrupt one fixture's answer → the replay leg reds and the exit code is nonzero | pending |
| 21-02 T1–T2 | 02 | 2 | REQ-forty-recorded-answers | Calibration stage (PAID, checkpoint 1): exactly one case recorded via `--case`, actual cost captured from the report, quote re-based (expect "2 measured" language or tighter assumed basis) | paid checkpoint | evidence: stage report JSON + the recorder's own printed actual; NO automated gate can run this — the checkpoint approval in the transcript is the authorization record | pending |
| 21-02 T3–T4 | 02 | 2 | REQ-forty-recorded-answers | Bulk stage (PAID, checkpoint 2): remaining 39 recorded in explicit `--case` batches (researched: a blind full re-run RE-SPENDS on existing fixtures — batching is the resume mechanism), refusals surfaced as findings with the recorder's own output preserved, never auto-retried | paid checkpoint | evidence: per-batch report JSONs; refusal list (possibly empty) in the SUMMARY; any re-run of a refused case is its own user-approved micro-checkpoint with incremental cost stated | pending |
| 21-03 T3 | 03 | 3 | REQ-forty-recorded-answers | Actual-vs-quote reported (success criterion 4): per-stage actuals summed against $17.4812, in the SUMMARY and the PR body | prose gate | numbers come from report JSONs, not memory; the delta is stated even if embarrassing in either direction | pending |
| 21-03 T2 (before-timing: 21-01 T2) | 01, 03 | 1, 3 | REQ-forty-recorded-answers | CI stays keyless and green with the new denominator; runtime measured before/after (41 → 80 graded checks); `--min-pass-rate 0.9` semantics stated against the grown denominator | integration | CI-equivalent local run with keys emptied; before/after runtime in the SUMMARY | pending |
| 21-03 T3 | 03 | 3 | REQ-forty-recorded-answers | Doc surfaces: README whole-file pass (eval counts at `:200`/`:221`, test counts if they move), OPERATIONS if it quotes eval counts; the Limitations bullet at README:286 BYTE-UNTOUCHED (Phase 22's) | grep gate + prose | bullet grep count 1 before and after, on the git axis; test-count sites measured not assumed | pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| The two paid stages themselves | Real spend on the operator's key; cannot and must not run in CI or verification | Verification checks the RECORD: report JSONs in the phase dir, fixture mtimes/contents, the checkpoint approvals in the transcript, actual-vs-quote arithmetic. It never re-spends. |
| Fixture answer quality skim | Graders judge answers mechanically; a human skim of 2–3 recorded answers for obvious garbage is cheap insurance on a $17 artifact | User may skim any fixture JSON's `answer` field at the checkpoint; not a blocking gate |

---

## Validation Sign-Off

- [ ] Completeness gate observed red in BOTH directions before trusted
- [ ] Every keyless gate: measured baseline AND recorded mutation
- [ ] Both paid stages: user-approved at their checkpoints, report JSONs archived, actuals vs quote stated
- [ ] Refusal list stated (even if empty)
- [ ] Suite + evals green with the new denominator; ruff clean
- [ ] `nyquist_compliant: true` set at reconciliation

**Approval:** pending execution.
