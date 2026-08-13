---
phase: 12
slug: caller-identity-session-ownership-bounded-stores
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-05
reconciled: 2026-08-11
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
| 12-01-T1 | 12-01 | 0 | REQ-store-lifecycle-and-ownership | `ChromaMemoryStore` imports and runs; the contract suite parametrizes 4 arms, not 3 | integration | **4 arms collect** (json, memory, chroma, pgvector) against the 3-arm baseline. `chromadb==1.4.1` reaches CI through the **composed** dev extra — `dev` pulls `research-agent[chroma]` the same way it pulls `[service]` — so no new package and no pin change, and a SQLite/JSON deploy still never installs chromadb. The chroma arm passes locally and is **never gated on `HAS_POSTGRES`**, which is what makes SC-5's fourth arm a real test rather than a promise | ✅ done |
| 12-02-T1 | 12-02 | 1 | REQ-demo-authentication | A request with no cookie gets a signed identity cookie minted **on the response** (`HttpOnly; SameSite=Lax; Secure`), and the stream/response body is unaffected | unit | **7 collected** in `test_service.py` against a **0** baseline, plus 17 in the new `test_identity.py` (**RED observed first** — ImportError at collection). Proven on the SSE stream, the `FileResponse` demo page and JSON routes alike, from pure-ASGI middleware, never behind a 401. **The research pitfall bit for real:** `TestClient` defaults to `http://testserver` and a `Secure` cookie silently never sets, so the fixture uses `https://testserver` — without it every identity test would have passed vacuously against a fresh identity per request | ✅ done |
| 12-02-T1 | 12-02 | 1 | REQ-demo-authentication | A tampered/invalid token is rejected and re-minted, never 401 on the demo's core routes | unit | **Green.** Never a 401 on the demo's core routes — a visitor with a corrupted cookie is a visitor, not an intruder | ✅ done |
| 12-02-T2 | 12-02 | 1 | REQ-demo-authentication | A token minted with the secret verifies; with a different secret it does not (HMAC) — falsifies by construction, not by `>=1` | unit | **Green.** Falsified by construction over stdlib-HMAC `v1.<uuid4hex>.<sha256>`, not by a `>= 1` count | ✅ done |
| 12-02-T2 | 12-02 | 1 | REQ-demo-authentication | Unset `IDENTITY_SIGNING_SECRET` degrades to per-machine ephemeral identity, global cap still bounds spend | unit | **Green**, with `test_health_reports_an_unset_signing_secret_as_false` as the operator signal. The live rollback that would exercise it was **not run** — see Manual-Only | ✅ done |
| 12-03-T1 | 12-03 | 2 | REQ-demo-authentication | Rate limit keys on identity, not IP; two identities from one IP get independent budgets; state is Postgres-backed (survives across machines) | integration (real PG) | **3 passed, 1 PG-gated skip** plain; `test_limits.py` **54 passed** armed. Both limits moved out of per-machine memory into a `LimitsStore` seam keyed on the signed identity | ✅ done |
| 12-03-T4 | 12-03 | 2 | REQ-demo-authentication | In-flight runs reserve `DEMO_RESERVED_RUN_USD` and settle to real cost; N concurrent runs cannot overshoot the cap (the ~3× race is closed) | integration (real PG) | **Proven by a two-thread race against real Postgres.** The reservation runs `SELECT pg_advisory_xact_lock(CAP_LOCK_KEY)` then the conditional INSERT inside `db.transaction()`, because a bare conditional INSERT is **not** race-free under READ COMMITTED — two guards each evaluate the WHERE against a snapshot excluding the other's uncommitted row. The ~3× overshoot is closed. *(The $0.20 figure this row names became $0.30 on 2026-08-11 via the audit's W2; the mechanism is unchanged.)* | ✅ done |
| 12-03-T2 | 12-03 | 2 | REQ-demo-authentication | The cap's "Read-only endpoints still work" 429 body survives verbatim | unit | **6 passed** with `status` | ✅ done |
| 12-03-T3 | 12-03 | 2 | REQ-demo-authentication | Reservation settles on BOTH the success and the SSE-error arm; a crashed run is reclaimed after the 900s staleness cutoff | integration (real PG) | **7 passed** plain across the reserve/settle family, **2 passed** armed including the 900s staleness reclaim. **Amended 2026-08-11:** the v1.1 audit found this row's success arm covered `_stream` but not `_execute` — the blocking route's `on_complete`/`record` sat outside its try, so a persistence failure there leaked the reservation *and* lost the run from the ledger. Fixed under W1 with a regression test asserting both routes | ✅ done |
| 12-04-T2 | 12-04 | 3 | REQ-store-lifecycle-and-ownership | `/sessions` lists only the caller's sessions; a valid `SESSIONS_TOKEN` lists all (dual-mode) | integration (real PG) | **Green.** `SESSIONS_TOKEN` turned from the visitor's credential into the operator's unscoped debugging view — the reversal Phase 10.5's hotfix made necessary | ✅ done |
| 12-04-T2 | 12-04 | 3 | REQ-store-lifecycle-and-ownership | A foreign session returns **404 byte-identical to a missing one** (`No session {id!r}.`) — no existence oracle | unit | **Green**, on the read path and the write path alike. Confirmed live at the cutover: a second identity gets `{"sessions":[]}` and a 404 byte-identical to the never-existed one. It bit again in Phase 17's live check, where an operator's own 404 turned out to be this working correctly | ✅ done |
| 12-04-T2 | 12-04 | 3 | REQ-store-lifecycle-and-ownership | `DELETE` succeeds for owner OR operator; refuses others identically to missing | integration (real PG) | **Green** — `test_service.py` + `test_limits.py` **159 passed / 4 skipped** for the wave | ✅ done |
| 12-04-T1 | 12-04 | 3 | REQ-store-lifecycle-and-ownership | A session idle > 7 days stops resolving (lazy filter against the DB clock); a read does NOT renew `updated_at` | integration (real PG) | **Green**, lazily against the DB clock; a read does not renew `updated_at`. 4 contract tests × 2 backends = 8, armed | ✅ done |
| 12-04-T1 | 12-04 | 3 | REQ-store-lifecycle-and-ownership | The opportunistic sweep on `create()` deletes expired sessions and their notes; two orphaned sessions + two orphaned notes are reclaimed | integration (real PG) | **Green** — two orphaned sessions and two orphaned notes reclaimed | ✅ done |
| 12-05-T1 | 12-05 | 4 | REQ-store-lifecycle-and-ownership | Notes scope to owner in `add()` and `query()` — recall returns only the caller's notes — identically across **all four** backends (SC-5) | integration | **4 arms collected and passing.** `owner=''` is an **exact value on every backend, never a wildcard** — so the two orphaned notes match nobody the moment the code ships and are collected physically by the TTL rather than by a migration script. This is the wave that closed the path by which one visitor's text reached another visitor's critic | ✅ done |
| 12-05-T1 | 12-05 | 4 | REQ-store-lifecycle-and-ownership | Notes older than 7 days stop being recalled and are swept, identically across all four backends | integration | **4 arms collected and passing.** The TTL comparison is post-filtered in Python on **every** backend, including chroma where a metadata `$gt` exists — one implementation of the comparison per store is what keeps four backends observably identical. Found here: once a sweep can shrink a collection, chroma's `count()`-derived ids can reproduce a live id, and chroma treats a repeated id as an **upsert** — silently overwriting a note instead of adding one. Ids became uuids | ✅ done |
| 12-04-T3 | 12-04 | 4 | REQ-store-lifecycle-and-ownership | The byte-identical cross-backend metrics assertion still passes; the 10.5 route-guard walker still counts its routes (extended, not bypassed) | unit | **Extended, not bypassed** — `AUTH_DEPENDENCIES` renamed, the `>= 6` non-vacuity floor and the delete `>= 4` / GETs `== 3` structure kept verbatim. **And this is where the milestone's deepest vacuous gate was found:** a *structurally sensible* walker assertion stayed green when the router dependency it protects was deleted, because the handlers also inject it as a parameter. Baselines are not enough | ✅ done |
| 12-06-T1 | 12-06 | 5 | both | ADR-0007 exists, `Accepted`, supersedes ADR-0006 with carry-forward; ADR-0006 status line edited per the README convention; README limitation updated | grep gate | grep gate | **Green.** ADR-0007 carries forward the three-and-a-half parts of ADR-0006 that survived rather than discarding the record; ADR-0006's status line edited per the README convention; the README stopped claiming the demo is "rate-limited, not authenticated". The router grouping is **reaffirmed** — only the dependency's name changed | ✅ done |
| 12-06-T3 | 12-06 | 5 | REQ-demo-authentication | **UI (criterion 6):** cleared-storage first paint differs from the pre-phase page by exactly two text deltas (footer + limits line), no interactive step; `grep -c innerHTML …/index.html` still 0; font-size/weight sets unchanged | unit + manual | unit + manual | **Green.** `-k page_` **0 → 10 passed**; `innerHTML` still **0**; exactly two text deltas at first paint. **Verified behaviourally, not only by grep:** no jsdom is installed and installing one was out of bounds, so a throwaway DOM shim ran the real script block and asserted **48 properties** — a stored turn fabricates no cost and no `undefined`; `cost_usd: 0` still renders; the list stays out of the document across empty/non-2xx/thrown-fetch and returns when it empties; a followed-up session renders each turn once rather than the last one twice; 404 removes the row; the next submission posts to `/sessions/{id}/ask/stream` | ✅ done |

---

## Wave 0 Requirements

- [x] `chromadb==1.4.1` added to the `dev` extra; `ChromaMemoryStore` confirmed importing in CI;
      contract suite parametrized over 4 arms (the 4th must **collect**, not skip, in CI).
- [x] `Database.transaction()` helper (the pool is autocommit; `pg_advisory_xact_lock` needs a
      transaction scope) — with a test.
- [x] New test modules follow the repo convention: shared fakes in the owning module, **no
      `conftest.py`**.
- [x] Start the local Postgres container (port 54329) before running gated tests — a green run
      with Postgres skipped is not evidence (established in Phase 11).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Two-machine identity continuity | REQ-demo-authentication | Needs both live Fly machines + a real browser cookie | Create a session on machine A (cookie minted); force a follow-up onto machine B; confirm it resolves and the cookie verifies on the machine that did not mint it. Record both `FLY_MACHINE_ID`s. | ✅ **VERIFIED 2026-08-05, release v9.** Machines **`846975f2604548`** (A) and **`d8d0320f751618`** (B), both `syd`. Cookieless `POST /research/stream` pinned to A minted `ra_id=v1.fac06ec6b6444571aa932c88e0d0bb50.…` on the SSE response and created session `7cb88e3e18274890aa684738ad759d43`. The same jar pinned to B: `GET /sessions` → 200 listing that session with `owner: fac06ec6…`, **`set-cookie` count 0**; `POST /sessions/{id}/ask` → **200 `mode: followup`** (this route 404s on a missing *or* foreign session, so 200 is positive proof). Reverse direction: A then reported `turns: 2`. The zero re-mint is the discriminator — a machine that could not verify would have minted a replacement. |
| Résumé-link first visit (criterion 6) | REQ-demo-authentication | Real browser, cleared storage | Open the live demo in a fresh/incognito profile; confirm the question form is usable with zero added step; run one question end-to-end; reload and confirm "Your recent research" now appears. | ⚠️ **VERIFIED LIVE VIA HTTP, NOT A BROWSER.** A genuinely cookieless `curl` (no jar, no `-b`) with a browser `Accept`/`User-Agent`: **200**, `content-type: text/html`, and `Set-Cookie` on that same response. First-paint interactive tag census of the **served bytes**: `1 <form`, `1 <input`, `1 <button` — no `<details>`, no `<dialog>`, no added control; wall words (`consent\|sign in\|log in\|modal`) **0**; `innerHTML` **0**. Cookieless `POST /research/stream` completed (`node×4`, `result`). Served page `sha256 f136a49f…9cec03` is **byte-identical** to `src/research_agent/static/index.html`, so Task 3's nine static gates gate exactly what production serves. **Not covered:** the JS-driven reload showing "Your recent research", observed in a real browser — that path has DOM-shim + static coverage only. |
| Cookie attributes | REQ-demo-authentication | Real browser dev tools | Confirm the identity cookie is `HttpOnly`, `Secure`, `SameSite=Lax`, and rides both the fetch and the fetch-stream calls. | ⚠️ **ATTRIBUTES VERIFIED VERBATIM IN THE RESPONSE HEADER**, on both the page response and the SSE response: `ra_id=v1.…; Max-Age=34560000; Path=/; HttpOnly; SameSite=Lax; Secure`. curl stored it under the Netscape `#HttpOnly_` prefix. It rode a subsequent `POST .../ask` to a 200 on the other machine, so it rides both plain and stream call sites. **Not covered:** invisibility to `document.cookie` observed in dev tools — `HttpOnly` in the header is the mechanism that produces it, but the observation itself was not made. |
| Rollback path | REQ-demo-authentication | Would require churning production | `fly secrets unset IDENTITY_SIGNING_SECRET` + redeploy; expect degradation to per-process ephemeral identity, not a broken demo. | ❌ **NOT TESTED.** Running it would have churned prod twice more and discarded the continuity just established. Unit coverage exists (`identity_secret_unset_degrades`, `test_health_reports_an_unset_signing_secret_as_false`) and `/health` would flip `identity_signing` to `false` as the operator signal — but that is inference, not observation. |

**Note the research pitfall:** `TestClient` uses `http://testserver`; a `Secure` cookie needs
`base_url="https://testserver"` or the cookie silently never sets in tests.

---

## Validation Sign-Off

- [x] Every criterion has a runnable, baseline-stated gate
- [x] Contract suite runs **4** arms in CI (json, memory, chroma, pgvector) — all collect
- [x] Local skip count justified against the 34 baseline (chroma/PG gating only; not disarmed coverage)
- [x] CI green with real Postgres and chroma — 527 passed / 47 skipped plain; 572 / 1 armed (`:54329`); `ruff` clean
- [x] **Two-machine identity continuity verified live with both machine IDs recorded** — `846975f2604548` and `d8d0320f751618`, release v9; zero re-mints across machines and across a full fleet restart
- [~] **Criterion 6 verified live from a genuinely cookieless caller — over HTTP, not in a browser.** The claim that is fully closed: a caller with nothing to send gets a working page, a `Set-Cookie` on that same response, a completed research stream, and served bytes sha-identical to the statically gated file, with a first-paint tag census showing no added control. The claim that is **not**: the same experience observed in an incognito browser window, including the reload that reveals "Your recent research".
- [x] `nyquist_compliant: true` — **set 2026-08-11.** It was left `false` because the Wave 0 checkboxes had never been ticked and plan 12-06 did not own them. Reconciling the phase closes that: all four Wave 0 items were delivered by 12-01 (the composed chroma extra, the four-arm fixture, `Database.transaction()` with its test, no `conftest.py`) and the gated tests ran against the local Postgres on `:54329`, not skipped. The `false` recorded missing bookkeeping, not missing evidence

**Approval:** **approved for the live-cutover rows, with two exceptions recorded rather than waived.**
Per-task map reconciled 2026-08-11 during the v1.1 milestone audit closure; the exceptions below stand
exactly as written, and two rows carry later amendments (the reservation figure, and the `_execute`
settle arm the audit found and fixed under W1).

The three claims that were live-only are now evidenced with recorded command output in `12-06-SUMMARY.md`
(§ Task 4), not with judgements about it:

1. `/health` reports `identity_signing: true` on **both** machines, corroborated by `fly checks list`.
2. A cookie minted on A verifies on B with **zero** re-mints, carries a `POST .../ask` to 200 on the
   machine that did not mint it, and survives a full fleet restart — which a per-process ephemeral
   secret cannot do by construction.
3. Ownership bites: a second identity gets `{"sessions":[]}` and a 404 on the foreign session that is
   byte-identical to the never-existed 404, on the read path and the write path alike.

**The exceptions, stated plainly so nobody reads this as a browser sign-off:**

- **No real browser was used.** Every live check was `curl`. Where a browser was the specified
  instrument (cookie invisibility to `document.cookie`; the reload revealing the session list), the
  row above says so and the claim is downgraded to the mechanism actually observed.
- **The rollback was not exercised.**

Neither gap blocks the phase: both concern observation instruments for behaviour whose mechanism is
verified elsewhere. Both are recorded so a later phase can close them cheaply rather than inherit
them as assumed-true.
