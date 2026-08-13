# Phase 13: Embedding model migration - Context

**Gathered:** 2026-08-06
**Status:** Ready for research
**Source:** Routine calls made by the orchestrator (user asked to proceed without a question
round). Each is revisable at plan review if Hesam disagrees — none is user-ratified the way
Phase 12's were, and the plans must not describe them as such.

<domain>
## Phase Boundary

Changing the embedding model or dimension gets a real path: a command that re-embeds an
existing corpus into a new table, with cost reported before the run, an explicit and
reversible cutover, and the model-vs-infrastructure recall question answerable rather than
confounded.

This is a **reversal in tension with DEC-10**, which copies embeddings during migration
*specifically* so recall behaviour does not change at the same moment infrastructure does
("two suspects and no way to separate them"). DEC-10 is not among the promoted five, so this
phase records **its own ADR** stating what supersedes it and what survives.

**Honest scale note:** production notes now expire after 7 days (Phase 12), so the live
corpus is tiny and self-cleaning. This phase's value is the *demonstrable path* — the
tooling, the cost preview, the isolation discipline — not rescuing a large corpus. Say that
in the docs rather than implying otherwise.

</domain>

<decisions>
## Implementation Decisions (orchestrator calls — confirm at plan review)

### Isolation: two distinct operations, measured by a golden recall set

- **Two separate commands, never one:**
  1. **Copy-only migration** — move a corpus to a new table, same vectors. DEC-10's
     guarantee survives here: recall must be **byte-identical** before and after, and a test
     proves it. This is the infrastructure variable, alone.
  2. **Re-embed migration** — embed the corpus's texts with a new model/dimension into a new
     table. Recall MAY change; that is the point. This is the model variable, alone.
- **A golden recall set makes criterion 5 measurable:** a frozen set of notes + queries with
  expected results, run against the old table before cutover and the new table after. The
  copy-only path must show zero delta; the re-embed path's delta is then attributable to the
  model by construction. Two operations, two measurements, one variable each.
- Rationale for taking both halves rather than choosing: they compose — the golden set is
  worthless for attribution unless the copy-only path exists to prove the infrastructure
  half, and the copy-only path alone proves nothing about what a model change did.

### `research_agent.migrate` gets proven, not left rotting

- The command has been **unexercised through two phases that touched the database** (11
  started clean by decision; 12 migrated nothing). A migration phase that leaves the
  existing migration tool unproven would be absurd.
- Give it real test coverage against a real Postgres. Then decide structurally: the new
  embedding-migration commands either **extend** `research_agent.migrate` or are siblings
  under one CLI surface — researcher proposes, based on what the code actually looks like.
  Do not fork a second, third migration idiom.

### Cost preview before the run (SC-2)

- The re-embed command reports the estimated cost **and refuses to proceed** without an
  explicit flag or confirmation. Voyage embedding pricing must be established from the
  provider's published rates and effective-dated the way `usage.py` prices Claude — note
  that Voyage spend is currently accounted **nowhere** (known gap since the Phase 10
  codebase mapping). Whether closing that accounting gap fully belongs here or in Phase 14
  is the researcher's proposal; at minimum the preview must be honest.
- `pricing_unknown` semantics from DEC-12 apply: fail loud, never zero.

### Cutover: explicit, reversible, boring

- The old table survives until the new one is confirmed — a cutover is a config change
  (`VECTOR_STORE_TABLE` or equivalent), not a destructive rename. Rollback is pointing back.
- The **loud dimension check stays loud** (SC-4). A migration tool that auto-coerces
  dimensions has become the silent failure the check exists to prevent.

### Scope

- All work happens against the **pgvector** backend (production). The other three backends
  are not migration targets — json/memory have no table concept and chroma is a dev
  curiosity — but the recall-measurement harness should be backend-agnostic where free.
- Owner scoping and note TTL (Phase 12) are part of the schema now: a migrated table carries
  `owner` and `created_at`, and the golden set must include owner-scoped queries so
  migration cannot silently drop tenancy.

### Post-research calls (2026-08-06, researcher recommendations adopted)

- **`VOYAGE_PRICES` lives in `usage.py`** — one pricing home, effective-dated `PriceWindow`
  pattern, so Phase 14 finds all pricing in one place. Fail-loud `pricing_unknown`.
- **The re-embed path is demonstrated live once** against Supabase scratch tables (created
  and dropped by the demonstration), not merely locally — the phase's value is the
  demonstrable path.
- **Preview semantics: the cost preview always prints; `--yes` is required to spend.**
  No flag combination silently embeds.
- **`migrate.py` needs REPAIR before proof:** it predates Phase 12 — `migrate_notes` inserts
  only `(text, embedding)`, silently orphaning every note to `owner=''` and restarting its
  TTL; `migrate_sessions` drops `owner` too. Repairing that data-loss bug is in scope and
  comes before the new subcommands.
- **New commands are argparse subcommands of `python -m research_agent.migrate`** (bare
  invocation stays the legacy path). One migration surface, no second idiom.
- **"Recall byte-identical" is never asserted through the HNSW index** (approximate, build
  not guaranteed deterministic). The claim decomposes: server-side `INSERT..SELECT` copy,
  SQL join asserting `embedding::text` equality, golden-query equality under **exact scan**
  (`SET LOCAL enable_indexscan = off`) with a tie-free golden set, plus a separate honest
  index-sanity set-equality check.
- **Dimension ceiling:** voyage-3.5 supports `output_dimension=2048`, which exceeds
  pgvector's HNSW limit (2000) for the `vector` type — the re-embed command refuses >2000
  loudly rather than creating an unindexable table.
- **ADR-0008 uses `Status: Accepted` with a `Source:` line** (the 0006/0007 precedent) —
  DEC-10 was never promoted, so there is no numbered record to supersede; the prose records
  what survives (copy-only IS DEC-10's operation) and what is new.

### Out of scope — explicitly

- Actually changing the production embedding model. The phase builds and proves the path;
  flipping models is an operator decision for later.
- Cost multipliers / `inference_geo` (Phase 14), eval quality (Phase 15).
- Any change to recall semantics (min_similarity, ranking) beyond what a model change
  inherently causes.

### Claude's Discretion

- CLI shape (`python -m research_agent.migrate embeddings --copy|--re-embed ...` vs
  subcommands), table naming scheme, batch sizes, resume-on-interrupt behaviour.
- Golden-set size and content, and where it lives (checked in, deterministic).
- Whether the fake embedder used by tests suffices for the golden harness locally, with the
  real Voyage path proven live once.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/ROADMAP.md` § Phase 13 — five success criteria, the DEC-10 tension note
- `.planning/REQUIREMENTS.md` — REQ-embedding-model-migration
- `.planning/intel/decisions.md` — DEC-10 (copy-don't-re-embed) and DEC-12 (pricing fails loud)
- `src/research_agent/migrate.py` — the unproven tool this phase must prove
- `src/research_agent/memory.py` — four backends; pgvector table with fixed `vector(N)` width,
  `owner`, `created_at`; the loud dimension check; `search_path` includes `extensions`
- `src/research_agent/usage.py` — the effective-dated price table pattern to imitate for Voyage
- `docs/adr/README.md` — supersession convention; this phase records a new ADR for DEC-10
- `tests/test_store_contract.py` — the 4-arm shared suite; `note_scoping`/`note_ttl` semantics
  a migrated table must preserve

</canonical_refs>

<specifics>
## Specific Ideas

- State of the world: release v9, two machines, Supabase (session pooler :5432,
  `prepare_threshold=None`, advisory-locked lazy DDL, `Database.transaction()` exists).
  Local Postgres 17 + pgvector on :54329 for gated tests; CI runs real Postgres + chroma.
  Baselines entering the phase: plain 527/47, armed 573/1.
- **Gate discipline: THIRTEEN vacuous gates across five phases.** Baselines are not enough —
  Phase 12 proved a structurally sensible gate can be blind to the exact mutation it exists
  to catch. Every gate gets mutated red before it is trusted, and the falsification recorded.
- Branch note: this branch is stacked on `gsd/phase-12-caller-identity` because the note
  schema (owner, created_at) comes from Phase 12. Once PR #6 merges, rebase onto `main`
  before execution. One PR for the whole phase at the end.
- README is a per-phase deliverable (standing instruction): the "Changing embedding model
  means a new pgvector table" limitation is this phase's to rewrite honestly.
- Do not pass `model=` overrides to spawned agents (standing instruction).

</specifics>

<deferred>
## Deferred Ideas

- Full Voyage spend accounting in `/metrics` — Phase 14 territory if the researcher judges
  the preview-only slice cleaner here.
- Actually switching the production embedding model.
- `/health` key-validity probing (still open from Phase 11).

</deferred>

---

*Phase: 13-embedding-model-migration*
*Context recorded: 2026-08-06 — orchestrator calls, to be confirmed at plan review*
