# Phase 21: Forty recorded answers - Context

**Gathered:** 2026-08-15
**Status:** Ready for research
**Source:** Milestone-questioning decisions (user-ratified 2026-08-13) plus two phase-level
decisions ratified today via AskUserQuestion: **the paid run executes at a mid-execution
checkpoint**, and **the spend is staged calibrate-first**.

<domain>
## Phase Boundary

Every one of the 40 golden cases gains a fixture carrying a real recorded answer plus the
settled judge's verdict as metadata, replayed and graded keylessly on every push. The paid
record run is an operator checkpoint: re-quoted at run time, approved by the user in the
prompt, actual spend reported against the quote. A case the recorder refuses — failed
graders or judge — is surfaced as a finding, not retried into silence: refusals are the
machinery working.

**Hard-order dependency satisfied:** Phase 18 settled the judge (`claude-opus-4-8`,
`stop_reason` guard, ADR-0012). Verdicts are recorded once; this phase records them under
that judge.

**Not in this phase:** deleting or editing any README Limitations bullet (Phase 22 owns
the section — including the recorded-answers bullet this phase falsifies); any change to
graders, the judge, the golden cases' definitions, or recall semantics; any Fly deploy of
substance (fixtures are repo data graded in CI, not service state — if the README/doc pass
merges, the deploy is routine and the user runs it).

</domain>

<decisions>
## Implementation Decisions

### The paid run is a mid-execution checkpoint — user-ratified today

- The phase plan includes the record run as a task with a `checkpoint` before any spend.
  Execution PAUSES, shows the fresh quote, and NOTHING runs `--yes` until the user approves
  in that prompt. The recorder's own refuse-without-`--yes` gate stays the enforcement.
- Money context measured at planning (2026-08-15): the live quote is **$17.4812** for
  40 cases / 11 follow-up turns / 91 judge calls, within a cent of the $17.48 quoted
  2026-08-13 — expected, since Sonnet 5's $2/$10 is now permanent and the judge's rates
  are unchanged. Basis: **1 measured, 39 assumed** — assumed tokens dominate.

### The spend is staged: calibrate, re-quote, checkpoint again — user-ratified today

- Stage 1: record ONE case (~$0.39 quoted), which converts the quote's basis for every
  later case sharing its shape. Stage 2: re-quote the remaining cases from the measured
  basis and present the tighter number at a second checkpoint before the bulk run.
- Two small approvals instead of one blind one. The recorder's own output recommends
  exactly this ("run a one-case calibration first"); the phase makes it the plan rather
  than a suggestion.

### Refusals are findings

- Per REQ-forty-recorded-answers verbatim: a case the recorder refuses is surfaced in the
  record run's output as a finding, not silently retried or dropped. The SUMMARY carries
  the refusal list (possibly empty) as a result either way.
- No auto-retry loops around the recorder. If a refusal looks transient (network, rate
  limit) the decision to re-run that case is the operator's, at the checkpoint, with the
  incremental cost stated.

### Claude's Discretion (researcher questions first, then planner)

- **The stale fixture question:** `technical-figures.json` was recorded 2026-08-10 —
  BEFORE Phase 18 settled the judge. The researcher must read the fixture and determine
  whether its verdict metadata came from the old judge; if so, re-recording it is in scope
  (verdicts are recorded once — *under the settled judge*, which is the entire reason for
  the phase ordering). If its metadata is judge-independent, keeping it is fine. Read,
  don't assume.
- How the keys reach a record run now that PR #28 removed chat.py's import-time
  `load_dotenv()` — check what `python -m evals --record --live` actually reads (exported
  env? its own dotenv? nothing?) and state the exact invocation the operator needs.
- What "all 40 replayed keylessly on every push" does to the offline eval denominator
  (today 41 = 40 golden + 1 recorded; does it become 80 graded checks, and what does CI
  runtime do?) and to `--min-pass-rate` semantics.
- Whether the record run is resumable — if it dies at case 23, are cases 1–22's fixtures
  kept and the re-quote incremental? This decides whether the bulk stage is one task or
  chunked.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The surfaces
- `evals/` — the recorder (`--record`), replay leg, fixtures dir (`evals/fixtures/`),
  graders, the judge wiring from Phase 18
- `evals/fixtures/technical-figures.json` — the one existing fixture; its provenance
  decides whether it survives
- `.github/workflows/ci.yml:73` — the eval gate (`--min-pass-rate 0.9`)
- `tests/test_evals.py` — the replay/recording tests that must keep passing

### House constraints
- Phase 18 records (`.planning/phases/18-*`) — the settled judge, ADR-0012, the
  ~$0.06-per-verdict figure
- DEC-13 honest denominators — however the pass-rate denominator changes, it changes
  honestly and visibly
- Keyless CI is inviolable: nothing this phase adds may require a key on push
- README updated in the phase's final PR (standing rule, re-affirmed by the user
  2026-08-15); the Limitations bullet about recorded answers stays UNTOUCHED for Phase 22

### Process
- `.planning/phases/20-note-count-bound/20-VERIFICATION.md` — the closing bar
- Tooling: gsd-tools (GSD Core v1.10.0); STATE.md edited by hand

</canonical_refs>

<specifics>
## Specific Ideas

- The actual-vs-quote report is a success criterion, not a nicety: criterion 4 says the
  spend is *reported against* the quote. The SUMMARY should carry the per-stage numbers
  (calibration actual, re-quote, bulk actual, total vs $17.4812).
- Recording happens locally on the operator's key, not through the deployed service — the
  service's spend cap and reserved-run guard are not in this path (verify, don't assume).
- The fixtures are the deliverable that outlives the phase: 40 real answers, graded on
  every future push for free, dated and attributed to the models that produced them. The
  replay output already prints that provenance honestly ("that grades what the pipeline
  said then") — keep that property.

</specifics>

<deferred>
## Deferred Ideas

- README Limitations rewrite — Phase 22, which now has three knowingly-false bullets
  waiting plus the recorded-answers one this phase falsifies.
- Any judge or grader evolution — a NEW milestone; ADR-0012 is settled.

</deferred>

---

*Phase: 21-forty-recorded-answers*
*Context gathered: 2026-08-15 from milestone decisions + checkpoint/staging ratification*
