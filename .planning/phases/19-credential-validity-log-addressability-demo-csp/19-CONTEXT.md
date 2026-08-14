# Phase 19: Credential validity, log addressability, demo CSP - Context

**Gathered:** 2026-08-14
**Status:** Ready for UI spec + research
**Source:** Milestone-questioning decisions (user-ratified 2026-08-13 at v1.2 start) plus
the session investigation. The user additionally chose — against the orchestrator's
recommendation — to run the UI design-contract step before planning, so a `19-UI-SPEC.md`
will exist and binds the CSP work.

<domain>
## Phase Boundary

Three closures, three surfaces, none of them touching routing:

1. `/health` reports whether the Anthropic and Voyage keys actually *work* — beside the
   existing presence booleans, backed by a cached async validity probe. The liveness path
   still never calls a provider.
2. `run_finished` log lines carry `session_id`, so a completed run is addressable from the
   logs.
3. The demo page ships a hash-based Content-Security-Policy header its inline JS survives.

**Not in this phase:** deleting any README Limitations bullet (Phase 22 owns the section);
the note count bound (Phase 20); anything touching the critic, the judge, or eval
recording; any change to what liveness means to Fly.

</domain>

<decisions>
## Implementation Decisions (user-ratified at milestone questioning)

### The probe is cached and async, and liveness is untouchable

- `count_tokens` is the Anthropic validity check — it authenticates and costs $0. Voyage
  gets a micro-embed (cheapest available call; effectively-zero but nonzero cost).
- New fields sit BESIDE the presence booleans, not replacing them: presence and validity
  are different facts and the credentials block should carry both.
- **The deliberate half of the original limitation survives**: Fly's check must never
  transitively call a provider, or a provider outage restarts a healthy container — the
  exact failure the presence-only design was protecting against. A probe failure is
  operator information, never a liveness failure.
- Probe spend is excluded from or attributed in cost accounting **deliberately, stated in
  code** — not silently. (The Voyage micro-embed would otherwise hit the Phase 14
  embedding meter; whichever way it goes, a comment and a test say which.)

### run_finished carries session_id

- The gap cost a wasted live run in Phase 17 (a completed run was not addressable from the
  logs). Attribution matters more than the field: the fix is in the logging call, not a
  schema change.

### CSP is hash-based, verified, and visually inert

- `unsafe-inline` is explicitly ruled out — a CSP with it is decorative.
- The header must be **verified against the actual page**: a test that derives the hashes
  from `static/index.html`'s real inline blocks, so editing the page without updating the
  policy fails a test rather than silently breaking the live demo.
- The UI-SPEC (being produced before planning) binds the constraint from the other side:
  the CSP must not change what the page looks like or does. If satisfying the CSP forces
  restructuring the page's JS, that surfaces as a checkpoint, not a silent rewrite.

### Claude's Discretion (researcher questions first, then planner)

- Probe cadence/TTL and refresh mechanism. **Constraint:** the service has no background
  scheduler today, and DEC-18 forbids import-time construction — serve-stale-refresh-async
  on `/health` reads is the likely shape, but the researcher should verify what composes
  with the existing lifespan and pool patterns.
- `/health` field shape (e.g. `anthropic: {present, valid, checked_at}` vs flat keys) —
  pick what reads best beside the existing block; additive only (Phase 12's rollout
  constraint style: no field disappears).
- Where CSP hashes are computed: build-time constant + derivation test, or startup
  derivation. Either is acceptable if the drift-fails-a-test property holds.
- Whether `/ready` also surfaces validity (probably not — readiness is stores, and mixing
  provider validity into readiness re-creates the restart hazard one hop away).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The surfaces being changed
- `src/research_agent/service.py` — `/health` (credentials block at ~:628-638), `/ready`,
  the lifespan, `run_finished` logging site, and the demo-page route that would carry the
  CSP header
- `src/research_agent/observability.py` — structured logging, where `run_finished` fields
  live
- `src/research_agent/static/index.html` — the inline JS/CSS the CSP must permit (two
  fetch calls, SSE wiring)
- `src/research_agent/usage.py` + the Phase 14 embedding meter — what a Voyage micro-embed
  would be counted by

### House constraints that bind the design
- DEC-18 (nothing constructed at import time; boot degraded and self-heal) — the probe
  must not break this
- `docs/adr/README.md` + Phase 12/14 records — additive-payload conventions, telemetry
  honesty
- `.planning/REQUIREMENTS.md` — the three REQ texts and the milestone acceptance bar (no
  successor limitation)

### Process
- `.planning/phases/18-independent-eval-judge/18-VERIFICATION.md` — the verification
  template this milestone now uses; Phase 19 closes the same way
- Tooling is `gsd-tools` (GSD Core v1.10.0); STATE.md frontmatter edits are done BY HAND —
  the old SDK verbs corrupted it three times in Phase 18

</canonical_refs>

<specifics>
## Specific Ideas

- The README's `/health` Limitations bullet says "What is missing is the other signal" —
  this phase builds exactly that signal; Phase 22 deletes the bullet. Do not touch the
  bullet here, but DO fix any other doc surface this phase falsifies (OPERATIONS' health
  documentation, DESIGN if it describes /health).
- The revoked-key outage from Phase 11 is the acceptance story: after this phase, that
  outage would be visible in `/health` within one probe TTL.
- Keyless suite: probe tests must run with `ANTHROPIC_API_KEY=""` — fakes for both
  providers, and the no-keys state should read as `valid: null`/unknown, not false (a
  missing key is a presence problem, not a validity one).

</specifics>

<deferred>
## Deferred Ideas

- Note count bound — Phase 20.
- README Limitations rewrite — Phase 22.
- Any provider-outage alerting beyond /health surfacing (out of milestone scope).

</deferred>

---

*Phase: 19-credential-validity-log-addressability-demo-csp*
*Context gathered: 2026-08-14 from milestone decisions + session investigation; UI-SPEC to follow*
