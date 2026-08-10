---
phase: 17-followups-that-can-reach-for-new-information
plan: 04
subsystem: docs
tags: [adr-supersession, index-arithmetic, whole-file-readme-pass, grep-gate, sc6, partial-execution]

# Dependency graph
requires:
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "01"
    provides: "the grader redesign and the retired follow-up-isolation property, both of which ADR-0011 and DESIGN.md:72 had to stop describing the old way"
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "02"
    provides: "row 4 flipped in place, the trace event, append-not-replace, the budget-stop asymmetry measurement ADR-0011 records as a consequence"
  - phase: 17-followups-that-can-reach-for-new-information
    plan: "03"
    provides: "the sentinel mechanism and — the argument ADR-0011 is built on — the RED-first discovery that the refusal text WAS the shipped draft"
provides:
  - "ADR-0011: the reversal recorded, Accepted, superseding ADR-0003; ADR-0002 reaffirmed by citation and zero-diff against main"
  - "docs/adr/README.md: index arithmetic true against its own table (11 records, 8 Accepted, 3 supersessions), and the reversal register recorded as spent"
  - "README: the follow-up limitation DELETED, the original nine-limitation list closed and said so in two places, Status 17 present"
  - "The 11-location 'no new search' inventory at zero on every tracked surface"
  - "SC-6 proven by AST-equality rather than by hunk count"
affects: [17-04-T3 (unstarted), phase close]

# Tech tracking
tech-stack:
  added: []  # zero packages installed this phase
  patterns:
    - "A gate that greps for the string you just typed is not a gate. The counting prose was verified by a script that reads the TABLE and derives the numbers; probe A5 moves a table row and leaves the prose alone, and every literal grep the plan named stays green while the checker reds."
    - "Prove SC-6 on the code, not on the diff. `git diff` hunk counts are a property of adjacency: probe B1 smuggles a routing `if` in beside a comment edit and the hunk count does not move. Comparing the ASTs modulo docstrings is the same claim made where it cannot be gamed."
    - "Grep before you delete, and relocate what you find. The deleted bullet held exactly one fact that lives nowhere else in the README, and it is still true after the reversal."
    - "A probe that passes is a result to investigate. B2's first attempt was green because `-k demo_page` never collects the test holding the pin; re-targeted by `--collect-only`, it reds in both directions."

key-files:
  created:
    - docs/adr/0011-followups-reach-for-new-information.md
  modified:
    - docs/adr/0003-followups-reuse-critic-no-prior-research.md
    - docs/adr/README.md
    - docs/DESIGN.md
    - README.md
    - src/research_agent/static/index.html
    - src/research_agent/service.py
    - tests/test_service.py

key-decisions:
  - "ADR-0011 and ADR-0003 use the index's supersession wording VERBATIM (`Superseded by ADR-0011 (Phase 17)` / `Accepted — supersedes ADR-0003`), unlinked, matching all four existing precedents. The first draft used markdown links; the index says 'follow this verbatim' and every prior record does, so drift in the one record that supersedes the milestone's highest-severity reversal would have looked like carelessness."
  - "The index's 'remaining *expected* supersessions' sentence was replaced, not just re-counted. ADR-0003 was the ONLY row carrying a forecast, so flipping it left that sentence describing an empty set. The reversal register is now spent and the prose says so — checkable as `grep -c 'expected:' docs/adr/README.md` == 0."
  - "The 'Reading a superseded record' paragraph was extended to ADR-0003 as its sharpest case: 'That reversal has not happened' is a sentence Phase 17 made false, sitting in a record Phase 17 superseded, and a reader who finds it needs to be told on purpose that it stays. Without that paragraph it reads as an oversight in the sweep."
  - "ADR-0011 carries **Source:**, and the index says WHY in its own paragraph. 0011 is the one Source record whose decision reverses a real DESIGN.md passage, so 'no DESIGN.md passage behind it' invites the objection that DEC-04 is right there. The record's argument did not come from a passage — it overturns the record that was promoted from one, and DESIGN.md was rewritten downstream."
  - "The closure claim is stated in § Limitations AND in § Status 17, because the user's instruction was that a reader must actually see it. Probe B5 shows why both matter: deleting the § Limitations sentence leaves `grep -ci nine README.md` at 2, because Status 17 also says it."
  - "service.py took TWO prose hunks, not the plan's one. Line 720's comment ('A follow-up is cheaper than a research run') is falsified by this phase's own change and sits in a shipped file; leaving it would have been a stale promise the sweep exists to remove. SC-6 is proven more strongly instead of more loosely — the AST modulo docstrings is byte-identical to main."
  - "Task 3 (the live checkpoint) is UNSTARTED by instruction, not deferred on judgement. It runs post-merge against the deployed service and the PR is not open."

# Metrics
duration: 55min
completed: 2026-08-10
---

# Phase 17 Plan 04: The record and the sweep Summary

**One-liner:** ADR-0011 records the milestone's strongest reversal with wave 3's own
measurement as its argument — under ADR-0003 the refusal text WAS the shipped draft, and
the critic approved it because a sentence that claims nothing cannot be ungrounded — while
ADR-0003 loses exactly one line, ADR-0002 loses none, the index arithmetic is verified
against its own table rather than against a string, and the README's follow-up limitation is
deleted, closing the last of the nine limitations v1.0 listed.

**Scope: Tasks 1 and 2 only.** Task 3, the live closing checkpoint, is **UNSTARTED** by
instruction — see § Task 3 below.

## Measured baselines and deltas

| Gate | Entering | After | Delta |
|------|----------|-------|-------|
| `.venv/bin/pytest` (plain) | 735 passed / 65 skipped | **735 passed / 65 skipped** | **0** |
| `DATABASE_URL=…:54329 LC_ALL=C .venv/bin/pytest` (armed) | 799 passed / 1 skipped | **799 passed / 1 skipped** | **0** |
| `env -u CRITIC_MODEL ANTHROPIC_API_KEY="" python -m evals` | 41/41 (100%) | **41/41 (100%)** | 0 |
| `tests/test_supervisor_routing.py` | 60 passed | **60 passed** | 0 |
| `.venv/bin/ruff check .` | clean | clean | — |
| `git diff main -- .github/workflows/ci.yml` | 0 lines | **0 lines** | — |
| ADR records on disk | 10 | **11** | +1 |

Every entering baseline was **measured before the first edit**, not taken from the plan:
plain 735/65, armed 799/1, evals 41/41, routing 60, ruff clean, 10 ADRs. All four suite
numbers are unchanged because this plan adds no tests — it rewrites one existing assertion's
string. Zero new skips, so there is no new skip to justify.

Every eval gate ran under `env -u CRITIC_MODEL ANTHROPIC_API_KEY=""`. Phase 16's fixture gate
compares `models.critic` against `graph.critic_model()`, so a `CRITIC_MODEL`-exporting shell
grades the one committed recording stale BY DESIGN and prints a spurious 40/41 that looks
exactly like a regression.

## What shipped

| Task | What | Commit |
|------|------|--------|
| 1 | ADR-0011, ADR-0003's status line, the index arithmetic, DESIGN.md's DEC-04 paragraph | `25c34d7` |
| 2 | README whole-file pass, demo copy + its pin, service.py prose, the final grep gate | `b2d6ccd` |
| 2 | the README's ADR count, stale since phase 16 — found by the whole-file pass | `1ffebe7` |
| 3 | — | **unstarted** |

---

## Task 1 — the record (`25c34d7`)

### ADR-0011, and the argument it is built on

The plan and RESEARCH both offered the design argument: ADR-0003 conflated "no answer from
parametric knowledge" with "no searches after session start", and only the first was ever the
point. That argument is in the record. But the record leads with the **measurement**, because
the user asked for what wave 3 discovered and it is the strongest thing here:

> Under ADR-0003, the refusal text WAS the shipped draft. A responder that concluded the notes
> could not answer wrote exactly that conclusion into `state["draft"]`. The critic graded it —
> and approved it, correctly, by its own rubric, because a sentence that asserts nothing cannot
> be an unsupported assertion. The caller received "the research didn't cover that" as their
> answer, stamped `approved: true`, having passed a grounding gate that had nothing to grade.

That is ADR-0011's § Context, and it does three jobs at once: it is the case for the reversal
(the guarantee held by shipping a non-answer the gate could not distinguish from a good one),
it is the measured reason **critic-as-detector** is rejected (the verdict is structurally blind
to the condition it would have been asked to detect), and it is evidence rather than opinion —
it came out of `cb2e7a5`'s reds, not out of a design discussion.

**What dies, what survives, recorded as separate claims:**

| | |
|---|---|
| **Dies** | "No searches after session start." The `no_prior_research` END state. README's "Follow-ups can't reach for new information." |
| **Survives** | ADR-0002's notes-as-sole-source-of-truth — reaffirmed by citation, **zero-diff**, `git diff main -- docs/adr/0002-separate-critic-node.md` is 0 lines. The replacement guarantee is the *window*: the insufficiency path returns before `draft`, `reviewed`, `revision_count` and the answer-length trace entry are written, so "no answer ships" is control flow rather than convention. |
| **New limit** | The one-pass bound, named as **this record's own deliberate limit** rather than left for a reader to discover, with multi-pass in the rejected alternatives and the honest-tail golden case (A1's `followup-refuses-an-uncovered-figure`) named as the pin for the branch a reversal is most tempted to leave untested. |
| **Redefined** | `no_prior_research` — stop reason → trace event. Not retired: the record says why it is *graded* rather than merely emitted (without it, an intended reach and a reach caused by a row moving by accident look identical, and both look green). |

Also recorded, per the user's instruction and the plan: the ADR-0001 equivalence argument (the
flag's origin is model output parsed by fixed prefix — exactly how `approved` has always
worked, so if this makes routing non-deterministic then `approved` always did); the adopted
names (`notes_insufficient`, `followup_research_done`, trace key `followup_research`); the
append-not-replace fix and why it was invisible rather than safe for fifteen phases; and
17-02's **budget-stop asymmetry** — a stop can now land after the researcher spent and before
any draft, and the notes that pass gathered are written before the supervisor sees the cost, so
they outlive the stop. That one is written as *measured, not predicted*, because it was: it
came out of `expect_notes_stored` staying False against the plan's guess.

A **Carried forward from ADR-0003** section states what survives of the superseded record — the
shared `draft` field, the shared rubric and revision loop, "the research didn't cover that" as
a correct answer (now *after* looking rather than *instead of* looking), and both of 0003's
rejected alternatives. It closes: *what ADR-0003 got wrong was not the standard, it was the
enforcement.*

### ADR-0003: one line, gated against MAIN

```
$ git diff main --numstat -- docs/adr/0003-followups-reuse-critic-no-prior-research.md
1	1	docs/adr/0003-followups-reuse-critic-no-prior-research.md

-**Status:** Accepted
+**Status:** Superseded by ADR-0011 (Phase 17)
```

Diffed against **main**, and re-checked **after** the commit landed — the phase-16 lesson the
user named: a working-tree diff is empty post-commit and passes vacuously. It still prints
`1	1`.

Its § *Expected reversal* ("That reversal has not happened") is untouched. The index's
convention forbids editing anything below the status line, and the sentence is history.

### The index: arithmetic verified against the table, not against itself

`grep -ci "eight of the eleven" docs/adr/README.md` is a gate satisfied by the string I just
typed. The real check reads the table and derives the numbers:

```
$ python check_index.py
records=11 accepted=8 superseded=3 expected_forecasts=0 files=11
OK — prose, table, and files agree
```

It cross-checks four things: files on disk == rows in the table; statuses partition into
Accepted + Superseded; the prose's spelled-out counts equal the derived ones; and every
`Superseded` row names a record that actually says `supersedes ADR-NNNN`, whose own status line
names it back.

**Three pieces of prose went stale with the eleventh record, not one:**

1. *Counting.* "Eight of the ten records… Two supersessions" → **eight of the eleven, three
   supersessions** (0003 Phase 17, 0005 Phase 16, 0006 Phase 12), each still forecast by the
   record it overturned.
2. *The forecast sentence.* "The remaining *expected* supersessions come from the reversal
   register…" — ADR-0003's was the **only** `*expected:*` cell in the table, so flipping it left
   that sentence describing an empty set. Replaced: with Phase 17 the register is spent, every
   supersession in the table is a fact, and no row carries a forecast. `grep -c "expected:"
   docs/adr/README.md` → **0**.
3. *The odd-ones-out paragraph.* "ADR-0006 through ADR-0010" → "ADR-0006 onward", six records,
   plus a new paragraph on the one case that could mislead: 0011 carries `**Source:**` even
   though the decision it reverses *did* come from `docs/DESIGN.md`. Its argument did not come
   from a passage; it overturns the record that was promoted from one, and the passage was
   rewritten afterwards to follow. **The DESIGN paragraph is downstream of 0011, not behind it.**

A fourth was extended: *Reading a superseded record* now covers ADR-0003 as the sharpest case
of the rule, precisely because "That reversal has not happened" now reads like an oversight
unless a reader is told on purpose that it stays.

### DESIGN.md

The DEC-04 paragraph rewritten to the replacement guarantee and forward-linked to ADR-0011,
keeping the ADR-0003 link as the historical record it now points to.

**Grep-before-rewrite, per the acceptance criterion.** Facts in the old paragraph and their
disposition:

| Fact | Disposition |
|------|-------------|
| The responder writes into the same `draft` field the writer does | **kept**, verbatim |
| The critic grades a follow-up with the same rubric and revision loop | **kept**, verbatim |
| "The research didn't cover that" is a correct answer, and the critic makes it stick | **kept**, reworded — it now ships *after* looking |
| "the single failure mode this whole pipeline exists to prevent" | **kept as a fact, dropped as a phrase** — now "the failure this whole pipeline exists to prevent — a model improvising once the notes run out — stays structurally impossible", which states the replacement. `grep -c "single failure mode" docs/DESIGN.md` → **0**; the criterion's first branch is met and the fact is not lost. |
| Asking a second question shouldn't mean re-searching the web | **superseded**, deliberately — it was the rationale being reversed. The cost consequence it protected survives in ADR-0011 § Consequences and in `limits.py`. |
| A follow-up with no prior notes stops with `no_prior_research` | **dies** |

### Deviation — [Rule 1] `docs/DESIGN.md:72`

"Offline evals grade… routing, both guardrails, **follow-up isolation**" names
`grade_followup_did_not_research`, retired in 17-01. Wave 3 fixed the identical sentence in
README:198 and did not know DESIGN.md carried it too. Corrected to "the one-pass bound on a
follow-up that reaches for new notes" — the same wording README already uses — in the same
commit, since DESIGN.md was already open for Task 1.

### Task 1 acceptance criteria, measured

| Criterion | Required | Measured |
|-----------|----------|----------|
| `ls docs/adr/*.md \| grep -cv README` | 11 | **11** |
| `git diff main --numstat -- docs/adr/0003-*` | `1	1` | **`1	1`** (post-commit) |
| `git diff main -- docs/adr/0002-*` | empty | **0 lines** |
| `grep -c "Superseded by" docs/adr/0003-*` | 1 | **1** |
| `grep -ci "eight of the eleven"` | 1 | **1** |
| `grep -ci "three supersessions"` | 1 | **1** |
| `grep -c "0011" docs/DESIGN.md` | ≥ 1 | **1** |
| `grep -c "single failure mode" docs/DESIGN.md` | 0 (or justified) | **0** |
| index arithmetic vs the table | agree | **records=11 accepted=8 superseded=3 files=11** |

---

## Task 2 — the sweep (`b2d6ccd`)

### README: grep FIRST, then delete

The bullet deleted:

> **Follow-ups can't reach for new information.** By design: a follow-up needing a fresh search
> gets "the research didn't cover that" rather than an answer.

RESEARCH row 3 says it "contains none [no facts] beyond the promise itself; verified". **That
is not quite right, and phase 15's near-miss is the reason to check rather than trust it.**
`grep -n "didn't cover" README.md` before the edit returned **one hit — this bullet**. The
sentence "a follow-up that can't answer from its notes says the research didn't cover it" is
still true *after* a research pass, and deleting the bullet would have removed the only place
the README says so.

**Relocated**, not lost — into the routing-table prose, where a reader learns the mechanism:

> One pass per turn, deliberately: if the answer still isn't in the notes after looking, "the
> research didn't cover that" is the answer, and the trace shows the attempt.

### The closure, said where a reader will see it

§ Limitations now opens (quoted, per the acceptance criterion):

> Known, and deliberate for the scope. **The v1.0 README listed nine limitations, and v1.1 has
> now closed all nine** — the last of them in phase 17, where follow-ups stopped being unable
> to reach for new information. Several were closed by narrowing rather than erasing, so their
> narrower successors are still here; everything below is one of those or a limit the v1.1 work
> created.

The claim is **checked against git history, not against itself**. `3acaec7:README.md` is the
v1.0 list; a script reads its nine bullet headings and asserts none survives in today's:

```
v1.0 (3acaec7) listed 9 limitations:
  closed        **Follow-ups can't reach for new information.**      <- this plan
  closed        **The critic shares the writer's model.**            <- phase 16
  closed        **Offline evals can't measure answer quality**       <- phase 15
  closed        **Cost is computed from list prices**                <- phase 14
  closed        **Stores grow without bound.**                       <- phase 12
  closed        **SQLite pins you to one machine.**                  <- phase 11
  closed        **No connection pool.**                              <- phase 11
  closed        **Changing embedding model means a new pgvector table.**  <- phase 13
  closed        **The public demo is rate-limited, not authenticated.**   <- phase 12
today's README lists 6
OK — nine listed in v1.0, zero of them still listed, closure stated, Status 17 present
```

The follow-up bullet was the **last of the nine still standing verbatim** — every other one had
already been closed, most of them by a narrower successor that is still on the list. The
sentence says that too ("closed by narrowing rather than erasing"), because "we closed nine
limitations and still list six" is a fair question and it deserves the honest answer rather
than a silent one.

§ Status v1.1 gains the phase-17 entry in the established style, saying it in its own words:

> - [x] **17 — Follow-ups reach for new information.** … This closes the last of the nine
>   limitations v1.0 listed ([ADR-0011](…), superseding ADR-0003 — the sharpest reversal in the
>   milestone).

### The rest of the whole-file pass

| Site | Change |
|------|--------|
| `:99` API row | "Follow-up from that session's notes — no new search" → "…; one fresh search when they can't answer" |
| routing prose | New paragraph: the two reach rows, the signal that routes instead of shipping, grounding restated as sole-source, the one-pass bound, the relocated refusal fact, ADR-0011 link |
| `:260` | **DELETED** |
| § Limitations opener | the closure |
| § Status | entry 17 |
| § Status entry 3 | **[whole-file pass]** "Follow-ups over prior notes" gained the established `*(… — see 17.)*` parenthetical, exactly as entries 6 and 9 carry for their own later corrections |
| § Status entry 10 | **[whole-file pass]** "Nine numbered ADRs" — stale since phase 16, two behind after this plan. Same parenthetical idiom (`1ffebe7`) |

The routing **table** and the `mode`-changes paragraph were already correct — wave 2 rewrote
them in `c938453` and this plan verified rather than re-edited them (`git diff main` shows
those lines untouched by `b2d6ccd`).

**Whole-file grep, every hit accounted for:**

| Pattern | Hits | Disposition |
|---------|------|-------------|
| `no new` | 0 | — |
| `didn't cover` | 1 (`:181`) | the relocated fact |
| `no_prior_research` | 2 (`:156`, `:170`) | wave 2's routing row + the paragraph stating it is **not** a stop reason |
| `reach for new` | 2 (`:48`, `:272`) | the two closure statements |
| `never search` | 0 | — |
| `never researches` | 1 (`:169`) | **true and load-bearing** — a capped or over-budget follow-up ENDs with its own reason; the guardrails outrank both reach rows, pinned by six tests in 17-02 |
| `isolation` | 0 | retired in wave 3 |
| `735` | 2 (`:15`, `:198`) | correct — this plan adds no tests |
| `nine` (case-insensitive) | 4 (`:40`, `:48`, `:270`, `:271`) | three are the closure statements; **`:40` was a stale fact the pass caught** — see the deviation below |

### Demo copy and its pin, one commit

```
$ git show --stat b2d6ccd
 README.md                            | 23 ++++++++++++++++----
 src/research_agent/service.py        |  8 +++++---
 src/research_agent/static/index.html |  8 +++++---
 tests/test_service.py                |  4 +++-
```

`FOLLOWUP_PLACEHOLDER` → `"Follow up on that — from its notes, or a fresh search if they fall
short"`, and the `LABELS` comment ("Follow-ups only use the last two — which is the point of
follow-ups") now says a follow-up starts at the responder and adds a researcher stage, *and why
that needs no JS*: the node events arrive the same way on either kind of turn. **Zero JS
changes**, as RESEARCH verified — `_stream` emits node events with no mode filter and
`LABELS.researcher = "searching the web"` already renders on follow-up turns.

`tests/test_service.py`'s pin moves in the same commit. It discriminates **in both directions**
— see probes B2/B3.

### service.py — SC-6, proven on the code

```
diff --git a/src/research_agent/service.py b/src/research_agent/service.py
@@ -698,7 +698,7 @@ def ask(
 ) -> RunResponse:
-    """Follow up on a session's research notes. No new web search.
+    """Follow up on a session's research notes; one fresh search if they fall short.
 
     Ownership is enforced HERE rather than by adding the session-tree
@@ -717,8 +717,10 @@ def ask(
     run = followup_state(session.state, body.cleaned(), owner=owner)
-    # A follow-up is cheaper than a research run, not free -- so it reserves
-    # too. Forgetting it here is the specific regression the four-route gate in
+    # A follow-up reserves too. It used to be cheap by construction; since
+    # Phase 17 a follow-up whose notes cannot answer runs a research pass and
+    # costs like one, so this line matters more than it did, not less.
+    # Forgetting it here is the specific regression the four-route gate in
     # tests/test_service.py exists to catch.
     limits.reserve_or_429(limits_store, run["run_id"], owner, metrics)
```

That is the whole diff of `src/research_agent/service.py` against main. **Two prose hunks, not
the plan's one** — the second is a Rule-1 deviation, below.

The plan's gate is "exactly one docstring hunk, no code lines". Hunk counts are a property of
*adjacency*, and probe B1 shows exactly how that fails: a routing `if` inserted beside the
comment edit lands **inside the same hunk** and the count does not move. So SC-6 is gated on the
code instead — parse main's `service.py` and the tree's, strip every docstring (comments never
reach an AST), compare the dumps:

```
$ python sc6_gate.py
main:  972 lines, AST 71291 chars
tree:  974 lines, AST 71291 chars
OK -- service.py's AST modulo docstrings is identical to main; every changed line is prose
```

`service.py` still holds no routing logic, and that is now a statement about the code rather
than about the shape of a diff.

### The final 11-location inventory gate

All 11 RESEARCH sites, with owners:

| # | Site | Owner | State |
|---|------|-------|-------|
| 1 | `README.md:99` API row | **17-04** | rewritten |
| 2 | `README.md` routing row + paragraph | 17-02 (`c938453`) | verified in tree |
| 3 | `README.md:260` limitation | **17-04** | **DELETED** |
| 4 | `docs/DESIGN.md` DEC-04 | **17-04** | rewritten |
| 5 | `docs/adr/0003-*` status | **17-04** | status line only |
| 6 | `docs/adr/README.md` index | **17-04** | arithmetic + 3 stale paragraphs |
| 7 | `graph.py` module docstring | 17-03 (`d0730d8`) | verified in tree |
| 8 | `graph.py` responder docstring | 17-03 (`ba50cd8`) | verified in tree |
| 9 | `graph.py` supervisor docstring | 17-02 (`826049a`) | verified in tree |
| 10 | `chat.py` ×2 | 17-03 (`d0730d8`) | verified in tree |
| 11 | `service.py:701` | **17-04** | rewritten (+ the `:720` comment, deviation) |
| 12 | `index.html:165` placeholder | **17-04** | rewritten |
| 13 | `index.html:155` comment | **17-04** | rewritten |
| 14 | `tests/test_service.py` pin | **17-04** | same commit as #12 |
| 15–17 | evals dataset/graders/limits+OPERATIONS | 17-01 / 17-03 | verified in tree |

```
$ git grep -n "no new search\|no new web search" -- README.md src docs
docs/adr/0011-…md:1:  # ADR-0011 — …grounding means sole source of truth, not no new search
docs/adr/README.md:65: | 0011 | … | …not no new search | Accepted — supersedes ADR-0003 | — |

$ git grep -n "can't reach for new information" -- README.md docs      → 0 hits
$ git grep -n "no_prior_research" -- src/research_agent
graph.py:597:  followup_research = "no_prior_research"     <- the trace event (row 4's branch)
graph.py:626:  # `no_prior_research` used to be a forced…   <- the comment stating the redefinition
```

**Zero stale locations.** The two remaining "no new search" hits are ADR-0011's own **title** —
the record naming the promise it retires — and the index row quoting that title. A record that
cannot name the thing it kills is not a record.

**One honest note on the gate's command.** The plan says `grep -rn … README.md src/ docs/`,
which also returns `src/research_agent.egg-info/PKG-INFO:130` — a stale copy of the README
generated by `pip install -e`. It is **untracked and `.gitignore`d** (`git ls-files
src/research_agent.egg-info` → 0 files; `.gitignore:33` is `*.egg-info/`), so it is build output
rather than a shipped surface, it regenerates on the next build, and it was left alone. The gate
above uses `git grep`, which searches tracked files, so it measures what actually ships.

### Task 2 acceptance criteria, measured

| Criterion | Required | Measured |
|-----------|----------|----------|
| Inventory grep for the "no new (web) search" **promise** | 0 | **0** (2 hits, both ADR-0011's title) |
| `grep -c "can't reach for new information" README.md` | 0 | **0** |
| `grep -ci "nine" README.md` in § Limitations / § Status | ≥ 1 | **4** — 2 in § Limitations, 1 in § Status 17, 1 in § Status 10 (the corrected ADR count) — the closure sentence is quoted above |
| README § Status contains `**17 —` | present | **present** |
| index.html + tests/test_service.py in one commit | yes | **`b2d6ccd`**, stat above |
| `git diff main -- service.py` = prose only (SC-6) | 1 hunk | **2 hunks, both prose; AST identical to main** — diff pasted above |
| Full suite plain | green | **735 / 65** |
| Full suite armed (local PG :54329) | green | **799 / 1** |
| Evals keyless | 41/41 | **41/41** |
| ruff | clean | **clean** |
| `git diff main -- .github/workflows/ci.yml` | 0 | **0 lines** |

---

## Mutation probes — eleven, each red on the assertion that owns it

The plan named none for these tasks (its verification is greps). Waves 1–3 ran ten, fifteen and
thirteen against plans naming three, five and three; every gate here was probed on the same
rule. Applied from pristine scratchpad copies and restored from those copies, not from git,
while work was uncommitted (the 12-06 lesson); `md5` compared after every restore.

### The record (Task 1)

| # | Mutation | Observed red |
|---|----------|--------------|
| A1 | ADR-0003's status reverted to `Accepted` | numstat → **empty**; `grep -c "Superseded by"` → **0**; checker: *ADR-0003's own status line does not name ADR-0011* |
| A2 | **T-17-14** — ADR-0003 edited BEYOND its status line (a Context sentence reworded) | numstat → **`2	2`**, gate requires exactly `1	1`. Note: `grep -c "Superseded by"` stays **1** — only the numstat gate sees this, which is why the plan specifies it exactly rather than approximately |
| A3 | ADR-0002's status line touched | zero-diff gate → **12 lines** |
| A4 | **T-17-15** — counting prose says "Nine of the eleven" | checker: *prose does not state the derived count: expected 'eight of the eleven…'* |
| A5 | **T-17-15, the important one** — the TABLE ROW drifts (0003 back to `Accepted`), prose left alone | checker reds on **both** count clauses (*expected 'nine of the eleven'*, *'two supersessions'*). **Both of the plan's literal greps stay GREEN** — `eight of the eleven` = 1, `three supersessions` = 1. This is the vacuous gate the Phase 16 lesson names, found by probing rather than by reading |
| A6 | ADR-0011 stops claiming the supersession | checker: *row 0003 says ADR-0011 supersedes it, but 0011-….md does not say so* |

### The sweep (Task 2)

| # | Mutation | Observed red |
|---|----------|--------------|
| B1 | **T-17-16 / SC-6** — a routing `if not run["research_notes"]: run["next_step"] = "researcher"` inserted next to the comment edit | AST gate: *FAIL — executable code changed in service.py*. **The hunk count stays at 2**, so the plan's hunk-shaped gate would have passed this |
| B2 | the demo copy moves, the pin does not | `test_page_copy_and_dom_present` — *assert 0 == 1* on the new string |
| B3 | the pin moves back to the old copy, the page does not | same test, the other direction — *assert 0 == 1* against the pre-17 string |
| B4 | the deleted limitation bullet comes back | checker: *README claims all nine closed; still listed: ["**Follow-ups can't reach for new information.**"]* |
| B5 | the § Limitations closure sentence deleted, bullet still gone | checker: *README no longer states the closure*. **`grep -ci "nine" README.md` stays at 2**, because § Status 17 also says it — the plan's literal gate does not see this |
| B6 | § Status's phase-17 entry removed | checker: *README § Status has no phase-17 entry* |

**B2 failed as a probe first, and the probe was what was wrong.** Run as `pytest
tests/test_service.py -k demo_page`, the mutation printed **3 passed** — because that selector
never collects the test holding the pin. `--collect-only` on the whole tree showed 5 tests under
`-k demo_page` and 1 under `-k page_copy_and_dom_present`; re-targeted, it reds. Wave 2's P13 and
wave 3's R3 were the same shape. A probe that passes is a result to investigate, never a green
to bank.

## `--collect-only` on every selector used

Each run against the whole `tests/` tree, not against the file under edit.

| Selector | Collected | Note |
|----------|-----------|------|
| `tests/ -k demo_page` | **5** | the WRONG selector — none of the five holds the placeholder pin |
| `tests/ -k page_copy_and_dom_present` | **1** | the pin's actual owner; B2 and B3 both red it |

## Deviations from plan

### [Rule 1 — a comment falsified by this phase] service.py takes a second prose hunk

**Found during:** Task 2, reading `service.py` for the docstring. Line 720 read *"A follow-up is
cheaper than a research run, not free -- so it reserves too."* The first clause is exactly the
claim this phase reverses, and it sits in a shipped file three lines from the docstring being
corrected. Leaving it would have shipped a stale promise inside the sweep that exists to remove
them, in the specific place a future reader would trust it (sizing the reservation). Rewritten
to say a reaching follow-up costs like a research run, so the reserve call matters more than it
did; the load-bearing second sentence about the four-route gate is preserved verbatim.

This makes the diff two hunks against the plan's one. SC-6's *intent* — no routing logic in
`service.py` — is not weakened but proven harder: the AST modulo docstrings is byte-identical to
main's, and probe B1 shows that gate catching a mutation the hunk-count gate cannot see.
**Files:** `src/research_agent/service.py`. **Commit:** `b2d6ccd`.

### [Rule 1 — the sentence wave 3 fixed in one file and not the other] `docs/DESIGN.md:72`

**Found during:** Task 1, scanning DESIGN.md for other follow-up prose before rewriting DEC-04.
"Offline evals grade… routing, both guardrails, **follow-up isolation**" names the grader
retired in 17-01. Wave 3 corrected the identical claim at README:198 and did not check
DESIGN.md. Fixed to the wording README already uses. **Commit:** `25c34d7`.

### [Rule 2 — three stale paragraphs, not one] The ADR index

**Found during:** Task 1. The plan and the user both flagged the counting prose. Two more
paragraphs go stale with the eleventh record and neither was named: the *"remaining expected
supersessions"* sentence, which described an empty set the moment 0003's forecast became fact
(ADR-0003 was the only row carrying one), and *Reading a superseded record*, which enumerates
0006 and 0005 by name. Both rewritten. A fourth — odd-ones-out — was named and also gained a
paragraph explaining the one thing about it that could mislead. **Commit:** `25c34d7`.

### [Rule 1 — what a whole-file pass is for] The README's ADR count, stale since phase 16

**Found during:** the self-check, when `grep -ci "nine" README.md` returned 4 rather than the 3
closure hits I expected. The fourth is § Status entry 10: *"Nine numbered ADRs under
`docs/adr/`"*. It was **measured and true when written** — `git log -S` puts it at `bafaff0`
with exactly nine records on disk — but phase 16 made it ten and this plan makes it eleven.

Nobody's whole-file pass had caught it because nobody had had a reason to grep for a number
word. Corrected in the README's own established idiom for a Status entry a later phase
falsified: *"(Nine then; eleven now, three of them superseded on the record — see 16 and 17.)"*,
the same shape entries 3, 6 and 9 already carry. The eleven and the three are the numbers the
index checker derives from the ADR table, so the two documents cannot drift apart silently.
**Commit:** `1ffebe7`.

Checked in the same pass and **left alone**: "and 20 other calls that could have gone the other
way" (README:191) — `docs/DESIGN.md` holds 23 bold-lead decision paragraphs, of which the
sentence names three, and this plan rewrote two paragraphs in place without adding or removing
one (`git diff main --numstat -- docs/DESIGN.md` → `2	2`).

### [convention over polish] The supersession status lines are unlinked

**Found during:** Task 1. Both status lines were first written with markdown links
(`Superseded by [ADR-0011](…)`). The index states the convention *verbatim* and all four
existing supersession lines (0005, 0006, 0007, 0010) use the plain form. Changed to match before
committing: a record that supersedes the milestone's highest-severity reversal is the last place
to introduce format drift. The table cells DO carry links, as the existing rows do.

### [ruff, caught by the gate] The pin wrapped

The new placeholder string put `tests/test_service.py:2541` at 102 chars (E501, limit 100).
Wrapped the `assert page.count(...)` call across three lines; the string itself stays one
literal, so the pin is still an exact-match count. Caught by `ruff check .` in the Task 2 gate
run, before the commit.

### [standing instruction] README test count

**Not** changed: this plan adds no tests, plain stays **735**, and both README sites (`:15`,
`:198`) already say 735. Verified rather than assumed.

## Task 3 — the live closing checkpoint: UNSTARTED

**Not executed, and not deferred on judgement** — the executing instruction scoped this run to
Tasks 1 and 2. Task 3 runs post-merge against the deployed service and the phase PR is not open
yet, so there is nothing on the wire to point it at.

Its state is **unstarted**, not resolved by either of the checkpoint's two paths. Nothing in this
plan has consumed it, and the phase is not closed until it resolves. What remains, verbatim from
the plan:

- `POST /research` with a narrow question, then `POST /sessions/{id}/ask` a follow-up the notes
  cannot cover.
- Capture: a researcher stage on the **follow-up** turn in the SSE stream; the answer grounded in
  the new notes (or an honest refusal **with** the attempt in the trace — both pass);
  `/sessions/{id}/trace` carrying the supervisor entry with the `followup_research` reason and
  `forced_stop_reason` NOT `no_prior_research`; a research-class cost on the follow-up turn.
- Estimated ~$0.35–0.45, **ceiling $0.60**, abort past it. Operator-held `ANTHROPIC_API_KEY` and
  `VOYAGE_API_KEY`.
- The defer path (Phase 15's record-run style) remains equally valid: all behaviour is pinned
  offline by three golden cases, four smoke tests and twelve precedence pairs.

## Threat register — dispositions discharged

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-17-13 | mitigate | The deleted bullet was grepped first; one fact lived only there and was relocated to the routing prose. DESIGN.md's paragraph got the same treatment, fact by fact, in the table above |
| T-17-14 | mitigate | numstat `1	1` against **main**, re-checked post-commit; probe A2 reds it at `2	2` while the status-line grep stays green |
| T-17-15 | mitigate | Arithmetic derived from the table by script, not grepped; probes A4 **and A5** red it, and A5 is the case where every literal gate stays green |
| T-17-16 | mitigate | Full service.py diff pasted; AST modulo docstrings identical to main; probe B1 reds it on smuggled routing logic the hunk count cannot see |
| T-17-17 | — | **Not reached** — Task 3 unstarted, no spend occurred |
| T-17-SC | accept | Zero packages installed |

No new security-relevant surface: this plan changes prose, one demo copy string and one test
assertion. No network endpoint, auth path, file access pattern or schema moved — proven for
`service.py`, the only source file touched, by the AST gate.

## Known stubs

None from this plan. One **open item** that is not a stub: Task 3 is unstarted, and § Task 3
above states exactly what it costs and what it would show.

## What remains for the phase

- **Task 3** — the live checkpoint, above.
- The VALIDATION sign-off boxes (`17-04-T1`, `17-04-T2`) are satisfiable on the evidence here;
  they are left ⬜ to match waves 1–3, none of which ticked its own rows.
- Branch `gsd/phase-17-followup-live-search`, **unpushed**, 25 commits ahead of main (three of
  them this plan's: `25c34d7`, `b2d6ccd`, `1ffebe7`). One branch, one PR, as locked. Nothing
  pushed and nothing merged by this plan.

## Self-Check: PASSED

- `.planning/phases/17-followups-that-can-reach-for-new-information/17-04-SUMMARY.md` — FOUND
- `docs/adr/0011-followups-reach-for-new-information.md` — FOUND
- `25c34d7` FOUND · `b2d6ccd` FOUND · `1ffebe7` FOUND
- All seven modified files present; plain 735/65, armed 799/1, evals 41/41 keyless, routing 60,
  ruff clean, CI diff 0, ADR count 11 — all measured after the last probe restore, with
  `git status --short` clean and every `md5` matching its pristine copy.
