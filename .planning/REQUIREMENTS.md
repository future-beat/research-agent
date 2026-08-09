# Requirements: research-agent

**Defined:** 2026-08-04 (ingested from `README.md` → `## Limitations`)
**Core Value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.

## Framing — read before planning any of these

These are **not bug reports**. Every one closes a gap that was consciously left open and
argued for. Six of the nine **reverse a stated design position**. A reversal is legitimate,
but it must be an explicit decision that supersedes a numbered record — not a silent
consequence of "closing the limitations list."

Acceptance criteria below are **synthesis proposals, not user-ratified**. Treat them as
drafts to be firmed up during each phase's discuss step. Each reversal requirement must
also decide its **replacement guarantee** during that discussion.

Source intel: `.planning/intel/requirements.md`, `.planning/intel/constraints.md`.
Conflict report (user-approved, 0 blockers): `.planning/INGEST-CONFLICTS.md`.

## v1.1 Requirements

Requirements for the current milestone. Each maps to exactly one roadmap phase.

### Grounding and evaluation

- [ ] **REQ-followup-live-search**: A follow-up whose question is unsupported by prior notes
  triggers a new research pass instead of terminating with "the research didn't cover that."
  *Reverses DEC-04 — the strongest reversal in the set.* DESIGN.md calls the guarantee this
  removes "the single failure mode this whole pipeline exists to prevent." The phase must
  define what `no_prior_research` means afterwards and how grounding survives.
  Constrained by: `service.py` holds no routing logic — the change belongs in the supervisor.

- [ ] **REQ-independent-critic-model**: The critic is separately configurable from the
  writer/researcher model, so it is a genuinely independent evaluator rather than
  "independent enough."
  *Reverses the premise DEC-22 rests on.* README's sentence "The eval judge runs on a
  stronger model precisely because of this" becomes false the moment this lands. The eval
  judge decision must be **re-derived, not inherited**.

- [ ] **REQ-offline-eval-quality**: Answer quality becomes measurable without billing every
  push, and the live case count grows past 12 to a size defensible as a benchmark.
  *In tension with DEC-20.* Grading quality is fine; re-introducing the implication that a
  green suite means "the model is good," or breaking the free/deterministic/every-push
  property, is the reversal to watch. `ANTHROPIC_API_KEY=""` must stay a CI invariant.

### Cost

- [x] **REQ-real-cost-accounting**: A configurable discount factor and `inference_geo`
  multiplier feed cost computation; `/pricing` exposes which multipliers are in effect.
  *Not a reversal — a pure extension of DEC-12.* Effective-dating must survive, including
  across the 2026-08-31 Sonnet 5 introductory-price boundary. `pricing_unknown` semantics
  unchanged: fails loud, never zero.

### Identity and lifecycle

- [x] **REQ-demo-authentication**: Callers to the public demo authenticate to an identity,
  not a shared token; rate limit and rolling spend cap key on identity rather than visitor
  IP, so `TRUST_FORWARDED_FOR` is no longer load-bearing for fairness.
  *Reverses a deliberate scope choice* — "rate-limited, not authenticated" was a call that
  bounding spend was enough for a public portfolio demo. The demo must stay usable without
  friction that defeats its purpose.

- [x] **REQ-store-lifecycle-and-ownership**: Notes carry at least one bound (eviction, dedup,
  or summarisation) and note deletion is consistent across JSON/memory/Chroma/pgvector;
  sessions carry an owner identity and an expiry, `/sessions` lists only the caller's
  sessions, and `/sessions/{id}` 403s or 404s for others.
  *Not a reversal* — the README calls unbounded growth a known gap, not a chosen property.
  Depends on REQ-demo-authentication for an identity to attach ownership to.

### Scaling and data

- [x] **REQ-multi-machine-state**: `DATABASE_URL` is set in production, `[[mounts]]` is gone
  from `fly.toml`, machine count is greater than 1, and sessions resolve identically from
  any machine.
  *Not a reversal* — DEC-15 and OPERATIONS already document this path; this executes it.

- [x] **REQ-connection-pool**: A pool with configurable min/max size replaces the single
  lock-guarded Postgres connection, preserving reconnect-on-failure and lazy schema
  application.
  *Reverses a sizing judgement, mildly.* The single connection is described as "right when
  a run occupies a worker for tens of seconds" — pooling is correct only alongside raised
  concurrency.

- [x] **REQ-embedding-model-migration**: A command re-embeds an existing corpus into a new
  table at a new dimension, with cost reported before the run starts and an explicit,
  reversible cutover; the loud dimension check must not become a silent coercion.
  *In tension with DEC-10*, which deliberately copies embeddings so recall behaviour does
  not change at the same moment infrastructure does. Any re-embedding path must isolate the
  recall change from the infrastructure change.

## Cross-cutting requirement

- [x] **REQ-adr-promotion**: The five load-bearing architectural decisions exist as numbered
  ADRs under `docs/adr/` with explicit `Status` fields, so each subsequent reversal
  supersedes a record rather than silently contradicting prose.
  Derived from INGEST-CONFLICTS WARNING 3, user-approved 2026-08-04. Not sourced from the
  README Limitations list.

- [x] **REQ-live-endpoint-exposure**: The session read and delete endpoints are not reachable
  without credentials on the deployed service, `DEMO_TOKEN` actually protects them, `DELETE`
  is rate-limited, and the SSE error handler stops returning unredacted exception text.
  Discovered during codebase mapping 2026-08-04, not present in the README Limitations list.
  Confirmed live, not theoretical: an unauthenticated `GET /sessions` returned two real
  sessions with full task text, and two `DELETE` calls returned 204 from the open internet.
  Scoped as a hotfix — per-caller ownership and expiry remain REQ-store-lifecycle-and-ownership.

## Out of Scope

| Feature | Reason |
|---------|--------|
| LangGraph checkpointer for sessions | Different feature, different failure model; couples schema to LangGraph internals |
| LLM-based routing | Routing must stay deterministic and testable with no API keys |
| Combined draft-and-self-assess node | "Reliably produces 'looks good to me'" |
| Separate backend flags per store | The real failure is setting one and forgetting another |
| A heavyweight auth wall on the demo | Defeats the demo's purpose — one click from a résumé link |
| A CI eval step that needs a live API key | Breaks on forks, on key rotation, during someone else's outage, and bills every push |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-adr-promotion | Phase 10 | Complete (PR #4 merged, both checks green, 2026-08-05) |
| REQ-live-endpoint-exposure | Phase 10.5 | Complete (Fly release v4, 2026-08-04) |
| REQ-multi-machine-state | Phase 11 | Complete (Fly v7, two machines, 2026-08-05) |
| REQ-connection-pool | Phase 11 | Complete (psycopg-pool, one shared pool per machine) |
| REQ-demo-authentication | Phase 12 | Complete — live on release v9, 2026-08-05 (12-06 T-06-4: cookieless caller reaches a working page + completed stream with a signed `HttpOnly; Secure; SameSite=Lax` identity minted on the response; verified across machines `846975f2604548`/`d8d0320f751618` and a fleet restart) |
| REQ-store-lifecycle-and-ownership | Phase 12 | Complete — code in 12-04 (sessions) / 12-05 (notes), ownership demonstrated live on release v9 (second identity gets `{"sessions":[]}` and a 404 indistinguishable from missing, on read and write). 7-day expiry/TTL proven against the DB clock in the Postgres-gated suite, not live |
| REQ-embedding-model-migration | Phase 13 | Complete |
| REQ-real-cost-accounting | Phase 14 | Complete |
| REQ-offline-eval-quality | Phase 15 | Pending |
| REQ-independent-critic-model | Phase 16 | Pending |
| REQ-followup-live-search | Phase 17 | Pending |

**Coverage:**
- v1.1 requirements from intel: 9 total
- Mapped to phases: 9
- Unmapped: 0 ✓
- Plus REQ-adr-promotion (cross-cutting, added during roadmapping) → Phase 10
- Plus REQ-live-endpoint-exposure (found during codebase mapping, not in the Limitations list) → Phase 10.5

---
*Requirements defined: 2026-08-04*
*Last updated: 2026-08-04 after roadmap creation*
