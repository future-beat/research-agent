---
phase: 8
slug: stateless
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 8 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-01).
> Criteria reconstructed at remaster; measurements against the 2026-08-12 tree
> (737 passed / 65 skipped keyless; 801 with Postgres armed).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| Every backend passes the same behavioural contract | `tests/test_store_contract.py` | **102 collected**, four arms (json, memory, chroma, pgvector) |
| Both metrics backends produce byte-identical summaries from identical input | contract suite (DEC-16) | Pinned; the assertion survived Phase 11's pooling cutover, which was one of its stated gates |
| The service boots with the database unreachable and reports degraded, not dead | `tests/test_service.py` health/readiness cases (from `97449af`) | Liveness always 200; readiness 503 when a store is down |
| No DDL at construction time | `tests/test_db.py` + DEC-18 pins | **37 collected** |
| A missing CI database fails the pgvector arm rather than skipping it | CI guard | Standing; stated in README's test section |

## What execution-time verification actually was

The contract suite, same-commit (452 lines), plus a live production shakeout the same
night — the liveness/readiness split and the boot-deadlock fix (`97449af`) were written
against a real symptom on Fly, not a hypothesis. This phase's verification record *is*
those follow-up commits.

## Honest gaps

- `migrate_to_postgres.py` shipped with no tests. Phase 13 found a live owner/TTL
  data-loss bug in exactly that path and covered it. Phase 11's production cutover
  then deliberately did **not** exercise it (empty database, volume kept as backup),
  so the legacy migration remained an unproven path — recorded as such in 11's
  criteria amendment.
- Multi-machine resolution was *enabled* here (shared Postgres) but not *true* until
  Phase 11 — v1.0 production kept SQLite on a single machine with a volume, and the
  v1.0 README listed exactly that as a limitation.
- One connection per machine, lock-guarded, was a measured-for-scope choice, reversed
  in Phase 11 with the reasoning recorded (pooling is only correct alongside raised
  concurrency).
