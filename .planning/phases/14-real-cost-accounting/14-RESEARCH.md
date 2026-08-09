# Phase 14: Real cost accounting - Research

**Researched:** 2026-08-09
**Domain:** Cost accounting — pricing multipliers, embedding spend, `/pricing` surface
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (orchestrator calls — confirm at plan review)

**Voyage spend joins /metrics — the Phase 13 debt lands here**
- Voyage embedding spend is currently accounted **nowhere** (known since the Phase 10
  codebase mapping; Phase 13 built `VOYAGE_PRICES` in `usage.py` but only the migration
  preview uses it). "Approximates the invoice" is false while a whole provider is missing,
  so per-run embedding cost enters usage accounting and `/metrics` this phase.
- **Honesty constraint from Phase 13's live run:** provider token counts are *telemetry,
  not billing truth* — Voyage reported 25 tokens where the tokenizer predicted 40, and a
  one-word document reported 0 while returning a valid embedding. The docs and `/pricing`
  must describe the figure as an approximation with that caveat, not imply invoice parity.

**Multipliers: two, composable, both default to neutral**
- `COST_DISCOUNT_FACTOR` (default 1.0) — one enterprise/negotiated discount factor applied
  to computed cost. `INFERENCE_GEO_MULTIPLIER` (default 1.0) — the `inference_geo`
  adjustment. Both configurable via env, both surfaced by `/pricing`, both applied at cost
  computation time, never mutating the base price table (list prices stay list prices;
  effective-dating stays intact).
- Whether Anthropic's actual `inference_geo` semantics suggest a different shape (per-model?
  request-level field?) is the researcher's question — establish what the API actually
  reports today and design to that, not to the name. *(Answered below: it is a request
  parameter AND a per-response usage field — see "The inference_geo reality".)*

**The September boundary is 25 days out**
- Sonnet 5's introductory window ($2/$10) ends 2026-08-31; standard ($3/$15) from
  2026-09-01. SC-3 pins both windows with a test. `/pricing` should make the upcoming
  window visible (current + next), because the operator decision it forces — caps binding
  ~⅓ sooner — is exactly what this phase's surface exists to expose.

**Semantics that must not move**
- `pricing_unknown` fails loud, never zero (DEC-12) — including for Voyage models.
- Effective-dating resolves by run date exactly as today.
- The spend cap keeps working: reservations settle to *multiplied* (real) cost, and the
  researcher must check whether `DEMO_RESERVED_RUN_USD`'s default needs a note now that
  settled costs shrink under a discount (< 1.0 factors make the estimate conservative,
  which is safe; say so rather than resize it).

**Out of scope — explicitly**
- Billing-API reconciliation (pulling actual invoices). The number stays an approximation.
- Changing cap defaults or the demo guardrails.
- The critic model itself (Phase 16); eval quality (Phase 15).

### Claude's Discretion
- Where multipliers apply in `usage.py`'s call graph; names of any new `/pricing` fields
  (additive only — Phase 12 established the payload must stay additive for rollout).
- Whether Voyage cost rides the existing per-run usage record or a parallel counter.

### Deferred Ideas (OUT OF SCOPE)
- Invoice reconciliation against the real bill.
- `/health` key-validity probing (still open).
- CSP header for the demo page (logged in Phase 12's deferred items).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-real-cost-accounting / SC-1 | A configurable discount factor and an `inference_geo` multiplier feed cost computation | "The inference_geo reality" + "The one choke point" — discount as env factor; geo as env-configurable rate applied when the *response* reports `usage.inference_geo == "us"` (field verified in anthropic 0.120.0) |
| REQ-real-cost-accounting / SC-2 | `/pricing` exposes which multipliers are in effect, not just base rates | "The /pricing extension" — additive `multipliers`, `windows` (current+next), `embedding` keys; current payload and consumers mapped |
| REQ-real-cost-accounting / SC-3 | Effective-dating resolves across 2026-08-31 → 09-01, test pins both windows | "SC-3 already half-exists" — four fixed-date tests in test_usage.py survive the boundary; what the phase adds is multiplied-cost boundary tests and a date-parameterised window helper for /pricing |
| REQ-real-cost-accounting / SC-4 | `pricing_unknown` fails loud, never zero — including Voyage | `record_embedding` path mirrors `record()`: UnknownModelPricing → `pricing_unknown = True`, tokens counted, cost stays a floor. Unknown geo value also fails toward the flag, not toward 1.0 |
| REQ-real-cost-accounting / SC-5 | `/metrics` cost moves to invoice-approximation; docs say which it is | Voyage spend enters the run usage dict and the runs table (column migration idioms exist in-repo); README limitation rewrite is a phase deliverable per CONTEXT |
</phase_requirements>

## Summary

Two external facts decide this phase's shape, and both were verified today rather than
assumed. First: `inference_geo` is not a billing-side mystery — it is a documented request
parameter on `POST /v1/messages` (`"global"` default, `"us"`), it carries a published
**1.1x multiplier on all token pricing categories** for Claude 4.6+ models, and — the
decisive part — **the response `usage` object reports `inference_geo`**, i.e. where
inference actually ran. The pinned SDK (anthropic 0.120.0, in `.venv`) already declares
`Usage.inference_geo` and `Messages.create(inference_geo=...)`. Crucially, a workspace can
set `default_inference_geo: "us"` in the Console, so a request that never sends the
parameter can still be billed at 1.1x — which means a blind operator-declared multiplier
can silently disagree with the invoice, while the response field cannot. Design to that:
the geo multiplier's *applicability* comes from the observed response field; only its
*rate* is configuration (`INFERENCE_GEO_MULTIPLIER`, default 1.1, applied when the
response says `"us"`). The discount factor stays a plain env number — negotiated discounts
are genuinely invisible in the API (docs: applied at invoice/CCU-conversion time).

Second: the Voyage seam already receives the token count and throws it away.
`voyageai 0.5.0`'s `EmbeddingsObject` carries `.total_tokens` beside `.embeddings`;
`VoyageEmbedder.embed_documents/embed_query` keep only `.embeddings`. A research run makes
at most 2 Voyage calls (1 recall query — skipped when the caller's store is empty — plus
1 note write); a follow-up makes 0. Count Voyage's **reported** tokens (the local
tokenizer alternative both overestimates — 40 vs 25 in Phase 13's live run — and fetches
a tokenizer from the HF hub on first call, a network dependency the hot path must not
have), and phrase the docs exactly as CONTEXT demands: telemetry, not billing truth.

The one choke point for `discount × geo` is `CallUsage.cost_usd()` — the only place
Claude tokens become USD. Every consumer (supervisor per-run cap, run record, `/metrics`,
`spend_since` → daily-cap reserve math, RunResponse, evals harness, demo page badge) sits
downstream of it, so multiplying there means the reservation settle sees real multiplied
cost with zero second call sites. The main construction risk in the whole phase is not
arithmetic — it is that `RunRecord` fields map 1:1 to database columns via `asdict()`, so
new embedding fields need a column migration on live tables. Both idioms already exist
in-repo (Postgres `ADD COLUMN IF NOT EXISTS` in the schema block; SQLite
`PRAGMA table_info` probe + `ALTER TABLE`, sessions.py:232–241).

**Primary recommendation:** multiply inside `CallUsage.cost_usd` using the response-observed
`inference_geo` plus two per-call-read env factors; capture Voyage `total_tokens` via a
contextvar meter in `usage.py` that `VoyageEmbedder` reports into and `researcher_node`
folds into `state["usage"]`; extend `/pricing` additively with `multipliers`, `windows`
(current + next, nullable), and `embedding`.

## Architectural Responsibility Map

Single-service backend — tiers map to modules:

| Capability | Primary Owner | Secondary | Rationale |
|------------|--------------|-----------|-----------|
| Multiplier arithmetic + env parsing | `usage.py` (`CallUsage.cost_usd`) | — | The only token→USD point for Claude calls; every consumer is downstream |
| Geo observation | `usage.py` (`CallUsage.from_response`) | — | The response `usage.inference_geo` field is captured where every other usage field already is |
| Voyage token capture | `memory.py` (`VoyageEmbedder`) | `usage.py` (meter) | The SDK response carrying `total_tokens` is only visible inside the wrapper |
| Embedding cost fold into the run | `graph.py` (`researcher_node`) | `usage.py` (`record_embedding`) | The only graph node that touches the store; it holds `state["usage"]` |
| Run-record columns + /metrics aggregates | `metrics.py` | — | `asdict(RunRecord)` drives INSERT columns; summary shape shared by both backends |
| `/pricing` payload | `service.py` | `usage.py` (window helpers) | Endpoint stays thin; date logic lives in unit-testable helpers |
| Cap-interaction documentation | `limits.py` docstrings + README | — | No guardrail code changes (out of scope); the note is the deliverable |
| Migration preview | `migrate.py` | — | **Unchanged** — Phase 13 documented it quotes list price; multipliers must not leak in |

## Standard Stack

**No new dependencies.** The phase is implementable entirely with what is pinned:

### Core (already installed — verified in `.venv` 2026-08-09)
| Library | Version | Relevance to this phase | Verified |
|---------|---------|------------------------|----------|
| anthropic | 0.120.0 | `Usage.inference_geo` field present (`model_config extra: allow`); `Messages.create` accepts `inference_geo` kwarg | [VERIFIED: local venv inspection] |
| voyageai | 0.5.0 | `EmbeddingsObject.total_tokens: int` accumulated from `response.usage.total_tokens` per call | [VERIFIED: local venv source read] |
| pytest | 9.1.1 | Existing suite: 529 plain / 591 armed (local PG on :54329) | [VERIFIED: pyproject + CONTEXT] |

Python stdlib `contextvars` covers the embedding meter — no library needed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Response-observed geo | Blind `INFERENCE_GEO_MULTIPLIER` env only | Simpler, but the number can lie: a workspace `default_inference_geo: "us"` bills 1.1x while the env sits at 1.0 (or vice versa). The response field is authoritative and free |
| Voyage reported `total_tokens` | Local `count_tokens` tokenizer | Overestimates (40 vs 25, Phase 13 live) and fetches a tokenizer from the HF hub on first call — a network call in the hot path. Disqualified |
| Contextvar meter | Widening the `MemoryStore`/`Embedder` seam to return usage | Explicit, but changes the ABC + Protocol + four backends + every test fake for two integers. Heavy for what it buys |

## Package Legitimacy Audit

No packages are installed this phase. `pyproject.toml` pins are untouched.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## The inference_geo reality (Question 1)

All claims here are from official docs fetched 2026-08-09 plus local SDK inspection.

1. **It is a request parameter.** `inference_geo` on `POST /v1/messages`: `"global"`
   (default — inference may run anywhere) or `"us"` (US-only infrastructure).
   [CITED: platform.claude.com/docs/en/manage-claude/data-residency]
2. **It is priced as a flat multiplier.** For Claude 4.6 and later models,
   `inference_geo: "us"` is billed at **1.1x across all token pricing categories** —
   input, output, cache writes, cache reads. Global routing = standard pricing. Earlier
   models 400 on the parameter and always bill standard.
   [CITED: platform.claude.com/docs/en/about-claude/pricing#data-residency-pricing]
   claude-sonnet-5 is later than 4.6, so the service's model is in scope.
3. **The response reports it.** The `usage` object includes `inference_geo` indicating
   where inference *actually ran*: `{"usage": {"input_tokens": 25, "output_tokens": 150,
   "inference_geo": "us"}}`. [CITED: data-residency docs, "Response" section]
   `anthropic 0.120.0`'s `Usage` model declares the field. [VERIFIED: local venv]
4. **A request can be geo-pinned without the code knowing.** Workspace settings
   `default_inference_geo` and `allowed_inference_geos` (Console / Admin API) apply when
   the parameter is omitted; organisations that ever opted out of global routing were
   auto-migrated to `default_inference_geo: "us"`. [CITED: data-residency docs,
   "Workspace-level restrictions", "Migration from legacy opt-outs"]
5. **The multiplier stacks** with prompt-caching multipliers (and batch, fast mode —
   neither used here). [CITED: pricing docs, "These multipliers stack…"]

**Design consequence — the recommended shape:**

- `CallUsage` gains `inference_geo: str = ""` captured in `from_response` (defensive
  `getattr`, same idiom as every other field — absent on old SDKs/fakes reads as `""`).
- Cost math applies the geo rate **when the response said "us"**, not when an env var
  says so. The *rate* is configurable: `INFERENCE_GEO_MULTIPLIER` (default **1.1**, the
  published rate) — this satisfies SC-1's "configurable" while making applicability
  observed truth. `""` and `"global"` → 1.0. Any *other* observed value (a future `"eu"`)
  → treat as unpriced: set `pricing_unknown`, count tokens, don't guess — DEC-12's
  fail-loud shape, extended to a pricing dimension.
- This service today sends no `inference_geo` and runs `"global"` → multiplier is inert
  at 1.0 unless the workspace pins geo — exactly the honest default. Actually *sending*
  the parameter (an `INFERENCE_GEO` env passed to `messages.create`) is possible with the
  pinned SDK but is a data-residency feature, not cost accounting — recommend deferring
  and noting it (see Open Questions).
- CONTEXT's fallback design ("plain configured factor, operator copies from rate card")
  is strictly worse than this because of finding 4: the workspace default can make the
  bill 1.1x while a blind env factor sits at 1.0. Say so at plan review.

Scope note: the 1.1x is documented against *token* categories. The $10/1k web-search fee
is not a token category, so geo should multiply the token portion only [ASSUMED —
inference from category wording; see Assumptions A1].

## The one choke point (Question 2)

Token→USD happens in exactly two functions, both in `usage.py`:

| Function | Prices | Callers |
|----------|--------|---------|
| `CallUsage.cost_usd(model, on)` | Claude tokens (4 classes) + web-search fee | `record()` (only production caller) + tests |
| `preview_cost_usd(tokens, model, on)` | Voyage flat rate | `migrate.py` preview only — **must stay list price** (Phase 13 doc promise) |

Downstream consumers of the number `cost_usd` produces — all automatic once the choke
point multiplies:

```
CallUsage.cost_usd  ←— apply discount × geo HERE
    └─ record() → state["usage"]["cost_usd"]
         ├─ supervisor_node budget check (per-run cap, graph.py:442)
         ├─ call_model / run_finished log lines
         ├─ RunResponse.build → API payload → demo page $ badge
         ├─ evals/harness.py (reads state["usage"]["cost_usd"])
         └─ RunRecord.from_state → runs.cost_usd column
              ├─ /metrics summary (total_usd, avg_usd_per_run)
              └─ metrics.spend_since → daily cap in reserve_or_429
```

`limits.settle()` merely deletes the reservation row; the "settled real cost" **is** the
metrics row, whose value flows from the same choke point. So the Phase 12 lesson is
satisfied by construction: there is no second arithmetic site to forget, not even in the
reservation path.

Recommended arithmetic (one expression, commented):

- geo multiplies the token portion (`self.inference_geo == "us"` → × geo rate);
- discount multiplies the whole Anthropic call cost including the web-search fee
  [ASSUMED: negotiated discounts apply to the invoice total — A2];
- Voyage cost gets **neither** multiplier: different vendor, different rate card, and
  `inference_geo` is an Anthropic dimension. `/pricing` and README say so.

Env-read conventions (both already established in this codebase):
- read per call, never cached at module scope (`max_run_cost_usd` precedent — tests flip
  with `monkeypatch.setenv`);
- unparseable or ≤ 0 values fall back to the default ("an unparseable budget falls back"
  test idiom). A `COST_DISCOUNT_FACTOR=0` typo must not zero every cost and silently
  disable the budget guardrail — that is the DEC-12 failure mode wearing a new hat.

## Voyage spend into the run record (Question 3)

**Call sites per run** (from graph.py + memory.py, read in full):

| Mode | Embed calls | Where |
|------|-------------|-------|
| research | 1× `embed_query` (recall — skipped when the caller's store is empty: all four backends early-return before embedding) + 1× `embed_documents` (note write, always) | `researcher_node` → `store.query` / `store.add` |
| followup | 0 | responder never touches the store |

Magnitude honesty for the README: a note is a few thousand tokens at $0.06/MTok
(voyage-3.5) ≈ **$0.0002/run vs ~$0.15 total — roughly 0.1%**. The point is that the
accounting surface is complete, not that the number is material; the docs should say that
rather than imply the figure moved.

**The seam today:** `VoyageEmbedder.embed_documents/embed_query` return
`self.client.embed(...).embeddings` — the sibling `total_tokens` on the same
`EmbeddingsObject` is **discarded**. [VERIFIED: memory.py:131–145 + voyageai 0.5.0 source]
`migrate.py`'s own wrapper already reads `response.total_tokens` (migrate.py:467), which is
the in-repo precedent for trusting the field's existence.

**Which side to count:** Voyage's reported `total_tokens`. The local tokenizer
overestimates (Phase 13 live: predicted 40, billed-side reported 25) and needs a HF-hub
network fetch on first call. The reported number is the provider's own figure, free at the
seam, and errs low. The docs phrase it exactly as CONTEXT requires: *"embedding cost is
computed from Voyage's reported token counts, which are telemetry rather than billing
truth — Phase 13 observed a one-word document report 0 tokens while returning a valid
embedding. The figure approximates the invoice; it is not the invoice."*

**Plumbing — three options (Claude's Discretion per CONTEXT):**

- **Option A (recommended): contextvar meter in `usage.py`.**
  `usage.embedding_meter()` context manager yields a small accumulator;
  `VoyageEmbedder` calls `usage.report_embedding(model, total_tokens)` after each
  `client.embed` — a no-op when no meter is active (REPL demo, migrate, tests with fake
  embedders all unaffected). `researcher_node` wraps its `store.query` + `store.add` in
  the meter and folds the result via a new `record_embedding(totals, model, tokens, on)`.
  Thread-safety is structural, not hopeful: the meter is entered and exited inside the
  node function body, and the store/embedder calls are synchronous calls in that same
  frame — whichever thread LangGraph runs the node on, set-and-read happen in one context.
  Concurrent runs are isolated by contextvars. No seam signature changes; four backends
  untouched.
- **Option B: widen the seam** — `MemoryStore.add/query` return usage. Explicit, but
  touches the ABC, the `Embedder` Protocol, four backends, and every test fake.
- **Option C: counter on the shared embedder instance — rejected.** `graph.memory()` is a
  module global shared across concurrent runs; attribution races.

**`record_embedding` semantics (mirrors `record()` exactly):**
- accumulate `embedding_tokens`, `embedding_requests` into the usage dict;
- price via `voyage_price_for(model, on)`; `UnknownModelPricing` → `pricing_unknown =
  True`, cost stays a floor — SC-4's "including for Voyage models" lands here;
- **fold the priced cost into `cost_usd` as well as into `embedding_cost_usd`** — so the
  per-run cap, the daily cap, RunResponse and /metrics all see the invoice approximation
  with no consumer changes, while the separate field keeps the provider visible.

**Run record and storage:**
- The usage dict rides `AgentState` JSON into sessions for free; old persisted states lack
  the new keys — read with `.get(..., 0)` (RunRecord.from_state already does this for
  every field).
- New `RunRecord` fields (`embedding_tokens`, `embedding_requests`, `embedding_cost_usd`)
  require **columns**, because both backends build INSERTs from `asdict(run)`. Neither
  schema block migrates existing tables — `CREATE TABLE IF NOT EXISTS` is a no-op on the
  live Supabase table and on existing SQLite files. Use the two in-repo idioms:
  Postgres `ALTER TABLE runs ADD COLUMN IF NOT EXISTS ... DEFAULT 0` appended to
  `POSTGRES_SCHEMA` (precedent: sessions.py:92, memory.py:498 — runs under the existing
  advisory-locked, retry-on-first-use `ensure_schema`); SQLite `PRAGMA table_info(runs)`
  probe + plain `ALTER TABLE` in the constructor (precedent: sessions.py:232–241,
  including the "SQLite has no ADD COLUMN IF NOT EXISTS" comment).
- `/metrics` additive keys under `cost`: `embedding_tokens`, `embedding_requests`,
  `embedding_usd` (both backends' totals SQL + `_SUM_COLUMNS` + `_summarise` — shape
  shared, contract-tested identical, existing pattern).

## The /pricing extension (Question 4)

**Current payload** (service.py:864–887): `model`, `usd_per_mtok{input, output,
cache_write_5m, cache_read}`, `web_search_usd_per_request`, `max_run_cost_usd`; 501 on
`UnknownModelPricing`. Consumers: `tests/test_service.py::test_pricing_endpoint_reports_todays_rates`
(asserts existing keys; `input in (2.0, 3.0)` — boundary-safe) and the demo page, which
only *links* /pricing (index.html:142) and parses nothing from it — additive extension is
safe for both.

**Additive keys (names are discretion; shapes matter):**

```
{
  ...everything exactly as today...,
  "multipliers": {
    "cost_discount_factor": 1.0,          // env, in effect now
    "inference_geo_multiplier": 1.1,      // env, applied when a response reports "us"
    "inference_geo_note": "applied per response usage.inference_geo; this service sends global routing"
  },
  "windows": {                            // for graph.MODEL
    "current": {"since": null, "until": "2026-08-31", "usd_per_mtok": {...}},
    "next":    {"since": "2026-09-01", "until": null, "usd_per_mtok": {...}}  // null when none
  },
  "embedding": {
    "model": "voyage-3.5",                // memory.EMBEDDING_MODEL
    "usd_per_mtok": 0.06,
    "note": "computed from Voyage-reported token counts; approximation, not the invoice"
  }
}
```

- `windows.next` must be **nullable from day one**: after 2026-09-01 the Sonnet 5 intro
  window is history and `claude-opus-5`/`haiku` have no dated windows at all — a payload
  that assumes a next window exists breaks 25 days after shipping.
- Needs a small date-parameterised helper in `usage.py` (`window_for(model, on)` /
  `next_window(model, on)` returning `PriceWindow`s, not bare `Price`s) so the boundary
  logic is unit-testable with fixed dates while the endpoint keeps using today.
- Unpriced embedding model (e.g. operator sets `VOYAGE_EMBEDDING_MODEL=voyage-4`, absent
  from the table by design): recommend the same 501 fail-loud treatment the LLM already
  gets — DEC-12 consistency. Alternative (200 with an error marker inside `embedding`) is
  defensible for ops-read availability; flag at plan review (Open Question 2).

## The cap interaction (Question 5)

Flow: `reserve_or_429` claims `DEMO_RESERVED_RUN_USD` ($0.20) → run finishes →
`RunRecord.cost_usd` (now multiplied, embedding included) lands in `runs` →
`limits.settle` deletes the reservation → subsequent reserves see `spend_since` = real
multiplied spend. No code change needed anywhere in limits.py for correctness.

**Quantified:** runs land ≈ $0.15 (limits.py's own sizing note). The estimate
under-reserves when `discount × geo × $0.15 > $0.20`, i.e. **combined multiplier >
~1.33**. The only real geo rate is 1.1 and discount ≤ 1.0 by definition, so with today's
published dimensions the estimate stays conservative (US-pinned: ≈ $0.165 < $0.20).
Embedding cost (+$0.0002) is noise against the margin.

- Discount < 1.0: settled costs shrink → the $0.20 estimate becomes *more* conservative →
  cap can only bind sooner during bursts, never overshoot. Safe; **say so, don't resize**
  (per CONTEXT).
- Combined multiplier > 1.33 is unreachable with published rates; a docstring/README note
  ("if a future geo dimension or premium pushes typical run cost above $0.20, raise
  `DEMO_RESERVED_RUN_USD` proportionally") is sufficient. A computed default would be a
  guardrail-default change — **explicitly out of scope** per CONTEXT, which settles the
  question.
- Adjacent note for docs: `AGENT_MAX_RUN_COST_USD` now bounds *multiplied* cost, so a
  discounted deployment gets more work per capped dollar. That is the correct semantics
  (the cap bounds spend, not calls) — state it, don't compensate.

## SC-3 already half-exists (Question 6)

Pinning the two Sonnet windows **today**, all with fixed dates, all surviving past
2026-09-01 (test_usage.py):
- `test_sonnet_5_introductory_pricing_applies_before_september` (2026-08-31)
- `test_sonnet_5_standard_pricing_applies_from_september` (2026-09-01)
- `test_the_two_sonnet_windows_do_not_overlap_or_leave_a_gap` (4 fixed probe dates)
- `test_the_same_call_costs_more_after_the_intro_window_closes` (1.5x ratio, both dates)

What the phase adds:
1. Multiplied-cost tests across the boundary: with `COST_DISCOUNT_FACTOR=0.5`
   (monkeypatch), cost on 2026-08-31 vs 2026-09-01 still ratios 1.5 — proves multipliers
   compose with effective-dating rather than replacing it.
2. `window_for`/`next_window` helper tests at fixed dates on both sides of the boundary,
   including "next is None after 2026-09-01" and "next is None for undated models".
3. The /pricing endpoint test asserts **shape** (keys present, `next` present-or-null),
   never values derived from today's date.

**The rule that keeps everything green on 2026-09-01:** no new test may call
`datetime.now()`/`date.today()` on an assertion path, and no assertion may require a
*particular* window to be current. The one existing today-dependent assertion
(`test_pricing_endpoint_reports_todays_rates`: `input in (2.0, 3.0)`) is already
boundary-proof by construction — copy that idiom if the endpoint test must touch values.

## Common Pitfalls

### Pitfall 1: New RunRecord fields crash INSERTs on live tables
**What goes wrong:** both metrics backends build column lists from `asdict(run)`; a new
dataclass field means a column the deployed Supabase table and existing SQLite files don't
have. First recorded run after deploy → insert error → every run "fails" at the metrics
step.
**How to avoid:** the two in-repo migration idioms (sessions.py:92 for Postgres inside the
schema block; sessions.py:232–241 for SQLite PRAGMA-probe). Postgres DDL rides
`ensure_schema`'s advisory lock + retry-on-first-use, so two machines can both run it.
**Warning sign:** a plan task that edits `RunRecord` without touching both `*_SCHEMA`
blocks and the SQLite constructor.

### Pitfall 2: A second multiplication site
**What goes wrong:** applying the discount in `cost_usd` *and* somewhere downstream
(e.g. /metrics aggregation, or the reservation path) — double-discounted dashboards; or
the inverse Phase-12 failure, a consumer that forgot the multiplier entirely.
**How to avoid:** multiply only inside `CallUsage.cost_usd` (and `record_embedding` for
the separate Voyage path — one function each, both in usage.py). A test that walks a run
end-to-end (fake responses → RunRecord → spend_since) and asserts one discount
application is the behavioural gate.

### Pitfall 3: Multiplier misconfiguration silently disabling the budget guardrail
**What goes wrong:** `COST_DISCOUNT_FACTOR=0` (typo or "disable" intuition) zeroes every
cost; the per-run cap and daily cap never fire; the demo spends unbounded — DEC-12's
exact fail-open scenario via a new door.
**How to avoid:** ≤ 0 or unparseable → fall back to 1.0 (idiom:
`test_an_unparseable_budget_falls_back_to_the_default`). Pin with a test.

### Pitfall 4: Trusting the env for geo when the response disagrees
**What goes wrong:** workspace `default_inference_geo: "us"` (including auto-migrated
legacy opt-out orgs) bills 1.1x while a blind env multiplier reports 1.0 — reported cost
under-approximates by exactly the dimension this phase exists to capture.
**How to avoid:** applicability from `response.usage.inference_geo`; env configures only
the rate. Unknown geo values → `pricing_unknown`, never a silent 1.0.

### Pitfall 5: Multiplying the migration preview
**What goes wrong:** `preview_cost_usd` picks up the discount; the Phase 13 preview's
printed "quotes list price" promise becomes false; a spending decision is made on a
discounted number that Voyage (a different vendor) never offered.
**How to avoid:** multipliers live in `CallUsage.cost_usd`/`record_embedding`, never in
`voyage_price_for`/`preview_cost_usd`. A test pins the preview at list price under a
non-neutral env.

### Pitfall 6: today()-dependent tests dying on 2026-09-01
**What goes wrong:** a test asserting `/pricing` shows the intro rate, or `next` non-null,
goes red 23 days after the phase merges.
**How to avoid:** fixed run dates everywhere; endpoint tests assert shape (see SC-3).

### Pitfall 7: Old persisted states and fake responses
**What goes wrong:** followup runs load pre-Phase-14 state blobs whose usage dict lacks
the new keys; test fakes' usage objects lack `inference_geo` → AttributeError or KeyError
in arithmetic.
**How to avoid:** `.get(..., 0)`/`getattr(..., "") ` defaults — both idioms are already
the local convention (`RunRecord.from_state`, `CallUsage.from_response`).

### Pitfall 8: Meter attribution races
**What goes wrong:** a per-instance counter on the shared `VoyageEmbedder` mixes two
concurrent runs' tokens.
**How to avoid:** contextvar meter entered inside the node body (Option A) — set and read
in one frame, isolated per context.

## Code Examples

Verified idioms from this codebase and the installed SDKs (not proposals to copy blind —
the planner shapes final code):

### Reading the geo field defensively (extends the existing from_response idiom)
```python
# CallUsage.from_response already does this for every field:
#   field(usage, "input_tokens") -> int(getattr(usage, name, None) or 0)
# The geo analogue, absent-safe for fakes and old SDKs:
inference_geo = str(getattr(usage, "inference_geo", None) or "")
# anthropic 0.120.0 Usage declares the field (verified); fakes read as "".
```

### What the Voyage seam discards today (memory.py:131–137)
```python
def embed_documents(self, texts):
    return self.client.embed(
        list(texts), model=self.model, input_type="document",
        output_dimension=self.output_dimension,
    ).embeddings          # <- EmbeddingsObject.total_tokens dropped here
```
```python
# voyageai 0.5.0, voyageai/object/embeddings.py (verified):
class EmbeddingsObject:
    def __init__(self, response=None):
        self.embeddings = []
        self.total_tokens: int = 0     # accumulated from response.usage.total_tokens
```

### The SQLite column-add idiom to reuse for `runs` (sessions.py:232–241)
```python
# SQLite has no `ADD COLUMN IF NOT EXISTS`, so the column list is probed
columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(sessions)")}
if "owner" not in columns:
    self._conn.execute("ALTER TABLE sessions ADD COLUMN owner TEXT NOT NULL DEFAULT ''")
```

### The Postgres idiom (sessions.py:92, runs under ensure_schema's advisory lock)
```sql
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT '';
```

### Env-factor parsing convention (usage.py:259–264 — copy for both multipliers, plus a ≤0 guard)
```python
def max_run_cost_usd() -> float:
    try:
        return float(os.environ.get("AGENT_MAX_RUN_COST_USD", "1.00"))
    except ValueError:
        return 1.00
```

## State of the Art

| Claim in code today | Reality (verified 2026-08-09) | Impact |
|---------------------|------------------------------|--------|
| PRICES Sonnet 5: $2/$10 → 2026-08-31; $3/$15 from 09-01; cache 1.25x/0.1x | Matches docs exactly, including cache rates ($2.50/$0.20 intro, $3.75/$0.30 std) | No table changes needed [CITED: pricing docs] |
| Opus 5 $5/$25, Haiku 4.5 $1/$5 | Matches docs | — |
| Web search $10/1k, fetch free | Matches docs ("If an error occurs… not billed" too) | — |
| Cost is list price only | `inference_geo: "us"` = 1.1x on token categories (Claude 4.6+); response reports the geo; workspace defaults exist | This phase's core finding |
| All `cache_creation_input_tokens` priced at the 5m rate | Docs also list a 1h cache write at 2x base; SDK `Usage` has a `cache_creation` breakdown object | Latent, pre-existing, out of scope — the service never requests 1h caches. Worth one line in docs, not code |
| Voyage rates verified 2026-08-06 (Phase 13) | 3 days old, no dated windows published | No re-verification burden |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The 1.1x geo multiplier does not apply to the $10/1k web-search fee (docs scope it to "token pricing categories") | inference_geo / choke point | Cost under-approximates by 10% of the search fee (~$0.002/run) when US-pinned — cosmetic |
| A2 | A negotiated discount applies to the whole Anthropic invoice including web-search fees | choke point | Discounted deployments over- or under-report the fee portion by the discount delta; docs already call the figure an approximation |
| A3 | Voyage bills what `response.total_tokens` reports | Voyage spend | Phase 13 observed a 0-token anomaly; this is precisely why the docs must say "telemetry, not billing truth" — the caveat is the mitigation |

All other load-bearing claims are [VERIFIED] (local SDK/source inspection) or [CITED]
(official docs fetched this session).

## Open Questions

1. **Does the response-observed geo design satisfy SC-1's "configurable multiplier"?**
   - What we know: the API reports geo per response; the rate is published (1.1x); CONTEXT
     drafted a blind env factor before this was established.
   - Recommendation: hybrid — `INFERENCE_GEO_MULTIPLIER` env configures the *rate*
     (default 1.1), the response field decides *applicability*. Confirm at plan review;
     it is a strict improvement on the drafted shape, for the workspace-default reason.
2. **`/pricing` when the embedding model is unpriced:** 501 (consistent with the LLM path,
   DEC-12-loud) vs 200 with an error marker inside `embedding` (ops read stays up).
   Recommendation: 501; the misconfiguration should be as loud as the LLM equivalent.
3. **Send `inference_geo` on requests?** The pinned SDK supports the kwarg. It is a data
   residency feature, not accounting; recommend deferring with a note. The accounting
   design works identically whether geo arrives via request param or workspace default.
4. **`web_fetch_requests`/`web_search` in the discount base** — folded into A2; a plan
   comment stating the choice is sufficient.

## Environment Availability

Skipped — no new external dependencies. The phase changes code, tests, and docs against
already-pinned, already-installed SDKs (`anthropic 0.120.0`, `voyageai 0.5.0` verified
present in `.venv`); the armed test suite's local Postgres on :54329 is running per
CONTEXT's state-of-the-world.

## Validation Architecture

(`.planning/config.json` absent → nyquist validation treated as enabled.)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 |
| Config file | pyproject.toml (dev extra) |
| Quick run command | `.venv/bin/pytest tests/test_usage.py -q` |
| Full suite command | `.venv/bin/pytest -q` (plain 529; armed 591 with local PG on :54329) |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| SC-1 | discount × geo applied at cost computation; neutral defaults change nothing | unit | `pytest tests/test_usage.py -q` | ✅ (new tests join existing file) |
| SC-1 | geo applies only when response reports "us"; unknown geo → pricing_unknown | unit | `pytest tests/test_usage.py -q` | ✅ |
| SC-2 | /pricing carries multipliers, current+next windows, embedding row; existing keys unchanged | integration (TestClient) | `pytest tests/test_service.py -q -k pricing` | ✅ |
| SC-3 | both Sonnet windows pinned; multiplied cost ratios 1.5 across boundary; helpers at fixed dates | unit | `pytest tests/test_usage.py -q` | ✅ |
| SC-4 | unpriced Voyage model → pricing_unknown, tokens counted, cost floor | unit | `pytest tests/test_usage.py -q` | ✅ |
| SC-5 | embedding tokens/cost in run usage, run record, /metrics aggregates; both backends identical | unit + contract (+ pg-gated arm) | `pytest tests/test_metrics.py tests/test_service.py -q` | ✅ |
| SC-5 | column migration: pre-phase SQLite file / table gains columns on open; insert succeeds | unit | `pytest tests/test_metrics.py -q` | ✅ (new test, existing file) |
| — | meter: VoyageEmbedder reports; researcher_node folds; concurrent isolation | unit (fake Voyage response / fake embedder) | `pytest tests/test_memory_stores.py tests/test_graph_smoke.py -q` | ✅ |
| — | preview_cost_usd stays list price under non-neutral env | unit | `pytest tests/test_migrate.py -q` | ✅ |
| — | cap path: settled (metrics) cost is multiplied cost end-to-end | integration | `pytest tests/test_service.py -q` | ✅ |

Everything above is unit/TestClient-testable offline with `ANTHROPIC_API_KEY=""` — this
phase has **no test that needs the network**. The one live-only fact (a real Voyage
response carries `total_tokens` through the wrapper) is already evidenced by Phase 13's
live run exercising `migrate.py`'s identical read; no live gate is warranted, and saying
so honestly beats inventing one.

### Sampling Rate
- **Per task commit:** `pytest tests/test_usage.py -q` (or the touched file)
- **Per wave merge:** `pytest -q`
- **Phase gate:** full suite green (plain; armed where PG available) before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements; every new test joins
an existing file with established idioms (FakeUsage/FakeResponse in test_usage.py,
make_client in test_service.py, in-memory stores in test_metrics.py).

### Gate discipline (the FIFTEEN-vacuous-gates directive)
Every gate needs a measured baseline (529/63 plain, 591/1 armed — from CONTEXT) and a
mutation observed red. Behavioural mutations that go red **by the intended route**:
- delete the `× discount` term in `cost_usd` → the SC-1 composition test reds (not an
  unrelated import error);
- hard-code geo applicability to `True` → the "global responses are unmultiplied" test reds;
- drop the `record_embedding` fold into `cost_usd` → the end-to-end cap/metrics test reds;
- remove the SQLite PRAGMA probe → the old-schema-file migration test reds.
Prefer these to greps; a grep for `COST_DISCOUNT_FACTOR` proves the string exists, not
that the arithmetic runs.

## Security Domain

Small surface, but non-zero:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Env factors parsed with the established fallback idiom; ≤ 0 → 1.0 (a misconfigured multiplier must fail toward *more* cost reported, never less — the guardrails read this number) |
| V4 Access Control | yes (unchanged) | `/pricing` stays an ungated ops read by design (limits.py doctrine); the additive fields expose only published rates and operator-chosen factors — no secrets, no per-caller data |
| V6 Cryptography | no | — |
| V2/V3 Auth/Session | no | Untouched this phase |

| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Cost-control fail-open via config (discount=0) | Tampering/DoS-adjacent | Clamp + test (Pitfall 3) |
| Trusting client-influenceable data for billing | Repudiation | `usage.inference_geo` comes from Anthropic's response, not from any caller input; callers cannot influence it |

## Sources

### Primary (HIGH confidence)
- https://platform.claude.com/docs/en/about-claude/pricing — fetched 2026-08-09: model
  rates, Sonnet 5 windows, cache multipliers, web search/fetch fees, data-residency
  pricing (1.1x, token categories, Claude 4.6+), multiplier stacking, discounts applied
  billing-side
- https://platform.claude.com/docs/en/manage-claude/data-residency — fetched 2026-08-09:
  `inference_geo` request parameter, response `usage.inference_geo` field, workspace
  `default_inference_geo`/`allowed_inference_geos`, legacy opt-out auto-migration, 400 on
  older models
- Local `.venv` inspection — anthropic 0.120.0 `Usage.model_fields` (has `inference_geo`;
  `extra: allow`), `Messages.create` signature (accepts `inference_geo`); voyageai 0.5.0
  `EmbeddingsObject` source (`.total_tokens`)
- The codebase itself, read in full: usage.py, graph.py, limits.py, service.py,
  metrics.py, memory.py, migrate.py (relevant parts), sessions.py (migration idioms),
  tests/test_usage.py, test_service.py (pricing/cap tests), test_limits.py (settle idioms)

### Secondary (MEDIUM confidence)
- WebSearch corroboration of the 1.1x semantics (finout.io pricing guide; claude-code
  issue #60641 discussing the `/cost` estimate missing the inference_geo multiplier) —
  consistent with the official docs above

### Tertiary
- None load-bearing.

## Metadata

**Confidence breakdown:**
- inference_geo semantics: HIGH — official docs + pinned-SDK field verification
- Choke point / call graph: HIGH — every consumer read in source this session
- Voyage seam & plumbing: HIGH for facts (SDK source read); recommendation (contextvar
  meter) is design judgment with the alternatives stated
- Cap interaction: HIGH — arithmetic over in-repo constants
- Pitfalls: HIGH — each anchored to a specific line of existing code

**Research date:** 2026-08-09
**Valid until:** ~2026-09-08 for pricing facts (but note: the Sonnet 5 boundary itself is
2026-08-31 — the phase should merge before it, and its tests must survive after it)
