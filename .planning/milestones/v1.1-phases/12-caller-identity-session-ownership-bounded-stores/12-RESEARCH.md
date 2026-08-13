# Phase 12: Caller identity, session ownership, bounded stores - Research

**Researched:** 2026-08-05
**Domain:** Anonymous signed-token identity, Postgres-backed rate/cap state, multi-backend tenant scoping and expiry
**Confidence:** HIGH (all recommendations verified against the current tree, MDN, or first principles on machinery this repo already owns)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Identity: auto-issued and anonymous — LOCKED**
- First visit **mints a signed identity token silently** (no signup, no wall, no visible ceremony). The browser stores it and presents it on every call. A stranger from a résumé link never notices identity exists.
- Identity means **possession of the token**, not a verified person. Say so honestly in the docs.
- **The fairness ceiling is documented, not hidden:** clearing browser storage mints a fresh identity with fresh limits. Per-identity limits are a fairness improvement over per-IP, not a hard boundary.
- **CONSEQUENCE THE DESIGN MUST HONOUR: identities are free to mint, so per-identity limits cannot be the only bound on the bill.** The global rolling daily spend cap survives as the backstop.
- Rejected: GitHub OAuth, email magic link.

**The replacement guarantee (this reversal's ADR)**
- Retires "fairness keys on visitor IP via `TRUST_FORWARDED_FOR`". Replacement: **fairness keys on an auto-issued identity; spend remains bounded globally regardless of identity count.** The phase must record a new ADR and handle ADR-0006's expected supersession per `docs/adr/README.md` (verify whether full supersession or amendment is honest, and record which).

**Session ownership and expiry — LOCKED**
- Sessions carry the creator's identity. `/sessions` lists **only the caller's sessions**. `/sessions/{id}` for someone else's session refuses; researcher picks 403 vs 404 (prefer the shape that leaks least).
- **Expiry: 7 days after last activity.** Expired sessions stop resolving. Mechanics (lazy vs sweep) researcher's call; must behave identically on both machines.

**Note tenant scoping — IN SCOPE**
- Notes become scoped to the caller identity; recall retrieves only the caller's notes. All four backends (json, memory, chroma, pgvector) must behave identically, proven by the shared behavioural suite.
- The two orphaned notes from the 2026-08-04 deletions are dealt with here (delete or claim-by-nobody-and-expire; researcher proposes).

**Note bounds — mechanics researcher-proposed, ratified at plan review**
- At least one enforced bound. A note TTL matching session expiry is the obvious candidate.

**Spend-cap race — IN SCOPE**
- Cap and rate-limit state move to Postgres (shared); in-flight runs count against the cap. The "Read-only endpoints still work" property of the cap's 429 must survive (`limits.py`'s documented behaviour).

### Claude's Discretion
- Token format and transport (signed cookie vs bearer in localStorage; must work for both fetch and SSE paths), signing mechanism and key rotation posture.
- Schema changes for owner/expiry columns; migration of the new Postgres data (small — the store is days old; the volume backup is not in play).
- 403 vs 404 for foreign sessions; lazy vs background expiry; exact note-bound mechanics.
- How the operator (`SESSIONS_TOKEN`) retains a global admin view, if at all.

### Deferred Ideas (OUT OF SCOPE)
- `/health` outbound key-validity probe (bounded, cached) — backlog.
- Durable accounts (OAuth) as an upgrade path — later, if ever.
- `GET /metrics` auth — public by design for now.
- Embedding migration (Phase 13), cost multipliers (Phase 14).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-demo-authentication | Callers authenticate to an identity, not a shared token; rate limit and spend cap key on identity so `TRUST_FORWARDED_FOR` is no longer load-bearing for fairness | §Token design (signed HttpOnly cookie, stdlib HMAC, `IDENTITY_SIGNING_SECRET` Fly secret), §Minting middleware, §Limits store (per-identity Postgres rate window + reservation-based cap) |
| REQ-store-lifecycle-and-ownership | Notes carry ≥1 bound and note deletion is consistent across json/memory/chroma/pgvector; sessions carry owner + expiry; `/sessions` lists only the caller's; `/sessions/{id}` refuses others | §Ownership schema (owner column, derived expiry, lazy filter + opportunistic sweep), §Note tenant scoping (owner param across the 4-backend ABC), §Note TTL bound, §404-not-403 |
</phase_requirements>

## Summary

The whole phase can be built from machinery this repo already owns: stdlib `hmac` for token signing, the existing `db.Database` pool for shared limit state, `ALTER TABLE ADD COLUMN` under the existing advisory-locked lazy-DDL path for ownership, and the existing contract-suite pattern to prove four note backends behave identically. **No new dependency is needed or recommended.** The one structural addition is a small pure-ASGI middleware — the codebase's first — because it is the only mechanism that can set a cookie on every response shape the service produces (JSON, `FileResponse`, `StreamingResponse` SSE) from one choke point; FastAPI's dependency-injected `Response` parameter is silently ignored when a handler returns a `Response` directly, which every streaming route here does.

The three decisions the UI spec and CONTEXT deferred all resolve cleanly. **Transport: a signed, HttpOnly, SameSite=Lax cookie** — verified against MDN that `fetch()` defaults to `credentials: "same-origin"`, so all five page call sites carry it with zero JS changes, and HttpOnly means the token is invisible to script forever. **Foreign sessions: 404**, identical to nonexistent — 403 is an existence oracle, and Phase 10.5's leak-least posture points the same way. **Expiry: both lazy filtering and an opportunistic sweep**, honestly — lazy filtering is what makes both machines behave identically (it is a pure function of shared DB state, made literally identical by comparing against the database's own clock), and the sweep is what stops rows accumulating, which is the "stores grow without bound" defect this phase exists to close.

The spend-cap race fix is the one place with a real correctness subtlety: a single conditional `INSERT ... SELECT` is one round trip but **not** race-free under READ COMMITTED — two concurrent guards can both read a passing sum and both insert. The correct primitive is a short explicit transaction holding `pg_advisory_xact_lock` around check-plus-reserve (~2 extra round trips, ~6–10 ms at Phase 11's measured 2.8–3.4 ms per statement), which is nothing on a path whose downstream run takes tens of seconds. In-flight runs are counted by reservation rows settled at run completion, with a staleness cutoff so a crashed run cannot pin the budget forever.

**Primary recommendation:** signed cookie + stdlib HMAC + pure-ASGI mint middleware; a `LimitsStore` seam (memory/postgres) following the existing `get_*_store()` pattern; owner columns added via the existing lazy-DDL path; TTL-based note bound; 404 for foreign sessions; ADR-0007 supersedes ADR-0006 with explicit carry-forward of the parts that survive.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Identity mint + verification | API (ASGI middleware in `service.py` + new `identity.py`) | Browser (stores cookie automatically) | Signature verification must happen server-side; the browser's only job is presenting the cookie, which it does with zero JS |
| Token storage | Browser cookie jar (HttpOnly) | — | HttpOnly removes the token from script reach entirely; localStorage would require edits at five fetch call sites and be XSS-readable |
| Rate limit / spend cap state | Database (Postgres tables) | API (`limits.py` issues the SQL) | Two machines must see one truth; anything in process memory is now wrong twice (CONTEXT) |
| Session ownership + expiry | Database (owner column, updated_at) | API (filters in `sessions.py`) | Filtering must be identical on both machines → derive from shared state, not per-machine logic |
| Note tenant scoping | Database / store backends | Graph (`researcher_node` passes owner from state) | The scoping lives in each backend's `add`/`query`; the graph threads the owner through `AgentState` |
| Session list UI | Browser (per 12-UI-SPEC.md) | API (`GET /sessions` becomes caller-scoped) | UI contract already written; server owns which sessions are returned |
| Operator global view | API (`SESSIONS_TOKEN` bypass) | — | Admin access stays a server-side credential check, API-only, no UI |

## Standard Stack

### Core

No new libraries. The phase is built entirely on what is already installed and pinned:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| stdlib `hmac` + `hashlib` + `secrets` | Python 3.14 stdlib | Sign/verify identity tokens; generate identity ids and the dev fallback secret | `hmac.compare_digest` is already the codebase's constant-time comparison idiom (`limits.py:191`); HMAC-SHA256 over a UUID is ~15 lines and has no rotation/serialization needs that would justify a dependency `[VERIFIED: reads of src/research_agent/limits.py in this session]` |
| `psycopg` / `psycopg_pool` (already installed) | Pinned in pyproject | Rate/cap tables, owner columns, advisory locks | The Phase 11 pool, timeouts, and lazy-DDL advisory lock are exactly the machinery the new tables need `[VERIFIED: src/research_agent/db.py read this session]` |
| Starlette pure-ASGI middleware (ships with FastAPI, already installed) | — | Mint-on-response cookie setting | The only mechanism that attaches a header to every response shape incl. `StreamingResponse` SSE from one choke point |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib HMAC | `itsdangerous` | Rejected. Not installed (verified: `import itsdangerous` → ModuleNotFoundError). It buys timestamp-signing and serialization we don't need — the identity itself never expires (sessions do), and the payload is one opaque id. The repo already rejected the `pgvector` python package on the identical "one fewer dependency beats the adapter" argument (`memory.py:363-369`). `[VERIFIED: local import test]` |
| Signed HttpOnly cookie | Bearer token in localStorage + header | Rejected. Requires edits at all five fetch call sites (and any future `EventSource`), is readable by script (XSS-exfiltratable), and needs explicit page JS to persist. The cookie needs **zero** page changes: `fetch()` defaults to `credentials: "same-origin"` `[CITED: developer.mozilla.org/en-US/docs/Web/API/RequestInit — "Defaults to same-origin"]` |
| Pure-ASGI middleware | `BaseHTTPMiddleware` | Rejected. BaseHTTPMiddleware wraps the response in a background-task/streaming shim with documented interaction hazards around streaming bodies; a pure ASGI callable that rewrites the `http.response.start` message is ~30 lines, has no such hazards, and touches the SSE stream's headers only, never its body. `[ASSUMED — BaseHTTPMiddleware streaming hazards are training knowledge; the pure-ASGI approach is safe regardless, which is why it is the recommendation]` |
| Per-identity Postgres rate window | Keep in-memory `RateLimiter` keyed by identity | Rejected by locked decision: per-machine memory means two machines each grant a full quota — the exact defect named in CONTEXT |
| Advisory-lock transaction for cap reserve | Single conditional `INSERT…SELECT` CTE | The CTE is one round trip but races under READ COMMITTED (both concurrent readers see the pre-insert sum). Kept as the shape of the SQL, but wrapped in `pg_advisory_xact_lock` — see Patterns |

**Installation:** nothing to install.

## Package Legitimacy Audit

This phase installs **no external packages**. All recommended machinery is Python stdlib or already-pinned dependencies (`psycopg`, `psycopg-pool`, `fastapi`/`starlette`). `itsdangerous` was evaluated and **rejected**, not added.

**Packages removed due to slopcheck [SLOP] verdict:** none (nothing proposed)
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Browser (index.html — 5 call sites, ZERO changes for transport)
   │  cookie: ra_id=v1.<id>.<sig>  (HttpOnly, SameSite=Lax, Secure, Max-Age 400d)
   ▼
┌───────────────────────────── FastAPI app ─────────────────────────────┐
│  IdentityMiddleware (pure ASGI, NEW)                                  │
│    verify cookie → scope state.identity = id                          │
│    invalid/absent → mint new id, remember to Set-Cookie on the way out│
│    on http.response.start: append Set-Cookie iff minted this request  │
│         │                                                             │
│         ▼                                                             │
│  guard (Depends) ──► limits.enforce(request, metrics, limits_store)   │
│    1. check_rate_limit(identity)  ── 1 SQL stmt ──► rate_hits table   │
│    2. check_daily_cap(...)        ── advisory-lock txn ──►            │
│         spend(runs, 24h) + reservations(in-flight) + est ≤ cap?       │
│         yes → INSERT reservation row · no → 429 (verbatim message)    │
│         │                                                             │
│         ▼                                                             │
│  route handler ──► graph run (owner threaded via AgentState["owner"]) │
│    researcher_node: memory().query(task, owner=o) / .add(text, owner) │
│    on_complete/_failed_record: settle reservation (DELETE row)        │
│         │                                                             │
│  sessions_router (require_session_access, RENAMED dependency)         │
│    identity → owner-scoped list/get/trace/delete (foreign ⇒ 404)      │
│    X-Demo-Token == SESSIONS_TOKEN → operator: unscoped (all sessions) │
└───────────────────────────────────────────────────────────────────────┘
   │ one shared psycopg pool per machine (Phase 11)
   ▼
Supabase Postgres (session-mode pooler)
   sessions(+owner)  runs  research_notes(+owner)  rate_hits(NEW)  run_reservations(NEW)
```

### Recommended Project Structure

```
src/research_agent/
├── identity.py        # NEW: token mint/verify, cookie constants, IdentityMiddleware
├── limits.py          # REWORKED: LimitsStore ABC + InMemoryLimits + PostgresLimits;
│                      #   enforce() keys on identity; 429 messages preserved
├── service.py         # middleware registration; require_session_access; owner threading
├── sessions.py        # owner column both schemas; owner/expiry filters; sweep
├── memory.py          # owner param on add()/query() across all four backends; TTL
├── graph.py           # AgentState gains "owner"; initial_state/followup_state accept it
└── db.py              # small addition: Database.transaction() for the cap reservation
```

### Pattern 1: Token format and signing (stdlib, stateless, shared secret)

**What:** `v1.<id>.<sig>` where `id = uuid4().hex` and `sig = HMAC-SHA256(secret, "v1." + id)` hex. Identity *is* possession of a validly-signed id — no server-side identity table exists or is needed. Both machines verify tokens minted by either because they share one secret.

**Secret:** `IDENTITY_SIGNING_SECRET`, set once as a Fly secret (Fly secrets are app-wide, so both machines receive it). When unset (local dev, tests): generate a per-process random secret via `secrets.token_hex(32)` and log a warning — the demo still works; on a two-machine fleet without the secret the degradation is per-machine identity (a caller bounced between machines re-mints), which is survivable because the global cap still bounds the bill. `/health`'s `credentials` block should report `"identity_signing": bool(...)` presence-not-value, same as the API keys.

**Rotation posture:** single secret; rotating it silently re-mints every identity on next request (old cookies fail verification → middleware mints fresh). Limits reset for everyone; the global cap backstops. Document, don't build dual-key verification.

```python
# identity.py — the whole verification surface
import hmac, hashlib, os, secrets, uuid

_COOKIE = "ra_id"
_VERSION = "v1"

def _secret() -> bytes: ...  # env or per-process fallback + warning

def mint() -> str:
    ident = uuid.uuid4().hex
    return f"{_VERSION}.{ident}.{_sign(ident)}"

def _sign(ident: str) -> str:
    return hmac.new(_secret(), f"{_VERSION}.{ident}".encode(), hashlib.sha256).hexdigest()

def verify(token: str) -> str | None:
    """The identity id, or None. None means 'mint a new one', never 401."""
    try:
        version, ident, sig = token.split(".")
    except ValueError:
        return None
    if version != _VERSION or not ident.isalnum():
        return None
    return ident if hmac.compare_digest(sig, _sign(ident)) else None
```

### Pattern 2: Mint-on-response via pure ASGI middleware (never 401)

**What:** one middleware resolves-or-mints identity before the app runs and appends `Set-Cookie` on the way out only when it minted. A request with no/invalid cookie is served normally under the fresh identity — the first-ever `POST /research/stream` succeeds AND receives the cookie in the SSE response headers (headers go out at `http.response.start`, before the stream body; nothing about SSE prevents Set-Cookie).

**Why not a FastAPI dependency with a `Response` parameter:** when a handler returns a `Response` directly — which `/research/stream`, `/sessions/{id}/ask/stream` (StreamingResponse) and `GET /` (FileResponse) all do — FastAPI ignores headers set on the injected `Response` parameter. The middleware is the only single choke point that covers every response shape. `[VERIFIED: service.py routes return StreamingResponse/FileResponse directly — read this session; the FastAPI direct-response caveat is CITED: fastapi.tiangolo.com/advanced/response-directly — "FastAPI won't do any … conversion" for direct responses]`

```python
class IdentityMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cookies = ...  # parse Cookie header from scope["headers"]
        ident = verify(cookies.get(_COOKIE, ""))
        minted = None
        if ident is None:
            minted = mint()
            ident = verify(minted)  # extract the id
        scope.setdefault("state", {})["identity"] = ident

        async def send_with_cookie(message):
            if minted and message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("set-cookie",
                    f"{_COOKIE}={minted}; Max-Age=34560000; Path=/; "
                    f"HttpOnly; SameSite=Lax; Secure")
            await send(message)

        await self.app(scope, receive, send_with_cookie)
```

**Cookie attributes, each justified:** `HttpOnly` (script never needs it — page and API are same-origin, fetch sends it automatically); `SameSite=Lax` (sent on top-level navigation from the résumé link AND on all same-origin fetches; blocks cross-site POSTs carrying the cookie); `Secure` (Fly serves HTTPS; modern browsers treat localhost as a secure context so dev still works — **but see Pitfall 2 for TestClient**); `Max-Age` ~400 days (Chrome's cap; identity outlives the 7-day session expiry deliberately — a returning visitor keeps their identity, their old sessions are gone, matching the footer copy); `Path=/`. No `Domain` attribute (host-only is tighter).

**CSRF note:** cookie auth reintroduces CSRF surface in principle, but three properties close it here: SameSite=Lax strips the cookie from cross-site POSTs; every state-changing route requires a JSON body (`AskRequest`), and cross-origin JSON POSTs trigger a preflight this service never approves (no CORS middleware is configured — verified absent from `service.py`); and the demo token/sessions token paths still require the explicit header. State this in the ADR rather than adding CSRF tokens.

### Pattern 3: `LimitsStore` seam — memory and postgres backends

**What:** follow the exact `SessionStore`/`MetricsStore` shape: an ABC with `check_rate(identity, limit, window) -> (allowed, retry_after)`, `reserve(run_id, identity, est_usd, cap) -> bool` (or a spent/reserved query pair), `settle(run_id)`, plus `get_limits_store()` defaulting on `DATABASE_URL`. The in-memory backend keeps today's `RateLimiter` semantics (now keyed by identity, not IP) so SQLite-only deployments and the fast test path still work; the Postgres backend is what production uses.

**Rate limit (single statement, one round trip):**

```sql
-- allowed iff the identity has fewer than $limit hits in the window; records the hit
INSERT INTO rate_hits (identity, ts)
SELECT %(id)s, EXTRACT(EPOCH FROM now())
WHERE (SELECT COUNT(*) FROM rate_hits
       WHERE identity = %(id)s
         AND ts > EXTRACT(EPOCH FROM now()) - %(window)s) < %(limit)s
RETURNING ts;
```

Row returned → allowed. No row → refused; a second cheap read of `MIN(ts)` in the window computes `Retry-After` (or fold it into one statement with a CTE returning both). A small race exists (two concurrent inserts can both pass the subquery); for a *fairness* tool the overshoot bound is the number of concurrent requests, which is acceptable — the spend cap is where strictness matters. Opportunistic purge: `DELETE FROM rate_hits WHERE ts < cutoff` every Nth check (the in-memory limiter's `SWEEP_EVERY = 500` is the precedent).

**Spend cap with in-flight reservation (reserve-then-settle, race-free):**

The honest answer to "can a single SQL statement do check+reserve atomically": **one statement is one round trip but is NOT race-free under READ COMMITTED** — two concurrent guards each evaluate the `SELECT` against a snapshot that excludes the other's uncommitted insert, and both reserve. The systematic 3× overshoot (counting only completed runs) is fixed by reservations alone; the residual concurrency race is fixed by serialising check+reserve behind `pg_advisory_xact_lock` in a short explicit transaction:

```sql
BEGIN;
SELECT pg_advisory_xact_lock(<CAP_LOCK_KEY>);          -- xact-scoped: auto-released at COMMIT
INSERT INTO run_reservations (run_id, identity, est_usd, created_at)
SELECT %(run_id)s, %(id)s, %(est)s, EXTRACT(EPOCH FROM now())
WHERE (
    COALESCE((SELECT SUM(cost_usd) FROM runs
              WHERE created_at >= EXTRACT(EPOCH FROM now()) - 86400), 0)
  + COALESCE((SELECT SUM(est_usd) FROM run_reservations
              WHERE created_at >= EXTRACT(EPOCH FROM now()) - 900), 0)
  + %(est)s
) <= %(cap)s
RETURNING run_id;
COMMIT;
```

- **Requires a tiny `Database.transaction()` addition** — the pool runs `autocommit=True`, and `pg_advisory_xact_lock` needs a real transaction to scope to. psycopg3's `conn.transaction()` context manager on a checked-out connection is the right tool. Use the **transaction-scoped** lock (not session-scoped) precisely because it cannot leak across pool checkouts — the failure mode `db.py:_apply_schema`'s docstring warns about. Use a **different lock key** than `SCHEMA_LOCK_KEY` (e.g. `zlib.crc32(b"research_agent.spendcap")`).
- **Reservation estimate:** `DEMO_RESERVED_RUN_USD`, default **0.20** (observed runs ≈ $0.15; `AGENT_MAX_RUN_COST_USD`'s 1.00 default would let only 5 concurrent runs against the $5 cap, which throttles the demo far below its real spend — verified `usage.py:198-203` default is 1.00). Ratify at plan review.
- **Settle:** `DELETE FROM run_reservations WHERE run_id = %s` in `on_complete` AND in `_failed_record`'s path (both already funnel through `service._execute`/`_stream`, which are the two choke points). The real cost lands in `runs` via `metrics.record` as today — `spend_since` is unchanged.
- **Crash leak:** a run that dies without settling leaves a reservation. The 900-second staleness cutoff in the reserved-sum (runs take tens of seconds; nothing legitimate runs 15 minutes) means a leaked reservation stops counting on its own. An opportunistic `DELETE ... WHERE created_at < now-900` keeps the table tiny.
- **The 429 contract:** the cap refusal must keep the documented "Read-only endpoints still work." sentence and the `Retry-After` header, and `guard` must stay OFF the session reads (ADR-0006 part 3 survives — see ADR section).

**Hot-path budget, confirmed affordable:** guard adds 1 statement (rate) + 1 short transaction ≈ 3 round trips (cap) ≈ 4 round trips total. At Phase 11's measured 2.8–3.4 ms p50 per probe statement, that is **~12–14 ms p50** added to endpoints whose downstream work takes 30–90 seconds and costs $0.15. `/demo` (`limits.status`) gains ~2 reads (~6 ms) on a page-load poll. Nothing here approaches the `/health` 9 s ceiling, and `/health` itself is untouched. `[VERIFIED: figures from Phase 11 measurements quoted in CONTEXT; arithmetic this session]`

### Pattern 4: Ownership schema and lazy migration

**Current schema, exactly (verified this session):**
- Postgres `sessions`: `id TEXT PK, created_at DOUBLE PRECISION, updated_at DOUBLE PRECISION, task TEXT, turns INTEGER, state JSONB` + index `sessions_updated_at`.
- SQLite `sessions`: same shape with `REAL`/`TEXT state`.
- Postgres `research_notes` (pgvector): `id BIGSERIAL PK, text TEXT, embedding vector(1024), created_at TIMESTAMPTZ DEFAULT now()` + HNSW index. **Note: `created_at` already exists here** — only `owner` is missing.
- json/memory stores: list of `{"text", "embedding"}` dicts — no owner, no timestamp.
- chroma: documents + embeddings, ids only — no owner metadata.

**Migration path:** append idempotent `ALTER TABLE`s to the existing schema blocks; they run under the existing advisory lock on first use, so the days-old live table is migrated lazily on the first post-deploy request, with both machines serialised — no migration script, no downtime:

```sql
-- appended to POSTGRES_SCHEMA in sessions.py
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS sessions_owner ON sessions (owner, updated_at DESC);

-- appended to PgVectorMemoryStore._ensure_schema
ALTER TABLE research_notes ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT '';
```

SQLite has no `ADD COLUMN IF NOT EXISTS`: probe `PRAGMA table_info(sessions)` for the column (or catch `sqlite3.OperationalError: duplicate column name`) in `SQLiteSessionStore.__init__`. Both are cheap and idempotent.

**No `expires_at` column.** Expiry is *derived*: a session is live iff `updated_at > now − 7·86400`. Deriving it from `updated_at` means a follow-up automatically renews the session with zero extra writes (`append_turn` already touches `updated_at`), and there is no second timestamp to drift out of sync.

**Orphan semantics (the 2 live sessions, owner=''):** identity ids are 32-hex uuids; the empty string matches no caller. Orphans therefore stop resolving for everyone the moment the owner filter lands, and the sweep deletes them once their `updated_at` passes the 7-day line — which for rows from 2026-08-04 is 2026-08-11 at the latest. **Recommendation: claim-by-nobody-and-expire.** No manual deletion step, no special case in code, and the operator token can still inspect them until they age out.

### Pattern 5: Expiry mechanics — lazy filter AND opportunistic sweep (both, honestly)

- **Lazy filter (correctness):** `get()`, `list()`, and the ownership `_require` all carry `AND updated_at > EXTRACT(EPOCH FROM now()) - %(ttl)s`. Using the **database's clock** in the comparison, not `time.time()`, makes both machines evaluate expiry against one clock — the design that *cannot* diverge. (SQLite backend: single machine by construction; `time.time()` is fine there, and the contract suite pins identical observable behaviour.)
- **Opportunistic sweep (boundedness):** on each `create()` (a rare, already-expensive event — one per completed run), issue `DELETE FROM sessions WHERE updated_at < cutoff`. DELETE is idempotent; two machines sweeping concurrently is harmless. No background thread, no scheduler, nothing per-machine to drift. Deleting a session's rows does **not** cascade to notes — notes have their own TTL (below) and are not keyed by session.
- Expired-but-unswept rows are invisible (lazy filter) and transient (next completed run sweeps). Config: `SESSION_TTL_DAYS` default 7, read per call per the env convention.

### Pattern 6: Note tenant scoping across four backends + TTL bound

**ABC change** (`memory.py:110-141`): `add(self, text: str, owner: str = "") -> None` and `query(self, query_text, top_k=…, min_similarity=…, owner: str = "") -> list[str]`. Default `""` keeps the REPL (`chat.py`), `__main__` demo, and eval harness call sites compiling; the service always passes a real identity. `owner=""` retrieves only `owner=""` notes — scoping is exact-match, never "empty means all".

**Threading:** `AgentState` gains `"owner": str`; `initial_state(task, owner="")` and `followup_state` carry it; `researcher_node` becomes `store.query(state["task"], top_k=3, owner=state["owner"])` and `store.add(f"[{state['task']}] {notes}", owner=state["owner"])`. Service handlers pass `request.state.identity` (or `scope["state"]["identity"]`) into `initial_state`/`followup_state`. This is the *injection fix*: one visitor's untrusted notes can no longer reach another visitor's critic.

**Per backend:**

| Backend | Owner | TTL timestamp | Mechanics |
|---------|-------|---------------|-----------|
| json / memory (`_BruteForceStore`) | entry dict gains `"owner"` | gains `"created_at"` (`time.time()`) | `query` filters snapshot by owner + age; `add` opportunistically drops expired entries before persist. Legacy JSON entries without keys read as `owner=""`, `created_at=0` → expired → evicted on next add |
| chroma | `metadatas=[{"owner": o, "created_at": t}]` | same metadata | `collection.query(..., where={"owner": o})`; TTL filtered post-query on metadata (Chroma `where` supports `$gt` on numeric metadata, but post-filtering in Python keeps all four backends' semantics byte-identical — prefer that) |
| pgvector | new `owner TEXT NOT NULL DEFAULT ''` | **`created_at` already exists** (TIMESTAMPTZ) | `WHERE owner = %s AND created_at > now() - interval '7 days'` added to the existing query; `add` inserts owner |
| behavioural suite | `tests/test_store_contract.py` `notes` fixture (currently json/memory/pgvector; **chroma is absent from the parametrisation — check whether chromadb is installed in CI before promising the 4th arm, and gate it like Postgres if not**) | | Suite gains: owner-A notes invisible to owner-B; `owner=""` isolation; expired notes not recalled; identical across all arms |

**The note bound — recommendation to ratify:** **TTL = `SESSION_TTL_DAYS` (7 days from `created_at`)**, enforced by lazy filter in `query` + opportunistic sweep in `add`. It aligns exactly with the session-hygiene posture, needs no new judgement calls, and the footer copy in 12-UI-SPEC.md already promises it ("…and expire after 7 days of inactivity" — note: the copy says *inactivity* but note TTL is from *creation*; notes are write-once so created==last-activity, no contradiction). **Dedup-on-write: evaluated, rejected** — exact-text dedup is trivial in pgvector (unique index on md5) but has no natural equivalent that behaves identically in chroma/json/memory without hand-rolling per backend, and the TTL alone satisfies "at least one enforced bound". Summarisation: rejected as an LLM-spend loop inside the thing that bounds spend.

**Orphan notes (the 2 from 2026-08-04):** same as sessions — `owner=''` matches nobody, TTL collects them. For pgvector their `created_at` is real, so they expire on schedule; delete-by-hand is unnecessary.

**pgvector caveat to note in the plan:** HNSW with a `WHERE` clause post-filters candidates, so a filtered query can return fewer than `top_k` even when matches exist. At demo scale (hundreds of notes) this is irrelevant, but the plan should not add a gate asserting "exactly k results" against the pgvector arm. `[ASSUMED — pgvector filtered-HNSW behaviour is training knowledge; consistent with pgvector docs' iterative-scan discussion]`

### Pattern 7: 403 vs 404, and the session-route dependency surgery

**404 for foreign AND expired sessions, byte-identical to nonexistent:** `HTTPException(404, f"No session {session_id!r}.")` — the existing message. 403 confirms a valid session id exists (an existence oracle on ids that appear in shared URLs, logs, or screenshots). Phase 10.5's 401-before-404 posture was "leak least"; 404-for-everything-you-don't-own is its continuation. The UI spec already renders 403 and 404 identically ("That session has expired"), so nothing on the page distinguishes them either.

**Route dependency changes (exact, for the walker test):**

| Route | Today | After |
|-------|-------|-------|
| `GET /sessions` | `require_sessions_token` (router) | `require_session_access` (router) — resolves to `("identity", id)` or `("operator", None)`; handler filters `WHERE owner = id` or unscoped for operator |
| `GET /sessions/{id}`, `/{id}/trace` | `require_sessions_token` | `require_session_access`; `_require` gains owner check → 404 for foreign/expired; operator sees all |
| `DELETE /sessions/{id}` | `require_sessions_token` + `check_rate_limit` | `require_session_access` + `check_rate_limit` (identity-keyed now); owner-or-operator only, foreign → 404 |
| `POST /sessions/{id}/ask`, `/ask/stream` | `guard` only (anonymous by design) | `guard` (now identity-keyed internally) — **dependency set unchanged**; ownership enforced inside the handler via the same `_require(store, session_id, identity)` → foreign/expired = 404. The demo's second turn cannot break: the follow-up caller holds the cookie that created the session (minted at page load, before the first question) |
| `POST /research`, `/research/stream` | `guard` | `guard` — unchanged set; identity read from scope state inside `enforce` |
| `GET /demo` | none | none — but `limits.status` becomes identity-aware (adds per-identity remaining figures for the reworded `#limits` line) |

**`require_session_access` semantics:** if `X-Demo-Token` matches `SESSIONS_TOKEN` (fail-closed lookup exactly as today) → operator, unscoped. Otherwise → the request's minted-or-verified identity (which always exists — the middleware guarantees it), scoped. **The fail-closed property inverts meaning:** an unset `SESSIONS_TOKEN` no longer closes the tree to everyone — visitors reach their *own* sessions via identity; unset only closes the *operator* view. That is the honest post-Phase-12 reading and must be stated in the ADR.

**Test extension (not bypass):** in `tests/test_service.py`, `AUTH_DEPENDENCIES = {"guard", "require_sessions_token"}` becomes `{"guard", "require_session_access"}`. The non-vacuity counts (`>= 6` route objects under `/sessions`, `>= 4` in the delete-meter test, `== 3` GETs) all still hold — no session routes are added or removed. New structural assertions to add: every `sessions_router` route carries `require_session_access`; the ask routes still do NOT carry it (ownership is in-handler, and guarding them with the session dependency would re-fight ADR-0006 part 4's grouping-by-dependency argument); no session route acquires `check_daily_cap` (existing assertion survives verbatim).

### Pattern 8: ADR-0007 and the fate of ADR-0006

**New record: ADR-0007 — "Fairness keys on an auto-issued anonymous identity; the global cap bounds the bill."** Contents: the reversal of "rate-limited, not authenticated"; the replacement guarantee verbatim from CONTEXT; the fairness ceiling (free-to-mint identities) stated as a documented property; `TRUST_FORWARDED_FOR` demoted from load-bearing to vestigial (keep the code path — `client_ip` may still serve logging — but nothing keys fairness on it).

**Supersession verdict — supersede, with explicit carry-forward.** Verified against `docs/adr/README.md`'s convention: there is no "Amended" status — the convention offers exactly two moves (status-line supersession, or a new record). ADR-0006's own §Expected reversal pre-named Phase 12 and predicted "parts 1 and 2 are the likely casualties." That prediction is correct in substance: the shared token stops being *the visitor's* credential for session reads (part 1's stated purpose), and fail-closed inverts meaning for visitors (part 2). Parts 3 (guard stays off the reads) and 4 (structural router grouping) survive intact. The honest execution under the convention: ADR-0007's status line reads `**Status:** Accepted — supersedes ADR-0006`, ADR-0006's becomes `**Status:** Superseded by ADR-0007 (Phase 12)`, the index updates both cells, and **ADR-0007's Decision section explicitly restates what it carries forward** (SESSIONS_TOKEN survives as the fail-closed *operator* credential; the read/cap decomposition and router grouping are reaffirmed; DEMO_TOKEN-never-in-production still holds). That is standard Nygard practice — a superseding record may re-affirm parts — and is more honest than leaving 0006 "Accepted" while its central sentence ("the credential for the session read/delete endpoints") is no longer the visitor-path truth. Bring this to plan review as the recommendation; if the user prefers amendment-in-place, that requires extending the convention in `docs/adr/README.md` first, which is a bigger change than the supersession.

### Anti-Patterns to Avoid

- **401-then-retry for missing identity:** breaks a first-time caller's `POST /research/stream` mid-flight and adds a visible failure the UI spec forbids. Mint-on-response, always.
- **Guarding the ask routes with the session-tree dependency:** re-litigates ADR-0006 part 4; ownership belongs in `_require`, dependency sets stay grouped by *what they protect*.
- **A background sweeper thread/scheduler:** per-machine timers drift and duplicate; opportunistic sweeps on writes are idempotent and identical everywhere.
- **`SELECT`-then-`INSERT` as two round trips for the cap:** the race CONTEXT names. One transaction, one advisory lock.
- **Keying the new rate table on `(identity, ip)` "just in case":** re-introduces `TRUST_FORWARDED_FOR` as load-bearing through the back door.
- **`check=` pool callback or session-scoped advisory locks:** both explicitly rejected in `db.py` comments with measured reasons; the cap lock must be `pg_advisory_xact_lock` (transaction-scoped) for exactly the leak reason `_apply_schema` documents.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Constant-time comparison | byte-loop comparison | `hmac.compare_digest` | Already the codebase idiom; timing-safe by contract |
| Token signing | custom hash concatenation | `hmac.new(..., hashlib.sha256)` | Naive `sha256(secret+msg)` is length-extension-vulnerable; HMAC is the construction that isn't |
| Cross-machine mutual exclusion | row polling / lock tables | `pg_advisory_xact_lock` | Already proven in this repo (schema lock); xact scope self-releases |
| Cookie parsing in middleware | regex over the header | `starlette.requests` cookie parsing / `http.cookies.SimpleCookie` | Cookie header quoting rules are fiddlier than they look |
| Transaction management | manual BEGIN/COMMIT strings | psycopg3 `conn.transaction()` | Correct rollback on exception for free; plays with the pool checkout |

**Key insight:** every hard sub-problem here (timing-safe compare, HMAC, advisory locks, pooled transactions, lazy DDL) already has a proven instance in this codebase or the stdlib. The phase's risk is wiring, not invention — which is why zero new dependencies is the right call.

## Runtime State Inventory

This phase alters live stores; the grep-clean question is "what runtime state holds the old shape after the code changes":

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | 2 live sessions (no owner column/value) and 2 orphaned notes in Supabase; `runs` table (untouched) | Lazy `ALTER TABLE ADD COLUMN ... DEFAULT ''` via existing advisory-locked DDL; orphans expire via TTL — **no data migration script** |
| Live service config | Fly secrets: `IDENTITY_SIGNING_SECRET` must be SET before/with the deploy (`fly secrets set` restarts machines) | New secret; document in OPERATIONS + `.env.example` |
| Browser state | Visitors' browsers hold no cookie yet; first post-deploy request mints | None — mint-on-response handles it |
| Env vars | `TRUST_FORWARDED_FOR` becomes non-load-bearing (may remain set, harmless); new `SESSION_TTL_DAYS`, `DEMO_RESERVED_RUN_USD` optional with defaults | Docs only |
| Build artifacts | None — single image, no schema baked in | None — verified: schema lives in code, applied lazily |
| Local dev | `sessions.db` at repo root and `agent_memory_store.json` carry old shapes | SQLite column probe handles the db; JSON entries without owner/created_at read as expired orphans — verified both files exist in tree |

## Common Pitfalls

### Pitfall 1: The cap's reservation never settles on the streaming path's error arm
**What goes wrong:** `_stream` catches all exceptions internally (the SSE contract), so a naive "settle in the route handler's except" never fires; the reservation leaks until the 900 s cutoff on every failed stream.
**How to avoid:** settle inside `_execute` and `_stream` themselves — the exact two places `metrics.record` already lives; success and failure both pass through them. The staleness cutoff remains the backstop for a hard process crash only.
**Warning signs:** `/demo` shows spent+reserved near cap while `/metrics` shows low spend.

### Pitfall 2: `Secure` cookie + `TestClient`'s default `http://testserver` base URL
**What goes wrong:** httpx's cookie jar honours the `Secure` flag — a Secure cookie set in a response is silently NOT sent back over an `http://` base URL, so every identity test passes the mint and fails the presentation, or worse, each request mints a fresh identity and the per-identity rate-limit tests never trip.
**How to avoid:** construct `TestClient(app, base_url="https://testserver")` in `make_client` (one line). Do NOT make `Secure` conditional on an env var — a prod/test behaviour fork in a security attribute is how attributes silently disappear.
**Warning signs:** rate-limit tests need N× more requests than the limit to 429. `[ASSUMED — httpx cookiejar Secure handling is training knowledge; the one-line https base_url is safe either way and should be adopted regardless]`

### Pitfall 3: FastAPI ignores dependency-set cookies on direct `Response` returns
**What goes wrong:** a `caller_identity(response: Response)` dependency appears to work on JSON routes and silently drops the Set-Cookie on `/research/stream`, `/ask/stream`, and `GET /` — the three routes a first-time visitor hits first.
**How to avoid:** the pure-ASGI middleware (Pattern 2). Do not mix mechanisms.

### Pitfall 4: The single-statement cap check that "greps atomic"
**What goes wrong:** `INSERT ... SELECT ... WHERE (sum) <= cap` looks atomic and passes every sequential test; under 2 machines × 16 concurrency, READ COMMITTED lets N concurrent guards all pass. This is the 3× overshoot reborn at smaller amplitude.
**How to avoid:** the advisory-lock transaction. **Gate it behaviourally:** a two-thread test against real Postgres where both threads race check+reserve with the cap set to admit exactly one — the same two-connection-exclusivity shape plan 11-02 used for the schema lock.

### Pitfall 5: Middleware breaks `TestClient` lifespan or dependency overrides
**What goes wrong:** tests monkeypatch `service.get_sessions` etc. via `app.dependency_overrides`; a middleware is not a dependency and cannot be overridden that way. Tests that need a fixed identity have no seam.
**How to avoid:** the middleware reads the cookie; tests mint real cookies via the public `identity.mint()` (with a monkeypatched secret) and set them on the client — testing the real path rather than overriding it. Provide `identity.mint()` as a public function for exactly this.

### Pitfall 6: Renewing `updated_at` on read
**What goes wrong:** if `get()` bumps `updated_at`, listing your own sessions renews them forever and "7 days after last activity" becomes "7 days after last glance" — stores never shrink.
**How to avoid:** activity = writes only (`create`, `append_turn`). Reads never touch `updated_at`. State this in the store docstring; add a contract test.

### Pitfall 7: The chroma arm of the behavioural suite may not exist yet
**What goes wrong:** CONTEXT and the success criteria say "all four backends… proven by the shared behavioural suite", but the current `notes` fixture parametrises json/memory/pgvector only; promising a chroma gate without chromadb installed in CI yields either a red build or a silently-skipped arm (the vacuous-gate failure mode).
**How to avoid:** planner must check whether `chromadb` is in the dev extra / CI image. If not: add it to the dev extra (it is a test-only need) or gate the chroma arm with a skip-detector exactly like `REQUIRE_POSTGRES` — and state the measured baseline ("chroma arm: N tests, skipped locally, exercised in CI") in the gate.

### Pitfall 8: `limits.status` / `/demo` shape change breaks the page's branches
**What goes wrong:** the page's `refreshLimits()` reads `rate_limit_per_hour`, `daily_cap_usd`, `spent_24h_usd`, `token_required`; the UI spec's new copy needs per-identity wording. Removing or renaming existing keys breaks the deployed page during the deploy window (two machines roll sequentially).
**How to avoid:** additive only — keep every existing key, add new ones. The page ships in the same deploy but the API must tolerate the old page for the rollout minutes.

## Code Examples

### Threading identity into a run (service.py)

```python
# Source: current service.py shapes, read this session
@app.post("/research/stream", tags=["research"], dependencies=[Depends(guard)])
def research_stream(body, request: Request, store=..., metrics=...):
    question = body.cleaned()
    owner = request.state.identity          # set by IdentityMiddleware, always present
    return _sse_response(
        initial_state(question, owner=owner), metrics,
        lambda state: store.create(question, state, owner=owner),
    )
```

### Owner-scoped `_require` (the one 404 shape)

```python
def _require(store: SessionStore, session_id: str, owner: str, *, operator: bool = False):
    session = store.get(session_id)          # get() already applies the expiry filter
    if session is None or (not operator and session.owner != owner):
        raise HTTPException(404, f"No session {session_id!r}.")   # identical for missing/foreign/expired
    return session
```

### SQLite column probe (sessions.py `__init__`)

```python
cols = {row[1] for row in self._conn.execute("PRAGMA table_info(sessions)")}
if "owner" not in cols:
    self._conn.execute("ALTER TABLE sessions ADD COLUMN owner TEXT NOT NULL DEFAULT ''")
```

### Database.transaction() addition (db.py)

```python
@contextmanager
def transaction(self):
    """A cursor inside an explicit transaction on one checked-out connection.
    For the spend-cap reserve: pg_advisory_xact_lock needs a real transaction
    (autocommit=True means there is none by default), and the xact scope is what
    guarantees the lock cannot leak across pool checkouts."""
    with self._pool.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                yield cur
```
*(Checkout-retry semantics should mirror `cursor()`; keep the PoolTimeout pass-through arm.)*

## State of the Art

| Old Approach (current tree) | Current Approach (this phase) | Impact |
|--------------|------------------|--------|
| Per-IP in-memory sliding window (`RateLimiter`) | Per-identity Postgres window, in-memory backend retained for SQLite deployments | Fairness survives 2 machines; `TRUST_FORWARDED_FOR` demoted |
| Cap counts completed runs only | Reservation rows count in-flight; advisory-lock atomicity | The ~3× concurrency overshoot closes |
| `SESSIONS_TOKEN` = the visitor's credential | Identity ownership for visitors; token = operator view | ADR-0006 superseded by ADR-0007 with carry-forward |
| Sessions immortal, notes immortal and communal | 7-day derived expiry; owner-scoped notes with 7-day TTL | Stores self-clean; cross-visitor prompt-injection path via shared notes closes |

**Deprecated/outdated:** nothing removed from the dependency set; `client_ip()` remains for logging but stops keying anything.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | httpx/TestClient cookie jar withholds `Secure` cookies over `http://` base URLs | Pitfall 2 | Low — the `https://testserver` base_url is a safe one-line change either way; verify with a 2-minute spike test in Wave 0 |
| A2 | Chroma `collection.query(where={"owner": ...})` metadata filtering works as described on the installed chromadb version | Pattern 6 | Medium — if the installed version's `where` syntax differs, post-filter in Python (already the recommendation for TTL); verify when writing the chroma arm |
| A3 | pgvector HNSW post-filters `WHERE` clauses (can return < top_k) | Pattern 6 caveat | Low — only affects what gates may assert, not correctness at demo scale |
| A4 | `BaseHTTPMiddleware` streaming hazards justify pure-ASGI | Alternatives | None in practice — pure-ASGI is correct regardless of whether BaseHTTPMiddleware would have worked |
| A5 | `DEMO_RESERVED_RUN_USD` default 0.20 is the right conservatism (obs. ~$0.15/run, per-run hard cap $1.00) | Pattern 3 | Low — a tunable env var with a default; user ratifies at plan review |
| A6 | Fly secrets propagate to both machines on `fly secrets set` (staged restart) | Pattern 1 | Low — standard Fly behaviour; deploy checklist should verify `/health` reports the credential present on both machines |

## Open Questions

1. **Does the operator listing (`SESSIONS_TOKEN` view) stay at `GET /sessions` or move?**
   - What we know: Phase 10.5 notes flagged "a public demo arguably should not have a global listing endpoint at all" as a Phase 12 question. The recommendation above keeps `GET /sessions` dual-mode (scoped for visitors, unscoped for operator) — smallest surface change, and the walker test's counts survive.
   - What's unclear: whether the user prefers the operator view removed entirely (DELETE-only admin) now that visitors self-serve.
   - Recommendation: keep dual-mode; note in the ADR that the global listing now requires the fail-closed operator token, which answers the 10.5 concern.
2. **Is chromadb installed in CI / the dev extra?** (Pitfall 7). Planner must check `pyproject.toml`'s extras before promising the fourth behavioural-suite arm and set the gate baseline accordingly.
3. **Should `DELETE /sessions/{id}` remain operator-reachable for foreign sessions?** Recommendation: yes (owner-or-operator) — it is the only cleanup tool besides TTL. API-only either way per the UI spec.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib (hmac/secrets/uuid) | identity.py | ✓ | 3.14 | — |
| psycopg + psycopg-pool | limits/ownership SQL | ✓ (pinned, in prod image) | pinned | in-memory limits backend for SQLite deployments |
| Local PostgreSQL 17 + pgvector @ :54329 | gated tests | ✗ **not responding at research time** (`pg_isready` no response — likely the container is stopped) | 17 | start the container before running gated tests; CI runs real Postgres regardless |
| Supabase Postgres (prod) | live stores | ✓ (release v7, per CONTEXT) | session-mode pooler | — |
| chromadb | 4th behavioural-suite arm | **unverified** — see Open Question 2 | — | gate the arm with a skip-detector |
| Fly secrets (`IDENTITY_SIGNING_SECRET`) | cross-machine token verification | to be set at deploy | — | per-process ephemeral secret (degrades to per-machine identity; cap still bounds) |

**Missing dependencies with no fallback:** none block planning; local :54329 must be started before executing gated tests.

## Validation Architecture

*(`.planning/config.json` not present; nyquist_validation treated as enabled.)*

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (dev extra), config in `pyproject.toml` `[tool.pytest.ini_options]`, no conftest.py — shared fakes live in owning modules |
| Quick run command | `pytest tests/test_limits.py tests/test_service.py -q` |
| Full suite command | `pytest -q` (baseline: **436 passed / 34 skipped** local; CI: real Postgres, `REQUIRE_POSTGRES=1`, 0 relevant skips) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-demo-authentication | mint/verify round-trip; tamper/garbage → None; version prefix | unit | `pytest tests/test_identity.py -q` | ❌ Wave 0 (new module) |
| REQ-demo-authentication | first request with no cookie: 200 + Set-Cookie with HttpOnly/SameSite=Lax/Secure, on JSON, `/` (FileResponse), and SSE responses | API | `pytest tests/test_service.py -k identity -q` | ❌ Wave 0 (extend; needs `base_url="https://testserver"`) |
| REQ-demo-authentication | per-identity rate limit: identity A exhausts, identity B unaffected; 429 detail + Retry-After preserved | API + contract | `pytest tests/test_limits.py -q` (memory arm) / same file postgres arm gated | extend existing |
| REQ-demo-authentication | cap counts in-flight: reserve admits exactly one of two racing threads (cap sized to admit one) | **real Postgres** | `DATABASE_URL=postgresql://…:54329/… pytest tests/test_limits.py -k reserve_race -q` | ❌ Wave 0 |
| REQ-demo-authentication | reservation settles on success AND on failed stream; stale reservation stops counting after cutoff | API (sqlite/memory limits arm fine for settle path) + Postgres arm | `pytest -k settle -q` | ❌ Wave 0 |
| REQ-demo-authentication | cap 429 message still contains "Read-only endpoints still work."; session reads reachable while capped | API | `pytest tests/test_service.py -k cap -q` | extend existing (this assertion partially exists) |
| REQ-store-lifecycle-and-ownership | `/sessions` returns only caller's; foreign `/sessions/{id}`, `/trace`, `DELETE`, and `/ask*` → 404 identical to missing | API | `pytest tests/test_service.py -k ownership -q` | ❌ Wave 0 |
| REQ-store-lifecycle-and-ownership | expired session stops resolving (freeze time / write old `updated_at`); sweep deletes on next create; reads don't renew `updated_at` | contract (both session backends) | `pytest tests/test_store_contract.py -k expiry -q` | ❌ Wave 0 (extend suite) |
| REQ-store-lifecycle-and-ownership | note scoping: A's notes invisible to B; `owner=""` isolated; TTL-expired notes not recalled — identical across json/memory/pgvector(/chroma if installed) | contract | `pytest tests/test_store_contract.py tests/test_memory_stores.py -k owner -q` | ❌ Wave 0 (extend suite) |
| REQ-store-lifecycle-and-ownership | SQLite + Postgres column migration idempotent against a pre-phase table | contract | `pytest -k migration -q` | ❌ Wave 0 |
| both | route walker: `AUTH_DEPENDENCIES` updated; ≥6 `/sessions` route objects; ask routes carry guard not session dependency; no session route carries `check_daily_cap` | structural | `pytest tests/test_service.py -k structural -q` | extend existing (`test_service.py:549-614`) |
| UI (12-UI-SPEC AC7/AC8) | font-size/weight sets unchanged from measured baseline; `grep -c innerHTML` == 0 (baseline 0, re-verified this session) | static | `grep -c innerHTML src/research_agent/static/index.html` | ✅ command-level |

### Sampling Rate
- **Per task commit:** `pytest tests/test_limits.py tests/test_identity.py tests/test_service.py -q` (< 30 s)
- **Per wave merge:** `pytest -q` + `ruff check .`
- **Phase gate:** full suite green locally AND against Postgres (`:54329` container up), offline evals 12/12, then live checks

### Live-only verification (cannot be automated in the suite — plan as checkpoint:human-verify)
- Two-machine identity continuity: mint on machine A (`fly-force-instance-id`), present same cookie to machine B → session visible, rate window shared.
- Real-browser cookie behaviour: HttpOnly invisible to `document.cookie`; survives reload; cleared-storage first visit matches AC1's two-textual-deltas diff.
- Rollout window: old page against new API (Pitfall 8) during the sequential machine deploy.

### Wave 0 Gaps
- [ ] `tests/test_identity.py` — token unit tests (REQ-demo-authentication)
- [ ] `make_client` gains `base_url="https://testserver"` + identity helpers (mint real cookies via public `identity.mint()` with a monkeypatched secret)
- [ ] Postgres limits-backend arm in `tests/test_limits.py` incl. the two-thread reserve race (skip-gated like the store contract, with the `REQUIRE_POSTGRES` detector pattern)
- [ ] Ownership/expiry cases added to `tests/test_store_contract.py` (both session backends; note backends)
- [ ] Decision on the chroma arm (install in dev extra vs skip-gated) — with a measured non-vacuity baseline stated in the gate

### Gate discipline (per CONTEXT: eight vacuous gates found across four phases)
Every gate in the plans must state its measured baseline on the current tree. Measured this session: `grep -c innerHTML …/index.html` = **0**; fetch call sites in index.html = **2** (`fetch(url…)` in `run()`, `fetch("/demo")` in `refreshLimits()` — the UI spec's "five call sites" counts post-phase additions); `/sessions` route objects = **6** (existing test asserts ≥6); suite = **436 passed / 34 skipped**. Any `>= 1`-count gate in the plans should be rejected at plan review in favour of exact sets or measured-delta assertions (the UI spec's AC7 font-set gate is the model).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (anonymous-identity variant) | HMAC-SHA256 signed token, constant-time verify, honest "possession ≠ person" documentation |
| V3 Session Management | yes | HttpOnly + SameSite=Lax + Secure cookie; server-side expiry derived from activity; no session fixation surface (identity is not privilege-bearing beyond own data) |
| V4 Access Control | yes | Owner check at the single `_require` choke point; 404 not 403 (no existence oracle); operator path fail-closed |
| V5 Input Validation | yes | Cookie value parsed by strict 3-part split + `isalnum` id check before any use; existing Pydantic `AskRequest` unchanged |
| V6 Cryptography | yes | stdlib HMAC only — never hand-roll a MAC construction; secret via Fly secrets, never logged (extend the `_redact`/never-by-value posture) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSRF via ambient cookie | Spoofing/Tampering | SameSite=Lax + JSON-body-only mutations + no CORS middleware (preflight fails cross-origin) — document in ADR |
| Existence oracle on session ids | Information disclosure | 404 byte-identical for missing/foreign/expired |
| Cross-tenant note injection → forced `APPROVED` | Tampering/Elevation | Owner-scoped recall (the phase's core fix); behavioural suite proves isolation per backend |
| Sybil identities to drain budget | DoS (economic) | Locked design: global cap is the backstop; per-identity limits are fairness only — never remove the cap |
| Signing-secret leak via logs/health | Information disclosure | Presence-only reporting in `/health`; secret never in any response or log line |
| Timing attack on token verify | Information disclosure | `hmac.compare_digest` |

## Sources

### Primary (HIGH confidence)
- Full reads this session: `src/research_agent/{limits,service,sessions,memory,metrics,db,graph}.py`, `static/index.html`, `tests/test_service.py` (walker + guard tests), `docs/adr/0006…`, `docs/adr/README.md`, `12-CONTEXT.md`, `12-UI-SPEC.md`, `.planning/{ROADMAP,REQUIREMENTS}.md`, `.planning/codebase/{TESTING,CONVENTIONS}.md`
- MDN `RequestInit` — fetch `credentials` defaults to `"same-origin"` (cookies ride free same-origin) `[CITED]`
- Local verification commands: `grep -c innerHTML` = 0; `import itsdangerous` fails (not installed); `pg_isready -p 54329` no response; `AGENT_MAX_RUN_COST_USD` default 1.00 (`usage.py:198`)

### Secondary (MEDIUM confidence)
- FastAPI documented behaviour: direct `Response` returns bypass dependency-injected response mutation (consistent with fastapi.tiangolo.com/advanced/response-directly)
- PostgreSQL semantics: READ COMMITTED snapshot visibility for the race analysis; `pg_advisory_xact_lock` transaction scoping (consistent with postgresql.org/docs explicit-locking) — both also cross-confirmed by this repo's own `db.py` battle-notes

### Tertiary (LOW confidence / flagged)
- Assumptions A1–A4 in the Assumptions Log (httpx Secure-cookie jar behaviour, chroma `where` filters, pgvector filtered-HNSW, BaseHTTPMiddleware hazards) — each has a cheap Wave 0 verification or a recommendation that is safe regardless

## Metadata

**Confidence breakdown:**
- Token/transport design: HIGH — MDN-verified transport, stdlib-only crypto, all call sites read
- Limits redesign: HIGH on architecture, MEDIUM on the exact reservation tunable (user ratifies)
- Ownership/expiry schema: HIGH — exact current schemas read; migration path reuses proven lazy-DDL
- Note scoping: HIGH for json/memory/pgvector (code read); MEDIUM for chroma (install status unverified — Open Question 2)
- ADR verdict: HIGH on the convention mechanics; the supersede-vs-amend recommendation is a judgement explicitly surfaced for plan review

**Research date:** 2026-08-05
**Valid until:** ~2026-09-05 (stable stack; the only moving parts are this repo's own tree)
