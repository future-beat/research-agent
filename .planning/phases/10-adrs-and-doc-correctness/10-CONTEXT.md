# Phase 10: ADRs and doc correctness - Context

**Gathered:** 2026-08-04
**Status:** Ready for planning
**Source:** Decisions taken directly with the user (no discuss-phase run — the phase's open
questions were format and research need, both answered)

<domain>
## Phase Boundary

This phase turns the project's architectural record from prose into numbered, status-bearing
ADRs, and stops three documents asserting things that are verifiably false.

It is a **documentation phase**. It changes no production code and no runtime behaviour. Its
value is that the six design reversals later in milestone v1.1 each get a record to supersede
rather than prose to quietly contradict.

</domain>

<decisions>
## Implementation Decisions

### ADR format — Nygard

- `docs/adr/` uses the **Nygard** form: Title, `Status`, Context, Decision, Consequences.
- **Rationale:** it maps almost one-to-one onto how `docs/DESIGN.md` already argues each
  decision — position, rejected alternative, consequence — so translation loss from the 23
  extracted decisions is minimal. It is also the form most reviewers recognise on sight.
- Every ADR carries an explicit `Status` field. Use `Accepted` for all five promoted here.
- Numbering is sequential and zero-padded: `docs/adr/0001-*.md` … `0005-*.md`.
- ADRs must support **supersession**: a later reversal adds `Superseded by ADR-000N` to the
  Status line of the record it overturns. Phases 13, 15, 16 and 17 depend on this working.

### No research phase

- Skipped deliberately. The 23 decisions already exist with rationale and rejected
  alternatives in `.planning/intel/decisions.md`, extracted during ingest; the three doc
  corrections are facts already verified against the code and against `fly releases`.
- Consequence: this phase's `VALIDATION.md` was written directly rather than derived from a
  `RESEARCH.md` "Validation Architecture" section. Verification here is **grep gates over
  documents**, not test sampling — there is no behaviour to sample.

### The five decisions to promote

Sourced from `.planning/intel/decisions.md` at the cited line numbers:

1. **DEC-01** (line 27) — Routing is a deterministic Python state machine, not an LLM prompt.
2. **DEC-02** (line 37) — The critic is a separate node with its own rubric.
3. **DEC-04** (line 55) — Follow-ups reuse the critic; no prior notes stops with
   `no_prior_research`.
4. **DEC-14** (line 178) — Sessions store completed runs in SQLite, deliberately not
   LangGraph's checkpointer.
5. **DEC-22** (line 262) — The eval judge runs on a stronger model than the pipeline and
   returns a structured verdict.

### Claude's Discretion

- ADR filename slugs.
- Whether Consequences is split into positive/negative subsections.
- How the forward-links from `docs/DESIGN.md` are worded and placed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope
- `.planning/ROADMAP.md` — the `### Phase 10` section, six success criteria, plus the
  **Outcome** note on Phase 10.5 which already satisfied SC-5
- `.planning/REQUIREMENTS.md` — `REQ-adr-promotion`

### Source material for the ADRs
- `.planning/intel/decisions.md` — all 23 decisions with rationale and rejected alternatives;
  the five to promote are at lines 27, 37, 55, 178, 262
- `docs/DESIGN.md` — the prose each ADR is promoted from; must gain forward-links

### Facts to correct
- `docs/OPERATIONS.md:49` — claims deploys run through Fly's GitHub integration and are not
  CI-gated. **Verified false.** Deploys are manual; `fly releases -a research-agent` shows
  every release attributed to the owner's personal account.
- `docs/DESIGN.md:28` — says `MemoryStore` has "three implementations … JSON (default),
  in-memory, and Chroma". There are **four**; `pgvector` has existed since Phase 8, and
  `docs/OPERATIONS.md:168` already says four.

### Reversal register
- `.planning/ROADMAP.md` § Reversal register — names which phase supersedes which record

</canonical_refs>

<specifics>
## Specific Ideas

- **SC-5 is already satisfied.** The Phase 10.5 cutover (Fly release v4, 2026-08-04) carried
  the README restructure, the `src/` reorganisation and its bugfix, so the deployed tree
  equals `main`. This phase should **re-verify** it (`fly releases`, plus `/`, `/health`,
  `/demo`, `/metrics` returning 200) and record the result — not redeploy.
- **SC-3's target moved slightly.** Phase 10.5 already edited `docs/OPERATIONS.md` to add the
  `SESSIONS_TOKEN` row. The false deploy claim at line 49 was **not** touched and is still
  there. Verify current line numbers before editing; do not trust the number in the criterion.
- **SC-6 (pricing).** The Sonnet 5 introductory $2/$10 window ends 2026-08-31 and $3/$15
  applies from 2026-09-01. `src/research_agent/usage.py:59-76` already implements both windows
  correctly — **no code change is needed**. The work is ensuring no doc quotes a single rate as
  permanent, and that `/pricing` is named as the live source.
- The `docs/OPERATIONS.md` "New files from Fly.io Launch" warning and the `min_machines_running`
  note are still accurate — do not sweep them while editing nearby lines.

</specifics>

<deferred>
## Deferred Ideas

- **Promoting the other 18 decisions.** Only the five load-bearing ones are in scope; the rest
  stay as narrative in `docs/DESIGN.md`. Reversals of decisions outside the five (DEC-10,
  DEC-20) create their own ADR in the phase that reverses them.
- **`_index_json` does not advertise `DELETE /sessions/{id}`** — found during Phase 10.5, left
  alone deliberately. Production code, not a doc fix.
- **`ruff format --check` flags `tests/test_service.py`**, and did before Phase 10.5. The gate
  is `ruff check`, which passes. Separate formatting commit, not this phase.
- Everything in `.planning/STATE.md` → Blockers/Concerns marked "not yet phased" (unscoped
  cross-visitor notes, spend-cap race, unpinned pydantic, untested 3.10 floor).

</deferred>

---

*Phase: 10-adrs-and-doc-correctness*
*Context recorded: 2026-08-04 — format and research-need decided with the user*
