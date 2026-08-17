---
phase: 21-forty-recorded-answers
verified: 2026-08-17T02:16:35Z
status: gaps_found
score: 4/4 roadmap success criteria verified (criterion 1 against its ratified amendment)
method: >-
  Goal-backward, run RETROSPECTIVELY — the phase shipped 2026-08-15 and merged as PR #30
  without ever being verified; the omission surfaced two days later during
  /gsd:complete-milestone. Every criterion re-proven from the tree, from git, and from the
  five report JSONs. Five mutations applied and observed (four red, one GREEN — that one is
  the phase's real gap), the money recomputed from the reports, the phase-close gates
  reproduced in a detached worktree at 14d4856. Both wave SUMMARYs are themselves
  RECONSTRUCTED (2026-08-17, from evidence, banner-labelled) and were read with extra
  suspicion — as claims to falsify, never as evidence.
retrospective: true
verifier_mutations: 5      # 4 observed red; 1 observed GREEN and that is gap 1
verifier_recomputations: 6 # spend, per-batch counts, judge calls, union from disk, refusal kinds, phase-close gates
overrides_applied: 0
behavior_unverified: 0
re_verification: false

# Gates re-run by the verifier, not read from any SUMMARY
gates:
  full_suite_today: "834 passed, 72 skipped in 30.05s, exit 0 — `.venv/bin/pytest -p no:warnings` (no second -q, counts visible)"
  full_suite_at_phase_close: "806 passed, 72 skipped in 28.27s — reproduced in a detached worktree at 14d4856, the phase's last commit. Matches 21-03-SUMMARY exactly"
  offline_evals_today: "PASS 65/65 (100% vs 90% required), real $? = 0 — `ANTHROPIC_API_KEY='' VOYAGE_API_KEY='' .venv/bin/python -m evals --quiet`"
  offline_evals_at_phase_close: "PASS 59/59, real $? = 0, reproduced at 14d4856. Matches 21-03-SUMMARY's claimed denominator (40 behavioural + 19 replayed) exactly"
  ruff_at_phase_close: "All checks passed! — `.venv/bin/ruff check .` in the 14d4856 worktree"
  ci_on_the_real_push_axis: "`.github/workflows/ci.yml` triggers on push to `branches: ['**']`; the Evals step exports ANTHROPIC_API_KEY='' VOYAGE_API_KEY='' DATABASE_URL='' and runs `python -m evals --report ... --min-pass-rate 0.9`. `gh run list --commit 19dfc8ce` (the PR #30 merge) → conclusion success"
  union_from_disk_at_phase_close: "19 fixtures + 21 refusals = 40 golden, overlap []; kinds {grader: 13, judge_truncated: 2, recorded_then_failed_replay: 6}; every entry carries a non-empty detail. Read from `git show 5c38735:evals/REFUSALS.json` and `git ls-tree 5c38735 evals/fixtures`"
  union_from_disk_today: "25 fixtures + 15 refusals = 40, overlap [], zero orphan refusals, zero orphan fixtures; kinds {grader: 7, judge_truncated: 2, recorded_then_failed_replay: 6} — the post-21.5 split, not a Phase 21 regression"
  settled_judge_data: "all 19 fixtures at 5c38735 carry `models.judge == claude-opus-4-8`; all 25 today do too, compared against `graders.DEFAULT_JUDGE_MODEL` resolved at import. Zero stale"
  nothing_forced: "`grep -rn '\"forced\"' evals/fixtures/` → 0 hits (the only matches for 'forced' anywhere in the fixtures are the `forced_stop_reason` state field). Independently: in every one of the five reports `written` == `passed`, so no write bypassed a failed grade"
  money_recomputed: "0.249561 + 1.901068 + 2.155575 + 2.202496 + 3.393240 = $9.901940 → the claimed $9.9019, 56.64% of the $17.4812 quote (claimed 56.6%). Per-batch actuals match the reconstructed table to 4dp; judge calls 2+17+22+20+24 = 85 as claimed"
  run_time_requote: "`record-quote-before.txt` is the re-quote resolved for 2026-08-15 (not the 08-13 quote): 40 cases / 11 follow-up turns / 91 judge calls, total $17.4812, basis '1 measured, 39 assumed — assumed tokens dominate this quote', ending 'estimate — treat as an upper bound; run a one-case calibration first'"
  working_tree: "clean at start; clean after all five mutations were reverted; clean at end. The worktree used for the phase-close reproduction was removed"

# Mutations the verifier applied itself. The fifth is the finding.
mutations:
  - name: "union gate — unaccounted arm"
    applied: "popped `chatty-label-falls-back` from evals/REFUSALS.json"
    result: "RED — `test_every_golden_case_is_recorded_or_documented_as_refused` fails naming 'chatty-label-falls-back'. Restored"
  - name: "union gate — overlap arm (the load-bearing one)"
    applied: "added a refusal entry for `contested-viewpoints`, which HAS a committed fixture"
    result: "RED — `AssertionError: recorded AND listed as refused -- stale refusal record: ['contested-viewpoints']`. This is the arm that forces a successful re-record to delete its refusal in the same commit; Phase 21.5 depended on it and it genuinely bites. Restored"
  - name: "union gate — orphan-refusal arm"
    applied: "added a refusal naming `a-case-that-does-not-exist`"
    result: "RED — `refusal names no golden case: ['a-case-that-does-not-exist']`. Restored"
  - name: "union gate — orphan-fixture direction"
    applied: "copied a fixture to `evals/fixtures/no-such-golden-case.json`"
    result: "RED — `assert (26 + 15) == 40`. The totality assertion catches the fourth direction the three named arms do not. Removed"
  - name: "replay leg — corrupt a recorded answer"
    applied: "set `turns[0].state.draft = 'garbage'` in technical-figures.json"
    result: "RED with a real non-zero exit — `EVALS_EXIT=1`, '1 recorded case(s) failed replay: technical-figures@recorded: recorded_coverage ... recorded_structure: a report must open with a markdown heading; got 'garbage'' and 'replay is all-must-pass'. Restored via git checkout"
  - name: "settled judge — stale judge in a committed fixture"
    applied: "set `models.judge = 'claude-opus-5'` (the superseded judge) in technical-figures.json"
    result: "**GREEN. Nothing caught it.** Full suite 834 passed / 72 skipped; offline evals PASS 65/65 with a real exit 0. See gap 1. Restored"

gaps:
  - truth: "The judge pin proves the committed fixtures carry the settled judge's verdicts; flipping one fixture's judge field reds it naming the file (21-03-PLAN must_haves; 21-VALIDATION per-task row 2)"
    status: failed
    reason: >-
      The planned real-directory pin `test_every_fixture_carries_the_settled_judge_verdict`
      was never written. `git log -S` over all branches finds the name in no commit, in no
      test file — only in 21-01-SUMMARY and the two PLANs that promised it. The helper it was
      to call, `stale_judges()`, EXISTS and is unit-tested in both directions, but only ever
      against synthetic tmp directories (tests/test_evals.py:2598, :2611). It is never once
      called with no argument — the real tree. Verified by mutation, not by reading: a
      superseded judge planted in a committed fixture leaves the suite at 834 green and the
      evals at 65/65 exit 0. `grade_fixture_current` deliberately does not check the judge
      (that divergence is documented and correct), so nothing else covers it.
      The DATA is true — all 19 fixtures at close and all 25 today carry
      claude-opus-4-8 — so criterion 1's metadata half holds as a measurement. What is
      missing is the gate that would keep it true. The omission is recorded nowhere: no
      SUMMARY, no deviation note, no deferred item names it.
    artifacts:
      - path: "tests/test_evals.py"
        issue: "`stale_judges()` has no real-directory caller; the promised pin (with its len(GOLDEN) non-vacuity guard) is absent"
    missing:
      - "A real-tree pin asserting `stale_judges() == []`, with a non-vacuity guard so a scan over zero files cannot pass — over the fixtures that exist, since the amendment means that set is no longer 40"
      - "Or, if the pin is judged unnecessary now, an explicit written decision saying so — the current state is silent omission, which is the one option the phase's own risk register (T-21-09, 'the real-directory pins weakened to pass an incomplete set') was written to prevent"
  - truth: "The phase's validation contract is reconciled at close (21-VALIDATION sign-off: `nyquist_compliant: true` set at reconciliation)"
    status: failed
    reason: >-
      `21-VALIDATION.md` still reads `status: draft`, `nyquist_compliant: false`,
      `wave_0_complete: false`, with all six sign-off boxes unticked and 'Approval: pending
      execution' — for a phase that merged two days ago. Every per-task row still reads
      `pending`. Compare `22-VALIDATION.md`, which carries `status: complete`,
      `nyquist_compliant: true`, `reconciled: 2026-08-16`. The file was edited once during
      the phase (713d172) to add the criterion amendment and never reconciled afterwards.
      The substance is not in doubt — this verification reproduces the gates the contract
      asked for — but the phase's own record says its validation never happened.
    artifacts:
      - path: ".planning/phases/21-forty-recorded-answers/21-VALIDATION.md"
        issue: "frontmatter and sign-off left in the pre-execution state; all seven per-task rows read `pending`"
    missing:
      - "Reconcile the frontmatter and per-task rows against measured evidence (this report supplies it), or record deliberately why it was left in draft"

# Errors found IN the two reconstructed SUMMARYs. They claim every number is re-derived
# from evidence; three claims are not, and one is attributable to the wrong phase.
reconstruction_errors:
  - claim: "21-03-SUMMARY: 'One test went stale by the phase's own success. `test_cli_writes_the_report` pinned `len(report[\"cases\"]) == 1` for `general-summary` ... Fixed deliberately'"
    verdict: "WRONG PHASE — this is Phase 21.5's work, not Phase 21's"
    evidence: >-
      `general-summary` was REFUSED in Phase 21 (batch A, topic_type) and appears in the
      21-refusal list at 5c38735; it had no fixture at this phase's close, so the `== 1`
      literal was still TRUE when Phase 21 ended. `git log -S 'len(report[\"cases\"]) == 1'`
      and `git log -S 'if (F.FIXTURES_DIR / f\"{case_id}.json\").exists():'` both return the
      same single commit: 60c93e9, `feat(21.5)`. `evals/fixtures/general-summary.json` has
      exactly one commit in its history — also 60c93e9. The test's own docstring says it
      outright: 'Phase 21.5 recorded it and the literal went stale overnight.'
      The reconstruction credited Phase 21 with a fix Phase 21.5 made.
  - claim: "21-02-SUMMARY: 'Of the refusals, six were the identical mismatch — topic_type expected \\'general\\', got \\'technical\\''"
    verdict: "UNDERCOUNT — measured EIGHT"
    evidence: >-
      Reading the failing grades out of the five report JSONs, exactly eight cases carry that
      identical string: general-summary, general-defines-a-term, general-explains-a-concept,
      general-how-a-mechanism-works, empty-label-falls-back, injection-tries-to-force-approval,
      followups-chain-of-three, followup-with-no-prior-research. Phase 21.5's own verification
      independently re-derived the same eight from `REFUSALS.json` and its re-record report
      shows `topic_type {passed: 8, failed: 0}`. 'Six' is 21.5's RE-RECORD count (six of eight
      landed), imported backwards into Phase 21's refusal count. The error is not the
      reconstruction's invention — `STATE.md` has said 'six identical topic_type mismatches'
      since 2026-08-15 — but the reconstruction repeated it while claiming re-derivation.
      The adjoining clause 'hitting every general-* case' is true, and there are four such cases.
  - claim: "21-02-SUMMARY: 'Three grader-quality refusals (max_revisions_exceeded) and two judge_grounding catches ... complete the set'"
    verdict: "The counts are right; 'complete the set' is not"
    evidence: >-
      Three cases do fail on `max_revisions_exceeded` (empty-label-falls-back,
      technical-version-numbers, sparse-niche-ecosystem) and two on judge_grounding
      (technical-percentage-figures, sparse-vendor-incident-history) — both confirmed from the
      reports. But the enumeration double-counts empty-label-falls-back (it fails topic_type
      AND max_revisions) and omits `followup_research_bounded` entirely, which is the sole
      cause of followup-stays-inside-thin-notes' refusal and a contributing cause in two more.
      6+3+2+2 = 13 was never going to close over 15 record-time refusals.
  - claim: "21-03-SUMMARY: 'Every claim below is re-derived from commit 5c38735 ... README and OPERATIONS re-derived by measurement'"
    verdict: "Attribution imprecise, substance correct"
    evidence: >-
      The README/OPERATIONS pass is not in 5c38735; it is the separate later commit 14d4856,
      `docs(21): README and OPERATIONS reflect the measured record run`. Its content checks
      out exactly (799→806 tests at two sites, 'One case of forty'→'Nineteen cases of forty',
      41→59 cases, a new paragraph explaining REFUSALS.json and the three refusal kinds), and
      `git diff 713d172 14d4856 -- README.md | grep -c Limitations` = 0, so the byte-untouched
      Limitations claim holds. Only the commit attribution is loose.
  - claim: "21-02-SUMMARY: 'The re-quote still read `0 measured, 39 assumed`'"
    verdict: "UNSUPPORTED by any archived artifact — plausible but unevidenced"
    evidence: >-
      The phase directory holds the BEFORE quote (`record-quote-before.txt`, '1 measured, 39
      assumed') and the five reports. No post-calibration re-quote was captured, so this
      claim rests on the reconstructor's reading rather than on a file. Its own explanation is
      self-consistent (a case's measured basis comes from its own fixture, and technical-figures
      was no longer in the remaining 39), and the adjacent arithmetic it supports DOES check
      out: the quote's assumed judge share is $0.3577 − $0.2427 = $0.1150, and $0.2496 + $0.1150
      = $0.3646, the 'roughly $0.365 against $0.3577' the summary reports. Flagged, not disputed.

# Not gaps. Recorded so /gsd:complete-milestone inherits the fact rather than the silence.
warnings:
  - finding: "The original, literal wording of criterion 1 was NOT met, and the milestone archive should inherit that sentence rather than the amended one alone"
    evidence: >-
      ROADMAP criterion 1 as written reads 'All 40 golden cases have a fixture carrying a real
      recorded answer plus the settled judge's verdict as metadata.' The phase closed with 19
      fixtures; today there are 25. Forty was never reached and, under the ratified amendment
      and the refusal of `--force`, was never going to be. Everything downstream of the
      amendment is honest — the ROADMAP line, the REQUIREMENTS entry and the README all state
      the split as a measured fraction rather than rounding to forty — but a reader of the
      archive should be able to find the unmet literal stated as such, in one sentence, which
      is what this row is.
    why_it_counts: "A milestone archive that only records the amended criterion reads as if the target was hit. It was not; it was renegotiated with evidence, mid-run, with the user's ratification, and the renegotiation is the better engineering. Both halves belong in the record."
  - finding: "The reconstructed wave-2 table's `total` row reads 25 recorded / 15 refused, which numerically coincides with TODAY's post-21.5 split while meaning something different"
    evidence: >-
      The table's columns are record-time outcomes: 25 cases were successfully recorded during
      the paid run, 15 were refused (both re-derived and confirmed against the reports). Six of
      those 25 then failed replay and were moved into REFUSALS.json, which is how the phase
      closed at 19/21. Phase 21.5 later re-recorded six different cases and arrived at 25/15
      again — the same pair of numbers, a different fact. The row is correct; nothing in the
      summary warns the reader of the collision, and the wave-3 summary's closing line
      ('19 recorded / 21 documented refusals ... Phase 21.5 later moved it to 25/15') is the
      only thing that disambiguates it.
    why_it_counts: "A future reader diffing the wave-2 table against today's tree will find them agreeing for the wrong reason."
  - finding: "The 19 Phase-21 fixtures carry no `models.classifier` key; the 6 recorded by Phase 21.5 do"
    evidence: "Measured across all 25: 19 have {pipeline, judge, critic}, 6 have {pipeline, judge, critic, classifier}. This is Phase 21.5's deliberate design (classifier recorded as provenance, compared nowhere — commit 3bd8224) and nothing grades the difference. Not a Phase 21 defect; recorded because a fixture-schema audit will find it."
    why_it_counts: "It is the only structural asymmetry inside evals/fixtures/, and it has a documented cause."

# Verifier notes. None changes the verdict.
notes:
  - "Criterion 2's literal wording — 'every push replays and grades all 40 cases keylessly' — is met on a reading worth stating precisely. All 40 golden cases are graded behaviourally on every push (the denominator is 40 + however many recordings exist: 41 before the phase, 59 at its close, 65 today). What is partial is the REPLAY leg, which can only cover cases that have fixtures. The criterion's own 'replays and grades' is satisfied for the 19/25 recorded and the 'grades keylessly' half for all 40, with no live key anywhere: CI exports empty ANTHROPIC_API_KEY, VOYAGE_API_KEY and DATABASE_URL, and the verifier reproduced exit 0 locally under the same emptied environment at both the close commit and HEAD."
  - "Criterion 3 is verified in the machinery, not only in the record. `evals/__main__.py:653` computes `ok = summary['ok'] and not replay_failures and not ungraded and not refused` — a refusal alone makes the record run exit non-zero, which is the structural form of 'a finding, not silence'. :679-686 prints 'N case(s) were NOT recorded' in red with each case id and its refusal string, and two tests pin that exact string (:2972, :3708). `grep -rn 'retry\\|retries' evals/__main__.py evals/fixtures.py` returns nothing — there is no auto-retry path to disable. The comment at :645 argues the point the criterion cares about: a refusal is 'the writer working, not a rate to average'."
  - "The refusal record is a finding record, not a list of excuses, and the gate says so. All 21 entries at close (and all 15 today) carry a `kind` from a closed set and a non-empty `detail`; `test_documented_refusals_say_why_and_distinguish_defect_from_judgement` asserts both, plus that `judge_truncated` is still PRESENT — so the phase's one infrastructure defect cannot be quietly reclassified into the pile of quality refusals. Two cases carry it (chatty-label-falls-back, followup-refuses-an-uncovered-figure), both traceable to a `ValueError: Judge verdict was TRUNCATED at max_tokens` in the reports' own error fields."
  - "'Nothing was forced' is the claim most worth attacking and it survives two independent checks. There is no `\"forced\": true` stamp anywhere in evals/fixtures/ (the recorder stamps exactly that key when `--force` is used, evals/fixtures.py:175). And in every one of the five reports the count of `written` recordings equals the report's `passed` count — 1/1, 7/7, 9/9, 4/4, 4/4 — so no fixture was written over a failed grade in the first place."
  - "The six recorded-then-failed-replay cases are visible on the git axis exactly as 21-03-SUMMARY describes. Five contested fixtures were ADDED in 47dd8d3 and DELETED in 5c38735 (the deletions are right there in the commit stat); the sixth, followup-refuses-a-forecast, was recorded in batch D and never committed at all. `evals/dataset.py` appears in NO Phase 21 commit, corroborating 'dataset.py ended the phase unmodified' — the pin re-authoring was tried and reverted, as claimed."
  - "The phase's money story is the strongest-evidenced thing in it and it survives recomputation to the cent. Quote $17.4812 (archived, run-time, 2026-08-15 rates); actual $9.901940 summed from the five reports' own `summary.cost_usd`, which in turn equal the sums of their per-case costs to 6dp. The 'metered pipeline only; 85 judge calls bill separately' caveat is the recorder's own language and is stated rather than folded into a better-looking number — as is the calibration correction, where the flattering 30%-under reading was withdrawn in favour of ~$0.365 vs $0.3577."
  - "Phase 21.5 falsifies nothing in Phase 21's artifacts. It moved the split from 19/21 to 25/15 and both the ROADMAP's 21.5 line and 21-03-SUMMARY's closing sentence say so explicitly. The one place the drift could mislead is the wave-2 table's total row (warning 2). REFUSALS.json's `recorded_on: 2026-08-15` and `judge_model: claude-opus-4-8` are both still accurate — 21.5 changed the CLASSIFIER model, not the judge, and `graders.DEFAULT_JUDGE_MODEL` still resolves to claude-opus-4-8."
  - "This phase was verified only because /gsd:complete-milestone went looking. The ROADMAP ticked both wave-2 and wave-3 plans `[x]` on 2026-08-15 while neither SUMMARY existed; they were written on 2026-08-17 (e6106f1) with a banner saying so. For one day the record was ahead of the evidence. That is worth naming in the milestone retrospective: the two waves that skipped their summaries are exactly the two the orchestrator executed inline rather than through an executor subagent, because both sat behind blocking spend checkpoints."

human_verification:
  - test: "Decide whether the missing settled-judge real-directory pin (gap 1) is closed before the milestone archives, or accepted and recorded."
    expected: "Either a small keyless test asserting `stale_judges() == []` over the real tree with a non-vacuity guard, or a written acceptance saying the pin is unnecessary and why."
    why_human: "It is a scope and risk judgement, not a correctness one. The data it would protect is true today on all 25 fixtures; what is missing is the guard against a future record run made with EVAL_JUDGE_MODEL exported — the exact scenario 21-01's P-03 argument was written about, and which the phase proved is undetectable without the pin. Closing it is roughly ten lines; the alternative is one honest sentence. Either is fine; silence is not."
  - test: "Decide whether 21-VALIDATION.md gets reconciled (gap 2) before archival."
    expected: "Frontmatter set to `status: complete` / `nyquist_compliant: true` with a `reconciled:` date and the per-task rows filled from this report's measured evidence — or a note recording that it was deliberately left in draft."
    why_human: "The evidence to fill it now exists in this report, but back-filling another phase's contract is an ownership call. Left as-is, the milestone archives with its most expensive phase reading 'Approval: pending execution'."
  - test: "Read the two reconstructed SUMMARYs' corrections above and decide whether to amend the files in place or leave the corrections living only here."
    expected: "A decision on the `test_cli_writes_the_report` mis-attribution and the six-versus-eight topic_type count — both are small factual edits with the evidence already assembled."
    why_human: "Amending a document explicitly labelled 'reconstructed from evidence' is a record-keeping judgement. Note that the 'six' error also sits in STATE.md, written contemporaneously on 2026-08-15, so a fix in one place leaves the other stale."
---

# Phase 21: Forty recorded answers — Verification Report

**Phase Goal:** All 40 golden cases carry a real recorded answer, replayed and graded
keylessly on every push.

**Verified:** 2026-08-17T02:16:35Z — **retrospectively**
**Status:** gaps_found (4/4 roadmap criteria verified; 2 gaps, neither a criterion failure)

## Why this ran late

The phase executed and merged on 2026-08-15 (PR #30, Fly v20) and was never verified. The
omission surfaced two days later while `/gsd:complete-milestone` was walking the milestone's
phases. Two of its three wave SUMMARYs did not exist either; they were reconstructed from
committed evidence on 2026-08-17 and carry a banner saying so, because waves 2 and 3 were
executed inline by the orchestrator rather than by executor subagents — both sat behind
blocking spend checkpoints only the orchestrator could obtain.

That makes this verification unusual in one specific way: the SUMMARYs are not
contemporaneous records but after-the-fact reconstructions, so they were treated as claims
to falsify rather than as evidence. Every number below comes from the tree, from git, or
from the five archived report JSONs. Where a reconstruction is wrong, it is named in the
`reconstruction_errors` block above rather than smoothed over.

**The headline: the phase goal is achieved under its ratified amendment, and the two gaps
are gate hygiene and record hygiene, not criterion failures.** The phase can be archived
honestly, provided the archive carries the sentence in the next section.

## The literal criterion, stated plainly

The original wording of success criterion 1 — *"All 40 golden cases have a fixture carrying
a real recorded answer plus the settled judge's verdict as metadata"* — **was not met.** The
phase closed with **19** fixtures of 40. Today, after Phase 21.5's re-record, there are 25.

It was not met because it could not be, and the phase proved that rather than assumed it.
Batch A refused 3 of 10 on the real pipeline, exposing REQ-forty-recorded-answers' own two
clauses as incompatible: *all forty recorded* against *a committed fixture is one the graders
and the judge approved*. The criterion was amended mid-execution with the user's ratification
and the amendment recorded in `21-VALIDATION.md` (commit 713d172, `docs(21): record the
ratified criterion amendment`): **every case is either recorded or carries a documented
refusal**, the union enforced by test, nothing forced.

Verification below is against the amended criterion. Both facts belong in the archive.

## Goal Achievement

### Success Criteria

| # | Criterion | Status | Measured evidence |
|---|-----------|--------|-------------------|
| 1 | All 40 golden cases carry a real recorded answer with the settled judge's verdict as metadata — **amended, user-ratified: recorded OR documented refusal** | ✓ VERIFIED (amended) · ✗ original literal wording NOT met | At close (`5c38735`): **19 fixtures + 21 refusals = 40**, overlap `[]`, zero orphan refusals. Today: **25 + 15 = 40**, same properties, recomputed from disk against `dataset.GOLDEN`. Judge metadata: **all 19 fixtures at close and all 25 today** carry `models.judge == claude-opus-4-8`, compared against `graders.DEFAULT_JUDGE_MODEL` rather than a literal or the env-resolved `JUDGE_MODEL`. Nothing forced: zero `"forced"` stamps, and `written == passed` in all five reports. The union is enforced by `test_every_golden_case_is_recorded_or_documented_as_refused` — **four mutations applied, four reds observed** (unaccounted, overlap, orphan refusal, orphan fixture). The overlap arm, which forces a re-record to delete its refusal in the same commit, is the one Phase 21.5 depended on and it bites. **Gap:** the judge half is true as data but unguarded — see gap 1 |
| 2 | Every push replays and grades all 40 cases keylessly, no live API key | ✓ VERIFIED | `.github/workflows/ci.yml` triggers `on: push: branches: ["**"]`; the Evals step exports `ANTHROPIC_API_KEY=""`, `VOYAGE_API_KEY=""`, `DATABASE_URL=""` and runs `python -m evals --min-pass-rate 0.9`. `gh run list --commit 19dfc8ce` (the PR #30 merge) → **success**. Reproduced locally with keys emptied: **59/59 exit 0** at the phase's close commit in a detached worktree, **65/65 exit 0** today. All 40 golden cases are graded behaviourally on every push; the replay leg covers the recorded ones, and the denominator grew honestly 41 → 59 → 65 rather than being held flat. **Mutation:** corrupting a recorded answer's draft produced `EVALS_EXIT=1` naming the case and the two failing pins, with 'replay is all-must-pass' — the leg is not decorative |
| 3 | A refused case is surfaced as a finding, not silently retried or dropped | ✓ VERIFIED | Structural, not merely documented: `evals/__main__.py:653` — `ok = summary["ok"] and not replay_failures and not ungraded and not refused`, so a refusal alone makes the record run exit non-zero; `:679-686` prints `N case(s) were NOT recorded` in red with each case id and its refusal reason, pinned by two tests. **No retry path exists** (`grep retry` over the recorder returns nothing). In the record: all 21 refusals at close carry a `kind` from a closed set and a **non-empty** detail, `judge_truncated` is kept distinct from `grader` and asserted PRESENT so the infrastructure defect cannot be reclassified into the quality pile. The 15 record-time refusals in `REFUSALS.json` reconcile case-for-case with the reports' own refusal strings; the other 6 are `recorded_then_failed_replay`, whose five deletions are visible in `5c38735`'s commit stat |
| 4 | The paid checkpoint is re-quoted at run time and actual spend reported against the quote | ✓ VERIFIED | `record-quote-before.txt` is the run-time re-quote **resolved for 2026-08-15** (not the 08-13 figure): 40 cases / 11 follow-up turns / 91 judge calls, per-case lines, **total $17.4812**, basis `1 measured, 39 assumed — assumed tokens dominate this quote`, closing 'treat as an upper bound; run a one-case calibration first'. Actual, recomputed by the verifier from the five reports: 0.249561 + 1.901068 + 2.155575 + 2.202496 + 3.393240 = **$9.901940**, i.e. the claimed **$9.9019 = 56.64%** of quote (claimed 56.6%). Every per-batch actual in the reconstructed table matches to 4dp; judge calls sum to **85** as claimed. The 'metered pipeline only, judge calls bill separately' caveat is the recorder's own and is stated rather than absorbed |

**Score: 4/4** roadmap criteria verified, criterion 1 against its ratified amendment and
explicitly NOT against its original literal wording.

### Gates reproduced, not read

| Gate | At phase close (worktree at `14d4856`) | Today (HEAD) | Claimed |
|------|----------------------------------------|--------------|---------|
| Full suite, keyless | **806 passed / 72 skipped** | 834 passed / 72 skipped | 806/72 ✓ exact |
| Offline evals, real `$?` | **59/59, exit 0** | 65/65, exit 0 | 59/59 exit 0 ✓ exact |
| `ruff check .` | **All checks passed!** | clean | clean ✓ |
| Union from disk | 19 + 21 = 40, overlap `[]` | 25 + 15 = 40, overlap `[]` | 19/21 ✓ |

The drift from 19/21 to 25/15 is **Phase 21.5's re-record**, not a Phase 21 regression, and
both the ROADMAP and 21-03-SUMMARY say so.

### Anti-patterns

None found in the phase's own surfaces. No `TODO`/`FIXME`/`XXX`/`HACK` markers in
`evals/REFUSALS.json` or in the 70 lines `5c38735` added to `tests/test_evals.py`. No stub
returns, no hardcoded empty data, no forced fixtures. The one thing that looks like an
anti-pattern and is not — 15 golden cases without recordings — is the ratified amendment, and
it is documented in four places.

## Gaps Summary

Two, and neither one touches a success criterion.

**1 — The settled-judge pin was planned, contracted, and never written.** `21-03-PLAN`'s
must_haves promise `test_every_fixture_carries_the_settled_judge_verdict` calling
`stale_judges()` against the real tree with a non-vacuity guard; `21-VALIDATION`'s row 2
requires it with a mutation red naming the file. `git log -S` over all branches finds the
name in no commit. The helper exists and is proven red-both-ways — but only on synthetic
tmp directories; it is never called with no argument. The verifier planted the superseded
judge `claude-opus-5` in a committed fixture and the suite stayed at **834 green** with
evals at **65/65 exit 0**. The data is right; the guard is absent; the absence is written
down nowhere. Phase 21's own risk register named this exact failure mode (T-21-09).

**2 — The validation contract was never reconciled.** `21-VALIDATION.md` still reads
`status: draft`, `nyquist_compliant: false`, every per-task row `pending`, every sign-off box
empty, 'Approval: pending execution' — for a phase merged two days ago and deployed. The
evidence to fill it exists and much of it is in this report.

**And three factual errors in the reconstructed SUMMARYs**, listed in full above. The most
consequential: 21-03-SUMMARY claims the `test_cli_writes_the_report` staleness and its fix
as Phase 21's, when git shows both belong entirely to Phase 21.5 (`60c93e9`) — the case in
question, `general-summary`, was still refused when Phase 21 closed. The reconstructions
were otherwise careful: the phase-close gates they claim reproduce **exactly**, and every
figure in the money table survives recomputation to the cent.

## Can this phase be archived honestly?

**Yes**, provided the archive carries three sentences it does not carry today: that the
original criterion 1 was not met and was renegotiated with evidence; that the settled-judge
pin the plan promised does not exist; and that the two paid waves' records are
reconstructions rather than contemporaneous notes. The engineering underneath is sound and
unusually well evidenced — five paid stages under explicit checkpoints, $9.90 against a
$17.48 quote reproduced to the cent, a union gate that bites in four directions, and a
refusal record that treats an infrastructure defect as distinct in kind from a quality
judgement. What is missing is bookkeeping, and it is nameable in a paragraph.

---

_Verified: 2026-08-17T02:16:35Z (retrospective)_
_Verifier: Claude (gsd-verifier)_
