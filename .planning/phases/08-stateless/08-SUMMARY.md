---
phase: 8
slug: stateless
milestone: v1.0
status: complete
executed: 2026-08-01
remastered: 2026-08-12
---

# Phase 8: Stateless — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** Sessions, metrics, and notes can live in Postgres/pgvector behind the same
interfaces.

**Shipped in:** `0741c61` (2026-08-01) — `db.py` (132 lines), Postgres session and
metrics backends, the pgvector store, `migrate_to_postgres.py` (176), and
`test_store_contract.py` (452 lines). Followed the same night by the first Fly
deployment and its hard-won fixes: `ee10cb8` (CI), `97449af` (liveness split from
readiness; boot without the database), `2382b22` (region `syd`; never merge Fly's
config PRs), and the deploy-workflow experiments (`b346796` → `9ebee6b`).

## What shipped

- **One `DATABASE_URL` moves sessions, metrics, and notes together** (DEC-15). All
  three stores default to Postgres when it is present, local disk when it isn't; any
  one can still be pinned explicitly. Three separate backend flags were rejected as
  "more configurable and worse: the failure you'd actually hit is setting one and
  forgetting another" — a deployment that degrades only as slowly worsening answers.
- **pgvector/HNSW replaces the O(n) scan** (DEC-09) — same cosine ranking, no
  whole-corpus pull into the agent process, and being shared, every machine recalls
  everything the agent learned.
- **"Swappable" enforced, not asserted** (DEC-16). Behavioural tests live in one file
  and run against every backend, and one test asserts both metrics backends produce
  **byte-identical** summaries from identical input. It caught real dialect traps:
  SQLite sums booleans where Postgres needs `COUNT(*) FILTER`, and Postgres returns
  `SUM(BIGINT)` as `Decimal` — not JSON-serialisable, and it would have 500'd
  `/metrics` on the first recorded run.
- **Nothing constructed at import time** (DEC-18, hardened in `97449af`). API clients
  build on first use; Postgres stores *register* schema and apply it on first use.
  Eager DDL meant an unreachable database stopped the service *booting* — making
  `/health`'s degraded-dependency reporting unreachable by definition, and against a
  provider that pauses idle instances, a deadlock no restart could break.
- **The first production deploy.** Fly app `research-agent`, region `syd`, releases
  v1–v3 belong to this era. The "silent `internal_port` merge" war story dates here:
  Fly's auto-generated config PRs were documented as never-merge (`2382b22`).

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| DEC-15 one `DATABASE_URL` | Never reversed; Phase 11 executed its documented multi-machine path (two machines over Supabase Postgres) |
| DEC-16 contract suite + byte-identical assertion | Never reversed; grew to four arms and ownership/TTL semantics in Phase 12 |
| DEC-18 lazy construction, boot degraded | Never reversed; Phase 11's pool disposal and `/health` bounds build on it |
| Single lock-guarded Postgres connection | Stated at the time as right "when a run occupies a worker for tens of seconds"; **reversed by Phase 11** (psycopg-pool, one pool per DSN) alongside the concurrency raise that justified it |
| `migrate_to_postgres.py` shipped untested | The debt surfaced in Phase 13, which found a live owner/TTL data-loss bug in it and gave the legacy path its first tests |

## Where it lives today

`src/research_agent/db.py`, the backends inside `sessions.py` / `metrics.py` /
`memory.py`, and `migrate.py`. Tests measured 2026-08-12: `test_store_contract.py`
**102**, `test_db.py` **37**, `test_sessions.py` **14**, `test_metrics.py` **21**
collected; the Postgres arms are among the 65 keyless skips locally and run armed in CI
(801 total) — the pgvector guard *fails* rather than skips when the database is missing.
