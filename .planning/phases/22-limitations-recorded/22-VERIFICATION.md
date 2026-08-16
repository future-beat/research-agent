---
phase: 22-limitations-recorded
verified: 2026-08-16T11:32:14Z
status: human_needed
score: 5/5 roadmap success criteria verified
method: goal-backward — every criterion re-proven from the tree. One mutation applied, observed red and reverted; six independent recomputations (the refusal split from disk, the classifier probe rescored from its own 38 rows, the ADR status census, the git axis per phrase, the sweep patterns' non-vacuity against the pre-deletion README, the STATE frontmatter YAML-parsed). Both SUMMARYs and 22-VALIDATION were read as claims, never as evidence
verifier_mutations: 1  # README count literal, applied, observed red, reverted; README confirmed byte-identical to HEAD after
verifier_recomputations: 6
overrides_applied: 0
behavior_unverified: 0
re_verification: false

# Gates re-run by the verifier, not read from a SUMMARY
gates:
  full_suite: "828 passed, 72 skipped in 26.76s, exit 0 — `ANTHROPIC_API_KEY='' VOYAGE_API_KEY='' .venv/bin/pytest -p no:warnings`, no second -q, counts visible"
  collected: "900 tests collected in 0.76s — `pytest --collect-only -p no:warnings`"
  offline_evals: "PASS 65/65 cases (100% vs 90% required), real $? = 0 — `ANTHROPIC_API_KEY='' VOYAGE_API_KEY='' .venv/bin/python -m evals --quiet`"
  ruff: "All checks passed! — `.venv/bin/ruff check .`"
  git_axis: "each of the four deleted phrases: exactly 2 commits touching README; earlier commit +1 line, `219e9e3` -1 line; `git grep -lF` over the whole tree returns hits only under `.planning/`"
  no_orphan_sweep: "all four enumerated patterns over `docs/` + `.planning/codebase/`: zero hits. Patterns proven non-vacuous — each matches exactly once in `219e9e3^:README.md`"
  link_gate: "4 of 4 targets resolve; the OPERATIONS anchor re-derived from `### The free-tier posture, and the upgrade path` (OPERATIONS:170) equals README's fragment"
  limitations_shape: "3 bullets; `grep -cF 'chosen, recorded, and argued for' README.md` = 1"
  union_from_disk: "25 fixtures + 15 refusals = 40 golden, overlap []; kinds {grader: 7, judge_truncated: 2, recorded_then_failed_replay: 6}; denominator len(GOLDEN)+fixtures = 65"
  adr_census: "14 files under docs/adr/ excluding README; 10 Accepted, 4 Superseded; 9 carry `**Source:**`"
  state_parse: "`gsd-tools query state.load` → state_exists true, roadmap_exists true; frontmatter independently YAML-parsed: milestone v1.2, status executed, progress 6/6 phases 16/16 plans 100%"
  scope_fence: "13 files changed across main..HEAD; zero under `src/`, zero under `evals/`, no graders/dataset/judge/pipeline edit. `.planning/codebase/CONCERNS.md` untouched"
  no_archival: "`.planning/milestones/` holds only v1.0 and v1.1 artifacts; `git diff --stat main..HEAD -- .planning/milestones/` is empty"
  working_tree: "clean at start, clean after the mutation was reverted, clean at end"

# Not gaps. Recorded so /gsd:complete-milestone and the milestone audit inherit the fact rather than the silence.
warnings:
  - finding: "The README Status list has no v1.2 block — it stops at 17.5 — while the new Limitations intro credits v1.2 by name with closing four limitations"
    evidence: "README:37 carries an explicit `**v1.1 — closing the limitations list.**` sub-header introducing entries 10–17.5. There is no v1.2 equivalent and no entries for 18, 19, 20, 21, 21.5 or 22. The string `v1.2` appears exactly once in the entire README — at :329, inside the Limitations intro (`v1.2 has now closed four more`). Nothing is false and no cross-reference dangles: the four `see NN` pointers resolve to 12, 15, 16 and 17, all of which exist. Git shows Status entries were historically added by each phase's own README pass (`71259ae`, `bafaff0`), so the debt is five phases old — 18 through 21.5 each skipped theirs — and was not created by this phase."
    why_it_counts: "The Status list is the README's spine and the first thing a top-down reader consumes. It currently ends one milestone short while the section below credits that milestone by name, so a reader who reaches :329 has no way to discover what v1.2 was. v1.2 contains the paid record run — the most substantial engineering in the repository — and it is invisible above the fold. This is incompleteness, not falsity, and it is the last visible asymmetry in a README this milestone otherwise made rigorous."
    verifier_judgement: "Phase 22's decision to leave it is a LEGITIMATE scope call, and it should still be closed before the milestone archives. Both are true and are not in tension. The plan's whole-README pass was scoped to 're-derive anything false'; this is incomplete, not false. Authoring six Status entries — each a dense paragraph with ADR links in the section's established voice — is a substantial act the plan does not name, inside the phase whose thesis is scope discipline. It was found by reading the file, recorded in two places (STATE's open items and 22-02-SUMMARY deviation 5), and handed forward with a named owner. That is the correct handling of an out-of-scope discovery, not an evasion."
    fix: "A small scoped README pass before `/gsd:complete-milestone`: six entries for 18, 19, 20, 21, 21.5 and 22 under a `**v1.2 — nothing uncovered.**` sub-header matching v1.1's shape. This is transcription against verified records rather than new authoring — ROADMAP:399–451's executed records, the five phase VERIFICATIONs and the ADR index supply every entry's content and links. Two constraints for whoever writes it: (a) prefer FROZEN measurements (32/38 vs 37/38, Fly v19/v20, ADR numbers) over live counts, because the derived-counts test scopes to `## Tests and evals` and does not reach the Status list; (b) confirm an owner — if `/gsd:complete-milestone` does not touch README, this needs explicit assignment or it ships as-is."
  - finding: "`docs/DESIGN.md:34` carries a stale cross-reference to the Limitations section, and it is NOT an orphan this phase created"
    evidence: "The line reads: 'The brute-force stores score every note on every query and pull the whole corpus into the agent process — exact, O(n), and the thing the Limitations section has flagged since Phase 1.' The present-perfect implies the Limitations section still flags it. It does not — and it did not before this phase either: `git show 219e9e3^:README.md` shows the seven pre-deletion bullets, none about brute-force scan or O(n) recall. The line dates to `3acaec7` ('Restructure the README; move design and ops detail into docs/'), pre-v1.2."
    why_it_counts: "Surfaced only because the verifier ran a broader adversarial paraphrase sweep than the phase's four enumerated patterns. It is outside this phase's gate by construction (the four patterns match only the four deleted claims) and outside its remit (Phase 19's precedent — correct only what your own phase falsified). Recorded so a future orphan sweep does not rediscover it as new, and so the milestone audit knows it exists."
    fix: "One-clause edit at `docs/DESIGN.md:34`, or leave it — it is a narrative aside about a superseded implementation, not a live claim about a limitation. Successor-milestone or `/gsd-map-codebase` territory, not a Phase 22 gap."
  - finding: "The fenced block's `# 828 tests` comment sits inside the derived-counts test's scope but is not one of its gated claims"
    evidence: "`test_the_readme_eval_counts_are_derived_from_the_tree` partitions on `## Tests and evals` and stops at the next `##`, so README:199's comment IS inside the captured prose (confirmed in the verifier's mutation output, where the collapsed section text begins with it). But the test's `claim()` list covers only the fixture count, the denominator, the refusal total and the three kinds. The comment is ungated."
    why_it_counts: "It went stale exactly once this milestone (827→828) and was caught by a human read-through at two sites, not by the gate — which is precisely the failure mode the gate exists to end. Also true of README:15's front-door count, which is outside the section entirely."
    fix: "Cheap successor hardening: add `f'# {suite_count} tests'` to the claim list with the count derived from a collection, or drop the number from the comment. Not a gap — this phase DID re-derive both sites correctly."

# Verifier nits. None changes a verdict.
notes:
  - "The boundary case in criterion 4 is worth stating explicitly, because it is the one place a strict reading could object. The new intro DOES narrate the four closings in a single ledger sentence ('The eval judge stopped sharing the critic's model, `/health` stopped calling a revoked key healthy, notes gained a second bound beside expiry, and the recorded-answers claim was rebuilt on a real paid run'). That is not the 'rewrite into release notes' the convention forbids: the convention forbids preserving each closed bullet as a reworded bullet, and no bullet was created (7 → 3, every survivor a genuine survivor). 22-CONTEXT explicitly ratifies the ledger framing ('the same treatment v1.1 gave v1.0's list'), criterion 5 REQUIRES an intro, and the sentence that follows it — 'Those four are *gone* from this list rather than reworded into it' — states the convention it is obeying."
  - "22-VALIDATION's Manual-Only row 2 ('no bullet stands uncovered') was left OPEN and routed to this verification. It is now CLOSED. The walk, performed per bullet: cost → ADR-0014 argues estimate-by-design in Context/Decision AND carries four numbered Admin-API rejection reasons under `### Rejected alternatives`, which is both halves of what the bullet claims. Identities → ADR-0007:53–58 argues the bullet's claims nearly verbatim ('Identities are free to mint: clearing browser storage produces a fresh identity with fresh limits… per-identity limits cannot be the only bound on the bill. The global rolling 24-hour spend cap…'). Database → the OPERATIONS posture note carries all three things the bullet promises are there: the tier, the measured headroom, and the one part of the upgrade path that is not a toggle. No bullet stands uncovered."
  - "Criterion 2 was verify-not-author and was treated that way. The identities bullet is BYTE-IDENTICAL to `219e9e3^` (diff empty), last touched in `7906a99` (2026-08-10), and its ADR-0007 link entered at `ab54fb5 docs(12-06)` — both SUMMARY provenance claims check out exactly. The rewrite left it alone rather than 'aligning voice' with its two rewritten neighbours."
  - "ADR-0014's handling of the unreproducible source is honest and the verifier confirmed the ADR does not assert the claim. Lines 128–138 name the research's quote ('Admin API keys are owned by the organization and remain active even after the creator is removed'), state it was NOT present on any of the three pages at re-read, and rest reason 1 on the current no-selectable-scopes text instead — which is a stronger form of the same point. The quote appears in the ADR only as the thing that could not be reproduced. This is the correct disposition: a rejection reason resting on a sentence a reader cannot find would be the worse record."
  - "Every fact ADR-0014 and the OPERATIONS posture note import traces to a pre-existing measured surface, checked by the verifier: the 40-vs-25-vs-0 Voyage telemetry at `docs/OPERATIONS.md:577`; `record_embedding`'s docstring quoted verbatim at `src/research_agent/usage.py:498-499`; the `/health` probe p50s (2.84 / 3.23 / 3.39 ms) at `OPERATIONS:248-249`; the pool arithmetic (`PG_POOL_MAX_SIZE` 5 × 2 machines = 10 of Nano's 60) at `OPERATIONS:337`; `HEALTH_PROBE_BUDGET` 3.0 s at `OPERATIONS:700`. The posture note argues; it does not invent. Its no-read-replica claim is labelled as carried from the tier's published shape rather than measured, and noted as wrong in the safe direction if wrong."
  - "The derived-counts gate is real, and the verifier proved it in the direction that matters. Mutating README's `**Twenty-five cases of forty are recorded**` to `Twenty-four` reds the test with the tree's own value in the message ('the tree says 'twenty-five cases of forty are recorded'; README's eval section does not'). Restored; `git diff --quiet -- README.md` confirms byte-identity. The test derives from `F.fixture_paths()`, `documented_refusals()` and `len(GOLDEN)` — no literal count, no parallel loader — and additionally holds the KIND LIST as a subset assertion and asserts the decomposition is total, which is the drift a per-number check cannot see."
  - "The `REQ-note-count-bound` flip was genuinely owed, not manufactured. `git show 04f5668^:.planning/REQUIREMENTS.md` shows the checkbox at `[ ]` while the same file's traceability row already read **Complete** (unchanged text, dated 2026-08-15), and `20-VERIFICATION.md` frontmatter reads `status: passed`, `score: 3/3`. A milestone closing with a verified, deployed requirement reading unchecked would have been the defect; the flip is attributed in the requirement body rather than done silently."
  - "Milestone archival was NOT performed, and the verifier looked for it specifically since overreach would itself be a finding. `.planning/milestones/` contains only v1.0 and v1.1 artifacts; the phase diff touches nothing under it. ROADMAP:450-451 and STATE's stopped_at both state the omission as deliberate, and ROADMAP:467's Next line routes to verification then `/gsd:complete-milestone`."
  - "`.planning/codebase/CONCERNS.md` was not edited (P-08 honoured — `git diff --stat main..HEAD` on it is empty) and its disposition is written down in `20-note-count-bound/deferred-items.md` rather than stepped around. The disposition includes a re-measurement: the four enumerated patterns returned zero hits there, and a broader paraphrase sweep then surfaced `:129` and `:254`, confirming the item is still live at this phase's close. Dispositioned, not silently skipped."
  - "The verifier's own broader adversarial paraphrase sweep over `docs/` (judge-shares-critic / same-model / only-one-recorded / keys-present-not-working / presence-not-validity / expiry-alone / no-bound / unbounded / no-eviction) returned four hits, ALL false positives: `DESIGN.md:41` ('unbounded amount' about cost overshoot), `OPERATIONS.md:727` ('only one of them bounds'), `ADR-0011:208` ('Unbounded cost'), `adr/README.md:121` ('Only one of its two positions'). No deleted claim survives anywhere in `docs/` under any phrasing the verifier could construct."

human_verification:
  - test: "Read the new Limitations section (README:326–358, quoted verbatim in 22-02-SUMMARY) at PR review and judge whether it reads as an engineer's honest ledger rather than a changelog."
    expected: "The intro's three paragraphs — closed / remain / discovered — land as one voice with the rest of the README, and the three surviving bullets read as positions rather than apologies."
    why_human: "Prose quality is the deliverable and no grep proves tone. 22-VALIDATION declares this Manual-Only for exactly this reason and the SUMMARY quotes the section in full so the read is possible without opening the diff. Every mechanical half is green: criterion-5 phrase greppable, three bullets, four links resolving, all counts independently reproduced."
  - test: "Decide whether the README Status list gets a v1.2 block (entries 18, 19, 20, 21, 21.5, 22) before `/gsd:complete-milestone` runs, and assign the owner."
    expected: "Either a scoped README pass adding the six entries under a `**v1.2 — nothing uncovered.**` sub-header, or an explicit accepted-as-is decision recorded somewhere that outlives the milestone."
    why_human: "This is a scope and product judgement, not a correctness one — nothing in the README is false today. See warning 1 for the verifier's full assessment and recommendation. It is the milestone's last chance to close it before archival, and if `/gsd:complete-milestone` does not touch README, an unassigned item will simply ship."
---

# Phase 22: Limitations recorded — Verification Report

**Phase Goal:** Every surviving README limitation points at a record, and the Limitations
section says plainly that what remains is chosen, not owed.

**Verified:** 2026-08-16T11:32:14Z
**Status:** human_needed — 5/5 roadmap success criteria verified; two items routed to the
user, one by design and one by the verifier's recommendation
**Method:** goal-backward. Both SUMMARYs and 22-VALIDATION were read as *claims*. Every
criterion below was re-proven from the tree: one mutation applied, observed red and reverted;
six independent recomputations. This is a prose-heavy phase, so the verification's centre of
gravity is the git axis, the sweep's non-vacuity, and re-deriving every number the prose
states from the source the prose points at.

---

## Goal Achievement

### Success Criteria (the ROADMAP contract)

| # | Criterion | Status | Evidence the verifier observed |
|---|-----------|--------|--------------------------------|
| 1 | A new ADR states the cost-approximation-by-design position and records why invoice reconciliation via Anthropic's Admin cost API was rejected | ✓ VERIFIED | `docs/adr/0014-cost-approximation-by-design.md`, 156 lines, `**Status:** Accepted`, `**Source:** Phase 22 (2026-08-16), REQ-limitations-recorded`, three `##` headings in the 0012/0013 register. Context argues estimate-by-design with **measured** evidence the verifier traced to source: the 40-vs-25-vs-0 Voyage telemetry at `OPERATIONS:577` and `record_embedding`'s docstring verbatim at `usage.py:498-499`. Decision states the position and the refusal to build reconciliation. `### Rejected alternatives` carries **four numbered Admin-API reasons** (unnarrowable Console key + individual-account precondition; daily-only buckets with workspace/description grouping; ~5-min lag against a synchronous response; infrastructure cost) plus three further alternatives considered and refused. The endpoint's own advertised use case is named before rejection, so the rejection is on fit not capability. Index row present at `docs/adr/README.md`; its counting prose "Ten of the fourteen records are `Accepted` today" independently re-derived by the verifier — 14 files, 10 Accepted (7 plain + 3 `Accepted — supersedes`), 4 Superseded |
| 2 | The mintable-identities limitation points at ADR-0007 instead of standing bare | ✓ VERIFIED | README:357 links `docs/adr/0007-anonymous-identity-fairness-global-cap.md`; `test -f` passes. The record actually argues the bullet's claims, checked line by line: ADR-0007:53–58 reads "Identities are free to mint: clearing browser storage produces a fresh identity with fresh limits… **Because identities are free to mint, per-identity limits cannot be the only bound on the bill.** The global rolling 24-hour spend cap…" — the bullet's three clauses, nearly verbatim. Verify-not-author honoured: the bullet is **byte-identical** to `219e9e3^` (diff empty), last touched `7906a99` (2026-08-10), link entered at `ab54fb5 docs(12-06)` |
| 3 | The free-tier-database limitation points at a database posture note in OPERATIONS.md | ✓ VERIFIED | `### The free-tier posture, and the upgrade path` at `docs/OPERATIONS.md:170`, under `## Going stateless`. The anchor was **re-derived from the heading text** (lowercase, punctuation stripped, spaces→hyphens) rather than string-compared: it yields `the-free-tier-posture-and-the-upgrade-path`, exactly README:358's fragment. The note delivers all three things the bullet promises are behind the link — the tier (Nano, one region, no replica, free), the **measured** headroom (2.84 / 3.23 / 3.39 ms p50 against a 3000 ms budget; 10 pooled connections of Nano's 60), and the one part of the upgrade path that is not a toggle (region is fixed at creation). Every number traces to a pre-existing OPERATIONS measurement (`:248-249`, `:337`, `:700`). The no-read-replica claim is labelled as carried from the published tier shape, not measured, and flagged as wrong in the safe direction if wrong |
| 4 | The four closed bullets are deleted from the README, per the standing convention — never rewritten into release notes | ✓ VERIFIED | **On the git axis, per phrase.** Each of the four distinctive phrases returns exactly **two** commits from `git log -S … -- README.md`, and the direction was measured, not inferred: the earlier commit's diff contains the phrase on a `+` line and `219e9e3` contains it on a `-` line, 1 line each way. Judge: `6d615ec` → `219e9e3`. Forty-answers: `7906a99` → `219e9e3`. `/health` keys: `708c545` → `219e9e3`. Expiry bound: `7906a99` → `219e9e3`. **`git grep -lF` over the whole tree** returns hits for all four ONLY under `.planning/` planning records — no `docs/` surface, no release note, no Status entry, has ever carried any of them. **The sweep re-run by the verifier**: all four enumerated patterns over `docs/` + `.planning/codebase/` → zero hits, so the empty exemption list is genuine. **The sweep is not vacuous by construction** — the verifier ran the same four patterns against `219e9e3^:README.md` and each matched **exactly once**, so the patterns provably match the deleted claims as written. Section shape: 7 bullets → **3**. Broader adversarial paraphrase sweep by the verifier: 4 hits, all false positives (see notes) |
| 5 | The Limitations section's intro states that what remains is chosen, recorded, and argued for | ✓ VERIFIED | `grep -cF 'chosen, recorded, and argued for' README.md` = **1**, at README:354 on its own line — the hard-wrap red was fixed by reflowing the prose rather than by relaxing the gate to tolerate wrapping, which is the correct call and is recorded as such. Every factual claim in the intro checked against the tree: "closed four more" = the four verified deletions; "Three remain" = 3 bullets counted; "found three things free testing structurally could not see" = classifier drift (fixed, ADR-0013) + judge truncation + record/replay divergence, all three present in the eval section or the ADR; **"32 of 38 … where Opus 5 got 37" independently rescored by the verifier from the committed probe's 38 raw rows** (`sonnet=32, opus=37`, every `*_match` field self-consistent, denominator 38, recorded 2026-08-16T05:45:22Z) |

**Score: 5/5 verified. 0 failed. 0 present-behaviour-unverified.**

---

## Independent Measurements (nothing below is read from a SUMMARY)

### Gates the SUMMARYs claim, reproduced

| Gate | SUMMARY claim | Verifier measured | Match |
|---|---|---|---|
| Full keyless suite | 828 passed / 72 skipped | **828 passed, 72 skipped in 26.76s**, exit 0 | ✓ |
| Collected | 900 | **900 tests collected** | ✓ |
| Offline evals | PASS 65/65, real exit 0 | **PASS 65/65 cases (100% vs 90% required)**, `$?` = **0** | ✓ |
| `ruff check .` | clean | **All checks passed!** | ✓ |
| Limitations bullets | 3 | **3** | ✓ |
| Deletion phrases in README | 0, 0, 0, 0 | **0, 0, 0, 0** | ✓ |
| Links resolving | 4 of 4 | **4 of 4**, anchor re-derived from the heading | ✓ |

The suite was run with a single `-q`-free invocation (`-p no:warnings`, no second `-q`), so
the counts are visible rather than suppressed.

### The refusal split, recomputed from disk

```
fixtures = 25 · refusals = 15 · TOTAL = 40 · overlap = []
kinds    = {grader: 7, judge_truncated: 2, recorded_then_failed_replay: 6}
len(GOLDEN) = 40 · denominator = 40 + 25 = 65
```

Every number the README eval section states matches: "Twenty-five cases of forty are
recorded", "grades 65 cases", "the other fifteen", "Seven are the machinery working", "Two
are a real defect", "Six are recordings that passed at record time". The three kinds sum to
15, so the decomposition is total.

### The derived-counts gate — mutated, not trusted

The gate's claim is that a drifted count in README reds the suite. Tested directly:

```
MUTATED: **Twenty-five cases of forty are recorded** -> **Twenty-four …**

E  AssertionError: the tree says 'twenty-five cases of forty are recorded';
   README's eval section does not: …
FAILED tests/test_evals.py::test_the_readme_eval_counts_are_derived_from_the_tree
1 failed, 193 deselected
```

Restored; `git diff --quiet -- README.md` → byte-identical to HEAD. The gate genuinely
binds README prose to `evals/REFUSALS.json`, `evals/fixtures/` and `len(GOLDEN)` — it derives
through `F.fixture_paths()`, `documented_refusals()` and `_SPELLED`, with no literal count and
no parallel loader. It additionally holds the **kind list** (`set(kinds) <= set(phrases)`) and
asserts the decomposition is total, which is the one drift a per-number check cannot see.

### Close-out completeness

| Item | Status | Evidence |
|---|---|---|
| `REQ-limitations-recorded` checked | ✓ | `[x]` at REQUIREMENTS:94 with a dated evidence block; traceability row :139 reads **Complete** with the same evidence shorthand the completed rows use |
| Zero `Pending` cells | ✓ | `grep -c Pending .planning/REQUIREMENTS.md` = **0** |
| `REQ-note-count-bound` flip genuinely owed | ✓ | `git show 04f5668^` shows the checkbox at `[ ]` against its own traceability row already reading **Complete** (2026-08-15) and `20-VERIFICATION.md` `status: passed`, `score: 3/3`. Attributed in the requirement body, not silent |
| `REQ-classifier-model` verified not re-flipped | ✓ | `[x]` at :50, row :138 carrying the measured 37/38-vs-32/38 result and the ADR-0013 pointer — pre-existing, untouched |
| Coverage honest | ✓ | 8/8 mapped, **6 of 8 checked**, the two unchecked named (`REQ-health-credential-validity`, `REQ-demo-csp-header`) as verified-but-awaiting-deploy rather than flipped on a promise |
| ROADMAP progress | ✓ | Phase 22 box checked at :145; `grep -c '\[x\] 22-0[12]-PLAN.md'` = **2**; executed-record paragraph in Phase 21's style; Progress row **16/16 / "All phases executed"**; Next line points at verification then `/gsd:complete-milestone` |
| STATE parses | ✓ | `gsd-tools query state.load` → `state_exists: true`, `roadmap_exists: true`. Frontmatter independently YAML-parsed: `milestone v1.2`, `status executed`, `progress {6/6 phases, 16/16 plans, 100%}`. Open Phase-19 Manual-Only items carried forward, not dropped |
| PROJECT.md counts | ✓ | **828 / 72 / 900** at :31-32, dated 2026-08-16; plus the two adjacent corrections — `docs/adr/` "holds **14** records, four of them superseded" (:29, re-derived by the verifier as 14 / 10 Accepted / 4 Superseded) and "Offline evals grade **65** cases" (:35). Phase 18's deliberate absence of the with-Postgres pass count is preserved |
| Both Phase-20 deferred items settled | ✓ | `deferred-items.md` carries written fates: PROJECT counts **SETTLED** with the commands; `CONCERNS.md` **DISPOSITIONED unedited** per P-08, with a re-measurement confirming the item is still live |
| Milestone archival NOT done | ✓ | `.planning/milestones/` holds only v1.0 and v1.1 artifacts; `git diff --stat main..HEAD -- .planning/milestones/` is empty. Stated as deliberate in ROADMAP:450-451 and STATE. **No overreach** |
| Scope fences held | ✓ | 13 files changed across `main..HEAD`; **zero** under `src/`, **zero** under `evals/`. No grader, judge, dataset or pipeline edit. `tests/test_evals.py` is additive — the new test plus `_SPELLED` extended 20→40 (the sole removed line is the `_SPELLED` line being replaced by its longer form). `CONCERNS.md` untouched |

### 22-VALIDATION Manual-Only row 2 — closed by this verification

The contract left "no bullet stands uncovered" OPEN and routed it here. The walk, per bullet:

| Bullet | What it claims | The record it points at | Covered? |
|---|---|---|---|
| Reported cost is an approximation | cost is never the invoice; token counts are telemetry; **and** invoice reconciliation was rejected | ADR-0014 Context + Decision argue the first two with measured evidence; `### Rejected alternatives` carries the four Admin-API reasons | ✓ both halves |
| Identities are free to mint | fresh identity with fresh limits; limits buy fairness not a bill bound; the global cap is the backstop | ADR-0007:53–58, nearly verbatim | ✓ |
| The database is a single region on a free tier | fine at this traffic; the tier, the measured headroom, and the non-toggle part of the upgrade path are behind the link | OPERATIONS:170's posture note carries all three | ✓ |

**No bullet stands uncovered.** The milestone's acceptance bar is met.

---

## Anti-Patterns

No `TBD`, `FIXME` or `XXX` markers were introduced by this phase's diff. `tests/test_evals.py`'s
additions are substantive (a 40-line test with a docstring naming the 17-04 lesson it applies,
plus a data-table extension). The one deliberate zero-branch in the new test is dead today by
design — no kind is at zero — and exists so that fixing a defect in a successor milestone forces
the sentence out of the prose rather than leaving "zero are a real defect" behind. That is a
guard, not dead code, and the docstring says so.

---

## Gaps Summary

**None.** All five roadmap success criteria are verified against the tree, each by measurement
rather than by reading a claim. The four deletions are proven gone on the git axis and proven
orphan-free by a sweep whose patterns were themselves proven non-vacuous. Every surviving
bullet resolves to a record that argues what the bullet asserts. Every number in the prose was
recomputed from the source the prose points at, and the gate that holds those numbers was
mutated and observed red.

Three warnings are recorded above, none of them a gap against this phase's goal:

1. **The README Status list has no v1.2 block.** Leaving it was a legitimate scope call; closing
   it before archival is the verifier's recommendation. Routed to the user for decision.
2. **`docs/DESIGN.md:34`'s stale Limitations cross-reference** — pre-existing, pre-v1.2, outside
   this phase's patterns and remit.
3. **The `# 828 tests` comment is ungated** — inside the derived-counts test's scope but not in
   its claim list. Cheap successor hardening.

**Milestone readiness:** v1.2's books are closed correctly and archival was correctly NOT
performed. The milestone can proceed to `/gsd:complete-milestone` once the two human items
above are dispositioned — the prose read at PR review, and the Status-list decision.

## The Status-list gap — closed after verification

Verification's recommendation was taken. The README's Status list stopped at 17.5 while the
new Limitations intro claimed "v1.2 has now closed four more", so `v1.2` appeared exactly
once in the whole document and a top-down reader had no way to find out what it was. Six
entries now sit under a **v1.2 — nothing uncovered** sub-header matching v1.1's shape:
18, 19, 20, 21, 21.5, 22.

Three constraints held while writing them. The entries are **transcription against the
verified phase records**, not new authoring — every claim traces to a VERIFICATION or a
SUMMARY. Measurements are quoted **frozen** (37/38 vs 32/38, $9.90 against $17.48, Fly
v21) rather than derived, because `test_the_readme_eval_counts_are_derived_from_the_tree`
scopes to the `## Tests and evals` section and cannot reach Status — a live count here
would be precisely the next thing to go stale unnoticed. And each entry was checked
against the four deleted phrases, since a Status entry is the easiest place to
accidentally resurrect a limitation this phase just deleted; all four still grep **zero**.

The debt was five phases old — 18 through 21.5 each skipped their entry — so this closes
it rather than creating it. Gates after: 828 passed / 72 skipped, evals 65/65 exit 0,
ruff clean. This changes no verdict above; it removes the document's last internal
contradiction before archival.

---

_Verified: 2026-08-16T11:32:14Z_
_Verifier: Claude (gsd-verifier) — goal-backward, 1 mutation, 6 independent recomputations_
