---
phase: 22
slug: limitations-recorded
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-16
---

# Phase 22 — Validation Strategy

> Close-out contract for a prose-heavy phase. Two disciplines dominate: DELETION is
> verified on the git axis (gone, not moved), and every NUMBER is re-measured at
> execution — this phase was planned before Phase 21.5 executed, so every count in the
> plans is a placeholder by design.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]` |
| **Quick run command** | `.venv/bin/pytest tests/test_evals.py tests/test_docs.py 2>/dev/null \|\| .venv/bin/pytest tests/test_evals.py` (verify which doc-gate file exists at execution) |
| **Full suite command** | `.venv/bin/pytest -p no:warnings 2>&1 \| tail -1` (a second `-q` suppresses the count line) |
| **Evals command** | `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --quiet; echo $?` (real exit, never piped) |

**Measured at PLANNING (2026-08-16, before 21.5 — placeholders, not commitments):**
806 passed / 72 skipped keyless; evals 59/59 exit 0 (40 behavioural + 19 replayed);
19 fixtures / 21 refusals; ruff clean. Limitations bullets at README:295/:296/:299/:301
(delete) and :297/:298/:300 (survive). **Every one of these is re-measured in the phase's
first task; 21.5 will have moved the split, the counts, and probably the line numbers.**

---

## Sampling Rate

- **After every task commit:** quick command + keyless evals
- **Before verification:** full suite green, evals green at the measured denominator,
  ruff clean, and the whole-README read-through done

---

## Per-Task Verification Map

*(Planner assigns Task IDs/Plan/Wave; executor fills Status with measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command / Mutation | Status |
|---------|------|------|-------------|-----------|-----------|------------------------------|--------|
| TBD | TBD | TBD | REQ-limitations-recorded | **Re-measure first:** fixtures/refusals split, eval denominator, suite counts, current Limitations line numbers — all recorded as the execution baseline before any edit | measurement | the numbers land in the SUMMARY and every later gate anchors to them, not to planning-time values | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **Deletion, on the git axis:** each closed bullet (judge, recorded-answers, credential-validity, note-bound) has grep count 1 before and 0 after; `git log -S` shows the text entered the repo once and left once — deleted, never moved or rewritten into release notes | grep + git gate | mutation: restore one deleted bullet → the post-state grep gate reds; the no-orphan sweep (next row) must NOT red on it (different gates, different jobs) | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **No orphaned claims:** no doc surface still asserts a deleted limitation's claim — the enumerated grep patterns (researcher's list: presence-not-validity phrasing, "bounded by expiry alone", "one of forty", judge-shares-critic phrasing) return 0 across README/docs/ADRs, with ADR historical texts exempted BY LISTED PATH, not by pattern | grep sweep | mutation: plant one orphaned claim in DESIGN.md → the sweep reds naming the file | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **ADR-0013 (cost approximation by design)** exists, follows the 0012 Nygard shape, states the four measured rejection reasons for Admin-API reconciliation (org-scoped admin key, aggregate daily buckets with no per-run dimension, ~5-min lag, and the one the researcher documented from the official docs), and the README cost bullet links it | file + link gate | mutation: break the README link target → the link gate reds | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **Surviving bullets all point at records:** identities → ADR-0007 (verify the existing link survives the rewrite), database → the new OPERATIONS posture note (anchor exists), cost → ADR-0013 | link gate | every relative link in the Limitations section resolves to an existing file/anchor; mutation: rename the OPERATIONS anchor → red | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **OPERATIONS database posture note** carries the verified facts (region, tier, 60-connection ceiling with ~10 held, no read replica, the upgrade path) and the genuinely-new "deliberate posture" framing the researcher confirmed exists nowhere today | prose + grep | facts cross-checked against the sources OPERATIONS already carries at :176/:292, not against the README bullet being replaced | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **The two paid-run defects recorded** where the researcher argued they live (README eval-section prose), with their evidence (truncation site graders.py:758, the six divergences in REFUSALS.json), and a derived-counts gate in the house pattern so the prose numbers cannot drift from the JSON | unit | mutation: change a REFUSALS.json count → the derived-counts test reds against the stale prose | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **Intro rewritten:** states v1.2 closed four, recorded three by design, and what the paid run discovered — remainder chosen/recorded/argued. Whole-README read-through for anything the rewrite falsifies | prose | cannot be automated: routed to the SUMMARY and the user's PR read; the falsification sweep IS automated (the no-orphan greps) | pending |
| TBD | TBD | TBD | REQ-limitations-recorded | **Close-out flips:** REQUIREMENTS checkbox + traceability (REQ-limitations-recorded; verify 21.5 flipped REQ-classifier-model), ROADMAP progress, STATE — hand-edited; the two Phase-20 deferred items (PROJECT.md counts, CONCERNS.md:242) settled or their disposition stated | checklist | `gsd-tools` state parse after the hand edit; grep the deferred items' fates | pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| The section reads as an honest ledger | Prose quality is the deliverable; no grep proves tone | The PR body quotes the new intro verbatim; the user judges it at review |
| The close-out claim ("no bullet stands uncovered") | It is the milestone's acceptance bar, and it is a reading, not a count | Verification walks every surviving bullet to its record and says so per bullet |

---

## Validation Sign-Off

- [ ] Execution baseline re-measured before any edit (post-21.5 numbers)
- [ ] Four deletions verified on the git axis; no-orphan sweep clean; every mutation observed red
- [ ] ADR-0013 landed in the house shape; all Limitations links resolve
- [ ] Suite + evals green at the measured denominator; ruff clean
- [ ] Milestone flips done and parsed
- [ ] `nyquist_compliant: true` at reconciliation

**Approval:** pending execution (after Phase 21.5).
