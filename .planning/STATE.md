---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Closing the limitations list
status: executing
stopped_at: "Completed 12-04-PLAN.md (Wave 3): sessions carry an owner and a derived 7-day expiry; SESSIONS_TOKEN is now the operator dual-mode credential; foreign/expired/missing are one 404. Next: 12-05."
last_updated: "2026-08-05T13:55:00.000Z"
last_activity: "2026-08-05 — Executed 12-04: session owner column (lazy migration, both backends), derived 7-day expiry against the DB clock with a sweep on create, require_session_access dual-mode, owner-checked _require returning one 404 for missing/expired/foreign, and the walker extended with the router-level assertion its per-route form was vacuous against. Suite 506/45 plain, 550/1 armed; README/OPERATIONS/.env.example corrected."
progress:
  total_phases: 19
  completed_phases: 9
  total_plans: 12
  completed_plans: 17
  percent: 57
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness (Phase 10.5 hotfix shipped)

## Current Position

Phase: 12 of 17 (Caller identity, session ownership, bounded stores) — **EXECUTING**
Plan: 4 of 6 executed · branch `gsd/phase-12-caller-identity` (off the PR #5 merge; main untouched)
Status: Wave 3 complete (12-04). Sessions now belong to the identity that created them and stop resolving seven days after their last write (derived from `updated_at`, evaluated against the *database's* clock, swept opportunistically on `create()`; reads never renew). `SESSIONS_TOKEN` survives as the **operator** credential — a valid token lists every owner's sessions, without one the listing is caller-scoped — and a foreign, expired or invented session id all return the same 404 with the same body. Criterion 3 and criterion 4 are in; the third named defect (sessions immortal and world-readable to any token holder) is closed.
Last activity: 2026-08-05 — Executed 12-04 (commits 82af2cc, b87a088, 6b52781).

**Phase 11 shipped** (PR #5 merged): two machines on Supabase Postgres, release v7.

Progress: [██████░░░░] 65% (11 of 17 phases complete + hotfix 10.5; v1.0 shipped)
Phase 12: [███████░░░] 4 of 6 plans — executing

**Carry into execution — what breaks the demo if wrong:**

- **Minting is pure-ASGI middleware, mint-on-response, NEVER 401.** `/research/stream`,
  `/ask/stream`, `GET /` return Response objects where a dependency's set_cookie is dropped.
  A first-time COOKIELESS caller's stream must not break — this is criterion 6's hinge.
- **The global daily cap SURVIVES.** Identities are free to mint (clear storage → fresh
  limits), so per-identity limits alone cannot bound the bill. Removing the global cap because
  "limits are per-identity now" is the failure mode.
- **The cap reservation is race-free only inside `pg_advisory_xact_lock`** (transaction-scoped;
  a new `Database.transaction()` helper — the pool is autocommit). Settlement on BOTH success
  and SSE-error arms; 900s staleness reclaim or a crashed run throttles the demo forever.
- **`reserve_or_429` now has a structural walker gate** (like `guard`) so it can't be silently
  forgotten on a route — the exact failure ADR-0006 exists to prevent.
- **Secure cookie + TestClient:** tests need `base_url="https://testserver"` or the cookie
  never sets and auth tests pass vacuously.
- **chromadb joins the `dev` extra**; the contract suite runs 4 arms that must PASS in CI (not
  skip). SC-5 depends on it.

Wave 5 (12-06) is `autonomous: false` — sets the `IDENTITY_SIGNING_SECRET` Fly secret, deploys,
and needs a real browser + two machines to verify criterion 6 and identity continuity.

**Sequencing note:** Phase 10.5 (live endpoint exposure) is a hotfix inserted ahead of
Phase 11 and depends on nothing. It may be planned and shipped before, after, or alongside
Phase 10 — but it must not wait for Phase 11.

## Performance Metrics

**Velocity:**

- Total plans completed: 0 under GSD (phases 1–9 predate GSD planning)
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1–9 | pre-GSD | — | — |
| 10 | 5 (10-01, 10-02, 10-03, 10-04, 10-05) | 55min | 11min |
| 11 | 4 of 5 (11-01, 11-02, 11-03, 11-04) | 230min | 58min |
| 12 | 4 of 6 (12-01, 12-02, 12-03, 12-04) | 86min | 22min |

**Recent Trend:**

- Last 5 plans: —
- Trend: — (no GSD-tracked plans yet)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Full ingested set (23, all soft):
`.planning/intel/decisions.md`.

Recent decisions affecting current work:

- [Ingest]: Zero ADRs existed at ingest — all 23 architectural decisions are soft/revisable. Nothing is LOCKED.
- [Phase 10, approved 2026-08-04]: Promote five load-bearing decisions (DEC-01, DEC-02, DEC-04, DEC-14, DEC-22) to numbered ADRs before any reversal lands.
- [Milestone scope, approved]: All nine README Limitations items are in scope for v1.1.
- [Ordering]: REQ-followup-live-search is last (deepest change); REQ-offline-eval-quality precedes both quality-affecting reversals so their effect is observable.
- [Phase 10.5-01]: Session endpoints reuse the `x-demo-token` header rather than a new `x-sessions-token` — one client-side auth story. CONTEXT left the header name to discretion.
- [Phase 10.5-01]: `require_sessions_token` fails closed (403 when no credential is configured), deliberately diverging from `check_token`'s open-when-unset convention. A control that goes inert on a missing env var is precisely the defect this hotfix exists to fix.
- [Phase 10.5-02]: The four session routes are grouped on an `APIRouter`, not given four per-route dependency lists. The defect was four routes each independently forgetting a credential, so membership had to become structural — a new route on `sessions_router` is guarded by construction.
- [Phase 10.5-02]: `check_rate_limit` on `DELETE /sessions/{id}` only, sharing the research bucket. Reads stay unmetered so the daily cap's "Read-only endpoints still work" message stays true.
- [Phase 10-01]: ADR provenance is a two-form contract — `**Promoted from:**` for the five `docs/DESIGN.md` promotions, `**Source:**` for ADR-0006, which originates in Phase 10.5 and has no DESIGN.md passage. The index says so in prose so no reader hunts for one.
- [Phase 10-01]: Supersession is a status-line edit and nothing else. A superseded record's Context, Decision and Consequences are never rewritten, including claims that stopped being true. `docs/adr/README.md` states this as a verbatim three-step instruction for Phases 12, 16 and 17.
- [Phase 10-01]: Expected supersessions (Phase 16 → ADR-0005, Phase 17 → ADR-0003, Phase 12 → ADR-0006) are carried in the index as italicised forecasts. All six records are `Accepted` today; nothing is marked superseded.
- [Phase 10.5-02]: **Any assertion over `app.routes` must now be recursive.** fastapi 0.141.1 leaves an `_IncludedRouter` in `app.routes` rather than flattening, so a flat scan silently misses every session route. Two pre-existing tests were fixed for this; plan 04's structural test must not repeat the mistake.
- [Phase 10.5-03]: The daily-cap test records real spend and asserts `POST /research` 429s *before* asserting a read is 200. Under the fixture's `DEMO_DAILY_USD_CAP=0`, `check_daily_cap` returns early, so the obvious construction cannot fail even if the cap were wired onto the reads.
- [Phase 10.5-03]: A guard test is not done until the guard has been removed and the test observed failing. All six controls in this phase were mutation-checked individually; the mutation table lives in `10.5-03-SUMMARY.md` and is plan 04's acceptance shortcut.
- [Phase 10.5-04]: `api_routes()` **supersedes** wave 2's private `_served_routes()` walker rather than sitting beside it. Two independent recursive walkers over `fastapi.routing._IncludedRouter` — a private, version-specific internal — is two things to fix on the next FastAPI upgrade and two things that can drift.
- [Phase 10.5-04]: The non-vacuity threshold is **6 route objects across 5 paths**, not 5 — `/sessions/{session_id}` is served by both a GET and a DELETE. Do not "correct" it downward.
- [Phase 10.5-04]: A naive flat route scan does not find *zero* session routes as the obvious analysis suggests — it finds the two `@app.post` ask routes, both of which carry `guard`, and therefore reports a perfectly clean sessions tree. A guard invariant without a count assertion goes green over exactly this phase's defect. Verified by mutation.
- [Phase 10-02]: Each record with a named future reversal carries a `### Expected reversal` subsection, not a passing mention — which phase, which requirement, and what specifically breaks. ADR-0005's is the sharpest: Phase 16 removes the record's *premise* (the critic's shared model), so the stronger-judge rationale must be re-derived rather than inherited.
- [Phase 10-02]: ADR-0006 leads its Consequences with a dedicated heading, `### DEMO_TOKEN must never be set in production`, rather than a bullet. The record exists for that one consequence; a list would bury it, and the refactor it guards against ("tidy the two tokens into one") is the plausible-looking kind.
- [Phase 10-02]: ADR-0006 states all four decision parts with individual reasons because they are separable — a future change is most likely to pick off one (apply `guard` to the reads, or make the credential open-when-unset) without seeing the others.
- [Phase 10-04]: The forward-links point at **ADR-0001…0005 only**. ADR-0006 is not linked from `docs/DESIGN.md` and must not be added: it originates in the Phase 10.5 hotfix and carries `**Source:**`, not `**Promoted from:**`. A link from DESIGN.md would assert a provenance that does not exist.
- [Phase 10-04]: The link text carries both the record number and the path (`Recorded as [ADR-000N](adr/000N-slug.md)`) rather than a bare title link, so a reader scanning the prose gets the identifier that supersession notices will use.
- [Phase 10-04]: The "expires this month" clause was replaced with "is time-boxed" rather than a fresher relative date. Any wording anchored to a writing date decays; the two ISO dates carry the fact.
- [Phase 10-05]: A red gate is recorded as red. SC-5 step 3 failed and the row was marked ❌ with the approval left pending, rather than the criterion being reworded to match the observed state. The Criterion and Automated Command columns of `10-VALIDATION.md` were not touched after the gates ran.
- [Phase 10-05]: Two edits were made to `10-VALIDATION.md` prose that the verify block forced, and neither weakens a gate: the `⬜ pending` token was dropped from the status legend (nothing is pending, so the key entry was dead), and the sign-off item `` `nyquist_compliant: true` set in frontmatter`` was reworded to "Frontmatter marks the phase Nyquist-compliant" so the literal token appears exactly once, in the frontmatter that owns it.
- [Phase 10-05]: `ruff` is not on `PATH` in this environment; `.venv/bin/ruff` is the working invocation, matching the `.venv/bin/pytest` convention. Recorded so a future phase does not read a bare `ruff check .` failure as a lint regression.
- [Phase 10-05]: The non-vacuity control is now four probes, not one — the zero-occurrence search, the file counter, the link resolver and the `Status` gate were each shown to fail on input that must fail. This repo has shipped five vacuous gates across two phases; a gate that has only ever passed is treated as unproven.
- [Phase 11-03]: **A guard that skips is a guard that config deletion disarms.** Two deploy tests `pytest.skip()`d whenever `[[mounts]]` was absent, so removing the mount would have made them no-ops with CI still green. Both are now two-armed — they assert in *both* topologies and skip in neither. The old guard was fed the same scratch file as the new one and returned `Skipped` where the new one raises. Any future mount-conditional or DSN-conditional check should be written this way from the start.
- [Phase 11-03]: **Removing the `*_DB_PATH` vars does not close the SQLite fallback; the pins do.** `sessions.py` defaults its path to a file beside the module and the backend selector returns `sqlite` with no DSN, so a mount-less machine with an unset `DATABASE_URL` boots on container-local SQLite, `/health` reports `dependencies: "ok"` because SQLite is perfectly reachable, and the only difference on the wire is a class name nothing reads. `SESSION_BACKEND`/`METRICS_BACKEND`/`VECTOR_STORE` pinned makes it fail closed at store construction instead. This is the gate `-k fails_closed` deliberately does not provide.
- [Phase 11-03]: **Assert on the parsed `[env]` table, never the file text, when one key name is a substring of another.** `grep -c 'VECTOR_STORE' fly.toml` returns 1 on a file with no `VECTOR_STORE` key at all, because `VECTOR_STORE_PATH` contains it. The inverse also applies: the `-k runbook` guard deliberately *does* read the text, because a comment is precisely what it guards and `tomllib` discards comments.
- [Phase 11-03]: **A test that is red until an edit lands belongs in the task that makes the edit.** The runbook-staleness guard was written in Task 2, not Task 1, because Task 1's verify runs the whole file and would have ended red. Recording the red observation against `git show HEAD:fly.toml` is what makes an absence-asserting gate falsifiable.
- [Phase 11-03]: **Two more vacuous gates caught before running** — bringing this repo to eight across four phases. `PG_CONNECT_TIMEOUT >= 1` and `SESSION_BACKEND >= 1` in `docs/OPERATIONS.md` both already passed on the untouched tree. Replaced with prose-only greps (`grep -v '^|'`), an old-text-is-gone check, a same-paragraph co-occurrence check, and a same-line tie to `pin|cutover`. The rule: state the *measured* baseline in the gate, and if it is not zero, the `>= 1` form proves nothing.
- [Phase 11-03]: **Line-oriented gates need line-oriented prose.** `grep 'X' file | grep -c 'Y'` requires both tokens on one *physical* line, and 80-column reflow kept separating them. The sentence was rewritten to suit the gate rather than the gate weakened to suit the sentence.
- [Phase 11-01]: `check=ConnectionPool.check_connection` is **deliberately not used**, against RESEARCH's own Pattern 1. The check is a server round trip performed *during* checkout and the pool's `timeout` does not interrupt one in flight, so on a partitioned database it adds an unbounded cost to every checkout — on `/health`, the exact endpoint this phase is bounding. Staleness stays covered by the retry-once arm. Gated by `grep -c 'check_connection' src/research_agent/db.py` returning 0, with the reason in a comment so the omission does not read as an oversight.
- [Phase 11-02]: **A local Postgres was built to run the gated suite**, because Docker was unavailable and this phase's plans state explicitly that a green local run is not evidence. It found three `db.py` bugs, two of which no fake could have caught. The rule this establishes: for a phase whose claims are server-shaped, "the Postgres tests skipped locally" is an unverified result, not a pass.
- [Phase 11-02]: **The retry discriminator is the SQLSTATE, not the exception class.** Both obvious rules are wrong. "Any `OperationalError`" retries `QueryCanceled` (57014) and doubles the statement timeout that just fired. "Has a SQLSTATE means the server is alive" refuses to retry `AdminShutdown` (57P01), which is exactly what `pg_terminate_backend` sends. The second rule shipped and was caught only by the real server. `_connection_was_lost()` now retries SQLSTATE `None`, class `08`, and `57P01/02/03`.
- [Phase 11-02]: **Reads retry the whole statement; writes deliberately do not.** A client cannot distinguish "never arrived" from "committed, response lost", so a retried write is at-least-once — a duplicated run in `/metrics` or a `UniqueViolation` over a row that exists. The asymmetry is documented in `_read()` rather than left to be inferred.
- [Phase 11-02]: **`pool.check()` on the failure path is not the `check=` callback 11-01 rejected.** A provider terminates every idle connection at once, so a bare retry-once drew the next dead connection and still failed against a real server. `check()` replaces all broken idle connections, but runs *only* after one has been found dead — so 11-01's objection (a round trip on every checkout, including `/health`'s) does not apply and still stands.
- [Phase 11-02]: **`_probe`'s deadline bounds availability, not execution**, and the docstring says so precisely. A `ThreadPoolExecutor` bounds its *workers*, not its *queue*; abandoned probes against a persistently hung peer are reaped by `tcp_user_timeout`, not by the worker count. `future.cancel()` was deliberately not added so the documented mechanism stays the true one.
- [Phase 11-02]: **The skip-count invariant rises from 28 to 34**, and the operative gate is restated as (1) `0` skipped in CI under `REQUIRE_POSTGRES=1` — actually run, not predicted — and (2) locally, skips rise by exactly 6, each named in the summary. 11-05 Task 4 must mirror this into `11-VALIDATION.md`.
- [Phase 11-02]: Two acceptance greps again tripped on the prose explaining why the forbidden token was removed — the same tension 11-01 logged. Resolved the same way: keep the gate, reword the reason. This is now a repeat pattern and a plan author should expect it.
- [Phase 11-01]: `Database.close()` is a **claim release**, not a disposal, and is idempotent. `service.lifespan` closes sessions and metrics but never the memory store, and the contract suite closes after every parametrised case; a `close()` that disposed a shared pool would break the remaining holders, and a `ConnectionPool` cannot be reopened. `db.close_all_pools()` exists for the lifespan `finally` and is not wired yet — that is 11-02.
- [Phase 11-01]: RESEARCH's Pitfall 7 was **wrong in the safe direction**. `PoolTimeout`'s message is "couldn't get a connection after 0.50 sec", and `test_store_contract.py`'s `match="(?i)connect"` is a `re.search`, which "connection" satisfies. The test needed no edit; do not loosen it later on the strength of the prediction.
- [Phase 11-01]: The retry arm in `cursor()` can only fire on an exception raised at *checkout*. A `@contextmanager` that yields a second time after an exception is thrown in raises `RuntimeError: generator didn't stop after throw()`. This is the pre-existing shape, unchanged by the port — worth knowing before anyone "improves" it.
- [Phase 11-04]: **With a staged secret, use `fly deploy`, never `fly secrets deploy`.** The latter re-releases the *current* image, so it would have shipped the new DSN onto the pre-pool v4 build — Postgres-backed stores running single-`RLock`-connection code with no per-probe deadline and no `machine` key. One `fly deploy` applies staged secrets **and** the branch code in the same release. The deployed release was then confirmed to carry waves 1–3 (the startup log naming all three backends, the `machine` key in `/health`) rather than assumed to.
- [Phase 11-04]: **Supabase's default `search_path` already contains `extensions`**, so `memory.py`'s unqualified `::vector` casts resolve *without* 11-01's `_configure()` callback. Verified both ways on the live database. The callback stays — it makes the requirement explicit rather than inherited from a provider default that can change, and it is what keeps the code portable — but it is **insurance that has not yet been needed**, not a fix for an observed break. Do not read 11-01's rationale as describing a failure that happened.
- [Phase 11-04]: **A provider-credential failure is not a reason to roll back a database cutover.** `POST /research` 502'd on a revoked `ANTHROPIC_API_KEY` minutes after the cutover. The tempting move is `fly secrets unset DATABASE_URL`. It would have discarded a verified-good migration and left the demo exactly as broken. The discriminator was cheap and should be reached for first: the failing secret's digest was unchanged by the deploy, and the 401 came from the third party's own API.
- [Phase 11-04]: **The HTTP round trip and the database round trip are separable, and worth separating when one is blocked.** Every HTTP write path runs the model first, so a dead model key blocks the session round trip through `/research`. Proving it at the store layer over `fly ssh console` — same classes, same pool, same DSN, same `::vector` cast — discharged the database claim honestly, with the gap (FastAPI's dependency wiring, already covered by `/health`) named rather than papered over.
- [Phase 11-04]: **`fly ssh console -C` takes no shell**, so RESEARCH's `python - <<'PY'` heredoc never reaches Python, and the container has no `curl`. base64-encode the script locally and run `python -c "import base64;exec(base64.b64decode('...'))"`. This also keeps credentials inside the machine — the script reads `os.environ['DATABASE_URL']` and never prints it.
- [Phase 10.5-01]: `REQ-live-endpoint-exposure` stays **Pending** until plan 05. Its text says "not reachable without credentials **on the deployed service**" — it cannot be honestly checked off by a plan that wires nothing and deploys nothing. Mark it at the cutover, not before.
- [Phase 12-01]: **The dev extra composes `research-agent[chroma]` rather than repeating the pin.** chromadb==1.4.1 stays pinned once, in the chroma extra; a SQLite/JSON deploy installing `[service]` alone still never pulls it. The contract fixture's chroma arm skips ONLY on a genuinely missing chromadb import — never on HAS_POSTGRES — so CI (which installs dev) collects and runs it.
- [Phase 12-01]: **`CAP_LOCK_KEY` (11165997) is a different advisory-lock key from `SCHEMA_LOCK_KEY` (3895545195)**, and the inequality test is deliberately not Postgres-gated so a keyless local run still catches a collapsed-constants edit. A shared key would serialise cap accounting against schema DDL.
- [Phase 12-01]: **The xact-lock test's held-half is what makes it falsifiable.** `pg_advisory_xact_lock` on an autocommit connection degenerates to a one-statement lock, so a `transaction()` that silently stopped opening a transaction would still pass an after-the-block acquisition check. The test therefore also asserts a rival connection is REFUSED the lock while the block is open. `transaction()` mirrors `cursor()`'s PoolTimeout/PoolClosed-before-OperationalError ordering.
- [Phase 12-01]: **The full-suite baselines moved and are fully explained**: plain 436/34 → 443/37 (+6 chroma-arm, +1 key-inequality; +3 Postgres-gated transaction skips), armed 469/1 → 479/1. README's "470 tests, ~10s" was falsified by this wave and updated to "480 tests, ~25s" in the same wave — the chroma client's startup is most of the wall-clock growth.
- [Phase 12-02]: **The HMAC gate is falsifiable by construction, not by presence.** One test mints under secret A and asserts verify returns the id under A AND None under B on the same token. A `grep -c compare_digest` gate alone proves wiring, not rejection.
- [Phase 12-02]: **Tests authenticate through the real path.** `IdentityMiddleware` is not dependency-overridable, so `mint_cookie(monkeypatch, secret=...)` mints genuine tokens under a pinned `IDENTITY_SIGNING_SECRET` and tests present them as the `ra_id` cookie. Later waves (limits, ownership, note scoping) key on this seam.
- [Phase 12-02]: **`Secure` is unconditional; the tests adapt, never the attribute.** `make_client` uses `base_url="https://testserver"` because httpx's jar withholds a Secure cookie over http — under the default base_url every request silently re-mints and per-identity tests pass vacuously. Do not fork the cookie attributes on env.
- [Phase 12-02]: **A bare ASGI stub cannot sit inside `with TestClient(...)`** — the context manager drives lifespan, which the stub answers with http messages and Starlette asserts. Raw-middleware tests use the client without the context manager.
- [Phase 12-02]: **README's identity narrative is left to the wave that owns it.** "guardrails … don't identify callers" stays true until Wave 3 rekeys the limits; Wave 5 owns the deployed-identity story. Only the falsified test count (480 → 504) was corrected in-wave.
- [Phase 12-03]: **The two halves of `LimitsStore` have deliberately different strictness, and confusing them is the expensive mistake.** `check_rate` is a fairness tool: one statement, one round trip, and a small concurrent-insert overshoot costs nothing. `reserve` is a money tool: check-and-insert inside `db.transaction()` holding `pg_advisory_xact_lock(CAP_LOCK_KEY)`, because a single conditional INSERT is **not** race-free under READ COMMITTED — two guards each evaluate the WHERE against a snapshot excluding the other's uncommitted row and both pass. The reason is written at the seam so nobody "simplifies" the reserve into the rate shape.
- [Phase 12-03]: **`caller_identity()` falls back to one SHARED bucket, never to `client_ip`.** A shared bucket is more restrictive than the truth, which is the safe direction; an address fallback would quietly reinstate the forgeable key this phase removed, and would do it exactly when the identity layer was broken — i.e. when nobody was looking. `client_ip` and `TRUST_FORWARDED_FOR` survive for **logging only**, with a do-not-key-limits-on-this comment.
- [Phase 12-03]: **The cap left `enforce()` rather than gaining a `run_id` parameter there.** A reservation needs state the guard cannot see (the run does not exist until the handler builds it), and a guard that half-enforces the cap is worse than one that visibly does not. `reserve_or_429` raises **synchronously inside the handler**, before any StreamingResponse is constructed, so a capped caller gets a real 429 rather than a 200 whose body turns out to be an error event.
- [Phase 12-03]: **An in-handler control needs two gates, not one.** `reserve_or_429` is not a route dependency, so the `api_routes()` walker structurally cannot see it — the exact ADR-0006 shape, on the same `/sessions` routes that forgot a credential four times. It is held by a parametrized four-route 429 test **and** a structural `inspect.getsource` invariant with a non-vacuity floor asserted first. Falsified, not assumed: deleting the reserve from `ask()` alone turns both red.
- [Phase 12-03]: **Settle goes next to `metrics.record`, never in the handler's `except`.** `_stream` swallows its exception to terminate the SSE cleanly, so the handler's own `except` never runs on a failed stream — a settle placed there leaks a reservation on every stream failure. Four terminal arms, four settles. `limits.settle()` itself never raises: a failed settle must not turn a finished run into a 500 or truncate a stream that already delivered, and `RESERVATION_STALE_SECONDS` (900s) makes the failure survivable while the warning keeps the leak visible.
- [Phase 12-03]: **The process-global `RateLimiter` instance is gone.** It was what made "the rate limit" mean something different on each machine, and a module global is not something a request can be pointed away from. The window now lives in the injected store; `RateLimiter` survives only as `InMemoryLimits`' internals.
- [Phase 12-03]: **Baselines moved and are fully explained**: plain 467/37 → 493/41, armed 503/1 → 533/1, collected 504 → 534. The four extra plain skips are exactly the Postgres-gated `test_limits.py` tests, so **a green plain run is not evidence for the no-overshoot race** — the armed run against `:54329` is. README's falsified spend-cap limitation was corrected by the wave that falsified it; the "rate-limited, not authenticated" line still belongs to Wave 5.
- [Phase 12-04]: **A dependency assertion over routes cannot see WHERE the dependency came from.** Every session handler injects `require_session_access` as a parameter to read its value, so `dependency_names(route)` is satisfied with or without the router-level declaration — deleting `sessions_router`'s own `dependencies=[...]` left the new structural gate GREEN. Observed by mutation, not reasoned about. `service.sessions_router.dependencies` is now asserted directly. Structural membership is the entirety of ADR-0006 part 4; a gate that cannot see it removed is not guarding it.
- [Phase 12-04]: **404 for foreign, expired and missing alike — asserted as an equality between two live responses**, not as two status codes. Equal status, equal key sets, and detail strings differing only in the echoed id. A 403 confirms an id names a real session, and session ids travel in shared URLs and screenshots.
- [Phase 12-04]: **`delete_session` calls `_require` before `store.delete`.** `store.delete` returns True/False, which distinguishes a real id from an invented one even while refusing both — the oracle rebuilt one layer down. Ownership is checked at the same choke point the reads use.
- [Phase 12-04]: **Expiry is derived from `updated_at`, never a second column, and Postgres evaluates it with `EXTRACT(EPOCH FROM now())`.** Two machines then read one clock; a Python-side cutoff would make "expired" mean something slightly different on each. `SESSION_TTL_DAYS` (7) is read per call. Reads must never renew — otherwise "7 days after last activity" silently becomes "7 days after last glance" and the table never shrinks (contract-tested on both backends, the renewal half asserted on a live session *before* the expiry half).
- [Phase 12-04]: **The fail-closed property of `SESSIONS_TOKEN` inverted, and that is the honest reading.** It used to raise 403 when unset because the token was the only thing between a stranger and someone else's research. Ownership is now that thing, and ownership cannot be left unset — so an unset token closes the operator view alone. `require_session_access` never raises. ADR-0007 (Wave 5) records it.
- [Phase 12-04]: **`client.cookies.set(name, value, domain="testserver")` silently does not send the cookie**; hand cookies to the `TestClient` constructor instead. 12-03's `test_delete_rate_limited_check_runs_after_the_token_check` used the broken form, so its stated premise ("carries the VICTIM'S cookie") was false while the test still passed.
- [Phase 12-04]: **Pre-Phase-12 rows need no migration step.** `owner=''` matches no caller (identities are 32-hex uuids), so orphans resolve for nobody the moment the filter lands and are swept once past the seven-day line. Claim-by-nobody-and-expire: no manual deletion, no special case in code, and the operator can still inspect them until they age out.
- [Phase 12-04]: **Baselines moved and are fully explained**: plain 493/41 → 506/45, armed 533/1 → 550/1, collected 534 → 551 (+17 in both arms). The four extra plain skips are exactly the postgres arms of the four new session-contract tests, so the **armed** run is what proves DB-clock expiry. README/OPERATIONS/.env.example corrected for ownership, expiry and `SESSIONS_TOKEN`; the "rate-limited, not authenticated" line at ~210 remains Wave 5's.

### Pending Todos

None yet.

### Blockers/Concerns

- **OPEN — `ANTHROPIC_API_KEY` is revoked; no research run can complete in production.**
  Found by plan 11-04 on 2026-08-05, immediately after the Supabase cutover. `POST /research`
  returns **502** in 0.73s with `{"event": "run_failed", "error": "AuthenticationError"}`. Probed
  from inside the machine: `GET https://api.anthropic.com/v1/models` returns
  **HTTP 401 `{"type":"authentication_error","message":"API key is invalid."}`**. The key is
  well-formed (`len=108`, prefix `sk-ant-api03`, no stray whitespace) — Anthropic is rejecting it
  server-side. `VOYAGE_API_KEY` is fine (HTTP 200), which is why pgvector embedding still works.
  **This is NOT caused by the cutover and rollback would not fix it:** the secret digest
  `35d77d861c484d1a` is identical before and after release v5, and plans 11-01..11-03 touched
  nothing on the model-client path. Fix: `fly secrets set -a research-agent ANTHROPIC_API_KEY='...'`
  then confirm `POST /research` returns 200 with a `session_id`.
  **Does not block 11-05** — SC-2/SC-3 are demonstrated by `/health`'s `machine` key, which needs no
  model call. It does block "demonstrable to a stranger", and it is why `/metrics` currently
  advertises a **100% failure rate** (one row, the failed run above).

- **`/health` cannot see the outage that matters — Phase 12 material.** It reports
  `"credentials": {"anthropic": true}` for a revoked key, because it checks *presence*, not
  *validity*. So the liveness probe was green throughout an outage that takes the public demo down
  completely. Making it validate means an outbound call on every probe with its own budget
  implications — a design decision, deliberately not taken in 11-04.

- **OPEN — `main` is 21 commits ahead of `origin/main`; Phase 10 sign-off waits on a push.**
  Found by plan 10-05's SC-5 re-verification on 2026-08-05, after a `git fetch origin` so the
  count is against a current remote and not a stale tracking ref. `origin/main` sits at
  `804b873` (the Phase 10.5 close); `main` sits at `238d479`. Every one of the 21 commits is
  Phase 10 documentation — `.planning/`, `docs/`, `docs/adr/`, `README.md` — **including the
  phase base `715e9aa` itself**, which is also unpushed.
  `git diff --name-only origin/main..main -- src/ tests/ evals/ pyproject.toml Dockerfile fly.toml`
  returns **0 files**, so the code in Fly release v4, on `origin/main` and on `main` is
  identical and the deployed image is not stale. **This is not a deploy problem and must not be
  answered with `fly deploy`** — `git push` alone turns the row green, after which Phase 10 and
  `REQ-adr-promotion` can both be closed. Recorded as ❌ red in
  `10-VALIDATION.md` § Execution Record with `**Approval:** pending`.

- **LIVE SECURITY EXPOSURE — Phase 10.5.** `GET /sessions`, `GET /sessions/{id}`,
  `GET /sessions/{id}/trace` and `DELETE /sessions/{id}` have no `Depends(guard)`
  (`src/research_agent/service.py:514`, `:519`, `:533`, `:539`). Confirmed against the
  deployed service on 2026-08-04: an unauthenticated `GET /sessions` returned two real
  sessions with full task text, and two `DELETE` calls returned 204 from the open internet.
  `DEMO_TOKEN` does not close this — `check_token` runs only inside `guard`, which these
  paths never reach. The two exposed sessions were backed up and deleted with the owner's
  consent; two orphaned notes remain in the memory store (`/memory` exposes counts only,
  not content). Also: the SSE error handler leaks unredacted `str(exc)`
  (`service.py:263`) while `/health` correctly redacts using a helper that already exists.
  **✅ RESOLVED 2026-08-04 — Fly release v4.** `SESSIONS_TOKEN` was staged and deployed in the
  same release as the code. Verified from the open internet: all four endpoints return **401**
  anonymously and **200** with the token; `/`, `/health`, `/demo`, `/metrics` still 200;
  `/demo` still reports `token_required: false`; an anonymous browser research run still
  completes. The SSE handler redacts and truncates. The cutover also carried Phase 10's three
  pending commits, so the deployed tree now equals `main` and the deploy drift is gone.

  **Residual, owned by Phase 12 — session half RESOLVED 2026-08-05, plan 12-04.** Sessions now
  carry the identity that created them, `GET /sessions` is caller-scoped (a valid `SESSIONS_TOKEN`
  switches to the unscoped operator view), a foreign or expired session returns 404 identical to
  missing, and sessions expire 7 days after their last turn. The two pre-Phase-12 rows carry
  `owner=''`, resolve for nobody, and are swept on the first `create()` past their TTL — no manual
  deletion needed. **Still open:** the two orphaned *notes* from the 2026-08-04 deletions (Wave 4,
  12-05, which scopes and bounds notes), and `_index_json` does not advertise
  `DELETE /sessions/{id}`.

- **Other findings from codebase mapping, not yet phased.** Notes are written to a shared
  store with no tenant scoping (`graph.py:274`) and recalled into other visitors' runs
  (`graph.py:248`), and the critic reads the same untrusted text it polices
  (`graph.py:385`) — so injection can force `APPROVED`. ~~The daily spend cap counts only
  completed runs, so ~16 concurrent runs can overshoot the $5 cap roughly 3×.~~
  **RESOLVED 2026-08-05, plan 12-03** — the cap reserves `DEMO_RESERVED_RUN_USD` per in-flight
  run and check+insert is serialised under `pg_advisory_xact_lock`; a two-thread race against
  real Postgres asserts exactly one of two concurrent reserves is admitted. `pydantic` is unpinned — used by every API model, absent from
  `pyproject.toml`, floating in via FastAPI. `requires-python = ">=3.10"` while Docker and
  CI run 3.14, so the floor is untested. Voyage embedding spend is accounted nowhere.
  Decide in Phase 12 planning which of these belong there versus a later phase.

- **Six requirements are design reversals, not bug fixes.** Each needs a replacement guarantee decided in its own discuss-phase. Two are severe: Phase 17 (REQ-followup-live-search) retires the guarantee DESIGN.md calls "the single failure mode this whole pipeline exists to prevent"; Phase 16 (REQ-independent-critic-model) falsifies README's eval-judge rationale, which must be re-derived rather than inherited. See ROADMAP.md → Reversal register.
- **Docs assert a verified-false fact.** `docs/OPERATIONS.md` (~lines 49–51) says deploys run through Fly's GitHub integration and are not CI-gated. `fly releases -a research-agent` shows 3 releases, all from the owner's personal account — deploys are manual via `fly deploy -a research-agent`. Fixed in Phase 10.
- ~~**Live release is 3 commits behind `main`**~~ — **RESOLVED 2026-08-04.** The Phase 10.5 cutover
  (release v4) carried the README restructure, the `src/` reorganisation and its bugfix. The
  deployed tree now equals `main`. This satisfies Phase 10's SC-5 ahead of schedule; Phase 10 need
  only re-verify rather than redeploy.
- ~~**`docs/DESIGN.md` says three `MemoryStore` backends; there are four**~~ (json, memory, chroma, pgvector) — **RESOLVED 2026-08-05, plan 10-04.** The seams paragraph now reads "four implementations" and names pgvector alongside the other three.
- **Pricing has a shelf life — but the code already handles it.** Verified 2026-08-04:
  `src/research_agent/usage.py:59-76` has contiguous windows (`until=date(2026, 8, 31)` and
  `since=date(2026, 9, 1)`), so no rollover work is needed. What does need a decision before
  2026-09-01: `AGENT_MAX_RUN_COST_USD=1.00` and `DEMO_DAILY_USD_CAP=5.00` in `fly.toml` will
  bind roughly a third sooner once the same workload costs 50% more. Planning docs must not
  quote a single rate as permanent. Touches Phase 14.

- Acceptance criteria in `.planning/intel/requirements.md` are synthesis proposals, **not user-ratified** — firm them up per phase.
- Verified 2026-08-04: nothing cites `/healthz` (which 404s); `/health` is cited correctly. No fix needed, but re-verify in Phase 10 rather than assume.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Docs drift | `docs/OPERATIONS.md` still says the spend cap counts completed runs only and "this is not fixed" (12-03 closed it), describes `DEMO_RATE_LIMIT_PER_HOUR` as per-visitor-IP (12-03 rekeyed it to identity), and omits `DEMO_RESERVED_RUN_USD` from the env table | Open — 12-06 owns the phase doc pass | 12-04 |

## Session Continuity

Last session: 2026-08-05
Stopped at: **Completed 12-04-PLAN.md — Wave 3 of Phase 12 is in.** Three commits on
`gsd/phase-12-caller-identity`: `82af2cc` (the `owner` column on both session backends — an
idempotent `ALTER TABLE … IF NOT EXISTS` appended to `POSTGRES_SCHEMA` so it runs inside the
existing advisory-locked lazy DDL, and a `PRAGMA table_info(sessions)` probe for SQLite, whose
owner index is created *after* the probe because a pre-Phase-12 file already has the table;
`session_ttl_seconds()` reading `SESSION_TTL_DAYS` (7) per call; a lazy expiry filter in
`get`/`list` computed from `EXTRACT(EPOCH FROM now())` on Postgres so two machines share one
clock; `list(limit, owner=None)`; an opportunistic sweep on `create()`; four contract tests over
BOTH backends), `b87a088` (`require_sessions_token` → `require_session_access` returning
`("operator", None)` or `("identity", id)` and never raising; `_require(store, id, owner, *,
operator)` raising one 404 for missing, expired and foreign; caller-scoped listing with the
operator dual-mode; `delete_session` going through `_require` *before* `store.delete`; the ask
routes keeping `guard` and enforcing ownership in-handler; `owner=` threaded into both
`store.create` call sites; the walker extended and then **strengthened after mutation showed the
plan's own form was vacuous**), and `6b52781` (README's API table and known-limitation bullet,
OPERATIONS' `SESSIONS_TOKEN` row and two-tokens paragraph, `SESSION_TTL_DAYS` into both env
tables, and `deferred-items.md`).
Suite: **506 passed / 45 skipped plain, 550 passed / 1 skipped armed** against 493/41 and 533/1.
Collected 534 → 551; the four extra plain skips are exactly the postgres arms of the four new
session-contract tests, so the plain run is **not** evidence for DB-clock expiry — the armed run
on `:54329` is. `ruff` clean. Nothing deployed; no push.
**Falsified, not assumed:** dropping the owner check from `_require` turns 7 tests red; forcing
the listing unscoped turns 3 red; and deleting `sessions_router`'s own `dependencies=[...]`
initially turned **nothing** red, which is why the gate now asserts the router's dependency list
directly.
**Owed to 12-05/12-06:** `REQ-store-lifecycle-and-ownership` stays Pending until the notes half
lands in Wave 4. `docs/OPERATIONS.md` still carries two claims 12-03 falsified (see Deferred
Items). README's "rate-limited, not authenticated" line at ~210 is still Wave 5's, and is now
false in both halves. The two orphaned *notes* from 2026-08-04 are Wave 4's to deal with; the
orphaned *sessions* need no action — `owner=''` matches nobody and the sweep collects them.
Resume file: None

Superseded — previous session: **Completed 12-03-PLAN.md — Wave 2 of Phase 12 is in.** Five commits on
`gsd/phase-12-caller-identity`: `fe50a83` (the `LimitsStore` ABC with `InMemoryLimits` and
`PostgresLimits`; two new tables under the lazy advisory-locked `ensure_schema`; `get_limits_store()`
defaulting on `DATABASE_URL` like sessions and metrics), `9db9125` (`DEMO_RESERVED_RUN_USD`;
`enforce` reduced to token + identity-rate; `reserve_or_429` carrying the verbatim
"Read-only endpoints still work." 429; `app.state.limits` + the `get_limits` accessor; the reserve
in all four spending handlers and `settle` after every `metrics.record` in `_execute` and
`_stream`; `status()` extended additively with `rate_limit_scope` and `reserved_run_usd`),
`40d2de9` (the doubled gate — parametrized four-route 429 plus the `inspect.getsource` structural
invariant with a non-vacuity floor; **falsified by deleting `ask`'s reserve and observing both go
red**), `7fb1c72` (the two-thread `cap_reservation_no_overshoot` race and the stale-reclaim test
against real Postgres on `:54329`, using two `_dsn_tagged` handles so the threads hold separate
pool connections), and `fd5267f` (README: the spend-cap known-limitation entry rewritten to what
is now true plus the residual it leaves — the 900s stale window and estimate accuracy — and
504 → 534 tests).
Suite: **493 passed / 41 skipped plain, 533 passed / 1 skipped armed** against 467/37 and 503/1.
Collected 504 → 534; the four extra plain skips are exactly the Postgres-gated `test_limits.py`
tests, each reporting `DATABASE_URL is not set` — so the plain run is **not** evidence for the
race gate. `ruff` clean. Nothing deployed; no push. `REQ-demo-authentication` stays Pending until
the Wave 5 cutover.
**Owed to 12-04/12-05:** `status()` now exposes `rate_limit_scope` and `reserved_run_usd` for the
UI wave to render, and `README.md`'s "rate-limited, not authenticated" line at ~210 is now
half-false — the limits *do* identify callers — and is Wave 5's to correct.
Resume file: None

Superseded — previous session: **Completed 12-02-PLAN.md — Wave 1 of Phase 12 is in.** Four commits on
`gsd/phase-12-caller-identity`: `ea204cd` (17 failing identity unit tests, TDD RED observed at
collection), `f7e2494` (`identity.py` — stdlib-HMAC `v1.<uuid4hex>.<sha256>` mint/verify with
`compare_digest`, never-raise verify, per-call `IDENTITY_SIGNING_SECRET` with a cached
per-process ephemeral degrade and one warning, `set_cookie_value` with the LOCKED attributes,
and the pure-ASGI `IdentityMiddleware`), `39ea349` (`app.add_middleware(IdentityMiddleware)`;
`make_client` on `base_url="https://testserver"`; `mint_cookie()` seam; 7 API tests proving the
mint lands on the SSE stream, the FileResponse demo page and a JSON route, that a valid cookie
is never re-minted, that a tampered cookie gets 200-not-401 plus a fresh mint, and that
`request.state.identity` is populated before any handler), and `a828ef1` (README 480 → 504).
Suite: 467 passed / 37 skipped plain, 503 passed / 1 skipped armed — +24 in both runs, every one
named (17 unit + 7 API), skip counts unchanged. `ruff` clean. Zero JS changes; nothing deployed;
no push. `REQ-demo-authentication` stays Pending until the Wave 5 cutover proves it deployed.
Resume file: None

Superseded — previous session: **Completed 12-01-PLAN.md — Wave 0 of Phase 12 is in.** Three commits on
`gsd/phase-12-caller-identity`: `0dbf46f` (chromadb into the dev extra by composing the existing
chroma extra, pin unchanged; the notes fixture parametrizes json/memory/chroma/pgvector and the
chroma arm passes all 6 note contract tests locally), `ea1bb8f` (`Database.transaction()` — one
pooled connection, `conn.transaction()`, cursor on that same connection; `CAP_LOCK_KEY` exported
for Wave 2; 4 tests proving commit-visible, rollback-absent, and the advisory lock held against a
rival while open then taken freely afterwards, run green against local Postgres :54329), and
`1cd461f` (README 470 → 480 tests, ~10s → ~25s). Suite: 443 passed / 37 skipped plain,
479 passed / 1 skipped armed — every delta from the 436/34 and 469/1 baselines named. `ruff`
clean. Nothing deployed; no push.
Resume file: None

Superseded — previous session: **Completed 11-04-PLAN.md — production is on Supabase, and every step is still
reversible.** Task 1 (provisioning) was done by the operator beforehand and was verified, not
redone. One `fly deploy -a research-agent` landed the branch code and the staged `DATABASE_URL` in
**release v5** — deliberately *not* `fly secrets deploy`, which would have put the new DSN on the
pre-pool v4 image. `/health` returns `PostgresSessionStore` / `PostgresMetricsStore` /
`PgVectorMemoryStore`, `dependencies: ok`, `unreachable: []`, `machine: 78156d2c32d738`, host
`aws-0-ap-southeast-2.pooler.supabase.com` with no password and no project ref; `/ready` 200;
`/`, `/demo`, `/metrics` 200; `/demo` still `token_required: false`.
**Measured** (Assumptions A1 and A2 discharged): connect+TLS **119.2 ms**, `SELECT 1` p50
**2.73 ms** / p95 **6.37 ms**; the three real store probes 2.84 / 3.23 / 3.39 ms p50, worst
observed 6.90 ms against a 3000 ms `HEALTH_PROBE_BUDGET` — ~435× headroom, so the `/health`
arithmetic needs no redoing before 11-05. `pg_stat_activity` **15–16** of 60 (5 under the app's
user: 4 idle + 1 active, i.e. `PG_POOL_MAX_SIZE=5` exactly). `/health` wall clock 0.270–0.427 s
over eleven samples. **Zero** `prepared statement` / `_pg3_` / `PoolTimeout` / `OperationalError`
errors over **74** probe-triggering responses across ~9 minutes — Pitfall 3 discharged in
production, where psycopg's threshold-of-5 would actually bite.
**pgvector proved properly:** it lives in the `extensions` schema (the case 11-02 flagged as
unreachable), the lazy advisory-locked DDL created `sessions`, `runs`, `research_notes` and the
HNSW index against an empty database, and a real Voyage-embedded note was inserted and retrieved
by cosine similarity. Also found: Supabase's *default* `search_path` already includes
`extensions`, so 11-01's `_configure()` callback is untested insurance rather than a fix for an
observed break — recorded so nobody misreads the rationale.
**Session round trip** proved at the store layer (`fly ssh console`), not through HTTP, because
every HTTP write path runs the model first: session `2c737084599646a8b0fcc0ec91c92ab2` created in
3.2 ms, read back by id in 2.8 ms with task and draft matching, appended to, listed, deleted. All
probe rows cleaned up afterwards; the one genuine failed production run was deliberately left.
**Nothing irreversible:** `git status --porcelain fly.toml` empty, `[[mounts]]` present,
`min_machines_running = 1`, one machine, volume `vol_vdegz1021w669gx4` attached, and `/data` still
holds 1 session / 3 runs / 3 notes — exactly the pre-cutover `/health` counts. The rollback
(`fly secrets unset DATABASE_URL`) is **untested**; everything it depends on is verified.
**Knowingly given up, now visible:** cumulative `/metrics` history. `spent_24h_usd` went
0.2289 → 0.0 and `/metrics` reads `{"total": 1, "failed": 1, "failure_rate": 1.0}`.
**BLOCKED, separately and not by the cutover:** `ANTHROPIC_API_KEY` is revoked (HTTP 401 from
Anthropic), so no research run completes. See Blockers.
Resume file: None

Superseded — previous session: **Completed 11-03-PLAN.md — the deploy guards are armed and the runbook is honest.**
Three tasks, three commits (`9b4afe6`, `53fb6a0`, `1991f7d`). Both mount-conditional guards in
`tests/test_deploy_config.py` used to `pytest.skip()` when `[[mounts]]` was absent, so 11-05's
mount removal would have silenced them with CI green; both now assert in **both** topologies and
`grep -c 'pytest.skip'` is `1` (the `fly` fixture's legitimate no-`fly.toml` skip), down from `3`.
The stateless arm requires more than the absence of the `*_DB_PATH` keys — it requires
`SESSION_BACKEND=postgres`, `METRICS_BACKEND=postgres`, `VECTOR_STORE=pgvector`, asserted on the
parsed `[env]` table because `VECTOR_STORE_PATH` contains the string `VECTOR_STORE`. Two new
guards: `DATABASE_URL` must not appear in the committed `[env]`, and a `-k runbook` test keeps
`fly postgres create`/`attach` out of `fly.toml` (recorded red against `git show HEAD:fly.toml`).
Four falsification checks run against scratch files, all four observed failing, plus a passing
control; check 1 was also fed to the old guard, which returned `Skipped` where the new one raises
`AssertionError` — the disarm-by-deletion demonstrated rather than argued.
`fly.toml`'s footer, health-budget, `auto_stop_machines`, `primary_region` and concurrency
comments were rewritten for the external-Supabase path, and `docs/OPERATIONS.md` carries the
ordered cutover, the fail-closed pins, the start-clean tradeoff, the kept volume and SC-6's
four-way timeout semantics. **Every `fly.toml` change is a comment** — `git diff -U0 fly.toml`
shows no changed non-comment line, and `tomllib` confirms `min_machines_running == 1`, `mounts`
present and `SESSION_DB_PATH` in `[env]`. Suite **436 passed, 34 skipped** (+2 tests, skip count
unchanged); `ruff` clean.
**Owed to 11-05:** removing `[[mounts]]` is now a four-part change or the tests fail — the three
`*_DB_PATH` vars out, the three pins in, `min_machines_running` ≥ 2. And `11-VALIDATION.md`'s
skip-count invariant still says 28; it is 34.
Resume file: None

Superseded — previous session: **Completed 11-01-PLAN.md — `db.py` is pooled.** Three tasks, three commits
(`8c7a145`, `9e46158`, `5df970b`). `psycopg-pool==3.3.1` pinned and installed; five new env
readers (`PG_POOL_MIN_SIZE`, `PG_POOL_MAX_SIZE`, `PG_POOL_TIMEOUT`, `PG_STATEMENT_TIMEOUT`,
`PG_TCP_USER_TIMEOUT`); one `ConnectionPool` per DSN behind a claim-refcounted registry, shared
by all three stores; the RLock and single `_conn` deleted; `prepare_threshold=None`,
`statement_timeout`, `tcp_user_timeout`, keepalives and a `search_path` `configure` callback all
reaching the connection; `PoolTimeout`/`PoolClosed` re-raised ahead of the retry; DDL under
`pg_advisory_lock(3895545195)` on one connection with the unlock's result checked. `tests/test_db.py`
is new (27 tests, no server needed). Suite **415 passed, 28 skipped** against a 388/28 baseline —
skip count unchanged, so Postgres coverage was extended rather than disarmed. `ruff` clean.
`fly.toml` untouched. Both behavioural gates were mutated, observed red and reverted; the table
is in `11-01-SUMMARY.md` § Falsification Checks.
**Owed to 11-02:** `test_the_connection_recovers_from_being_dropped` reaches into `store.db._conn`,
which this plan deletes. It is Postgres-gated so it skips locally, but it **will fail in CI**.
Repairing it, wiring `close_all_pools()` into the lifespan, the `/health` per-probe deadline and
the real-server lock/pgvector tests are all 11-02's.
Resume file: None

Superseded — previous session: **Completed 10-05-PLAN.md — the phase gate battery.** Every gate in
`10-VALIDATION.md` was run as written on macOS and recorded with its literal output: five ADRs
with `Status` lines and Nygard sections, all five citing `docs/DESIGN.md` and all five linked
back from it, ADR-0006 verified separately (exists, `Accepted`, `DEMO_TOKEN` present, zero
`Promoted from`) so the `000[1-5]` globs stayed as written, `GitHub integration` at zero,
`Deploys are manual` and `enforce_admins` present, four backends with `pgvector`, no unpaired
`$2/$10`, `src/` byte-identical to `715e9aa`, the suite at exactly 388 passed / 28 skipped, and
`.venv/bin/ruff check .` clean. Four non-vacuity controls were run and recorded. SC-5 was
re-verified read-only — release v4 `complete` under the owner's personal account, `/`, `/health`,
`/demo`, `/metrics` all 200 — with **nothing redeployed**. One row is ❌ red: SC-5 step 3
returned `21` for `origin/main..main`, so `**Approval:** pending`. ROADMAP's stale Phase 10.5 row
was reconciled to 5/5 Complete. `REQ-adr-promotion` is left Pending with the blocker named.
Resume file: None

Superseded — previous session: **Completed 10-04-PLAN.md.** SC-2, SC-4 and the DESIGN half of SC-6 are done, so
every corrective criterion in Phase 10 has now landed. `docs/DESIGN.md` names four
`MemoryStore` implementations including pgvector; its pricing paragraph carries both windows
as `2026-08-31` / `2026-09-01` on one line with `/pricing` as the live source and no
"this month" phrasing; and its five promoted paragraphs each end with a `Recorded as ADR-000N`
link, with `adr/README.md` linked from the preamble. All five paths resolve on disk and the
reverse citation from each record back to `docs/DESIGN.md` still holds. `docs/OPERATIONS.md`
and `README.md` remain as 10-03 left them; `docs/adr/` remains the complete six-record set
from 10-01/10-02. Only plan 10-05 (phase-wide verification, including the SC-5 live re-check)
remains. (Phase 10.5 remains complete and shipped as Fly release v4.)
Resume file: None

**Carry forward — findings that outlive this phase:**

- **`DEMO_TOKEN` must stay UNSET in production.** `guard` checks it and fronts
  `POST /research/stream`; the demo page sends no token header, so setting it 401s every
  anonymous visitor and takes the public demo offline. Session endpoints use `SESSIONS_TOKEN`
  instead (sent as `x-demo-token`, fails closed at 403 when unset). Any future phase that
  touches auth must not "tidy" these into one variable.

- **Any assertion over `app.routes` must walk recursively.** fastapi 0.141.1 leaves a
  `fastapi.routing._IncludedRouter` in `app.routes` rather than flattening. A flat scan sees
  only the two `@app.post` ask routes — both legitimately guarded — computes an empty
  unguarded list, and reports a *clean* sessions tree while the four leaking routes stay
  invisible. Use `api_routes()` in `tests/test_service.py` and always assert a route count
  first. Two pre-existing tests had this bug.

- **`docs/adr/README.md` is owned by plan 10-01 and is already complete.** It carries index
  rows for all six records with their titles and expected superseders. Plan 10-02 wrote the
  record files 0003–0006 without editing the index; every row now resolves to a file on disk.

- **`docs/DESIGN.md` is now a two-way index into `docs/adr/`.** Any future phase that renames
  an ADR file must update the five `adr/000N-slug.md` links in `docs/DESIGN.md` as well as the
  index rows in `docs/adr/README.md`. The check is
  `for f in $(grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md | sort -u); do test -f "docs/$f" || echo "DANGLING $f"; done`.

- **The `000[1-5]` ADR gates deliberately exclude 0006.** Records 0001–0005 are DESIGN.md
  promotions and are gated for a `DESIGN.md` citation; ADR-0006 has none by design. Widening
  those globs to `000[1-6]` would make the citation gate fail correctly-written work.

- **Deploys are manual and now proven so.** `fly secrets set --stage` then one `fly deploy`
  puts secret and code in the same release — required whenever a control fails closed.

- **A `@contextmanager` cannot retry from inside the caller's `with` body.** Yielding a second
  time after `gen.throw` raises `RuntimeError: generator didn't stop after throw()`, which fails
  the call *and* destroys the original exception. This is why `db.cursor()` retries only the
  checkout and `db._read()` owns the statement-level retry. Anyone "improving" the retry should
  read both docstrings first.

- **`HEALTH_PROBE_BUDGET` is a new tunable**, 3.0s default with a 0.1 floor, and it has no
  `fly.toml` entry on purpose — the default is the intended production value. 11-05 should
  confirm the resulting 9s ceiling against the real check timeout in `fly.toml`.

- **`fly ssh console -C` runs no shell, and the container has no `curl`.** Heredocs are passed as
  literal argv. base64-encode the script and run
  `python -c "import base64;exec(base64.b64decode('...'))"` — quoting-safe, and it keeps any
  credential inside the machine.

- **`Session.id`, not `Session.session_id`.** The `session_id` key exists only in `summary()`'s
  dict. And `research_notes`'s text column is `text`, not `content`. Both cost a failed probe in
  11-04.

Next: **11-05** — remove `[[mounts]]` and the three `*_DB_PATH` vars, add the three backend pins,
raise `min_machines_running` to 2 and `fly scale count 2`. This is the point of no return for
per-machine state, and 11-04 has cleared its precondition: the database is reachable and proven.
`tests/test_deploy_config.py` makes that a four-part change or it fails. Also owed there:
`11-VALIDATION.md`'s skip-count invariant still says 28 and must become 34, and the branch
`gsd/phase-11-multi-machine-postgres` (waves 1–4) is unpushed — land it via a **pull request**,
not a push, since `enforce_admins` is `false`.
