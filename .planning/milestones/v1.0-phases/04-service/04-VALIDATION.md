---
phase: 4
slug: service
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 4 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-01).
> Criteria reconstructed at remaster; measurements against the 2026-08-12 tree
> (737 passed / 65 skipped keyless).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| Blocking and SSE routes drive the real graph through the real app | `tests/test_service.py` (FastAPI `TestClient`, real app, stubbed model client) | **128 collected** |
| A stream emits exactly one terminal event, including on mid-run failure | SSE tests in `test_service.py` | Covered; the error detail's *redaction* is additionally pinned since Phase 10.5 |
| Sessions survive a restart; a follow-up resolves its session from storage | `tests/test_sessions.py` + service-level follow-up tests | **14** + service coverage |
| `service.py` holds no routing logic | structural constraint, re-verified by Phase 17's review | Constraint held through the deepest routing change in v1.1 |

## What execution-time verification actually was

The suite, from the same commit: 562 test lines against the real FastAPI app — the
project's stated testing position ("SQLite, Postgres and the FastAPI app are real,
because persistence and routing are what would be worth faking least") dates from here.

## Honest gaps

- **The session routes had no auth and no test asserting they should.** Every service
  test exercised them anonymously as if that were the contract — and it was, until
  v1.1's codebase mapping read them as an exposure, confirmed it against production
  (real sessions read, two deleted over plain `curl`), and Phase 10.5 closed it. The
  guard invariant that now exists (a sessions route cannot go anonymous; the walker is
  recursive and asserts a route count first) is exactly the test this phase should have
  had.
- Durable-session behaviour was tested against SQLite only; the cross-backend
  contract arrived with Phase 8, and cross-*machine* resolution only became true (and
  tested) in Phase 11.
