# Phase 22: Limitations recorded - Context

**Gathered:** 2026-08-15
**Status:** Ready for research
**Source:** Milestone-questioning decisions (user-ratified 2026-08-13) plus what Phases
18–21 actually produced. **Planned before Phase 21.5 executes, deliberately** — the user
asked for this planning now — so every count, list and split this phase touches is a
claim to re-measure at execution, never a number to carry from these documents.

<domain>
## Phase Boundary

The milestone's close-out. The README's Limitations section is rewritten around what
genuinely survives: the closed bullets are DELETED (never rewritten into release notes,
the standing convention), each surviving limitation points at a record (ADR, OPERATIONS
note, or refusal file), and the intro states plainly that what remains is chosen,
recorded, and argued for. The milestone's acceptance bar is that no bullet stands
uncovered — closed things gone, open things owned.

**Sequencing (user-ratified today):** Phase 22 executes LAST, after Phase 21.5
(classifier on Opus 5) — so the close-out records only what survives the classifier fix
and its re-record checkpoint. Planning happens now; execution waits.

**Not in this phase:** fixing anything. The judge-truncation defect, the record/replay
grading divergence, and whatever refusal residue 21.5 leaves are RECORDED here, not
repaired — repairs are successor-milestone work. No grader, judge, dataset, or pipeline
changes. No milestone-archive mechanics (`/gsd:complete-milestone` is its own step after
this phase merges).

</domain>

<decisions>
## Implementation Decisions (from milestone questioning, still binding)

### The five roadmap criteria, verbatim commitments

1. A new ADR states the **cost-approximation-by-design** position and why invoice
   reconciliation via Anthropic's Admin cost API was rejected.
2. The **mintable-identities** limitation points at ADR-0007 instead of standing bare.
3. The **free-tier-database** limitation points at a database posture note in
   OPERATIONS.md.
4. The closed bullets are **deleted** — judge independence (:295), credential validity
   (:299), the note count bound (:301), and the recorded-answers bullet (:296), which
   Phase 21 falsified in an amended form. Deletion, never a rewrite into release notes.
5. The section intro states that what remains is **chosen, recorded, and argued for**.

### What v1.2's own execution added to the record (the part the 2026-08-13 plan
could not have known)

- **The recorded-answers bullet's replacement must tell the amended truth**: 19 recorded
  + 21 documented refusals (numbers as of 2026-08-15; Phase 21.5's checkpoint will move
  some), the union enforced by test, refusals in `evals/REFUSALS.json`. Whether the
  final state warrants a *surviving* limitation bullet (the refusal residue) or only the
  honest prose in the eval section is the planner's call — but the residue is recorded
  somewhere that outlives this phase either way.
- **Two defects discovered by the paid run are recorded as known defects**, distinct
  from chosen limitations: the judge's verdict truncating at `max_tokens=1500` (shared
  with adaptive thinking — `graders.py:758` predicted it; it cost two recordings), and
  record-time vs replay-time grading disagreeing (six fixtures passed record-time and
  failed replay; the contested-case pins cannot be re-authored without weakening them
  against `dataset.py`'s reference reports). Where they live — Limitations bullets, an
  ADR, a KNOWN-DEFECTS note — is the researcher/planner's question; that they are
  written down with their evidence is not negotiable.
- **The milestone's acceptance bar is met honestly, not numerically**: v1.2 set out to
  close 4 limitations and record 3. The classifier drift and the two defects were
  *discovered*, not *created* — the record should say which is which rather than
  claiming nothing new exists.

### Standing rules

- README updated in the phase's PR (standing rule) — this IS the README phase.
- All counts (tests, evals denominator, fixtures/refusals split) re-measured at
  execution; STATE/ROADMAP/REQUIREMENTS close-out flips happen here, since this is the
  milestone's last phase.
- ADR numbering continues from the highest existing (verify — believed 0012).

### Claude's Discretion

- Whether the surviving-limitations list gets per-bullet "why this is chosen" prose
  inline or via links only (match the section's existing voice).
- Whether the two defects share one record or get one each.
- Whether `evals/REFUSALS.json` deserves a README pointer beyond the eval section's
  existing one.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The surfaces
- `README.md` — the Limitations section (:287–:301 today; line numbers WILL drift after
  21.5), the eval section prose Phase 21 already rewrote
- `docs/adr/` — 0007 (identities), 0009 (recorded evals), 0010/0012 (judge); the new
  cost ADR lands here
- `docs/OPERATIONS.md` — gains the database posture note; already documents the deploy
  discipline this phase's PR follows
- `evals/REFUSALS.json` + `tests/test_evals.py`'s union/refusal gates — the record the
  recorded-answers story points at
- `.planning/phases/21-*/21-VALIDATION.md` (the amendment record) and
  `.planning/phases/21.5-*/` (whatever 21.5 produces — read at execution, not now)

### House constraints
- The deletion convention: closed limitations are deleted, verified on the git axis, not
  moved. Phases 18/19/20 each left their bullet byte-identical specifically so this
  phase could delete them — honour that by actually deleting them.
- DEC-13 honest denominators; keyless CI inviolable; `git commit -F`; README-every-PR.
- Verification bar: `.planning/phases/20-note-count-bound/20-VERIFICATION.md` and
  `21-*` records.

</canonical_refs>

<specifics>
## Specific Ideas

- The intro's current framing ("v1.1 has now closed all nine") gets the same treatment
  v1.1 gave v1.0's list: state what v1.2 closed, what it recorded, and what it found.
  The section should read as an engineer's honest ledger, not a changelog.
- The strongest close-out sentence available is true and measured: the milestone closed
  four limitations, recorded three by design, and its paid run *discovered* three more
  things free testing structurally could not see — two of which are fixed (classifier,
  via 21.5) or documented with their evidence (truncation, record/replay divergence).
- `PROJECT.md:31-32`'s stale counts and `CONCERNS.md:242`'s false no-eviction claim are
  already in `.planning/phases/20-note-count-bound/deferred-items.md` — this phase is
  the natural place to settle both, or to state where they get settled.

</specifics>

<deferred>
## Deferred Ideas

- Fixing the judge truncation (raise/split the token budget) — successor milestone;
  ADR-0012's fence stands until then.
- Re-authoring contested pins to survive re-records — successor milestone, and only
  with a design that keeps them binding on both reference reports and recordings.
- Any further recording spend beyond 21.5's checkpoint.

</deferred>

---

*Phase: 22-limitations-recorded*
*Context gathered: 2026-08-15; executes after Phase 21.5*
