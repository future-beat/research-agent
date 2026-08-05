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
