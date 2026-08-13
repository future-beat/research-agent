---
phase: 12-caller-identity-session-ownership-bounded-stores
plan: 02
subsystem: api
tags: [identity, hmac, cookie, asgi-middleware, sse, security]

# Dependency graph
requires:
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 01
    provides: "Wave-0 foundations and the 443/37 plain, 479/1 armed suite baselines"
provides:
  - "identity.py: mint()/verify() over v1.<uuid4hex>.<hmac-sha256>, stdlib-only, constant-time compare, never raises"
  - "IdentityMiddleware: pure-ASGI, mint-on-response on every response shape (SSE, FileResponse, JSON), never 401, request.state.identity always set"
  - "IDENTITY_SIGNING_SECRET read per call; unset degrades to one cached per-process ephemeral secret with a single warning"
  - "set_cookie_value(): the LOCKED attribute string — HttpOnly; SameSite=Lax; Secure; Max-Age=34560000; Path=/; no Domain"
  - "Test seam for all later waves: make_client on base_url=https://testserver + mint_cookie() minting real tokens"
affects: [12-03, 12-04, 12-05, 12-06]

# Tech tracking
tech-stack:
  added: []  # stdlib hmac/hashlib/secrets/uuid/http.cookies only — itsdangerous deliberately absent
  patterns:
    - "Pure-ASGI middleware instead of a Depends for anything that must touch direct Response returns — FastAPI drops dependency-set cookies on StreamingResponse/FileResponse"
    - "Mint-on-response: Set-Cookie appended at http.response.start via MutableHeaders, only when this request minted"
    - "Tests authenticate by minting real tokens under a pinned secret, not by overriding — the middleware is not dependency-overridable"
    - "Secure is unconditional; tests adapt (https base_url) rather than the security attribute forking on env"

key-files:
  created:
    - src/research_agent/identity.py
    - tests/test_identity.py
  modified:
    - src/research_agent/service.py
    - tests/test_service.py
    - README.md

key-decisions:
  - "The HMAC gate is falsifiable by construction: one test mints under secret A, asserts verify returns the id under A AND None under B on the same token"
  - "The raw-middleware state test uses TestClient without the context manager — `with` runs lifespan, which a bare ASGI stub does not speak"
  - "verify() accepts None and non-str without raising: the token is attacker-supplied on every request and every malformed shape is the same answer"
  - "README's identity narrative (line ~210, 'guardrails … don't identify callers') is deliberately NOT touched: it stays true of the guardrails until Wave 3 rekeys them; Wave 5 owns the story"
  - "REQ-demo-authentication left Pending: this plan is the groundwork; the criterion is only demonstrable on the deployed service at the Wave 5 cutover"

# Metrics
duration: 20min
completed: 2026-08-05
---

# Phase 12 Plan 02: Signed identity token + mint-on-response middleware Summary

**One-liner:** Every caller now gets a signed `ra_id` identity cookie minted silently on the response of the very route they first hit — proven on the SSE stream, the FileResponse demo page and JSON routes alike, never behind a 401 — via a pure-ASGI middleware over stdlib-HMAC `v1.<uuid4hex>.<sha256>` tokens that degrade safely when the secret is unset.

## What was built

### Task 1 — identity.py, TDD (commits ea204cd RED, f7e2494 GREEN)

- **RED:** `tests/test_identity.py` (17 tests) written and observed failing at collection (`ImportError: cannot import name 'identity'`). Committed failing.
- **GREEN:** `src/research_agent/identity.py` — `mint()` returns `v1.<uuid4().hex>.<hmac-sha256 hex>` with the signature over `"v1.<id>"`; `verify()` splits into exactly three parts, checks version and `isalnum()`, compares with `hmac.compare_digest` (the `limits.py` idiom), and returns `None` on every malformed shape — including `None` input — without raising. `_secret()` reads `IDENTITY_SIGNING_SECRET` per call (the monkeypatch-friendly env convention); unset lazily generates ONE `secrets.token_hex(32)` per process under a lock, caches it, and logs a single warning that identities are ephemeral and the global cap remains the bound. `_reset_secret_cache()` gives tests a clean slate. `set_cookie_value()` emits the LOCKED attributes verbatim.
- The `IdentityMiddleware` class also lives in this commit (same file per the plan's artifact spec); its registration and API proof are Task 2.

### Task 2 — middleware registration + all three response shapes (commit 39ea349)

- `service.py`: `app.add_middleware(IdentityMiddleware)` with the middleware-not-dependency reason in a comment. Zero route handlers touched; zero JS touched.
- `IdentityMiddleware`: non-http scopes pass through; the Cookie header is parsed with `http.cookies.SimpleCookie` (no regex); absent/invalid → `mint()`; `scope.setdefault("state", {})["identity"]` set before the downstream app runs; `Set-Cookie` appended at `http.response.start` via `MutableHeaders` only when this request minted. Never short-circuits, never 401s.
- `tests/test_service.py`: `make_client` now builds `TestClient(service.app, base_url="https://testserver", ...)` — httpx's jar withholds a `Secure` cookie over http, which would silently re-mint every request and pass the per-identity tests vacuously. `mint_cookie(monkeypatch, secret=...)` is the public seam later waves use to present a fixed real identity. Seven new API tests:
  - `test_mint_on_response_reaches_the_sse_stream` — cookieless `POST /research/stream` returns 200 SSE, the terminal `result` event arrives (stream body unaffected), and the response headers carry `ra_id` with HttpOnly/SameSite=Lax/Secure/Max-Age.
  - `test_mint_on_response_reaches_the_demo_page` / `..._a_json_route` — the FileResponse and JSON shapes, same assertions: all three shapes proven.
  - `test_a_valid_cookie_is_not_reminted` and `test_a_returning_caller_keeps_the_identity_they_were_minted` — mint only on absent/invalid, including the full jar round trip.
  - `test_invalid_token_reminted_never_401` — a tampered cookie on `POST /research/stream` gets `status != 401` (asserted explicitly), a completed stream, and a fresh mint that is not the forgery echoed back.
  - `test_identity_state_is_populated_before_the_handler` — `scope["state"]["identity"]` proven against the raw middleware, since no current route echoes it.

### README correction (commit a828ef1)

This wave falsified "480 tests" (504 collected now); updated. The "~25s" claim and the identity/anonymity narrative at line ~210 remain true until Waves 3/5 and are left to the waves that own them (`grep -in "token|identity|anonymous"` reviewed).

## Verification record

| Gate | Baseline | Result |
|------|----------|--------|
| `pytest tests/test_identity.py` | file absent | 17 passed (RED observed first: ImportError at collection) |
| `grep -c itsdangerous src/research_agent/identity.py` | n/a (itsdangerous not installed) | 0 |
| `grep -c compare_digest src/research_agent/identity.py` | 0 | 2 |
| `grep -c IdentityMiddleware src/research_agent/service.py` | 0 | 2 (import + registration) |
| `grep -c "https://testserver" tests/test_service.py` | 0 | 8 |
| `pytest tests/test_service.py -k "mint_on_response or invalid_token_reminted or identity"` | 0 collected | 7 passed |
| `pytest tests/test_service.py` | 85 passed | 92 passed |
| Full suite, plain | 443 passed / 37 skipped | **467 passed / 37 skipped** |
| Full suite, armed (:54329) | 479 passed / 1 skipped | **503 passed / 1 skipped** |
| ruff | clean | clean |

**Delta fully explained:** +24 passed in both runs = 17 `test_identity.py` unit tests + 7 new `test_service.py` API tests. Skip counts unchanged in both arms. Total collected 480 → 504.

## Deviations from Plan

None on substance. Two mechanical notes:

**1. [Rule 1 - Bug] Raw-middleware state test initially failed under `with TestClient(...)`**
- **Found during:** Task 2
- **Issue:** the context manager drives lifespan startup, which the bare ASGI stub answered with `http.response.start` — an assertion error inside Starlette, and the lifespan scope reached the stub before any http request.
- **Fix:** dropped the context manager for that one test (no lifespan needed against the raw middleware), with the reason in a comment.
**2. [Rule 3 - Blocking] Two lint-driven edits:** the identity docstring's "itsdangerous rejected" phrasing tripped the plan's own `grep -c itsdangerous == 0` gate (reworded to "a signing library"); ruff SIM105 and I001 required `contextlib.suppress` in the cookie parse and import reordering in service.py. Behaviour identical.

## Threat Flags

None — every surface this plan adds (the cookie trust boundary, the Set-Cookie attributes, the HMAC verify path, the free-to-mint Sybil acceptance) is already dispositioned in the plan's threat register (T-12-02-01..05), and each `mitigate` row is implemented and tested.

## Requirements

`REQ-demo-authentication` is deliberately left Pending: this plan is the groundwork half of Criterion 1, and the requirement's text is only demonstrable on the deployed service — that is Wave 5 (12-06), which sets the Fly secret and verifies in a real browser.

## Self-Check: PASSED

- src/research_agent/identity.py and tests/test_identity.py exist; service.py, tests/test_service.py, README.md modified as claimed
- Commits ea204cd, f7e2494, 39ea349, a828ef1 all on `gsd/phase-12-caller-identity`
