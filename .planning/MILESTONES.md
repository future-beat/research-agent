# Project Milestones: research-agent

Newest first. Full detail per milestone in `.planning/milestones/`.

---

## Since the v1.1 close (no milestone open)

**Phase 17.5 — Row level security on the public schema.** Landed 2026-08-12, after v1.1
was tagged, so it belongs to no milestone. A Supabase security-linter report flagged all
five `public` tables as RLS-disabled and exposed to the Data API. Measured against the real
DDL on a local stand-in, a role with the grants Supabase hands `anon` read session text and
identity hashes and **deleted every row of `runs`** — the daily spend cap's only input, so
an emptied ledger reads as $0 spent and the bill loses its bound.

Fixed in the schema constants rather than by an operator script, because
`migrate.py embeddings re-embed --to` creates tables on demand and a one-time fix would
miss them. Suite 737 → 739 keyless, 801 → 805 armed; three mutations observed red.

**Closed the same day, end to end.** Shipped in Fly release v13; the one-time `REVOKE` of
the `anon`/`authenticated` grants was run in the Supabase SQL editor and confirmed (all
five tables: `owner = postgres`, `rls_on = t`, `api_grants = (none)`). The provider's
linter went from six `ERROR` findings to five `INFO` `rls_enabled_no_policy` notices — the
correct end state, since a policy is the only way to grant access back and none should exist.

**One lesson outlives the phase:** the `REVOKE` as first published was wrong in the way that
fails silently — a bare `ALTER DEFAULT PRIVILEGES` governs only the role that runs it, so it
would have looked like it worked while protecting no future table. Caught by testing the
script against a stand-in rather than by reading it again.

**Sonnet 5 pricing became permanent, 2026-08-12.** Anthropic made the $2/$10 per MTok
introductory rate the standing price and cancelled the $3/$15 rise scheduled for
2026-09-01. The price table collapsed to a single open-ended window — a data edit, which
is exactly what the effective-dating design existed to absorb. The subtler half was the
tests: six boundary tests used Sonnet 5's two windows as their subject, so removing the
second window would have left `window_for` only ever returning `(None, None)` and
`next_window` only ever `None`. They moved onto a synthetic two-window table declared in
the test file and labelled as such, and two mutations confirm it earns its place — both
pass silently without it. **This removes the project's last dated obligation**: the
reservation threshold and the "record the evals before the price rises" argument expired
with it. Verified against the published pricing, not the announcement alone.

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
- Tests **364 → 737** passing with no API keys (**801** with Postgres armed); offline evals 12 → **41** cases
  *(baseline corrected at the v1.0 remaster, 2026-08-12: this line previously opened at 436, which does not
  reproduce from `5c01b3e` — the closing v1.0 suite re-runs at 364 passed / 28 skipped keyless)*
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

## v1.0 Production pipeline (Shipped: pre-GSD, closing commit `5c01b3e` 2026-08-02)

**Delivered:** A supervisor-routed multi-agent research pipeline, packaged and operated as a
production service — live at `research-agent.fly.dev`.

**Phases completed:** 1–9, plus the 9.1 package reorganisation. Pre-GSD: no plan artifacts
existed at execution time. **Record remastered 2026-08-12** — per-phase SUMMARY and
retroactive VALIDATION files under `.planning/milestones/v1.0-phases/`, each labeled
reconstructed, with the closing suite re-measured (364 passed / 28 skipped keyless).

**Archive:** [`v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md) ·
[`v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md)

**Stats:** 23 commits · 5 days (2026-07-29 → 2026-08-02) · 44 files, 10,317 insertions ·
tests 0 → 364 keyless · Fly releases v1 → v3

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
