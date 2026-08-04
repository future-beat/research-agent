# Roadmap: research-agent

## Overview

Phases 1–9 built and shipped a supervisor-routed research pipeline as a real service:
deterministic routing, vector memory, an HTTP surface, cost accounting with a spend cap,
an eval harness, a Docker/CI/Fly deploy, Postgres+pgvector backends, and a public demo
with guardrails. It is live at `research-agent.fly.dev`.

Milestone v1.1 takes on all nine items from the README's `## Limitations` list. Six of
them reverse a design position the project argues *for*, so the milestone opens by
promoting the five load-bearing decisions into numbered ADRs — every later reversal names
the ADR it supersedes. From there the work runs outward-in: infrastructure that nothing
else depends on first (multi-machine Postgres, pooling), then identity and lifecycle,
then data migration and cost, then the measurement that makes quality changes visible,
and only then the two reversals that change what the pipeline *says* — an independent
critic, and follow-ups that can reach for new information.

**Definition of done for this project:** demonstrable to an employer. Live URL that works,
green CI, a README a stranger can skim. Surface tidiness is part of the deliverable.

## Milestones

- ✅ **v1.0 Production pipeline** — Phases 1–9 (shipped, plus post-Phase-9 housekeeping)
- 🚧 **v1.1 Closing the limitations list** — Phases 10–17 (next)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Production pipeline (Phases 1–9) — SHIPPED</summary>

- [x] **Phase 1: Core loop** - Supervisor pattern with deterministic Python routing
- [x] **Phase 2: Memory** - Voyage embeddings, cosine recall with a relevance floor, persisted
- [x] **Phase 3: Conversation & resilience** - Follow-ups, pluggable stores, per-node retry, tests
- [x] **Phase 4: Service** - FastAPI, blocking and SSE, sessions surviving restart
- [x] **Phase 5: Cost & observability** - Date-aware pricing, spend cap as routing rule, `/metrics`
- [x] **Phase 6: Evals** - Twelve-case golden set, deterministic graders plus an LLM judge
- [x] **Phase 7: Ship it** - Two-stage Dockerfile, non-root, CI gates, Fly deploy
- [x] **Phase 8: Stateless** - Postgres and pgvector behind the existing interfaces
- [x] **Phase 9: Demo & guardrails** - Streaming demo page, rolling spend cap, rate limit, token
- [x] **Post-Phase-9 housekeeping** - `src/` package reorganisation, one consolidated `pyproject.toml`

</details>

### 🚧 v1.1 Closing the limitations list (Phases 10–17)

- [ ] **Phase 10: ADRs and doc correctness** - Promote the load-bearing five to numbered ADRs; fix verified-false docs; redeploy so live matches `main`
- [x] **Phase 10.5: Close the live endpoint exposure (hotfix)** - Guard the unauthenticated session read/delete paths and stop leaking exception text; ship immediately
- [ ] **Phase 11: Multi-machine state and pooled Postgres** - Take the `DATABASE_URL` path, run more than one machine, replace the single connection with a pool
- [ ] **Phase 12: Caller identity, session ownership, bounded stores** - The demo identifies callers; sessions have owners and expiry; notes stop growing forever
- [ ] **Phase 13: Embedding model migration** - A real, reversible path when the embedding model or dimension changes
- [ ] **Phase 14: Real cost accounting** - Discounts and `inference_geo` so reported cost approximates the invoice
- [ ] **Phase 15: Answer-quality evals** - Quality becomes measurable without billing every push; the live set outgrows a smoke test
- [ ] **Phase 16: Independent critic model** - The critic stops sharing the writer's model, and the eval-judge rationale is re-derived
- [ ] **Phase 17: Follow-ups that can reach for new information** - An unsupported follow-up triggers research instead of refusing

## Phase Details

<details>
<summary>✅ v1.0 phase details (Phases 1–9)</summary>

### Phase 1: Core loop
**Goal**: A question routes through a supervisor to workers and returns a grounded report
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 2: Memory
**Goal**: Notes persist and are recalled by similarity, not by growing the prompt
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 3: Conversation & resilience
**Goal**: Follow-ups work over prior notes; stores are pluggable; transient failures retry
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 4: Service
**Goal**: The pipeline is reachable over HTTP, blocking or streaming, with durable sessions
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 5: Cost & observability
**Goal**: Every run reports what it cost, and a spend cap stops runaway runs
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 6: Evals
**Goal**: The pipeline's behaviour is checkable against a golden set
**Status**: Complete — found a real bug (the unreachable revision cap) on its first run
**Plans**: Complete (pre-GSD)

### Phase 7: Ship it
**Goal**: The service builds to an image, passes CI gates, and deploys
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 8: Stateless
**Goal**: Sessions, metrics, and notes can live in Postgres/pgvector behind the same interfaces
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 9: Demo & guardrails
**Goal**: A stranger can use the live demo without it being abusable
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 9.1: Package reorganisation (housekeeping)
**Goal**: `src/` layout and one `pyproject.toml`, so a passing test run can't rely on a module that never reaches the image
**Status**: Complete
**Plans**: Complete (pre-GSD)

</details>

### Phase 10: ADRs and doc correctness
**Goal**: The architectural record is numbered and status-bearing, and the docs stop asserting things that are verifiably false
**Depends on**: Nothing (first phase of v1.1)
**Requirements**: REQ-adr-promotion
**Success Criteria** (what must be TRUE):
  1. `docs/adr/` contains five numbered ADRs, each with an explicit `Status` field, covering: deterministic Python routing (DEC-01), the separate critic node with notes as sole source of truth (DEC-02), no-new-search follow-ups and `no_prior_research` (DEC-04), the Opus 5 judge against a Sonnet 5 pipeline (DEC-22), and sessions in SQLite rather than LangGraph's checkpointer (DEC-14).
  2. A reader can trace each ADR back to the passage in `docs/DESIGN.md` it was promoted from, and the DESIGN prose points forward to the ADR.
  3. `docs/OPERATIONS.md` no longer claims deploys run through Fly's GitHub integration — it states that deploys are manual via `fly deploy -a research-agent`, which is what `fly releases -a research-agent` actually shows.
  4. `docs/DESIGN.md` names four `MemoryStore` backends (json, memory, chroma, pgvector), not three.
  5. The deployed release matches `main` — the README restructure, the `src/` reorganisation, and its bugfix are live, and `/`, `/health`, `/demo`, `/metrics` still return 200.
  6. No planning or reference doc quotes a Sonnet 5 rate as if permanent; the introductory $2/$10 window through 2026-08-31 and the $3/$15 rate from 2026-09-01 are both stated, with `/pricing` named as the live source.
**Plans**: 5 plans

Plans:
- [x] 10-01-PLAN.md — ADR index, Nygard contract and supersession convention, plus ADR-0001 and ADR-0002
- [x] 10-02-PLAN.md — ADR-0003, ADR-0004 and ADR-0005, completing the promoted five, plus ADR-0006 (the Phase 10.5 auth decisions)
- [x] 10-03-PLAN.md — Kill the false GitHub-integration deploy claim; name `/pricing` as the live rate source in README
- [ ] 10-04-PLAN.md — `docs/DESIGN.md`: four backends, ISO-dated price windows, forward-links to all five ADRs
- [ ] 10-05-PLAN.md — Run every gate, prove no `src/` change and an unchanged suite, re-verify SC-5 live (checkpoint)

**Notes for discuss-phase:**
- The ADR set is the gate for everything after it. Phases 13, 15, 16, and 17 each supersede or re-derive one of these records; if the record does not exist, the reversal is silent.
- Reversals of decisions *not* in the five (DEC-10, DEC-20) should create a new ADR in the phase that reverses them rather than retrofitting one here.
- Verified 2026-08-04: nothing in the repo or docs cites `/healthz` (which 404s) — `/health` is cited correctly everywhere. No fix needed; re-verify rather than assume.

### Phase 10.5: Close the live endpoint exposure (hotfix)
**Goal**: The public service stops handing session contents to anyone and stops accepting anonymous deletes
**Status**: ✅ Complete — shipped as Fly release **v4** on 2026-08-04. All four endpoints return 401 anonymously from the open internet; the demo still serves anonymous research runs.
**Depends on**: Nothing — ships ahead of Phase 11 regardless of Phase 10's state
**Requirements**: REQ-live-endpoint-exposure
**Success Criteria** (what must be TRUE):
  1. `GET /sessions`, `GET /sessions/{id}`, `GET /sessions/{id}/trace` and `DELETE /sessions/{id}` are no longer reachable without credentials on the deployed service. Today all four lack `Depends(guard)` (`src/research_agent/service.py:514`, `:519`, `:533`, `:539`).
  2. Setting `DEMO_TOKEN` actually protects them. It does not today: `check_token` runs only inside `guard`, and these four paths never reach it — so the existing token control is inert on exactly the endpoints that leak.
  3. `DELETE /sessions/{id}` is rate-limited, not merely authenticated. It is currently both unauthenticated and unmetered, which makes wiping the demo a two-line script.
  4. The SSE error handler redacts exception text (`src/research_agent/service.py:263`). The redaction helper already exists and is tested — the `/health` path uses it correctly; this call site just is not wired to it.
  5. Tests cover each newly-guarded path for both the 401/403 case and the authorised case, and fail if a future endpoint is added to the sessions router without a guard.
  6. Verified against the deployed service, not just locally: an unauthenticated `GET /sessions` from the open internet returns 401/403.

**Outcome (2026-08-04):** all six met, with SC-2 satisfied by a **superseding decision** rather than
literally. Research found that setting `DEMO_TOKEN` in production would 401 every anonymous visitor
on `POST /research/stream` and kill the public demo — `guard` already checks it and the demo page
sends no token header. SC-2's intent was "the token control stops being inert on the endpoints that
leak"; that is met by a separate `SESSIONS_TOKEN` (with `DEMO_TOKEN` accepted as a fallback value),
which fails closed at 403 when unset. `DEMO_TOKEN` must remain **unset** in production. Locked in
`10.5-CONTEXT.md` § Protection mechanism.

SC-5's structural test was nearly worthless as first conceived: fastapi 0.141.1 leaves an
`_IncludedRouter` in `app.routes`, so a flat walker sees only the two `@app.post` ask routes — both
legitimately guarded — computes an empty unguarded list, and reports a clean sessions tree while the
four leaking routes stay invisible. The shipped test walks recursively and asserts a route count
first. Two pre-existing tests had the same flat-scan bug and were fixed.

**Plans**: 5 plans

Plans:
- [x] 10.5-01-PLAN.md — Add the fail-closed `SESSIONS_TOKEN` credential to `limits.py`, with unit coverage
- [x] 10.5-02-PLAN.md — Regroup the four session routes behind it, rate-limit the DELETE, redact the SSE error, repair the suite
- [x] 10.5-03-PLAN.md — Behavioural coverage: refusal, service, fail-closed, fallback, unmetered reads, and a demo that survives
- [x] 10.5-04-PLAN.md — Recursive non-vacuous route-guard invariant, plus the DELETE's limiter pinned structurally
- [ ] 10.5-05-PLAN.md — Truth up the docs, then the single cutover and live verification (checkpoint)

**Notes for discuss-phase:**
- Scope discipline: this is a hotfix, not Phase 12. It closes the hole with the guard mechanism that already exists. Per-caller ownership, expiry, and note lifecycle stay in Phase 12 — do not start modelling identity here.
- Decide what `GET /sessions` should do long-term. Guarding it is the fast fix, but a public demo arguably should not have a global listing endpoint at all, even an authenticated one. That question belongs to Phase 12; this phase only has to stop it being open.
- Verified live on 2026-08-04: `GET /sessions` returned two real sessions with full task text to an unauthenticated caller, and two `DELETE` calls returned 204 from the open internet. Both sessions were backed up and removed with the owner's consent. The exposure is confirmed, not theoretical.
- The deployed tree is 3 commits behind `main`, but the endpoints are unguarded on `main` too — redeploying does not fix this, and fixing this requires a deploy. Sequence with Phase 10's redeploy criterion so there is one cutover, not two.

### Phase 11: Multi-machine state and pooled Postgres
**Goal**: The service runs on more than one machine with shared state and pooled database access
**Depends on**: Phase 10
**Requirements**: REQ-multi-machine-state, REQ-connection-pool
**Success Criteria** (what must be TRUE):
  1. `DATABASE_URL` is set in production, `research_agent.migrate` has been run dry-run then real, and `/health` reports Postgres-backed stores.
  2. `[[mounts]]` is gone from `fly.toml` and more than one machine is running.
  3. A session created against one machine resolves identically from another — the "404 on a session that demonstrably exists" failure is gone.
  4. Postgres access goes through a pool with configurable min/max size; reconnect-on-failure still works and no DDL runs at construction time.
  5. `tests/test_deploy_config.py` guards the new topology, and the byte-identical cross-backend metrics assertion still passes.
  6. `PG_CONNECT_TIMEOUT` semantics are documented for the pooled case.
**Plans**: TBD

**Notes for discuss-phase:**
- REQ-connection-pool is a mild reversal of a sizing judgement: the single lock-guarded connection is "right when a run occupies a worker for tens of seconds." Pooling is only correct alongside raised concurrency — decide the concurrency change and the pool together, or the pool is unjustified.
- REQ-multi-machine-state is not a reversal; DEC-15 and OPERATIONS already lay this path out. This executes it.
- Deploys are manual (established in Phase 10). Plan the production cutover as a deliberate sequence, not a push.

### Phase 12: Caller identity, session ownership, bounded stores
**Goal**: The demo knows who is calling, sessions belong to someone and expire, and notes stop growing forever
**Depends on**: Phase 11
**Requirements**: REQ-demo-authentication, REQ-store-lifecycle-and-ownership
**Success Criteria** (what must be TRUE):
  1. A caller authenticates to an identity rather than presenting a shared `DEMO_TOKEN`.
  2. Rate limit and rolling spend cap key on that identity, so `TRUST_FORWARDED_FOR` is no longer load-bearing for fairness.
  3. `/sessions` lists only the caller's sessions and `/sessions/{id}` returns 403 or 404 for anyone else.
  4. Sessions carry an expiry and expired sessions stop resolving.
  5. Notes have at least one enforced bound — eviction, dedup, or summarisation — and note deletion behaves the same across json, memory, chroma, and pgvector, proven by the shared behavioural suite.
  6. A stranger following a link from a résumé can still reach a working demo without abandoning at an auth wall.
**Plans**: TBD
**UI hint**: yes

**Notes for discuss-phase:**
- **Reversal.** "Rate-limited, not authenticated" was a deliberate scope call that bounding *spend* was sufficient for a public portfolio demo. The replacement guarantee to decide: what identity scheme buys enough fairness to be worth the friction it adds to a demo whose whole value is one-click access. Criterion 6 is the constraint that can kill an otherwise-correct design.
- The two requirements are coupled: ownership needs an identity to attach to. They may split into separate plans (identity first, then ownership+expiry, then note bounds) but they should not split across phases.
- The demo page changes visibly here — this is the phase where `/gsd:ui-phase` is worth running.

### Phase 13: Embedding model migration
**Goal**: Changing the embedding model or dimension has a real path that does not require hand-building a table
**Depends on**: Phase 11
**Requirements**: REQ-embedding-model-migration
**Success Criteria** (what must be TRUE):
  1. A command re-embeds an existing corpus into a new table at the new dimension.
  2. The cost of re-embedding is reported before the run starts.
  3. Cutover is explicit and reversible — the old table survives until the new one is confirmed.
  4. The loud dimension check still fires; it has not become a silent coercion.
  5. A recall change caused by a new embedding model is distinguishable from an infrastructure change — the two variables are isolated, not confounded.
**Plans**: TBD

**Notes for discuss-phase:**
- **Reversal (in tension with DEC-10).** DEC-10 copies embeddings during migration *specifically* so recall behaviour does not change at the same moment infrastructure does — "two suspects and no way to separate them." A re-embedding path re-opens exactly that ambiguity unless criterion 5 is designed for, not hoped for. DEC-10 is not among the promoted five; this phase should record its own ADR stating what supersedes it.
- Depends on Phase 11 because the production pgvector path should be real before a migration tool is built against it.

### Phase 14: Real cost accounting
**Goal**: Reported cost approximates the actual invoice rather than list price
**Depends on**: Phase 10
**Requirements**: REQ-real-cost-accounting
**Success Criteria** (what must be TRUE):
  1. A configurable discount factor and an `inference_geo` multiplier feed cost computation.
  2. `/pricing` exposes which multipliers are in effect, not just base rates.
  3. Effective-dating still resolves correctly across the 2026-08-31 → 2026-09-01 Sonnet 5 boundary, with a test pinning both windows.
  4. `pricing_unknown` semantics are unchanged — an unpriced model still fails loud and never costs zero.
  5. `/metrics` cost figures move from "the shape of the bill" to an approximation of the bill, and the docs say which it is.
**Plans**: TBD

**Notes for discuss-phase:**
- **Not a reversal** — pure extension of DEC-12. Lowest-risk requirement in the milestone.
- Ordered before Phase 16 deliberately: an independent critic model needs the price table to carry a row for whatever the critic runs on, and needs the per-run spend cap to account for a more expensive critic path.

### Phase 15: Answer-quality evals
**Goal**: Answer quality is measurable, and the live set is big enough to be called a benchmark
**Depends on**: Phase 10
**Requirements**: REQ-offline-eval-quality
**Success Criteria** (what must be TRUE):
  1. Answer quality is graded by a mechanism that does not spend money on every push — recorded-response fixtures, a scheduled live run, a separately gated job, or another approach chosen during discussion.
  2. The live case count grows past 12 to a size defensible as a benchmark.
  3. The every-push CI gate still runs offline, deterministically, with `ANTHROPIC_API_KEY=""`.
  4. The printed caveat matches whatever has become true — no run implies "the model is good" when the suite cannot support that.
**Plans**: TBD

**Notes for discuss-phase:**
- **Reversal (in tension with DEC-20).** DESIGN.md argues offline evals *should not* claim to grade quality, and prints that caveat every run because "a green suite that quietly implies 'the model is good' is worse than no suite." The replacement guarantee to decide: what the suite is now allowed to claim, and how the caveat changes to stay honest. DEC-20 is not among the promoted five; record a new ADR here.
- Ordered before Phases 16 and 17 on purpose. Those two change what the pipeline says; without a quality measure landing first, their effect on answer quality is unobservable.

### Phase 16: Independent critic model
**Goal**: The critic is a genuinely independent evaluator, and the eval-judge rationale is re-derived rather than inherited
**Depends on**: Phase 14, Phase 15
**Requirements**: REQ-independent-critic-model
**Success Criteria** (what must be TRUE):
  1. The critic's model is configurable independently of the writer/researcher model.
  2. Cost accounting prices each model correctly per node — the price table carries a row for whatever the critic runs on, or `pricing_unknown` fires.
  3. The per-run spend cap accounts for the more expensive critic path.
  4. The eval-judge choice is stated as a fresh decision with its own reasoning, superseding the promoted ADR for DEC-22 — not carried forward by default.
  5. README no longer says "The eval judge runs on a stronger model precisely because of this," because the "this" it refers to is gone.
**Plans**: TBD

**Notes for discuss-phase:**
- **Reversal — second-strongest in the set. Supersedes the ADR promoted from DEC-22.** The shared critic model was not accidental: it is the explicit justification for the stronger eval judge. Removing it removes the reason the judge is stronger.
- The replacement guarantee to decide: with an independent critic, what is the judge *for*? Answer that from scratch. Inheriting "Opus 5 because the critic is weak" is the specific failure this phase must avoid.
- Depends on Phase 14 (per-model pricing and spend-cap accounting) and Phase 15 (a quality measure that can show whether the independent critic actually helps).

### Phase 17: Follow-ups that can reach for new information
**Goal**: A follow-up unsupported by prior notes triggers new research instead of refusing, without losing the grounding guarantee
**Depends on**: Phase 15, Phase 16
**Requirements**: REQ-followup-live-search
**Success Criteria** (what must be TRUE):
  1. A follow-up whose question prior notes cannot support routes to the researcher rather than returning "the research didn't cover that."
  2. New notes join the session's note set and are attributed to the follow-up turn.
  3. The critic still grades the follow-up answer against notes as the sole source of truth — no answer comes from parametric knowledge.
  4. `no_prior_research` is explicitly redefined or retired; it is not left dangling as a reachable-but-meaningless stop reason.
  5. Spend cap, iteration cap, and revision cap all still bound the expanded path, and a forced stop still reports honestly.
  6. The routing change lives in the supervisor. `service.py` still holds no routing logic.
**Plans**: TBD

**Notes for discuss-phase:**
- **Reversal — the strongest in the set. Supersedes the ADR promoted from DEC-04.** README marks the current behaviour "By design." DESIGN.md calls the guarantee this removes "the single failure mode this whole pipeline exists to prevent."
- The replacement guarantee to decide, before any code: what does grounding mean once a follow-up can go get its own notes, and what stops the model answering from its own knowledge in the window between "notes insufficient" and "new notes arrive"? This question is the phase.
- Deepest architectural change in the milestone, and last on purpose: it wants the ADR record (Phase 10), a quality measure (Phase 15), and a settled critic (Phase 16) already in place.
- Caution: the supervisor routing table currently has "follow-up with no prior notes → END" *above* the node-selection rows. Changing its position changes precedence against the cap and budget rows.

## Progress

**Execution Order:**
Phases execute in numeric order: 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

Phases 12, 13, and 14 depend only on earlier work and not on each other; if parallel
capacity exists, they can overlap. Phases 15 → 16 → 17 are strictly sequential.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core loop | v1.0 | — | Complete | pre-GSD |
| 2. Memory | v1.0 | — | Complete | pre-GSD |
| 3. Conversation & resilience | v1.0 | — | Complete | pre-GSD |
| 4. Service | v1.0 | — | Complete | pre-GSD |
| 5. Cost & observability | v1.0 | — | Complete | pre-GSD |
| 6. Evals | v1.0 | — | Complete | pre-GSD |
| 7. Ship it | v1.0 | — | Complete | pre-GSD |
| 8. Stateless | v1.0 | — | Complete | pre-GSD |
| 9. Demo & guardrails | v1.0 | — | Complete | pre-GSD |
| 9.1 Package reorganisation | v1.0 | — | Complete | pre-GSD |
| 10. ADRs and doc correctness | v1.1 | 3/5 | In Progress|  |
| 10.5 Close the live endpoint exposure (hotfix) | v1.1 | 4/5 | In Progress | - |
| 11. Multi-machine state and pooled Postgres | v1.1 | 0/TBD | Not started | - |
| 12. Caller identity, session ownership, bounded stores | v1.1 | 0/TBD | Not started | - |
| 13. Embedding model migration | v1.1 | 0/TBD | Not started | - |
| 14. Real cost accounting | v1.1 | 0/TBD | Not started | - |
| 15. Answer-quality evals | v1.1 | 0/TBD | Not started | - |
| 16. Independent critic model | v1.1 | 0/TBD | Not started | - |
| 17. Follow-ups that can reach for new information | v1.1 | 0/TBD | Not started | - |

## Reversal register

Six requirements reverse a stated design position. Each must decide its replacement
guarantee during its own discuss-phase, and name the record it supersedes.

| Phase | Requirement | Reverses | Severity | Supersedes |
|-------|-------------|----------|----------|------------|
| 11 | REQ-connection-pool | Sizing judgement in current `db.py` | Low | No ADR — record one in-phase |
| 12 | REQ-demo-authentication | Scope choice: guardrails-not-identity | Low | No ADR — record one in-phase |
| 13 | REQ-embedding-model-migration | DEC-10 (copy, don't re-embed) | Medium | No ADR — record one in-phase |
| 15 | REQ-offline-eval-quality | DEC-20 (offline evals grade pipeline only) | Medium | No ADR — record one in-phase |
| 16 | REQ-independent-critic-model | DEC-22's premise | **High** | ADR promoted from DEC-22 (Phase 10) |
| 17 | REQ-followup-live-search | DEC-04 | **Highest** | ADR promoted from DEC-04 (Phase 10) |

Not reversals: REQ-multi-machine-state (executes DEC-15's documented path),
REQ-real-cost-accounting (extends DEC-12), REQ-store-lifecycle-and-ownership (closes a
gap the README calls a gap, not a chosen property).
