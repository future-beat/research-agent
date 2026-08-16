---
phase: 22
slug: limitations-recorded
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-16
reconciled: 2026-08-16
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

**MEASURED AT EXECUTION (2026-08-16, after 21.5 — the values every gate below anchors to):**
**828 passed / 72 skipped** keyless, **900 collected**; evals **PASS 65/65, real `$?` 0**
(40 behavioural + 25 replayed); **25 fixtures / 15 refusals**, decomposing **7 grader /
2 judge_truncated / 6 recorded_then_failed_replay**; `ruff check .` clean. The planning
placeholders drifted on **every axis**, exactly as this contract predicted: +22 tests,
denominator 59 → 65, and the split moved 19/21 → 25/15 (six cases re-recorded by 21.5, two
more rewritten in place). The Limitations line numbers moved twice — to :295-:301 at 22-01's
measurement and to :334-:340 after 22-01's own eval-section expansion — which is why every
gate below locates by heading and phrase, never by line number. **One number the planning
snapshot got right by accident and was still re-measured: ruff clean.**

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
| 22-01 T1 | 22-01 | 1 | REQ-limitations-recorded | **Re-measure first:** fixtures/refusals split, eval denominator, suite counts, current Limitations line numbers — all recorded as the execution baseline before any edit | measurement | the numbers land in the SUMMARY and every later gate anchors to them, not to planning-time values | **PASS** — measured before any edit and recorded in 22-01's SUMMARY: 827/72/899 at that moment (828/72/900 after 22-01's own test), evals 65/65 exit 0, 25 fixtures / 15 refusals, `## Limitations` at README:293→:326, all four deletion candidates grepping exactly 1. Every planning placeholder drifted; **no planning-document number was carried into any surface either plan wrote**. The re-measurement also caught the live consequence that ADR **0013 was taken** by 21.5, firing the renumber contingency |
| 22-02 T1 (delete) / T2 (git axis) | 22-02 | 2 | REQ-limitations-recorded | **Deletion, on the git axis:** each closed bullet (judge, recorded-answers, credential-validity, note-bound) has grep count 1 before and 0 after; `git log -S` shows the text entered the repo once and left once — deleted, never moved or rewritten into release notes | grep + git gate | mutation: restore one deleted bullet → the post-state grep gate reds; the no-orphan sweep (next row) must NOT red on it (different gates, different jobs) | **PASS** — all four phrases grep **1 before, 0 after**; the section holds exactly **3** bullets. Git axis, per phrase: `git log --oneline -S"<phrase>" -- README.md` returns exactly two commits, and the direction was verified rather than assumed — the earlier commit shows the line with a `+` (`6d615ec`, `7906a99`, `708c545`, `7906a99`) and `219e9e3` shows it with a `-`. `git grep -lF` over the whole tree: **no file outside `.planning/` planning records has ever carried any of the four**, so nothing was moved into release notes. **Mutation observed:** the note-bound bullet pasted back → deletion gate RED (`grep = 1, expected 0`; bullet count `4, expected 3`) while the sweep stayed CLEAN. Reverted, re-run green |
| 22-02 T2 | 22-02 | 2 | REQ-limitations-recorded | **No orphaned claims:** no doc surface still asserts a deleted limitation's claim — the enumerated grep patterns (researcher's list: presence-not-validity phrasing, "bounded by expiry alone", "one of forty", judge-shares-critic phrasing) return 0 across README/docs/ADRs, with ADR historical texts exempted BY LISTED PATH, not by pattern | grep sweep | mutation: plant one orphaned claim in DESIGN.md → the sweep reds naming the file | **PASS, and the exemption list came out EMPTY.** All four enumerated patterns return **zero hits** across `docs/` and `.planning/codebase/`, so no ADR historical text needed exempting and T-22-03 (tampering with frozen records) had **no opportunity to fire** — the safest possible outcome, and better than a justified exemption list. A deliberately broader paraphrase sweep (`judge (shares\|uses) the critic`, `present, not that they work`, `presence, not validity`, `no (eviction\|dedup)`, `expiry alone`, `only one of forty`, `one recorded answer`) returned **two** hits, both `.planning/codebase/CONCERNS.md` (:129, :254) — the already-known Phase-20 deferred item, dispositioned unedited per P-08, not an orphan this phase created. **Mutation observed:** `Notes are bounded by expiry alone…` planted in `docs/DESIGN.md` → sweep RED naming `docs/DESIGN.md:85`, while README's deletion gate stayed GREEN. Reverted; `git diff --quiet docs/DESIGN.md` confirms byte-identity |
| 22-01 T2 (record) / 22-02 T1 (link) | 22-01 / 22-02 | 1 → 2 | REQ-limitations-recorded | **ADR-0013 (cost approximation by design)** exists, follows the 0012 Nygard shape, states the four measured rejection reasons for Admin-API reconciliation (org-scoped admin key, aggregate daily buckets with no per-run dimension, ~5-min lag, and the one the researcher documented from the official docs), and the README cost bullet links it | file + link gate | mutation: break the README link target → the link gate reds | **PASS, with the number corrected: the record is ADR-0014, not ADR-0013.** Phase 21.5 took `0013` for `classifier-on-its-own-model` between this contract being written and the phase executing; the slug `cost-approximation-by-design` is unchanged and every 22-01 gate was slug-anchored, so none needed editing. `docs/adr/0014-cost-approximation-by-design.md` exists, carries `**Status:** Accepted`, the `## Context / ## Decision / ## Consequences` three-heading contract with `### Rejected alternatives`, and the four Admin-API rejection reasons. **Beyond the contract:** the reasons were **re-read at execution** and reason 1's quoted sentence could **not** be reproduced on any of Anthropic's three relevant pages — the ADR says so in the record and rests the reason on the current no-selectable-scopes text instead. The README cost bullet links it; `test -f` on the target resolves |
| 22-02 T1 (links) / T2 (gate) | 22-02 | 2 | REQ-limitations-recorded | **Surviving bullets all point at records:** identities → ADR-0007 (verify the existing link survives the rewrite), database → the new OPERATIONS posture note (anchor exists), cost → ADR-0013 | link gate | every relative link in the Limitations section resolves to an existing file/anchor; mutation: rename the OPERATIONS anchor → red | **PASS** — four link targets extracted from the section and each resolved: `docs/adr/0014-cost-approximation-by-design.md`, `docs/adr/0007-anonymous-identity-fairness-global-cap.md`, `docs/adr/0013-classifier-on-its-own-model.md` (the intro's classifier pointer), and `docs/OPERATIONS.md#the-free-tier-posture-and-the-upgrade-path`. No BROKEN lines. The anchor was **re-derived from the heading text** (lowercase, punctuation stripped, spaces→hyphens) rather than string-matched: `### The free-tier posture, and the upgrade path` → `the-free-tier-posture-and-the-upgrade-path`, matching README's fragment. ADR-0007 confirmed `Status: Accepted — supersedes ADR-0006` and its bullet **verified, not re-authored** (byte-identical through the rewrite). **Mutation observed:** heading renamed posture→stance → anchor gate RED naming the fragment and reporting the heading that now derives `the-free-tier-stance-and-the-upgrade-path`. Reverted, byte-identical |
| 22-01 T2 | 22-01 | 1 | REQ-limitations-recorded | **OPERATIONS database posture note** carries the verified facts (region, tier, 60-connection ceiling with ~10 held, no read replica, the upgrade path) and the genuinely-new "deliberate posture" framing the researcher confirmed exists nowhere today | prose + grep | facts cross-checked against the sources OPERATIONS already carries at :176/:292, not against the README bullet being replaced | **PASS** — `### The free-tier posture, and the upgrade path` landed under `## Going stateless`, beside the argued "Why Supabase and not Neon" sibling rather than inside the "Supabase specifics" runbook. Heading count 1; `read replica` now appears 4× in OPERATIONS (**0 before this phase**); upgrade/tier vocabulary 6× inside the section. Every fact traces to an OPERATIONS passage or is labelled unsourced, and **none traces to the README bullet being replaced**. Pitfall 3 cleared on substance, not layout: the section adds the *argument* (connections bounded by `PG_POOL_MAX_SIZE`, so the fleet holds 10 of 60 and would have to grow six-fold; `/health` store probes at 2.84/3.23/3.39 ms p50 against a 3000 ms budget, ~435× headroom, so a replica would relieve a primary that is not struggling; the ~7-day idle pause *prevented* by the same probes that disqualified Neon) and the **upgrade path including what it does not fix** — tier is a reversible toggle, region is a one-way door. Assumption A2 is stated **as a caveat**: no-read-replica is carried from the tier's published shape, not measured here, and wrong in the safe direction if wrong |
| 22-01 T3 | 22-01 | 1 | REQ-limitations-recorded | **The two paid-run defects recorded** where the researcher argued they live (README eval-section prose), with their evidence (truncation site graders.py:758, the six divergences in REFUSALS.json), and a derived-counts gate in the house pattern so the prose numbers cannot drift from the JSON | unit | mutation: change a REFUSALS.json count → the derived-counts test reds against the stale prose | **PASS, and the gate found a real defect on its first run.** Both defects are recorded in README's eval-section prose with their evidence (`Judge.verdict`'s own docstring in `evals/graders.py` predicting the `max_tokens=1500` truncation; the six divergences in `REFUSALS.json`) and the reason neither is fixed here (ADR-0012 owns the judge's configuration; the contested pins must also satisfy `dataset.py`'s hand-authored reference reports, and re-authoring was tried and reverted). `test_the_readme_eval_counts_are_derived_from_the_tree` derives everything through `F.fixture_paths()`, `documented_refusals()`, `len(GOLDEN)` and `_SPELLED` — no literal count. **The RED was not manufactured:** on its first execution it failed on a claim nobody had ever quantified — the prose said *"Most refusals are the machinery working"* with no number, leaving the largest of the three kinds (7 grader) unstated anywhere in the milestone. Two additions beyond the contract: the test holds the **kind list** (`set(kinds) <= set(phrases)`), so a third defect category cannot leave both quoted counts correct and the paragraph silently incomplete, and it implements the **zero branch** (a kind that falls to zero must be dropped from the prose, not written as a zero) across every spelling. **Mutation observed:** `technical-version-numbers` popped from `REFUSALS.json` → **2 gates red on 2 different axes** — the derived-counts gate on stale prose, the union gate on a case accounted nowhere. Restored byte-identically, both green |
| 22-02 T1 (intro) / T2 (read-through) | 22-02 | 2 | REQ-limitations-recorded | **Intro rewritten:** states v1.2 closed four, recorded three by design, and what the paid run discovered — remainder chosen/recorded/argued. Whole-README read-through for anything the rewrite falsifies | prose | cannot be automated: routed to the SUMMARY and the user's PR read; the falsification sweep IS automated (the no-orphan greps) | **DONE — prose routed to the user, mechanical half automated and green.** The intro states all three: v1.2 **closed four**, **three remain** and each ends at a record, and the paid run **found three things free testing structurally could not see** (the classifier mislabelling at 32/38 vs Opus 5's 37, fixed in 21.5; the judge truncation and the record/replay divergence, recorded not fixed). It ends on the criterion-5 phrase **verbatim**, gated by `grep -cF 'chosen, recorded, and argued for' ≥ 1` — which went **RED on the first attempt** because the hard-wrap split the phrase across a newline, and was fixed by reflowing rather than by weakening the gate. The section holds **exactly three bullets** (P-07). **Quoted verbatim in 22-02's SUMMARY for the user's PR read — that judgement is the user's and is not claimed here.** Whole-README read-through done end to end: three falsified counts re-derived (827→828 at `:15` and `:199`; "twelve now"→"fourteen now" at `:40`, with "four of them superseded" re-derived from the files and left standing because it is still correct), and one claim checked and deliberately **left** (`:191`'s "20 other calls" — DESIGN.md has no per-decision heading to count, and nothing this phase did falsified it) |
| 22-02 T3 | 22-02 | 2 | REQ-limitations-recorded | **Close-out flips:** REQUIREMENTS checkbox + traceability (REQ-limitations-recorded; verify 21.5 flipped REQ-classifier-model), ROADMAP progress, STATE — hand-edited; the two Phase-20 deferred items (PROJECT.md counts, CONCERNS.md:242) settled or their disposition stated | checklist | `gsd-tools` state parse after the hand edit; grep the deferred items' fates | **PASS** — `REQ-limitations-recorded` flipped `[x]` with a dated evidence block and its traceability row moved Pending → **Complete**; **zero** `Pending` cells remain. `REQ-classifier-model` **verified already flipped by 21.5** (checkbox and row both carrying the measured 37/38-vs-32/38 result) — verified, not re-flipped. **One miss found and corrected:** `REQ-note-count-bound` read `[ ]` while its own traceability row had said **Complete** since 2026-08-15 (verified, deployed Fly v19) — flipped here on Phase 20's behalf and recorded as a correction rather than done silently. Coverage stays 8/8 mapped, with a new line stating **6 of 8 checked** and naming the two that are verified-but-awaiting-deploy rather than incomplete. ROADMAP: Phase 22 box and **both** plan boxes checked (`grep -c '\[x\] 22-0[12]-PLAN.md'` = 2), executed-record paragraph appended in Phase 21's style, Progress row moved `0/TBD` → `16/16`, and **no milestone-archive edit made**. STATE: front matter (`completed_phases` 4→6, plans 12→16, 100%), `stopped_at`, Current Position, Performance Metrics and Session Continuity all hand-edited, `state.load` **parses**, and the open Phase-19 Manual-Only items are carried forward rather than dropped. PROJECT.md settled to the measured 828/72/900 (plus two adjacent corrections this milestone had falsified). Both Phase-20 deferred items carry written fates: counts **SETTLED**, `CONCERNS.md` **DISPOSITIONED unedited** per P-08 |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| The section reads as an honest ledger | Prose quality is the deliverable; no grep proves tone | The PR body quotes the new intro verbatim; the user judges it at review — **OPEN, and correctly so.** The intro is quoted verbatim in 22-02's SUMMARY and belongs in the PR body. The mechanical half is green (criterion-5 phrase verbatim, three bullets, all links resolving); the *tone* judgement is the user's and is not claimed as passed here |
| The close-out claim ("no bullet stands uncovered") | It is the milestone's acceptance bar, and it is a reading, not a count | Verification walks every surviving bullet to its record and says so per bullet — **OPEN for `/gsd:verify-work`**, which has not run (no `22-VERIFICATION.md` exists). The walk is *prepared* rather than performed here: cost → ADR-0014 argues cost-approximation-by-design **and** the rejection of invoice reconciliation, which is what the bullet claims; identities → ADR-0007 argues fairness-not-a-bill-bound with the global cap as backstop, which is what the bullet claims; database → the OPERATIONS posture note argues acceptability at this traffic **and** the upgrade path, which is what the bullet claims. Recorded as a reading for the verifier to confirm, not as a gate this plan passed |

---

## Validation Sign-Off

- [x] Execution baseline re-measured before any edit (post-21.5 numbers) — 828/72/900, evals 65/65, 25/15 split; every planning placeholder drifted and none was carried
- [x] Four deletions verified on the git axis; no-orphan sweep clean; every mutation observed red — each phrase in once (`+`) and out once (`-`, `219e9e3`); sweep returns **zero hits, exemption list empty**; **all four named mutations** observed red and reverted (restored bullet; planted DESIGN.md claim; renamed OPERATIONS heading; popped `REFUSALS.json` entry), plus 22-01's ADR-index-row mutation, for **five** total
- [x] ADR-**0014** landed in the house shape; all Limitations links resolve — *the number changed*: 21.5 took 0013 between planning and execution, the slug did not move, and every slug-anchored gate passed unedited
- [x] Suite + evals green at the measured denominator; ruff clean — 828 passed / 72 skipped; `PASS 65/65` with a real `$?` of 0; `All checks passed!`
- [x] Milestone flips done and parsed — REQUIREMENTS (plus one Phase-20 miss corrected), ROADMAP, STATE (`state.load` parses), PROJECT, both deferred items
- [x] `nyquist_compliant: true` at reconciliation

**Two things this contract records as NOT done, deliberately, so the tick above means what it says:**
1. **Phase verification has not run** — no `22-VERIFICATION.md` exists. Both Manual-Only rows stay OPEN and say why.
2. **No milestone archival.** `/gsd:complete-milestone` owns it; this phase was explicitly fenced out and did not touch it.

**Approval:** executed and reconciled 2026-08-16. Every automated row carries measured
evidence — command, observed result, and what the recorded mutation did. The two Manual-Only
rows are open with written reasons rather than ticked on a promise.
