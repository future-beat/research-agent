---
phase: 9
slug: demo-and-guardrails
milestone: v1.0
status: complete
executed: 2026-08-02
remastered: 2026-08-12
---

# Phase 9: Demo & guardrails — Summary

> **Remastered record.** Phases 1–9 predate GSD — no CONTEXT, PLAN, or execution artifact
> existed at the time. Reconstructed 2026-08-12 from the phase's commits, the README as the
> phase left it, and the design rationale later ingested as DEC-01…DEC-23
> (`.planning/intel/decisions.md`). It records what shipped and why; it does not claim any
> GSD step ran.

**Goal:** A stranger can use the live demo without it being abusable.

**Shipped in:** `9568ec5` (2026-08-02) — `limits.py` (230 lines), the streaming demo
page (`static/index.html`, 367 lines), `test_limits.py` (291), `test_deploy_config.py`,
and the service wiring.

## What shipped

- **The demo page.** A browser front-end over the SSE stream: ask a question, watch
  the node events arrive, watch the critic push back. This is the project's thesis made
  visible — the deliverable was always "demonstrable to a stranger in one click," and
  this page is where that became literally true.
- **A rolling daily spend cap** — the service-level backstop over the per-run budget
  (Phase 5's cap bounds a run; this bounds the day).
- **A per-visitor rate limit** keyed on visitor IP, with `TRUST_FORWARDED_FOR`
  governing what "visitor" means behind a proxy.
- **An optional `DEMO_TOKEN`** — set, it gates the research routes; unset, the demo is
  open and the guardrails are the protection. The scope position, stated in the README
  it shipped with: "rate-limited, not authenticated. Guardrails bound the spend; they
  don't identify callers."

## Decisions made here and their fate

| Decision | Fate |
|---|---|
| Guardrails, not identity | A deliberate scope call, named a limitation at ship — **reversed by Phase 12**: an auto-issued signed `HttpOnly` cookie (no signup, no wall), limits keyed on identity, and the insight that identities free to mint buy *fairness* while only the global cap bounds the *bill* ([ADR-0007](../../../docs/adr/0007-anonymous-identity-fairness-global-cap.md)) |
| Rolling daily cap as the abuse backstop | Never reversed; Phase 12 made it reservation-based inside a `pg_advisory_xact_lock`, closing a ~3× concurrency overshoot, and the v1.1 audit resized the reservation on measurement ($0.20 → $0.30) |
| `DEMO_TOKEN` as the only credential | Superseded twice: Phase 10.5's `SESSIONS_TOKEN` (fail-closed, because production `DEMO_TOKEN` must stay unset or it kills the anonymous demo), then Phase 12's identity. `DEMO_TOKEN` survives as the operator's cross-owner view |
| The demo page itself | Rewritten identity-aware in Phase 12; still the first thing a résumé link reaches |

## Where it lives today

`src/research_agent/limits.py`, `static/index.html` (under `src/research_agent/` since
Phase 9.1). Tests measured 2026-08-12: `test_limits.py` **57**, `test_deploy_config.py`
**13** collected. With this phase, v1.0 was complete as a product: live URL, working
demo, guardrails — Fly releases v1–v3.
