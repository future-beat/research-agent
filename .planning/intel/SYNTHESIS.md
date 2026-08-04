# Synthesis

Entry point for downstream consumers (`gsd-roadmapper`). Ingest mode: `new`.
Ingest date: 2026-08-04.

Project: supervisor-routed multi-agent research pipeline (LangGraph + Claude
Sonnet 5), live at research-agent.fly.dev, repo github.com/future-beat/research-agent, MIT.

---

## Docs ingested (3)

| type | count | sources |
|---|---|---|
| ADR | 0 | — |
| SPEC | 0 | — |
| PRD | 0 | — |
| DOC | 3 | `README.md`, `docs/DESIGN.md`, `docs/OPERATIONS.md` |

All three classified `DOC` at `medium` confidence. No manifest overrides, no
per-doc precedence overrides, no UNKNOWN or low-confidence classifications.

## Decisions — 23 captured, 0 LOCKED

**Every decision is soft / revisable.** Zero ADRs in the ingest set, so nothing
is locked and nothing can block a downstream override. Twenty-two of the 23 come
from the `decision_candidates` array the `docs/DESIGN.md` classifier emitted as a
non-schema field — carried deliberately, because that array is this project's
real architectural record even though the document classifies as DOC.

Headline decisions: routing is a deterministic Python state machine, never an LLM
call (DEC-01); the critic is a separate node given the notes as sole source of
truth (DEC-02); all loops bounded with forced stops reported honestly (DEC-03);
follow-ups reuse the critic and stop with `no_prior_research` rather than answer
from model knowledge (DEC-04); the spend cap is a routing rule, not a wrapper
(DEC-11); prices are effective-dated and unpriced models report `pricing_unknown`
rather than zero (DEC-12); failed runs stay in the metrics denominator (DEC-13);
sessions store completed runs in SQLite, deliberately not LangGraph's checkpointer
(DEC-14); one `DATABASE_URL` moves all three stores (DEC-15); nothing is
constructed at import time so the service boots degraded and self-heals (DEC-18);
the eval judge runs on Opus 5 against a Sonnet 5 pipeline (DEC-22).

→ `decisions.md`

## Requirements — 9 extracted

All nine derive from `README.md` → `## Limitations`, which frames them as
deliberate trade-offs rather than defects. The owner has decided to take on all
nine in the next milestone.

- `REQ-followup-live-search` — follow-ups can trigger new research
- `REQ-independent-critic-model` — critic no longer shares the writer's model
- `REQ-offline-eval-quality` — answer quality becomes measurable; live set grows past 12
- `REQ-real-cost-accounting` — discounts and `inference_geo` in cost figures
- `REQ-store-lifecycle-and-ownership` — bounded note growth; session owners and expiry
- `REQ-multi-machine-state` — take the `DATABASE_URL` path; run more than one machine
- `REQ-connection-pool` — pooled Postgres access
- `REQ-embedding-model-migration` — a real path when embedding model/dimension changes
- `REQ-demo-authentication` — the public demo identifies callers

Acceptance criteria in `requirements.md` are synthesis proposals, not user-ratified.

→ `requirements.md`

## Constraints

Lifted from `docs/OPERATIONS.md`, which classified DOC — its two contract tables
document existing defaults rather than mandating them, so nothing is a ratified
SLO or API contract. Breakdown: deployment invariants (9), CI invariants (5),
configuration defaults (6 groups), one time-sensitive pricing constraint, one
architectural boundary (`service.py` holds no routing logic).

**Also in `constraints.md`, and the most important thing on that page:** six of
the nine requirements reverse a stated design position rather than fix a bug.
The two most design-reversing are `REQ-followup-live-search` (README marks the
current behaviour "By design"; DESIGN.md calls the guarantee it removes "the
single failure mode this whole pipeline exists to prevent") and
`REQ-independent-critic-model` (removes the stated premise for the stronger eval
judge). Four lower-stakes reversals: embedding re-migration, offline eval
quality, demo auth, connection pooling. Three are not reversals at all:
multi-machine state, real cost accounting, store lifecycle.

→ `constraints.md`

## Context — 7 topics

Project identity; phase status (1-9 all complete, nothing in flight); graph
topology and the full supervisor routing table; API surface; testing posture;
four war stories worth preserving (the unreachable revision cap the evals caught
on run one, the `Decimal` that would have 500'd `/metrics`, the boot deadlock
from eager DDL, the silent `internal_port` merge); ingest provenance.

→ `context.md`

## Conflicts — 0 blockers, 3 warnings, 6 info

**BLOCKERS (0).** No LOCKED decisions exist, so no LOCKED-vs-LOCKED contradiction
is possible. No cycle blocker (the README↔DESIGN↔OPERATIONS cycle is
navigational, not derivational — see the report). No low-confidence docs.

**WARNINGS (3) — user input required before routing:**
1. Deploy gating disputed. `docs/OPERATIONS.md` says deploys run through Fly's
   GitHub integration and are NOT CI-gated; the owner's working understanding is
   manual `fly deploy`. Repo evidence (commit 9ebee6b deleting
   `.github/workflows/deploy.yml`) supports the doc, but the deciding state lives
   in Fly's dashboard, outside the repo. Not resolved by guessing.
2. Six requirements reverse argued design decisions — confirm each explicitly.
3. Twenty-three decisions sit at DOC precedence with none locked; recommend
   promoting the load-bearing ones to numbered ADRs.

**INFO (6):** README's critic-vs-judge model claim verified true against
`src/research_agent/graph.py:38` (single `MODEL = "claude-sonnet-5"`) and
`evals/graders.py:28` (`JUDGE_MODEL` default `claude-opus-5"`); navigational
cross-ref cycle not gated; stale three-vs-four backend count in DESIGN.md; no
competing acceptance variants; Sonnet 5 introductory pricing expires 2026-08-31
(27 days from ingest); no open roadmap items inherited.

→ `../INGEST-CONFLICTS.md`

## Files

- `.planning/intel/decisions.md`
- `.planning/intel/requirements.md`
- `.planning/intel/constraints.md`
- `.planning/intel/context.md`
- `.planning/INGEST-CONFLICTS.md`

## Status

**AWAITING USER** — 3 warnings need resolution before routing. No blockers.
