# Roadmap: research-agent

## Overview

Phases 1–9 built and shipped a supervisor-routed research pipeline as a real service:
deterministic routing, vector memory, an HTTP surface, cost accounting with a spend cap,
an eval harness, a Docker/CI/Fly deploy, Postgres+pgvector backends, and a public demo
with guardrails. It is live at `research-agent.fly.dev`.

Milestone v1.1 took on all nine items from the README's `## Limitations` list and closed
every one. Six of them reversed a design position the project argues *for*, so the milestone
opened by promoting the five load-bearing decisions into numbered ADRs — every later reversal
names the ADR it supersedes, and the register of expected reversals closed as spent. The work ran
outward-in: infrastructure nothing else depends on first (multi-machine Postgres, pooling),
then identity and lifecycle, then data migration and cost, then the measurement that makes
quality changes visible, and only then the two reversals that change what the pipeline *says* —
an independent critic, and follow-ups that can reach for new information.

The service runs on two machines against Supabase Postgres at `research-agent.fly.dev`, on
release **v13**. One phase landed after the v1.1 close and before any milestone reopened:
**17.5**, a hotfix enabling row level security on every table the service creates — shipped
the same day it was found, deployed, and closed with nothing outstanding.

**Milestone v1.2 "Nothing uncovered" is now open (Phases 18–22).** An investigation on
2026-08-13 sorted the v1.1 README's seven remaining limitations into four that close without
a successor limitation (judge independence, health credential validity, the note count bound,
and the forty recorded golden answers) and three that cannot close honestly and instead get a
record (cost-approximation-by-design, mintable identities via ADR-0007, and the free-tier
database posture). One reversal is in scope and ceremonised: moving the judge off the critic's
model supersedes ADR-0010, deliberately reopening the reversal register v1.1 closed as spent.

**Definition of done for this project:** demonstrable to an employer. Live URL that works,
green CI, a README a stranger can skim. Surface tidiness is part of the deliverable.

## Milestones

- ✅ **v1.0 Production pipeline** — Phases 1–9 (shipped, plus post-Phase-9 housekeeping). Pre-GSD; record remastered 2026-08-12. → [archive](milestones/v1.0-ROADMAP.md) · [requirements](milestones/v1.0-REQUIREMENTS.md)
- ✅ **v1.1 Closing the limitations list** — Phases 10–17 + the inserted 10.5, **shipped 2026-08-11** (Fly v12). All nine limitations the v1.0 README listed are closed; six were deliberate reversals, each superseding a numbered ADR. → [archive](milestones/v1.1-ROADMAP.md) · [requirements](milestones/v1.1-REQUIREMENTS.md) · [audit](v1.1-MILESTONE-AUDIT.md)
- 🚧 **v1.2 Nothing uncovered** — Phases 18–22, **in progress** (roadmap created 2026-08-13). Closes four README limitations honestly and records the three that cannot close honestly, so the Limitations section's terminal state is "chosen and argued for," not backlog.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Production pipeline (Phases 1–9) — SHIPPED</summary>

Full remastered detail in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md);
per-phase records (SUMMARY + retroactive VALIDATION, reconstructed 2026-08-12 and labeled
as such) in `.planning/milestones/v1.0-phases/`.

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

**Closed 2026-08-12 — nothing outstanding.** The one-time `REVOKE` of the
`anon`/`authenticated` grants (which cannot live in code, since those roles do not exist on
a plain Postgres) was run and confirmed: all five tables report `owner = postgres`,
`rls_on = t`, `api_grants = (none)`, and no `postgres`-granted default privileges remain to
cover future tables. The provider's own linter agrees — the five `rls_disabled_in_public`
errors and the `sensitive_columns_exposed` error on `runs` are cleared, replaced by five
`INFO` `rls_enabled_no_policy` notices that are the correct end state and must **not** be
"fixed" by adding a policy.

Records: [`17.5-CONTEXT.md`](milestones/v1.1-phases/17.5-row-level-security-on-the-public-schema/17.5-CONTEXT.md) ·
[`17.5-01-SUMMARY.md`](milestones/v1.1-phases/17.5-row-level-security-on-the-public-schema/17.5-01-SUMMARY.md) ·
[`17.5-VALIDATION.md`](milestones/v1.1-phases/17.5-row-level-security-on-the-public-schema/17.5-VALIDATION.md)

</details>

### 🚧 v1.2 Nothing uncovered (Phases 18–22) — IN PROGRESS

Phase numbering continues from v1.1's close (Phase 17, plus the post-close 17.5 hotfix), so
v1.2 starts at Phase 18. Ordering is constrained: the judge phase must settle before the
record run (judge verdicts are recorded once, as fixture metadata), and the record run and
the README/records close-out sit at the end, since the close-out deletes bullets the other
phases close.

- [x] **Phase 18: Independent eval judge** - `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8`, independent of the critic and the writer; ADR-0012 supersedes ADR-0010
- [ ] **Phase 19: Credential validity, log addressability, demo CSP** - `/health` reports whether keys actually work; `run_finished` carries `session_id`; the demo page ships a hash-based CSP header
- [ ] **Phase 20: Note count bound** - A per-owner count cap with oldest-first eviction, identical across all four backends
- [ ] **Phase 21: Forty recorded answers** - All 40 golden cases carry a real recorded answer, graded keylessly on every push
- [ ] **Phase 22: Limitations recorded** - Every surviving README limitation points at a record; the four closed bullets are deleted, not rewritten into release notes

## Phase Details

<details>
<summary>✅ v1.0 phase details (Phases 1–9)</summary>

> Remastered 2026-08-12: each phase below now has a reconstructed record —
> `NN-SUMMARY.md` and a retroactive `NN-VALIDATION.md` — under
> `.planning/milestones/v1.0-phases/<NN-slug>/`, and the milestone is archived in
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

### Phase 18: Independent eval judge
**Goal**: The eval judge grades every case on a model independent of the critic, and a judge
refusal surfaces as a finding rather than a misleading parse error
**Depends on**: Nothing (first phase of v1.2)
**Requirements**: REQ-judge-independent-of-critic
**Success Criteria** (what must be TRUE):
  1. `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8` — not the critic's model
     (`claude-opus-5`), stronger than the writer it grades (Sonnet 5), at zero cost change
     against `/pricing`.
  2. A judge response the safety classifier refuses is surfaced as a graded finding, because
     `graders.py` checks `stop_reason` before reading content instead of misparsing it.
  3. ADR-0012 exists, records the supersession of ADR-0010, and states plainly that this
     reopens the reversal register v1.1 closed as spent.
  4. The price table carries an Opus 4.8 row, so a judge run's cost is reported rather than
     landing on `pricing_unknown`.
**Plans**: 4 plans

Plans:
- [x] 18-01-PLAN.md — PRICES row + `JUDGE_MODEL` default flip in one commit, independence pinned against the deployed critic
- [x] 18-02-PLAN.md — the refusal guard: `stop_reason` checked before content, a decline is a graded finding reaching the recorder's failed-graders branch
- [x] 18-03-PLAN.md — ADR-0012 supersedes ADR-0010, index re-derived with a derived-counts checker, the 0005→0010→0012 chain test extended in the same commit
- [x] 18-04-PLAN.md — the collision line's premise re-derived (silent at shipped defaults, points at ADR-0012), every other judge==critic doc surface cleaned

**Status: COMPLETE (2026-08-14).** All four success criteria hold, each with a measured gate.
Final gate keyless: **749 passed / 67 skipped** exit 0; offline evals **41/41 (100% vs 90%
required)** exit 0; ruff clean. Thirteen mutations observed red across the four waves, plus
three honest greens with recorded reasons — ledger in `18-VALIDATION.md`. **Deferred and
recorded, not silent:** a real Opus 4.8 judge verdict has never round-tripped (every path is
fake-driven); the ~$0.06 one-verdict probe belongs to Phase 21's record run. **`README.md:285`
is deliberately left contradicting the tree** — Phase 22 deletes that Limitations bullet.

### Phase 19: Credential validity, log addressability, demo CSP
**Goal**: `/health` reports whether the API keys actually work without touching liveness, a
completed run is addressable from its logs, and the demo page's inline JS survives a real CSP
**Depends on**: Nothing (independent of Phase 18; sequenced here for milestone flow)
**Requirements**: REQ-health-credential-validity, REQ-run-finished-session-id, REQ-demo-csp-header
**Success Criteria** (what must be TRUE):
  1. `/health` surfaces new credential-validity fields for Anthropic and Voyage, beside the
     existing presence booleans, backed by a cached async probe (`count_tokens` for
     Anthropic, a micro-embed for Voyage).
  2. The liveness path Fly's health check reads still never calls a provider — a healthy
     container is not restarted during a provider outage.
  3. Probe spend is either excluded from cost accounting or attributed within it, and the
     code states which, deliberately rather than silently.
  4. `run_finished` log lines carry `session_id`, so a completed run is addressable from the
     logs without cross-referencing another line.
  5. The demo page ships a hash-based Content-Security-Policy header (no `unsafe-inline`)
     and its inline JS still runs, verified against the live page.
**Plans**: TBD
**UI hint**: yes

### Phase 20: Note count bound
**Goal**: Notes are bounded by count as well as expiry, with identical eviction behaviour on
every backend
**Depends on**: Nothing (independent of Phases 18–19; sequenced here for milestone flow)
**Requirements**: REQ-note-count-bound
**Success Criteria** (what must be TRUE):
  1. Each owner's notes are capped at a fixed per-owner count, with the oldest note evicted
     first once the cap is exceeded.
  2. Eviction semantics are byte-identical across json, memory, chroma, and pgvector, proven
     by the shared 4-arm contract suite (same inputs, same outcomes, all four backends).
  3. The README's notes-unbounded-by-count limitation is falsified by a passing test, not
     merely narrowed in prose.
**Plans**: TBD

### Phase 21: Forty recorded answers
**Goal**: All 40 golden cases carry a real recorded answer, replayed and graded keylessly on
every push
**Depends on**: Phase 18 (the judge must settle first — verdicts are recorded once, as fixture
metadata, and recording under a judge about to be replaced would file verdicts from an
abandoned judge)
**Requirements**: REQ-forty-recorded-answers
**Success Criteria** (what must be TRUE):
  1. All 40 golden cases have a fixture carrying a real recorded answer plus the settled
     judge's verdict as metadata.
  2. Every push replays and grades all 40 cases keylessly, with no live API key required.
  3. A case the recorder refuses (failed graders or judge) is surfaced as a finding in the
     record run's output, not silently retried or dropped.
  4. The paid checkpoint is re-quoted at run time (quoted **$17.48** on 2026-08-13) and the
     actual spend is reported against that quote.
**Plans**: TBD

### Phase 22: Limitations recorded
**Goal**: Every surviving README limitation points at a record, and the Limitations section
says plainly that what remains is chosen, not owed
**Depends on**: Phases 18–21 (every closable limitation — judge independence, credential
validity, the note count bound, and the forty recorded answers — must close before the
section can be rewritten around what's left)
**Requirements**: REQ-limitations-recorded
**Success Criteria** (what must be TRUE):
  1. A new ADR states the cost-approximation-by-design position and records why invoice
     reconciliation via Anthropic's Admin cost API was rejected.
  2. The mintable-identities limitation points at ADR-0007 instead of standing bare.
  3. The free-tier-database limitation points at a database posture note in OPERATIONS.md.
  4. The four closed bullets (judge independence, credential validity, the note count bound,
     forty recorded answers) are deleted from the README, per the standing convention —
     never rewritten into release notes.
  5. The Limitations section's intro states that what remains is chosen, recorded, and
     argued for.
**Plans**: TBD

## Progress

**v1.1 shipped 2026-08-11.** Per-phase execution records are archived in
[milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md); the phase-by-phase evidence lives in
`.planning/milestones/v1.1-phases/*/`, where every VALIDATION contract now reads `status: complete` and
`nyquist_compliant: true`.

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 Production pipeline | 1–9 (+9.1) | — | Complete | pre-GSD; remastered 2026-08-12 |
| v1.1 Closing the limitations list | 10–17 (+10.5) | 43/43 | **Complete** | 2026-08-11, Fly v12 |
| _(no milestone)_ | 17.5 | 1/1 | **Complete, deployed** | landed and shipped 2026-08-12, Fly v13 |
| v1.2 Nothing uncovered | 18–22 | 0/TBD | **In progress** | roadmap created 2026-08-13 |

**Next:** Phase 18 — independent eval judge. `/gsd:plan-phase 18`

## Reversal register — spent at v1.1 close, reopened once by v1.2

Six requirements reversed a stated design position during v1.1. All six landed, each
superseding a record rather than contradicting prose, and the register closed as **spent**:
`docs/adr/README.md`'s "remaining expected supersessions" described an empty set. The full
v1.1 table is archived in [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

| Phase | Reversed | Recorded as |
|-------|----------|-------------|
| 11 | Sizing judgement in `db.py` | in-phase |
| 12 | Guardrails-not-identity | **ADR-0007** supersedes 0006 |
| 13 | DEC-10 (copy, don't re-embed) | **ADR-0008** |
| 15 | DEC-20 (offline evals grade the pipeline only) | **ADR-0009** |
| 16 | DEC-22's premise | **ADR-0010** supersedes 0005 |
| 17 | DEC-04 | **ADR-0011** supersedes 0003 |

**v1.2 reopens this register once, deliberately:** Phase 18 moves the eval judge off the
critic's model, which supersedes ADR-0010 with a new record, **ADR-0012** — recorded as an
intentional reopening, not drift.
