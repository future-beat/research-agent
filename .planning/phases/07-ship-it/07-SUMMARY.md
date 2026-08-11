---
phase: 7
slug: ship-it
milestone: v1.0
status: complete
executed: 2026-08-01
remastered: 2026-08-12
---

# Phase 7: Ship it — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** The service builds to an image, passes CI gates, and deploys.

**Shipped in:** `b6d8649` (2026-08-01) — `Dockerfile` (74 lines, two-stage),
`.github/workflows/ci.yml` (129), `docker-compose.yml`, `fly.toml`, `ruff.toml`, and the
requirements split (`requirements.txt` / `-service` / `-dev`) that Phase 9.1 later
consolidated into extras.

## What shipped

- **A two-stage, non-root, healthchecked image.** Build deps stay in the builder;
  the runtime image installs the service requirements only and excludes `tests/` and
  `evals/` — "the eval dataset contains scripted model output, which has no business
  inside a production image" (the position later recorded as DEC-23).
- **CI that runs everything keyless.** Lint (`ruff`), the full test suite, the offline
  eval cases, an image build, and a container smoke test — all with
  `ANTHROPIC_API_KEY=""`. That invariant (every gate keyless) became a standing project
  constraint, load-bearing for Phase 15's design: whatever answer-quality mechanism
  landed, it was not allowed to break this.
- **Deploy configuration** (`fly.toml`) — the target the Phase 8 follow-up commits made
  real when the service first went live on Fly.

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| Split dependencies so the image installs only what it runs | Consolidated by Phase 9.1 into `pyproject.toml` extras (`[service]`, `[dev]`) — the decision survived, its mechanism improved |
| Keyless CI as the only CI | Never reversed; every v1.1 phase measured its suite counts against it, and the pgvector guard *fails* rather than skips when the database is missing |
| A container smoke test in CI | Never reversed; it caught the Phase 9.1 reorganisation bugs (`5c01b3e`) the same day |

## Where it lives today

`Dockerfile`, `.github/workflows/ci.yml`, `docker-compose.yml`, `fly.toml` — all still
the shipping path. The CI keyless invariant is stated in PROJECT.md's constraints;
deploys are **manual** (`fly deploy -a research-agent`), a fact Phase 10 established
against the docs' earlier claim of GitHub-integration deploys.
