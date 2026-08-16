# Roadmap: research-agent

## Overview

Phases 1–9 built and shipped a supervisor-routed research pipeline as a real service:
deterministic routing, vector memory, an HTTP surface, cost accounting with a spend cap,
an eval harness, a Docker/CI/Fly deploy, Postgres+pgvector backends, and a public demo
with guardrails. It is live at `research-agent.fly.dev`.

Milestone v1.1 took on all nine items from the README's `## Limitations` list and closed
every one. Six of them reversed a design position the project argues *for*, so the milestone
opened by promoting the five load-bearing decisions into numbered ADRs — every later reversal
names the ADR it supersedes, and the register of expected reversals closed as spent. The work ran
outward-in: infrastructure nothing else depends on first (multi-machine Postgres, pooling),
then identity and lifecycle, then data migration and cost, then the measurement that makes
quality changes visible, and only then the two reversals that change what the pipeline *says* —
an independent critic, and follow-ups that can reach for new information.

The service runs on two machines against Supabase Postgres at `research-agent.fly.dev`, on
release **v13**. One phase landed after the v1.1 close and before any milestone reopened:
**17.5**, a hotfix enabling row level security on every table the service creates — shipped
the same day it was found, deployed, and closed with nothing outstanding.

**Milestone v1.2 "Nothing uncovered" is now open (Phases 18–22).** An investigation on
2026-08-13 sorted the v1.1 README's seven remaining limitations into four that close without
a successor limitation (judge independence, health credential validity, the note count bound,
and the forty recorded golden answers) and three that cannot close honestly and instead get a
record (cost-approximation-by-design, mintable identities via ADR-0007, and the free-tier
database posture). One reversal is in scope and ceremonised: moving the judge off the critic's
model supersedes ADR-0010, deliberately reopening the reversal register v1.1 closed as spent.

**Definition of done for this project:** demonstrable to an employer. Live URL that works,
green CI, a README a stranger can skim. Surface tidiness is part of the deliverable.

## Milestones

- ✅ **v1.0 Production pipeline** — Phases 1–9 (shipped, plus post-Phase-9 housekeeping). Pre-GSD; record remastered 2026-08-12. → [archive](milestones/v1.0-ROADMAP.md) · [requirements](milestones/v1.0-REQUIREMENTS.md)
- ✅ **v1.1 Closing the limitations list** — Phases 10–17 + the inserted 10.5, **shipped 2026-08-11** (Fly v12). All nine limitations the v1.0 README listed are closed; six were deliberate reversals, each superseding a numbered ADR. → [archive](milestones/v1.1-ROADMAP.md) · [requirements](milestones/v1.1-REQUIREMENTS.md) · [audit](v1.1-MILESTONE-AUDIT.md)
- 🚧 **v1.2 Nothing uncovered** — Phases 18–22, **in progress** (roadmap created 2026-08-13). Closes four README limitations honestly and records the three that cannot close honestly, so the Limitations section's terminal state is "chosen and argued for," not backlog.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Production pipeline (Phases 1–9) — SHIPPED</summary>

Full remastered detail in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md);
per-phase records (SUMMARY + retroactive VALIDATION, reconstructed 2026-08-12 and labeled
as such) in `.planning/milestones/v1.0-phases/`.

- [x] **Phase 1: Core loop** - Supervisor pattern with deterministic Python routing
- [x] **Phase 2: Memory** - Voyage embeddings, cosine recall with a relevance floor, persisted
- [x] **Phase 3: Conversation & resilience** - Follow-ups, pluggable stores, per-node retry, tests
- [x] **Phase 4: Service** - FastAPI, blocking and SSE, sessions surviving restart
- [x] **Phase 5: Cost & observability** - Date-aware pricing, spend cap as routing rule, `/metrics`
- [x] **Phase 6: Evals** - Twelve-case golden set, deterministic graders plus an LLM judge
- [x] **Phase 7: Ship it** - Two-stage Dockerfile, non-root, CI gates, Fly deploy
- [x] **Phase 8: Stateless** - Postgres and pgvector behind the existing interfaces
- [x] **Phase 9: Demo & guardrails** - Streaming demo page, rolling spend cap, rate limit, token
- [x] **Post-Phase-9 housekeeping** - `src/` package reorganisation, one consolidated `pyproject.toml`

</details>

<details>
<summary>✅ v1.1 Closing the limitations list (Phases 10–17, plus 10.5) — SHIPPED 2026-08-11</summary>

Full detail in [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

- [x] **Phase 10: ADRs and doc correctness** - Promote the load-bearing five to numbered ADRs; fix verified-false docs; redeploy so live matches `main`
- [x] **Phase 10.5: Close the live endpoint exposure (INSERTED, hotfix)** - Guard the unauthenticated session read/delete paths and stop leaking exception text; shipped as Fly v4 the day it was found
- [x] **Phase 11: Multi-machine state and pooled Postgres** - Two machines over Supabase Postgres, one pool per machine
- [x] **Phase 12: Caller identity, session ownership, bounded stores** - An auto-issued signed cookie; sessions and notes own and expire; the cap reserves against in-flight runs
- [x] **Phase 13: Embedding model migration** - Copy a corpus unchanged, or re-embed it at a new model and dimension; cost quoted before spending
- [x] **Phase 14: Real cost accounting** - Discounts and response-observed `inference_geo` at one choke point; Voyage spend counted for the first time
- [x] **Phase 15: Answer-quality evals** - Forty golden cases; real recorded answers graded keylessly and free on every push
- [x] **Phase 16: Independent critic model** - `CRITIC_MODEL`, production on Opus 5 — the gate more capable than the writer it checks
- [x] **Phase 17: Follow-ups that can reach for new information** - The unsupported follow-up researches instead of refusing; grounding kept, and it was never what was being given up

**Closed after the audit:** the `_execute` ledger hole (W1), the reservation's stale arithmetic
(W2, $0.20 → $0.30), and the five unreconciled VALIDATION contracts.

</details>

<details>
<summary>✅ Phase 17.5 — Row level security on the public schema (INSERTED, hotfix, post-close)</summary>

**Inserted 2026-08-12, after v1.1 shipped and was tagged.** It carries a v1.1-style number
because it closes a defect in v1.1's infrastructure, but it is **not part of the v1.1
milestone as archived** — the tag, the audit and `milestones/v1.1-*.md` all predate it, and
no milestone was open when it landed.

- [x] **Phase 17.5: Row level security on the public schema** - Every Postgres table the
  service creates denies every role but its owner, applied by the schema DDL itself so a
  table created later (`migrate.py embeddings re-embed --to`) cannot be missed

**Trigger:** a Supabase security-linter report — five `public` tables with RLS disabled,
plus `runs` flagged for exposing `session_id`. Not found by the requirements list, the
milestone audit, or any phase gate. Second time a live exposure arrived from outside the
plan, after Phase 10.5.

**Why it is more than a privacy finding:** `runs` is the daily spend cap's only input
(`spend_since` sums it). Measured against the real DDL on a local stand-in, a role holding
the grants Supabase hands `anon` deleted every row of `runs` without error — an emptied
ledger reads as $0 spent and the one control bounding the Anthropic bill stops bounding it.

**Shipped as Fly release v13 on 2026-08-12**, deployed by hand after three green merges
produced no release at all. Verified live: both machines on v13, all three Postgres stores
reachable, and the row counts unchanged at 7 sessions / 10 runs / 8 notes — which is the
proof that matters in both directions, since a failed `ALTER` would have surfaced the store
as unreachable and a missing owner exemption would have shown zeros with no error.

**Closed 2026-08-12 — nothing outstanding.** The one-time `REVOKE` of the
`anon`/`authenticated` grants (which cannot live in code, since those roles do not exist on
a plain Postgres) was run and confirmed: all five tables report `owner = postgres`,
`rls_on = t`, `api_grants = (none)`, and no `postgres`-granted default privileges remain to
cover future tables. The provider's own linter agrees — the five `rls_disabled_in_public`
errors and the `sensitive_columns_exposed` error on `runs` are cleared, replaced by five
`INFO` `rls_enabled_no_policy` notices that are the correct end state and must **not** be
"fixed" by adding a policy.

Records: [`17.5-CONTEXT.md`](milestones/v1.1-phases/17.5-row-level-security-on-the-public-schema/17.5-CONTEXT.md) ·
[`17.5-01-SUMMARY.md`](milestones/v1.1-phases/17.5-row-level-security-on-the-public-schema/17.5-01-SUMMARY.md) ·
[`17.5-VALIDATION.md`](milestones/v1.1-phases/17.5-row-level-security-on-the-public-schema/17.5-VALIDATION.md)

</details>

### 🚧 v1.2 Nothing uncovered (Phases 18–22) — IN PROGRESS

Phase numbering continues from v1.1's close (Phase 17, plus the post-close 17.5 hotfix), so
v1.2 starts at Phase 18. Ordering is constrained: the judge phase must settle before the
record run (judge verdicts are recorded once, as fixture metadata), and the record run and
the README/records close-out sit at the end, since the close-out deletes bullets the other
phases close.

- [x] **Phase 18: Independent eval judge** - `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8`, independent of the critic and the writer; ADR-0012 supersedes ADR-0010
- [x] **Phase 19: Credential validity, log addressability, demo CSP** - `/health` reports whether keys actually work; `run_finished` carries `session_id`; the demo page ships a hash-based CSP header
- [x] **Phase 20: Note count bound** - A per-owner count cap with oldest-first eviction, identical across all four backends
- [x] **Phase 21: Forty recorded answers** - Every golden case is recorded or carries a documented refusal (amended mid-run, user-ratified): 19 recorded, 21 in `evals/REFUSALS.json`, union enforced by test; $9.90 actual vs $17.48 quoted
- [x] **Phase 21.5: Classifier on Opus 5** - The classifier runs `claude-opus-5`, measured 37/38 vs Sonnet 5's 32/38 against the corrected labels (five fixes, zero regressions, +0.2%/run); three disputed labels relabelled and one left with its structural conflict recorded; six of eight topic_type-refused cases re-recorded, the two remaining refusing on different graders
- [x] **Phase 22: Limitations recorded** - Every surviving README limitation points at a record; the closed bullets are deleted, not rewritten into release notes — seven bullets became three, the four deletions verified on the git axis and orphan-free everywhere the sweep reaches
- [x] **Phase 22.5: The demo shows progress (INSERTED, hotfix)** - The stream announces the stage it is STARTING, not only the one it finished, so the demo stops looking dead for the two minutes the researcher runs

## Phase Details

<details>
<summary>✅ v1.0 phase details (Phases 1–9)</summary>

> Remastered 2026-08-12: each phase below now has a reconstructed record —
> `NN-SUMMARY.md` and a retroactive `NN-VALIDATION.md` — under
> `.planning/milestones/v1.0-phases/<NN-slug>/`, and the milestone is archived in
> [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

### Phase 1: Core loop
**Goal**: A question routes through a supervisor to workers and returns a grounded report
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 2: Memory
**Goal**: Notes persist and are recalled by similarity, not by growing the prompt
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 3: Conversation & resilience
**Goal**: Follow-ups work over prior notes; stores are pluggable; transient failures retry
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 4: Service
**Goal**: The pipeline is reachable over HTTP, blocking or streaming, with durable sessions
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 5: Cost & observability
**Goal**: Every run reports what it cost, and a spend cap stops runaway runs
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 6: Evals
**Goal**: The pipeline's behaviour is checkable against a golden set
**Status**: Complete — found a real bug (the unreachable revision cap) on its first run
**Plans**: Complete (pre-GSD)

### Phase 7: Ship it
**Goal**: The service builds to an image, passes CI gates, and deploys
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 8: Stateless
**Goal**: Sessions, metrics, and notes can live in Postgres/pgvector behind the same interfaces
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 9: Demo & guardrails
**Goal**: A stranger can use the live demo without it being abusable
**Status**: Complete
**Plans**: Complete (pre-GSD)

### Phase 9.1: Package reorganisation (housekeeping)
**Goal**: `src/` layout and one `pyproject.toml`, so a passing test run can't rely on a module that never reaches the image
**Status**: Complete
**Plans**: Complete (pre-GSD)

</details>

### Phase 18: Independent eval judge
**Goal**: The eval judge grades every case on a model independent of the critic, and a judge
refusal surfaces as a finding rather than a misleading parse error
**Depends on**: Nothing (first phase of v1.2)
**Requirements**: REQ-judge-independent-of-critic
**Success Criteria** (what must be TRUE):
  1. `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8` — not the critic's model
     (`claude-opus-5`), stronger than the writer it grades (Sonnet 5), at zero cost change
     against `/pricing`.
  2. A judge response the safety classifier refuses is surfaced as a graded finding, because
     `graders.py` checks `stop_reason` before reading content instead of misparsing it.
  3. ADR-0012 exists, records the supersession of ADR-0010, and states plainly that this
     reopens the reversal register v1.1 closed as spent.
  4. The price table carries an Opus 4.8 row, so a judge run's cost is reported rather than
     landing on `pricing_unknown`.
**Plans**: 4 plans

Plans:
- [x] 18-01-PLAN.md — PRICES row + `JUDGE_MODEL` default flip in one commit, independence pinned against the deployed critic
- [x] 18-02-PLAN.md — the refusal guard: `stop_reason` checked before content, a decline is a graded finding reaching the recorder's failed-graders branch
- [x] 18-03-PLAN.md — ADR-0012 supersedes ADR-0010, index re-derived with a derived-counts checker, the 0005→0010→0012 chain test extended in the same commit
- [x] 18-04-PLAN.md — the collision line's premise re-derived (silent at shipped defaults, points at ADR-0012), every other judge==critic doc surface cleaned

**Status: COMPLETE (2026-08-14).** All four success criteria hold, each with a measured gate.
Final gate keyless: **749 passed / 67 skipped** exit 0; offline evals **41/41 (100% vs 90%
required)** exit 0; ruff clean. Thirteen mutations observed red across the four waves, plus
three honest greens with recorded reasons — ledger in `18-VALIDATION.md`. **Deferred and
recorded, not silent:** a real Opus 4.8 judge verdict has never round-tripped (every path is
fake-driven); the ~$0.06 one-verdict probe belongs to Phase 21's record run. **`README.md:285`
is deliberately left contradicting the tree** — Phase 22 deletes that Limitations bullet.

### Phase 19: Credential validity, log addressability, demo CSP
**Goal**: `/health` reports whether the API keys actually work without touching liveness, a
completed run is addressable from its logs, and the demo page's inline JS survives a real CSP
**Depends on**: Nothing (independent of Phase 18; sequenced here for milestone flow)
**Requirements**: REQ-health-credential-validity, REQ-run-finished-session-id, REQ-demo-csp-header
**Success Criteria** (what must be TRUE):
  1. `/health` surfaces new credential-validity fields for Anthropic and Voyage, beside the
     existing presence booleans, backed by a cached async probe (`count_tokens` for
     Anthropic, a micro-embed for Voyage).
  2. The liveness path Fly's health check reads still never calls a provider — a healthy
     container is not restarted during a provider outage.
  3. Probe spend is either excluded from cost accounting or attributed within it, and the
     code states which, deliberately rather than silently.
  4. `run_finished` log lines carry `session_id`, so a completed run is addressable from the
     logs without cross-referencing another line.
  5. The demo page ships a hash-based Content-Security-Policy header (no `unsafe-inline`)
     and its inline JS still runs, verified against the live page.
**Plans**: 3 plans

Plans:
- [x] 19-01-PLAN.md — the cached credential probe: fire-and-forget on the existing `_probes()` pool, invalid vs unreachable kept distinct, Voyage probe spend excluded and pinned (wave 1)
- [x] 19-02-PLAN.md — `csp.py` derives the policy from the page itself, attached to the one `FileResponse` branch, with the counts and handler gates that catch a shape change (wave 2)
- [x] 19-03-PLAN.md — `run_finished` moves to where `session_id` exists, the graph's terminal line renamed honestly, then the OPERATIONS/README doc pass (wave 3)

**Sequencing note:** the three surfaces are conceptually independent but all three edit
`service.py` and `tests/test_service.py`, so they run as three sequential waves rather than in
parallel. Success criterion 4's literal wording is honoured by plan 19-03's P-07: the
service-side line is the one named `run_finished`, and the graph's becomes `graph_finished`.
**UI hint**: yes

**Executed 2026-08-14** — all three waves complete; 19-VALIDATION reconciled (`status:
complete`, `nyquist_compliant: true`). 772 passed / 67 skipped keyless (+23 for the phase),
offline evals 41/41 real exit 0, ruff clean. All five success criteria met, criterion 4
literally: the line named `run_finished` carries `session_id` on all four routes, exactly
once per run, with `run_failed` as its complement on both the blocking and streaming paths —
the streaming half of which this phase had to ADD, having found that a failed stream logged
nothing at all. **Two Manual-Only verifications remain OPEN**, both awaiting the manual
deploy: the live page under the CSP header (criterion 5's "verified against the live page"
half, UI-SPEC acceptance checks 1–7) and a real provider probe round-trip.

### Phase 20: Note count bound
**Goal**: Notes are bounded by count as well as expiry, with identical eviction behaviour on
every backend
**Depends on**: Nothing (independent of Phases 18–19; sequenced here for milestone flow)
**Requirements**: REQ-note-count-bound
**Success Criteria** (what must be TRUE):
  1. Each owner's notes are capped at a fixed per-owner count, with the oldest note evicted
     first once the cap is exceeded.
  2. Eviction semantics are byte-identical across json, memory, chroma, and pgvector, proven
     by the shared 4-arm contract suite (same inputs, same outcomes, all four backends).
  3. The README's notes-unbounded-by-count limitation is falsified by a passing test, not
     merely narrowed in prose.
**Plans**: 2 plans

Plans:
- [x] 20-01-PLAN.md — `NOTE_CAP_PER_OWNER` (default 100, discount-factor clamp) plus oldest-first eviction inside all four `add()` implementations, proven by four new 4-arm contract cases, a chroma reordered-`get()` gate, and a migration-bypass pin (wave 1)
- [x] 20-02-PLAN.md — OPERATIONS gains the knob row, DESIGN judged by reading, README whole-file pass with measured counts and the Limitations bullet untouched for Phase 22, 20-VALIDATION reconciled (wave 2)

**Sequencing note:** the two plans share no files but the dependency is real — the doc pass
describes what Wave 1 shipped and README's counts can only be measured after Wave 1's tests
land, so 20-02 runs as wave 2. Tie-breaking is the researched hazard (14 unique
`time.time()` values per 200 calls, measured): eviction order is insertion-native on every
backend — list order / an explicit chroma `seq` / BIGSERIAL id — never wall-clock alone.

**Executed 2026-08-14** — both waves complete, 7 commits. All three success criteria hold:
the cap evicts oldest-first per owner (criterion 1), byte-identically on all four arms with
pgvector run **armed** at `:54329` rather than skipped (criterion 2), and the README
limitation is falsified **by a passing test** rather than narrowed in prose (criterion 3).
Final gates: keyless **796 passed / 71 skipped** (+23 / +4, reconciled test by test against a
zero-removal `--collect-only` id diff); contract file armed **118 / 1**; offline evals 41/41
real exit 0; ruff clean both forms. Seven mutations observed red for the six the plans named.
**The phase's finding:** the shared 4-arm suite is *structurally blind* to a chroma
`created_at`-vs-`seq` tie-break regression — chromadb 1.4.1 returns `get()` in insertion
order, so the wrong sort passes anyway — which is why a stubbed reordered-`get()` gate ships
beside it. **`README.md:291` is deliberately left contradicting the tree** ("Notes are bounded
by expiry alone"), the third such bullet standing; Phase 22 deletes all three.

### Phase 21: Forty recorded answers
**Goal**: All 40 golden cases carry a real recorded answer, replayed and graded keylessly on
every push
**Depends on**: Phase 18 (the judge must settle first — verdicts are recorded once, as fixture
metadata, and recording under a judge about to be replaced would file verdicts from an
abandoned judge)
**Requirements**: REQ-forty-recorded-answers
**Success Criteria** (what must be TRUE):
  1. All 40 golden cases have a fixture carrying a real recorded answer plus the settled
     judge's verdict as metadata.
  2. Every push replays and grades all 40 cases keylessly, with no live API key required.
  3. A case the recorder refuses (failed graders or judge) is surfaced as a finding in the
     record run's output, not silently retried or dropped.
  4. The paid checkpoint is re-quoted at run time (quoted **$17.48** on 2026-08-13) and the
     actual spend is reported against that quote.
**Plans**: 3 plans

Plans:
- [x] 21-01-PLAN.md — keyless machinery: the completeness and settled-judge gates proven red in both directions before any spend, the pre-spend baseline measured, the operator runbook and fresh quote captured (wave 1)
- [x] 21-02-PLAN.md — the paid operator act: checkpoint 1 → one-case calibration (re-records the stale-judge fixture, closes Phase 18's deferred judge probe), constants corrected, re-quote → checkpoint 2 → the 39 in four resumable `--case` batches, refusals surfaced as findings (wave 2)
- [x] 21-03-PLAN.md — closure: the real-directory pins go live with their reds observed, the denominator and runtime measured, README/OPERATIONS re-derived (Limitations bullet byte-untouched), actual-vs-quote reconciled from report JSONs (wave 3)

**Sequencing note:** three sequential waves, no parallelism — 21-02 spends real money only
against gates 21-01 proved can bite, and 21-03's pins can only be committed green once
21-02's fixtures exist. The two paid stages inside 21-02 are blocking user checkpoints
(`autonomous: false`); nothing passes `--yes` outside them.

**Executed 2026-08-15** (merged PR #30, deployed Fly v20 — a no-behaviour-change release;
the image excludes `evals/`). Five paid stages, each user-approved: calibration $0.2496,
batches A–D $1.9011/$2.1556/$2.2025/$3.3932 — **$9.9019 total against the $17.4812 quote
(56.6%)**, metered pipeline only; 85 judge calls bill separately and are not metered.
**Criterion 1 was amended mid-run, user-ratified:** batch A refused 3 of 10, exposing the
requirement's two clauses (all forty recorded; only grader-approved fixtures committed) as
incompatible on the real pipeline. Landed: **19 recorded, 21 documented in
`evals/REFUSALS.json`**, the union enforced by test with three mutations observed red.
Nothing forced. Findings the run bought: (1) classifier drift — six refusals on the same
`topic_type expected 'general', got 'technical'` mismatch, invisible to the keyless suite
which stubs the classifier (→ Phase 21.5); (2) the judge's verdict truncated twice at
`max_tokens=1500` shared with adaptive thinking, exactly as `graders.py:758` predicted;
(3) record-time and replay-time grading disagree — six fixtures passed record-time and
failed replay: five on contested-case pins whose re-authoring was tried and reverted (the
pins must also satisfy the hand-authored reference reports; `dataset.py` ends the phase
unmodified), one a hedged half-answer (admits the gap, then estimates anyway) that
record-time grading approved — kept as a finding, not passed by widening
`REFUSAL_PATTERNS`. Evals denominator 41 → **59** (40 behavioural + 19 replayed), exit 0;
806 passed / 72 skipped; ruff clean.

### Phase 21.5: Classifier on Opus 5
**Goal**: Classification runs on the model measured better against the golden labels, the
divergent labels are resolved deliberately, and the six topic_type-refused recordings get
one re-attempt under the fixed classifier
**Depends on**: Phase 21 (the record run is what surfaced and measured the drift; the
refusal list it wrote is this phase's re-record input)
**Requirements**: REQ-classifier-model
**Success Criteria** (what must be TRUE):
  1. The classifier calls `claude-opus-5` in production, as a deliberate per-node model
     choice in the ADR record (the critic precedent: Phase 16 / `CRITIC_MODEL`), not a
     silent constant edit.
  2. The 2026-08-15 probe (34/38 vs 29/38, zero regressions, +$0.0005/run) is REPEATED at
     execution and holds before the switch is trusted — the original was n=1 per case and
     classification is not pinned deterministic.
  3. The four cases both models label `technical` against a golden `general` are resolved
     deliberately: labels corrected with the reasoning recorded, or the divergence
     documented — the `general` stratum is not quietly gutted either way.
  4. A user-approved paid checkpoint re-attempts the six `topic_type`-refused recordings
     under the new classifier (~$2.40 at measured per-case actuals, re-quoted at run
     time); successes move from `evals/REFUSALS.json` to `evals/fixtures/`, failures stay
     documented, and the completeness union stays total throughout.
  5. Suite, evals and docs reflect whatever the measurements produce — counts re-measured,
     never carried.
**Plans**: 2 plans

Plans:
- [ ] 21.5-01-PLAN.md — the keyless wave: `classifier_model()` defaulting to `claude-opus-5` directly (the researched trap closed and mutation-gated), four-site threading with the three known smoke reds observed then deliberately updated, provenance-only `models.classifier` (the 19-red staleness cascade demonstrated and reverted), the committed spend-guarded probe importing the real prompt, the fly.toml pin with its inverted fail-direction, the three-way label resolution inside the stratum floors, ADR-0013, and the doc prose (wave 1)
- [ ] 21.5-02-PLAN.md — the paid wave, autonomous: false: checkpoint 1 the probe repeat (~$0.05, shape must hold — Opus ≥ Sonnet, zero regressions — or checkpoint back with the numbers), checkpoint 2 the re-record of the DERIVED topic_type-refused list (eight per research, not the believed six; re-quoted at run time), one attempt each with same-commit union-gate discipline, then the close-out: counts re-measured, REQ-classifier-model flipped, Phase 22's exact precondition gates re-run and passing (wave 2)

**Sequencing note:** defined mid-milestone 2026-08-15 (the 10.5/17.5 precedent) after
Phase 21's record run measured the drift. Runs BEFORE Phase 22 so the close-out records
only what genuinely survives. The user proposed the upgrade; the measurement confirmed it
against the orchestrator's initial skepticism, which is worth remembering when weighing
"differently right" intuitions against a $0.05 probe.

### Phase 22.5: The demo shows progress (INSERTED, hotfix)
**Goal**: A visitor watching the demo sees the stage that is running, not the last one that
finished, so the two minutes the researcher spends searching read as progress rather than
a hang
**Depends on**: Nothing. Inserted 2026-08-16 from a live report, the third time a demo-facing
problem arrived from outside the roadmap (after 10.5 and 17.5)
**Requirements**: REQ-demo-shows-progress
**Success Criteria** (what must be TRUE):
  1. The stream emits an event when a stage STARTS, derived from the supervisor's existing
     `routed_to`, in addition to the completion events it already sends.
  2. The demo page renders the starting stage immediately and resolves it when the matching
     completion arrives — no stage row is ever orphaned or duplicated.
  3. Phase 19's streaming guarantees survive: exactly one terminal event per stream, the
     `run_finished`/`run_failed` pair unchanged, and the derived CSP still matches the page
     after the edit (hashes re-derived, never hand-maintained).
  4. The gap a visitor sees between the first and second visible stage is bounded by the
     supervisor's routing, not by the researcher's runtime — measured, not asserted.
  5. The blocking `/research` route and the follow-up routes are unaffected in shape.

**Measured evidence this phase exists (2026-08-16, one $0.2235 reproduction against v21):**
`classifier` at +2s, `researcher` at **+122s**, then writer/critic every 5–12s to a terminal
`result` at +183s. The stream, the pipeline and the terminal contract were all healthy — the
run recorded and was billed. The only defect is 120 seconds of silence at the front, which is
exactly where a first-time visitor decides whether the thing works. `_stream` discards the
supervisor event as "pure noise on the wire"; that comment was true when only completions
mattered and is now backwards, because `routed_to` is the sole signal of what is starting.

**Plans**: 1 plan

Plans:
- [x] 22.5-01-PLAN.md — the whole hotfix in one wave: T1 the tracer (the four-line `_stream`
  forward with its headline gate observed red on today's code BEFORE the fix, the page's
  per-run pending pointer upgraded in place inside the single `<script>` block with zero CSS,
  the keyless wire-to-page vocabulary coupling, and the two falsified assertions updated in the
  same commit so the suite is never red); T2 the gates one happy path cannot reach (the
  terminal-routing filter with its non-vacuity trace assertion, the scripted two-revision
  alternation that is the server-side proxy for the client's row-keying property, the
  `/ask/stream` inheritance, and byte-identical proof for the two protected Phase 19 tests);
  T3 README's public SSE example checked against a real capture, the VALIDATION record closed
  with the paid post-deploy row honestly left open, and the arithmetic re-measured against
  827/72 (wave 1)

**Executed 2026-08-16.** 832 passed / 72 skipped keyless (827 → 832; `-k stream` 23 → 28);
evals 65/65 exit 0; ruff clean. **The headline gate was observed red on a wholly unmodified
tree** — `assert 1 == 2`, one researcher event where the gate demands two — which is what
makes it evidence rather than ceremony. Eight mutations, each paired with the green half
that gives it meaning: the revision-loop mutation reds at index 8 while every single-pass
gate stays green, demonstrating exactly what a one-pass fixture cannot see. The two Phase 19
tests the design promised not to disturb ended **byte-identical**, proven by extracting their
source from the merge base rather than by reading hunk headers.

A visitor now sees `searching the web` at the routing hop (~+2s) instead of at the
researcher's completion (+122s, measured). The 120 seconds do not shrink — that work is
honest — but the label shown during them stops being false. Found by the owner, not by any
gate: the suite proved the stream's contract and never asked whether a human would wait.

### Phase 22: Limitations recorded
**Goal**: Every surviving README limitation points at a record, and the Limitations section
says plainly that what remains is chosen, not owed
**Depends on**: Phases 18–21 and 21.5 (every closable limitation — judge independence,
credential validity, the note count bound, the record run, and the classifier fix — must
close before the section can be rewritten around what's left; 21.5's re-record checkpoint
also decides the final recorded/refused split this phase's prose cites)
**Requirements**: REQ-limitations-recorded
**Success Criteria** (what must be TRUE):
  1. A new ADR states the cost-approximation-by-design position and records why invoice
     reconciliation via Anthropic's Admin cost API was rejected.
  2. The mintable-identities limitation points at ADR-0007 instead of standing bare.
  3. The free-tier-database limitation points at a database posture note in OPERATIONS.md.
  4. The four closed bullets (judge independence, credential validity, the note count bound,
     forty recorded answers) are deleted from the README, per the standing convention —
     never rewritten into release notes.
  5. The Limitations section's intro states that what remains is chosen, recorded, and
     argued for.
**Plans**: 2 plans

Plans:
- [x] 22-01-PLAN.md — the post-21.5 baseline re-measured before any edit; ADR-**0014** (cost approximation by design, the four measured Admin-API rejection reasons) plus its index row; the OPERATIONS free-tier posture note; the eval-section defect record re-derived with a derived-counts gate in the ADR-index-test pattern (wave 1)
- [x] 22-02-PLAN.md — the Limitations rewrite: four deletions verified on the git axis, three survivors linked to their records, the honest-ledger intro ending "chosen, recorded, and argued for"; the no-orphan sweep with path-listed exemptions; the whole-README pass; the milestone close-out flips (REQUIREMENTS/ROADMAP/STATE/PROJECT, both Phase-20 deferred items) and 22-VALIDATION reconciliation (wave 2)

**Planning note (2026-08-16):** planned before Phase 21.5 executed, deliberately — every
count in these plans is a placeholder the execution re-measures; 22-01 Task 1 is that
re-measurement and carries a precondition halting if 21.5's artifacts are absent. Wave 2
depends on wave 1 for the records its links target (ADR-0013's filename, the OPERATIONS
anchor) and the measured baseline its prose cites.

**Executed 2026-08-16.** The close-out, in two waves, zero spend — every command ran with
`ANTHROPIC_API_KEY="" VOYAGE_API_KEY=""` prefixed. **Wave 1** wrote the records the
survivors point at: **ADR-0014** (*not* 0013 — 21.5 took that number between planning and
execution, so the plan's renumber contingency became the live path and the slug-anchored
gates needed no edit), its index row with every counting sentence re-derived, the
OPERATIONS `### The free-tier posture, and the upgrade path` note, and the eval section's
three-way refusal decomposition **7 grader / 2 judge_truncated / 6 recorded_then_failed_replay**
behind a new derived-counts test — which caught an unquantified claim on its first run
(the prose said "Most refusals are the machinery working" with no number, so the largest
kind had never been stated anywhere in the milestone). **Wave 2** rewrote Limitations:
**seven bullets → three**, the four closed ones DELETED and verified on the git axis (each
distinctive phrase enters README once and leaves once, at `219e9e3`; no file outside
`.planning/` planning records has ever carried them), the no-orphan sweep over `docs/` +
`.planning/codebase/` returning **zero hits so the exemption list is empty**, every
survivor link resolving including the OPERATIONS anchor re-derived from its heading text,
and an intro that states which things were **closed**, which are **recorded by design**,
and which the paid run **discovered** — ending on "chosen, recorded, and argued for".
The whole-README pass re-derived three stale counts the rewrite exposed (827→828 at two
sites, "twelve now"→"fourteen now" ADRs). Final gates: **828 passed / 72 skipped** keyless
(900 collected), offline evals **PASS 65/65 with a real `$?` of 0**, `ruff check .` clean.
**Four named mutations observed red and reverted** across the wave, two of them proving the
deletion gate and the orphan sweep are genuinely different gates. **No milestone archival
was performed — that is `/gsd:complete-milestone`'s step, deliberately not this phase's.**

## Progress

**v1.1 shipped 2026-08-11.** Per-phase execution records are archived in
[milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md); the phase-by-phase evidence lives in
`.planning/milestones/v1.1-phases/*/`, where every VALIDATION contract now reads `status: complete` and
`nyquist_compliant: true`.

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 Production pipeline | 1–9 (+9.1) | — | Complete | pre-GSD; remastered 2026-08-12 |
| v1.1 Closing the limitations list | 10–17 (+10.5) | 43/43 | **Complete** | 2026-08-11, Fly v12 |
| _(no milestone)_ | 17.5 | 1/1 | **Complete, deployed** | landed and shipped 2026-08-12, Fly v13 |
| v1.2 Nothing uncovered | 18–22 (+21.5) | 16/16 | **All phases executed** 2026-08-16 | not yet shipped — verification, then `/gsd:complete-milestone` |

**Next:** phase verification for Phase 22, then `/gsd:complete-milestone` for v1.2.
Still open across the milestone, carried rather than dropped: 19-VALIDATION's **two
Manual-Only rows** (browser CSP enforcement on the live page, and a real provider
round-trip through `/health`) both need the manual deploy, and `REQ-health-credential-validity`
and `REQ-demo-csp-header` stay unchecked until it happens.

## Reversal register — spent at v1.1 close, reopened once by v1.2

Six requirements reversed a stated design position during v1.1. All six landed, each
superseding a record rather than contradicting prose, and the register closed as **spent**:
`docs/adr/README.md`'s "remaining expected supersessions" described an empty set. The full
v1.1 table is archived in [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

| Phase | Reversed | Recorded as |
|-------|----------|-------------|
| 11 | Sizing judgement in `db.py` | in-phase |
| 12 | Guardrails-not-identity | **ADR-0007** supersedes 0006 |
| 13 | DEC-10 (copy, don't re-embed) | **ADR-0008** |
| 15 | DEC-20 (offline evals grade the pipeline only) | **ADR-0009** |
| 16 | DEC-22's premise | **ADR-0010** supersedes 0005 |
| 17 | DEC-04 | **ADR-0011** supersedes 0003 |

**v1.2 reopens this register once, deliberately:** Phase 18 moves the eval judge off the
critic's model, which supersedes ADR-0010 with a new record, **ADR-0012** — recorded as an
intentional reopening, not drift.
