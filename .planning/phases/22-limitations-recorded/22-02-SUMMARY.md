---
phase: 22-limitations-recorded
plan: 02
subsystem: docs + milestone close-out
tags: [limitations, deletion, git-axis, no-orphan-sweep, link-gate, close-out, keyless, zero-spend]

# Dependency graph
requires:
  - phase: 22-limitations-recorded
    plan: "01"
    provides: "the records this plan's survivors point at (ADR-0014 — NOT 0013; the OPERATIONS posture anchor), the measured execution baseline, and the eval-section prose whose derived-counts gate lets the Limitations intro point at it instead of restating its split"
  - phase: 21.5-classifier-on-opus-5
    plan: "*"
    provides: "the settled 25/15 split and the frozen classifier probe (32/38 vs 37/38) the intro's discovered-ledger cites; REQ-classifier-model already flipped, so this plan verified rather than flipped it"
  - phase: 18-independent-eval-judge
    plan: "*"
    provides: "one of the four byte-identical bullets left standing specifically so this diff could delete it"
provides:
  - "README.md `## Limitations` — seven bullets to three: the four v1.2 closed DELETED and verified on the git axis, three survivors each ending at a record, under an intro that states what the milestone closed, recorded and DISCOVERED"
  - "the no-orphan result: zero hits across docs/ and .planning/codebase/ on all four patterns, so the exemption list is EMPTY — no ADR historical text needed exempting and T-22-03 had no opportunity to fire"
  - "the milestone's books, closed with evidence: REQUIREMENTS (plus one Phase-20 miss corrected), ROADMAP, STATE, PROJECT.md's settled counts, both Phase-20 deferred items' written fates, 22-VALIDATION reconciled"
affects: [/gsd:verify-work, /gsd:complete-milestone]

# Tech tracking
tech-stack:
  added: []  # zero packages, three plans running. 22-RESEARCH's Package Legitimacy Audit stays N/A.
  patterns:
    - "Two gates that look like one are proven separate by mutating each and watching the OTHER stay green. Restoring a deleted README bullet reds the deletion gate and leaves the orphan sweep clean; planting the same sentence in DESIGN.md reds the sweep and leaves the deletion gate green. Neither can stand in for the other, and only running both mutations shows it."
    - "A verbatim-phrase gate is a constraint on the TEXT LAYOUT, not just the words. `grep -cF 'chosen, recorded, and argued for'` went red on correct prose because a hard-wrap split the phrase across a newline. The fix is to reflow the prose, never to weaken the gate to tolerate wrapping — a gate relaxed to accept its first honest red stops being the gate."
    - "Point at a gated number instead of restating it. The Limitations intro could have quoted the 25/15 recorded/refused split; it points at the eval section instead, because that section's numbers are held by a derived-counts test and a copy in Limitations would be a fifth ungated literal in the very phase whose thesis is that every claim points at a record."
    - "A frozen measurement is safe to state as a literal; a live count is not. The classifier's 32/38-vs-37/38 describes a probe that ran once on a date and is committed — it cannot go stale. Suite counts and fixture splits can, and did, three times in this milestone."

key-files:
  created:
    - .planning/phases/22-limitations-recorded/22-02-SUMMARY.md
  modified:
    - README.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/PROJECT.md
    - .planning/phases/20-note-count-bound/deferred-items.md
    - .planning/phases/22-limitations-recorded/22-VALIDATION.md

key-decisions:
  - "The intro POINTS at the recorded/refused split rather than restating it. The plan permitted measured values from the 22-01 baseline; restating 25/15 in Limitations would create a literal outside the derived-counts test's reach (that test scopes to `## Tests and evals` and stops at the next `##`). The classifier's 32/38-vs-37/38 IS stated, because a committed probe report is a frozen measurement rather than a live count."
  - "docs/DESIGN.md is in the plan's files_modified and was NOT modified. It was the likeliest orphan surface and the sweep found nothing there — so the honest outcome is an untouched file, not a defensive edit. It was modified only to plant and revert the sweep mutation."
  - "The exemption list is EMPTY, which is a stronger result than a justified one. T-22-03 (tampering with frozen ADR texts during the sweep) had no opportunity to fire, because no ADR carried a deleted claim in the first place."
  - "REQ-note-count-bound was flipped HERE, on Phase 20's behalf. Its checkbox read `[ ]` while its own traceability row had said Complete since 2026-08-15 (verified, deployed Fly v19). Found by counting checkboxes rather than by reading the one requirement this plan owned — the same class of finding as the plan's own REQ-classifier-model instruction, applied to a requirement nobody had thought to check."
  - "The `/pricing` sentence was dropped from the cost bullet, deliberately. P-05 allows one why-sentence and the ADR carries the /pricing argument; README still names /pricing in the API table and the Deployment section, so nothing became unreachable."
  - "CONCERNS.md was NOT edited (P-08 honoured), and the broader paraphrase sweep re-confirmed the item is still live by measurement — recorded in deferred-items.md as a disposition rather than stepped around silently for the second phase running."
  - "The README Status list has no v1.2 block and one was NOT authored. Recorded as an open finding with /gsd:complete-milestone as the natural owner — writing six speculative Status entries in the phase whose thesis is scope discipline would have been the wrong trade."

# Metrics
duration: 60min
completed: 2026-08-16
status: complete

actuals:
  tokens: 9400    # chars/4 over the realized diff (~37,600 chars across 7 files)
  tasks: 3
  commits: 3
---

# Phase 22 Plan 02: The Limitations rewrite and the milestone close-out Summary

**One-liner:** Seven Limitations bullets became three — the four v1.2 closed **deleted** and
proven gone on the git axis (each phrase in once, out once, never moved to another surface),
the three survivors each ending at ADR-0014 / ADR-0007 / the OPERATIONS posture note, under an
intro that says what the milestone closed, what it records by design, and what its paid run
**discovered** — and the milestone's books closed with evidence, including one requirement
checkbox Phase 20 had missed.

**Zero spend.** Every command ran with `ANTHROPIC_API_KEY="" VOYAGE_API_KEY=""` explicitly
prefixed. No `--yes`, no `--live`, no `--record`.

---

## The new Limitations section, verbatim

Quoted in full because 22-VALIDATION routes the prose judgement to the user's PR read, and a
summary that describes the deliverable instead of showing it makes that read impossible.

```markdown
## Limitations

Known, and deliberate for the scope. **The v1.0 README listed nine limitations
and v1.1 closed all nine; v1.2 has now closed four more.** The eval judge
stopped sharing the critic's model, `/health` stopped calling a revoked key
healthy, notes gained a second bound beside expiry, and the recorded-answers
claim was rebuilt on a real paid run — the eval section above reports what that
bought, refusals included, every number in it derived from the tree rather than
typed. Those four are *gone* from this list rather than reworded into it, which
is the only version of "closed" worth writing.

**Three remain, and this milestone's work was to stop them standing bare.**
Several of the nine closed by narrowing rather than erasing, so their narrower
successors are still here; each of the three below is one of those or a limit
the v1.1 work created, and each now ends at the record that argues it — an ADR,
or an operations note — so the position can be checked rather than taken.

**The paid run also found three things free testing structurally could not
see**, and a close-out claiming otherwise would be the one dishonest sentence in
the section. The classifier was mislabelling: 32 of 38 labelled cases where Opus
5 got 37, on a probe run once and kept, and *fixed* rather than recorded
([ADR-0013](docs/adr/0013-classifier-on-its-own-model.md)). The other two are
defects rather than positions — the judge's verdict truncating against a token
budget it shares with adaptive thinking, and record-time grading disagreeing
with replay-time grading — and they sit in the eval section above with their
per-case evidence and the reason neither is fixed here. A defect belongs there,
not in a list of choices.

What remains below is **chosen, recorded, and argued for**.

- **Reported cost is an approximation, never the invoice.** Nothing here reads a bill: provider token counts are telemetry — measured live, Voyage reported 25 tokens where the tokenizer counted 40, and 0 for a one-word document that embedded fine. Recorded as [ADR-0014](docs/adr/0014-cost-approximation-by-design.md), which also states why reconciling against Anthropic's Admin cost API was rejected.
- **Identities are free to mint.** Clearing browser storage gets you a fresh one with fresh limits, so per-caller limits buy fairness, not a bound on the bill. The global rolling daily spend cap is the actual backstop. Recorded as [ADR-0007](docs/adr/0007-anonymous-identity-fairness-global-cap.md).
- **The database is a single region on a free tier.** Fine at this traffic, and the first thing to look at if it isn't — the tier, the measured headroom behind that judgement, and the one part of the upgrade path that is not a toggle are in [the database posture note](docs/OPERATIONS.md#the-free-tier-posture-and-the-upgrade-path).
```

The identities bullet is **byte-identical** to what Phase 12 wrote. Criterion 2 was
verify-not-author and was treated that way: its link has resolved since commit `ab54fb5`, and
the rewrite left its prose alone rather than "aligning voice" with its two rewritten
neighbours, which P-05 permitted but nothing required.

---

## Task 1 — the rewrite

**Commit `219e9e3`.**

### The four deletions

Each bullet removed whole, links included, replaced with nothing. Grep counts, before → after:

| Phrase | Before | After |
|---|---|---|
| `The eval judge shares the critic's model` | 1 | **0** |
| `Only one of forty answers is recorded` | 1 | **0** |
| `checks that the API keys are *present*` | 1 | **0** |
| `Notes are bounded by expiry alone` | 1 | **0** |

Section bullet count: **7 → 3** (`awk` over the section, `grep -c '^- \*\*'`). P-07 held: no
bullet was created for the refusal residue or either defect.

### The gate that went red on correct prose

`grep -cF 'chosen, recorded, and argued for' README.md` returned **0** on the first run. The
prose contained the phrase; the hard-wrap split it across a newline (`…argued\nfor**`). The
gate is a constraint on the phrase being greppable, not merely present, so the fix was to
reflow — the closing sentence became its own one-line paragraph, which reads better as a
close anyway. **Recorded because the tempting fix was the wrong one:** relaxing the gate to
collapse whitespace (as 22-01's derived-counts test legitimately does) would have made this
particular gate stop testing what criterion 5 asks for.

### The two survivors that were rewritten

Cost keeps its bolded position and its strongest why — the measured Voyage telemetry
discrepancy — and ends at ADR-0014. The old bullet's third sentence (`/pricing` shows the
rate window; read it there) was **dropped**: P-05 allows one why-sentence, the ADR carries
that argument, and `/pricing` is still named in the API table and the Deployment section.

Database drops the region/ceiling/replica detail entirely — that now lives behind the link,
which is the whole point of moving it — and keeps only the position, one clause of why, and
the pointer. Nothing the README line states is restated from the OPERATIONS note.

### Mutation observed (named in the plan)

The note-bound bullet pasted back into the section:

```
RED: grep -cF 'Notes are bounded by expiry alone' README.md = 1, expected 0
RED: bullet count = 4, expected 3
--- no-orphan sweep over docs/ + .planning/codebase/ ---
sweep exit: no hits above = CLEAN
```

**Both halves are the point.** The deletion gate reds; the sweep — which does not read
README — stays clean. Reverted from a pre-mutation copy; gates re-run green.

---

## Task 2 — the git axis, the sweep, the link gate, the read-through

**Commit `ee3dd27`.**

### The git axis: entered once, left once, never moved

For each phrase, `git log --oneline -S"<phrase>" -- README.md` returns exactly **two**
commits, and the direction was verified rather than inferred — the earlier commit shows the
line prefixed `+`, `219e9e3` shows it prefixed `-`:

| Phrase | Entered | Left |
|---|---|---|
| judge shares the critic's model | `6d615ec` docs(16-03) | `219e9e3` |
| one of forty answers recorded | `7906a99` docs: delete limitations… | `219e9e3` |
| checks that the API keys are | `708c545` docs: the README whole-file pass | `219e9e3` |
| bounded by expiry alone | `7906a99` docs: delete limitations… | `219e9e3` |

No phrase needed the "explain the extra commits honestly" branch — each is a clean two.

`git grep -lF` over the whole tree confirms the other half of the claim: **no file outside
`.planning/` planning records has ever carried any of the four.** Nothing was rewritten into
release notes, a changelog, or a Status entry. `.planning/STATE.md` carries
`bounded by expiry alone` as Phase 20's own record of leaving the bullet standing — a
planning record, not a doc surface, and now superseded by this plan's STATE edit.

### The sweep: zero hits, and therefore an empty exemption list

All four enumerated patterns across `docs/` and `.planning/codebase/`: **no output**.

**So the exemption list is empty** — no ADR historical text needed exempting, and the
threat register's T-22-03 (tampering with a frozen record during an over-eager orphan fix)
had **no opportunity to fire**. That is a stronger result than a well-justified exemption
list, and it is worth stating as the outcome rather than leaving an empty section to look
like an omission.

A deliberately broader paraphrase sweep (`judge (shares|uses) the critic`,
`present, not that they work`, `presence, not validity`, `no (eviction|dedup)`,
`expiry alone`, `only one of forty`, `one recorded answer`) returned **two** hits, both
`.planning/codebase/CONCERNS.md` (`:129`, `:254`) — the already-known Phase-20 deferred
item, not an orphan this phase created. Dispositioned per P-08, unedited.

### The link gate

Four targets extracted from the section, all resolving: `docs/adr/0014-…`,
`docs/adr/0007-…`, `docs/adr/0013-…` (the intro's classifier pointer), and
`docs/OPERATIONS.md#the-free-tier-posture-and-the-upgrade-path`. The anchor was **re-derived
from the heading text** (lowercase, punctuation stripped, spaces→hyphens) rather than
string-compared:

```
target fragment : the-free-tier-posture-and-the-upgrade-path
matching heading: The free-tier posture, and the upgrade path
ANCHOR GATE: GREEN
```

### Mutations observed (both named in the plan)

**(a) Orphan planted in `docs/DESIGN.md`:**
```
RED: docs/DESIGN.md:85:Notes are bounded by expiry alone, with no dedup or summarisation.
README deletion gate still GREEN — the sweep and the deletion gate are provably independent
```

**(b) OPERATIONS heading renamed by one word** (posture → stance):
```
ANCHOR GATE RED: README links #the-free-tier-posture-and-the-upgrade-path
                 but no heading in docs/OPERATIONS.md derives it
nearest headings now: ['the-free-tier-stance-and-the-upgrade-path']
```

Both reverted; `git diff --quiet` confirms both files byte-identical to HEAD.

**Taken together with Task 1's mutation, the two gates are proven separate in both
directions** — restore a README bullet and only the deletion gate reds; plant the same
sentence in DESIGN.md and only the sweep reds. Neither can stand in for the other.

### The whole-README pass — three counts re-derived, one deliberately left

- **`:15`** — "827 tests" → **828**. The front-door paragraph. Not flagged by 22-01, which
  named only the fenced block; found by reading the file rather than by following the
  handoff.
- **`:199`** — the fenced block's `# 827 tests` → **828**. The staleness 22-01 handed
  forward by name.
- **`:40`** — "twelve now" → **"fourteen now"**. 21.5 landed ADR-0013 and 22-01 landed
  ADR-0014; neither pass touched the Status line counting them. Re-derived from the files
  themselves — 14 records, **10 `Accepted`, 4 `Superseded`** — so the sentence's
  "four of them superseded on the record" was still correct and **stays unchanged**.
- **`:191`'s "20 other calls that could have gone the other way"** — checked and
  **deliberately left**. `docs/DESIGN.md` has seven `##` sections and no per-decision
  heading, so there is no countable unit to re-derive; the figure is prose, and nothing this
  phase did falsified it.

**This is the ninth-odd instance of the whole-file-pass-means-counting family**, and the
first where the count that went stale was the ADR count made stale by the phase's own wave 1.

---

## Task 3 — the close-out flips

**Commit: the close-out commit below.**

### REQUIREMENTS

`REQ-limitations-recorded` flipped `[x]` with a dated evidence block (four deletions on the
git axis, three survivors linked, ADR-0014, the posture anchor, the empty exemption list, the
measured gates); traceability row **Pending → Complete** in the register the completed rows
use. **Zero `Pending` cells remain.**

`REQ-classifier-model` **verified, not flipped** — 21.5 had already checked it and filled its
row with the measured 37/38-vs-32/38 result and the ADR-0013 pointer. Its requirement *body*
still quotes the pre-execution 34/38-vs-29/38 probe, which is correct as an ex-ante
justification (the body explicitly says the measurement "is repeated at execution before the
switch is trusted") and is left alone.

**One miss found and corrected.** `REQ-note-count-bound` read `[ ]` while its own traceability
row had said **Complete** since 2026-08-15 (verified, `20-VERIFICATION.md` passed, deployed
Fly v19). Flipped here on Phase 20's behalf, with the attribution stated in the requirement
itself rather than done silently. Found by counting checkboxes (5 checked / 3 unchecked
against 8 requirements) rather than by reading the one requirement this plan owned.

Coverage stays 8/8 **mapped** — that arithmetic did not change — with a new line stating
**6 of 8 checked** and naming the two that are not: `REQ-health-credential-validity` and
`REQ-demo-csp-header`, both verified in their automated half and awaiting the manual deploy.
They stay unchecked rather than flipped on a promise.

### ROADMAP

Phase 22 box checked; **both** plan boxes checked (`grep -c '\[x\] 22-0[12]-PLAN.md'` = 2);
an executed-record paragraph appended in Phase 21's style — dated, measured, naming what was
closed versus discovered, and stating explicitly that no milestone archival was performed.
The Progress table's v1.2 row moved `0/TBD` / "In progress" → **`16/16`** / "All phases
executed", and the stale `**Next:** Phase 18` line now points at verification then
`/gsd:complete-milestone`, carrying the open Manual-Only items with it.

**No milestone-archive edit was made.** 22-CONTEXT fences it and the execution brief repeats
the fence; `/gsd:complete-milestone` owns that step.

### STATE

Hand-edited throughout, **by hand** as instructed (SDK verbs corrupted this file three times
in Phase 18), and `gsd-tools query state.load` **parses** after the edit. Front matter:
`status` executing → executed, `completed_phases` 4 → **6**, plans 12 → **16**, percent 67 →
**100**, `last_updated`/`last_activity` current, and `stopped_at` rewritten from "Phase 21
complete → 21.5 defined" (stale from before 21.5 executed) to Phase 22's close, with the
Phase 21 text demoted to a labelled prior entry rather than discarded. Current Position,
Performance Metrics (phases 21, 21.5 and 22 added) and Session Continuity likewise — the
last of which had been stranded on "Phase 19 COMPLETE" since 2026-08-14, three phases behind.

The still-open Phase 19 Manual-Only items are **carried forward, not dropped**, alongside
four other open items stated plainly.

### PROJECT.md — deferred item 2, settled

The named owner took it. Re-measured rather than carried from Phase 20's note:

```
$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:warnings | tail -1
828 passed, 72 skipped in 26.50s
$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest --collect-only -p no:warnings | tail -1
900 tests collected in 0.68s
```

`749 / 67 / 816` → **`828 / 72 / 900`**, dated 2026-08-16. Phase 18's deliberate absence is
preserved verbatim: the with-Postgres pass count is still **not** restated, because nobody
has run that arm and deriving it from the keyless delta would be arithmetic, not measurement.

**The predicted two-line edit was four lines.** Two adjacent claims in the same paragraph were
also stale, both falsified by this milestone's own work: `docs/adr/` "holds 12 records" →
**14** (21.5's ADR-0013 and this phase's own ADR-0014; "four of them superseded" re-derived
and left standing), and "Offline evals grade 41 cases … including one real recorded answer" →
**65 cases** (40 behavioural + 25 replayed), false since Phase 21's record run.

### deferred-items.md — both fates in writing

Item 2 (PROJECT counts): **SETTLED**, with the commands and the two extra corrections.
Item 1 (`CONCERNS.md`): **DISPOSITIONED, unedited**, per P-08 — dated audit snapshot,
`/gsd-map-codebase` re-run remains the owner, and the broader paraphrase sweep re-confirmed
by measurement that the claim is still live at this phase's close.

### 22-VALIDATION.md — reconciled

`status: complete`, `wave_0_complete: true`, `nyquist_compliant: true`. All **nine** automated
rows carry measured evidence — command, observed result, and what the recorded mutation did.
An execution-baseline block sits beside the planning placeholders showing that **every axis
drifted** (+22 tests, denominator 59 → 65, split 19/21 → 25/15). Both Manual-Only rows are
left **OPEN with written reasons** rather than ticked, and the sign-off carries an explicit
"two things this contract records as NOT done" block so the ticks mean what they say.

---

## Gates, at close

| Gate | Result |
|---|---|
| Full suite, keyless | **828 passed / 72 skipped**, 900 collected |
| Offline evals | **PASS 65/65**, real exit **0** |
| `ruff check .` | clean |
| Four deletion phrases in README | **0, 0, 0, 0** |
| Limitations bullet count | **3** |
| Criterion-5 phrase, verbatim | present |
| Limitations links resolving | **4 of 4**, anchor re-derived |
| No-orphan sweep | **zero hits; exemption list empty** |
| Git axis | each phrase **in once (`+`), out once (`-`)** |
| Mutations this plan | **3 named, 3 observed red, 3 reverted** (5 across the phase) |
| `state.load` | parses |
| Spend | **$0.00** |

---

## Deviations from Plan

**1. [Judgement call, within P-05] The intro points at the recorded/refused split instead of
restating it.**
- **Found during:** Task 1, drafting the intro.
- **Issue:** the plan permits "measured values from the 22-01 baseline". Writing
  "twenty-five of forty recorded, fifteen documented refusals" into Limitations would place a
  literal count **outside** the derived-counts test's reach — that test partitions on
  `## Tests and evals` and stops at the next `##`, so a Limitations copy is ungated.
- **Fix:** the intro says the claim was rebuilt on a real paid run and points at the eval
  section, "every number in it derived from the tree rather than typed." The classifier's
  32/38-vs-37/38 **is** stated, because a committed probe report is a frozen measurement of a
  run that happened, not a live count.
- **Impact:** the section's only literals are frozen measurements. Consistent with the
  phase's own thesis.

**2. [Rule 1 — Correctness] README `:40`'s ADR count was stale, and this phase made it staler.**
- **Found during:** Task 2's read-through, not named in the plan or in 22-01's handoff.
- **Issue:** "twelve now" against fourteen records on disk — 21.5 added 0013, 22-01 added 0014.
- **Fix:** re-derived from the files (14 / 10 Accepted / 4 Superseded) rather than
  incremented; "four of them superseded" verified still correct and left unchanged.
- **Commit:** `ee3dd27`.

**3. [Rule 1 — Correctness] README `:15`'s test count was stale at a site nobody had flagged.**
- **Found during:** Task 2's read-through. 22-01's handoff named only the fenced block.
- **Fix:** 827 → 828 at both sites.
- **Commit:** `ee3dd27`.

**4. [Rule 2 — Missing critical] `REQ-note-count-bound`'s checkbox was never flipped by Phase 20.**
- **Found during:** Task 3, counting checkboxes rather than reading the single requirement
  this plan owned.
- **Issue:** `[ ]` against its own traceability row reading **Complete** since 2026-08-15
  (verified, deployed). A milestone must not close with a verified, deployed requirement
  reading unchecked — the same principle the plan applied to REQ-classifier-model.
- **Fix:** flipped with the attribution stated in the requirement body.

**5. [Scope — recorded, deliberately NOT done] The README Status list has no v1.2 block.**
- **Found during:** Task 2's read-through.
- **Issue:** Status stops at 17.5. The new Limitations intro says "v1.2 has now closed four
  more" and a reader looking for what v1.2 *was* finds nothing behind it. Not false —
  incomplete. Git shows Status entries have historically been added by each phase's own
  README pass (`71259ae`, `bafaff0`), so phases 18–21.5 each skipped theirs.
- **Why not fixed here:** authoring six Status entries is a substantial act the plan does not
  name, and the execution brief fences this phase out of milestone close-out work.
  `/gsd:complete-milestone` or a milestone summary is the natural owner.
- **Recorded in:** STATE's Current Position open-items list, and here.

**6. [Not a deviation, recorded for the verifier] `docs/DESIGN.md` is in `files_modified` and
was not modified.** It was the likeliest orphan surface; the sweep found nothing there. It was
touched only to plant and revert mutation (a), and `git diff --quiet` confirms byte-identity.

No Rule 4 (architectural) situations arose. No authentication gates. No checkpoints — this
plan is fully autonomous, as its frontmatter states.

---

## What is still open

1. **Phase 22 verification has not run** — no `22-VERIFICATION.md`. Both of 22-VALIDATION's
   Manual-Only rows are open by design: the prose-quality judgement is the user's at PR read
   (the intro is quoted verbatim above for exactly that), and the "no bullet stands uncovered"
   walk is *prepared* per bullet in the contract but not claimed as passed.
2. **Milestone archival is deliberately not done.** `/gsd:complete-milestone` owns it.
3. **Phase 19's two Manual-Only rows** still need the manual deploy, which is why two of eight
   requirements stay unchecked.
4. **The README Status list has no v1.2 block** (deviation 5).
5. **`.planning/codebase/CONCERNS.md`** still asserts notes have no eviction path — false
   since Phase 12, dispositioned unedited for the second phase running; owner is a
   `/gsd-map-codebase` re-run.
6. **The branch is unpushed** and lands via a pull request, not a push.

---

## Self-Check: PASSED

Files claimed created, verified on disk:
- `.planning/phases/22-limitations-recorded/22-02-SUMMARY.md` — FOUND

Files claimed modified, verified in the commits:
- `README.md` — FOUND in `219e9e3` and `ee3dd27`
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`,
  `.planning/PROJECT.md`, `.planning/phases/20-note-count-bound/deferred-items.md`,
  `.planning/phases/22-limitations-recorded/22-VALIDATION.md` — FOUND in the close-out commit

Commits claimed, verified in `git log`:
- `219e9e3` — FOUND
- `ee3dd27` — FOUND

Gates re-run at close: suite 828/72 (900 collected), evals 65/65 exit 0, ruff clean,
`state.load` parses, all four deletion phrases at 0, three bullets, four links resolving.
