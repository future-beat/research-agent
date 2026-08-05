# Phase 12: Caller identity, session ownership, bounded stores - Context

**Gathered:** 2026-08-05
**Status:** Ready for UI spec, then research
**Source:** Decisions taken directly with the user before planning

<domain>
## Phase Boundary

The demo learns who is calling, sessions belong to someone and expire, notes stop growing
forever and stop leaking across visitors, and the spend-cap machinery stops being fooled by
concurrency and multiple machines.

This is the milestone's **fourth design reversal** and its most user-visible one:
"rate-limited, not authenticated" was a deliberate scope call recorded in the README and now
in the ADR trail. The replacement guarantee is defined below. **Criterion 6 is the constraint
that kills wrong designs: a stranger following a link from a résumé must reach a working demo
without an auth wall.**

</domain>

<decisions>
## Implementation Decisions

### Identity: auto-issued and anonymous — LOCKED

- First visit **mints a signed identity token silently** (no signup, no wall, no visible
  ceremony). The browser stores it and presents it on every call. A stranger from a résumé
  link never notices identity exists.
- Identity means **possession of the token**, not a verified person. Say so honestly in the
  docs — this is the right strength for a public demo, not a weak version of real auth.
- **The fairness ceiling is documented, not hidden:** clearing browser storage mints a fresh
  identity with fresh limits. Per-identity limits are therefore a fairness improvement over
  per-IP, not a hard boundary.
- **CONSEQUENCE THE DESIGN MUST HONOUR: identities are free to mint, so per-identity limits
  cannot be the only bound on the bill.** The global rolling daily spend cap survives as the
  backstop. Per-identity limits give fairness; the global cap bounds the invoice. Removing
  the global cap because "limits are per-identity now" is the failure mode to design against.
- Rejected: GitHub OAuth (two-tier logic doubles the surface; the anonymous tier still needs
  this scheme anyway), email magic link (an auth wall by criterion 6's definition).

### The replacement guarantee (this reversal's ADR)

The reversal retires "fairness keys on visitor IP via `TRUST_FORWARDED_FOR`". What replaces
it: **fairness keys on an auto-issued identity; spend remains bounded globally regardless of
identity count.** `TRUST_FORWARDED_FOR` stops being load-bearing for fairness. The phase
must record this as a new ADR and mark ADR-0006's expected supersession per the convention
in `docs/adr/README.md` (status-line edit only; Phase 12 was pre-named as its expected
superseder — verify whether full supersession or amendment is honest, and record which).

### Session ownership and expiry — LOCKED

- Sessions carry the creator's identity. `/sessions` lists **only the caller's sessions**.
  `/sessions/{id}` for someone else's session refuses; researcher picks 403 vs 404 (mind
  the existence-oracle concern from Phase 10.5 — prefer the shape that leaks least).
- **Expiry: 7 days after last activity** — aggressive demo hygiene, chosen deliberately.
  This is a demo, not a product; the public store stays small and self-cleaning. Returning
  visitors lose old history after a week and that is accepted.
- Expired sessions stop resolving. Mechanics (lazy filtering vs background sweep) are the
  researcher's call, but whatever is chosen must behave identically on both machines.

### Chroma joins CI — RATIFIED 2026-08-05

- **Discovered during research:** `chromadb` is an optional extra, NOT installed by the `dev`
  extra CI runs, and the shared contract suite parametrizes only `json/memory/pgvector`. So
  SC-5's "across json, memory, chroma, and pgvector, proven by the shared behavioural suite"
  was **unprovable** as written — chroma had no suite arm.
- **Decision:** add `chromadb==1.4.1` to the `dev` extra and parametrize the contract suite
  over all FOUR backends, so SC-5 becomes literally true and green. Accept the heavier CI
  (chromadb pulls onnxruntime and friends). This makes the roadmap criterion honest rather
  than amending it downward.
- Wave 0 must confirm `ChromaMemoryStore` actually imports and runs in CI before the rest of
  the phase depends on the 4-arm suite.

### Note tenant scoping — IN SCOPE (user-approved addition)

- Notes are currently written to one shared store and recalled into **other visitors'**
  runs; the critic reads that same untrusted text, so injection can force `APPROVED`.
  Shipping "ownership" while the pipeline's brain stays communal would be the ownership
  requirement applied to everything except the thing that feeds answers.
- Notes become scoped to the caller identity: recall retrieves only the caller's notes.
  All four backends (json, memory, chroma, pgvector) must behave identically, proven by the
  shared behavioural suite.
- The two orphaned notes from the 2026-08-04 deletions are dealt with here (delete or
  claim-by-nobody-and-expire; researcher proposes).

### Note bounds — RATIFIED 2026-08-05

- **Notes expire 7 days after creation**, matching session hygiene. Dedup-on-write was
  evaluated and **rejected** — no identical semantics across the four backends, so it would
  fail SC-5's "behaves the same" bar. TTL is the bound.
- pgvector already has `created_at`; only `owner` columns are new. Lazy filter against the
  database clock plus an opportunistic sweep on `create()`, mirroring session expiry.

### Cap reservation — RATIFIED 2026-08-05

- Each in-flight run **reserves `DEMO_RESERVED_RUN_USD` (default $0.20)** against the daily
  cap, settled to real cost when the run finishes (both the success and SSE-error arms funnel
  through `_execute`/`_stream`). Avg run is ~$0.20–0.25, so the reservation is honest, not
  punitive. Tunable env var.
- Reservation rows checked+inserted inside `pg_advisory_xact_lock` (transaction-scoped — needs
  a small `Database.transaction()` helper; the pool is autocommit today). A 900s staleness
  cutoff backstops crashed runs that never settle. The cap's "Read-only endpoints still work"
  429 property survives verbatim.

### Operator view — RATIFIED 2026-08-05

- **`SESSIONS_TOKEN` survives as the operator credential.** `GET /sessions` is dual-mode: a
  valid operator token lists ALL sessions (the debugging view used this week); without it, the
  listing is identity-scoped to the caller. `DELETE` works for the **owner or the operator**.
- Therefore **ADR-0007 SUPERSEDES ADR-0006** (SESSIONS_TOKEN's role changes but survives) with
  explicit carry-forward of 0006's still-true decisions — the README convention has no
  "Amended" status and 0006 pre-named Phase 12 as its superseder.
- Foreign/expired sessions return **404, byte-identical to missing** (`No session {id!r}.`),
  continuing 10.5's leak-least, existence-oracle-free posture. Not 403.

### Transport — RATIFIED (from research, HIGH confidence)

- **Signed HttpOnly cookie.** `fetch()` defaults to `credentials: "same-origin"`, so all five
  page call sites carry it for free — **zero JS changes**. `HttpOnly; SameSite=Lax; Secure;
  Max-Age=400d`. Token `v1.<uuid4hex>.<hmac-sha256>` via stdlib `hmac` (`itsdangerous`
  rejected — buys nothing needed). Secret `IDENTITY_SIGNING_SECRET` as an app-wide Fly secret;
  unset degrades to per-machine ephemeral identity with the global cap still bounding the bill.
- **Minting is pure-ASGI middleware, mint-on-response, never 401** — `/research/stream`,
  `/ask/stream` and `GET /` return `Response` objects directly, where dependency-set cookies
  are dropped. A first-time caller's stream must never break.

### Spend-cap race — IN SCOPE (user-approved addition)

- Today the daily cap counts **completed** runs only, so concurrent runs overshoot ~3×; and
  cap/rate-limit state is **per-machine memory**, so two machines each grant a full budget.
  Both defects compound now that release v7 runs 2 machines × 16 concurrent.
- Cap and rate-limit state move to Postgres (shared, like everything else now), and
  in-flight runs count against the cap. The "Read-only endpoints still work" property of
  the cap's 429 must survive (`limits.py`'s documented behaviour).

### Out of scope — explicitly

- `/health` key-validity probing (stays a backlog item; presence-not-validity gap noted).
- Any signup, OAuth, or email flow. Any account management UI.
- Embedding migration (Phase 13), cost multipliers (Phase 14).
- `GET /metrics` authentication — still public by design; revisit later if ever.

### Claude's Discretion

- Token format and transport (signed cookie vs bearer in localStorage; must work for both
  fetch and SSE paths), signing mechanism and key rotation posture.
- Schema changes for owner/expiry columns; migration of the *new* Postgres data (small —
  the store is days old; the volume backup is not in play).
- 403 vs 404 for foreign sessions; lazy vs background expiry; exact note-bound mechanics.
- How the operator (`SESSIONS_TOKEN`) retains a global admin view, if at all.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope
- `.planning/ROADMAP.md` § Phase 12 — six success criteria, the reversal note, UI hint
- `.planning/REQUIREMENTS.md` — REQ-demo-authentication, REQ-store-lifecycle-and-ownership

### The ADR trail this phase touches
- `docs/adr/README.md` — the supersession convention (status-line edit only)
- `docs/adr/0006-separate-sessions-token-fails-closed.md` — Phase 12 is its pre-named
  expected superseder

### Code
- `src/research_agent/limits.py` — guard, check_token, check_rate_limit, check_daily_cap,
  require_sessions_token; all in-memory today
- `src/research_agent/service.py` — sessions_router (token-guarded), ask routes (anonymous
  by design — the demo's second turn), SSE paths
- `src/research_agent/sessions.py`, `memory.py`, `metrics.py`, `db.py` — pooled Postgres
  as of Phase 11; one shared pool per machine; advisory-locked lazy DDL
- `src/research_agent/static/index.html` — the demo page; exactly two fetch call sites as
  of Phase 10.5 (note: `static/index.html` does not exist at repo root — use the full path)

### State of the world (post-Phase 11)
- Release v7, TWO machines, all stores on Supabase (session-mode pooler, port 5432).
  Anything stateful that stays in process memory is now wrong twice.
- `DEMO_TOKEN` must stay unset in production (ADR-0006). `SESSIONS_TOKEN` guards the
  session read/delete tree, fails closed.
- Suite baseline: 436 passed / 34 skipped local; CI runs real Postgres. No conftest.py.
  Local PostgreSQL 17 + pgvector on port 54329 for gated tests.

</canonical_refs>

<specifics>
## Specific Ideas

- The structural route-guard test from 10.5 (`api_routes()` recursive walker, non-vacuity
  count) must be extended, not bypassed, when routes change ownership semantics.
- Rate-limit/cap checks moving to Postgres will add a DB round trip to `guard` — the
  budget arithmetic from Phase 11 (`/health` 9s ceiling; probes measured 2.8–3.4ms p50)
  says this is affordable, but the researcher must confirm for the hot path.
- **Gate discipline: eight vacuous gates were found across four phases. Any presence/absence
  gate must state its measured baseline on the current tree before it is accepted.**
- One PR for the whole phase at the end; no direct pushes to `main`.

</specifics>

<deferred>
## Deferred Ideas

- `/health` outbound key-validity probe (bounded, cached) — backlog.
- Durable accounts (OAuth) as an upgrade path on top of anonymous identity — later, if ever.
- `GET /metrics` auth — public by design for now.

</deferred>

---

*Phase: 12-caller-identity-session-ownership-bounded-stores*
*Context recorded: 2026-08-05 — user-approved before UI spec and research*
