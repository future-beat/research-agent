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
- ✅ **v1.2 Nothing uncovered** — Phases 18–22 + the inserted 21.5 and 22.5, **shipped 2026-08-17** (Fly v18 → v23). Seven limitations became three: four closed and deleted, three given records that argue them. Its paid record run found three things no free test could reach, and two of its phases exist because of what that run — or a user — reported. → [archive](milestones/v1.2-ROADMAP.md) · [requirements](milestones/v1.2-REQUIREMENTS.md) · [audit](v1.2-MILESTONE-AUDIT.md)

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

<details>
<summary>✅ v1.2 Nothing uncovered (Phases 18–22, plus 21.5 and 22.5) — SHIPPED 2026-08-17</summary>

Full detail in [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md).

- [x] **Phase 18: Independent eval judge** - `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8`, independent of the critic and the writer; ADR-0012 supersedes ADR-0010
- [x] **Phase 19: Credential validity, log addressability, demo CSP** - `/health` reports whether keys actually work; `run_finished` carries `session_id`; the demo page ships a hash-based CSP header
- [x] **Phase 20: Note count bound** - A per-owner count cap with oldest-first eviction, identical across all four backends
- [x] **Phase 21: Forty recorded answers** - Every golden case is recorded or carries a documented refusal (amended mid-run, user-ratified): 19 recorded, 21 in `evals/REFUSALS.json`, union enforced by test; $9.90 actual vs $17.48 quoted
- [x] **Phase 21.5: Classifier on Opus 5** - The classifier runs `claude-opus-5`, measured 37/38 vs Sonnet 5's 32/38 against the corrected labels (five fixes, zero regressions, +0.2%/run); three disputed labels relabelled and one left with its structural conflict recorded; six of eight topic_type-refused cases re-recorded, the two remaining refusing on different graders
- [x] **Phase 22: Limitations recorded** - Every surviving README limitation points at a record; the closed bullets are deleted, not rewritten into release notes — seven bullets became three, the four deletions verified on the git axis and orphan-free everywhere the sweep reaches
- [x] **Phase 22.5: The demo shows progress (INSERTED, hotfix)** - The stream announces the stage it is STARTING, not only the one it finished, so the demo stops looking dead for the two minutes the researcher runs

**The milestone's own close-out found a gap in itself:** Phase 21's two paid plans were
ticked while their records did not exist. Reconstructed from archived evidence, verified
retrospectively, and the promised settled-judge gate — which had never been written —
written and mutation-tested. Recorded rather than tidied away.

</details>
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

*v1.2's per-phase detail lives in [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) and in each phase's own records under `.planning/phases/`.*

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
| v1.2 Nothing uncovered | 18–22 (+21.5) | 16/16 | **All phases executed** 2026-08-16 | not yet shipped — verification, then `/gsd:complete-milestone` |

**Next:** phase verification for Phase 22, then `/gsd:complete-milestone` for v1.2.
Still open across the milestone, carried rather than dropped: 19-VALIDATION's **two
Manual-Only rows** (browser CSP enforcement on the live page, and a real provider
round-trip through `/health`) both need the manual deploy, and `REQ-health-credential-validity`
and `REQ-demo-csp-header` stay unchecked until it happens.

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
