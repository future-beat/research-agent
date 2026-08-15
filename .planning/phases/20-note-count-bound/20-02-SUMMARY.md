---
phase: 20-note-count-bound
plan: 02
subsystem: docs
tags: [operations-knob, readme-pass, measured-counts, deliberate-transient, validation-reconciliation]

# Dependency graph
requires:
  - phase: 20-note-count-bound
    plan: "01"
    provides: "the shipped cap — the knob's exact contract (NOTE_CAP_PER_OWNER, int, default 100, read per call, <= 0 / unparseable / empty / whitespace / non-integer all reading 100), the measured counts this wave re-measured rather than carried, and the eval-seeding sentence 20-RESEARCH Open Question 2 asked for"
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "03"
    provides: "the doc-pass precedent this wave follows: measured greps with absences recorded as results, a two-line README diff, and one knowingly-false Limitations bullet left standing by explicit phase assignment"
provides:
  - "docs/OPERATIONS.md — the NOTE_CAP_PER_OWNER row beside NOTE_TTL_DAYS, carrying the clamp and the eval-seeding consequence"
  - "README.md — test counts measured at 796, Limitations bullet byte-identical (grep 1 before, 1 after)"
  - ".planning/phases/20-note-count-bound/20-VALIDATION.md — all eight automated rows carrying measured Status evidence, plus the Manual-Only row's written disposition"
  - "the recorded judgement that docs/DESIGN.md is NOT falsified by the cap, with the reason, so a later reader does not re-open the question"
  - "one finding for whoever owns the codebase maps: CONCERNS.md still asserts notes have no eviction path at all — false since Phase 12, doubly false now, and left standing deliberately"
affects: [21, 22]

# Tech tracking
tech-stack:
  added: []  # docs only; no dependency, no source file, no test file touched
  patterns:
    - "A whole-file pass means counting, and the count is never only where the plan pointed. The plan named README:15 and :199; the phase had also falsified docs/OPERATIONS.md:609."
    - "A documented absence is a result. DESIGN was read end to end and left untouched, and that is recorded as a judgement with its reason rather than as a silence."
    - "A knowingly-false sentence in the front door earns a paragraph in the record, not a tick. Third phase running (18 at :285, 19 at :289, now 20 at :291)."

key-files:
  created:
    - .planning/phases/20-note-count-bound/20-02-SUMMARY.md
    - .planning/phases/20-note-count-bound/deferred-items.md
  modified:
    - docs/OPERATIONS.md
    - README.md
    - .planning/phases/20-note-count-bound/20-VALIDATION.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "README's Limitations bullet at :291 — 'Notes are bounded by expiry alone' — is now KNOWINGLY FALSE and was deliberately left byte-identical. It stopped being true at 81c0bd2, four commits before this wave began. Phase 22 owns the Limitations section and deletes the bullet there; removing it here would strand that phase with a section it no longer owns end to end, which is the same reasoning Phase 18 applied at :285 (the judge bullet, false since the judge left Opus 5) and Phase 19 at :289 (the /health bullet, false since the credential probe shipped). The transient is stated out loud rather than left for a stranger to catch: grep -c prints 1 before this wave and 1 after."
  - "DESIGN.md was read end to end and NOT edited, which is a judgement rather than an omission. 20-CONTEXT's rule is that DESIGN gets the whole-file treatment IF it describes note lifecycle. Its Memory section argues four things — retrieval with a relevance floor, the store/embedder seams, HNSW replacing the brute-force scan, and migration copying vectors rather than re-embedding — and none of them says what bounds the store. Nothing there is falsified, so nothing there was changed. The case for ADDING a cap paragraph (the clamp direction and the seq tie-break are both choices that could have gone the other way, which is DESIGN's stated admission criterion) was considered and declined: this plan's scope is fixing what the phase made untrue, the argument already lives in memory.py's docstrings and 20-01's record, and an unrequested new section in the milestone's argument file is Phase 22's call, not a doc pass's."
  - "The OPERATIONS row's clamp sentence mirrors COST_DISCOUNT_FACTOR's by design, because P-01 adopted that clamp for the same reason: both knobs have a plausible typo that reads as 'disable this' and both fail toward the safe direction instead. Discount 0 would cost every run at $0.00 and silently disarm the spend caps; cap 0 would make every add() evict the note it just wrote and silently switch recall off. Same shape, same wording register, so an operator reading both rows sees one rule rather than two coincidences."
  - "One doc claim outside the plan's list was found false and fixed in the same task: docs/OPERATIONS.md:609's CI block read '773 tests'. The plan named README:15 and :199 as the stale count sites; this is the third. Fixed on the same measured basis README uses (the keyless pass count), and flagged here because it is the eighth-plus instance of the family this project keeps meeting — the whole-file pass finds the number the plan did not point at."
  - "The Manual-Only row is discharged by stating a fact, not by performing a check. Production holds 8 notes across 7 sessions, so no owner is within two orders of magnitude of the default cap and no live add() can reach the eviction branch. There is no live check to run; claiming one would be the dishonest version of that row. The armed arm against :54329 is the proof — the four pgvector cap cases run for real there rather than skipping."

# Metrics
duration: 35min
completed: 2026-08-14
status: complete

actuals:
  tokens: 4159     # chars/4 over the realized docs diff, 0941a7f..HEAD (16,636 chars)
  tasks: 2
  commits: 3
---

# Phase 20 Plan 02: The doc pass and the phase's honest close Summary

**One-liner:** OPERATIONS gained the knob beside the TTL it composes with, README's counts were re-measured rather than carried (773 → 796, from this wave's own run), DESIGN was read and deliberately left alone with the reason recorded, and 20-VALIDATION's eight automated rows now carry measured evidence — while the one README sentence this phase made false stays byte-identical on purpose, named here rather than discovered later.

## The gate, measured in this wave

| Gate | Entering the phase | Measured here | Result |
|------|--------------------|---------------|--------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest`) | 773 passed / 67 skipped | **796 passed / 71 skipped**, exit 0 | +23 / +4 for the phase — reconciled test by test in `20-01-SUMMARY.md` against a zero-removal `--collect-only` id diff |
| `tests/test_store_contract.py`, armed at `:54329` | 101 passed / 1 skipped | **118 passed / 1 skipped** | +17; the one skip is `REQUIRE_POSTGRES`-gated by design. All four pgvector cap arms ran armed |
| Offline evals (`.venv/bin/python -m evals --min-pass-rate 0.9`) | 41/41, exit 0 | **41/41 (100% vs 90% required)**, real `$?` of **0** | unchanged |
| `.venv/bin/ruff check .` · `.venv/bin/ruff check src tests evals` | clean | **clean, both forms** | — |
| `git diff --stat HEAD -- src tests` at both task commits | — | **0 lines** | this wave is docs and planning metadata only, measured rather than promised |

The keyless suite was run twice: once at the top of Task 2 (the run README's number comes
from) and once at HEAD after both commits landed. Identical: 796 / 71. The exit status of
the eval run was taken from a bare invocation rather than through a pipe, so the `0` is the
evals CLI's own and not `tail`'s.

## Task 1 — OPERATIONS gains the knob; DESIGN judged by reading: `111df6f`

### The row

Immediately after `NOTE_TTL_DAYS`, in that row's operator voice, at default `100`:

> **The second bound on notes, beside the TTL:** one owner holds at most this many live
> notes, and adding past the cap evicts that owner's oldest inside the same `add()` that
> already sweeps expiry — identically on all four vector backends, and never across owners.
> `≤ 0` or unparseable falls back to `100`, so a typo cannot silently switch recall off by
> making every write evict the note it just made; an operator who wants no cap leaves this
> unset. It bounds **every** `add()`, including the notes the eval harness seeds, so a future
> large-corpus eval case would be truncated to the cap.

Three things checked against `memory.py` rather than against the plan's description of it,
because the row is what an operator will believe:

- **Default 100 and read per call** — `NOTE_CAP_PER_OWNER_DEFAULT = 100`, `note_cap_per_owner()`
  reading `os.environ` on every call (`memory.py:65, 91-113`). Unset, empty and
  whitespace-only all reach the default through `.strip()` then `if raw else`; non-integer
  through the `except ValueError`; zero and negative through the closing `cap if cap > 0 else`.
  Six inputs, one default — exactly the contract 20-01's SUMMARY handed over, verified in the
  source before the row was written.
- **Same `add()` as the sweep, in a fixed order** — the ABC's own docstring (`memory.py:242-246`)
  states sweep → insert → evict, sweep unconditional. The row says "inside the same `add()`
  that already sweeps expiry" rather than inventing a second mechanism.
- **Never across owners** — `MemoryStore`'s third property bullet (`memory.py:220-229`), which
  Wave 1 added. Worth one clause in the row because an operator tightening the cap for a small
  database is entitled to know it cannot spill into another identity's notes.

The tie-break detail (insertion-native ordering, never `created_at` alone) is deliberately
**not** in the row. It is a correctness argument for a reader of the code, it lives in
`memory.py`'s docstrings and in 20-01's record, and an env-table row that explains a stable
sort has stopped being an env-table row.

### The greps, with their outcomes — including the absences

Each was run; each result is recorded whether or not it produced an edit.

```
$ grep -n -iE "note|expiry|expire|TTL|bound" docs/OPERATIONS.md      →  38 hits, all read
$ grep -c "NOTE_CAP_PER_OWNER" docs/OPERATIONS.md   (before → after) →  0 → 1
$ grep -rn -iE "expiry alone|only bound|bounded by expiry|notes expire" .planning/codebase/  →  0
$ grep -rn -E "[0-9]{3} tests" docs/ README.md                       →  3 sites, one unplanned
```

**Nothing in OPERATIONS claimed expiry was the only bound.** That is the result, not a
shortcut. Three neighbourhoods were read closely and each judged NOT falsified, with the
reason:

| Site | Claim | Judgement |
|------|-------|-----------|
| `:674`, the `NOTE_TTL_DAYS` row | "A stored note stops being recalled this long after it was written, and is swept on the next `add()`" | **True and non-exclusive.** It describes expiry; it never says expiry is all there is. Left byte-identical, which is also what lets the new row read as a second bound beside it rather than as a correction to it |
| `:440-445`, the embedding migration's scale note | "Notes expire seven days after they are written, so the live corpus is small and self-cleaning" | **Tightened, not falsified.** The cap makes the corpus smaller still; a bound that shrinks does not make a smaller-corpus claim untrue. Rewriting it would have been editing to prove the file had been read |
| `:452-458`, the no-dual-write argument | "the corpus is at most seven days of notes by construction" | **Still an upper bound.** Adding a second, tighter bound cannot falsify a stated upper one. The argument it supports — that dual-write for a self-erasing corpus is theatre — is untouched |

**One claim WAS falsified, and it was not in the plan's list.** `docs/OPERATIONS.md:609`, the
CI block, read `ruff, 773 tests, 41 offline eval cases`. Wave 1 moved that number to 796. Fixed
in this task on the same measured basis README's two sites use — the keyless pass count, which
is what the 773 it replaces also meant. Stated rather than quietly corrected, because the plan
pointed at two count sites and there were three; a number this task had just measured, left
false in a file this task was editing, would be the exact failure the wave exists to prevent.

*(The nuance, so the number is not over-read: CI provisions Postgres, so more of the 71 skips
run there than run locally. `796` is the keyless figure, on the identical basis as the number
it replaces.)*

### DESIGN: read end to end, and left untouched on purpose

`docs/DESIGN.md` is 83 lines and all 83 were read. Its **Memory** section makes four arguments —
retrieval with a relevance floor rather than a growing prompt (`:30`), the store and embedder as
separate seams (`:32`), HNSW replacing the brute-force scan (`:34`), and migration copying
embeddings rather than re-embedding (`:36`) — and **not one of them states what bounds the
store**. There is no TTL claim, no expiry claim, no "notes are removed when…" claim anywhere in
the file. The cap therefore falsifies nothing in it, and the file is unmodified.

This is the finding 20-CONTEXT's conditional was written for ("whatever DESIGN says about note
lifecycle gets the whole-file treatment **if** this phase falsifies it"), and the honest answer
to the conditional is that its antecedent is false. Recorded here so the next reader does not
have to re-derive it, and so "DESIGN unchanged" reads as a measurement rather than as an
oversight.

## Task 2 — README measured, validation reconciled: `4e0d7e6`

### README: read end to end, two lines changed

Both test counts, `:15` and `:199`, **773 → 796**, from this task's own keyless run rather than
from 20-01's SUMMARY or the plan's projection. The rest of the file was checked claim by claim
against the cap and nothing else was found false:

- `:43` — the Phase 12 status entry, "Sessions and notes belong to a caller and expire after
  seven days." **True.** They do expire after seven days; the cap adds a second bound without
  contradicting the first, and this entry is a record of what Phase 12 shipped, not a current
  exhaustive statement of note lifecycle.
- `:28` — the Phase 2 entry, "cosine recall with a relevance floor, persisted across runs."
  **Untouched by the cap** — it describes retrieval.
- `:97-105` — the endpoint table. **No row describes note lifecycle.** `/memory` is not listed;
  nothing there is falsified.
- `:243-247` — Deployment, "mount a volume at `/data` or every session and stored note dies
  with the container." **True**, and about durability rather than bounds.
- `:266-270` — the configuration paragraph, which names `COST_DISCOUNT_FACTOR`,
  `INFERENCE_GEO_MULTIPLIER`, `SESSIONS_TOKEN` and `CRITIC_MODEL`. **Not extended.** It is a
  four-knob pointer at the OPERATIONS table, not an inventory, and the new knob's home is the
  table it points at.
- No Phase 20 entry was added to the Status list. Following the same convention Phases 18 and
  19 followed — the v1.1 list ends at 17.5 and the v1.2 phases enter the README when Phase 22
  rewrites the front matter around the closed limitations.

The whole README diff for this plan is **two lines**, both counts.

### The bullet that is now false on purpose

`README.md:291` says, today, on the branch that just shipped a per-owner count cap:

> **Notes are bounded by expiry alone.** Within one identity there's no dedup or
> summarisation — neither has semantics that four vector backends can agree on, and identical
> behaviour across them is the claim being defended.

**The first sentence is false.** It stopped being true at `81c0bd2`, four commits before this
wave began. Notes are bounded by expiry **and count**, on all four backends, proven by four
4-arm contract cases plus a stubbed chroma gate.

It was left byte-identical, deliberately. Phase 22 owns the Limitations section and deletes the
bullet there as part of rewriting the section around what survives; deleting it here would
strand that phase with a section it no longer owns end to end, and would also drop the
second sentence — the dedup/summarisation refusal — which is still **true** and still recorded
in REQUIREMENTS' Out of Scope. Splitting a bullet mid-phase to salvage half a sentence is worse
than leaving the whole one for the phase that rewrites the section.

This is the third consecutive phase to leave one: Phase 18 left `:285` (the judge bullet, false
since the judge moved off the critic's model), Phase 19 left `:289` (the `/health` bullet, false
since the credential probe shipped), and Phase 20 leaves `:291`. Three knowingly-false sentences
now stand in the portfolio's front door by explicit assignment. That is a real cost of the
sequencing and it is written down rather than absorbed — and it is the strongest argument
available for Phase 22 landing before anything else discretionary.

The gate that keeps it byte-identical:

```
$ grep -c "Notes are bounded by expiry alone" README.md   # before Task 2
1
$ grep -c "Notes are bounded by expiry alone" README.md   # after Task 2
1
```

### Live behaviour: a guarantee, not an observable change

Stated plainly, per 20-CONTEXT, rather than oversold. The production database holds **8 notes
across 7 sessions**. The default cap is 100 per owner, so no live identity is within two orders
of magnitude of it, and no `add()` in production can currently reach the eviction branch at all.

Nothing a live user does will look different this week. What changed is what is now *impossible*:
one identity can no longer accumulate an unbounded pile of notes between TTL sweeps, on any of
the four backends. That is worth shipping and it is not worth claiming as a behaviour change,
and the difference between those two sentences is the whole point of saying it out loud.

### 20-VALIDATION reconciled

All **eight** automated rows carry measured Status evidence: the command, the observed result,
and what the recorded mutation did. Two are worth reading rather than ticking:

- **The tie-break row is MET through its own stated alternative**, not its first branch. Its
  mutation clause allowed either a red chroma arm *or* an honest report that the design was
  revisited. Mutation 2c (chroma sorting the eviction by `created_at` instead of `seq`) left the
  chroma arm **GREEN** — real chromadb 1.4.1 returns `get()` in insertion order, so a stable
  sort over collided timestamps reproduces `seq` order and the correct note is deleted anyway.
  The shared 4-arm suite is **structurally blind** to that regression on chroma. The revision
  is `test_chroma_cap_eviction_survives_a_reordered_get`, which reds under 2c. The row now says
  this, because a Status column reading "MET — mutation red" would have been a transcription
  that inverted the finding.
- **The composition row records that mutation 2b also reds a pre-existing test.** The new case
  is not that mutant's sole gate; what it adds is a non-default cap and a mixed live/expired
  set, neither of which `test_note_ttl` reaches.

The Manual-Only row's disposition is written into the file beneath the table and repeated in
this SUMMARY: no live check exists, the armed arm is the proof. The Task ID / Plan / Wave
columns were assigned at planning and are **correct as assigned** — every gate landed in the
task the planner predicted, so nothing was renumbered. The sign-off checkboxes, `status:` and
`nyquist_compliant:` were left untouched: those are phase verification's to set, and an
executor ticking its own sign-off is the shape of gate this project keeps finding decorative.

The file also gained a measured post-phase baseline block beside the entering one, so the
+23 / +4 is visible in the validation contract itself rather than only in a SUMMARY.

## The finding this wave carries forward

`grep -rn -iE "\bTTL\b|expir|sweep|bound" .planning/codebase/` turned up something the
planning-time grep did not: **`.planning/codebase/CONCERNS.md:242-270`** still says, as
current fact —

> ### Stores grow without bound — confirmed, and worse in the memory store
> **Verified as stated, with detail.** There is genuinely no eviction, deduplication, or
> summarisation anywhere. The `MemoryStore` contract does not even have a method that could
> remove a note — the seam would need widening before an eviction policy could be written.

Three things about it, in order of what matters:

1. **It was already false before this phase started.** Phase 12's unconditional TTL sweep
   physically removes rows inside `add()`; the "no eviction anywhere" claim died there, over
   two milestones ago. Phase 20 makes it *more* false, not newly false.
2. **Its prediction was wrong in an interesting way.** It says the seam would need widening
   before an eviction policy could be written. Phase 20 wrote one and the seam is
   character-identical — measured, in 20-01: no `+`/`-` line in the `memory.py` diff matches
   `def (add|query|__len__|describe)\(`, and `graph.py`'s diff is zero lines. Eviction lives
   *inside* `add()` and returns nothing, so no method needed adding.
3. **It was NOT edited, deliberately.** The file is a dated snapshot (`**Analysis Date:**
   2026-08-04`) of an audit whose findings carry "Fix approach" sections — editing its findings
   rewrites the audit rather than updating a doc. It is also `/gsd-map-codebase` output,
   regenerated wholesale, and Phase 18 already recorded three maps' staleness as a deferral for
   exactly that reason. Precedent followed: Phase 19 corrected a map line **its own phase**
   falsified and left the rest; this phase falsified nothing there.

Recorded here rather than silently stepped around, because "the map says the store has no
eviction" is the single most misleading sentence about this subsystem now in the repository,
and the person who runs the next `/gsd-map-codebase` should know it is waiting.

**A second stale claim, same treatment:** `.planning/PROJECT.md:31-32` reads "749 tests pass
with no API keys, and 67 more are Postgres-gated — 816 collected. (Measured 2026-08-14,
keyless.)" That was Phase 18's correction and was true when written; Phase 19 added 23 and
left it, Phase 20 added 23 more plus four skips. Measured today: **796 / 71 / 867**. Not
fixed here — `PROJECT.md` is in no task's `<files>` and this wave's remit is the published doc
surfaces plus the phase's own validation contract — but recorded **with the measured numbers**
in `deferred-items.md`, so the fix is a two-line edit rather than another measurement run.

Both items are in `.planning/phases/20-note-count-bound/deferred-items.md` and named in
STATE.md's deferred block.

## Deviations from plan

### [Rule 1 — false claim, fixed in place] A third stale test count

`docs/OPERATIONS.md:609` read `773 tests`. The plan named only `README.md:15` and `:199`.
Falsified by this phase's own Wave 1, found by grepping for the pattern rather than the two
named sites, fixed to the measured 796 in Task 1's commit alongside the knob row. No
architectural question, no user decision — a number this task measured, in a file this task
owned, left false.

### [scope, additive and recorded] STATE.md and ROADMAP.md updated in the closing commit

The plan's `files_modified` lists four files and neither of these. Wave 1 deliberately left
STATE.md alone (it is hand-edited by convention, and SDK verbs corrupted it three times in
Phase 18). This is the phase's last wave, so leaving both stale would mean the phase closes
with its own record still saying Phase 19 is where the project stopped. Both were edited **by
hand** — no SDK verb touched either file — and STATE.md's frontmatter was re-read after
editing to confirm it still parses. This follows the Phase 19 pattern exactly (`docs(19-03):
close the phase` did the same in its final wave).

### [judgement, recorded rather than performed] DESIGN.md untouched

Covered in full above. Named here too, because "a file in `files_modified` has an empty diff"
is the kind of thing a verifier should find explained rather than have to ask about.

### [not a deviation, stated to be explicit] Zero source and test changes

`git diff --stat HEAD -- src tests` printed **0 lines** at both task commits. No defect was
found in Wave 1's code while documenting it; had one been found, the standing instruction was
to report rather than fix it silently, and there is nothing to report.

## Acceptance criteria, measured

| # | Criterion | Result |
|---|-----------|--------|
| 1 | OPERATIONS documents the knob beside the TTL it composes with, clamp included | ✅ `grep -c NOTE_CAP_PER_OWNER docs/OPERATIONS.md` 0 → 1; row at `:675`, immediately after `NOTE_TTL_DAYS`, carrying the clamp in `COST_DISCOUNT_FACTOR`'s register and the eval-seeding sentence |
| 2 | README's counts measured, Limitations bullet untouched, the contradiction recorded | ✅ 773 → 796 from this wave's own run; bullet grep **1 before, 1 after**; the falseness named in its own section above, with the Phase 18/19 precedent |
| 3 | DESIGN and the codebase maps judged by reading, edited only where falsified | ✅ DESIGN read end to end, no note-lifecycle claim, unmodified with the reason recorded; maps grepped, one pre-existing false claim found, left standing with its ownership stated |
| 4 | 20-VALIDATION reconciled: every automated row measured, Manual-Only disposed of | ✅ 8/8 rows carry command + result + mutation outcome; Manual-Only discharged in writing as its Instructions specify; sign-off left to verification |
| 5 | The full phase gate green | ✅ keyless **796 / 71** exit 0; armed contract file **118 / 1**; evals **41/41** real `$?` 0; ruff clean both forms |

## Threat register — dispositions discharged

| Threat | Disposition | How |
|--------|-------------|-----|
| T-20-11 Repudiation (docs claiming expiry is the only bound after the cap ships) | mitigate | Every surface re-derived against a measured grep, with three absences recorded as results (OPERATIONS' TTL row and two migration passages judged non-falsified; DESIGN judged not to claim it at all; the codebase maps grepped). One unplanned falsification found and fixed. README's counts re-measured rather than carried |
| T-20-12 Repudiation (README's Limitations bullet knowingly false until Phase 22) | accept | The deliberate transient held: grep count 1 before and after, whole README diff two lines. Named in its own section, with the Phase 18 and Phase 19 precedents and the running cost of three standing false bullets stated rather than absorbed |
| T-20-SC Tampering (package-manager installs) | accept | N/A held — no install ran, `pyproject.toml` unmodified, `git diff --stat HEAD -- src tests` 0 lines at both commits |

## What the verifier needs

- **Every phase gate was re-run in this wave, not carried:** keyless 796 / 71, armed contract
  file 118 / 1, evals 41/41 with a real exit 0 taken from a bare invocation, ruff clean both
  forms. The keyless run was repeated at HEAD after both commits: identical.
- **`README.md:291` is knowingly false and must stay that way until Phase 22.** If a
  verification step flags it as a contradiction, that is the intended state, recorded in three
  places (here, `20-CONTEXT.md`, and `20-01-SUMMARY.md`). The gate that protects it is
  `grep -c "Notes are bounded by expiry alone" README.md` == 1.
- **Two other knowingly-false README bullets are already standing** (`:285` from Phase 18,
  `:289` from Phase 19). Phase 22 owns all three. Three is the most that should ever be
  outstanding at once.
- **`20-VALIDATION.md`'s frontmatter is deliberately unchanged** — `status: draft`,
  `nyquist_compliant: false`, and the four sign-off checkboxes unticked. All eight automated
  rows below them carry measured evidence; the sign-off is verification's.
- **The tie-break row's evidence inverts the plan's expectation** and is the phase's most
  transferable finding: the shared 4-arm suite cannot see a chroma `created_at`-vs-`seq`
  regression, because chromadb 1.4.1's `get()` order rescues the wrong sort. If `chromadb` is
  ever unpinned, `test_chroma_cap_eviction_survives_a_reordered_get` is the test that still
  means something.
- **`.planning/codebase/CONCERNS.md:242` claims notes have no eviction path at all.** False
  since Phase 12, left standing deliberately (dated audit snapshot, regenerated wholesale,
  Phase 18's recorded map deferral). Not this phase's to patch; worth knowing before anyone
  reads that map as current.
- **Nothing in `src/` or `tests/` moved in this wave**, so no re-review of Wave 1's code is
  implied by these two commits.

## Self-Check: PASSED

- `docs/OPERATIONS.md` — FOUND, `grep -c NOTE_CAP_PER_OWNER` = 1, `grep -c "773 tests"` = 0
- `README.md` — FOUND, `grep -c "796 tests"` = **2** (both count sites, `:15` and `:199`), `grep -c "773"` = 0, `grep -c "Notes are bounded by expiry alone"` = 1 at `:291`
- `docs/DESIGN.md` — FOUND, unmodified (absent from `git diff --stat 0941a7f HEAD`)
- `.planning/phases/20-note-count-bound/20-VALIDATION.md` — FOUND, 0 rows reading `pending`
- `111df6f` — FOUND in `git log`
- `4e0d7e6` — FOUND in `git log`
