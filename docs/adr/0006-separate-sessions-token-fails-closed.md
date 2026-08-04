# ADR-0006 — Session endpoints use a separate, fail-closed `SESSIONS_TOKEN`

**Status:** Accepted
**Source:** Phase 10.5 (2026-08-04), shipped as Fly release v4

## Context

Four session routes — `GET /sessions`, `GET /sessions/{id}`, `GET /sessions/{id}/trace` and
`DELETE /sessions/{id}` — shipped with no credential at all.

The exposure was **confirmed against production, not inferred**. An unauthenticated
`GET /sessions` from the open internet returned real session contents, and two `DELETE`
calls returned `204` and actually deleted the sessions.

Setting `DEMO_TOKEN` did not close it, and it is worth being exact about why: `check_token`
runs only inside `guard`, and those four paths never reached `guard`. The control existed
in the code and was inert on the deployed service — which is the shape of the defect this
record is really about.

## Decision

Four parts, each with its reason.

**1. A separate `SESSIONS_TOKEN`,** sent as `x-demo-token`, with `DEMO_TOKEN` accepted as a
fallback *value* (`limits.sessions_token`). Separate because the two credentials protect
different things, and because — see the first consequence — `DEMO_TOKEN` cannot be set in
production. Honouring it as a fallback is what makes "setting `DEMO_TOKEN` protects the
session endpoints" true rather than quietly false.

**2. It fails closed — `403` when unset** (`limits.require_sessions_token`). This
deliberately diverges from `check_token`'s open-when-unset convention. The defect being
fixed was precisely a control that existed in code and went inert on a missing env var; a
design where forgetting the secret silently reopens the hole repeats that exact mistake.
`403` when nothing is configured (nobody passes), `401` when a credential exists and the
caller's is missing or wrong.

**3. `guard` is deliberately *not* applied to the reads.** `guard` bundles `check_token` +
`check_rate_limit` + `check_daily_cap` indivisibly. Guarding the reads would meter listing
a session against the caller's research quota, and would `429` every read once the daily
spend cap fired — contradicting the cap's own message, which promises "Read-only endpoints
still work". The correct decomposition is a token-only dependency on the group, with
`check_rate_limit` on the `DELETE` only, as the one route that destroys anything.

**4. The four routes are grouped on an `APIRouter`,** not given four per-route dependency
lists. The original defect was four routes each independently forgetting a credential, and
a control you have to remember to repeat is a control that will be forgotten again.
Membership is structural: a future `@sessions_router.get("/{id}/notes")` inherits the
credential by construction, with nothing to remember. Grouping is by **dependency, not by
path prefix** — `POST /sessions/{id}/ask*` shares the prefix and stays off the router,
because it is the demo's second turn and guarding it would break follow-ups.

## Consequences

### `DEMO_TOKEN` must never be set in production

This is the consequence the record exists for.

`guard` fronts `POST /research/stream`, and the demo page sends no token header. Setting
`DEMO_TOKEN` in production therefore **401s every anonymous visitor and takes the public
demo offline** — the entire purpose of deploying this service.

Any future refactor that "tidies" the two tokens into one reintroduces exactly that. The
two names are not redundancy and not an oversight: `SESSIONS_TOKEN` closes the session tree
*without touching the demo*, and that separation is the whole point. Merge them and the
demo goes dark.

### Also accepted

- Failing closed cost roughly **14 test call-site updates**, because every existing test
  that hit a session endpoint had to start presenting a credential. That was priced in and
  paid; it is the recurring cost of the safe default, and the safe default is still right.
- The token proves *authorised*, not *who*. `GET /sessions` still lists **every** session to
  any token holder. This closes anonymous access; it does not introduce ownership.

### Expected reversal

Phase 12 (`REQ-store-lifecycle-and-ownership`) is expected to supersede this record. When
per-caller identity lands, parts 1 and 2 are the likely casualties — a system that knows
who is asking does not need a single shared bearer secret, and its failure default is a
different question. Nothing is overturned today; this record is `Accepted` as written.
