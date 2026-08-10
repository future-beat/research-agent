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

- [x] **Phase 10: ADRs and doc correctness** - Promote the load-bearing five to numbered ADRs; fix verified-false docs; redeploy so live matches `main`
- [x] **Phase 10.5: Close the live endpoint exposure (hotfix)** - Guard the unauthenticated session read/delete paths and stop leaking exception text; ship immediately
- [x] **Phase 11: Multi-machine state and pooled Postgres** - Take the `DATABASE_URL` path, run more than one machine, replace the single connection with a pool
- [x] **Phase 12: Caller identity, session ownership, bounded stores** - The demo identifies callers; sessions have owners and expiry; notes stop growing forever
- [ ] **Phase 13: Embedding model migration** - A real, reversible path when the embedding model or dimension changes
- [ ] **Phase 14: Real cost accounting** - Discounts and `inference_geo` so reported cost approximates the invoice
- [ ] **Phase 15: Answer-quality evals** - Quality becomes measurable without billing every push; the live set outgrows a smoke test
- [x] **Phase 16: Independent critic model** - The critic stops sharing the writer's model, and the eval-judge rationale is re-derived
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
- [x] 10-04-PLAN.md — `docs/DESIGN.md`: four backends, ISO-dated price windows, forward-links to all five ADRs
- [x] 10-05-PLAN.md — Run every gate, prove no `src/` change and an unchanged suite, re-verify SC-5 live (checkpoint)

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
- [x] 10.5-05-PLAN.md — Truth up the docs, then the single cutover and live verification (checkpoint)

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
  1. `DATABASE_URL` is set in production against an external managed Postgres and `/health` reports Postgres-backed stores. **Amended 2026-08-05:** originally "…`research_agent.migrate` has been run dry-run then real…". The user decided the phase starts against an empty database with no data migration, keeping the volume as a backup, so the migrate step is deliberately **not** exercised. What is knowingly given up is the cumulative `/metrics` history. `research_agent.migrate` therefore remains an unproven path — a later phase needing a real migration must not assume otherwise.
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
**Plans**: 6 plans
- [x] 12-01-PLAN.md — Wave 0: chromadb joins the dev extra + 4-arm contract suite; Database.transaction() helper
- [x] 12-02-PLAN.md — Wave 1: signed HMAC identity token + mint-on-response IdentityMiddleware (never 401)
- [x] 12-03-PLAN.md — Wave 2: Postgres identity-keyed rate limit + reservation-based spend cap (advisory-lock)
- [x] 12-04-PLAN.md — Wave 3: session ownership, 7-day derived expiry, dual-mode listing, 404-not-403, walker surgery
- [x] 12-05-PLAN.md — Wave 4: owner-scoped notes + 7-day TTL across all four backends; owner threaded through the graph
- [x] 12-06-PLAN.md — Wave 5: ADR-0007 supersedes 0006, README fix, identity-aware page (criterion 6), live cutover
      — **Tasks 1–3 only.** Task 4 (T-06-4, the `checkpoint:human-action` live cutover) is
      deferred by the user and unstarted: no Fly secret set, no deploy, live service untouched.
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
**Plans**: 5 plans

Plans:
- [x] 13-01-PLAN.md — Repair migrate.py's live owner/TTL data-loss bug, then prove the legacy SQLite→Postgres path with its first tests
- [x] 13-02-PLAN.md — Golden recall harness + `embeddings copy` subcommand; byte-fidelity and exact-scan zero-delta gates (SC-5 infrastructure half)
- [x] 13-03-PLAN.md — `embeddings re-embed` + VOYAGE_PRICES cost preview + `--yes` spend gate + dimension ceiling and loud-check gates (SC-1/2/4)
- [x] 13-04-PLAN.md — Cutover-reversible test + ADR-0008 (DEC-10 disposition) + OPERATIONS/README rewrites (SC-3)
- [x] 13-05-PLAN.md — Live demonstration against Supabase scratch tables (checkpoint) + phase gate battery

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
**Plans**: 3 plans

Plans:
- [x] 14-01-PLAN.md — Multipliers at the one choke point: discount × response-observed geo in `CallUsage.cost_usd`, boundary/fail-loud/preview-list-price pins (SC-1/3/4)
- [x] 14-02-PLAN.md — Voyage token capture via contextvar meter, `record_embedding` fold, RunRecord column migration on both live-table idioms, settle-sees-multiplied-cost gate (SC-4/5)
- [x] 14-03-PLAN.md — `/pricing` multipliers + nullable `windows.next` + embedding row, `/metrics` embedding aggregates, README/OPERATIONS honesty rewrite (SC-2/5)

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
**Plans**: 6 plans

Plans:
- [x] 15-01-PLAN.md — Recorder seam (`capture_state` in `run_case`) + fixture schema/refusal layer (`evals/fixtures.py`), proven against fakes
- [x] 15-02-PLAN.md — Deterministic quality graders (grounding/coverage/structure/refusal/case-pins), each with a passing AND failing synthetic fixture + claim-boundary docstrings
- [x] 15-03-PLAN.md — Automatic replay in offline mode + model-mismatch hard gate + SC-4 caveat rewrite; CI command and keyless invariant unchanged
- [x] 15-04-PLAN.md — Dataset 12 → 40 across the taxonomy; `seeded_notes` adversarial mechanism; `no_prior_research` gap closed; property pins (SC-2)
- [x] 15-05-PLAN.md — `--record`/`--yes`/`--force` CLI + runtime cost preview via `price_for()`, all machinery proven with fakes
- [x] 15-06-PLAN.md — ADR-0009 + README/DESIGN honesty rewrite + calibration recording checkpoint (~$0.25) + full-run record-or-defer decision

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
**Plans**: 4 plans

Plans:
- [x] 16-01-PLAN.md — critic_model() accessor + four-site threading in call_model + attribution proofs (neutral default, misbilling discriminator, per-node arithmetic)
- [x] 16-02-PLAN.md — Fixture gate with backfill semantics + recorder critic entry + judge/critic collision warning + reservation threshold prose
- [x] 16-03-PLAN.md — ADR-0010 supersedes ADR-0005 + graders/DESIGN stale prose + README whole-file pass (limitation deleted)
- [ ] 16-04-PLAN.md — Live demonstration (haiku critic, record-or-defer) + full phase gate + close checkpoint

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
**Plans**: 4 plans

Plans:
- [x] 17-01-PLAN.md — Eval/grader mechanics first (expectation-keyed bounded-research grading, ScriptedClient pop-lists, preview topology) — zero behavior change, keeps every wave green
- [x] 17-02-PLAN.md — Path 1: row 4 flips to researcher in place, append-not-replace (red-first), eight precedence pairs with mutations observed red, path-1 golden case flip
- [x] 17-03-PLAN.md — Path 2: the INSUFFICIENT sentinel + one-pass bound, three path-2 golden flips (A1 honored), no_prior_research vocabulary sweep in code
- [ ] 17-04-PLAN.md — ADR-0011 supersedes ADR-0003, README whole-file pass (limitation DELETED, nine-list closed), demo copy + pin, live closing checkpoint (record-or-defer) — **Tasks 1–2 DONE (`25c34d7`, `b2d6ccd`, `1ffebe7`); Task 3, the live checkpoint, is UNSTARTED: it runs post-merge and the PR is not open**

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
| 10. ADRs and doc correctness | v1.1 | 5/5 | In Progress | All 5 plans executed; SC-1/2/3/4/6 green. Sign-off pending on SC-5 step 3 — `main` is 21 docs-only commits ahead of `origin/main`. No code differs; resolve with a push, not a deploy. |
| 10.5 Close the live endpoint exposure (hotfix) | v1.1 | 5/5 | Complete | Shipped as Fly release v4 on 2026-08-04; re-verified live 2026-08-05 (v4 healthy, `/`, `/health`, `/demo`, `/metrics` all 200) |
| 11. Multi-machine state and pooled Postgres | v1.1 | 5/5 | Blocked | All 5 plans executed, but 11-05 Tasks 2–3 are blocked: `fly deploy` cannot answer its own volume-detach prompt non-interactively on flyctl v0.4.78. `fly.toml` is stateless and the guards pass, but production is still ONE machine on release v6 with the volume attached, so **SC-2's live half and SC-3 are unproven**. Needs an operator-run interactive deploy, then `fly scale count 2`. |
| 12. Caller identity, session ownership, bounded stores | v1.1 | 6/6 | Executed — awaiting verify + PR | All 6 plans executed, suites green (527/47 plain, 572/1 armed, `ruff` clean), and **the live cutover is done**: `IDENTITY_SIGNING_SECRET` deployed app-wide, releases **v8** then **v9**, both machines (`846975f2604548`, `d8d0320f751618`) healthy. Verified live with recorded output: `identity_signing: true` on both machines; a cookieless caller gets a working page + a completed research stream with a signed `HttpOnly; Secure; SameSite=Lax` identity minted on that same response; a cookie minted on A verifies on B with **zero** re-mints and survives a fleet restart; a second identity gets an empty listing and a 404 indistinguishable from missing. Both requirements now **Complete**. Two gaps recorded rather than waived: no real-browser dev-tools session (all live checks were `curl`) and the rollback was not exercised. Not yet pushed; branch `gsd/phase-12-caller-identity`. |
| 13. Embedding model migration | v1.1 | 5/5 | Executed — awaiting verify + PR | All 5 plans executed; suites green (529/63 plain, 591/1 armed, 592/0 with `REQUIRE_POSTGRES=1`, `ruff` clean); 13-VALIDATION signed off. **The path was demonstrated live once** (2026-08-09) against production Supabase on `migration_demo_*` scratch tables: copy leg **zero** recall delta, re-embed to voyage-3.5-lite moved **8 of 8** golden queries (one changing which notes returned), tenancy and the 7-day clock carried, all three tables dropped with `pg_tables` proving zero residue (confirmed via the app client and `psql`). Real spend ≈ $0.000015. `research_notes` untouched; no `fly secrets`, no deploy, no production model flip. The run found four things the local gates could not: `recall_delta` was also comparing two query vectors (the source deltaed against **itself**), Voyage's `total_tokens` is not an invoice (0 for a one-word document), the preview over-counts (40 vs 25), and `PG_POOL_TIMEOUT=2.0` does not fit an operator laptop — all four carried into code, tests and the runbook. Not yet pushed; branch `gsd/phase-13-embedding-migration`. |
| 14. Real cost accounting | v1.1 | 3/3 | Complete   | 2026-08-09 |
| 15. Answer-quality evals | v1.1 | 6/6 | Executed — awaiting verify + PR | Waves 1–6 done; **the phase is complete**. Wave 1: the recorder seam (`run_case(capture_state=True)`) and `evals/fixtures.py` — a models MAP rather than a flat model string, refusal of any recording whose own grades failed, total load-time validation. Wave 2: five deterministic quality graders over a recorded state, each with a synthetic state it passes AND one it fails, each stating what it cannot catch, enforced by a test over the registries. Wave 3: replay wired into the offline run, keyless, with the CI command and `ANTHROPIC_API_KEY: ""` unchanged — the replay leg **all-must-pass at the exit code** while the behavioural leg stays rate-governed at 0.9; the caveat prints the recording's date/model/sha/age. Wave 4: GOLDEN 12 → 40 across the locked taxonomy, the `no_prior_research` gap closed, two adversarial cases seeding a poisoned note into their own store, seven property pins. Wave 5: `--record` prices itself from `usage.py` at run time, refuses without `--yes`, and refuses to write a red recording. **Wave 6: ADR-0009, the README claim, and the first real recording.** `technical-figures` recorded live for a measured **$0.2427** (preview $0.2950); the fixture is committed and replays green keyless — offline is now **41/41** and the shipped caveat prints `recorded 2026-08-10 on claude-sonnet-5 (225b06b, 0 days ago)`. Three findings that only a real run could produce: the preview's pipeline assumption was a **35% under-quote** hidden inside a generous judge assumption (constants corrected; the full-run quote moves $12.78 → **$16.51**, $21.06 from 2026-09-01); a CLI test was passing only because `evals/fixtures/` was empty; and grounding has a **role-blind collision** — `4.0` in a note about "the earlier 3.x/4.0 model generations" grounds a draft restating a $2 price as $4, green. That is pinned by a two-directional test and written into ADR-0009's cannot-catch column. **The full 40-case record run is explicitly DEFERRED** — an operator spend decision, not a phase blocker; fixtures exist for **1 of 40** and the README says so. Suites **663/65** plain, **727/1** armed, `ruff` clean, `.github/workflows/ci.yml` zero diffs. Branch `gsd/phase-15-answer-quality-evals`, unpushed. |
| 16. Independent critic model | v1.1 | 3/4 | In Progress | Wave 1: `graph.critic_model()` reads `CRITIC_MODEL` per call (unset or blank means the writer's model — a neutral default, so the capability ships as a no-op until an operator acts), and `call_model` takes a keyword-only `model`, resolves it once, and uses it at **all four** places it names a model: the span, the API request, the cost `record()` and the log line. That four-way threading is load-bearing because attribution here is a **passed constant, not a response echo** — `CallUsage.from_response` never reads `response.model`, so a name threaded to the API call alone would bill an Opus critic at Sonnet rates, 2.5× under, with no error anywhere. Fifteen new tests across the four VALIDATION selectors (5/4/3/3, each `--collect-only` verified against the whole `tests/` tree): the accessor and its per-call read; the four sites each asserted separately; the misbilling discriminator (an unpriced `CRITIC_MODEL` fires `pricing_unknown` **only** if the threaded name reached `record()`); and exact per-node arithmetic measured as a *difference* between haiku and opus runs — both undated rows, so the $0.0060 gap is fixed forever and Sonnet's 2026-08-31 boundary never enters an exact assertion. The neutral default is **demonstrated, not claimed**: full per-call payload dicts with the variable unset compare equal to a run with it set to the writer's own model, each against a fresh store. Six mutation probes rather than the planned three — the span and log sites had none, and each added probe reds exactly one test; and under every threading mutation **all twenty pre-existing smoke tests stay green**, which measures rather than assumes RESEARCH Pitfall 3 (the fakes ignore `kwargs["model"]`, so these fifteen tests are the entire coverage of the seam). Suites **678/65** plain and **742/1** armed (both baseline +15, zero new skips), offline evals **41/41** keyless with `CRITIC_MODEL` provably unset, `ruff` clean. Nothing in README or `docs/` is falsified yet — the "critic shares the writer's model" limitation stays literally true of the deployed default and is wave 3's to delete. **Wave 2:** the replay staleness gate learns the second role. `grade_fixture_current` grades **pipeline against `graph.MODEL` and critic against `graph.critic_model()`**, backfilling a missing or blank `critic` key to the pipeline model — honest rather than convenient, because the one committed fixture was recorded at `225b06b` when `call_model` had no `model` parameter at all, so its critic ran on `graph.MODEL` *by construction*. `record_case_to_fixture` writes the third entry from now on, so absence keeps meaning pre-16 and the pre-16 population stays exactly one file. Consequence recorded rather than discovered: after the cutover that fixture grades **stale** in any environment that sets `CRITIC_MODEL` — the designed staleness, with the re-record deferred to the full 40-case run; CI is keyless and never sets it, so offline stays **41/41**. Record mode now states the judge/critic relation once per run on stderr, worded as a **fact** because it fires on the chosen production config (judge and critic both `claude-opus-5`): it names the shared model, says the verdicts stay independent of the *writer's* model and are not independent of the critic's, and points at ADR-0010 — a test forbids "misconfig"/"error"/"invalid". The **$0.20 reservation stays flat** with the arithmetic that would move it written into `reserved_run_usd`'s docstring and OPERATIONS (baseline: zero `CRITIC_MODEL` mentions in either, now 1 and 6): Opus-critic typical ≈ **$0.18**, the 3-call revised tail ≈ **$0.28** outside the estimate by design, and the threshold that actually breaks $0.20 is **2026-09-01**, when Sonnet's introductory window closes and a typical *unchanged* run reaches $0.21–0.22. The function itself did **not** become model-aware — `limits.py` still imports neither `usage` nor `graph`, and a test now reds if someone builds the rejected alternative. Twelve new tests (`fixture_critic_gate` 5, `judge_critic_collision_warning` 4, `reservation_threshold` 2, plus the recorder's env-driven twin) and **fifteen mutation probes where the plan named two**. Two of this wave's gates had **no probe at all** and both gained a test: the new stderr site dereferences `judge.model` upstream of the judgeless refusal, and the reservation prose's only gate was a grep inside a plan that nothing runs again. The sharpest probe: a recorder writing `graph.MODEL` into the critic slot **satisfies the models-map pin**, because the suite runs with `CRITIC_MODEL` unset and the two are then the same string — a pin that runs at the neutral default cannot see a mutation that produces the neutral default. Two of the plan's own verify selectors were vacuous (`-k docstring` collects 0; `-k "record and models"` misses the map pin) and were corrected before the probes were believed. Suites **690/65** plain and **754/1** armed (both +12, zero new skips), evals **41/41** keyless, `ruff` clean, zero diffs in `evals/fixtures.py`, `evals/fixtures/` and `.github/workflows/ci.yml`. **Wave 3:** the record catches up with the reversal. **ADR-0010** answers from scratch the question ADR-0005 could no longer answer — with an independent critic, what is the judge *for*? — on four legs, two of which are positions rather than deductions. (a) The **different job** stands alone: the critic gates *drafts* against *notes* inline and feeds the revision loop; the judge grades *finished answers* against *question + rubric* retrospectively, and its verdicts are the refusal gate for recordings and the replayed assertions of every keyless CI run — true whatever models either runs on, so removing the shared-model premise removed a reason the judge had to be STRONGER, not a reason it EXISTS. (b) The **critic-outranks-the-writer** stance is recorded as **Hesam's own position, quoted verbatim** ("Use Opus as the critic's model since it has to be more capable than the writer's model"), explicitly his rationale rather than an inference — the research had recommended deferring the flip. It inverts ADR-0005: that record justified a strong JUDGE by a weak critic; this one wants the GATE stronger than what it gates. (c) Independence is re-targeted to judge ≠ **WRITER** (`:464` survives untouched) and **judge == critic is recorded as an ACCEPTANCE, not an oversight** — both `claude-opus-5` in production, so verdicts are independent of the writer's model and **not** of the critic's family; the honest narrowing of ADR-0005's claim, stated rather than discovered, with the note that Opus 5 and Sonnet 5 share a family anyway. (d) "Stronger" survives for the judge as a **preference** and never again as the reason. Structured-verdict half carried forward in an ADR-0007-shaped section; five rejected alternatives including the twice-rejected model-aware reservation. **Mechanics exact:** 0005's diff against **main** is `1 1` (the status line, nothing else), 0002 is zero-diff, both index rows land the pre-named forecast, and the counting prose is corrected to **eight of ten / two supersessions** — the plan asked for "nine of ten" while also asking for "two supersessions", which cannot both hold. Stale prose: `graders.py`'s docstring rewritten (no test pins it — four `__doc__` greps recorded), `DESIGN.md:74` one line and one hunk, and the **README limitation DELETED, not rewritten** — grep ran first and found the only load-bearing fact ("the judge runs on a stronger model") surviving independently at `:32`, so nothing needed relocating. The residual is one sentence stating REALITY: the critic runs on Opus 5, a more capable model than the Sonnet 5 writer it gates, and the judge shares it. Whole-file pass found four things the plan did not name: **`663 tests` at two sites, falsified by this phase's own waves 1–2 → 690**, the stack line naming one model where production runs two, the config paragraph owing `CRITIC_MODEL` (placed *after* the `/pricing` sentence, because `/pricing` deliberately does not surface it), and the `$0.14` transcript figures left alone rather than replaced with an estimate. **Two gates had no probe, again.** The record-mode line names `ADR-0010` and three tests pin that string — nothing checked it resolves; a test now holds both halves of the supersession, and probe A shows all four collision tests stay **green** with the record deleted. And the docstring above the `:464` pin still ended "the same limitation the in-graph critic already has" — the dead premise, invisible to every grep in the plan, the research and VALIDATION; corrected in the same two lines so the assertion stays at `:464`. Suites **691/65** plain and **755/1** armed (+1, zero new skips), evals **41/41** keyless, `ruff` clean. |
| 17. Follow-ups that can reach for new information | v1.1 | 3/4 | In Progress | **Wave 1: the eval machinery the flips will land on, with zero behaviour change.** The wave order is a deliberate deviation from the sketched shape (graph first) and it is forced: the offline evals drive the REAL supervisor, so `grade_followup_did_not_research` — which reds ANY researcher visit on a follow-up — would red the suite the moment the graph flipped. `ScriptedClient` returned `case.notes` for **every** `"Search the web"` prompt (Pitfall 5), so a reaching follow-up would have "found" the notes it already had and wave 2's grounded-answer case would ground on nothing new; researcher outputs are now a pop-list (the `verdicts` idiom, exhaustion falls back rather than raising) and `self.answers` interleaves the authored `INSUFFICIENT:` sentinel ahead of each answer, so one follow-up turn can speak twice. `Followup` gained `expect_research` / `insufficiency` / `research_notes`, all defaulting to today's behaviour, and its `expect_forced_stop` docstring stopped claiming "today only `no_prior_research`" — the claim this phase falsifies. `grade_followup_did_not_research` is retired **BY DESIGN** and replaced by `grade_followup_research_bounded`, whose `expect_research=False` branch is **the old body verbatim** (a follow-up whose notes cover its question must still never search — scoping a property to the cases it is true of is not softening it) and whose True branch is bounded on **both** sides: `!= 1`, because zero passes (the reach never happened; the answer came from somewhere nobody authorised) is as silent a failure as two, and `> 1` would have shipped that half ungated. New `grade_followup_reach_traced` makes SC-4's redefinition of `no_prior_research` **graded rather than renamed** — a supervisor trace entry must carry a `followup_research` reason drawn from a named vocabulary, and an unrecognised value is a fail, not just a missing one. The record preview now prices an `expect_research` follow-up at the research constants with its five web searches: Phase 15 paid $0.24 to learn its quote read 35% low, and the identical failure was structurally available here on a forty-case run — closed before a record run rather than after one, with the calibration comment stating that **both** turn classes remain unmeasured. **Ten mutation probes against the plan's three**, each red on the assertion that owns it; two of them drop the run to **33/41**, which is the proof both new graders are actually reached by the real suite and not dead registry weight — something no unit test can establish. All three `-k` selectors `--collect-only`'d first (5, 8, 7 against minimums 3, 6, 1). The three wave-2-owned before-pins survive intact; weakening them a wave early is Pitfall 4 and would leave the dataset flip ungated. Suites **705/65** plain and **769/1** armed (both +13, zero new skips), offline evals **41/41** keyless before and after, routing suite 38 untouched, `ruff` clean, zero diff in `.github/workflows/ci.yml`. README's "no new search", routing row and follow-up limitation deliberately **unchanged** — still true of the shipped graph, and waves 2/4 own them; the one fact this wave falsified was its own test count (690 → 705). Branch `gsd/phase-17-followup-live-search`, unpushed. **Wave 2: the reversal itself, path 1.** Routing row 4 flips IN PLACE — a follow-up with no notes behind it routes to the **researcher** instead of ending `no_prior_research`, and the row keeping its POSITION is the load-bearing half: above the classifier row is what keeps "a follow-up never classifies" a property of the table rather than of how `followup_state` happens to be built. New flag-gated row 5 (`notes_insufficient and not followup_research_done -> researcher`, consuming the flag and recording its reason) ships its consumer half; nothing sets the flag until wave 3, and it is unit-tested from hand-built state, which is how this suite works. `no_prior_research` is now a **trace event** on the supervisor's own entry and has **zero** forced-stop assignments in `src/`. **The sharpest bug was not the routing table:** `state["research_notes"] = notes` was a REPLACE that discarded the session's note set on a follow-up pass while everything stayed green, because the critic grades the draft against whatever `research_notes` holds — a swapped set and an enlarged one produce identical runs. It now APPENDS, and the pin was written and observed **RED first** (`assert 'FACTS: …'.startswith('PRIOR NOTES MUST SURVIVE')`), quoted in the summary; a green-from-the-start pin would have proven nothing here. **The flip is destination-invisible** — row 4 and the generic no-notes row send the same state to the same node — so all twelve precedence tests assert SIDE EFFECTS (the trace reason, the spent pass, the empty forced stop, the classifier the position skips), and mutation M2 (row 4 moved below the generic row) leaves `next_step == "researcher"` while reddening on the flag. **Five row mutations plus five extra probes**, each red on the assertion that owns it: the mode guard, the flag gate, the flag clear, the store prefix and the append itself own lines no row move can reach. Six of the twelve say the **guardrails outrank both reach rows** (3 caps × 2 rows): a capped or over-budget follow-up still ENDs honestly and never researches, and M5 (row 5 above the caps) reds three of them at once. `followup-with-no-prior-research` flipped to the **route-then-guardrail** end-to-end pin — one golden case pinning the route AND the guardrail through the compiled graph, where "the caps win" is a claim about accumulated cost no routing-table test can make — with its three dependent pins in the **same commit**. The flip-tag test kept its BEFORE half rather than being replaced: it expires per case, not per wave, and the three refusal cases flip in wave 3. `expect_notes_stored` stays **False** against the plan's guess, measured: that grader runs on the RESEARCH turn, which the budget stops before the researcher — while the follow-up's own pass does store its note, which is ADR-0011 consequence material. **P15** (supervisor stops recording WHY it reached) drops the real 41-case run to **40/41**, which is the proof wave 1's trace grader is reached by the shipped suite rather than dead registry weight. Suites **721/65** plain and **785/1** armed (both +16, zero new skips), evals **41/41** keyless, routing suite **38 → 52**, `ruff` clean. README's routing table and test count (705 → 721) corrected — the two facts this wave falsified; the "no new search" promise and the follow-up limitation are still true of the shipped responder and remain wave 4's. **Wave 3: the reversal itself, path 2 — and the producer row 5 was waiting for.** The responder now signals insufficiency in the critic's own idiom: the prompt asks for `INSUFFICIENT: ` + one line naming what is missing, and the node parses it by fixed prefix exactly as `verdict.startswith("APPROVED")` is parsed. **One boolean gates the prompt branch AND the parse** (`pre_research = not followup_research_done`), which is the whole defence against Pitfall 3: a sentinel can never be read out of a response the prompt never asked for. The signal path returns **before** `draft`, `reviewed`, `revision_count` and the `answer_length` trace entry are touched, so "the insufficiency window ships NO answer" is a property of the control flow rather than a promise kept by convention — the flag routes, it never generates. All four behaviour pins were observed **RED first** against the shipped responder, and the three identical reds are one fact: *today the sentinel text IS the shipped draft* — a responder saying `INSUFFICIENT: …` handed it to the critic, which APPROVED it (it claims nothing), and the caller received it as their answer. **The one-pass bound is proven on both halves**: the honest refusal ships critic-reviewed WITH the attempt in its trace, and a post-research sentinel is an ORDINARY DRAFT that cannot re-route — probe P1 (parse ungated) shows the alternative silently corrupting the shipped answer with the fake's fallback reply, **no error anywhere**. `critic_node` is **byte-identical to main** (`md5` equal on the extracted function; no diff hunk falls inside its line range) — SC-3 and ADR-0002 discharged by measurement, not assertion. The mode-free gate was **verified, then pinned**: `"responder"` is produced by exactly one expression in the table (`author`), which is the responder only in follow-up mode, and an eight-state parametrized test now says so. **Three path-2 golden cases flipped with their taxonomy pins in ONE commit** — `admits-a-gap` → research-then-grounded (the pass carries Gartner's $4.2bn 2027 figure and the answer cites it), `refuses-an-uncovered-figure` → honest-refusal-after-one-pass (**A1 honoured over RESEARCH Q5's lean**: the pass returns more `statement_timeout` material and nothing on `lock_timeout`), `refuses-a-forecast` → the same shape on a genuinely unanswerable question. All three run responder → researcher → responder → critic through the compiled graph with notes 240→500, 241→468, 229→440 — **row 5 firing end to end**, which makes the README row wave 2 shipped describe a path an input can actually take. Zero net-new cases; the count stayed 41/41. The strata test now pins **four counted shapes** including the one Phase 17 KEPT (≥4 answerable-no-reach cases — the set `grade_followup_research_bounded`'s verbatim pre-17 branch is applied to, which at zero cases grades nothing while looking green). The flip-tag test's BEFORE half was **retired one wave after wave 2 deliberately kept it**: with every refusal case flipped, no case satisfies `not answerable and not expect_research`, so it would loop over zero cases and pass forever — replaced by a counted after-pin plus a `stranded` clause. Three refusal-grader fixtures were re-pointed off the now-answerable Gartner case; left alone they answered every assertion with *"not a refusal case"*. SC-4's code half swept: `no_prior_research` is **absent from `chat.py` entirely** (the REPL's special case dies with the stop it explained), appears in `graph.py` **exactly once outside a comment** and never as a `forced_stop_reason`, and the HELP text stops promising "no new web search" — all held by a source-reading gate that strips comment lines before counting, because a gate that counts prose can be satisfied by deleting prose. `MAX_ITERATIONS` gains one comment line (path-2's worst case is the same ten turns) and **no constant moves**; the reservation prose says follow-ups joined the research cost class (~$0.21) and that **$0.20 still stands**, in `limits.py` and its OPERATIONS mirror. **Thirteen mutation probes where the plan named three**, each red on the assertion that owns it; Q1/Q2/Q4 also drop the **real** 41-case run to 40/41, the only evidence that these cases are graded by the suite that gates the phase. Two gates were added because the plan's set left them uncovered: the PROMPT branch is invisible to the fakes (P2 reds only the new prompt-content pin), and the followup-only premise had no test at all. R3's first red landed on a weaker clause of the same conjunction; the assertions were reordered so the strongest claim reports, and it was re-run — a probe that reports the wrong line is a result to fix, not a gate to trust. Suites **735/65** plain and **799/1** armed (both +14, zero new skips), evals **41/41** keyless, routing **52 → 60**, smoke **37 → 43**, `ruff` clean, zero diff in `.github/workflows/ci.yml`. README: the test count (721 → 735) and "follow-up isolation" — which named a grader retired in wave 1 — are the two facts this wave falsified; line 99's "no new search" and line 260's limitation remain wave 4's. **Wave 4, TASKS 1–2 ONLY — the record and the sweep; the live checkpoint (17-04-T3) is UNSTARTED by instruction, since it runs post-merge and the PR is not open.** ADR-0011 is `Accepted — supersedes ADR-0003`, and it leads with wave 3's own measurement rather than the design argument, because that is the stronger case: under ADR-0003 **the refusal text WAS the shipped draft**, approved by the critic — correctly, since a sentence that asserts nothing cannot be an unsupported assertion — so the pipeline's one quality gate was at its most vacuous exactly where the reader needed it most. The record separates what dies ("no searches after session start", the `no_prior_research` END, the README limitation) from what survives (**ADR-0002 reaffirmed by citation and zero-diff**, and the replacement guarantee: the insufficiency path returns before `draft`/`reviewed`/`revision_count`/the answer-length trace entry, so "the window ships nothing" is control flow, not convention), names **the one-pass bound as its own deliberate limit** with multi-pass in the rejected alternatives, and records `no_prior_research` as **redefined, not retired** — with the reason it is *graded* rather than merely emitted. Also recorded: the ADR-0001 equivalence (the flag's origin is model output parsed by fixed prefix, exactly as `approved` always was), the append-not-replace fix, and 17-02's measured **budget-stop asymmetry** (notes stored before the supervisor sees cost outlive the stop). ADR-0003 loses **exactly one line** — `git diff main --numstat` prints `1	1`, re-checked POST-commit because a working-tree diff is empty then and passes vacuously — and its "That reversal has not happened" stays as written. **The index arithmetic is verified against the table, not against a string**: a checker derives records=11 / accepted=8 / superseded=3 from the rows, cross-checks files on disk, and requires each superseded row's target to say `supersedes` back. **Three paragraphs went stale with the eleventh record, not one** — the counting prose, the "remaining *expected* supersessions" sentence (0003 held the only forecast, so flipping it left that sentence describing an empty set; the reversal register is now spent and `grep -c "expected:"` is **0**), and *Reading a superseded record*, extended to 0003 as the sharpest case of the never-edit rule. A fourth, odd-ones-out, gained the paragraph explaining why 0011 carries `**Source:**` even though the decision it reverses came from DESIGN.md: its argument overturns the record promoted from that passage, and the passage is downstream. README: the limitation **DELETED**, and grep-before-delete earned its keep — RESEARCH said the bullet held no facts of its own, but the phrase *"the research didn't cover that"* lived **only** there and is still true after a pass, so it was relocated to the routing prose. The closure is said in **two** places (§ Limitations opener and § Status 17) and **checked against git history**: `3acaec7`'s nine bullet headings, none surviving today, the follow-up one last. **Eleven mutation probes** where the plan named none, and two of them found vacuous gates: **A5** moves the 0003 table row and leaves the prose alone — both of the plan's literal greps stay GREEN while the checker reds on both count clauses; **B5** deletes the § Limitations closure sentence and `grep -ci "nine"` stays nonzero because § Status also says it. **B1** is the SC-6 one: a routing `if` smuggled in beside the comment edit lands in the SAME hunk, so the hunk-count gate does not move — SC-6 is proven instead by **AST equality modulo docstrings against main** (71291 chars, identical), which is the claim "service.py holds no routing logic" made where it cannot be gamed. B2 PASSED first and the probe was wrong (`-k demo_page` never collects the pin's owner); re-targeted by `--collect-only`, it reds in both directions. `service.py` took **two** prose hunks, not one: line 720's "a follow-up is cheaper than a research run" is falsified by this phase and sits three lines from the docstring. The whole-file pass also caught the README's **"Nine numbered ADRs"**, true when written at `bafaff0` and two behind since phase 16. Suites **735/65** plain and **799/1** armed — **zero delta, this plan adds no tests** — evals **41/41** keyless, routing **60**, smoke 43, `ruff` clean, zero diff in `.github/workflows/ci.yml`, ADR count 10 → **11**. Every entering baseline measured before the first edit rather than taken from the plan. Branch unpushed, nothing merged. |

## Reversal register

Six requirements reverse a stated design position. Each must decide its replacement
guarantee during its own discuss-phase, and name the record it supersedes.

| Phase | Requirement | Reverses | Severity | Supersedes |
|-------|-------------|----------|----------|------------|
| 11 | REQ-connection-pool | Sizing judgement in current `db.py` | Low | No ADR — record one in-phase |
| 12 | REQ-demo-authentication | Scope choice: guardrails-not-identity | Low | No ADR — record one in-phase |
| 13 | REQ-embedding-model-migration | DEC-10 (copy, don't re-embed) | Medium | No ADR — record one in-phase |
| 15 | REQ-offline-eval-quality | DEC-20 (offline evals grade pipeline only) | Medium | **ADR-0009 recorded in-phase** (Accepted; supersedes DEC-20's scope in prose, the 0008 precedent) |
| 16 | REQ-independent-critic-model | DEC-22's premise | **High** | ADR promoted from DEC-22 (Phase 10) |
| 17 | REQ-followup-live-search | DEC-04 | **Highest** | ADR promoted from DEC-04 (Phase 10) |

Not reversals: REQ-multi-machine-state (executes DEC-15's documented path),
REQ-real-cost-accounting (extends DEC-12), REQ-store-lifecycle-and-ownership (closes a
gap the README calls a gap, not a chosen property).
