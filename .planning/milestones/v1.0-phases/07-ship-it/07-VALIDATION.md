---
phase: 7
slug: ship-it
status: complete
retroactive: true
remastered: 2026-08-12
nyquist_compliant: true # measured against the 2026-08-12 tree; no contract existed at execution time
---

# Phase 7 — Validation (retroactive)

> **Remastered record.** No validation contract existed at execution time (2026-08-01).
> Criteria reconstructed at remaster; measurements against the 2026-08-12 tree
> (737 passed / 65 skipped keyless).

## Criteria → evidence, measured 2026-08-12

| Criterion (reconstructed) | Where enforced today | Measured |
|---|---|---|
| The image builds, runs non-root, and answers its healthcheck | CI's image-build + container smoke gates | Green on `main`; the CI badge is the README's first line |
| Every CI gate runs with `ANTHROPIC_API_KEY=""` | `.github/workflows/ci.yml` | Invariant held through v1.1 (a stated Phase 15 constraint) |
| The image contains the service and not the tests or eval dataset | Dockerfile install target (`[service]` since Phase 9.1) + `.dockerignore` | Structural |
| Deploy config is guarded, not assumed | `tests/test_deploy_config.py` (begun Phase 9, grown through Phase 11) | **13 collected** |

## What execution-time verification actually was

CI itself — this phase built the machine that verified every later phase. Its own
verification was the first green run of that machine, plus the container smoke test
proving the image boots and serves.

## Honest gaps

- The deploy *pipeline* was the least settled part: a CI-gated deploy workflow was
  added (`b346796`) and then dropped for Fly's GitHub integration (`9ebee6b`) during
  the Phase 8 cutover work — and by v1.1's ingest, deploys were verifiably **manual**
  while `docs/OPERATIONS.md` still claimed the integration. Phase 10 corrected the
  docs to the measured truth (`fly releases` showed 3 releases, all from the owner's
  account). The lesson entered the project's working style: a doc's deploy claim is a
  claim to check.
- Python version drift: the phase pinned 3.10+; CI and the image run 3.14 today. The
  README's stack line tracks the measured value.
