# Phase 22: Limitations recorded - Research

**Researched:** 2026-08-16
**Domain:** Documentation/ADR close-out — no code, no pipeline, no grader changes. The
domain is "prove a claim about prose against the tree," not a framework or library.
**Confidence:** MEDIUM — every in-repo claim below is `[VERIFIED]` against a file this
session read; the one external fact (Anthropic's Admin cost API) is `[CITED]` against
official docs but scored LOW by the confidence seam (see Metadata). The biggest open
risk is not technical: it is that every count this document reports (19 recorded / 21
refused / 806 tests) is a snapshot **one phase before this one executes**, and Phase
21.5 will move some of them before Phase 22 runs. The plan must be written so its tasks
re-derive numbers, not copy the ones below.

## Summary

Phase 22 rewrites seven README bullets into three, and every one of the three gets a
different kind of record. Four bullets close by deletion (verified byte-identical since
the phases that falsified them, per the git-axis convention `20-VERIFICATION.md`
establishes and this research re-confirms). Three bullets survive, and two of the three
already point at their record or nearly do: the mintable-identities bullet (`README.md:298`)
**already links ADR-0007** — has since Phase 12, commit `ab54fb5` — so criterion 2 of the
five roadmap criteria is close to done today; the plan's job there is verification and
possibly wording, not authorship. The free-tier-database bullet (`:300`) asserts three
facts — Nano tier, `ap-southeast-2`, no read replica, a 60-connection ceiling of which
the fleet holds ten — of which only the connection-ceiling numbers currently exist in
`docs/OPERATIONS.md` (`:292-296`); "no read replica" and the single-region framing as a
**deliberate, argued** posture do not exist anywhere in OPERATIONS today and must be
written, not linked. The cost-approximation bullet (`:297`) needs an entirely new ADR
(next number verified as `0013`), and its strongest material — the reason invoice
reconciliation was rejected — is not primarily a claim about this codebase; it is a claim
about Anthropic's Admin/Usage-and-Cost API, which this research fetched from official docs
and found genuinely dispositive: it is org-scoped, admin-keyed, aggregate (workspace/day,
not per-run), and lagged (~5 minutes, "may occasionally be longer") — four independent,
verifiable reasons to reject it, not one hand-wavy one.

Two things discovered by Phase 21's paid run do not fit the "chosen limitation" shape at
all and should not go in the Limitations section as written: the judge's `max_tokens=1500`
truncation and the six record/replay grading disagreements are **defects**, not design
positions, and the section's own new intro (criterion 5) commits to calling what remains
"chosen, recorded, and argued for" — a defect is none of those three. Both are already
substantively recorded today, just not in one durable place: the code predicted the
truncation in its own docstring (`evals/graders.py:758`), the evidence lives in
`evals/REFUSALS.json`, and README's eval-section prose (`:230-233`) already narrates both
in one paragraph. The gap is that the prose paragraph's numbers are today's and will be
stale the moment 21.5 re-records; the fix is to keep the defects where they already live
(README eval-section prose + REFUSALS.json evidence) and make the prose derive its numbers
from the tree instead of stating them as literals — following the exact pattern
`tests/test_evals.py::test_the_adr_index_counting_prose_is_derived_from_the_table`
already established for the ADR index's "eight of the twelve" sentence.

**Primary recommendation:** Treat this phase as three independent tracks that share only
the README diff — (1) delete four bullets and grep-prove they're gone from every doc
surface, not just README; (2) write ADR-0013 (cost-approximation-by-design) and a new
OPERATIONS.md subsection (database posture) and re-point two README bullets at them;
(3) leave the two paid-run defects where Phase 21 already put them, and add one
derived-counts test so the prose that cites their numbers cannot go stale silently the
way the ADR index's used to. Do not invent a fourth record type (no `KNOWN-DEFECTS.md`) —
the codebase already has a precedent for "found something broken, decided not to fix it
yet, wrote down why" prose (`OPERATIONS.md`'s "Do not fix the five `rls_enabled_no_policy`
notices" section), and it is a doc-prose pattern, not a new architectural-decision type.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. A new ADR states the **cost-approximation-by-design** position and why invoice
   reconciliation via Anthropic's Admin cost API was rejected.
2. The **mintable-identities** limitation points at ADR-0007 instead of standing bare.
3. The **free-tier-database** limitation points at a database posture note in
   OPERATIONS.md.
4. The closed bullets are **deleted** — judge independence (`:295`), credential validity
   (`:299`), the note count bound (`:301`), and the recorded-answers bullet (`:296`), which
   Phase 21 falsified in an amended form. Deletion, never a rewrite into release notes.
5. The section intro states that what remains is **chosen, recorded, and argued for**.

What v1.2's own execution added mid-milestone (binding, not merely informative):
- The recorded-answers bullet's replacement must tell the amended truth: recorded +
  documented-refusal counts as of execution, the union enforced by test, refusals in
  `evals/REFUSALS.json`. Whether the final state warrants a *surviving* residue bullet or
  only honest eval-section prose is the planner's call — but the residue must be recorded
  somewhere that outlives this phase either way.
- Two defects discovered by the paid run are recorded as **known defects**, distinct from
  chosen limitations: judge verdict truncation at `max_tokens=1500` (`graders.py:758`
  predicted it), and record-time vs. replay-time grading disagreement (six fixtures).
  Where they live is the researcher/planner's call; that they are written down with their
  evidence is not negotiable.
- The milestone's acceptance bar is met honestly, not numerically: state which things
  were *closed*, which were *recorded by design*, and which were *discovered* — never
  claim nothing new exists.

Standing rules:
- README updated in the phase's PR (standing rule) — this IS the README phase.
- All counts (tests, evals denominator, fixtures/refusals split) re-measured at
  execution; STATE/ROADMAP/REQUIREMENTS close-out flips happen here, since this is the
  milestone's last phase.
- ADR numbering continues from the highest existing (verify — believed 0012).

### Claude's Discretion

- Whether the surviving-limitations list gets per-bullet "why this is chosen" prose
  inline or via links only (match the section's existing voice).
- Whether the two defects share one record or get one each.
- Whether `evals/REFUSALS.json` deserves a README pointer beyond the eval section's
  existing one.

### Deferred Ideas (OUT OF SCOPE)

- Fixing the judge truncation (raise/split the token budget) — successor milestone;
  ADR-0012's fence stands until then.
- Re-authoring contested pins to survive re-records — successor milestone, and only
  with a design that keeps them binding on both reference reports and recordings.
- Any further recording spend beyond 21.5's checkpoint.

**Sequencing constraint that shapes everything below:** this phase is being *planned*
now, before Phase 21.5 has executed, but it *executes* after 21.5. Every number in this
research is a 2026-08-16 snapshot the plan must not hardcode — see Open Question 1 and
the Validation Architecture section's "measured-counts gates."
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-limitations-recorded | Every surviving README limitation points at a record: a new ADR states cost-approximation-by-design (and why invoice reconciliation was rejected), mintable identities already carry ADR-0007, and the database posture moves to OPERATIONS with one honest README line. The four closed bullets are deleted per the standing convention (never rewritten into release notes), and the section intro is rewritten: what remains is chosen, recorded, and argued for. | Full README inventory (verbatim text + line numbers) below; ADR-0013 raw material and rejection reasons for the Admin cost API; the exact facts OPERATIONS.md is missing for the database posture note; deletion/no-orphan/link verification gates in Validation Architecture. |
</phase_requirements>

## Architectural Responsibility Map

This phase touches no runtime tier — it is 100% documentation and one repo-root file
(`README.md`) plus one `docs/` file plus one new `docs/adr/` file. The map below exists
to make that explicit, since the phase's own scope note says "no grader, judge, dataset,
or pipeline changes" and this table is the verification that nothing in the plan should
cross into a code tier.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Limitations section rewrite | Documentation (`README.md`) | — | Pure prose; no code path reads this file |
| Cost-approximation ADR | Documentation (`docs/adr/`) | — | Nygard-form record; supersedes nothing, adds a table row |
| Database posture note | Documentation (`docs/OPERATIONS.md`) | — | Consolidates facts already scattered across two existing OPERATIONS sections plus one new fact (no read replica) |
| Defect record (judge truncation, record/replay divergence) | Documentation (`README.md` eval-section prose) | Evidence: `evals/REFUSALS.json` (already committed, Phase 21) | The defects live where Phase 21 already wrote them; this phase only removes staleness risk from the prose, per Assumption A1 below |
| Requirements/roadmap/state close-out | `.planning/` (project meta, not app code) | — | Standard end-of-milestone bookkeeping, same shape as Phases 18–20's closes |
| **Explicitly NOT touched** | `evals/graders.py`, `evals/harness.py`, `evals/dataset.py`, any grader, any judge, any pipeline node | — | House constraint: ADR-0012's fence stands; this phase records defects, does not fix them |

## Standard Stack

Not applicable — this phase installs no packages and touches no runtime dependency.
`docs/adr/README.md`'s own Nygard-form convention is the only "stack" in play, and it is
already established (0001–0012 on disk, house style verified below). No `npm install` /
`pip install` line applies to this phase.

## Package Legitimacy Audit

Not applicable — no packages are introduced by this phase. Skipped per the gate's own
scope ("required whenever this phase installs external packages").

## Architecture Patterns

### 1. The README Limitations section, inventoried exactly

`[VERIFIED: README.md:287-301]` — read this session, both at the start and re-grepped
independently afterward to confirm byte-identity across the two reads (the project's own
"byte-identical, verified on the git axis" convention, matched here by a second read
rather than a `git diff`, since no commit separates the two reads).

Intro (`:289-293`):
> "Known, and deliberate for the scope. **The v1.0 README listed nine limitations,
> and v1.1 has now closed all nine** — the last of them in phase 17, where
> follow-ups stopped being unable to reach for new information. Several were
> closed by narrowing rather than erasing, so their narrower successors are still
> here; everything below is one of those or a limit the v1.1 work created."

The seven bullets, verbatim first sentences and disposition:

| Line | First sentence (verbatim) | Disposition | Closed by |
|------|---------------------------|--------------|-----------|
| `:295` | "The eval judge shares the critic's model." | **DELETE** | Phase 18 (`ADR-0012`) |
| `:296` | "Only one of forty answers is recorded." | **DELETE** (replace with amended-truth prose, per CONTEXT's addendum) | Phase 21, amended criterion |
| `:297` | "Reported cost is an approximation, never the invoice." | **SURVIVES** → new ADR-0013 | — |
| `:298` | "Identities are free to mint." | **SURVIVES** → already links `ADR-0007` | — |
| `:299` | "`/health` checks that the API keys are *present*, not that they work." | **DELETE** | Phase 19 |
| `:300` | "The database is a single region on a free tier." | **SURVIVES** → OPERATIONS posture note | — |
| `:301` | "Notes are bounded by expiry alone." | **DELETE** | Phase 20 |

This matches the roadmap's "four closed, three keepers" arithmetic exactly (`ROADMAP.md`
Phase 22 success criterion 4 names judge independence, credential validity, the note
count bound, and forty recorded answers as the four).

**Bullet `:299` is a live falsification worth confirming precisely, because the deletion
gate depends on it.** `[VERIFIED: src/research_agent/service.py:869-925]` (read this
session) — the `/health` handler reads `credentials[f"{name}_valid"]`,
`credentials[f"{name}_checked_at"]`, `credentials[f"{name}_error"]` for both `anthropic`
and `voyage`, backed by `_credential_status()` and a cached async probe. The bullet's
claim ("checks that the API keys are present, not that they work") is false today — it
describes the pre-Phase-19 handler. `[VERIFIED: docs/OPERATIONS.md:25-30]` confirms the
same in prose: *"`/health` reports two separate facts about each key and never the value
itself: whether it is present, and whether it actually works (`anthropic_valid` and
`voyage_valid`, with a `_checked_at` and a `_error` beside each)."* Delete confidently.

**Bullet `:298` already links ADR-0007 — criterion 2 may already be substantively met.**
`[VERIFIED: git log -p --follow -- README.md]`, read this session: the line *"Recorded as
[ADR-0007](docs/adr/0007-anonymous-identity-fairness-global-cap.md)"* has been present
since commit `ab54fb5` ("docs(12-06): ADR-0007 supersedes ADR-0006 with explicit
carry-forward"), i.e. since Phase 12, well before this milestone opened. The plan should
treat criterion 2 as **verify, not author** — confirm the link still resolves (the ADR
file exists, `[VERIFIED: docs/adr/0007-anonymous-identity-fairness-global-cap.md]`, read
in full this session, 155 lines, Nygard-form, `Status: Accepted — supersedes ADR-0006`)
and leave the bullet's prose as-is unless the section's voice pass changes wording for
consistency with the two newly-rewritten bullets beside it.

### 2. The cost-approximation ADR's raw material

**What the codebase already claims (survives into the new ADR's Context section).**
`[VERIFIED: README.md:297]`, verbatim: *"Nothing here reads a bill. Provider token counts
are telemetry — measured live, Voyage reported 25 tokens where the tokenizer counted 40,
and 0 for a one-word document that embedded fine."* `[VERIFIED: docs/OPERATIONS.md:532-538]`
carries the same measurement with a date: *"Measured 2026-08-09: a 12-note corpus the
local tokenizer counted at **40** tokens came back from the API reported as **25**, and a
single one-word document came back as **0**... Read the predicted figure as an honest
upper bound, the reported figure as what the response said, and **Voyage's usage
dashboard as the only authority on what you were billed**."`

`[VERIFIED: src/research_agent/usage.py:490-503]` (read this session, `record_embedding`
docstring) states the same epistemic position for a second, independent code path:
*"Zero tokens is not an error. Voyage's reported count is telemetry, not billing truth...
That records as $0.00 through the normal priced path."* And separately: *"No multipliers.
`COST_DISCOUNT_FACTOR` and the `inference_geo` rate are Anthropic dimensions — a
negotiated Anthropic discount and a Claude data-residency surcharge. Voyage is a
different vendor on a different rate card, and applying either here would invent a
discount nobody negotiated."* This is strong, already-written material: the ADR's
Context section can lean on it almost verbatim rather than re-deriving the argument.

**What is new: why the Admin cost API specifically was rejected.** `[CITED:
platform.claude.com/docs/en/manage-claude/usage-cost-api]` — fetched this session via
WebFetch. Four independently verifiable, dispositive facts:

1. **Admin-key-scoped, organization-wide.** *"These endpoints require an Admin API key,
   which is different from a standard Claude API key... Admin API keys are owned by the
   organization and remain active even after the creator is removed."* This is a
   materially bigger secret than the two the service already manages
   (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`) — it can read across every workspace and every
   API key in the org, not just this service's usage, and `docs/OPERATIONS.md:23-24`'s
   existing posture (*"Credentials never reach an image layer"*) would need a new,
   higher-blast-radius secret to wire.
2. **Aggregate, not per-run.** The Cost endpoint (`/v1/organizations/cost_report`)
   supports *"Time buckets: Daily granularity only (`1d`)"* and groups only by
   `workspace_id` or `description` — there is no per-request or per-session-id dimension.
   This service's cost claim is per-run (`cost_usd` in the SSE payload, per
   `README.md:118`); the Admin API cannot answer "what did *this* run cost," only "what
   did the whole workspace cost yesterday." Reconciling would require inferring a
   per-run split from a daily aggregate, which is a new estimation problem, not a
   solution to the one being reconciled.
3. **Lagged.** *"Usage and cost data typically appears within 5 minutes of API request
   completion, though delays may occasionally be longer."* Not real-time and not
   guaranteed-bounded — a genuine gap against a service whose cost figures are surfaced
   synchronously in the same response as the answer (`/pricing`, `/metrics`).
4. **New infrastructure for a demo-scale service.** Reconciliation would need a
   scheduled job, a place to store the daily aggregate, and correlation logic against
   this service's own per-run ledger (`runs` table) — real engineering for a service
   whose own `README.md:298` already states the honest backstop is a client-side
   estimate read against `/pricing`, not an invoice.

This is materially better ADR content than a hand-wave: each of the four reasons is a
verifiable API property, not an opinion, and the ADR can cite the endpoint's own
documented shape rather than asserting "reconciliation is hard."

**Next ADR number.** `[VERIFIED: docs/adr/]` (`ls` run this session) — twelve files,
`0001` through `0012`, plus `README.md`. `0013` is free. `[VERIFIED: docs/adr/README.md:
"Eight of the twelve records are `Accepted` today... Four supersessions have actually
happened"]` confirms the index's own count matches the twelve files on disk.

**House ADR format**, read from `docs/adr/README.md` (Record shape section) and
cross-checked against `docs/adr/0012-judge-independent-of-the-critic.md` (read in full
this session) and `docs/adr/0007-anonymous-identity-fairness-global-cap.md` (read in
full this session):

- Title line: `# ADR-000N — <Title>`
- `**Status:**` line — for a new, non-superseding record: `Accepted`
- Provenance line: `**Source:**` (not `**Promoted from:**`, since this record has no
  `docs/DESIGN.md` passage behind it — no existing DESIGN.md prose currently argues the
  cost-approximation position at ADR length; `docs/DESIGN.md`'s Cost section, read in
  full this session, covers the spend cap, effective-dating, and unpriced-model handling,
  but never makes the "reported cost is an estimate, not the invoice" argument by name).
  Follow the ADR-0006-onward pattern: `**Source:** Phase 22 (2026-08-1X),
  REQ-limitations-recorded`.
- `## Context`, `## Decision`, `## Consequences` — in that order, `##` headings, the
  three-heading contract.
- `## Consequences` may split into `### Accepted` / `### Rejected alternative` — ADR-0012
  does this; ADR-0007 does this. Recommend the same shape here: `### Rejected
  alternatives` is exactly where the Admin cost API's four reasons belong, framed as "why
  this specific alternative was rejected" rather than folded into Context.
- **After writing ADR-0013, `docs/adr/README.md`'s Index table and its counting prose
  both need a new row and a re-derived count** — see Validation Architecture's "ADR index
  gate" for the exact mechanics; this is enforced by an existing test
  (`tests/test_evals.py::test_the_adr_index_counting_prose_is_derived_from_the_table`)
  that will fail if the prose isn't updated, and it is self-adjusting (does not need a
  new test written for it — the existing one already re-derives from the table).

### 3. The OPERATIONS.md database-posture note

**What OPERATIONS already has, and where.** `[VERIFIED: docs/OPERATIONS.md:148-161]`
("Why Supabase and not Neon") states the region and tier as an aside inside a *different*
argument (why Supabase over Neon, not "here is our accepted risk posture"): the
Oceania/Sydney region choice is stated at `:176-178` under "The cutover, in order," not
in the Neon-comparison section. `[VERIFIED: docs/OPERATIONS.md:292-296]` ("Supabase
specifics" → "Connection budget") states the exact numbers the README bullet cites:
*"`hard_limit = 16` × 2 machines = up to 32 in-flight requests against one database, but
the app pool caps connections at `PG_POOL_MAX_SIZE` (5), so the fleet holds at most 10 of
Supabase Nano's 60."* This confirms the README bullet's "60-connection ceiling of which
the fleet holds ten" is accurate and sourced.

**What is missing.** `[VERIFIED: grep -n -i "replica\|nano\|single region\|free tier"
docs/OPERATIONS.md README.md docs/DESIGN.md]`, run this session — the phrase "read
replica" appears **nowhere in `docs/OPERATIONS.md`**, only in `README.md:300`. There is
no OPERATIONS sentence today that frames the single-region, no-replica, free-tier choice
as a **deliberate, argued posture** with an upgrade path — the closest existing material
(the Neon-comparison section) argues why Supabase specifically over Neon, not why staying
on the free tier at all is acceptable. The posture note is therefore new prose, not a
pointer to something that already says this.

**What it should carry**, gathered from facts already verified elsewhere in OPERATIONS
this session: region `ap-southeast-2` (`:176-178`, "next to Fly's `syd`, because every
store probe pays that hop... cannot be changed after creation"), Supabase Nano tier and
its free-tier absence of a compute meter (`:158-161`), the connection ceiling and
fleet-held numbers above, and — new — an explicit statement that no read replica exists
and why that is acceptable at current traffic (this last part is not sourced anywhere in
the tree; it is the one genuinely new factual claim the plan must write and should
justify with the same reasoning style OPERATIONS already uses elsewhere, e.g. the
measured round-trip numbers at `:203-208` — "Fine at this traffic; the first thing to
look at if it isn't," which is literally the README bullet's own closing sentence and
can migrate into OPERATIONS nearly verbatim).

**Where it belongs structurally.** The "Going stateless" section (`## Going stateless`,
`docs/OPERATIONS.md:137`) is the natural home — it already contains "Why Supabase and not
Neon" as a subsection making a closely related argument. Recommend a new `###` subsection
there (e.g. "Free-tier posture, and the upgrade path") rather than folding it into
"Supabase specifics," which is written as a reference/runbook section (connection
strings, `sslmode`, RLS grants), not an argued-position section. The README bullet then
becomes a one-line pointer, matching the mintable-identities bullet's existing shape
(one sentence + a link), per the phase's own criterion 3 wording ("one honest README
line").

### 4. The two paid-run defects — where they live, argued

**The judge truncation.** `[VERIFIED: evals/graders.py:744-795]`, read in full this
session. The `Judge.verdict()` docstring names the defect before the run that found it
existed: *"**Truncated** (`stop_reason=\"max_tokens\"`) -- the 1500-token budget is
shared with adaptive thinking, so a long deliberation can cut the JSON off mid-object.
Raises, but says TRUNCATED rather than letting an operational failure masquerade as a
malformed verdict."* — `graders.py:758-761`. The actual call site, `graders.py:773-782`,
confirms `max_tokens=1500` and `thinking={"type": "adaptive"}` are the same call, so the
docstring's "shared with adaptive thinking" claim is not speculative, it is the literal
code shape. `[VERIFIED: evals/REFUSALS.json]`, read in full this session — two entries
carry `"kind": "judge_truncated"`: `chatty-label-falls-back` (batch A, `cost_usd: 0`) and
`followup-refuses-an-uncovered-figure` (batch D, `cost_usd: 0.106609`), both with
`"detail": "judge verdict truncated at max_tokens=1500 (shared with adaptive thinking)"`.

**The record/replay divergence.** `[VERIFIED: evals/REFUSALS.json]` — six entries carry
`"kind": "recorded_then_failed_replay"`: five contested-topic cases
(`contested-monorepo-vs-polyrepo`, `contested-open-weight-models`,
`contested-rag-versus-finetuning`, `contested-service-boundaries`,
`contested-static-typing-payoff`) sharing one detail string, and one distinct case
(`followup-refuses-a-forecast`) with its own detail. The five share:
*"recorded and approved at record time, but fails replay on case_pins (must_mention
'proponents','critics'). The recording argues both sides at length in different words.
The pins cannot simply be re-authored: the same must_mention must also be satisfied by
the case's hand-authored reference report in dataset.py, which is written in
proponents/critics vocabulary, so any replacement collapses to a lowest-common-denominator
word that tests less than the pin it replaced. Left for a successor phase to resolve
properly."* `[VERIFIED: evals/harness.py:445-491]` (`replay_case`, read this session)
confirms the mechanism this describes: replay grades against `case_pins` plus recorded
judge verdicts, and `grade_fixture_current` (`harness.py:353-424`) never compares the
judge role — only pipeline and critic models — so this divergence is genuinely a pin/data
issue, not a staleness-gate false positive.

**Recommendation: do not create a new record type.** Considered and rejected:

- **New Limitations bullets** — rejected. The section's own new intro (criterion 5)
  commits to "chosen, recorded, and argued for." A defect discovered by a paid run is
  none of the three; it would directly contradict the intro it sits under.
- **A new ADR** — rejected. `docs/adr/README.md`'s Record shape requires a `## Decision`
  section; there is no decision being made here (the deferred-items list explicitly rules
  out fixing the defect this phase, per ADR-0012's fence and the CONTEXT.md Deferred
  Ideas section), only a finding being reported. Forcing a Nygard-shaped record around a
  bug report would misuse the format the project has been careful to keep load-bearing.
- **A new `KNOWN-DEFECTS.md`** — rejected as unnecessary. It would be a fourth doc
  surface in a project that already has three (`README.md`, `docs/DESIGN.md`,
  `docs/OPERATIONS.md`) each with a clear, distinct job, and a new file needs its own
  discoverability story this phase has no budget to build.
- **Leave them exactly where Phase 21 already put them** — recommended. `[VERIFIED:
  README.md:230-233]`, read this session, already narrates both defects in the eval
  section: *"Most refusals are the machinery working; two are a real defect (the judge's
  verdict truncating against a token budget it shares with adaptive thinking) and six are
  recordings that passed at record time and then failed replay, which is its own finding
  about the two grading paths disagreeing."* This is materially the same content this
  research assembled above, already committed. The evidence store (`evals/REFUSALS.json`)
  is already committed and already carries the per-case `kind`/`detail`/`cost_usd`
  fields. `docs/OPERATIONS.md` has a strong stylistic precedent for exactly this shape of
  "found, not fixed, written down" prose: `:407-425`'s *"Do not \"fix\" the five
  `rls_enabled_no_policy` notices"* section is a finding, explicitly left unfixed, with
  reasoning, in the same document style. **What is missing is not a new home — it is that
  the eval-section prose's numbers ("two," "six," "Nineteen... twenty-one") are literals
  that will go stale the moment 21.5 re-records, exactly the failure mode
  `test_the_adr_index_counting_prose_is_derived_from_the_table`'s own docstring names:
  "A gate that greps for the string you just typed is not a gate."** The concrete
  recommendation is in Validation Architecture below: add one derived-counts test mirroring
  that existing one, so the prose is checked against `evals/fixtures/` and
  `evals/REFUSALS.json` rather than trusted.

### 5. Refusal-residue placeholder discipline

`[VERIFIED: evals/fixtures/]` (`ls | wc -l`, run this session) — 19 files, matching
README's current "Nineteen cases of forty are recorded." `[VERIFIED: evals/REFUSALS.json]`
— 21 keys under `"refusals"`. `[VERIFIED: python -m evals --quiet, run this session]` —
`PASS 59/59 cases (100% vs 90% required)`, `$2.3440 · 0.1s`, denominator 59 (40 behavioural
+ 19 replayed), matching `ROADMAP.md`'s Phase 21 close note.

Phase 21.5's roadmap entry (`[VERIFIED: ROADMAP.md:381-384]`) commits to re-attempting
"the six `topic_type`-refused recordings." This research checked whether that "six" maps
cleanly onto a `grep`-able subset of today's `REFUSALS.json` and it does **not**
trivially: entries whose `"detail"` field is the single literal string `"topic_type"`
number five (`general-defines-a-term`, `general-explains-a-concept`,
`general-how-a-mechanism-works`, `general-summary`, `injection-tries-to-force-approval`),
while entries where `"topic_type"` appears as *part of* a multi-cause detail (e.g.
`"topic_type, approval, forced_stop"`) add three more. Which exact set Phase 21.5
resolves as "the six" is that phase's business, not this one's, but the mismatch is worth
recording precisely because it demonstrates why the house rule ("counts re-measured at
execution, never carried") is not boilerplate here — even a plausible-looking `grep -c
topic_type REFUSALS.json` would not reproduce the roadmap's own "six."

**What Phase 22's plan must therefore do:**
- Never hardcode 19/21/59/806/878 (or any count in this document) into a task's expected
  output or into README prose the plan authors directly. Every number the rewritten
  README states must be produced by a command run at execution time
  (`ls evals/fixtures/*.json | wc -l`, a `json.load` count over `REFUSALS.json`, a bare
  `python -m evals --quiet` invocation, `pytest` exit summary).
- Structure the recorded-answers bullet's replacement and the eval-section prose as
  **templates with placeholders the executor fills from a measured command**, not as
  prose drafted now and pasted in later.
- Decide (Claude's Discretion, per CONTEXT.md) whether the residue — whatever it
  measures to after 21.5 — earns a *surviving* Limitations bullet or lives only in the
  eval-section prose. This research's inventory above (Pattern 1's table) assumed no new
  bullet is added for the residue, consistent with `REQUIREMENTS.md`'s explicit
  "no new bullet is born" acceptance bar for every closure — the residue is not a
  closure, but the same spirit argues against inventing a bullet for something that was
  never claimed to be an unbounded gap, just an honestly-reported partial result.

**Does any sentence Phase 21 wrote need updating when the split moves?** `[VERIFIED:
README.md:196-243]`, the full "Tests and evals" section, read this session. Three
sentences carry today's numbers and will need re-deriving, not just the Limitations
section: `:220-221` ("**Nineteen cases of forty are recorded**... so a run now grades 59
cases"), `:225` ("The other twenty-one are in `evals/REFUSALS.json`"), and `:230-233`
(the "two... six" defect-count sentence quoted above). All three sit in prose Phase 21
already rewrote and are therefore this phase's to re-derive, not author from scratch.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Proving a prose claim didn't silently drift from the table backing it | A hand-checked "make sure the numbers still match" note in a SUMMARY | A derived-counts pytest test in the shape of `test_the_adr_index_counting_prose_is_derived_from_the_table` | The project has already paid for this exact lesson once (`17-04`'s "a gate that greps for the string you just typed is not a gate"); reusing the pattern is cheaper than re-learning it |
| A new "we found a bug and didn't fix it" doc convention | A new `docs/KNOWN-DEFECTS.md` file with its own format | `docs/OPERATIONS.md`'s existing "Do not fix the five `rls_enabled_no_policy` notices" prose shape | The convention already exists in the tree, in the same voice, for the same kind of finding |
| Deciding whether a claim is truly gone from the tree | Trusting the README diff alone | `grep`/`git grep` across `README.md`, `docs/DESIGN.md`, `docs/OPERATIONS.md`, `docs/adr/*.md`, and `.planning/codebase/*.md` for a deleted bullet's distinctive phrase | A deleted README bullet whose exact claim survives in DESIGN.md or an ADR is the phase's stated failure mode (see CONTEXT.md canonical refs and this document's Validation Architecture "no-orphan gate") |

**Key insight:** every "don't hand-roll" here is really the same insight once: this
project has a working, tested pattern (`test_the_adr_index_counting_prose_is_derived_from_the_table`)
for exactly the failure this phase is most exposed to (prose that quotes a number and
drifts from its source), and the plan should extend that pattern rather than invent a
parallel one.

## Common Pitfalls

### Pitfall 1: Deleting the bullet but leaving the claim
**What goes wrong:** The README bullet disappears, but the same false-and-now-corrected
claim (e.g. "checks presence, not validity") survives in `docs/DESIGN.md`, an ADR's
Consequences section, or a stale `.planning/codebase/` map, so a reader who lands on that
surface first is still misled.
**Why it happens:** The phase's own scope is framed around the README diff; nothing
forces a cross-repo grep unless the plan explicitly schedules one.
**How to avoid:** Run a no-orphan grep per deleted bullet before calling the deletion
done — this research's Validation Architecture section below gives the exact patterns.
**Warning signs:** A grep for the deleted bullet's distinctive noun phrase (e.g. "checks
that the API keys are") returns a hit anywhere under `docs/` or `.planning/codebase/`.

### Pitfall 2: The ADR index test catching a forgotten row, but only in CI
**What goes wrong:** ADR-0013 is written and the table row is added, but the counting
prose ("Eight of the twelve records are Accepted") is left unchanged — `nine of the
thirteen` is what the test now demands, and a forgotten edit fails
`test_the_adr_index_counting_prose_is_derived_from_the_table` at the full-suite gate,
which is late to discover a one-line miss.
**Why it happens:** The prose sits above the table it counts, easy to forget when the
edit that matters (the new row) is below it.
**How to avoid:** Add the new ADR row and immediately re-run
`pytest tests/test_evals.py -k adr_index` (or the equivalent `-k` selector) before moving
on, rather than waiting for the full suite.
**Warning signs:** `assert f"{spelled(accepted)} of the {spelled(len(rows))} records" in
prose` failing with a mismatch between the table's derived count and the prose string.

### Pitfall 3: Writing the database posture note as a restatement instead of an argument
**What goes wrong:** The new OPERATIONS subsection lists the same facts the README
bullet already had (region, tier, connection ceiling) without adding the thing criterion
3 actually asks for — an argued, deliberate posture with an upgrade path — so the README
bullet ends up pointing at a paragraph that says nothing the bullet didn't already say,
defeating the purpose of moving it.
**Why it happens:** The facts already exist scattered in OPERATIONS (Pattern 3 above);
it's easy to copy them into one place and call it done.
**How to avoid:** The posture note's job is specifically the "no read replica, and here
is why that's fine at this traffic, and here is the upgrade path" sentence that exists
**nowhere** in the tree today (verified by grep, Pattern 3 above) — that is the new
content this phase must actually write, not the numbers.
**Warning signs:** The new OPERATIONS subsection, if diffed against the deleted README
sentence, adds no information a careful reader didn't already have.

### Pitfall 4: Treating the defects as Limitations-shaped
**What goes wrong:** A well-meaning plan adds "The judge's verdict can truncate" and
"Record-time and replay-time grading can disagree" as two new Limitations bullets,
directly undermining the phase's own intro rewrite ("what remains is chosen, recorded,
and argued for") on the same PR that writes that sentence.
**Why it happens:** "Record the defects" and "the Limitations section is what gets
recorded" are easy to conflate when reading the roadmap quickly.
**How to avoid:** Keep the defects in the eval-section prose (already their home,
Pattern 4 above) and explicitly do not touch the Limitations bullet count for them.
**Warning signs:** The rewritten Limitations section has more than three bullets, or a
bullet's first sentence uses a defect-shaped verb ("truncates," "disagree") rather than a
decision-shaped one ("is," "means").

## Code Examples

### The deletion + no-orphan grep pattern (mutate-and-observe, matching `20-VERIFICATION.md`'s style)

```bash
# Before deleting a bullet, confirm it's still there exactly once (the git-axis baseline):
grep -c "checks that the API keys are \*present\*" README.md   # expect 1

# After deleting it:
grep -c "checks that the API keys are \*present\*" README.md   # expect 0

# No-orphan sweep — the deleted claim must not survive anywhere else in the doc surfaces
# the phase's canonical refs name (README, docs/adr/, docs/OPERATIONS.md, docs/DESIGN.md,
# .planning/codebase/*.md):
grep -rn "checks that the API keys are" README.md docs/ .planning/codebase/ 2>/dev/null
# expect: no output
```

### The derived-counts test pattern to extend for the eval-section prose

```python
# Source: tests/test_evals.py (existing test, read this session — the pattern to mirror,
# not to copy verbatim; adapt paths/wording to the README eval section rather than the
# ADR index).
def test_the_adr_index_counting_prose_is_derived_from_the_table():
    """A gate that greps for the string you just typed is not a gate (17-04).
    ...numbers are DERIVED from the table's own Status cells and compared
    against the prose. Nothing here hardcodes this phase's counts: add a
    thirteenth record and the checker demands the prose say thirteen."""
    # ... parses docs/adr/README.md's table, derives counts, asserts the
    # spelled-out prose matches.
```

A parallel test for README's eval-section prose would instead: count
`len(list(pathlib.Path("evals/fixtures").glob("*.json")))`, count
`len(json.loads(pathlib.Path("evals/REFUSALS.json").read_text())["refusals"])`, assert
their sum equals `len(GOLDEN)`, and assert the spelled-out numbers in
`README.md`'s eval section match — reusing the `_SPELLED` dict already defined in
`tests/test_evals.py:3153-3157` rather than re-inventing number-spelling.

### The known-defect prose precedent to match in voice

```markdown
<!-- Source: docs/OPERATIONS.md:407-425, read this session — the closest existing
     precedent in this codebase for "found, explicitly not fixed, written down why." -->
### Do not "fix" the five `rls_enabled_no_policy` notices

Advisors now reports five `INFO` findings — one per table — saying RLS is
enabled but no policies exist. **That is this design working, not a defect, and
the linter's suggested remediation would undo the phase that put it there.**
...
The finding is `INFO`, it stays, and it stays for a reason. If a future change
genuinely needs PostgREST access, that is a design decision with its own record,
not a linter notice to clear.
```

The judge-truncation and record/replay-divergence prose in README's eval section should
match this voice — stated plainly, evidence cited, explicitly not fixed here, with the
reason why (ADR-0012's fence; the pins-must-also-satisfy-`dataset.py` constraint).

## Runtime State Inventory

Not applicable. This is not a rename/refactor/migration phase — no identifier, key, or
path is being renamed across surfaces. Deletion of README prose is a content change, not
a runtime-state change; nothing in a database, a live service config, an OS registration,
a secret, or a build artifact carries any of the seven bullet texts being deleted. Stated
explicitly per the trigger's own instruction rather than left blank.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The two paid-run defects should live in README's eval-section prose (expanded with a derived-counts test) plus `evals/REFUSALS.json`, not in a new ADR, a new Limitations bullet, or a new doc file. | Architecture Patterns §4 ("The two paid-run defects") | If the planner or user disagrees, the plan's structure for this piece changes entirely — it's the one genuinely open design call in this research, argued rather than verified, and CONTEXT.md explicitly leaves it as "the researcher/planner's question." Low risk to reverse (it's a location decision, not a technical one) but worth flagging as a recommendation, not a fact. |
| A2 | The "no read replica" fact for the database posture note is true and should be stated as a deliberate, accepted posture rather than a gap. | Architecture Patterns §3 | This is true of Supabase's free tier generically (no read replica option exists below a paid tier) but this research did not independently re-verify it against Supabase's current pricing page this session — it is carried from the existing README bullet's own claim, itself unsourced in the tree. Low risk: if wrong, the posture note overstates a limitation that doesn't exist, which is the safer direction to be wrong in. |
| A3 | Phase 21.5's "six `topic_type`-refused recordings" does not map cleanly onto today's `REFUSALS.json` `"detail"` field via a simple grep (5 single-cause + 3 more multi-cause entries mention `topic_type`, not a clean 6). | Architecture Patterns §5 | If the planner assumes a specific six-case list from today's data, the assumption will be wrong the moment Phase 21.5 defines its own set — this is exactly the placeholder-discipline point being made, so the risk is self-correcting if the recommendation (never hardcode the list) is followed. |

## Open Questions

1. **Will Phase 21.5 change which of the "closed" claims are still true?**
   - What we know: Phase 21.5 (classifier model, re-record checkpoint) does not touch
     any of the four deletion candidates' underlying code (judge model, `/health`
     probes, note count bound, or the fixture/refusal mechanism itself) — it only moves
     some cases from `REFUSALS.json` to `evals/fixtures/`.
   - What's unclear: whether 21.5's re-record run surfaces a *new* finding that changes
     the eval-section prose's shape beyond just the numbers (e.g., a different defect
     category).
   - Recommendation: the plan's Wave 0 (or its first task) should re-read
     `.planning/phases/21.5-*/` artifacts at execution time — CONTEXT.md's own canonical
     refs already say to read that directory "at execution, not now."

2. **Exact wording for the section intro (criterion 5) — inline "why chosen" prose per
   bullet, or link-only?**
   - What we know: CONTEXT.md leaves this as Claude's Discretion, "match the section's
     existing voice."
   - What's unclear: the existing voice is inconsistent across the three surviving
     bullets today — `:298` (identities) already has one full sentence of "why," `:300`
     (database) has one clause ("Fine at this traffic..."), `:297` (cost) has none beyond
     the measured-telemetry examples.
   - Recommendation: since two of the three surviving bullets are being rewritten anyway
     (cost gets a new ADR pointer, database gets a new OPERATIONS pointer), match them to
     the identities bullet's existing shape — one sentence of "why," then the link —
     rather than inventing a new voice.

## State of the Art

Not meaningfully applicable — there is no external framework or library whose "current
approach" vs. "old approach" matters here. The one relevant "state of the art" fact is
Anthropic's own API surface, already covered in Architecture Patterns §2: the Admin
Usage & Cost API exists and is the modern replacement for manual invoice reading, but its
shape (aggregate, admin-scoped, lagged) is exactly why it doesn't fit this service's
per-run cost model — not a case of this project using an outdated approach.

## Environment Availability

Skipped — this phase has no external tool, service, or runtime dependency beyond what
the repository already requires (`pytest`, `ruff`, the existing `.venv`). All commands
used in this research (`pytest`, `python -m evals`, `grep`, `git log`) were run
successfully against the existing `.venv` this session; no new environment probe is
needed.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (per `pyproject.toml`), verified this session by running the suite |
| Config file | `pyproject.toml` (`pythonpath = [".", "src", "tests"]`) |
| Quick run command | `.venv/bin/pytest tests/test_evals.py -k adr` (existing ADR-index test; a new README-derived-counts test should sit near it) |
| Full suite command | `.venv/bin/python -m pytest` — `[VERIFIED: run this session]` **806 passed, 72 skipped, 878 collected**, 31.26s, keyless |
| Evals command | `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/python -m evals --quiet; echo $?` — `[VERIFIED: run this session]` **PASS 59/59 cases (100% vs 90% required)**, exit 0 |

**These exact numbers (806/72/878/59) are 2026-08-16 snapshots and must be re-measured at
execution, per the standing house rule.** They are recorded here only so the plan's
"expected baseline" step has a number to diff against for drift, not as a value to carry
into any doc surface the plan writes.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-limitations-recorded (deletion, ×4) | Each closed bullet's distinctive phrase has grep count 0 in README, and 0 anywhere else under `docs/` or `.planning/codebase/` | doc-grep gate | `grep -c "<phrase>" README.md` per bullet; `grep -rln "<phrase>" docs/ .planning/codebase/` | ❌ Wave 0 — no existing test greps README bullets; write one, or run manually as a plan-level verification step (see note below) |
| REQ-limitations-recorded (survivor links) | `:297` new-ADR link resolves to a file that exists; `:298` ADR-0007 link resolves (already does); `:300` OPERATIONS anchor resolves | link-existence gate | `test -f docs/adr/0013-*.md`; grep the anchor text into `docs/OPERATIONS.md` and confirm the README link's fragment matches a heading | ❌ Wave 0 |
| REQ-limitations-recorded (ADR index) | `docs/adr/README.md`'s Index table gains a `0013` row and its counting prose is re-derived | existing derived-counts test | `pytest tests/test_evals.py -k adr_index` (selector may need adjusting to the actual test id; the test function is `test_the_adr_index_counting_prose_is_derived_from_the_table`) | ✅ exists, will auto-catch a forgotten prose update |
| REQ-limitations-recorded (measured eval-section prose) | README's "Nineteen... twenty-one... two... six" sentences match `evals/fixtures/` count + `REFUSALS.json` count + the `judge_truncated`/`recorded_then_failed_replay` kind counts | new derived-counts test, mirroring the ADR index one | `pytest tests/test_evals.py -k readme_eval_counts` (new selector, name TBD by planner) | ❌ Wave 0 — recommended new test, see Code Examples |
| REQ-limitations-recorded (intro wording) | Section intro states "chosen, recorded, and argued for" (or a paraphrase carrying the same three commitments) | manual/human skim | N/A — see note below | N/A |
| Requirements/roadmap/state close-out | `REQUIREMENTS.md` checkbox + traceability row flip for `REQ-limitations-recorded`; `ROADMAP.md` Phase 22 checkbox + Progress table row; `STATE.md` front matter | file-content gate | `grep -n "REQ-limitations-recorded" .planning/REQUIREMENTS.md` (expect `[x]` and non-"Pending" table cell) | ❌ Wave 0 (bookkeeping, not a pytest test — verified by the same manual-diff convention Phases 18–20 used) |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/test_evals.py -k "adr or readme"` (fast,
  targeted at the doc-derived-count tests this phase touches)
- **Per wave merge:** full suite (`.venv/bin/python -m pytest`) + offline evals
  (`python -m evals --quiet`)
- **Phase gate:** full suite green, offline evals green, plus the manual grep/link gates
  below, before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] A doc-grep verification step (could be a pytest test under a new
  `tests/test_readme.py`, or a documented manual `grep` sequence run and pasted into the
  plan's verification block — precedent for the latter is `20-VERIFICATION.md`'s
  `readme_bullet` gate, which used a bare `diff`/`grep` rather than a pytest test).
  Recommend a real pytest test if the phase's PR is expected to survive future doc
  changes without a human remembering to re-run a manual grep; a manual gate is cheaper
  but relies on the verifier repeating it by hand, same tradeoff `20-VERIFICATION.md`
  accepted for its `readme_bullet` row.
- [ ] `test_readme_eval_counts_are_derived_from_the_tree` (or similar name) —
  mirrors `test_the_adr_index_counting_prose_is_derived_from_the_table`'s pattern against
  `evals/fixtures/` + `evals/REFUSALS.json` instead of `docs/adr/README.md`'s table.
- [ ] No framework install needed — pytest, ruff, and the existing `.venv` already cover
  this phase's tooling needs.

## Security Domain

**`security_enforcement` config key:** not present in `.planning/config.json` (the file
does not exist in this repo — `[VERIFIED: ls .planning/config.json, run this session,
no such file]`). Per the instruction's own default ("absent = enabled"), treated as
enabled, but this phase's actual attack surface is effectively nil: it changes no code,
no auth path, no data flow, and no runtime configuration. Documented briefly rather than
skipped, since the instruction requires either an explicit `false` or a completed section.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No auth path touched |
| V3 Session Management | No | No session code touched |
| V4 Access Control | No | No access-control code touched |
| V5 Input Validation | No | No input-handling code touched |
| V6 Cryptography | No | No crypto code touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| A new ADR or OPERATIONS note accidentally documenting an operational secret handling change incorrectly (e.g. implying an Admin API key would be stored insecurely if adopted) | Information Disclosure (documentation only, not code) | The rejected-alternative framing in ADR-0013 should explicitly note the Admin API key's blast radius as one of the rejection reasons (already recommended in Architecture Patterns §2, reason 1) — this is itself the mitigation: documenting the risk of the *unbuilt* alternative, not building it |

The one security-adjacent fact this research surfaced is that the Admin cost API's key
is a meaningfully larger secret than what the service manages today — worth stating
plainly in the ADR (as recommended above) precisely because it's a real, verifiable
reason to reject the alternative, not because this phase introduces any new risk itself.

## Sources

### Primary (HIGH confidence)
- `README.md` (full file, both a git-tracked read and a live re-grep this session) —
  Limitations section inventory, eval-section prose, API table, architecture diagram
- `src/research_agent/service.py:860-930` — `/health` handler, credential validity fields
- `src/research_agent/usage.py:470-540` — `record_embedding`, the two deliberate
  asymmetries with `record()`
- `docs/OPERATIONS.md` (full file, 919 lines) — credential-validity prose, Supabase
  region/tier/connection-budget facts, RLS "do not fix" precedent
- `docs/DESIGN.md` (full file) — Cost section, Testing section (judge rationale history)
- `docs/adr/README.md` (full file) — Record shape, supersession convention, Index table
  and its derived-counts convention
- `docs/adr/0007-anonymous-identity-fairness-global-cap.md` (full file) — Nygard-form
  reference, Carried-forward convention
- `docs/adr/0012-judge-independent-of-the-critic.md` (full file) — most recent Nygard-form
  reference, `### Rejected alternatives` shape
- `evals/graders.py:735-810` — `Judge.verdict()`, the `max_tokens=1500` truncation
  docstring and call site
- `evals/harness.py:340-495` — `replay_case`, `grade_fixture_current`,
  `record_case_to_fixture`
- `evals/REFUSALS.json` (full file) — 21 documented refusals, kinds and details
- `tests/test_evals.py:3130-3225` — the ADR chain test and
  `test_the_adr_index_counting_prose_is_derived_from_the_table`, the pattern to mirror
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — traceability
  table, Phase 22 success criteria, current milestone state
- `.planning/phases/20-note-count-bound/deferred-items.md`,
  `.planning/phases/20-note-count-bound/20-VERIFICATION.md` — deletion-gate style
  precedent, the two settled-or-deferred items (`PROJECT.md:31-32`, `CONCERNS.md:242`)
- `.planning/codebase/CONCERNS.md:242-270` — the stale "no eviction" claim
- `.planning/PROJECT.md:1-45` — current stale test counts
- Live commands run this session: `.venv/bin/python -m pytest` (806/72/878),
  `python -m evals --quiet` (59/59), `ls evals/fixtures | wc -l` (19), `ls docs/adr/`
  (12 records + README), `git log -p --follow -- README.md` (ADR-0007 link provenance)

### Secondary (MEDIUM confidence)
- None distinct from Primary — every claim in this document is either read directly from
  the tree this session or fetched from Anthropic's own official docs (below).

### Tertiary (LOW confidence, per the classify-confidence seam)
- `[CITED: platform.claude.com/docs/en/manage-claude/usage-cost-api]` — fetched via
  WebFetch this session. The seam's `classify-confidence --provider webfetch --verified`
  call returned `LOW` even with `--verified` set (webfetch is not in the seam's HIGH/MEDIUM
  provider table), so this is reported as LOW per the tool's authoritative output despite
  being sourced from Anthropic's own official documentation. Treat the four rejection
  reasons in Architecture Patterns §2 as well-sourced but not independently
  cross-checked against a second source this session.
- `[ASSUMED]` — A2 in the Assumptions Log (Supabase free-tier read-replica absence):
  carried from the existing README bullet's own unsourced claim, not independently
  re-verified against Supabase's current pricing page this session.

## Metadata

**Confidence breakdown:**
- README/ADR/OPERATIONS inventory: HIGH — every line number and verbatim quote was read
  from the file this session, several re-confirmed with a second independent read or grep
- Cost-approximation ADR's Anthropic API material: MEDIUM-in-substance, LOW-per-seam — the
  facts are from official Anthropic docs, but the fetch provider (`webfetch`) is scored
  LOW by this project's `classify-confidence` seam regardless of source authority; the
  planner should treat the four rejection reasons as solid but worth a second glance if
  Anthropic's API shape has changed since this session
- Defects-record placement recommendation: MEDIUM — argued from house precedent
  (`OPERATIONS.md`'s RLS-notices section) and the intro's own wording constraint, but
  explicitly left as Claude's Discretion in CONTEXT.md, so it is a recommendation, not a
  verified fact

**Research date:** 2026-08-16
**Valid until:** Effectively pinned to Phase 21.5's execution — this document's numeric
snapshots (test counts, fixture/refusal counts) are stale the moment 21.5 lands, by
design (see the sequencing note in `<user_constraints>`). The structural/architectural
findings (ADR format, bullet dispositions, OPERATIONS gaps, defect-placement argument) are
not time-sensitive and should hold through Phase 22's execution regardless of 21.5's
outcome.
