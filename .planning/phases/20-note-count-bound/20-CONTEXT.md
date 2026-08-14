# Phase 20: Note count bound - Context

**Gathered:** 2026-08-14
**Status:** Ready for research
**Source:** Milestone-questioning decisions (user-ratified 2026-08-13) plus one phase-level
decision ratified today via AskUserQuestion: **the cap is an env knob defaulting to 100**.

<domain>
## Phase Boundary

Notes gain a second bound: a per-owner count cap with oldest-first eviction, with
byte-identical semantics across json, memory, chroma, and pgvector, proven by the shared
4-arm contract suite. Notes are then bounded by expiry AND count, which kills the README
bullet ("Notes are bounded by expiry alone") rather than narrowing it.

**Not in this phase:** semantic dedup or summarisation (explicitly Out of Scope in
REQUIREMENTS — no semantics four vector backends can agree on); deleting the README bullet
(Phase 22 owns the Limitations section); the record run (Phase 21); any change to recall
semantics, the relevance floor, or the TTL.

</domain>

<decisions>
## Implementation Decisions

### The cap is an env knob, default 100 — user-ratified today

- `NOTE_CAP_PER_OWNER` (exact name at planner's discretion, following the codebase's
  env-knob naming conventions), **default 100**, read per call like every other knob in
  this codebase (the `session_ttl_seconds()` convention — monkeypatch-able in tests,
  never cached in a module constant).
- Rationale accepted with the choice: a research run writes a handful of notes; 100 is
  weeks of heavy use for one identity, and the 7-day TTL already prunes. The knob exists
  so the operator can tighten it for the free-tier database without a deploy.
- Floor/validation semantics (what does 0 mean? negative? — probably "invalid reads as
  default" per the `session_ttl_seconds` fallback style) are the researcher's question.

### Oldest-first eviction, at write time

- Eviction is FIFO by `created_at` within one owner: adding note N+1 past the cap evicts
  the oldest. Every backend already carries `owner` and `created_at` (Phase 12), which is
  exactly why this bound is implementable where semantic dedup is not.
- Eviction happens on `add()` — the same place the TTL sweep already runs — so no
  scheduler is needed and the bound holds as an invariant after every write, not
  eventually.
- Owner matching is EXACT, per the Phase 12 convention: `owner=""` (legacy rows) is its
  own bucket, never a wildcard. Eviction must never cross owners.

### Byte-identical across four backends, proven not asserted

- The claim being defended (the README bullet's own words): identical behaviour across
  json, memory, chroma, and pgvector. The 4-arm contract suite is where that's proven —
  same inputs, same eviction outcome, all four arms.
- Tie-breaking when `created_at` collides must be DEFINED and identical (the researcher
  should check what orderings each backend can actually guarantee — this is exactly where
  byte-identical claims die).

### Claude's Discretion

- Where the eviction lives per backend (a shared helper vs per-store implementations —
  whatever keeps the four honest; the contract suite is the referee either way).
- Whether eviction of expired-but-unswept rows counts against the cap before or after the
  TTL sweep (define the order: sweep first, then count — probably — but verify it's
  identical everywhere).
- Whether `add()` returns anything about eviction (probably not — no caller needs it —
  but if a trace entry is cheap and honest, planner's call).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The surfaces being changed
- `src/research_agent/memory.py` — all four `MemoryStore` backends, the `add()` seam, the
  TTL sweep each backend already runs, owner scoping (Phase 12), the pgvector DDL (which
  Phase 17.5 gave RLS — any new SQL stays inside the existing schema patterns)
- `tests/test_store_contract.py` — the 4-arm behavioural suite (102 tests today); this is
  where the new semantics get their arms
- `tests/test_memory_stores.py` — the store unit tests

### House constraints
- DEC-08 (store/embedder seams; the graph reaches stores only through add/query/len/
  describe — the cap must not change the seam's shape)
- DEC-16 style (shared behavioural tests are the enforcement, not prose)
- Phase 12 records in `.planning/milestones/v1.1-phases/12-*` — owner/TTL semantics this
  must compose with
- Keyless suite; pgvector arm Postgres-gated exactly as today (66 of the 67 skips)

### Process
- `.planning/phases/19-*/19-VERIFICATION.md` and `18-*/18-VERIFICATION.md` — the
  verification bar this phase closes against
- Tooling: gsd-tools (GSD Core v1.10.0); STATE.md edited by hand

</canonical_refs>

<specifics>
## Specific Ideas

- The README bullet this phase falsifies ("bounded by expiry alone… no dedup or
  summarisation") stays in place for Phase 22 — but its claim becomes knowingly false the
  moment the cap lands, the same deliberate transient Phases 18/19 left. State it in the
  SUMMARY.
- OPERATIONS' configuration table gains the new knob; whatever DESIGN says about note
  lifecycle gets the whole-file treatment if this phase falsifies it.
- The live database currently holds 8 notes across 7 sessions — eviction will be
  invisible in production at today's volumes, which is fine: the bound is a guarantee,
  not a behaviour change for current users. Say so rather than overselling.

</specifics>

<deferred>
## Deferred Ideas

- Semantic dedup / summarisation — permanently out (recorded in REQUIREMENTS Out of Scope).
- README Limitations rewrite — Phase 22.
- The record run — Phase 21.

</deferred>

---

*Phase: 20-note-count-bound*
*Context gathered: 2026-08-14 from milestone decisions + cap-value ratification*
