# Phase 17: Follow-ups that can reach for new information - Context

**Gathered:** 2026-08-10
**Status:** Ready for research
**Source:** Routine orchestrator calls (standing "proceed without a question round"
preference). Revisable at plan review; not user-ratified. This is the LAST phase of
milestone v1.1 and the strongest reversal — extra care over speed.

<domain>
## Phase Boundary

A follow-up whose question prior notes cannot support **routes to the researcher** instead
of returning "the research didn't cover that." New notes join the session's set, attributed
to the follow-up turn. The critic still grades against notes as the sole source of truth.
The caps still bound everything. The routing change lives in the supervisor.

**The strongest reversal in the milestone — supersedes ADR-0003 (pre-named in the index).**
README marks the current behaviour "By design"; DESIGN.md calls the removed guarantee "the
single failure mode this whole pipeline exists to prevent." The phase's central question,
answered below as the replacement guarantee, is: what does grounding mean once a follow-up
can go get its own notes?

</domain>

<decisions>
## Implementation Decisions (orchestrator calls — confirm at plan review)

### The replacement guarantee (ADR-0011's core)

**Grounding was never "no new searches" — it is "no answer from parametric knowledge."**
The old design conflated the two: refusing to search guaranteed the answer came from
existing notes or not at all. The reversal separates them:

- An answer is still produced ONLY from notes the researcher gathered and the critic
  reviewed. What changes is *when* notes may be gathered — mid-conversation, not just at
  session start.
- **The window between "notes insufficient" and "new notes arrive" produces NO answer.**
  The supervisor routes to the researcher, the researcher gathers, the author drafts from
  the enlarged note set, the critic reviews. There is no path where the responder answers
  an unsupported question directly — the insufficiency signal routes, it never generates.
- The failure mode DESIGN feared — the model improvising when notes run out — remains
  structurally impossible: the responder's only alternatives are "answer from notes" or
  "signal insufficiency," and insufficiency now routes to research instead of END.

### Two trigger paths, one mechanism

1. **No prior notes at all** (the current `no_prior_research` END): the supervisor routes
   the follow-up to the researcher directly — it cannot be answered from nothing, so
   research is the only honest move. No LLM judgment involved; the routing table row
   changes destination from END to researcher.
2. **Notes exist but do not cover the question**: the responder signals the gap (it
   already produces "the research didn't cover that" — that signal becomes a state flag
   the supervisor reads, not a final answer). One research pass is triggered; the enlarged
   note set gets one authoring attempt; if the critic still finds the answer unsupported,
   the honest "didn't cover that" ships WITH the trace showing research was attempted.
   **Research-per-follow-up is bounded to ONE pass** — a follow-up cannot loop
   research→insufficient→research.

### `no_prior_research` is REDEFINED, not retired (SC-4)

It stops being a terminal stop reason and becomes a **trace event**: "this follow-up
triggered research because prior notes were absent/insufficient." The forced-stop
vocabulary loses it; the trace gains it. Everything that enumerates stop reasons
(metrics, evals, demo copy) must be swept — the researcher inventories the touch points.

### Routing-table discipline

- The caps and budget rows stay ABOVE everything: a budget-exceeded follow-up still ENDs
  with `budget_exceeded` — research triggering never outranks a guardrail. The old caution
  stands: this table's row order is load-bearing and has bitten before; every row move
  ships with a precedence test.
- `service.py` still holds no routing logic (SC-6). The insufficiency signal is state; the
  supervisor reads state.

### Cost honesty

- A research-triggering follow-up now costs like a research run (~$0.21 at current rates)
  instead of pennies. The ask routes already carry `reserve_or_429` (Phase 12's structural
  gate) so reservations cover it — but the flat $0.20 estimate is now marginally under a
  typical RESEARCH run and follow-ups join that class. Note it with the documented
  threshold; do not resize in this phase unless research shows the estimate materially
  lies.
- Demo copy and README currently promise "no new search" on follow-ups — that promise is
  the thing being reversed. Whole-file pass on both; the follow-up limitation is DELETED.

### Evals: the before/after Phase 15 built

- The golden `no_prior_research` case(s) currently expect the forced stop — they flip to
  expecting a research pass. The before-behaviour is preserved in git history and the
  ADR, not in living tests.
- The `followup-admits-a-gap` case: decide from the actual case content whether it now
  triggers research (path 2) or legitimately still admits the gap post-research.
- New cases pin: research-triggered follow-up produces a grounded answer; the one-pass
  bound holds; guardrails still outrank the new routing.

### Post-research calls (2026-08-10, researcher findings adopted)

- **The sharpest trap is NOT the routing table:** `researcher_node` does
  `state["research_notes"] = notes` (graph.py:333) — a REPLACE. On a follow-up pass that
  silently discards the session's existing notes and violates SC-2 while everything stays
  green, because the critic grades whatever notes it is handed. Append-not-replace, with a
  pin proving the pre-existing notes survive the second research pass.
- **The row flip is destination-invisible:** post-flip, "followup, no notes → researcher"
  shares its destination with the generic `not research_notes → researcher` row, so
  row-swap/delete mutations cannot be caught by `next_step` alone. Precedence tests pin
  SIDE EFFECTS: the trace event, `followup_research_done`, empty `forced_stop_reason`, and
  the classifier-skip discriminator. Eight precedence pairs enumerated in RESEARCH.
- **The insufficiency signal is the critic's own idiom:** a sentinel-prefix verdict
  (`INSUFFICIENT: …`) parsed in `responder_node` exactly like `APPROVED`/`REVISE:` — flag
  set, draft stays empty, supervisor routes on plain state. ADR-0001 (deterministic
  routing) stays intact by the same argument that makes `approved` legal.
- **Caps need NO changes:** worst-case path-2 follow-up is ten supervisor turns — identical
  to research mode — under MAX_ITERATIONS=12; the revision cap stays the honest backstop.
- **The recorded fixture does NOT go stale** (one research turn, zero follow-ups, models
  untouched — verified). `grade_followup_did_not_research` breaks BY DESIGN; 4 golden
  cases flip; 3 taxonomy pins move in the same commit as the dataset; the record-cost
  preview under-quotes the new topology (the exact 35% lesson Phase 15 paid once — fix the
  assumptions this time).
- **The "no new search" promise lives at 11 shipped locations** (README ×3, DESIGN.md,
  chat.py ×2, service.py docstring, index.html ×2, graph.py docstrings, plus the test
  pinning the placeholder copy) — the sweep uses RESEARCH's grep patterns. The demo needs
  ZERO JS: researcher node events already render "searching the web" on follow-up turns.
- **A1 decided:** `followup-refuses-an-uncovered-figure` flips to the honest-refusal-after-
  one-pass branch — research IS triggered, the scripted researcher still lacks the figure,
  the refusal ships WITH the research attempt in its trace. That pins the otherwise-
  uncovered "one pass then honest gap" behaviour.
- **A3 decided:** the live closing checkpoint runs (one research-triggered follow-up end to
  end, ~$0.35–0.45 ceiling $0.60) — the milestone's last phase closes with wire evidence,
  record-or-defer style.
- Researcher's open Q1 (phase-16 sequencing) is STALE — phase 16 completed and v10 is live;
  the researcher misread repo state. No action.

### Out of scope — explicitly

- Multi-pass research loops within one follow-up (bounded to one, by design).
- Any change to session-start research, the critic, the judge, or models.
- The full 40-case record run (still deferred; the fixture staleness note from Phase 16
  stands).

### Claude's Discretion

- The exact state flag name for the insufficiency signal; trace event shape; how the demo
  page surfaces "researching…" on a follow-up turn (it already renders node events).

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` § Phase 17 — six criteria and the row-order caution
- `.planning/REQUIREMENTS.md` — REQ-followup-live-search ("the change belongs in the supervisor")
- `docs/adr/0003-followups-reuse-critic-no-prior-research.md` — the record being superseded
- `docs/adr/0002-separate-critic-node.md` (notes as sole truth — NOT touched, reaffirmed)
- `src/research_agent/graph.py` — the supervisor routing table (row order is load-bearing),
  `followup_state`, the responder, `forced_stop_reason`
- `evals/dataset.py` — the `no_prior_research` and follow-up cases; `evals/graders.py` —
  refusal/forced-stop graders; the recorded fixture (follow-up semantics unchanged? check)
- `src/research_agent/static/index.html` — the follow-up placeholder copy promising "no new
  search"
- `README.md` — the "Follow-ups can't reach for new information" limitation (DELETE) and
  the API table's "no new search" row

</canonical_refs>

<specifics>
## Specific Ideas

- State of the world: release v10 live (critic on Opus), main at PR #13. Suites plain
  692/65, armed 756/1, offline evals 41/41 keyless. Local PG on :54329 (LC_ALL=C).
- **The routing-table caution has history:** the codebase mapping flagged in Phase 10 that
  moving the `no_prior_research` row below the `not research_notes → researcher` row would
  "make a follow-up silently run a live web search — the exact DEC-04 failure." That
  accident is now the *intent* — which is precisely why it must ship deliberately, with
  precedence tests, not as a row shuffle.
- **Gate discipline: SIXTEEN vacuous gates; three consecutive phase-16 waves found gates
  with NO probe at all.** `--collect-only` everything; probe every gate; measured
  baselines; honest greens with reasons.
- Whole-file README pass; the limitation DELETED (grep first for facts living only in the
  deleted prose). Execute all waves in one go; one PR; no `model=` overrides.

</specifics>

<deferred>
## Deferred Ideas

- Multi-pass follow-up research; re-recording fixtures; the full record run.
- Post-milestone: the v1.1 completion audit (`/gsd:complete-milestone`).

</deferred>

---

*Phase: 17-followups-that-can-reach-for-new-information*
*Context recorded: 2026-08-10 — orchestrator calls, to be confirmed at plan review*
