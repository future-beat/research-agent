# Deferred items — Phase 12

Out-of-scope discoveries logged during execution, not fixed by the wave that found them.

## Found during 12-04 (Wave 3)

**`docs/OPERATIONS.md` still describes two defects that Wave 2 (12-03) closed.**

1. The paragraph beginning *"Concurrency and the spend cap interact, and this is not fixed"*
   says the daily cap counts only completed runs and that a burst overshoots it ~3×. 12-03
   replaced that with reservation-based counting under `pg_advisory_xact_lock`; the paragraph
   even points forward to "Phase 12" as the fix. It is now describing history as present tense.
2. The `DEMO_RATE_LIMIT_PER_HOUR` row reads *"Requests per visitor IP"*. 12-03 rekeyed the
   window onto the signed caller identity and demoted `TRUST_FORWARDED_FOR` to logging.
   `DEMO_RESERVED_RUN_USD` is also absent from the env table entirely.

Not fixed here: both belong to the wave that falsified them, and 12-06 owns the phase's
documentation and ADR pass. Wave 3 corrected only the OPERATIONS/README/.env.example claims
about session ownership, expiry and `SESSIONS_TOKEN`, which are its own.

**CLOSED by 12-06 Task 1 (commit `ab54fb5`).** Both items are corrected in `docs/OPERATIONS.md`:
the concurrency paragraph now describes the reservation mechanism and states the residual
(900s stale-reclaim, estimate accuracy) instead of claiming the defect is unfixed, and the
`DEMO_RATE_LIMIT_PER_HOUR` row reads "per caller identity (the signed cookie), not per IP".
`DEMO_RESERVED_RUN_USD` and `IDENTITY_SIGNING_SECRET` were added to the env table, the
`TRUST_FORWARDED_FOR` row now says it is log-only, and `.env.example` carried the same
per-visitor-IP error and was corrected alongside.

---

## Found during 12-06 Task 4 (the live cutover), deferred out of Phase 12

**1. No `Content-Security-Policy` header is served.**

`index.html` is written to be CSP-compatible — no inline event handlers, all DOM through
`el()`/`textContent`, no external resource — and its docstring says so. But the live response
headers (recorded in full in `12-06-SUMMARY.md` § Task 4) carry no CSP header at all. Nothing in
the repo *claims* one is served, so no documented claim is falsified and this is not a Phase 12
defect. It is noted because the expensive half of adopting CSP (writing the page so a strict
policy does not break it) is already paid for, and the cheap half — one response header — has
not been. A future phase gets a real XSS backstop for roughly one line.

**2. No real-browser verification instrument exists for the demo page.**

Every live check in Task 4 was `curl`. Two specified checks could therefore only be verified by
their mechanism rather than their observable: the cookie's invisibility to `document.cookie`
(verified as `HttpOnly` in the response header) and the reload that reveals "Your recent
research" (covered by Task 2's DOM-shim harness and Task 3's static gates against byte-identical
served markup). Both are recorded as gaps in `12-VALIDATION.md`'s Manual-Only table rather than
signed off. Whether that matters enough to justify a browser-automation dependency is a genuine
question for a later phase, not something to smuggle in here.

**3. The rollback path is unit-tested but never exercised live.**

`fly secrets unset IDENTITY_SIGNING_SECRET` + redeploy should degrade the fleet to per-process
ephemeral identity rather than break the demo. Two unit tests cover the degradation and `/health`
would flip `identity_signing` to `false`, but the live path was not run — doing so would have
churned production and discarded the identity continuity just established.
