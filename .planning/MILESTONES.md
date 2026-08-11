# Project Milestones: research-agent

Newest first. Full detail per milestone in `.planning/milestones/`.

---

## v1.1 Closing the limitations list (Shipped: 2026-08-11)

**Delivered:** All nine limitations the v1.0 README listed are closed — six of them by
deliberately reversing a design position, each superseding a numbered ADR rather than quietly
contradicting prose.

**Phases completed:** 10–17, plus the inserted 10.5 (43 plans, ~118 tasks)

**Key accomplishments:**

- **Nine limitations closed, six as recorded reversals.** The milestone opened by promoting the
  five load-bearing decisions to numbered ADRs so every later reversal had a record to supersede.
  `docs/adr/` went 0 → 11, three superseded, and the register of *expected* reversals is now spent.
- **A live security exposure found and closed the same day.** Codebase mapping — not the
  requirements list — found four session routes reachable by anyone. Confirmed against production
  by reading real sessions and deleting two over plain `curl`. Fly v4, phase 10.5.
- **The service became genuinely multi-tenant without a signup wall.** An auto-issued signed
  `HttpOnly` cookie, minted on the response by pure-ASGI middleware; sessions and notes own and
  expire; rate limits key on identity; the spend cap reserves against in-flight runs inside a
  `pg_advisory_xact_lock`, closing a ~3× overshoot. A stranger from a résumé link still reaches a
  working demo in one click.
- **The two hardest reversals landed with their replacement guarantees stated.** The critic runs
  on a *more capable* model than the writer it gates (Opus 5 over Sonnet 5), and the eval judge's
  rationale was re-derived rather than inherited. A follow-up whose notes cannot answer now
  researches instead of refusing — and grounding survived, because it never meant "no new search";
  it meant the answer comes only from notes the critic reviewed.
- **Measurement replaced assertion, repeatedly.** Voyage embedding spend is counted for the first
  time; `inference_geo` turned out to be response-observed rather than an env declaration, and the
  design improved for it; the admission reservation was resized on two live runs rather than an
  estimate; answer quality is graded from *recorded* runs that go stale on purpose.

**The recurring defect, recorded because it shaped the milestone:** sixteen-plus **vacuous gates**
across seven phases — gates that pass on the unchanged tree. Phase 12 found the deeper form: a
*structurally sensible* gate blind to the exact mutation it exists to catch. The discipline that
grew against it — mutate every gate and observe it red before trusting it — ran 10–15 probes
against plans naming three, and twice a probe *passed and the probe itself was wrong*, and was
re-targeted rather than banked.

**Stats:**

- 187 files created/modified · 56,420 insertions / 575 deletions (49 files and 18,013 insertions
  outside `.planning/`)
- ~24,000 lines of Python across `src/`, `tests/`, `evals/`
- 9 phases · 43 plans · ~118 tasks
- Tests 436 → **737** passing with no API keys (**801** with Postgres armed); offline evals 12 → **41** cases
- 251 commits · 8 days (2026-08-04 → 2026-08-11)
- Fly releases **v4 → v12**; 9 merged PRs (#4–#17)

**Git range:** `5c01b3e` (pre-GSD) → `e8d4301` (PR #17 merged)

**Audit:** [`v1.1-MILESTONE-AUDIT.md`](v1.1-MILESTONE-AUDIT.md) — 11/11 requirements satisfied on
live or gated evidence, 8/8 connections wired, 4/4 E2E flows complete. Returned `tech_debt` on two
findings and one process gap; the findings were fixed (a completed run could be lost from the cost
ledger; the reservation's arithmetic was stale) and the nine VALIDATION contracts reconciled.

**Known deferred items at close:** the full 40-case eval record run (~$16.51); `/health` checks
that API keys are present, not valid; no CSP header on the demo page; the `DATABASE_URL` rollback
path documented but never exercised; and **no phase carries a `VERIFICATION.md`** — left open
deliberately, since writing them after the fact would record a step that did not happen.

**What's next:** No milestone defined. `/gsd:new-milestone` starts the questioning → research →
requirements → roadmap chain. The dated item on the horizon is **2026-09-01**, when Sonnet 5's
introductory pricing window closes.

---

## v1.0 Production pipeline (Shipped: pre-GSD)

**Delivered:** A supervisor-routed multi-agent research pipeline, packaged and operated as a
production service — live at `research-agent.fly.dev`.

**Phases completed:** 1–9, plus post-Phase-9 package reorganisation (pre-GSD; no plan artifacts)

**Key accomplishments:**

- Deterministic supervisor routing over a classifier/researcher/writer/critic graph — control flow
  is a function of state, never an LLM's choice, so it is unit-testable with no API keys.
- A separate critic node given research notes as the sole source of truth, with a bounded revision
  loop and honest forced stops.
- Vector memory with a relevance floor; FastAPI with blocking and SSE; date-aware cost accounting
  with the spend cap as a routing rule; Postgres and pgvector behind the existing interfaces.
- A twelve-case eval harness that found a real bug — an unreachable revision cap — on its first run.
- Two-stage non-root Docker image, CI gates that run with `ANTHROPIC_API_KEY=""`, Fly.io deploy.

**What's next:** v1.1 — closing the limitations list.

---
