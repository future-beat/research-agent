# research-agent

## What This Is

A supervisor-routed multi-agent research pipeline. Ask a question; it classifies the
topic, searches the web, drafts a report, then fact-checks that draft against its own
research notes and revises until every claim is grounded. It is packaged and operated as
a production service — bounded loops, per-run cost accounting, a spend cap, swappable
SQLite/Postgres+pgvector backends, an eval harness, and a test suite that runs with no
API keys.

Audience: employers evaluating the author's engineering judgement. A stranger should be
able to open the live URL, ask a question, watch the critic push back, and read a README
that explains why each piece is the way it is.

## Core Value

The pipeline never answers from model knowledge when it should be answering from
research — and it is demonstrable to a stranger in one click.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Deterministic supervisor routing over a classifier/researcher/writer/responder/critic graph — Phase 1
- ✓ Vector memory with a relevance floor, persisted across runs — Phase 2
- ✓ Follow-up conversations, pluggable stores, per-node retry with jittered backoff — Phase 3
- ✓ FastAPI service with blocking and SSE endpoints; sessions survive restart — Phase 4
- ✓ Date-aware cost accounting, spend cap as a routing rule, JSON logs, `/metrics` — Phase 5
- ✓ Twelve-case eval harness with deterministic graders plus an LLM judge — Phase 6
- ✓ Two-stage non-root Docker image, CI gates, Fly.io deploy — Phase 7
- ✓ Postgres and pgvector behind the existing interfaces, one shared contract suite — Phase 8
- ✓ Streaming demo page with rolling spend cap, per-visitor rate limit, optional token — Phase 9
- ✓ `src/` package layout and a single consolidated `pyproject.toml` — post-Phase-9 housekeeping

### Active

<!-- Current milestone (v1.1). All nine items from README "## Limitations". -->

- [ ] Load-bearing architectural decisions exist as numbered ADRs with explicit status
- [ ] Follow-ups can trigger new research instead of refusing (REQ-followup-live-search)
- [ ] The critic runs on a model independent of the writer (REQ-independent-critic-model)
- [ ] Answer quality is measurable; the live eval set outgrows smoke-test size (REQ-offline-eval-quality)
- [ ] Reported cost reflects discounts and `inference_geo`, not just list price (REQ-real-cost-accounting)
- [ ] Notes are bounded; sessions have owners and expiry (REQ-store-lifecycle-and-ownership)
- [ ] More than one machine runs, sharing state over `DATABASE_URL` (REQ-multi-machine-state)
- [ ] Postgres access is pooled (REQ-connection-pool)
- [ ] Changing embedding model has a real migration path (REQ-embedding-model-migration)
- [ ] The public demo identifies callers, not just rate-limits them (REQ-demo-authentication)

### Out of Scope

- LangGraph's checkpointer for session persistence — solves resuming a half-finished
  graph, a different feature with a different failure model; would couple the schema to
  LangGraph internals.
- An LLM router choosing the next hop — routing stays a deterministic Python state
  machine so it is unit-testable with no API keys.
- A one-model draft-and-self-assess node — "reliably produces 'looks good to me.'"
- Three separate backend flags instead of one `DATABASE_URL` — more configurable and
  worse; the real failure is setting one and forgetting another.
- An auth wall heavy enough that a stranger will not click through it — the demo's whole
  value is that it is one click from a résumé link.
- Any eval mechanism that bills money on every push, or that needs a live
  `ANTHROPIC_API_KEY` in CI.

## Context

- Live at `research-agent.fly.dev`; repo `github.com/future-beat/research-agent`; MIT.
- Stack: Python 3.10+ · LangGraph · Claude Sonnet 5 · Voyage embeddings · FastAPI ·
  SQLite/Postgres+pgvector. Deployed on Fly.io (app `research-agent`, region `syd`,
  1GB volume at `/data`).
- Phases 1–9 are complete and shipped. This milestone is net-new work, sourced entirely
  from the README's `## Limitations` list.
- The planning intel was ingested from three documents (`README.md`, `docs/DESIGN.md`,
  `docs/OPERATIONS.md`), all classified `DOC`. Twenty-three architectural decisions were
  recovered, **none locked** — zero ADRs existed at ingest. Phase 10 changes that for the
  load-bearing five.
- Six of the nine active requirements **reverse** a stated design position rather than fix
  a defect. See `.planning/intel/constraints.md`.
- Verified as of 2026-08-04: deploys are **manual** (`fly deploy -a research-agent`), not
  run through Fly's GitHub integration — `fly releases -a research-agent` shows 3 releases,
  all from the owner's personal account. `docs/OPERATIONS.md` says otherwise and is wrong.
- Verified as of 2026-08-04: the live release is 3 commits behind `main` (missing the
  README restructure, the `src/` reorganisation, and its bugfix). Functionally healthy —
  `/`, `/health`, `/demo`, `/metrics` all return 200 — but the deployed tree differs from `main`.
- War stories worth preserving in the docs: the unreachable revision cap the evals caught
  on run one; the `Decimal` that would have 500'd `/metrics`; the boot deadlock from eager
  DDL; the silent `internal_port` merge.

## Constraints

- **Deliverable definition**: "Done" means demonstrable to an employer — a live URL that
  works, green CI, a README a stranger can skim. Surface tidiness (commit history, deploy
  records, CI checks, root-level file count) is part of the deliverable, not cosmetic.
- **Tech stack**: Python, FastAPI, LangGraph, Claude, Voyage, Postgres/pgvector on Fly.io.
- **Architectural boundary**: `service.py` holds no routing logic. Any that did would mean
  the supervisor is no longer the single place deciding what runs next. This constrains
  where REQ-followup-live-search may be implemented.
- **CI**: every gate runs with `ANTHROPIC_API_KEY=""`. `ruff` · full test suite · offline
  eval cases · image build · container smoke test. The pgvector guard fails rather than
  skips. `main` is protected; force pushes and branch deletion blocked.
- **Deployment**: container listens on port 8000; never merge Fly's "New files from
  Fly.io Launch" PRs; always pass `-a` explicitly to `fly`; credentials never reach an
  image layer; the image installs `[service]` only and excludes `tests/` and `evals/`.
- **Pricing, time-sensitive**: Claude Sonnet 5 introductory pricing ($2/$10 per MTok) runs
  through 2026-08-31 and moves to $3/$15 on 2026-09-01. The effective-dated price table
  handles this at runtime; planning documents must not quote a single rate as if permanent.
  `/pricing` is the live source.
- **Reversals need replacement guarantees**: no reversal lands without stating what
  replaces the guarantee it removes, and which ADR it supersedes.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Routing is a deterministic Python state machine, never an LLM call | Control flow identical every run and testable with no API keys | ✓ Good |
| Critic is a separate node given notes as sole source of truth | One model drafting and self-assessing "reliably produces 'looks good to me'" | ✓ Good |
| Every loop bounded; forced stops reported honestly | A silent unapproved draft is worse than no draft | ✓ Good |
| Follow-ups stop with `no_prior_research` rather than answering from model knowledge | "The single failure mode this whole pipeline exists to prevent" | ⚠️ Revisit — REQ-followup-live-search reverses this |
| Spend cap is a routing rule, not a wrapper | One more row in the same routing table, same `forced_stop_reason` machinery | ✓ Good |
| Prices effective-dated; unpriced models report `pricing_unknown`, never zero | A cost control that fails open without saying so is worse than none | ✓ Good |
| Failed runs stay in the metrics denominator; zero-denominator rates return `null` | "No runs yet" and "nothing was approved" are different facts | ✓ Good |
| Sessions persist completed runs in SQLite, not LangGraph's checkpointer | Different feature, different failure model; avoids coupling schema to LangGraph | ✓ Good |
| One `DATABASE_URL` moves sessions, metrics, and notes together | The real failure is setting one flag and forgetting another | ✓ Good |
| Nothing constructed at import time; service boots degraded and self-heals | Eager DDL made `/health`'s degraded reporting unreachable by definition | ✓ Good |
| Eval judge on Opus 5 against a Sonnet 5 pipeline | The in-graph critic shares the writer's model, so a same-model judge inherits its blind spots | ⚠️ Revisit — premise falsified by REQ-independent-critic-model |
| Migration copies embeddings rather than re-embedding | Re-embedding would change recall at the same moment infrastructure changes — two suspects, no way to separate them | ⚠️ Revisit — tension with REQ-embedding-model-migration |
| Offline evals grade the pipeline only, with the caveat printed every run | "A green suite that quietly implies 'the model is good' is worse than no suite" | ⚠️ Revisit — tension with REQ-offline-eval-quality |
| Promote the load-bearing five decisions to numbered ADRs before any reversal lands | Six coming requirements reverse a stated position; each must supersede a record, not silently contradict prose | — Pending (Phase 10) |

---
*Last updated: 2026-08-04 after doc ingest and v1.1 roadmap creation*
