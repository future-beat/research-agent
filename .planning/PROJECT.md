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

## Current State

**Shipped: v1.1 "Closing the limitations list"** — 2026-08-11, Fly release **v12**, two machines
in `syd` against Supabase Postgres. Live at `research-agent.fly.dev`.

All nine limitations the v1.0 README listed are closed. Six were deliberate reversals, each
superseding a numbered ADR rather than quietly contradicting prose — the reversal register the
milestone opened with is now spent. `docs/adr/` holds 11 records, three of them superseded.

737 tests pass with no API keys; 801 with Postgres armed. Offline evals grade 41 cases keylessly
on every push, including one real recorded answer.

**What is true now that was not at v1.0:** a stranger from a résumé link gets an auto-issued
signed identity with no signup; sessions and notes belong to that caller and expire; the spend
cap reserves against in-flight runs across both machines; the critic runs on a *more capable*
model than the writer it gates; a follow-up whose notes cannot answer goes and researches
instead of refusing; and reported cost is an approximation of the invoice rather than of the
list price, with Voyage embedding spend counted for the first time.

## Next Milestone Goals

**None defined.** `/gsd:new-milestone` starts the questioning → research → requirements →
roadmap chain. Carried forward as open items rather than requirements:

- The full 40-case eval record run (**~$16.51, and no longer time-sensitive** — the ~$21
  figure assumed the 2026-09-01 Sonnet 5 price rise, which was cancelled on 2026-08-12).
  Machinery proven by one paid calibration case; recording the rest is an operator decision,
  and the deadline that was the only argument for doing it sooner is gone.
- `/health` checks that API keys are *present*, not that they work — it stayed green through a
  full revoked-key outage. Now listed in the README's Limitations.
- No phase carries a `VERIFICATION.md`. The audit's P1, left open deliberately: writing them
  after the fact would record a verification step that did not happen.
- No CSP header on the demo page; `run_finished` carries no `session_id`; the `DATABASE_URL`
  rollback path is documented but never exercised.
- ~~**2026-09-01** closes Sonnet 5's introductory pricing window~~ — **cancelled 2026-08-12**:
  $2/$10 per MTok is permanent, so no run gets a third more expensive and
  `DEMO_RESERVED_RUN_USD` stays $0.30. **The project now has no dated obligation at all.**

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

<!-- v1.1 — all nine README limitations, plus two found during planning. -->

- ✓ Load-bearing architectural decisions exist as numbered ADRs with explicit status — Phase 10
- ✓ The session read/delete routes are not reachable without credentials **on the deployed service** — Phase 10.5 *(found by codebase mapping, never in the Limitations list)*
- ✓ More than one machine runs, sharing state over `DATABASE_URL` — Phase 11
- ✓ Postgres access is pooled — Phase 11
- ✓ The public demo identifies callers, not just rate-limits them — Phase 12 *(as an auto-issued **anonymous** identity: an auth wall a stranger will not click through destroys the demo's value)*
- ✓ Notes are bounded; sessions have owners and expiry — Phase 12
- ✓ Changing embedding model has a real migration path — Phase 13 *(two commands, not one: copy and re-embed answer different questions)*
- ✓ Reported cost reflects discounts and `inference_geo`, not just list price — Phase 14 *(geo turned out to be response-observed, not an env declaration)*
- ✓ Answer quality is measurable; the live eval set outgrows smoke-test size — Phase 15 *(1 of 40 answers recorded; the rest a priced, explicit deferral)*
- ✓ The critic runs on a model independent of the writer — Phase 16 *(and more capable than it)*
- ✓ Follow-ups can trigger new research instead of refusing — Phase 17

### Active

<!-- No milestone defined. Run /gsd:new-milestone. -->

_None. v1.1 closed 2026-08-11._

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
- Stack: Python 3.14 (CI and image) · LangGraph · Claude Sonnet 5 with an **Opus 5 critic** · Voyage embeddings · FastAPI ·
  SQLite/Postgres+pgvector. Deployed on Fly.io (app `research-agent`, region `syd`,
  1GB volume at `/data`).
- Phases 1–9 shipped v1.0; phases 10–17 shipped v1.1, sourced entirely from the README's
  `## Limitations` list. Both are archived under `.planning/milestones/`.
- The planning intel was ingested from three documents (`README.md`, `docs/DESIGN.md`,
  `docs/OPERATIONS.md`), all classified `DOC`. Twenty-three architectural decisions were
  recovered, **none locked** — zero ADRs existed at ingest. Phase 10 changes that for the
  load-bearing five.
- Six of the nine active requirements **reverse** a stated design position rather than fix
  a defect. See `.planning/intel/constraints.md`.
- Deploys are **manual** (`fly deploy -a research-agent`); a merge to `main` ships
  nothing. Verified 2026-08-04, re-measured 2026-08-12: auto-deploy on push was enabled
  that day, three green merges (PRs #19, #20, #21) produced **no release** while a
  hand-run deploy produced v13 at once, and the setting was **switched back off** the same
  day. This project has already shipped one false deploy claim in its docs and the
  correction cost Phase 10 a plan, so the rule stands regardless of settings: confirm with
  `fly releases`, never infer from a merge.
- The drift Phase 10 existed to remove: deploys now run from merged `main` only, and every
  release since v4 is recorded in its phase SUMMARY with the evidence it was verified by.
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
- **Pricing, no longer time-sensitive**: Claude Sonnet 5 is **$2/$10 per MTok permanently**
  — the scheduled 2026-09-01 rise to $3/$15 was cancelled on 2026-08-12. The effective-dated
  price table still resolves by date and still must: the constraint was never "this one rate
  expires", it is that a rate can change on a date somebody else picks. Planning documents
  should keep citing `/pricing` as the live source rather than quoting a rate inline.
  `/pricing` is the live source.
- **Reversals need replacement guarantees**: no reversal lands without stating what
  replaces the guarantee it removes, and which ADR it supersedes.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Routing is a deterministic Python state machine, never an LLM call | Control flow identical every run and testable with no API keys | ✓ Good |
| Critic is a separate node given notes as sole source of truth | One model drafting and self-assessing "reliably produces 'looks good to me'" | ✓ Good |
| Every loop bounded; forced stops reported honestly | A silent unapproved draft is worse than no draft | ✓ Good |
| ~~Follow-ups stop with `no_prior_research`~~ → an unsupported follow-up **researches**, one pass | Grounding was never "no new search" — it is "no answer from parametric knowledge", and refusing to search was the enforcement, not the guarantee | ✗ Reversed — [ADR-0011](../docs/adr/0011-followups-reach-for-new-information.md) supersedes 0003 |
| Spend cap is a routing rule, not a wrapper | One more row in the same routing table, same `forced_stop_reason` machinery | ✓ Good |
| Prices effective-dated; unpriced models report `pricing_unknown`, never zero | A cost control that fails open without saying so is worse than none | ✓ Good |
| Failed runs stay in the metrics denominator; zero-denominator rates return `null` | "No runs yet" and "nothing was approved" are different facts | ✓ Good |
| Sessions persist completed runs in SQLite, not LangGraph's checkpointer | Different feature, different failure model; avoids coupling schema to LangGraph | ✓ Good |
| One `DATABASE_URL` moves sessions, metrics, and notes together | The real failure is setting one flag and forgetting another | ✓ Good |
| Nothing constructed at import time; service boots degraded and self-heals | Eager DDL made `/health`'s degraded reporting unreachable by definition | ✓ Good |
| Eval judge on Opus 5 — **rationale re-derived, not inherited** | The old reason (a weak critic) died with the independent critic. The judge survives on a different job: it grades finished answers against a rubric, retrospectively. Judge == critic is recorded as an **acceptance**, not an oversight | ✓ Good — [ADR-0010](../docs/adr/0010-judge-rederived-for-an-independent-critic.md) supersedes 0005 |
| Migration is **two** commands: copy *or* re-embed | The original reason survives and became the copy leg's guarantee; re-embed is a separate, measured act with its cost quoted first | ✓ Good — [ADR-0008](../docs/adr/0008-embedding-migration-two-commands.md) |
| Offline evals also grade **recorded** answers, and never claim them of the current model | The caveat did not weaken — it got more specific: a replay reports what the pipeline said on a stated date, model and commit, and goes stale on purpose | ✓ Good — [ADR-0009](../docs/adr/0009-recorded-answer-quality-evals.md) |
| Promote the load-bearing five decisions to numbered ADRs before any reversal lands | Six coming requirements reverse a stated position; each must supersede a record, not silently contradict prose | ✓ Good — the milestone's best structural call; 11 records now, 3 superseded |
| The critic runs on a **more capable** model than the writer it gates | The user's own position, quoted verbatim in ADR-0010; it inverts the old rationale, which justified a strong judge by a weak critic | ✓ Good — Fly v10, ~12% of a run's cost |
| Fairness keys on an auto-issued anonymous identity; the global cap bounds the bill | Identities are free to mint, so per-caller limits buy fairness, not a bound — and a signup wall would cost more than it buys | ✓ Good — [ADR-0007](../docs/adr/0007-anonymous-identity-fairness-global-cap.md) supersedes 0006 |
| The admission reservation is sized on **measurement**, not estimate | Two live runs put a typical run above the $0.20 estimate; the docstring's own rule already named $0.30 | ✓ Good — raised at the v1.1 audit |

---
*Last updated: 2026-08-11 at v1.1 milestone close (Fly release v12)*
