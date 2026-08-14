# Requirements: v1.2 — Nothing uncovered

**Defined:** 2026-08-13
**Core Value:** The pipeline never answers from model knowledge when it should be answering
from research — and it is demonstrable to a stranger in one click.

## Framing — read before planning any of these

The v1.1 README carries seven limitations. An investigation on 2026-08-13 (recorded in the
milestone-start commit and PROJECT.md) sorted them into four that close **without a
successor limitation** and three that cannot close honestly: cost-approximation is an
epistemic fact about client-side accounting, mintable identities are ADR-0007's chosen
position, and the free-tier database is a cost-proportionate posture. The milestone's
acceptance bar, on every closure: **no new bullet is born.** The three keepers don't close —
they get records, so the Limitations section's terminal state is "chosen and argued for,
not backlog."

One reversal is in scope and must be ceremonised: moving the judge off the critic's model
supersedes ADR-0010, which reopens the reversal register v1.1 closed as spent. That is
deliberate and the new record (ADR-0012) must say so.

Ordering constraint that shapes the roadmap: **the judge settles before the record run** —
judge verdicts are recorded once, as fixture metadata, and recording 40 cases under a judge
about to be replaced would file verdicts from an abandoned judge.

## v1.2 Requirements

### Evaluation

- [x] **REQ-judge-independent-of-critic** *(Phase 18 — complete, verified 2026-08-14)*: The eval judge runs on a model independent of
  the critic — default `claude-opus-4-8`: not the critic's model, stronger than the writer
  it grades, zero cost change. The judge's response handling checks `stop_reason` before
  reading content (a safety-classifier refusal today surfaces as a misleading parse error —
  `graders.py:733`), and the price table carries an Opus 4.8 row. ADR-0012 records the
  supersession of ADR-0010 and the reopening of the reversal register.

- [ ] **REQ-forty-recorded-answers**: All 40 golden cases carry recorded real answers,
  replayed and graded keylessly on every push. The record run is a paid operator checkpoint
  (quoted **$17.48** on 2026-08-13; re-quote at run time), sequenced after the judge
  settles. A case the recorder refuses (failed graders or judge) is surfaced as a finding,
  not retried into silence — refusals are the machinery working.

### Observability

- [ ] **REQ-health-credential-validity**: `/health` reports whether the Anthropic and
  Voyage keys actually *work*, via a cached async validity probe (`count_tokens` is free
  for Anthropic; a micro-embed for Voyage), surfaced as new fields beside the existing
  presence booleans. The liveness path still never calls a provider — Fly must not restart
  a healthy container during a provider outage. Probe spend is excluded from or attributed
  in cost accounting deliberately, not silently.

- [ ] **REQ-run-finished-session-id**: `run_finished` log lines carry `session_id`, so a
  completed run is addressable from the logs (the gap cost a wasted live run in Phase 17).

### Data

- [ ] **REQ-note-count-bound**: Notes carry a per-owner count bound with oldest-first
  eviction, with byte-identical semantics across json, memory, chroma, and pgvector,
  proven by the shared 4-arm contract suite. Notes are then bounded by expiry *and* count,
  which kills the README bullet rather than narrowing it.

### Security

- [ ] **REQ-demo-csp-header**: The demo page ships a Content-Security-Policy header that
  its inline JS survives (hash-based, not `unsafe-inline`), verified against the live page.
  Open since Phase 12's deferred items.

### The record

- [ ] **REQ-limitations-recorded**: Every surviving README limitation points at a record:
  a new ADR states cost-approximation-by-design (and why invoice reconciliation was
  rejected), mintable identities already carry ADR-0007, and the database posture moves to
  OPERATIONS with one honest README line. The four closed bullets are **deleted** per the
  standing convention (never rewritten into release notes), and the section intro is
  rewritten: what remains is chosen, recorded, and argued for.

## Out of Scope

- **Closing the cost-approximation bullet** — any client-side figure is an estimate;
  Anthropic's Admin cost API is aggregate and delayed, and wiring it adds an admin secret
  (a worse trade). It gets a record instead.
- **Closing the mintable-identities bullet** — any real closure is an auth wall, which
  PROJECT.md's core value and ADR-0007 both rule out.
- **Closing the free-tier-database bullet by paying** — recurring spend that buys nothing
  at demo traffic; an operator toggle any day, not a milestone requirement.
- **Semantic note dedup or summarisation** — no semantics four vector backends can agree
  on; the count bound is the honest bound.
- **The `DATABASE_URL` rollback drill** — operational exercise, not a feature.

## Traceability

Every v1.2 requirement maps to exactly one phase. Filled by `/gsd:roadmap` on 2026-08-13.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-judge-independent-of-critic | Phase 18 — Independent eval judge | **Complete** (verified, `18-VERIFICATION.md` status: passed) |
| REQ-health-credential-validity | Phase 19 — Credential validity, log addressability, demo CSP | **Implemented** (19-01, wave 1; `19-01-SUMMARY.md`) — not yet Complete: the phase is unverified, and a real provider round trip is keyless-suite-invisible until the first deploy after merge (19-VALIDATION Manual-Only) |
| REQ-run-finished-session-id | Phase 19 — Credential validity, log addressability, demo CSP | Pending |
| REQ-demo-csp-header | Phase 19 — Credential validity, log addressability, demo CSP | Pending |
| REQ-note-count-bound | Phase 20 — Note count bound | Pending |
| REQ-forty-recorded-answers | Phase 21 — Forty recorded answers | Pending |
| REQ-limitations-recorded | Phase 22 — Limitations recorded | Pending |

**Coverage:** 7/7 v1.2 requirements mapped. No orphans.
