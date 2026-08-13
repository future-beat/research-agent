# Phase 14: Real cost accounting - Context

**Gathered:** 2026-08-06
**Status:** Ready for research
**Source:** Routine orchestrator calls (per the user's standing "proceed without a question
round" preference). Revisable at plan review; not user-ratified.

<domain>
## Phase Boundary

Reported cost moves from "the shape of the bill" to an approximation of the invoice: a
configurable discount factor and an `inference_geo` multiplier feed cost computation,
`/pricing` exposes which multipliers are in effect, and the docs say plainly what the number
is and is not.

**Not a reversal** — a pure extension of DEC-12 (effective-dated prices, `pricing_unknown`
fails loud, never zero). Lowest-risk requirement in the milestone. Ordered before Phase 16
deliberately: an independent critic model needs a price-table row for whatever it runs on
and a spend cap that accounts for a costlier critic path.

</domain>

<decisions>
## Implementation Decisions (orchestrator calls — confirm at plan review)

### Voyage spend joins /metrics — the Phase 13 debt lands here

- Voyage embedding spend is currently accounted **nowhere** (known since the Phase 10
  codebase mapping; Phase 13 built `VOYAGE_PRICES` in `usage.py` but only the migration
  preview uses it). "Approximates the invoice" is false while a whole provider is missing,
  so per-run embedding cost enters usage accounting and `/metrics` this phase.
- **Honesty constraint from Phase 13's live run:** provider token counts are *telemetry,
  not billing truth* — Voyage reported 25 tokens where the tokenizer predicted 40, and a
  one-word document reported 0 while returning a valid embedding. The docs and `/pricing`
  must describe the figure as an approximation with that caveat, not imply invoice parity.

### Multipliers: two, composable, both default to neutral

- `COST_DISCOUNT_FACTOR` (default 1.0) — one enterprise/negotiated discount factor applied
  to computed cost. `INFERENCE_GEO_MULTIPLIER` (default 1.0) — the `inference_geo`
  adjustment. Both configurable via env, both surfaced by `/pricing`, both applied at cost
  computation time, never mutating the base price table (list prices stay list prices;
  effective-dating stays intact).
- Whether Anthropic's actual `inference_geo` semantics suggest a different shape (per-model?
  request-level field?) is the researcher's question — establish what the API actually
  reports today and design to that, not to the name.

### The September boundary is 25 days out

- Sonnet 5's introductory window ($2/$10) ends 2026-08-31; standard ($3/$15) from
  2026-09-01. SC-3 pins both windows with a test. `/pricing` should make the upcoming
  window visible (current + next), because the operator decision it forces — caps binding
  ~⅓ sooner — is exactly what this phase's surface exists to expose.

### Semantics that must not move

- `pricing_unknown` fails loud, never zero (DEC-12) — including for Voyage models.
- Effective-dating resolves by run date exactly as today.
- The spend cap keeps working: reservations settle to *multiplied* (real) cost, and the
  researcher must check whether `DEMO_RESERVED_RUN_USD`'s default needs a note now that
  settled costs shrink under a discount (< 1.0 factors make the estimate conservative,
  which is safe; say so rather than resize it).

### Post-research calls (2026-08-06, researcher recommendations adopted)

- **Hybrid geo design.** `INFERENCE_GEO_MULTIPLIER` (env, default 1.1 = the published rate)
  configures the *rate*; the **response's `usage.inference_geo` field decides applicability**
  per call. The pinned `anthropic 0.120.0` already declares the field. A blind env multiplier
  can lie — a workspace `default_inference_geo: "us"` bills 1.1× with no code change — while
  the response field cannot. SC-1's "configurable" is satisfied by the rate being env-set.
- **The one choke point is `CallUsage.cost_usd`** — every consumer (per-run cap, RunRecord,
  /metrics, spend_since, daily-cap reserve math, RunResponse, evals, demo badge) is
  downstream of it; `settle()` only deletes the reservation row. Multipliers apply there and
  nowhere else.
- **Voyage: the seam already receives and discards `total_tokens`** — the wrapper keeps only
  `.embeddings`. ≤2 embed calls per research run, ~$0.0002/run. Contextvar meter in
  `usage.py` (set/read in one node frame; thread-safe by construction).
- **Schema risk over arithmetic risk:** new `RunRecord` fields crash `asdict()`-driven
  INSERTs on live tables — use the in-repo migration idioms (sessions.py:92 PG,
  sessions.py:232 SQLite PRAGMA probe).
- **`/pricing` with an unpriced model → 501** (DEC-12-consistent fail-loud), and the payload
  gains a nullable `windows.next` across the 2026-08-31/09-01 boundary. Additive only.
- **Not sending `inference_geo` on requests** — that is a data-residency feature, not
  accounting; deferred deliberately.
- Cap math quantified: under-reservation needs combined multiplier > ~1.33, unreachable at
  the published 1.1 — a docs note, not a guardrail change.

### Out of scope — explicitly

- Billing-API reconciliation (pulling actual invoices). The number stays an approximation.
- Changing cap defaults or the demo guardrails.
- The critic model itself (Phase 16); eval quality (Phase 15).

### Claude's Discretion

- Where multipliers apply in `usage.py`'s call graph; names of any new `/pricing` fields
  (additive only — Phase 12 established the payload must stay additive for rollout).
- Whether Voyage cost rides the existing per-run usage record or a parallel counter.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` § Phase 14 — five success criteria
- `.planning/REQUIREMENTS.md` — REQ-real-cost-accounting
- `.planning/intel/decisions.md` — DEC-12
- `src/research_agent/usage.py` — PRICES, VOYAGE_PRICES, PriceWindow, the cost math
- `src/research_agent/graph.py` — where usage is recorded per node call; the embedder call site
- `src/research_agent/limits.py` — reservation settle path (settles to real cost)
- `src/research_agent/service.py` — `/pricing` and `/metrics` endpoints
- `src/research_agent/metrics.py` — what a run record carries
- `docs/adr/README.md` — no reversal here, so no new ADR expected unless research finds one

</canonical_refs>

<specifics>
## Specific Ideas

- State of the world: release v9 live, two machines, Supabase; suites at plain 529/63,
  armed 591/1 (local PG on :54329, still running). Branch off clean `main` (PR #7 merged).
- **Gate discipline: FIFTEEN vacuous gates across six phases.** Every gate: measured
  baseline AND mutation observed red (or honestly reported green with the reason). Prefer
  behavioural gates to greps; a mutation that goes red by an unrelated route is a false
  positive for the gate it was meant to test.
- README is a per-phase deliverable: the "Cost is computed from list prices" limitation is
  this phase's to rewrite honestly. No `model=` overrides on spawned agents.
- One PR for the whole phase; nothing pushed until it's ready.

</specifics>

<deferred>
## Deferred Ideas

- Invoice reconciliation against the real bill.
- `/health` key-validity probing (still open).
- CSP header for the demo page (logged in Phase 12's deferred items).

</deferred>

---

*Phase: 14-real-cost-accounting*
*Context recorded: 2026-08-06 — orchestrator calls, to be confirmed at plan review*
