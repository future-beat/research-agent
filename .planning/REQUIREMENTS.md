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

- [x] **REQ-forty-recorded-answers** *(Phase 21 — complete under the amended criterion,
  shipped and deployed 2026-08-15)*: All 40 golden cases carry recorded real answers,
  replayed and graded keylessly on every push. The record run is a paid operator checkpoint
  (quoted **$17.48** on 2026-08-13; re-quote at run time), sequenced after the judge
  settles. A case the recorder refuses (failed graders or judge) is surfaced as a finding,
  not retried into silence — refusals are the machinery working.
  **Amendment, user-ratified mid-execution 2026-08-15:** the run measured this
  requirement's two clauses in tension — 15 of 40 cases satisfy "only grader-approved
  fixtures are committed" only by failing "all forty recorded". The criterion became:
  every case is **recorded or carries a documented refusal** (`evals/REFUSALS.json`),
  the union enforced by test. Landed 19 recorded / 21 documented, $9.9019 actual against
  the $17.4812 quote. Nothing was forced.

- [x] **REQ-classifier-model** *(Phase 21.5 — complete, executed 2026-08-16; defined mid-milestone 2026-08-15, after
  Phase 21's record run surfaced the drift)*: The classifier runs on `claude-opus-5` —
  measured against all 38 golden cases carrying an expected label: 34/38 correct versus
  Sonnet 5's 29/38, five fixes, zero regressions, +$0.0005 per run (~0.2% of a measured
  run). The measurement is repeated at execution before the switch is trusted (the probe
  was n=1 per case). The four cases BOTH models label `technical` against a golden
  `general` are resolved deliberately — stale labels corrected or the divergence recorded
  — never papered over. Ends with a user-approved paid checkpoint re-attempting the six
  `topic_type`-refused recordings under the fixed classifier; successes move from
  `evals/REFUSALS.json` to fixtures, failures stay documented.

- [x] **REQ-demo-shows-progress** *(complete — shipped PR #34, deployed Fly v22; the Manual-Only human observation was given by the project owner on 2026-08-17: "The demo bug has been fixed." The optional ~$0.22 wall-clock timing of the first researcher signal remains deliberately unspent)* *(inserted 2026-08-16 as Phase 22.5, from a live report)*:
  The demo announces the stage it is starting, not only the stage it finished. Measured on
  the deployed service: the classifier's completion event arrives at +2s and the
  researcher's at +122s, so the page shows one stale label for two minutes and reads as
  frozen — visitors reload and lose the run they were watching. The fix forwards the
  supervisor's existing `routed_to`, which `_stream` currently discards. Phase 19's
  streaming contract (exactly one terminal event; the `run_finished`/`run_failed` pair) and
  its derived CSP must both survive the change.

### Observability

- [x] **REQ-health-credential-validity** *(complete — deployed Fly v18; Manual-Only closed by measurement against production 2026-08-17: both providers report valid=true with checked_at timestamps minutes old, which is the real provider round trip the row required)*: `/health` reports whether the Anthropic and
  Voyage keys actually *work*, via a cached async validity probe (`count_tokens` is free
  for Anthropic; a micro-embed for Voyage), surfaced as new fields beside the existing
  presence booleans. The liveness path still never calls a provider — Fly must not restart
  a healthy container during a provider outage. Probe spend is excluded from or attributed
  in cost accounting deliberately, not silently.

- [x] **REQ-run-finished-session-id** *(Phase 19 — complete, verified 2026-08-14; no deploy dependency)*: `run_finished` log lines carry `session_id`, so a
  completed run is addressable from the logs (the gap cost a wasted live run in Phase 17).

### Data

- [x] **REQ-note-count-bound** *(Phase 20 — complete, verified 2026-08-15, deployed Fly
  v19)*: Notes carry a per-owner count bound with oldest-first
  eviction, with byte-identical semantics across json, memory, chroma, and pgvector,
  proven by the shared 4-arm contract suite. Notes are then bounded by expiry *and* count,
  which kills the README bullet rather than narrowing it.
  **Checkbox flipped by Phase 22's close-out, on Phase 20's behalf.** The requirement was
  verified (`20-VERIFICATION.md`, status passed, 3/3 criteria plus the post-verification
  orphan-bucket gap) and its traceability row has read **Complete** since 2026-08-15; only
  this checkbox was missed. Recorded as a correction rather than flipped silently — and
  Phase 22 deleted the README bullet it killed, which is the evidence it is genuinely done.

### Security

- [x] **REQ-demo-csp-header** *(complete — deployed Fly v18; Manual-Only closed by measurement against production 2026-08-17: the served header's two hashes recomputed from the served page's own inline blocks and matched, exactly one script and one style block, no unsafe-inline. The page working live is what shows the policy does not block its own JS)*: The demo page ships a Content-Security-Policy header that
  its inline JS survives (hash-based, not `unsafe-inline`), verified against the live page.
  Open since Phase 12's deferred items.

### The record

- [x] **REQ-limitations-recorded** *(Phase 22 — complete, executed 2026-08-16)*: Every
  surviving README limitation points at a record:
  a new ADR states cost-approximation-by-design (and why invoice reconciliation was
  rejected), mintable identities already carry ADR-0007, and the database posture moves to
  OPERATIONS with one honest README line. The four closed bullets are **deleted** per the
  standing convention (never rewritten into release notes), and the section intro is
  rewritten: what remains is chosen, recorded, and argued for.
  **Landed:** seven bullets → three. The four closed bullets deleted and verified on the
  git axis — each distinctive phrase enters README once (`+`) and leaves once (`-`, in
  `219e9e3`), and no file outside `.planning/` planning records has ever carried them.
  The three survivors each end at a record: cost → **ADR-0014**
  (`cost-approximation-by-design`; **0014, not 0013** — 21.5 took 0013), identities →
  ADR-0007 (linked since Phase 12, verified rather than re-authored), database → the
  OPERATIONS anchor `#the-free-tier-posture-and-the-upgrade-path`. Intro closes on the
  criterion-5 phrase verbatim. No-orphan sweep over `docs/` + `.planning/codebase/`:
  **zero hits on all four patterns, so the exemption list is empty**. Gates: 828 passed /
  72 skipped keyless, evals PASS 65/65 exit 0, ruff clean, derived-counts and ADR-index
  tests green; four mutations observed red and reverted.

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
| REQ-health-credential-validity | Phase 19 — Credential validity, log addressability, demo CSP | **Verified** (`19-VERIFICATION.md` status: passed, criteria 1–3). Automated half complete and independently re-measured — 20 concurrent `/health` reads against two hanging providers peaked at 0.016s. **Awaiting deploy** for the one thing a keyless suite cannot show: a real provider round trip (19-VALIDATION Manual-Only) |
| REQ-run-finished-session-id | Phase 19 — Credential validity, log addressability, demo CSP | **COMPLETE** — verified (`19-VERIFICATION.md`, criterion 4), and unlike the other two Phase 19 requirements this one has **no** Manual-Only dependency and needs no deploy. Met literally rather than by reinterpretation (P-07): the line NAMED `run_finished` carries `session_id` on all four routes, exactly once per run, alongside `run_id`; the graph's terminal line is renamed `graph_finished` and asserted to carry no session identity, since it structurally cannot know one. Six test items, three mutation reds |
| REQ-demo-csp-header | Phase 19 — Credential validity, log addressability, demo CSP | **Verified** (`19-VERIFICATION.md`, criterion 5) — both hashes re-derived a fourth time by the verifier, byte-identical. **Awaiting deploy**: the requirement says "verified against the live page", and browser CSP enforcement cannot run in pytest. The automated half is done (derived seven-directive policy, no `unsafe-` source, six gates, four mutation reds, `index.html` at zero edits); UI-SPEC acceptance checks 1–7 against the deployed page are 19-VALIDATION's Manual-Only row |
| REQ-note-count-bound | Phase 20 — Note count bound | **Complete** (verified, `20-VERIFICATION.md` status: passed, 3/3 criteria + the post-verification orphan-bucket gap closed; deployed Fly v19, 2026-08-15) |
| REQ-forty-recorded-answers | Phase 21 — Forty recorded answers | **Complete under the amended criterion** (19 recorded / 21 documented refusals, union enforced by `test_every_golden_case_is_recorded_or_documented_as_refused`; $9.9019 actual vs $17.4812 quoted; merged PR #30, deployed Fly v20, 2026-08-15) |
| REQ-classifier-model | Phase 21.5 — Classifier on Opus 5 | **Complete** — probe repeated against the corrected labels: Opus 5 **37/38** vs Sonnet 5 **32/38**, five fixes, zero regressions, $0.0459 vs $0.0439 quoted. Classifier defaults to `claude-opus-5` directly (never `MODEL` — a `MODEL` default would have made local record runs classify with Sonnet and re-fail); mutation flipping it back reds 7 tests keylessly. Three labels relabelled, `chatty-label-falls-back` left untouched at its stratum floor with the conflict recorded. Re-record: 6 of 8 landed ($1.4001 vs $3.7120 quoted); the 2 refusals moved to *different* graders, which is the fix working. ADR-0013 |
| REQ-limitations-recorded | Phase 22 — Limitations recorded | **Complete** — seven Limitations bullets → three, executed 2026-08-16. Four deletions verified on the git axis (each phrase in once, out once at `219e9e3`; no `docs/` surface ever carried them) and the no-orphan sweep over `docs/` + `.planning/codebase/` returns **zero hits, exemption list empty**. Survivors linked: cost → **ADR-0014** (0014, not 0013 — 21.5 took 0013), identities → ADR-0007 (verified, not re-authored), database → `OPERATIONS.md#the-free-tier-posture-and-the-upgrade-path`, anchor re-derived from the heading. Intro is the closed/recorded/discovered ledger ending "chosen, recorded, and argued for". Whole-README pass re-derived three stale counts (827→828 twice, twelve→fourteen ADRs). 828/72 keyless, evals 65/65 exit 0, ruff clean, 4 mutations red |

**Coverage:** 8/8 v1.2 requirements mapped (7 at milestone open + REQ-classifier-model,
defined mid-milestone 2026-08-15). No orphans.

**At milestone close (2026-08-16):** **6 of 8 checked**. The two unchecked —
`REQ-health-credential-validity` and `REQ-demo-csp-header` — are **verified in their
automated half and awaiting the manual deploy**, which is 19-VALIDATION's two Manual-Only
rows: browser CSP enforcement and a real provider round trip cannot run in pytest. They
are not incomplete work; they are work whose last gate is a deploy, and they stay
unchecked rather than being flipped on a promise.
