# Roadmap: research-agent

## Overview

Phases 1–9 built and shipped a supervisor-routed research pipeline as a real service:
deterministic routing, vector memory, an HTTP surface, cost accounting with a spend cap,
an eval harness, a Docker/CI/Fly deploy, Postgres+pgvector backends, and a public demo
with guardrails. It is live at `research-agent.fly.dev`.

Milestone v1.1 took on all nine items from the README's `## Limitations` list and closed
every one. Six of them reversed a design position the project argues *for*, so the milestone
opened by promoting the five load-bearing decisions into numbered ADRs — every later reversal
names the ADR it supersedes, and the register of expected reversals is now spent. The work ran
outward-in: infrastructure nothing else depends on first (multi-machine Postgres, pooling),
then identity and lifecycle, then data migration and cost, then the measurement that makes
quality changes visible, and only then the two reversals that change what the pipeline *says* —
an independent critic, and follow-ups that can reach for new information.

The service runs on two machines against Supabase Postgres at `research-agent.fly.dev`, on
release v12. **No milestone is currently defined.** One phase has landed since the v1.1
close: **17.5**, a hotfix enabling row level security on every table the service creates —
in code, **not yet deployed**.

**Definition of done for this project:** demonstrable to an employer. Live URL that works,
green CI, a README a stranger can skim. Surface tidiness is part of the deliverable.

## Milestones

- ✅ **v1.0 Production pipeline** — Phases 1–9 (shipped, plus post-Phase-9 housekeeping). Pre-GSD; record remastered 2026-08-12. → [archive](milestones/v1.0-ROADMAP.md) · [requirements](milestones/v1.0-REQUIREMENTS.md)
- ✅ **v1.1 Closing the limitations list** — Phases 10–17 + the inserted 10.5, **shipped 2026-08-11** (Fly v12). All nine limitations the v1.0 README listed are closed; six were deliberate reversals, each superseding a numbered ADR. → [archive](milestones/v1.1-ROADMAP.md) · [requirements](milestones/v1.1-REQUIREMENTS.md) · [audit](v1.1-MILESTONE-AUDIT.md)
- **Next milestone: not yet defined** — start with `/gsd:new-milestone`

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Production pipeline (Phases 1–9) — SHIPPED</summary>

Full remastered detail in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md);
per-phase records (SUMMARY + retroactive VALIDATION, reconstructed 2026-08-12 and labeled
as such) in `.planning/phases/01-*` … `09.1-*`.

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

<details>
<summary>✅ v1.1 Closing the limitations list (Phases 10–17, plus 10.5) — SHIPPED 2026-08-11</summary>

Full detail in [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

- [x] **Phase 10: ADRs and doc correctness** - Promote the load-bearing five to numbered ADRs; fix verified-false docs; redeploy so live matches `main`
- [x] **Phase 10.5: Close the live endpoint exposure (INSERTED, hotfix)** - Guard the unauthenticated session read/delete paths and stop leaking exception text; shipped as Fly v4 the day it was found
- [x] **Phase 11: Multi-machine state and pooled Postgres** - Two machines over Supabase Postgres, one pool per machine
- [x] **Phase 12: Caller identity, session ownership, bounded stores** - An auto-issued signed cookie; sessions and notes own and expire; the cap reserves against in-flight runs
- [x] **Phase 13: Embedding model migration** - Copy a corpus unchanged, or re-embed it at a new model and dimension; cost quoted before spending
- [x] **Phase 14: Real cost accounting** - Discounts and response-observed `inference_geo` at one choke point; Voyage spend counted for the first time
- [x] **Phase 15: Answer-quality evals** - Forty golden cases; real recorded answers graded keylessly and free on every push
- [x] **Phase 16: Independent critic model** - `CRITIC_MODEL`, production on Opus 5 — the gate more capable than the writer it checks
- [x] **Phase 17: Follow-ups that can reach for new information** - The unsupported follow-up researches instead of refusing; grounding kept, and it was never what was being given up

**Closed after the audit:** the `_execute` ledger hole (W1), the reservation's stale arithmetic
(W2, $0.20 → $0.30), and the five unreconciled VALIDATION contracts.

</details>

<details>
<summary>✅ Phase 17.5 — Row level security on the public schema (INSERTED, hotfix, post-close)</summary>

**Inserted 2026-08-12, after v1.1 shipped and was tagged.** It carries a v1.1-style number
because it closes a defect in v1.1's infrastructure, but it is **not part of the v1.1
milestone as archived** — the tag, the audit and `milestones/v1.1-*.md` all predate it, and
no milestone was open when it landed.

- [x] **Phase 17.5: Row level security on the public schema** - Every Postgres table the
  service creates denies every role but its owner, applied by the schema DDL itself so a
  table created later (`migrate.py embeddings re-embed --to`) cannot be missed

**Trigger:** a Supabase security-linter report — five `public` tables with RLS disabled,
plus `runs` flagged for exposing `session_id`. Not found by the requirements list, the
milestone audit, or any phase gate. Second time a live exposure arrived from outside the
plan, after Phase 10.5.

**Why it is more than a privacy finding:** `runs` is the daily spend cap's only input
(`spend_since` sums it). Measured against the real DDL on a local stand-in, a role holding
the grants Supabase hands `anon` deleted every row of `runs` without error — an emptied
ledger reads as $0 spent and the one control bounding the Anthropic bill stops bounding it.

**Shipped as Fly release v13 on 2026-08-12**, deployed by hand after three green merges
produced no release at all. Verified live: both machines on v13, all three Postgres stores
reachable, and the row counts unchanged at 7 sessions / 10 runs / 8 notes — which is the
proof that matters in both directions, since a failed `ALTER` would have surfaced the store
as unreachable and a missing owner exemption would have shown zeros with no error.

**Still outstanding:** the one-time `REVOKE` of the `anon`/`authenticated` grants, which
cannot live in code because those roles do not exist on a plain Postgres. Instructions in
`docs/OPERATIONS.md` § "Row level security", pre-flight first.

Records: [`17.5-CONTEXT.md`](phases/17.5-row-level-security-on-the-public-schema/17.5-CONTEXT.md) ·
[`17.5-01-SUMMARY.md`](phases/17.5-row-level-security-on-the-public-schema/17.5-01-SUMMARY.md) ·
[`17.5-VALIDATION.md`](phases/17.5-row-level-security-on-the-public-schema/17.5-VALIDATION.md)

</details>

## Phase Details

<details>
<summary>✅ v1.0 phase details (Phases 1–9)</summary>

> Remastered 2026-08-12: each phase below now has a reconstructed record —
> `NN-SUMMARY.md` and a retroactive `NN-VALIDATION.md` — under
> `.planning/phases/<NN-slug>/`, and the milestone is archived in
> [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

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

## Progress

**v1.1 shipped 2026-08-11.** Per-phase execution records are archived in
[milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md); the phase-by-phase evidence lives in
`.planning/phases/*/`, where every VALIDATION contract now reads `status: complete` and
`nyquist_compliant: true`.

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 Production pipeline | 1–9 (+9.1) | — | Complete | pre-GSD; remastered 2026-08-12 |
| v1.1 Closing the limitations list | 10–17 (+10.5) | 43/43 | **Complete** | 2026-08-11, Fly v12 |
| _(no milestone open)_ | 17.5 | 1/1 | **Complete, undeployed** | landed 2026-08-12 |

**Next:** no milestone defined. `/gsd:new-milestone` starts the questioning → research →
requirements → roadmap chain.

## Reversal register — spent

Six requirements reversed a stated design position. All six landed, each superseding a record
rather than contradicting prose, and the register is now **spent**: `docs/adr/README.md`'s
"remaining expected supersessions" describes an empty set. The full table is archived in
[milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

| Phase | Reversed | Recorded as |
|-------|----------|-------------|
| 11 | Sizing judgement in `db.py` | in-phase |
| 12 | Guardrails-not-identity | **ADR-0007** supersedes 0006 |
| 13 | DEC-10 (copy, don't re-embed) | **ADR-0008** |
| 15 | DEC-20 (offline evals grade the pipeline only) | **ADR-0009** |
| 16 | DEC-22's premise | **ADR-0010** supersedes 0005 |
| 17 | DEC-04 | **ADR-0011** supersedes 0003 |
