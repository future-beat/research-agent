---
phase: 12
slug: caller-identity-session-ownership-bounded-stores
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

The milestone's most user-visible phase and its fourth design reversal. Three claims are
live-only (two-machine identity continuity, cookie behaviour in a real browser, the résumé-link
first-visit). Everything else must be unit- or Postgres-testable, and the demo must never break
for a first-time caller mid-stream.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml`, `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` — `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Quick run** | `.venv/bin/pytest tests/test_service.py tests/test_limits.py` |
| **Full suite** | `.venv/bin/pytest` (bare — `addopts = "-q"` becomes `-qq`, hides counts) |
| **Real Postgres** | local PostgreSQL 17 + pgvector on port 54329 (start the container before gated tests — it was down at research time); CI provides one |
| **Chroma** | NEW this phase: `chromadb==1.4.1` joins the `dev` extra; Wave 0 confirms it imports in CI |

**Measured baselines on the current tree (2026-08-05), for gate discipline:**
- Suite: **436 passed, 34 skipped** local
- `grep -c innerHTML src/research_agent/static/index.html` → **0**
- `/sessions` route objects → **6** (the 10.5 walker count)
- Contract suite arms today → **3** (json, memory, pgvector); target after this phase → **4**

Eight vacuous gates were found across four phases. **Every presence/absence gate below states
its measured baseline. Any `>= 1` count gate is rejected in review.**

---

## Sampling Rate

- **After every task commit:** the task's own selector
- **After every plan wave:** bare `.venv/bin/pytest` plus `.venv/bin/ruff check .`
- **Before `/gsd:verify-work`:** full suite green, CI green with real Postgres AND chroma, live cutover verified
- **Max feedback latency:** 15s

---

## Per-Task Verification Map

Task IDs assigned by the planner; fill them, drop no row, and never rewrite a Criterion or
Automated Command after its gate has run.

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| TBD | TBD | 0 | REQ-store-lifecycle-and-ownership | `ChromaMemoryStore` imports and runs; the contract suite parametrizes 4 arms, not 3 | integration | `pytest tests/test_store_contract.py -k chroma` collects ≥1 | ⬜ pending |
| TBD | TBD | 1 | REQ-demo-authentication | A request with no cookie gets a signed identity cookie minted **on the response** (`HttpOnly; SameSite=Lax; Secure`), and the stream/response body is unaffected | unit | `pytest tests/ -k mint_on_response` | ⬜ pending |
| TBD | TBD | 1 | REQ-demo-authentication | A tampered/invalid token is rejected and re-minted, never 401 on the demo's core routes | unit | `pytest tests/ -k invalid_token_reminted` | ⬜ pending |
| TBD | TBD | 1 | REQ-demo-authentication | A token minted with the secret verifies; with a different secret it does not (HMAC) — falsifies by construction, not by `>=1` | unit | `pytest tests/ -k identity_hmac` | ⬜ pending |
| TBD | TBD | 1 | REQ-demo-authentication | Unset `IDENTITY_SIGNING_SECRET` degrades to per-machine ephemeral identity, global cap still bounds spend | unit | `pytest tests/ -k identity_secret_unset_degrades` | ⬜ pending |
| TBD | TBD | 2 | REQ-demo-authentication | Rate limit keys on identity, not IP; two identities from one IP get independent budgets; state is Postgres-backed (survives across machines) | integration (real PG) | `pytest tests/ -k rate_limit_per_identity` | ⬜ pending |
| TBD | TBD | 2 | REQ-demo-authentication | In-flight runs reserve `DEMO_RESERVED_RUN_USD` and settle to real cost; N concurrent runs cannot overshoot the cap (the ~3× race is closed) | integration (real PG) | `pytest tests/ -k cap_reservation_no_overshoot` | ⬜ pending |
| TBD | TBD | 2 | REQ-demo-authentication | The cap's "Read-only endpoints still work" 429 body survives verbatim | unit | `pytest tests/ -k reads_survive_the_cap` | ⬜ pending |
| TBD | TBD | 2 | REQ-demo-authentication | Reservation settles on BOTH the success and the SSE-error arm; a crashed run is reclaimed after the 900s staleness cutoff | integration (real PG) | `pytest tests/ -k reservation_settles_and_reclaims` | ⬜ pending |
| TBD | TBD | 3 | REQ-store-lifecycle-and-ownership | `/sessions` lists only the caller's sessions; a valid `SESSIONS_TOKEN` lists all (dual-mode) | integration (real PG) | `pytest tests/ -k sessions_listing_scoped_and_dual_mode` | ⬜ pending |
| TBD | TBD | 3 | REQ-store-lifecycle-and-ownership | A foreign session returns **404 byte-identical to a missing one** (`No session {id!r}.`) — no existence oracle | unit | `pytest tests/ -k foreign_session_is_indistinguishable` | ⬜ pending |
| TBD | TBD | 3 | REQ-store-lifecycle-and-ownership | `DELETE` succeeds for owner OR operator; refuses others identically to missing | integration (real PG) | `pytest tests/ -k delete_owner_or_operator` | ⬜ pending |
| TBD | TBD | 3 | REQ-store-lifecycle-and-ownership | A session idle > 7 days stops resolving (lazy filter against the DB clock); a read does NOT renew `updated_at` | integration (real PG) | `pytest tests/ -k expiry_lazy_and_reads_do_not_renew` | ⬜ pending |
| TBD | TBD | 3 | REQ-store-lifecycle-and-ownership | The opportunistic sweep on `create()` deletes expired sessions and their notes; two orphaned sessions + two orphaned notes are reclaimed | integration (real PG) | `pytest tests/ -k sweep_deletes_expired` | ⬜ pending |
| TBD | TBD | 4 | REQ-store-lifecycle-and-ownership | Notes scope to owner in `add()` and `query()` — recall returns only the caller's notes — identically across **all four** backends (SC-5) | integration | `pytest tests/test_store_contract.py -k note_scoping` (4 arms collected) | ⬜ pending |
| TBD | TBD | 4 | REQ-store-lifecycle-and-ownership | Notes older than 7 days stop being recalled and are swept, identically across all four backends | integration | `pytest tests/test_store_contract.py -k note_ttl` (4 arms collected) | ⬜ pending |
| TBD | TBD | 4 | REQ-store-lifecycle-and-ownership | The byte-identical cross-backend metrics assertion still passes; the 10.5 route-guard walker still counts its routes (extended, not bypassed) | unit | `pytest tests/ -k route_guard_invariant` | ⬜ pending |
| TBD | TBD | 5 | both | ADR-0007 exists, `Accepted`, supersedes ADR-0006 with carry-forward; ADR-0006 status line edited per the README convention; README limitation updated | grep gate | see 12-05 acceptance criteria (baselines stated there) | ⬜ pending |
| TBD | TBD | 5 | REQ-demo-authentication | **UI (criterion 6):** cleared-storage first paint differs from the pre-phase page by exactly two text deltas (footer + limits line), no interactive step; `grep -c innerHTML …/index.html` still 0; font-size/weight sets unchanged | unit + manual | 12-UI-SPEC.md AC1, AC7, AC8 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `chromadb==1.4.1` added to the `dev` extra; `ChromaMemoryStore` confirmed importing in CI;
      contract suite parametrized over 4 arms (the 4th must **collect**, not skip, in CI).
- [ ] `Database.transaction()` helper (the pool is autocommit; `pg_advisory_xact_lock` needs a
      transaction scope) — with a test.
- [ ] New test modules follow the repo convention: shared fakes in the owning module, **no
      `conftest.py`**.
- [ ] Start the local Postgres container (port 54329) before running gated tests — a green run
      with Postgres skipped is not evidence (established in Phase 11).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Two-machine identity continuity | REQ-demo-authentication | Needs both live Fly machines + a real browser cookie | Create a session on machine A (cookie minted); force a follow-up onto machine B; confirm it resolves and the cookie verifies on the machine that did not mint it. Record both `FLY_MACHINE_ID`s. |
| Résumé-link first visit (criterion 6) | REQ-demo-authentication | Real browser, cleared storage | Open the live demo in a fresh/incognito profile; confirm the question form is usable with zero added step; run one question end-to-end; reload and confirm "Your recent research" now appears. |
| Cookie attributes | REQ-demo-authentication | Real browser dev tools | Confirm the identity cookie is `HttpOnly`, `Secure`, `SameSite=Lax`, and rides both the fetch and the fetch-stream calls. |

**Note the research pitfall:** `TestClient` uses `http://testserver`; a `Secure` cookie needs
`base_url="https://testserver"` or the cookie silently never sets in tests.

---

## Validation Sign-Off

- [ ] Every criterion has a runnable, baseline-stated gate
- [ ] Contract suite runs **4** arms in CI (json, memory, chroma, pgvector) — all collect
- [ ] Local skip count justified against the 34 baseline (chroma/PG gating only; not disarmed coverage)
- [ ] CI green with real Postgres and chroma
- [ ] Two-machine identity continuity verified live with both machine IDs recorded
- [ ] Criterion 6 verified in a real browser from cleared storage
- [ ] `nyquist_compliant: true` set

**Approval:** pending
