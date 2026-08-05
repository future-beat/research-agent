# ADR-0007 — Fairness keys on an auto-issued anonymous identity; the global cap bounds the bill

**Status:** Accepted — supersedes ADR-0006
**Source:** Phase 12 (2026-08-05), `REQ-demo-authentication` and `REQ-store-lifecycle-and-ownership`

## Context

Until this phase the public demo was **rate-limited, not authenticated**. Fairness keyed on the
visitor's IP address, read from `X-Forwarded-For` when `TRUST_FORWARDED_FOR` was set, and nothing
else distinguished one caller from another. Sessions and research notes belonged to nobody, which
meant in practice they belonged to everybody: `GET /sessions` listed every visitor's research to
any token holder, and the note store recalled one visitor's text into another visitor's run.

Three things had gone wrong with that arrangement by the time Phase 12 opened.

**The fairness key was forgeable and shared.** `X-Forwarded-For` is caller-supplied; a proxy chain
is the only thing that makes any prefix of it trustworthy, and mobile carriers and corporate NATs
put thousands of unrelated visitors behind one address anyway. The key was simultaneously too easy
to change and too coarse to be fair.

**The key was per-machine.** Release v7 runs two machines. Rate-limit and spend-cap state lived in
process memory, so each machine granted a full budget and a full hourly allowance independently.
"Ten requests per hour" meant twenty, and the daily cap meant twice the daily cap.

**Communal notes were a security defect, not just untidiness.** Recalled notes are pasted verbatim
into the researcher's prompt and the critic reviews what comes back, so text one visitor caused to
be written sat on another visitor's path to `APPROVED`. Shipping "ownership" while the pipeline's
memory stayed communal would have applied the requirement to everything except the thing that
produces answers.

The constraint that kills most of the obvious fixes is the demo's whole purpose: **a stranger
following a link from a résumé must reach a working demo without an auth wall.** Signup, OAuth and
email magic links all fail that test. So does anything that renders an "initializing" state before
the first question can be typed.

## Decision

**Fairness keys on an auto-issued anonymous identity; spend remains bounded globally regardless of
identity count.**

The first request from a browser mints a signed identity token silently and returns it on the
response of whichever route the caller happened to hit. There is no signup, no wall, and no visible
ceremony. The token is `v1.<uuid4hex>.<hmac-sha256>` over stdlib `hmac`, signed with
`IDENTITY_SIGNING_SECRET` — an app-wide Fly secret, so a token minted on one machine verifies on the
other. Unset, the service degrades to a per-process ephemeral secret with a logged warning: callers
re-mint when they bounce between machines, which is survivable precisely because of the second half
of this decision.

**Identity means possession of the token, not a verified person.** That is the honest strength of
this scheme and the right one for a public demo. It is stated here rather than left to be inferred,
because a reader who assumes otherwise will over-trust the `owner` column.

**The fairness ceiling is documented, not hidden.** Identities are free to mint: clearing browser
storage produces a fresh identity with fresh limits. Per-identity limits are therefore a *fairness*
improvement over per-IP, not a hard boundary. **Because identities are free to mint, per-identity
limits cannot be the only bound on the bill.** The global rolling 24-hour spend cap survives
untouched as the backstop, now shared across machines in Postgres and counting in-flight runs by
reservation. Removing the global cap because "limits are per-identity now" is the failure mode this
record exists to forbid.

**Transport is a signed HttpOnly cookie.** `fetch()` defaults to `credentials: "same-origin"`, so
every call site the demo page makes carries it with zero JavaScript changes, including the
hand-rolled SSE readers. Attributes are `HttpOnly; SameSite=Lax; Secure; Max-Age=34560000; Path=/`
with no `Domain`. HttpOnly means the token is invisible to script forever, which is what keeps an
XSS in the report renderer from becoming identity theft. CSRF needs no separate token here:
`SameSite=Lax` withholds the cookie from cross-site POSTs, the write routes accept only a JSON body
(a cross-site HTML form cannot produce `content-type: application/json`), and there is no CORS
middleware, so no other origin can read a response. Minting happens in pure-ASGI middleware on the
*response*, never as a 401-then-retry — a first-time caller's stream must not break.

**Foreign and expired sessions return 404, byte-identical to a missing one.** 403 would confirm that
an id names a real session, and session ids travel in shared URLs. This continues Phase 10.5's
leak-least, existence-oracle-free posture.

**`TRUST_FORWARDED_FOR` is demoted from load-bearing to vestigial.** `client_ip` survives for log
lines and nothing keys fairness on it. The env var may remain set; it is harmless and no longer
meaningful. Re-keying the rate window on `(identity, ip)` "just in case" would reintroduce the
forgeable key through the back door and is rejected.

### Carried forward from ADR-0006

This record supersedes ADR-0006, but three of that record's four parts survive and one survives with
an inverted meaning. They are restated here so that superseding 0006 does not silently discard them.

**`SESSIONS_TOKEN` survives — as the *operator* credential.** `GET /sessions` is dual-mode: a valid
`SESSIONS_TOKEN` lists every owner's sessions (the debugging view), and without it the listing is
scoped to the caller's own identity. `DELETE /sessions/{id}` works for the **owner or the operator**.
Its fail-closed property **inverts** rather than disappearing: an unset token used to mean nobody
passes, because the token was the only thing between a stranger and someone else's research; it is
no longer the only thing, so an unset token now closes only the cross-owner debugging view and
leaves every visitor reaching their own sessions. This is what makes 0006 a supersession rather than
a deletion — the credential still exists and still fails closed, but it no longer answers the
question "may this visitor read a session".

**`guard` still does not front the session reads (0006 part 3).** The read/cap decomposition is
reaffirmed. Guarding the reads would meter listing a session against the caller's research quota and
would 429 every read once the daily budget fired, contradicting the cap's own message that
"Read-only endpoints still work." Phase 12 makes that decomposition finer, not coarser: the cap left
`guard` entirely for an in-handler `reserve_or_429`, and the `DELETE` carries the rate half of
`guard` on its own.

**The session routes stay grouped on an `APIRouter` (0006 part 4).** Membership is structural: a
future `@sessions_router.get("/{id}/notes")` inherits access control by construction. The original
defect was four routes each independently forgetting a credential, and a control you have to
remember to repeat is a control that will be forgotten again. Only the dependency's *name* changed —
`require_sessions_token` became `require_session_access` — and the structural walker test that
enforces membership was extended rather than bypassed. Grouping remains by dependency, not by path
prefix: `POST /sessions/{id}/ask*` shares the prefix, stays off the router, and enforces ownership
in-handler.

**`DEMO_TOKEN` must never be set in production.** 0006's central consequence still holds without
qualification. `guard` fronts `POST /research/stream` and the demo page sends no token header, so
setting `DEMO_TOKEN` in production 401s every anonymous visitor and takes the demo offline. Nothing
in this record relaxes that: identity is not a token the visitor has to produce, and it is not a
substitute for `DEMO_TOKEN` being unset.

## Consequences

### Accepted

- **The reversal is user-visible in exactly two sentences.** The demo page gains a muted footer line
  ("Your sessions and notes are private to this browser and expire after 7 days of inactivity.") and
  a reworded limits line naming both scopes — the per-browser rate limit and the all-visitors spend.
  Nothing else about a first visit changes: no banner, no prompt, no consent step. That constraint
  is machine-checked, not merely intended.
- **A determined abuser can mint identities in a loop.** This is accepted, named, and bounded: the
  global daily cap is what makes it a nuisance rather than an invoice. Per-identity limits buy
  fairness between ordinary visitors, which is what they were introduced for.
- **Rotating `IDENTITY_SIGNING_SECRET` re-mints everyone.** Old cookies fail verification and the
  middleware mints fresh ones on the next request. Limits reset for everybody; the global cap
  backstops the window in which that matters. Dual-key verification is deliberately not built — this
  is a demo, and the recovery from a leaked signing secret is "everyone's limits reset once".
- **The `owner` column is only as strong as a cookie.** Sessions and notes are private to a browser,
  not to a person. Someone who copies a cookie is that identity. Stated plainly in the README and in
  the page's own footer sentence rather than dressed up.
- **Losing the cookie loses the history.** Clearing storage is indistinguishable from a new visitor,
  by construction. There is no recovery flow, because there is no account to recover.

### Rejected alternatives

- **GitHub OAuth.** Two tiers of caller doubles the authorisation surface, and the anonymous tier
  still needs this exact scheme underneath it — so OAuth adds a wall without removing any work.
- **Email magic link.** An auth wall by the résumé-link criterion's definition.
- **A bearer token in `localStorage`.** Readable by any script that lands on the page, and it would
  require touching every one of the page's five call sites, including the two hand-rolled SSE
  readers. The cookie costs zero JavaScript changes and is invisible to script.
- **`itsdangerous` or another signing library.** Buys nothing over eleven lines of stdlib `hmac`
  with `compare_digest`, which is already the comparison idiom in `limits.py`.
- **Keeping per-IP limits alongside per-identity ones.** Reintroduces the forgeable, machine-local
  key this record retires, and makes the fairness story two stories.
- **Amending ADR-0006 in place.** `docs/adr/README.md` offers exactly two moves — status-line
  supersession, or a new record — and has no "Amended" status. Leaving 0006 `Accepted` while its
  central sentence is no longer the visitor-path truth would be the quiet contradiction the ADR trail
  exists to prevent. Hence: supersede, and carry forward explicitly above.
