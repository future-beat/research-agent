# Phase 17: Follow-ups that can reach for new information - Research

**Researched:** 2026-08-10
**Domain:** Internal — the supervisor routing table, the responder/researcher seam, the eval before/after, and the documentation sweep. No new libraries, no new services.
**Confidence:** HIGH (every claim below is read directly from this tree at research time; file:line citations throughout)

## Summary

The reversal is smaller in code than in meaning. The entire mechanism lives in
`supervisor_node` (graph.py:472–534) plus two node-local edits: the responder learns to
*signal* insufficiency instead of finalizing a refusal (pre-research only), and the
researcher learns to *append* to `research_notes` instead of overwriting them — today
`researcher_node` does `state["research_notes"] = notes` (graph.py:333), which would
**discard** the session's existing notes on a follow-up pass and silently violate SC-2's
"new notes join the session's set." That one-line replace-vs-append is the sharpest
correctness trap in the phase and nothing in the CONTEXT names it.

The routing change itself is two rows: the existing `no_prior_research` row
(graph.py:497–502) changes destination from END to researcher *in place* — same position,
above the classifier row, which is what keeps "follow-ups never classify" a table property
— and one new row routes a responder-raised insufficiency flag to the researcher, gated by
a `followup_research_done` bool that the supervisor itself sets. Both new-route rows sit
below the three cap rows, untouched. The one-pass bound is structural for the no-notes
path (after research, notes are non-empty, the row cannot re-fire) and flag-gated for the
insufficiency path. Crucially, the row-4 flip is **destination-invisible against the
generic `not research_notes → researcher` row below it** — swapping or deleting row 4
still routes to researcher — so its precedence tests must pin the *side effects* (the
trace event, the `followup_research_done` flag, and classifier-skip when `topic_type` is
empty), not just the destination, or the row is decorative and mutation-unprovable.

The blast radius outside `graph.py` is wide but enumerable, and this document enumerates
it exactly: 4 golden cases flip, 1 follow-up grader breaks by design
(`grade_followup_did_not_research` reds any researcher visit on a follow-up), 3 taxonomy
pin tests were built as before-measures and must be rewritten in the same commit that
flips the dataset, the record-cost preview's follow-up constants under-quote
research-triggering follow-ups (the exact failure mode Phase 15 corrected once already),
and the "no new search" promise lives at 11 distinct shipped locations (grep patterns
below). The recorded fixture does **not** go stale: `technical-figures.json` has one
research turn and zero follow-up turns, so no follow-up semantics touch its replay.

**Primary recommendation:** implement the insufficiency signal as a sentinel-prefix
verdict parsed in `responder_node` (the exact `APPROVED`/`REVISE:` idiom `critic_node`
already uses at graph.py:463–466), route on two new boolean state keys read
deterministically by the supervisor, and ship every routing row move with a
side-effect-pinning precedence test proven red under row-swap mutation.

<user_constraints>
## User Constraints (from CONTEXT.md)

**Source status:** Routine orchestrator calls (standing "proceed without a question round"
preference). Revisable at plan review; not user-ratified.

### Locked Decisions

**The replacement guarantee (ADR-0011's core)**
- Grounding was never "no new searches" — it is "no answer from parametric knowledge."
  The old design conflated the two; the reversal separates them.
- An answer is still produced ONLY from notes the researcher gathered and the critic
  reviewed. What changes is *when* notes may be gathered — mid-conversation, not just at
  session start.
- The window between "notes insufficient" and "new notes arrive" produces NO answer. The
  insufficiency signal routes, it never generates. There is no path where the responder
  answers an unsupported question directly.

**Two trigger paths, one mechanism**
1. No prior notes at all (the current `no_prior_research` END): the supervisor routes the
   follow-up to the researcher directly. No LLM judgment involved; the routing table row
   changes destination from END to researcher.
2. Notes exist but do not cover the question: the responder signals the gap (the signal
   becomes a state flag the supervisor reads, not a final answer). One research pass; the
   enlarged note set gets one authoring attempt; if the critic still finds the answer
   unsupported, the honest "didn't cover that" ships WITH the trace showing research was
   attempted. **Research-per-follow-up is bounded to ONE pass.**

**`no_prior_research` is REDEFINED, not retired (SC-4)** — it stops being a terminal stop
reason and becomes a **trace event**: "this follow-up triggered research because prior
notes were absent/insufficient." The forced-stop vocabulary loses it; the trace gains it.
Everything that enumerates stop reasons (metrics, evals, demo copy) must be swept.

**Routing-table discipline**
- The caps and budget rows stay ABOVE everything: a budget-exceeded follow-up still ENDs
  with `budget_exceeded`. Every row move ships with a precedence test.
- `service.py` still holds no routing logic (SC-6). The insufficiency signal is state; the
  supervisor reads state.

**Cost honesty**
- A research-triggering follow-up now costs like a research run (~$0.21 at current rates).
  The ask routes already carry `reserve_or_429`; note the flat $0.20 estimate with the
  documented threshold; do not resize in this phase unless research shows the estimate
  materially lies.
- Demo copy and README promise "no new search" on follow-ups — whole-file pass on both;
  the follow-up limitation is DELETED.

**Evals: the before/after Phase 15 built**
- The golden `no_prior_research` case(s) flip to expecting a research pass. The
  before-behaviour is preserved in git history and the ADR, not in living tests.
- `followup-admits-a-gap`: decide from the actual case content whether it now triggers
  research (path 2) or legitimately still admits the gap post-research.
- New cases pin: research-triggered follow-up produces a grounded answer; the one-pass
  bound holds; guardrails still outrank the new routing.

**Out of scope — explicitly**
- Multi-pass research loops within one follow-up (bounded to one, by design).
- Any change to session-start research, the critic, the judge, or models.
- The full 40-case record run (still deferred; the fixture staleness note from Phase 16
  stands).

### Claude's Discretion
- The exact state flag name for the insufficiency signal; trace event shape; how the demo
  page surfaces "researching…" on a follow-up turn (it already renders node events).

### Deferred Ideas (OUT OF SCOPE)
- Multi-pass follow-up research; re-recording fixtures; the full record run.
- Post-milestone: the v1.1 completion audit (`/gsd:complete-milestone`).

### Specifics carried from CONTEXT
- The Phase 10 mapping warned that moving the `no_prior_research` row below the
  `not research_notes → researcher` row would "make a follow-up silently run a live web
  search — the exact DEC-04 failure." That accident is now the *intent* — so it must ship
  deliberately, with precedence tests, not as a row shuffle.
- Gate discipline: SIXTEEN vacuous gates found milestone-wide; three consecutive phase-16
  waves found gates with NO probe. `--collect-only` everything; probe every gate; measured
  baselines; honest greens with reasons.
- Whole-file README pass; grep first for facts living only in the deleted prose. Execute
  all waves in one go; one PR; no `model=` overrides.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-followup-live-search | A follow-up whose question is unsupported by prior notes triggers a new research pass instead of terminating with "the research didn't cover that"; `no_prior_research` redefined; grounding survives; change belongs in the supervisor | §Routing Table (before/after, precedence pairs, pinning tests), §The Insufficiency Signal, §Researcher in Follow-up Mode (append-not-replace, SC-2 attribution), §Caps Interplay (worst-case walk under MAX_ITERATIONS=12), §Evals Before/After, §Touch-Point Sweep, §ADR-0011 skeleton |

Roadmap success criteria mapped: SC-1 (§Routing Table), SC-2 (§Researcher in Follow-up
Mode), SC-3 (§The Insufficiency Signal — critic untouched), SC-4 (§Trace Event + §Touch-Point
Sweep), SC-5 (§Caps Interplay), SC-6 (§The Insufficiency Signal — signal is state,
service.py untouched).
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Route follow-up to researcher | Graph supervisor (`graph.py:supervisor_node`) | — | SC-6: `service.py` holds no routing; routing is deterministic Python over state (ADR-0001) |
| Detect "notes don't cover this" | Responder node (`graph.py:responder_node`) | Supervisor reads the flag | The responder is the only component that reads notes against the question; the supervisor must stay model-free, so the node parses and the supervisor routes |
| One-pass bound | Graph supervisor (state flag) | — | A bound is a routing rule, and routing rules live in one place |
| Note append + store write + attribution | Researcher node (`graph.py:researcher_node`) | Memory store (unchanged schema) | Notes have owner + created_at only; attribution is via the note-text task prefix and the turn's trace, both already produced here |
| Turn persistence of enlarged notes | Sessions store (`sessions.py.append_turn`) — unchanged | — | `append_turn` already stores the turn's full final state; the enlarged `research_notes` carries to later turns via `followup_state` with zero store changes |
| Reservation/spend gating | `limits.py` via `service.py` ask routes — unchanged | — | `reserve_or_429` already fires on both ask routes (service.py:723, :745); flat $0.20 stays per CONTEXT |
| Demo "researching…" on a follow-up | `static/index.html` — copy only | `service.py` `_stream` — unchanged | Node events are emitted per finished node from `graph.app.stream` (service.py:322–327) with no mode filter; the researcher stage row renders automatically (§UI) |
| Eval before/after | `evals/dataset.py`, `evals/graders.py`, `tests/test_evals.py` | `evals/__main__.py` cost preview | The flip is recorded by editing cases + graders in step with their taxonomy pins |
| The record | `docs/adr/0011-*.md`, ADR index, README, DESIGN.md, chat.py, service docstrings | — | Reversal must supersede a numbered record (ADR-0003 status line only) |

## Standard Stack

### Core

No new dependencies. The phase is pure modification of existing modules:

| Component | Location | Change class |
|-----------|----------|--------------|
| Supervisor routing | `src/research_agent/graph.py:472–534` | 1 row destination flip in place, 1 new row, 2 new state keys, trace event |
| Responder | `src/research_agent/graph.py:394–438` | Prompt branch + sentinel parse (critic's `APPROVED`/`REVISE:` idiom) |
| Researcher | `src/research_agent/graph.py:292–347` | Append-not-replace on `research_notes` |
| State schema | `AgentState` / `initial_state` / `followup_state` (graph.py:156–239) | Two booleans, per-turn, default False |
| Follow-up graders | `evals/graders.py:186–253` | `grade_followup_did_not_research` replaced by an expectation-keyed bounded-research grader |
| Golden dataset | `evals/dataset.py` | 4 case flips, `Followup` gains fields, 0–2 new cases |
| Taxonomy pins | `tests/test_evals.py:160–230` | Rewritten to the after-taxonomy in the same commit |
| Routing tests | `tests/test_supervisor_routing.py` (38 tests, green at research time) | New precedence pairs, side-effect pins |
| Cost preview | `evals/__main__.py:245–298` | Research-priced follow-up turns for `expect_research` cases |
| Docs/copy | README, DESIGN.md, ADR index, ADR-0003, ADR-0011 (new), chat.py, index.html, service.py docstrings | Sweep per §Touch-Point list |

**Installation:** none. **Version verification:** n/a — no packages are added or upgraded
in this phase; the existing dev venv (`.venv/bin/pytest`, ruff) is the whole toolchain.

## Package Legitimacy Audit

Not applicable — this phase installs **zero** external packages. No slopcheck run needed;
nothing for the planner to gate.

## Architecture Patterns

### System Architecture Diagram (after)

```
                          POST /sessions/{id}/ask[/stream]        (service.py — NO routing here)
                                      │ reserve_or_429  ($0.20 flat, unchanged)
                                      ▼
                     followup_state(previous, question, owner)    (fresh per-turn flags = False)
                                      ▼
        ┌───────────────────────► supervisor ─────────────────────────────┐
        │   caps first, always:  iteration > 12 ──► END max_iterations    │
        │                        revisions > 2  ──► END max_revisions     │
        │                        cost > budget  ──► END budget_exceeded   │
        │                                                                 │
        │   followup ∧ no notes ────────────────► researcher  ← was END   │
        │        (trace event: no_prior_research; sets research_done)     │
        │   followup ∧ insufficient ∧ ¬research_done ──► researcher       │
        │        (trace event: notes_insufficient; sets research_done)    │
        │   no draft ───────────► responder                               │
        │   not reviewed ───────► critic  (UNCHANGED — notes sole truth)  │
        │   not approved ───────► responder (revision loop, capped)       │
        │   else ───────────────► END                                     │
        │                                                                 │
        ▼                                                                 ▼
   responder ── notes cover it ──────────► draft ──► critic ──► APPROVED ─► END
        │                                                └─ REVISE ─► responder
        └─ notes DON'T cover it:
             ¬research_done → emit "INSUFFICIENT: …" sentinel
                              node parses → flag set, draft stays EMPTY
                              (the window produces NO answer — it routes)
             research_done  → honest refusal ships as draft → critic → END
                              (trace proves research was attempted)

   researcher (followup mode): recall(owner) → web search on the FOLLOW-UP question
        → research_notes = existing + "\n\n" + new     ← APPEND, not replace
        → store.add("[<followup question>] <notes>", owner)   ← SC-2 attribution
```

### Recommended change layout (no new files in `src/`)

```
src/research_agent/graph.py        # rows, flags, sentinel parse, append
src/research_agent/chat.py         # HELP + no_prior note copy
src/research_agent/service.py      # ask docstring only ("No new web search." dies)
src/research_agent/static/index.html  # placeholder + comment copy
evals/dataset.py                   # Followup fields + case flips
evals/graders.py                   # bounded-research grader + docstrings
evals/__main__.py                  # follow-up cost constants for expect_research
tests/test_supervisor_routing.py   # precedence pairs, side-effect pins, mutation-proven
tests/test_graph_smoke.py          # sentinel parse, append, end-to-end flip
tests/test_evals.py                # taxonomy rewrite + synthetic-state updates
tests/test_service.py:2541         # placeholder copy pin moves with the copy
docs/adr/0011-*.md (new), docs/adr/0003 (status line), docs/adr/README.md (index),
docs/DESIGN.md (§ the graph paragraph), README.md (3 sites), docs/OPERATIONS.md (reservation prose, optional)
```

---

### Q1 — The routing table, exactly

**BEFORE (graph.py:484–514, verbatim order):**

| # | Condition | Destination | Side effect |
|---|-----------|-------------|-------------|
| 1 | `iteration > MAX_ITERATIONS` (12) | END | `forced_stop_reason="max_iterations_exceeded"` |
| 2 | `revision_count > MAX_REVISIONS` (2) | END | `"max_revisions_exceeded"` |
| 3 | `budget > 0 and cost_usd > budget` | END | `"budget_exceeded"` |
| 4 | `mode=="followup" and not research_notes` | **END** | **`"no_prior_research"`** |
| 5 | `not topic_type` | classifier | — |
| 6 | `not research_notes` | researcher | — |
| 7 | `not draft` | author (writer/responder by mode) | — |
| 8 | `not reviewed` | critic | — |
| 9 | `not approved` | author | — |
| 10 | else | END | — |

**AFTER (proposed):**

| # | Condition | Destination | Side effect |
|---|-----------|-------------|-------------|
| 1–3 | caps and budget — **byte-identical, same order** | END | unchanged |
| 4 | `mode=="followup" and not research_notes` | **researcher** | set `followup_research_done=True`; trace event, reason `no_prior_research` |
| 5 | **NEW** `mode=="followup" and notes_insufficient and not followup_research_done` | researcher | set `followup_research_done=True`; clear `notes_insufficient`; trace event, reason `notes_insufficient` |
| 6 | `not topic_type` | classifier | — |
| 7 | `not research_notes` | researcher | — |
| 8 | `not draft` | author | — |
| 9 | `not reviewed` | critic | — |
| 10 | `not approved` | author | — |
| 11 | else | END | — |

(Flag names are Claude's discretion per CONTEXT; `notes_insufficient` /
`followup_research_done` are used throughout this document as working names.)

**Why row 4 stays exactly where it is.** Keeping the flip *in place* — above the
classifier row — preserves "follow-ups never classify" as a **table property** rather
than a constructor invariant. `followup_state` always sets `topic_type` (graph.py:231,
`previous.get("topic_type") or "general"`), so in practice row 6's classifier never fires
for a follow-up — but `tests/test_supervisor_routing.py` builds states by hand, and the
distinguishing input exists: `mode="followup", topic_type="", research_notes=""` routes to
researcher with row 4 present and to **classifier** with row 4 deleted. That state is the
mutation discriminator for the row's existence.

**The destination-invisibility trap (load-bearing for test design).** After the flip, row
4 and row 7 route to the **same destination** for a no-notes follow-up. A row-swap or
row-delete mutation of row 4 is invisible to any test that only asserts
`next_step == "researcher"`. Row 4's pins must therefore assert its **side effects**:

- `followup_research_done` became True at the supervisor (not at the researcher),
- the trace carries the redefined `no_prior_research` event,
- `forced_stop_reason` stays `""`,
- classifier-skip on the `topic_type=""` discriminator state above.

The same applies to new row 5 vs row 8: with the flag set and draft empty, only row order
decides researcher vs responder — that pair IS observable by destination.

**Every precedence pair that changes, with its pinning test:**

| Pair | Before | After | Pinning test (each proven red under row-swap/row-delete mutation) |
|------|--------|-------|-------------------------------------------------------------------|
| caps(1–3) vs row 4 | both ended the run — order partially unobservable | order now decides END-vs-research | followup, no notes, `iteration=MAX_ITERATIONS` → `max_iterations_exceeded`, NOT researcher; same for `revision_count=MAX_REVISIONS+1`; same for cost>budget (`budget_exceeded`) — three tests, one per cap row |
| row 4 destination | END `no_prior_research` | researcher + trace event | followup, no notes → `next_step=="researcher"`, `forced_stop_reason==""`, trace event present, `followup_research_done` True |
| row 4 vs row 6 (classifier) | row 4 above | unchanged position — pin it anyway | followup, `topic_type=""`, no notes → researcher, never classifier (the row-delete discriminator) |
| caps vs NEW row 5 | n/a | caps win | followup, notes present, `notes_insufficient=True`, each cap tripped → the cap's stop reason, NOT researcher — three tests |
| NEW row 5 vs row 8 (author) | n/a | row 5 above | followup, notes present, draft `""`, flag set, `research_done=False` → researcher NOT responder |
| NEW row 5 one-pass bound | n/a | flag-gated | same state but `research_done=True` → responder (falls through to author); this is THE one-pass test |
| row 5 mode guard | n/a | followup-only | `mode="research"`, `notes_insufficient=True` (hand-built) → normal research routing, never the new row |
| reachability | — | researcher reachable in followup mode | extend `test_every_reachable_next_step_has_an_edge` (tests/test_supervisor_routing.py:266–291) with the two new override combos |

Also required: `initial_state` and `followup_state` pins that both new keys exist and
default False **per turn** (the one-pass bound is per-turn by design — a *new* follow-up
turn gets a fresh pass allowance, which is correct: each turn is a new run with its own
budget, run_id, and reservation, see tests/test_supervisor_routing.py:365–373).

**One-pass structural note:** the no-notes path needs no flag to be bounded — after one
researcher visit `research_notes` is non-empty and row 4 cannot re-fire (a researcher
returning empty text would loop to the iteration cap, exactly as research mode already
can; not a new failure). Setting `followup_research_done` on row 4 anyway is still
required, so a *post-research* insufficiency sentinel can never buy a second pass.

### Q2 — The insufficiency signal

**How "didn't cover that" is produced today:** it is free text the responder LLM
generates, under a prompt instruction (graph.py:421–424: "If the notes do not cover what
was asked, say plainly that the research didn't cover it rather than guessing"). It lands
in `state["draft"]`, the critic reviews it, approves it (it *is* grounded — honestly
refusing is supported by the notes), and the run ENDs approved. There is no detectable
state; the only machine-readable shadow of it is the eval-side `REFUSAL_PATTERNS` regex
(graders.py:529–536), which is a grader, not a router.

**Why the critic cannot be the detector:** the critic's verdict cannot distinguish "a
grounded honest refusal" (APPROVED today, correctly) from "notes insufficient, go
research." An unsupported *answer* gets REVISE — but the refusal is not unsupported. A new
critic verdict is out of scope ("no critic changes", CONTEXT). Reject this option and say
so in ADR-0011's alternatives.

**Recommended mechanism — the sentinel-verdict idiom, parsed in the node:**

The codebase already has exactly this pattern: `critic_node` asks for
`'APPROVED'` or `'REVISE: '+feedback` and Python parses `verdict.startswith("APPROVED")`
(graph.py:458–466). The responder gets the twin:

1. **Pre-research prompt branch** (`mode=="followup" and not followup_research_done`):
   replace the "say plainly" instruction with — *"If the notes do not cover what was
   asked, respond with exactly 'INSUFFICIENT: ' followed by one line naming what is
   missing. Never answer from your own knowledge."*
2. **Node parse** (in `responder_node`, gated on the same condition as the prompt
   branch): if the reply starts with the sentinel → set `notes_insufficient=True`,
   **leave `draft` empty**, `reviewed` stays False, append a trace entry
   (e.g. `{"node": "responder", "insufficient": True}`). The insufficiency window
   produces no answer: the sentinel text is never stored as a draft and never reaches the
   critic or the caller.
3. **Post-research prompt branch** (`followup_research_done` True): keep today's wording
   verbatim — the honest refusal ships as the draft, the critic reviews it, and the trace
   already shows the research attempt. Because the parse is gated on the same condition
   as the prompt, a stray post-research "INSUFFICIENT:" is treated as an ordinary draft
   and the critic deals with it; it cannot re-route (row 5 is flag-gated anyway).

**Why this does not violate ADR-0001 (deterministic routing)** — the argument the
plan-checker will want: the supervisor still routes on plain state; no model call decides
what runs next. The *flag's origin* is model output parsed by a fixed prefix — precisely
how `approved` already works. ADR-0011 should state this equivalence explicitly.

**Signal lifecycle:** supervisor row 5 consumes the flag (clears it) at the moment it
routes, sets `followup_research_done`, and appends the trace event with reason
`notes_insufficient`; row 4 appends reason `no_prior_research`. After research the flags
never route again this turn. **Trace event shape (discretion, recommended):** augment the
supervisor's existing trace append (graph.py:516) rather than invent a new entry type —
e.g. `{"node": "supervisor", "routed_to": "researcher", "followup_research":
"no_prior_research" | "notes_insufficient"}`. That keeps `/sessions/{id}/trace` the
surface of record and costs nothing in the SSE stream (supervisor chunks are deliberately
skipped there, service.py:325–326).

**SC-6 check:** `service.py` changes are docstring-only (the "No new web search." line at
service.py:701). Both ask routes already build state via `followup_state` and call
`reserve_or_429` (service.py:719–723, 744–745). Nothing else moves.

### Q3 — Researcher in follow-up mode

`researcher_node` (graph.py:292–347) needs **two** deliberate behaviours checked, one of
which requires a code change:

1. **The question source is already correct.** The node searches
   `state["task"]` — and in followup mode `task` *is* the follow-up question
   (AgentState comment, graph.py:159; `followup_state` puts the question there via
   `initial_state(question, …)`, graph.py:227). Recall (`store.query(state["task"],
   top_k=3, owner=state["owner"])`) also keys on it. The prompt's
   `RESEARCH_STRATEGY[state["topic_type"]]` cannot KeyError: `followup_state` guarantees
   a valid label (`previous.get("topic_type") or "general"`, and the classifier
   normalizes off-menu labels before any state is persisted). No change.

2. **Notes must APPEND, not replace — this is the phase's sharpest silent bug.** Today:
   `state["research_notes"] = notes` (graph.py:333). On a path-2 follow-up this would
   *discard the session's existing notes*, so the "enlarged note set" would actually be a
   swapped one; the author would draft from only the new notes, prior-turn follow-ups
   would lose their grounding, and SC-2's "new notes JOIN the session's set" fails
   silently — everything would still look green because the critic grades against
   whatever `research_notes` contains. Fix:
   `existing = state["research_notes"]; state["research_notes"] = f"{existing}\n\n{notes}" if existing else notes`.
   Unconditional (no mode check) is safe and simpler: in research mode `existing` is
   always `""` at researcher time (row 7 only routes when notes are empty). Pin with a
   test that a followup-mode researcher pass preserves the prior notes verbatim as a
   prefix.

3. **Attribution (SC-2) — what exists vs what SC-2 needs.** The note store schema is
   `{text, embedding, owner, created_at}` across all four backends (memory.py:274,
   :415, :509–520). There is **no session or turn column anywhere**. What already
   provides attribution, with zero schema change:
   - the stored note's text is prefixed with the task —
     `store.add(f"[{state['task']}] {notes}", owner=…)` (graph.py:334) — and in followup
     mode the task IS the follow-up question, so the note self-describes its turn;
   - `owner` scopes it to the caller (both directions, Phase 12);
   - the follow-up turn's own trace records the researcher visit with `notes_length`
     (graph.py:343–346), and `append_turn` persists that turn's full final state — so the
     session's stored thread proves *which turn* gathered the notes;
   - the enlarged `research_notes` carries to every later follow-up automatically,
     because `followup_state` reads them from the previous turn's stored state
     (graph.py:233).

   **Recommendation:** define SC-2 as satisfied by task-prefix + owner + turn trace.
   Adding a turn/session column would touch four backends plus the shared contract suite
   for zero functional gain — reject in ADR-0011's alternatives.

4. **Recall self-overlap, noted not fixed:** in followup mode, recall may surface the
   session's *own* earlier note (same vocabulary, same owner). The prompt already handles
   it ("Prefer new information not already covered above", graph.py:327). The embedding
   meter and `record_embedding` fold need no change — the researcher is still the only
   embedding node, per its own frame (graph.py:295–301).

### Q4 — The caps interplay, walked exactly

`MAX_ITERATIONS = 2*(MAX_REVISIONS+2)+4 = 12`; `MAX_REVISIONS = 2` (graph.py:40–48).
`iteration` increments on every supervisor entry. The comment at graph.py:41–48 derives
research mode's worst case as supervisor turn `2 + 2*(MAX_REVISIONS+2) = 10`.

**Path 2 worst case (notes exist, insufficiency, research, full revision loop):**

| Sup. turn | Routes to | State after |
|-----------|-----------|-------------|
| 1 | responder | sentinel → flag set, draft empty |
| 2 | researcher (NEW row 5) | notes appended, `research_done=True` |
| 3 | responder | draft rev 0 |
| 4 | critic | REVISE |
| 5 | responder | rev 1 |
| 6 | critic | REVISE |
| 7 | responder | rev 2 (last allowed — mirror of tests:211–220) |
| 8 | critic | REVISE |
| 9 | responder | rev 3, `revision_count=3` |
| 10 | — | `revision_count > 2` → END `max_revisions_exceeded` |

Ten turns — **identical to research mode's worst case**, because signal+researcher (2
turns) replaces classifier+researcher (2 turns). Headroom under the iteration cap: 2.

**Path 1 worst case (no prior notes):** researcher(1), responder(2), critic(3), …,
responder rev3(8), rev-cap stop(9). Nine turns; headroom 3.

**Conclusion: no cap constant changes.** A legitimately-triggered follow-up cannot hit
the iteration cap before the revision cap on any path — the revision cap remains the
reachable backstop and reports the truthful reason, exactly the property the Phase 6 bug
fix established. `MAX_ITERATIONS` stays 12; its derivation comment (graph.py:41–48)
should gain one line noting the follow-up path now shares the same worst case — a comment
edit, not a formula change.

**Where a forced stop can now land mid-path, and what it reports (SC-5):**
- Budget can trip at supervisor turn 2/3 — after the researcher spent real money, before
  any draft. Result: END `budget_exceeded`, empty draft. Honest by existing machinery:
  `grade_answer_present` accepts "empty, explained by forced_stop_reason"
  (graders.py:132–140), `grade_never_silently_unapproved` passes, the demo badge shows
  "NOT approved — budget_exceeded" (index.html:280–285), and the session still records
  the turn with its trace. Notably the new notes ARE stored (memory write happens inside
  the researcher, before the supervisor sees the cost) — a later follow-up can use them.
  That asymmetry is worth one sentence in ADR-0011's consequences, not a fix.
- Per-turn budget context: each follow-up is a fresh run with fresh usage
  (tests/test_supervisor_routing.py:365–373), so a research-triggering follow-up gets the
  full `AGENT_MAX_RUN_COST_USD` ($1.00 default, usage.py:528), which comfortably covers
  the ~$0.21 path.

**Cost honesty (locked):** flat $0.20 reservation unchanged; both ask routes already
reserve. The one edit: `reserved_run_usd`'s docstring (limits.py:114–158) — which already
documents the 2026-09-01 threshold — gains a sentence that research-triggering follow-ups
now sit in the research cost class rather than the pennies class. Optionally mirror in
OPERATIONS where that docstring's prose lives (6 mentions added in Phase 16 wave 2).

### Q5 — Evals: before → after, case by case

**The four affected golden cases (verbatim expectations today):**

| Case (dataset.py) | Today | After (recommended) |
|-------------------|-------|---------------------|
| `followup-admits-a-gap` (:302–323) — "Gartner forecast for agent memory spending in 2027?", `answerable=False`, scripted answer "The research didn't cover Gartner forecasts…" | refusal is the pass; any researcher visit reds `followup_reuses_notes` | **Flip to research-then-grounded**: sentinel → scripted follow-up research notes carrying a Gartner figure → grounded answer, `expect_approved=True`, `expect_research=True`. This is the CONTEXT's "research-triggered follow-up produces a grounded answer" pin. (Case content supports it: a spending forecast is findable; contrast the 2028-share case below.) |
| `followup-refuses-an-uncovered-figure` (:777–804) — "what does lock_timeout default to?" | refusal | **Flip to research-then-grounded** (the answer is real, documented Postgres config — the archetype of "a neighbouring setting one search away"). Gives a second grounded-flip data point on the `technical` stratum. |
| `followup-refuses-a-forecast` (:805–831) — "What share of those banks will have deployed MCP by 2028?", sparse | refusal | **Flip to research-then-STILL-refuses** — the honest tail: sentinel → research pass returns thin/no projection notes → post-research refusal ships as draft, approved, trace shows the attempt. Pins CONTEXT's "if the critic still finds it unsupported, the honest answer ships WITH the trace." A 2028 market-share forecast is genuinely unanswerable, so the case content decides it, as CONTEXT instructs. |
| `followup-with-no-prior-research` (:832–857) — research turn budget-stopped (`budget_usd=1e-7`), follow-up `expect_forced_stop="no_prior_research"`, answer "(never reached)" | the END stop is the pass | **Flip to route-then-guardrail**: the follow-up (fresh usage, cost 0 at turn 1) routes to researcher via new row 4; the scripted researcher call's folded usage trips the case's budget at turn 2 → `expect_forced_stop="budget_exceeded"`, `expect_research=True`, no draft. One case now pins BOTH the row-4 flip and "guardrails outrank the new route" end-to-end through the real graph — the third CONTEXT-required pin, for free. |

Unchanged: `followup-uses-prior-notes`, `followups-chain`, `followups-chain-of-three`,
`followup-stays-inside-thin-notes` — notes cover their questions; no sentinel fires; the
no-research expectation stays and keeps meaning something (see grader redesign).

**Which graders break, exactly:**

| Grader | Status |
|--------|--------|
| `grade_followup_did_not_research` (graders.py:186–194) | **Breaks by design** for every flipped case (reds any classifier/researcher in a follow-up trace). Replace with an expectation-keyed grader over a new `Followup.expect_research: bool = False`: when False → today's check verbatim (answerable-from-notes follow-ups must still never search — the property survives, scoped); when True → **exactly one** researcher visit and **zero** classifier visits (the one-pass bound and never-classify, graded per turn). Recommended name: `grade_followup_research_bounded`. |
| `grade_followup_forced_stop` (:228–245) | Mechanism unchanged; per-case expectations move (`no_prior_research` → `budget_exceeded` on the flipped guardrail case). The `Followup.expect_forced_stop` docstring (dataset.py:60–65: "today only no_prior_research") is falsified — rewrite. |
| `grade_followup_was_checked` / `_expected_stop_fired` (:197–219) | Generic over stop names; survives verbatim. Docstring at :201 cites `no_prior_research` as its example — cosmetic sweep. |
| `grade_recorded_refusal` + `REFUSAL_PATTERNS` (:529–585) | **Survives and stays load-bearing** — post-research refusals (the honest tail) still phrase-match and must not fill the gap. Its `_expected_stop_fired` accommodation simply becomes exercisable only by non-`no_prior_research` stops. |
| New grader (recommended) | Trace-event pin: a flipped turn's trace contains the `followup_research` event with the expected reason — this is what makes SC-4's redefinition *graded* rather than asserted. |

**Taxonomy/property pins that must move in the same commit as the dataset**
(tests/test_evals.py):
- `test_dataset_taxonomy_followup_strata` (:160–175) — requires ≥3 refusal cases and a
  `no_prior_research` stop case; rewrite to the after-strata (≥2 research-triggered
  grounded, ≥1 research-then-still-refuses, ≥1 route-then-guardrail, ≥4 answerable
  no-research, chain intact).
- `test_dataset_taxonomy_phase17_flip_cases_are_tagged` (:216–226) — its purpose expires
  the moment the flip lands; replace with an after-pin (e.g. every `expect_research` case
  states the reversal in its `why`).
- `test_a_followup_with_no_prior_notes_stops_honestly` (:625–670) — asserts
  `forced_stop_reason == "no_prior_research"` end-to-end; becomes the end-to-end flip
  test (routes to researcher; guardrail catches it; trace event present).
- Synthetic-state grader tests at :355–412 use `"no_prior_research"` as their stop-name
  literal; the graders stay generic, but leave the retired vocabulary out of living
  tests — swap the literal for a real stop name so the test suite stops teaching the old
  meaning.
- `test_followup_without_prior_research_refuses_to_answer` (test_supervisor_routing.py:117–122)
  and `test_followup_without_prior_research_makes_no_api_calls`
  (test_graph_smoke.py:201–210) — both flip: the follow-up now routes/spends. The smoke
  test's *replacement* should pin the new truth: it makes researcher+responder+critic
  calls, not zero, and never answers from nothing.

**Offline scripting mechanics the planner must budget for:** the `ScriptedClient`
dispatches on prompt text (harness.py:114–131): `"Search the web"` → returns
`case.notes` — the SAME notes for every researcher call, and `"follow-up question"` pops
one answer per responder call. Flipped cases need (a) a second, *different* researcher
output (the follow-up pass's notes) and (b) **two** scripted responder outputs per
flipped turn (the `INSUFFICIENT:` sentinel, then the post-research answer) — except
path-1 cases, which have one researcher output and one responder output. Recommended:
`Followup` gains `research_notes: str = ""` (scripted output of the triggered pass) and
the sentinel line is authored explicitly in the script (keeping "the script is authored
in the dataset" true, dataset.py:26–29); `ScriptedClient` keeps researcher outputs in a
pop-list like `verdicts`. Also note the prompt-dispatch fragility cuts the right way: if
the responder's pre-research prompt is rewritten so it no longer contains "follow-up
question", the eval notices — by design (harness.py:102–105).

**The recorded fixture does NOT go stale.** `evals/fixtures/technical-figures.json`
holds exactly one turn, labeled `research`, with `models {pipeline: claude-sonnet-5,
judge: claude-opus-5}` (verified by direct read). Replay applies `FOLLOWUP_GRADERS` /
`RECORDED_FOLLOWUP_GRADERS` only to turns after index 0 (harness.py:452–461) — there are
none — and `grade_fixture_current` compares models only, which this phase does not touch
(scope fence: no model changes). The `evals/__main__.py` calibration comment (:224) states
it too: "the calibration case has no follow-ups." Offline stays 41/41 keyless provided
the behavioural leg's flipped cases are re-scripted correctly.

**The record-cost preview under-quotes the new topology — fix it now, cheaply.**
`_assumed_pipeline_cost` (evals/__main__.py:277–294) prices every follow-up turn at
6K-in/2K-out with **zero web searches**. A research-triggering follow-up costs
approximately a research turn (~72K in, 5 web searches — the measured constants at
:245–251). Phase 15 paid $0.24 to learn a 35% under-quote lesson (:214–221); repeating it
knowingly would be worse. Recommended: price `expect_research` follow-up turns with the
research constants (and count their judge call as today). This changes the full-run quote
upward — state the new figure in whatever prose quotes $16.51.

### Q6 — UI + docs touch points (the complete sweep)

**Grep patterns for the whole-file passes** (a single pattern misses sites — chat.py says
"no new **web** search" while README says "no new search"):
`no new` · `didn['’]t cover` · `no_prior_research` · `reach for new` · `skip classification`
· `FOLLOWUP_PLACEHOLDER` · `never searches`

**Shipped-surface inventory (verified at research time):**

| # | Site | What it says | Action |
|---|------|--------------|--------|
| 1 | `README.md:99` | API row: "Follow-up from that session's notes — no new search" | Rewrite (e.g. "reaches for new information when the notes can't answer") |
| 2 | `README.md:155` | Routing table row: "follow-up with no prior notes → END *(`no_prior_research`)*" | Rewrite to the after-table (and the surrounding "the caps, the critic hop and the revision loop are byte-identical in both" at :163–165 — now also byte-identical *plus* the reach rows; check the whole paragraph) |
| 3 | `README.md:254` | Limitation: "**Follow-ups can't reach for new information.** By design…" | **DELETE** (grep the bullet first for facts living only there — it contains none beyond the promise itself; verified) |
| 4 | `docs/DESIGN.md:21` | Full DEC-04 paragraph incl. "the single failure mode…", links ADR-0003 | Rewrite the paragraph to the new guarantee; forward-link ADR-0011 |
| 5 | `docs/adr/0003-…md` | `Status: Accepted` + "That reversal has not happened" (:62–64) | **Status line edit only** (the Nygard convention, per the index: "Only the status line changes") → `Superseded by ADR-0011` |
| 6 | `docs/adr/README.md:47–63` | Index: counting prose "Eight of the ten records are `Accepted` today. Two supersessions…" + row 0003 `Accepted / *expected:* Phase 17` | Add 0011 row; flip 0003 row; counting becomes **eight of eleven / three supersessions** (0003, 0005, 0006) — the Phase 16 lesson about impossible arithmetic applies; also extend the "odd ones out" Source-vs-Promoted paragraph to cover 0011 |
| 7 | `src/research_agent/graph.py:5–19` | Module docstring: followup mode diagram + "Follow-ups skip classification and search entirely" | Rewrite the mode diagram and sentence |
| 8 | `graph.py:394–402, 421–424` | Responder docstring ("it never searches") + prompt | Changes with the mechanism (Q2) |
| 9 | `graph.py:472–479` | Supervisor docstring: "The only thing `mode` changes is which node produces the text" | Now false — mode also changes reach; rewrite |
| 10 | `src/research_agent/chat.py:126–134, 148–158` | `no_prior_research` REPL note ("run a research question first") + HELP "`/ask` … no new web search" | Rewrite both (the stop-reason branch dies with the vocabulary) |
| 11 | `src/research_agent/service.py:701` | `ask` docstring: "No new web search." | One-line edit; **no code** in service.py moves (SC-6) |
| 12 | `src/research_agent/static/index.html:165` | `FOLLOWUP_PLACEHOLDER = "Follow up on that — answered from its notes, no new search"` | Rewrite copy |
| 13 | `index.html:155–156` | Comment: "Follow-ups only use the last two — which is the point of follow-ups" | Rewrite comment |
| 14 | `tests/test_service.py:2541` | Pins the placeholder string count == 1 | Moves with #12 in the same commit or the suite reds |
| 15 | `evals/dataset.py:11–19, 60–65` + flipped-case `why` texts | "a follow-up that re-searches" as a listed failure; "today only no_prior_research"; "Phase 17's before-measure" | Rewrite with the flip |
| 16 | `evals/graders.py:186–219` docstrings | "The whole point is that the notes are already on disk" | Rewrite with the grader redesign |
| 17 | `src/research_agent/limits.py:114–158` (+ OPERATIONS mirror) | Reservation prose | Add the follow-ups-join-the-research-class sentence; no resize (locked) |

**Stop-reason enumerations (SC-4 sweep):** `metrics.py` never enumerates reasons — the
`/metrics` breakdown is a dynamic `GROUP BY forced_stop_reason` (metrics.py:288–289), and
the demo badge prints whatever string arrives (index.html:284). So the redefinition needs
**no data migration and no metrics code change**; historical `no_prior_research` rows in
the runs table will keep appearing in `/metrics` as history, which is honest. The only
hardcoded consumers of the *name* are chat.py:130 (#10) and the eval/test literals (Q5).

**The demo "just works" — verified, with one nuance.** `_stream` emits one SSE `node`
event per finished node with no mode filter (service.py:322–327), `_node_detail` handles
`researcher` unconditionally (service.py:365 — `recalled_from_memory` off the trace), and
the page's `LABELS.researcher = "searching the web"` renders any researcher event
(index.html:157–163, 379–382). A follow-up that routes to researcher therefore shows a
live "searching the web — recalled N note(s)" stage row with **zero JS changes**. The
only UI work is copy (#12, #13). Discretionary polish (a follow-up-specific "reaching for
new information" label) is possible but not needed; recommend copy-only.

### Q7 — ADR-0011 skeleton

File: `docs/adr/0011-followups-reach-for-new-information.md` (number pre-named by the
index forecast on row 0003). Carries `**Source:**` (Phase 17), not `**Promoted from:**` —
extend the index's "odd ones out" paragraph accordingly.

```markdown
# ADR-0011 — Follow-ups reach for new information; grounding means sole-source-of-truth, not no-new-search

**Status:** Accepted — supersedes [ADR-0003](0003-followups-reuse-critic-no-prior-research.md)
**Source:** Phase 17 (REQ-followup-live-search), the reversal ADR-0003 itself forecast.

## Context
ADR-0003 bought grounding by refusing to search: with no new notes possible, the answer
came from existing notes or not at all. That conflated two guarantees. The one worth
keeping is "no answer from parametric knowledge" (ADR-0002's notes-as-sole-truth,
reaffirmed here, untouched). The one being dropped is "no searches after session start" —
which was never the point, only the cheapest way to enforce the point.

## Decision
- Two trigger paths, one mechanism: a follow-up with no prior notes routes straight to
  the researcher (the old END row, destination flipped in place); a follow-up whose notes
  don't cover the question has the responder emit a structured insufficiency sentinel —
  parsed in the node, the critic's APPROVED/REVISE idiom — which becomes a state flag the
  supervisor reads. Routing stays deterministic Python over state (ADR-0001 intact: the
  flag's origin is model output, exactly as `approved` always was).
- The insufficiency window produces NO answer. The sentinel is never a draft; the only
  exits are "answer from notes" or "route to research."
- ONE research pass per follow-up turn, supervisor-enforced. Post-research, the honest
  refusal ships as the final answer — critic-reviewed, with the trace proving the attempt.
- `no_prior_research` is redefined from a forced-stop reason to a trace event naming why
  a follow-up reached ("prior notes absent" / "notes insufficient"). Historical metrics
  rows keep the old meaning as history.
- New notes append to the session's set and are attributed by task-prefix, owner, and the
  turn's trace; the note-store schema is unchanged.

## Consequences
### Accepted
- A research-triggering follow-up costs like a research run (~$0.21 today, more from
  2026-09-01); reservations already cover it; the flat $0.20 estimate stands with its
  documented threshold.
- The caps bound the expanded path with the same worst case as research mode (ten
  supervisor turns against a cap of twelve); the revision cap remains the reachable
  backstop. A budget stop can now land after the researcher spent and before any draft —
  reported honestly, and the gathered notes survive for the next turn.
- The eval before-measures flip; the before-behaviour lives in git history and this record.
### Rejected alternatives
- Critic-as-detector (an honest refusal is APPROVED — the verdict can't see insufficiency).
- Responder answering directly once notes run out (the failure the pipeline exists to prevent).
- Multi-pass research within one follow-up (unbounded cost for marginal reach).
- A turn/session column on notes (four backends + contract suite for zero functional gain).
- Regex refusal-detection as the router (a grader's maintenance cost imported into routing).
```

Companion edits (from Q6): ADR-0003 status line; index row + counting prose
(eight-of-eleven, three supersessions); DESIGN.md forward-link. ADR-0002 is **zero-diff**
— reaffirmed by citation from 0011, per CONTEXT.

### Q8 — see `## Validation Architecture` below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Insufficiency detection | An LLM router, a second classifier call, or a REFUSAL_PATTERNS regex inside the graph | The sentinel-prefix verdict parsed in the node (critic idiom, graph.py:463–466) | Deterministic, already proven in this graph, no new failure vocabulary, no regex maintenance in the routing path |
| Turn attribution for notes | A session/turn column across four store backends | Task-prefix + owner + turn trace (all already written) | Schema change touches memory.py ×4 + the shared contract suite; the existing mechanisms already answer "which turn gathered this" |
| Bounding follow-up research | Cost heuristics, a per-turn researcher budget | One supervisor-owned boolean | The routing table is the one place bounds live and the one place they're unit-testable keylessly |
| Cost control for the new path | A model-aware reservation | The existing flat `reserve_or_429` + per-run `AGENT_MAX_RUN_COST_USD` | Twice-rejected already (limits.py:150–157 and the Phase 16 test that reds the model-aware alternative); CONTEXT locks no-resize |
| Demo progress for follow-up research | New SSE event types or client state | The existing per-node event stream | Verified: researcher events render on follow-up turns with zero JS changes |

**Key insight:** every mechanism this phase needs already exists in the codebase in a
tested form — the verdict-prefix parse, the boolean-row routing table, the trace, the
reservation, the node-event stream. The phase is recomposition, not construction; any
plan that introduces a new mechanism class should be treated as scope creep.

## Common Pitfalls

### Pitfall 1: Researcher replaces the note set instead of enlarging it
**What goes wrong:** `state["research_notes"] = notes` (graph.py:333) silently discards
prior notes on a follow-up pass; the critic grades against the swapped set so everything
stays green while SC-2 is violated.
**Why:** research mode never had pre-existing notes at researcher time, so replace was
always correct until now.
**Avoid:** append-if-existing (Q3); pin with a prior-notes-survive-verbatim test.
**Warning sign:** a flipped eval case whose post-research answer no longer cites
first-turn facts.

### Pitfall 2: Destination-only precedence tests make the new rows decorative
**What goes wrong:** row 4 (followup, no notes) and row 7 (no notes) share a destination;
a test asserting only `next_step == "researcher"` stays green when row 4 is deleted or
swapped below row 7 — the exact "no test can distinguish the guard from its absence"
family STATE.md logs four times this milestone.
**Avoid:** pin side effects (trace event, `followup_research_done`, empty
`forced_stop_reason`, classifier-skip on the `topic_type=""` discriminator); run the
row-swap and row-delete mutations and observe red before believing any green.

### Pitfall 3: The sentinel leaks into the draft (or the parse outlives its prompt)
**What goes wrong:** if the node stores "INSUFFICIENT: …" into `draft`, the supervisor's
`not draft` row won't re-fire after research, or the sentinel reaches the critic/caller;
conversely a parse not gated on the same condition as the prompt branch turns a stray
post-research sentinel into a routing input.
**Avoid:** signal ⇒ draft stays empty; gate parse and prompt on the identical condition;
smoke-test both (sentinel turn produces no draft; post-research sentinel text is treated
as an ordinary draft for the critic).

### Pitfall 4: Flipping the dataset without its taxonomy pins (or vice versa)
**What goes wrong:** `test_dataset_taxonomy_followup_strata` and the flip-tagging test
(test_evals.py:160–175, 216–226) hard-require the before-shape; editing dataset.py first
reds them, editing them first makes the dataset flip ungated. They must move in one
commit, and the after-pins must be as specific as the before-pins were.
**Warning sign:** a taxonomy test rewritten to `assert True`-shaped conditions — the
vacuous-gate failure mode CONTEXT explicitly warns about (sixteen found milestone-wide).

### Pitfall 5: The scripted client can't tell the two researcher calls apart
**What goes wrong:** `ScriptedClient` returns `case.notes` for every "Search the web"
prompt (harness.py:120), so a flipped case's follow-up research pass "finds" the original
notes again and the grounded-answer script has nothing new to ground on.
**Avoid:** per-call researcher outputs (pop-list, like `verdicts`) + a
`Followup.research_notes` script field; author the sentinel line explicitly in the
dataset.

### Pitfall 6: Old state blobs and the new keys
**What goes wrong:** live Postgres sessions store pre-17 state JSON. Any code that reads
the new keys off a *previous* turn's blob with `state["key"]` KeyErrors on a live row —
the exact pre-Phase-12 `owner` lesson (graph.py:216–219 reads defensively for this
reason).
**Avoid:** the new keys are per-turn and initialized fresh in `initial_state`; nothing
should ever read them from `previous`. If any code must, use `.get`. No data migration
needed; no runtime state changes shape (sessions, metrics, notes schemas all untouched).

### Pitfall 7: The cost preview quietly under-quotes the new topology
**What goes wrong:** `_assumed_pipeline_cost` prices follow-up turns without web searches;
a future record run of flipped cases repeats Phase 15's 35% under-quote surprise.
**Avoid:** price `expect_research` turns with the measured research constants now; update
any prose quoting $16.51.

## Code Examples

All patterns cited from this tree (the authoritative source for this phase):

**The verdict-prefix idiom to copy** — graph.py:458–466 (critic): prompt demands
`'APPROVED'` or `'REVISE: ' + feedback`; node does `verdict.startswith("APPROVED")` and
writes booleans into state. The responder's sentinel is this, verbatim in spirit.

**The side-effect-bearing routing row to copy** — graph.py:497–502 (current row 4): a
mode-guarded condition with a named reason. The flip keeps the condition and the reason,
changes `next_step` and moves the reason from `forced_stop_reason` to the trace.

**The defensive-legacy-read to copy** — graph.py:221 / :227 (`previous.get(...)`) for any
read that could touch a pre-17 session blob.

**The precedence-test shape to copy** — tests/test_supervisor_routing.py:186–235
(`test_caps_outrank_an_approved_draft`, `test_the_iteration_cap_still_outranks_the_budget`)
— named by .planning/codebase/ARCHITECTURE.md:418 as "the models to copy."

**The per-turn-fresh-run property already pinned** —
tests/test_supervisor_routing.py:365–373 (`test_a_followup_is_a_new_run_with_its_own_id_and_budget`)
— the reason the one-pass bound is per-turn and the budget walk in Q4 holds.

## State of the Art

| Old Approach (ADR-0003 / DEC-04) | Current Approach (this phase) | When Changed | Impact |
|----------------------------------|-------------------------------|--------------|--------|
| Follow-up with no notes → END `no_prior_research` | → researcher, `no_prior_research` becomes a trace event | Phase 17 | SC-1/SC-4; README routing table row rewritten |
| "Didn't cover that" is a correct final answer, always | Correct only *post-research*; pre-research it is a routing signal | Phase 17 | Responder prompt/parse; refusal graders survive for the post-research tail |
| Grounding = no new searches | Grounding = notes-as-sole-source (ADR-0002, reaffirmed, zero-diff) | Phase 17 | ADR-0011 records the separation |
| Follow-ups cost pennies (responder+critic) | Research-triggering follow-ups cost like research (~$0.21; ~$0.28+ from 2026-09-01 with the revised tail) | Phase 17 | Reservation prose note only; no resize (locked) |
| `grade_followup_did_not_research` unconditional | Expectation-keyed bounded-research grading | Phase 17 | The no-research property survives, scoped to cases whose notes suffice |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `followup-refuses-an-uncovered-figure` should flip to research-then-grounded (vs still-refuses) | Q5 | Low — either direction is implementable; CONTEXT delegates the call to case content, and lock_timeout being real documented config supports grounded. Confirm at plan review. |
| A2 | The flipped `followup-with-no-prior-research` case doubles as the guardrails-outrank pin (budget trips at supervisor turn 2 after the scripted researcher's folded usage) | Q5 | Low — arithmetic verified against the scripted usage constants (harness.py:57–63: 2000 in/400 out/2 searches ⇒ cost ≫ 1e-7), but the offline cost fold path should be sanity-run before trusting the flip's expectations. |
| A3 | A single live research-triggered follow-up (~$0.35–0.45 total) is worth running as the closing checkpoint | Validation | Operator spend decision — precedent in 13-05/15-06/16-04; recommend yes, record-or-defer. |

Everything else in this document is `[VERIFIED: codebase]` — read directly from the tree
at the cited file:line locations on 2026-08-10.

## Open Questions (RESOLVED)

Q1 declared STALE by CONTEXT § Post-research calls (phase 16 was complete; repo state
misread). Q2's no-schema-change recommendation adopted by 17-04's copy-only demo work.
Q3's working names adopted in 17-02's interfaces block.


1. **Phase 16 is 3/4 — is Phase 17 building on settled ground?**
   - What we know: this tree contains 16 waves 1–3 (critic_model, fixture gate, ADR-0010,
     README pass); 16-04 (live haiku-critic demonstration + close checkpoint) is
     unstarted; branches 15/16 are unpushed per ROADMAP; the current branch is
     `gsd/phase-17-followup-live-search`.
   - What's unclear: whether the operator wants 16-04 closed (and PRs landed) before 17
     executes, per the "one PR" instruction in CONTEXT specifics.
   - Recommendation: plan Phase 17 against this tree (nothing in 16-04 changes code); flag
     the sequencing to the operator at plan review, not as a blocker.
2. **Does `RunResponse`/the result card need to say a follow-up reached?**
   - What we know: the live stage row ("searching the web") already shows it during the
     stream; the stored-turn card shows no per-node history (renders question+answer only,
     by design — index.html:252–264); `/sessions/{id}/trace` carries the event.
   - Recommendation: no schema change; the trace event + live stage row satisfy SC-4's
     visibility. Discretionary.
3. **Flag and event names** — `notes_insufficient` / `followup_research_done` / trace key
   `followup_research` are working names; Claude's discretion at plan time (CONTEXT).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/pytest` | all gates | ✓ | collects 757 tests in 0.69s (baseline: routing suite 38 passed) | — |
| `ruff` | lint gate (CI: `ruff check .`) | ✓ (dev extra) | per lockfile | — |
| `ANTHROPIC_API_KEY=""` evals | offline gate | ✓ | 41/41 baseline (40 behavioural + 1 replay) | — |
| Live API keys | ONLY the optional closing checkpoint | operator-held | — | defer the live demonstration (record-or-defer, 16-04 style) |
| Postgres / Fly / deploy | **not required** | — | — | phase touches no deploy config; no `fly secrets`, no cutover |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project `.venv`; config in `pyproject.toml`) |
| Quick run command | `.venv/bin/pytest tests/test_supervisor_routing.py -q` (38 tests, <1s at baseline) |
| Full suite command | `.venv/bin/pytest -q` (757 collected at baseline; armed baseline 756 passed / 1 skipped per Phase 16 wave 3) |
| Offline evals | `ANTHROPIC_API_KEY="" .venv/bin/python -m evals --report /tmp/evals-report.json --min-pass-rate 0.9` — 41/41 baseline, keyless invariant untouched (ci.yml:61–73 must show **zero diffs**) |
| Lint | `.venv/bin/ruff check .` |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| SC-1 | Unsupported follow-up routes to researcher (both paths) | unit | `.venv/bin/pytest tests/test_supervisor_routing.py -q` (new precedence + side-effect pins per Q1 table) | ✅ file exists; tests are new |
| SC-1 | End-to-end flip through the real graph, offline | integration | `.venv/bin/pytest tests/test_graph_smoke.py tests/test_evals.py -q` (flipped smoke + golden cases) | ✅ files exist; tests flip |
| SC-2 | Notes append + attribution (prefix, owner, trace) | unit | `.venv/bin/pytest tests/test_graph_smoke.py -k "research or note" -q` (prior-notes-survive pin, store-write prefix pin) | ✅ / new tests |
| SC-3 | Critic path byte-unchanged; post-research answer critic-reviewed | unit + evals | flipped-case `followup_fact_checked` grades + a zero-diff assertion on `critic_node` (scope fence) | ✅ |
| SC-4 | `no_prior_research` = trace event; stop vocabulary swept | unit + grader | trace-event grader (new) + grep gate over the Q6 inventory | new grader in graders.py |
| SC-5 | Caps bound the expanded path; forced stops honest | unit | Q4 walk as tests: rev-cap fires at supervisor turn 10 on path 2; budget-mid-path reports `budget_exceeded` with empty draft accepted by `grade_answer_present` | ✅ |
| SC-6 | service.py holds no routing | structural | `git diff --stat src/research_agent/service.py` shows docstring-only; existing routing tests never import service | ✅ |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_supervisor_routing.py tests/test_graph_smoke.py -q`
- **Per wave merge:** full suite + offline evals + ruff
- **Phase gate:** full suite green, evals ≥ baseline count (41 grows with any new cases —
  state the expected number, don't accept "≥"), `ruff` clean, ci.yml zero-diff

### Gate discipline (CONTEXT-mandated, with the phase-16 failure named)
- **`--collect-only` every selector before believing it** — two of phase 16's own verify
  selectors collected 0 or missed their target (`-k docstring` → 0 collected). Any `-k`
  expression in a plan ships with its collected count.
- **Probe every gate** — three consecutive phase-16 waves found gates with no probe.
  Every routing precedence pair in the Q1 table gets a named mutation (row swap, row
  delete, side-effect removal) observed RED before the green is recorded. The
  destination-invisible row-4 mutations (Pitfall 2) are the ones a lazy probe misses.
- **Measured baselines:** 757 collected / routing 38 green / evals 41 / ruff clean,
  recorded here at research time — plans state deltas against these, not "tests pass."

### Live-only validation (recommendation)
One real research-triggered follow-up end to end: a cheap research run, then a follow-up
the notes cannot answer, observing sentinel→researcher→grounded answer in the live trace
(or the honest tail). Cost ≈ $0.21 research + ~$0.15–0.25 follow-up ≈ **$0.35–0.45**.
**Recommend YES**, as the phase's closing `checkpoint:human-action` in 13-05/15-06/16-04
record-or-defer style: this is the strongest reversal in the milestone and the
demonstrable-to-an-employer artifact is the point of the project; a single live trace
showing a follow-up that reaches is the cheapest possible proof the guarantee replacement
actually holds. No deploy, no fixture re-record, no `fly secrets` — a local/live API run
only. Defer path: all behaviour is fully pinned offline; the checkpoint records the
deferral like 15's record run.

### Wave 0 Gaps
None — every test file this phase touches already exists
(`tests/test_supervisor_routing.py`, `tests/test_graph_smoke.py`, `tests/test_evals.py`,
`tests/test_service.py`); the framework is installed; new tests slot into existing files.

## Sources

### Primary (HIGH confidence — direct reads of this tree, 2026-08-10)
- `src/research_agent/graph.py` (entire file — routing table :484–514, responder :394–438, researcher :292–347, state :156–239, caps :40–48)
- `src/research_agent/sessions.py`, `src/research_agent/memory.py` (note/session schemas), `src/research_agent/limits.py` (:114–158, reserve/settle), `src/research_agent/service.py` (:646–746 ask routes, :306–381 SSE), `src/research_agent/chat.py` (:118–158), `src/research_agent/metrics.py` (:227–289), `src/research_agent/static/index.html` (:150–330)
- `evals/dataset.py` (all follow-up cases verbatim), `evals/graders.py` (FOLLOWUP/RECORDED graders), `evals/harness.py` (ScriptedClient :99–131, run/replay/record), `evals/fixtures/technical-figures.json` (1 turn, no follow-ups), `evals/fixtures.py` (:1–80), `evals/__main__.py` (:210–304 cost preview)
- `tests/test_supervisor_routing.py` (all 38), `tests/test_graph_smoke.py` (:190–225), `tests/test_evals.py` (:160–230, :355–412, :600–670), `tests/test_service.py:2541`
- `docs/adr/0003-…md` (full), `docs/adr/README.md` (index + counting prose), `README.md` (:93–169, :240–262), `docs/DESIGN.md:21`, `.github/workflows/ci.yml`
- `.planning/`: 17-CONTEXT.md, ROADMAP.md §17 + progress table, REQUIREMENTS.md, STATE.md, codebase/ARCHITECTURE.md (:127–182, :412–418)
- Command evidence: `pytest --collect-only` → 757 collected; `pytest tests/test_supervisor_routing.py` → 38 passed; fixture JSON inspected via script; grep sweeps for the promise inventory.

### Secondary / Tertiary
None used — no external libraries, services, or ecosystem questions in scope.

## Metadata

**Confidence breakdown:**
- Routing table & precedence design: HIGH — read from source; caps walk arithmetically checked against the in-code derivation comment
- Insufficiency mechanism: HIGH for the seam and idiom (critic precedent in-tree); the exact sentinel wording/flag names are discretionary
- Eval before/after: HIGH for inventory and breakage; MEDIUM on the two per-case flip directions flagged in the Assumptions Log
- Pitfalls: HIGH — Pitfall 1 (replace-vs-append) and Pitfall 2 (destination-invisible rows) are verified against current code, not hypothesized
- Cost figures: HIGH for mechanisms (reservation, budget); MEDIUM for the live-run dollar estimate (extrapolated from the measured $0.2427 recording and the limits.py arithmetic)

**Research date:** 2026-08-10
**Valid until:** the next merge to this tree that touches `graph.py`, `evals/`, or the docs listed in Q6 (line numbers cited will drift); content assumptions stable ~30 days
