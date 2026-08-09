# Phase 13: Embedding model migration - Research

**Researched:** 2026-08-06
**Domain:** pgvector table migration, Voyage embedding API + pricing, ANN-vs-exact recall equivalence
**Confidence:** HIGH (code claims verified by reading the tree; Voyage pricing verified against docs.voyageai.com; pgvector limits verified against the official README)

<user_constraints>
## User Constraints (from CONTEXT.md)

**Provenance note:** these are orchestrator calls, not user-ratified decisions. Revisable at
plan review; plans must not describe them as user-locked.

### Locked Decisions (orchestrator calls — confirm at plan review)

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
- **`research_agent.migrate` gets proven, not left rotting.** Real test coverage against a
  real Postgres. Then decide structurally: the new embedding-migration commands either
  extend `research_agent.migrate` or are siblings under one CLI surface — researcher
  proposes, based on what the code actually looks like. Do not fork a second, third
  migration idiom.
- **Cost preview before the run (SC-2).** The re-embed command reports the estimated cost
  and refuses to proceed without an explicit flag or confirmation. Voyage pricing
  established from published rates and effective-dated the way `usage.py` prices Claude.
  Voyage spend is currently accounted **nowhere**. Whether closing that gap fully belongs
  here or in Phase 14 is the researcher's proposal; at minimum the preview must be honest.
  `pricing_unknown` semantics from DEC-12 apply: fail loud, never zero.
- **Cutover: explicit, reversible, boring.** Old table survives until the new one is
  confirmed — cutover is a config change (`VECTOR_STORE_TABLE` or equivalent), not a
  destructive rename. Rollback is pointing back. The **loud dimension check stays loud**
  (SC-4); auto-coercion is forbidden.
- **Scope:** all work against the **pgvector** backend. json/memory/chroma are not
  migration targets, but the recall-measurement harness should be backend-agnostic where
  free. A migrated table carries `owner` and `created_at`, and the golden set must include
  owner-scoped queries so migration cannot silently drop tenancy.
- **Out of scope explicitly:** actually flipping the production embedding model; cost
  multipliers / `inference_geo` (Phase 14); eval quality (Phase 15); any change to recall
  semantics (min_similarity, ranking) beyond what a model change inherently causes.

### Claude's Discretion

- CLI shape (`python -m research_agent.migrate embeddings --copy|--re-embed ...` vs
  subcommands), table naming scheme, batch sizes, resume-on-interrupt behaviour.
- Golden-set size and content, and where it lives (checked in, deterministic).
- Whether the fake embedder suffices for the golden harness locally, with the real Voyage
  path proven live once.

### Deferred Ideas (OUT OF SCOPE)

- Full Voyage spend accounting in `/metrics` — Phase 14 territory if the researcher judges
  the preview-only slice cleaner here.
- Actually switching the production embedding model.
- `/health` key-validity probing (still open from Phase 11).

### Standing instructions (from CONTEXT.md Specifics)

- Gate discipline: **thirteen vacuous gates across five phases** — every gate gets a
  measured baseline AND a mutation that turns it red, with the falsification recorded.
- Branch is stacked on `gsd/phase-12-caller-identity`; rebase onto `main` once PR #6
  merges, before execution. One PR for the whole phase.
- README is a per-phase deliverable: the "Changing embedding model means a new pgvector
  table" limitation is this phase's to rewrite honestly.
- Do not pass `model=` overrides to spawned agents.
- Baselines entering the phase: plain 527/47, armed 573/1.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-embedding-model-migration | A command re-embeds an existing corpus into a new table at a new dimension, with cost reported before the run starts and an explicit, reversible cutover; the loud dimension check must not become a silent coercion. Any re-embedding path must isolate the recall change from the infrastructure change (tension with DEC-10). | Re-embed mechanics (§Architecture Patterns 3), verified Voyage pricing + `count_tokens` preview (§Standard Stack, §Code Examples), `PGVECTOR_TABLE`/`VECTOR_DIMENSIONS` cutover already latent in `memory.py` (§Architecture Patterns 5), dimension-check preservation analysis (§Pitfall 4), copy-only + golden-set isolation design resolving the ANN determinism question (§Architecture Patterns 2, §Pitfall 1) |
</phase_requirements>

## Summary

The phase is smaller and more repair-shaped than its title suggests. Three of its five
success criteria are already latent in the codebase: the cutover mechanism exists
(`PGVECTOR_TABLE` and `VECTOR_DIMENSIONS` env vars, read at `memory.py` import, applied by
a deploy restart — no new config surface needed), the loud dimension check exists and is
already tested (`test_a_dimension_mismatch_is_explained_not_a_type_error`), and the
embedder seam already accepts a per-instance model (`VoyageEmbedder(model=...)`). What does
not exist: any test for `migrate.py`, any Voyage price anywhere, any way to move vectors
between pgvector tables, and any recall measurement.

Forensic reading of `migrate.py` (full findings in §Migrate.py Forensics): it still
*imports and runs* against the pooled `db.py` — it goes through the store classes and
`Database.execute`/`fetchall`, all of which survived Phases 11–12 — but it is
**semantically stale against the Phase 12 schema**. `migrate_notes` inserts only
`(text, embedding)`, silently dropping `owner` and `created_at`; under Phase 12 semantics
every migrated note lands on `owner=''` (belongs to nobody) with a fresh `created_at`
(TTL restarted). `migrate_sessions` likewise drops `owner`. "Proving it" therefore costs a
repair first: the tool must be fixed to carry `owner`/`created_at`, then tested. The new
embedding commands should be **subcommands of the same `python -m research_agent.migrate`
surface** (argparse subparsers, legacy behaviour preserved as the `stores` subcommand and
as the bare-invocation default) — one migration idiom, as CONTEXT demands.

The phase's subtlest question — is an HNSW rebuild a recall-affecting event? — resolves
cleanly: **HNSW is approximate and its build is not deterministic, so "byte-identical
recall" must never be asserted through the index.** The correct decomposition: (1) copy
server-side with `INSERT INTO new SELECT ... FROM old` so vectors never round-trip through
Python — byte equality is then provable with a SQL join; (2) assert golden-query equality
under **exact scan** (`SET LOCAL enable_indexscan = off`, the pgvector-documented escape
hatch), which removes the ANN layer from the correctness claim entirely; (3) separately
assert that the *indexed* query over the new table returns the same result set as the exact
scan — honest at this corpus size (far below `hnsw.ef_search`'s default 40), and stated as
set-equality, not order-equality. Voyage pricing is verified current from the provider's
own docs ($0.06/M tokens for voyage-3.5, the deployed model), billed in tokens, countable
locally and exactly with `voyageai.Client.count_tokens` — which ships in the pinned
voyageai 0.5.0 with `tokenizers` already installed.

**Primary recommendation:** repair-then-prove `migrate.py`, add `embeddings copy` and
`embeddings re-embed` subcommands under it, assert copy fidelity byte-wise plus
exact-scan golden equality, price the preview from an effective-dated `VOYAGE_PRICES`
table imitating `usage.py` (preview-only; `/metrics` accounting deferred to Phase 14), and
cut over via the env vars that already exist.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Copy-only table migration | CLI tool (`migrate.py`) issuing server-side SQL | Database (Postgres executes `INSERT..SELECT`) | Vectors must never round-trip through Python; the DB copies bytes exactly |
| Re-embed migration | CLI tool batching through the Embedder seam | Voyage API (embedding), Database (target writes) | The seam (`VoyageEmbedder`) is the only place text becomes vectors; the CLI orchestrates batches |
| Cost preview | CLI tool, local tokenization | New `VOYAGE_PRICES` table in code | Billing unit is tokens; `count_tokens` counts them locally before any spend |
| Golden recall harness | Shared library module (`src/research_agent/`) | Tests + migration CLI both import it | Two consumers, one implementation — no duplication |
| Recall-equality verification | Database (exact scan queries) | Harness compares results | `SET LOCAL enable_indexscan = off` is a per-transaction DB concern |
| Cutover / rollback | Deploy config (Fly env: `PGVECTOR_TABLE`, `VECTOR_DIMENSIONS`) | `memory.py` (reads them at import) | Already exists; a restart applies it; rollback is pointing back |
| Dimension enforcement | Store (`PgVectorMemoryStore._check_dimensions`) | CLI (must not bypass or coerce) | The loud check lives at the store and must stay the single authority |
| ADR-0008 | `docs/adr/` | `.planning/intel/decisions.md` (DEC-10 annotation) | Supersession is a documentation act with a fixed convention |

## Standard Stack

### Core — nothing new to install

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| voyageai | 0.5.0 (pinned in pyproject.toml) | Embedding + **local token counting** (`Client.count_tokens`, `Client.tokenize`) | Already the production embedder; `count_tokens` verified present in the installed 0.5.0 with signature `(self, texts: List[str], model: str \| None) -> int` [VERIFIED: inspected in project venv] |
| tokenizers | 0.23.1 (transitive dep of voyageai, already installed) | Backs `count_tokens` via HF tokenizer files | Declared dependency of voyageai — `pip show voyageai` lists it [VERIFIED: project venv] |
| pgvector (Postgres extension) | on Supabase (`extensions` schema) and local :54329 | Vector column, HNSW index, `<=>` cosine distance, exact-scan toggle | Already the production store [VERIFIED: codebase + live probe] |
| psycopg / psycopg_pool | current (via `db.py`) | All SQL through `Database` | Phase 11's pool; migration must reuse it, not open raw connections |
| pytest | 9.1.1 | Test framework | Existing suite [VERIFIED: `.venv/bin/pytest --version`] |

**No new packages. No installation step.** The Package Legitimacy Gate is therefore
trivially satisfied.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `count_tokens` (exact, local) | Voyage embed-response `total_tokens` | Exact but only reported *after* spend — useless for a preview. Use it as the post-run reconciliation number instead |
| `count_tokens` | chars/4 heuristic | Free of the HF-hub fetch, but approximate; the preview should be exact when it can be, with the heuristic only as an offline fallback if planned at all |
| Server-side `INSERT..SELECT` copy | Read rows into Python, re-insert via `_literal()` | `repr(float)` round-trips exactly in Python, but a client round-trip adds an unnecessary place for bytes to change and is slower; server-side copy is provably byte-preserving |
| New `VOYAGE_PRICES` in a new module or `usage.py` | Reusing `PRICES` dict | Claude prices are per-token-class (input/output/cache); Voyage is one flat rate per Mtok. Same `PriceWindow` shape, separate table — do not force Voyage into the 4-field `Price` dataclass |

## Package Legitimacy Audit

No packages are installed by this phase. Every library used (voyageai 0.5.0, tokenizers
0.23.1, psycopg, pytest) is already pinned in `pyproject.toml` and present in the project
venv. **Packages removed due to slopcheck [SLOP] verdict:** none. **Packages flagged
[SUS]:** none.

## Migrate.py Forensics (the "prove it" cost, established)

`src/research_agent/migrate.py` (177 lines, three functions + main) — read in full against
the current tree:

**What still works** [VERIFIED: code reading]:
- All its imports resolve: `PGVECTOR_TABLE`, `STORE_PATH`, `VECTOR_DIMENSIONS`,
  `PgVectorMemoryStore`, `db.postgres_configured`, the SQLite/Postgres store classes.
- It never touches a retired single-connection API — it drives the store classes and
  `Database.execute`/`fetchall`/`fetchone`, all pool-backed since Phase 11. It should run.
- The dimension check (lines 114–120) is still loud: JSON entry width vs
  `VECTOR_DIMENSIONS`, `SystemExit` with instructions on mismatch. Preserve verbatim.
- Re-runnability idiom (skip already-present rows) is intact.

**What is semantically broken against the Phase 12 schema** [VERIFIED: code reading]:
1. **`migrate_notes` drops `owner` and `created_at`.** It inserts only
   `(text, embedding)` (line 133–135). JSON-store entries since Phase 12 carry both
   fields. The pg table defaults fill in `owner=''` (belongs to *nobody* under the
   exact-match rule) and `created_at=now()` (TTL restarted). A migration that silently
   orphans every note and resets its expiry is the exact "silently drop tenancy" failure
   the golden set exists to catch.
2. **`migrate_sessions` drops `owner`.** `target.create(...)` is called without `owner=`
   (the parameter exists since Phase 12), and the restoring `UPDATE` (lines 59–63) fixes
   `created_at/updated_at/turns` but not `owner`.
3. **Note dedup keys on `text` alone** (line 126–129) — with owner scoping, the same text
   under two owners is a legitimate pair of rows; the second would be skipped.
4. **`migrate_sessions` silently skips expired sessions** — `source.list()` applies the
   TTL filter (verified in `SQLiteSessionStore.list`, line 302–313). Arguably correct
   behaviour (expired data should not be resurrected), but it must be *stated* in the
   tool's output, not discovered.
5. **Zero test coverage.** `grep -rl migrate tests/` returns nothing. [VERIFIED]
6. **Import-time constants hinder testing.** `migrate.py` imports `VECTOR_DIMENSIONS`,
   `STORE_PATH`, `SESSION_DB_PATH`, `METRICS_DB_PATH` as module constants; a test that
   monkeypatches the env after import changes nothing. The repair should either pass
   explicit CLI args in tests (the `--sessions-db/--metrics-db/--notes` flags exist;
   dimensions does not) or move the dimension read into `migrate_notes`.

**Conclusion:** "proving it" = repair items 1–3 (and decide/state 4), then a Postgres-gated
end-to-end test driving `main(argv)`. The plan must budget the repair as its own task, not
fold it into "add tests."

**CLI structure decision (proposed):** extend `migrate.py` with argparse subparsers:
- `python -m research_agent.migrate` (no subcommand) → legacy stores migration, preserving
  the invocation documented in `docs/OPERATIONS.md` and this module's docstring.
- `python -m research_agent.migrate embeddings copy --to TABLE [--dry-run]`
- `python -m research_agent.migrate embeddings re-embed --to TABLE --model MODEL
  [--dimensions N] [--dry-run] [--yes]`

One file, one surface, one idiom — the sibling-module alternative would fork the idiom
CONTEXT forbids. The module is 177 lines; it can absorb two subcommands without strain.

## Architecture Patterns

### System Architecture Diagram

```
                        ┌─────────────────────────────────────────────┐
                        │  python -m research_agent.migrate           │
                        │  ┌──────────┬───────────────┬────────────┐  │
 operator invokes ────► │  │ (legacy) │ embeddings    │ embeddings │  │
                        │  │ stores   │ copy          │ re-embed   │  │
                        │  └────┬─────┴──────┬────────┴─────┬──────┘  │
                        └───────┼────────────┼──────────────┼─────────┘
                                │            │              │
                                │            │              ├──► count_tokens (local,
                                │            │              │    HF tokenizer cache)
                                │            │              ├──► VOYAGE_PRICES table
                                │            │              │    → cost preview → --yes gate
                                │            │              ├──► VoyageEmbedder(model, dims)
                                │            │              │    → Voyage API (batched)
                                ▼            ▼              ▼
                        ┌──────────────────────────────────────────────┐
                        │ db.Database (pooled, advisory-locked DDL)    │
                        │                                              │
                        │  research_notes (old)      <to> table (new)  │
                        │  vector(1024) ────copy────► vector(1024)     │
                        │       │        INSERT..SELECT (server-side)  │
                        │       └────────re-embed───► vector(N)        │
                        │                (via Python + Voyage)         │
                        └──────────┬───────────────────────────────────┘
                                   │
                        ┌──────────▼───────────────────────────────────┐
                        │ Golden recall harness (shared module)        │
                        │  exact-scan queries (enable_indexscan=off)   │
                        │  old-table results  ==  new-table results ?  │
                        │  copy: zero delta │ re-embed: delta = model  │
                        └──────────────────────────────────────────────┘

 Cutover (separate, human act):  fly secrets/env  PGVECTOR_TABLE=<new>
                                 [+ VECTOR_DIMENSIONS=<N> if re-embed]
                                 → deploy restart → memory.py reads at import
 Rollback: point the env back. Old table is never dropped by any command.
```

### Recommended placement

```
src/research_agent/
├── migrate.py          # repaired + two new subcommands (one CLI surface)
├── memory.py           # VoyageEmbedder gains optional output_dimension (seam-preserving)
├── usage.py            # untouched (Claude); VOYAGE_PRICES lives beside PRICES or in migrate.py — see Open Q2
└── recall_golden.py    # golden set data + harness (importable by CLI and tests)
tests/
├── test_migrate.py     # NEW: repair gates + copy fidelity + re-embed + preview arithmetic
└── test_store_contract.py  # untouched; harness may reuse FakeEmbedder from test_memory_stores
docs/adr/
└── 0008-embedding-migration-two-commands.md  # NEW
```

### Pattern 1: Server-side copy — the only byte-identical move

**What:** the copy-only command never materialises a vector in Python.

```sql
-- target table created first via PgVectorMemoryStore(table=new, dimensions=1024)
-- so DDL goes through the advisory-locked ensure_schema path, then:
INSERT INTO {new} (text, embedding, owner, created_at)
SELECT text, embedding, owner, created_at FROM {old}
ON CONFLICT DO NOTHING;   -- re-runnable; ids are fresh BIGSERIAL in the target
```

**Why:** `embedding` copies as a pgvector value inside the server — bit-for-bit. Any
client-side path (fetch → parse floats → `_literal()` → insert) introduces a
float-formatting boundary that must then be *proven* lossless instead of being lossless by
construction. `repr(float)` does round-trip exactly in Python 3, but "provably nothing
happened" beats "provably reversible transformation happened." [VERIFIED: code reading of
`_literal`; server-side copy semantics are standard Postgres]

Note: `id` is `BIGSERIAL PRIMARY KEY` and deliberately not copied (the target assigns its
own). The fidelity join therefore keys on `(text, owner, created_at)` — unique in practice
for this corpus, and the same key the re-runnability skip should use.

### Pattern 2: What "recall byte-identical" means, concretely (SC-5's copy half)

Three assertions, strongest first, each meaning something different:

1. **Row-count equality:** `SELECT count(*) FROM old` = `... FROM new`.
2. **Vector byte equality:**
   ```sql
   SELECT count(*) FROM {old} o
   JOIN {new} n USING (text, owner, created_at)
   WHERE o.embedding::text IS DISTINCT FROM n.embedding::text;
   -- must be 0; joined-row count must equal the table count (no unmatched rows)
   ```
3. **Golden-query equality under exact scan:** for every golden query, run the production
   `SELECT` shape against both tables inside a transaction with
   `SET LOCAL enable_indexscan = off` (pgvector's documented exact-search switch
   [CITED: github.com/pgvector/pgvector README]) and assert the *ordered* result lists are
   identical, including scores.

**Why the index must be excluded from the claim — the ANN question, answered:** HNSW in
pgvector is approximate: it "can miss results by design" and `hnsw.ef_search` defaults
to 40 [CITED: pgvector README]. The index build is parallelised and level assignment is
randomized, so two builds over identical vectors are not guaranteed to produce identical
graphs [ASSUMED — the README does not state build determinism either way; treat
non-determinism as the safe assumption]. Therefore an HNSW rebuild **could in principle**
reorder near-ties or drop a true neighbour at scale, and the byte-identical claim must be
made where it is actually true: on the vectors (assertion 2) and on exact-scan query
results (assertion 3), where identical bytes mathematically force identical distances and
identical ordering — with one caveat: **exact ties**. The production query orders by
`embedding <=> q` with no tiebreak, so two rows at the same distance order arbitrarily.
Do not change the production SQL (scope fence). Instead, the golden set is *constructed*
tie-free: the harness asserts, as part of its own self-check, that no golden query has two
stored notes at equal distance. Tie-freedom makes ordering deterministic without touching
recall semantics.

4. **Index sanity (separate, honest, weaker):** the *indexed* production query over the
   new table returns the same result **set** as the exact scan. At this corpus size (tens
   of rows, far below ef_search=40) the HNSW search effectively explores everything and
   set-equality is expected; state it as set-equality at this scale, never as a general
   ANN guarantee.

### Pattern 3: The re-embed path

```python
# Batched through the seam. VoyageEmbedder gains one optional field:
class VoyageEmbedder:
    def __init__(self, model: str = EMBEDDING_MODEL, output_dimension: int | None = None):
        ...
    def embed_documents(self, texts):
        return self.client.embed(list(texts), model=self.model,
                                 input_type="document",
                                 output_dimension=self.output_dimension).embeddings
```

- `voyageai 0.5.0`'s `Client.embed` accepts `output_dimension` [VERIFIED: signature
  inspected in project venv]. voyage-3.5 supports 1024 (default), 256, 512, 2048
  [CITED: docs.voyageai.com/docs/embeddings].
- Flow: read `(text, owner, created_at)` from old table → batch (propose 128 texts;
  limits are 1,000 texts and 320K tokens per request for voyage-3.5
  [CITED: docs.voyageai.com/docs/embeddings]) → `embed_documents` → dimension-check every
  vector against the target width via the store's existing `_check_dimensions` (do NOT
  reimplement it — SC-4 requires the same check, not a copy of it) → insert with
  `owner, created_at` preserved.
- Resume-on-interrupt: skip rows whose `(text, owner, created_at)` already exist in the
  target — the same idiom the legacy tool uses. The corpus is tiny; nothing fancier.
- Preserving `created_at` matters twice: the TTL must not restart, and it is the fidelity
  join key.

### Pattern 4: `VOYAGE_PRICES`, imitating `usage.py`

Reuse `PriceWindow` exactly (it is model-agnostic); the price itself is one flat USD/Mtok
float, not usage.py's four-class `Price`:

```python
# USD per million tokens. Voyage bills the text embedding endpoint on tokens
# in the documents/queries. Verified 2026-08-06 against
# https://docs.voyageai.com/docs/pricing — Voyage publishes no dated windows,
# so each rate opens an unbounded window from verification; a future change
# closes it with `until=` the way the Sonnet 5 boundary is recorded.
VOYAGE_PRICES: dict[str, list[PriceWindow-like]] = {
    "voyage-3.5":      [(0.06, since=None)],
    "voyage-3.5-lite": [(0.02, since=None)],
    "voyage-3-large":  [(0.18, since=None)],
    # voyage-4 family exists ($0.12/$0.06/$0.02 large/std/lite) — add rows only
    # if the demo actually offers those targets; an absent row fails loud.
}
```

An unlisted model or uncovered date raises (the `UnknownModelPricing` idiom) and the
re-embed command **refuses to run** — DEC-12's `pricing_unknown` fails loud, never zero.
Verified rates [CITED: docs.voyageai.com/docs/pricing, fetched 2026-08-06]:
voyage-3.5 $0.06/Mtok, voyage-3.5-lite $0.02, voyage-3-large $0.18, voyage-3 $0.06,
voyage-3-lite $0.02; voyage-4-large/voyage-4/voyage-4-lite $0.12/$0.06/$0.02 with a 200M
free-token allowance on the 4-family (older models have no free tier). Billing unit is
**tokens**, not characters. The preview should mention the free-tier caveat honestly
("list price; the 4-family has a 200M-token free allowance") rather than model it.

**Token counting for the preview:** `voyageai.Client.count_tokens(texts, model=...)` —
local, exact, sums `tokenize()` lengths using the model's HF tokenizer
(`Tokenizer.from_pretrained(f"voyageai/{model}")`) [VERIFIED: source inspected in venv;
CITED: docs.voyageai.com/docs/tokenization]. Two operational facts: it needs the
`tokenizers` package (already installed) and the **first call fetches tokenizer files from
the Hugging Face hub** (then caches). The preview therefore needs network on first use but
never spends Voyage tokens. The post-run reconciliation number is the embed responses'
summed `total_tokens` (verified field on `EmbeddingsObject`); printing predicted-vs-actual
closes the loop cheaply.

**Phase 14 boundary (proposal):** preview-only here. Wiring Voyage spend into `/metrics`
touches `RunRecord`, both metrics backends, and the summary shape — Phase 14's territory
(`inference_geo`, discounts) where the accounting model is already being reopened.
CONTEXT's deferred list points the same way. The ADR and README should name the gap.

### Pattern 5: Cutover — the boring answer

The switch **already exists**: `PGVECTOR_TABLE` (memory.py line 58) and
`VECTOR_DIMENSIONS` (line 59), both env-driven, read at import, applied by process
restart. Cutover is `fly secrets set PGVECTOR_TABLE=research_notes_v2`
(+ `VECTOR_DIMENSIONS=N` for a re-embed) and a deploy/restart. Rollback is pointing back.
Do not invent `VECTOR_STORE_TABLE`; the CONTEXT's "or equivalent" is satisfied by the var
that already exists and is already documented in OPERATIONS.md.

- **Dual-table state:** both tables exist; config points at exactly one; no command ever
  drops the old table. Deleting it is a documented manual operator step after confirmation.
- **Writes during migration:** propose *quiesce–migrate–flip*, stated plainly. Justification
  the docs can print: the corpus is ≤7 days of notes by construction (Phase 12 TTL); any
  note written mid-migration and missed would expire within a week anyway; dual-write
  machinery for a self-erasing corpus is engineering theatre. The honest-scale note in
  CONTEXT explicitly asks for this framing.
- Table-name validation: the target name must pass the same
  `table.replace("_","").isalnum()` rule — reuse the store's constructor (which enforces
  it) rather than duplicating the check.

### Pattern 6: ADR-0008

Per `docs/adr/README.md`: `0008-<slug>.md`, title line `# ADR-0008 — ...`, `**Status:**`,
provenance, then `## Context / ## Decision / ## Consequences`. One convention wrinkle the
plan must get right: **DEC-10 was never promoted to an ADR**, so there is no record for
ADR-0008 to supersede and the `Status: Accepted — supersedes ADR-000M` form does not
apply. Use `**Status:** Accepted` with `**Source:**` naming
`.planning/intel/decisions.md` DEC-10 (the README's documented form for non-DESIGN.md
records, per the ADR-0006/0007 precedent), and record the supersession of DEC-10 in prose:

- **What survives of DEC-10:** the copy-only command *is* DEC-10's operation, preserved
  verbatim (same vectors, free, exact); its *reason* ("two suspects") survives as the
  design rule that the two variables are never changed in one command, now measured by the
  golden set rather than enforced by prohibition.
- **What is new:** a re-embed path exists at all, made safe by the isolation discipline —
  golden set before/after, copy-only proving the infrastructure half, delta attributable
  to the model by construction.
- Update the index table in `docs/adr/README.md` (new row, Status Accepted, Superseded
  by —). Consider a one-line annotation on DEC-10 in decisions.md pointing at ADR-0008,
  mirroring how the file already cross-references.

### Anti-Patterns to Avoid

- **Asserting recall equality through the HNSW index** — the claim silently becomes "the
  ANN approximation agreed twice," which a rebuild can falsify at scale. Exact scan or
  nothing.
- **Client-side vector copy** — introduces a float-formatting boundary the proof must then
  cover.
- **Reimplementing the dimension check in the CLI** — SC-4 says the *existing* loud check
  must not become a coercion; the way to guarantee that is to route inserts through the
  store's check, and to add the mutation test that a wrong-width vector still raises.
- **`ALTER TABLE ... ALTER COLUMN embedding TYPE vector(N)`** — an in-place dimension
  change is precisely the "new setting instead of new table" the check's error message
  forbids.
- **A second migration module** — CONTEXT forbids forking the idiom.
- **Costing an unknown Voyage model at zero** — DEC-12.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting for the preview | chars/4 or word-count heuristics | `voyageai.Client.count_tokens(texts, model=...)` | Exact, local, uses the model's real tokenizer; verified in pinned 0.5.0 |
| Exact recall comparison | A Python cosine re-scorer over fetched vectors | `SET LOCAL enable_indexscan = off` + the production SQL | The store's own SQL is the semantics under test; a parallel scorer can agree while production disagrees |
| Vector serialization for copy | Fetch/format/reinsert via `_literal` | Server-side `INSERT..SELECT` | Byte-identical by construction |
| Effective-dated pricing | A new windowing mechanism | `usage.py`'s `PriceWindow` (reuse the class) | Already tested across the Sonnet 5 boundary; one windowing idiom |
| Target-table DDL | Hand-written `CREATE TABLE` in the CLI | `PgVectorMemoryStore(table=..., dimensions=...)` construction | Reuses advisory-locked `ensure_schema`, table-name validation, and keeps one schema definition |
| Concurrency around DDL | New locking | `db.Database` advisory-lock path | Phase 11 already proved it (two-connection exclusivity test) |

**Key insight:** almost every mechanism this phase needs already exists and is already
tested; the phase's craft is *routing through* those mechanisms so the existing proofs
carry over, rather than building parallel ones that must be proven from scratch.

## Runtime State Inventory

This is a migration phase; the checklist applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Supabase pgvector table `research_notes` (vector(1024), owner, created_at, HNSW + owner indexes); rows ≤7 days old by TTL. Local :54329 Postgres holds test tables (`contract_test_notes` etc.) | The phase's subject. No destructive action; new tables created beside it. Contract-test tables must not collide with migration-test tables — use distinct names |
| Live service config | Fly env/secrets: `DATABASE_URL`, `VOYAGE_API_KEY`, pinned `VECTOR_STORE=pgvector`; `PGVECTOR_TABLE`/`VECTOR_DIMENSIONS` currently *unset* (defaults active) | Cutover act = setting them. No change until the (out-of-scope) production flip; docs describe the procedure |
| OS-registered state | None — service is Fly machines from a Docker image; no schedulers/plists reference table names | None — verified by reading fly.toml/Dockerfile/CI |
| Secrets/env vars | `VOYAGE_API_KEY` (unchanged); no secret embeds a table name | None |
| Build artifacts | None affected — no rename; Docker image contents unchanged by config-only cutover | None |
| Third-party caches | HF tokenizer cache (`~/.cache/huggingface`) created on first `count_tokens` — on the *operator's* machine, since migration runs as a CLI, not in the service | None; note the first-use network fetch in docs |

## Common Pitfalls

### Pitfall 1: Trusting the HNSW index inside the byte-identical claim
**What goes wrong:** the copy gate passes/fails depending on ANN traversal order, not on
the data. **Why:** HNSW is approximate (misses possible, ef_search=40 default) and rebuild
determinism is not guaranteed. **How to avoid:** exact-scan comparison (Pattern 2); index
agreement asserted separately as set-equality at this corpus size. **Warning signs:** a
recall test that flakes between CI runs on identical data.

### Pitfall 2: The migration silently orphans notes (owner) or resurrects them (created_at)
**What goes wrong:** default column values fill in `owner=''` and `created_at=now()`;
every migrated note belongs to nobody and gets seven fresh days. This is *already true* of
`migrate_notes` today. **How to avoid:** carry both columns explicitly in every copy and
re-embed insert; golden set includes owner-scoped queries (the gate that catches it).
**Mutation for the gate:** drop `owner` from the copy column list → owner-scoped golden
queries must go red.

### Pitfall 3: 2048-dimension target cannot be HNSW-indexed
**What goes wrong:** voyage-3.5 offers `output_dimension=2048`, but pgvector's HNSW index
supports the `vector` type only up to **2,000 dimensions** (`halfvec` reaches 4,000)
[CITED: pgvector README]. `_ensure_schema`'s `CREATE INDEX ... USING hnsw` fails, and
depending on error tolerance the table could end up unindexed. **How to avoid:** the
re-embed command validates the requested dimension ≤ 2000 and refuses loudly, naming
`halfvec` as the documented-but-unbuilt path. Boring answer: supported targets are
256/512/1024.

### Pitfall 4: The dimension check quietly bypassed
**What goes wrong:** the re-embed path inserts via its own SQL and never calls
`_check_dimensions`; SC-4 is then satisfied in the store but not in the tool that most
needs it. **How to avoid:** run every batch's vectors through the store's check (or insert
via the store); add the mutation test — feed a wrong-width vector, assert the existing
`ValueError` message fires, in the migration path specifically.

### Pitfall 5: Import-time constants make migrate.py untestable-looking
**What goes wrong:** tests monkeypatch `VECTOR_DIMENSIONS`/`PGVECTOR_TABLE` env after
import and see no effect; someone "fixes" it with `importlib.reload`, which re-executes
module DDL and confuses pool claims. **How to avoid:** thread explicit parameters through
the new subcommand functions (`--from/--to/--dimensions` CLI args), so tests pass values
instead of patching module state. The legacy path already does this for the three source
paths.

### Pitfall 6: Golden set with score ties
**What goes wrong:** production `ORDER BY embedding <=> q` has no tiebreak; ordered
comparison flakes. **How to avoid:** harness self-check asserts tie-freedom
(Pattern 2). With the FakeEmbedder's 5-dim binary bag-of-words vectors ties are *easy* to
create accidentally (two notes with the same vocab-word set embed identically) — the
self-check is not optional.

### Pitfall 7: Contract suite and migration tests sharing tables
**What goes wrong:** `test_store_contract.py` TRUNCATEs `contract_test_notes` per case;
migration tests using the same names race in CI. **How to avoid:** dedicated
`migration_test_notes_old/_new` names, dropped/created per test.

### Pitfall 8: The preview needs network for a "local" count
**What goes wrong:** first `count_tokens` call fetches the tokenizer from the HF hub; in
an offline/gated CI job it errors and looks like a bug. **How to avoid:** unit tests of
preview *arithmetic* take a token count as input (pure function: tokens × price → USD);
tokenizer-touching tests are live/gated only.

## Code Examples

### Cost preview (pure arithmetic, unit-testable)
```python
# Source: usage.py idiom + docs.voyageai.com/docs/pricing (verified 2026-08-06)
def preview_cost_usd(total_tokens: int, model: str, on: date | None = None) -> float:
    return total_tokens * voyage_price_for(model, on) / 1_000_000
# voyage_price_for raises UnknownModelPricing for an unlisted model/date — the
# command prints the error and exits nonzero; it never proceeds at $0.00.
```

### Exact-scan golden comparison (the SC-5 measurement)
```python
# Source: pgvector README (SET LOCAL enable_indexscan = off inside a transaction)
def golden_results(database: db.Database, table: str, qvec: list[float],
                   owner: str, top_k: int, floor: float) -> list[tuple[str, float]]:
    lit = PgVectorMemoryStore._literal(qvec)
    with database.transaction() as cur:      # transaction() exists since Phase 11
        cur.execute("SET LOCAL enable_indexscan = off")
        cur.execute(
            f"""SELECT text, 1 - (embedding <=> %s::vector) AS similarity
                FROM {table}
                WHERE 1 - (embedding <=> %s::vector) >= %s AND owner = %s
                ORDER BY embedding <=> %s::vector LIMIT %s""",
            (lit, lit, floor, owner, lit, top_k))
        return [(r[0], r[1]) for r in cur.fetchall()]
# NOTE: mirrors memory.py's production SELECT minus the TTL predicate — golden
# rows are freshly inserted so TTL is vacuous; keeping the WHERE shape otherwise
# identical is what makes this a measurement of production semantics.
```

### Copy fidelity gate
```python
counts_match = old_count == new_count
unmatched = fetchone(f"""
    SELECT count(*) AS n FROM {old} o
    LEFT JOIN {new} n2 USING (text, owner, created_at)
    WHERE n2.text IS NULL""")["n"] == 0
byte_diff = fetchone(f"""
    SELECT count(*) AS n FROM {old} o
    JOIN {new} n2 USING (text, owner, created_at)
    WHERE o.embedding::text IS DISTINCT FROM n2.embedding::text""")["n"] == 0
```

### Token counting (live path, exercised once)
```python
# Source: docs.voyageai.com/docs/tokenization + voyageai 0.5.0 source (verified)
client = voyageai.Client()                    # reads VOYAGE_API_KEY (tokenize itself is local)
tokens = client.count_tokens(texts, model="voyage-3.5-lite")
# post-run reconciliation: sum of EmbeddingsObject.total_tokens across batches
```

## Golden Recall Set (proposal — Claude's discretion area)

- **Location:** `src/research_agent/recall_golden.py` — data (a module-level list of
  frozen dicts) plus the harness functions. Production-importable so the migration
  subcommands can run the measurement; tests import the same module. No duplication.
- **Size/content:** ~12 notes over the FakeEmbedder vocabulary
  (`langgraph, chroma, retry, voyage, supervisor`) across three owners
  (`alice`, `bob`, `""`), with per-owner distinct vocab combinations so no two notes under
  one owner embed identically (tie-freedom); ~8 queries: per-owner relevance-ordering
  queries, an owner-isolation query (identical text, different owners — the Phase 12
  scoping gate re-run across migration), a below-floor query, and an empty-owner query.
  Expected results stored as ordered lists per query.
- **Fake vs live:** the fake embedder (5-dim, deterministic) is sufficient for every CI
  assertion — the harness measures *store/migration* behaviour, not embedding quality,
  exactly the argument `test_memory_stores.py`'s docstring already makes. The real Voyage
  path is exercised once, live, against a scratch table on the prod-shaped Supabase:
  re-embed the golden texts with `voyage-3.5-lite` (cheapest real model, $0.02/Mtok;
  golden corpus is a few hundred tokens ≈ $0.00001) and record the observed delta as the
  demonstrable artifact. The copy-only live run must show zero delta.
- **Backend-agnostic where free:** the golden data and the expected-results comparison are
  store-agnostic (they speak `add/query`); the exact-scan verification is pgvector-only by
  nature and lives in a pg-specific function.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DEC-10: migration copies embeddings, re-embedding forbidden (confounds variables) | Two commands: copy-only (DEC-10 preserved) + re-embed (new), delta attributed via golden set | This phase (ADR-0008) | The prohibition becomes a measurement discipline |
| `migrate.py` pre-Phase-12: `(text, embedding)` is a whole note | Notes are `(text, embedding, owner, created_at)`; `''` owner = nobody; TTL live | Phase 12 | migrate.py is semantically stale; repair required before "proven" |
| Single locked connection | Pooled `Database`, `transaction()`, advisory-locked DDL | Phase 11 | Migration tooling gets `transaction()` (needed for `SET LOCAL`) for free |
| voyage-3 family | voyage-3.5 deployed (`VOYAGE_EMBEDDING_MODEL` default `voyage-3.5`); voyage-4 family now published ($0.12/$0.06/$0.02) | verified 2026-08-06 | Price table rows for what the demo offers; 3.5-lite is the natural cheap re-embed target |

**Deprecated/outdated:** README's limitation "Changing embedding model means a new
pgvector table" — after this phase it's true-with-a-path; rewrite honestly (per-phase
README deliverable).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HNSW index build in pgvector is not deterministic across rebuilds | Pattern 2 | Low — the design already excludes the index from the correctness claim; if builds were deterministic the design is merely conservative |
| A2 | Voyage publishes no effective-dated price windows; open-ended windows from verification date are the right encoding | Pattern 4 | Low — a future price change closes the window; the `pricing_unknown` fail-loud covers a gap |
| A3 | `(text, owner, created_at)` is a unique key in practice for the notes corpus | Patterns 1–2 | Duplicate rows would make the fidelity join ambiguous; the copy gate should also assert join-row-count == table count, which catches it |
| A4 | Supabase's pgvector version supports `SET LOCAL enable_indexscan = off` exact scan (standard Postgres planner GUC, not version-gated) | Pattern 2 | Very low — it is a core Postgres setting; the live run would surface it immediately |
| A5 | Quiesce-migrate-flip is acceptable for the demo (no dual-write) | Pattern 5 | Product-taste call flagged for plan review; CONTEXT's honest-scale note supports it |

## Open Questions (RESOLVED)

All three were adopted as recommended — see 13-CONTEXT.md § "Post-research calls
(2026-08-06)". Q1 → `VOYAGE_PRICES` lives in `usage.py`. Q2 → the live demonstration runs
against Supabase scratch tables, cleaned up after. Q3 → preview always prints; `--yes`
required to spend; `--dry-run` stops after the preview.

1. **Where does `VOYAGE_PRICES` live — `usage.py` or `migrate.py`?**
   - Known: `PriceWindow` is reusable; Phase 14 will touch `usage.py` heavily.
   - Recommendation: put the table and `voyage_price_for()` in `usage.py` next to
     `PRICES` (one pricing home, Phase 14 finds it where it expects), imported by the CLI.
     Planner may flip if it prefers keeping usage.py untouched this phase; either is
     defensible.
2. **Does the live re-embed demonstration run against Supabase or only local?**
   - Known: CONTEXT wants the real Voyage path proven live once; the scratch table on
     Supabase costs nothing and proves the prod-shaped path (pooler, search_path).
   - Recommendation: live run against Supabase scratch tables, cleaned up after; recorded
     in the phase's verification notes.
3. **Should `--dry-run` on `embeddings re-embed` be the same flag as the cost preview?**
   - Recommendation: preview always prints; `--dry-run` stops after preview + plan;
     without `--yes`, an interactive confirm (or refusal when non-TTY). Keeps SC-2's
     "refuses to proceed" unambiguous in scripts.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Local Postgres + pgvector :54329 | Postgres-gated tests | ✓ (probed 2026-08-06, accepting connections) | PG17 (per CONTEXT) | CI's pgvector image |
| voyageai + tokenizers in venv | re-embed, count_tokens | ✓ | 0.5.0 / 0.23.1 | — |
| pytest | all tests | ✓ | 9.1.1 | — |
| VOYAGE_API_KEY | live re-embed run only | not probed (secret) | — | live step is a checkpoint; CI uses fake embedder |
| Supabase DATABASE_URL | live verification | not probed (secret) | — | local :54329 for everything except the one live run |
| HF hub reachability | first `count_tokens` | assumed on operator machine | — | preview-arithmetic tests take counts as input |

**Missing dependencies with no fallback:** none identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 |
| Config file | pyproject.toml (existing suite conventions) |
| Quick run command | `DATABASE_URL=postgresql://postgres:<pw>@localhost:54329/postgres .venv/bin/pytest tests/test_migrate.py -x -q` |
| Full suite command | `DATABASE_URL=... REQUIRE_POSTGRES=1 .venv/bin/pytest -q` (armed baseline 573/1; plain 527/47) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-emm / SC-1 | Re-embed produces a new table at a new dimension with owner/created_at preserved | integration (real PG, fake embedder at a second fake dimension) | `pytest tests/test_migrate.py -k re_embed -x` | ❌ Wave 0 |
| REQ-emm / SC-2 | Preview arithmetic: tokens × price, unknown model refuses | unit | `pytest tests/test_migrate.py -k preview -x` | ❌ Wave 0 |
| REQ-emm / SC-3 | Old table survives; both commands are non-destructive; re-run is idempotent | integration | `pytest tests/test_migrate.py -k cutover or idempotent -x` | ❌ Wave 0 |
| REQ-emm / SC-4 | Wrong-width vector in the migration path raises the existing loud ValueError | integration | `pytest tests/test_migrate.py -k dimension -x` | ❌ Wave 0 |
| REQ-emm / SC-5 | Copy: zero golden delta (byte + exact-scan); re-embed: delta attributed | integration | `pytest tests/test_migrate.py -k golden -x` | ❌ Wave 0 |
| REQ-emm (repair) | Legacy migrate carries owner/created_at; owner-aware dedup | integration | `pytest tests/test_migrate.py -k legacy -x` | ❌ Wave 0 |
| REQ-emm (live) | Real Voyage re-embed once against Supabase; copy path zero-delta live | manual-only (spends tokens, needs secrets) — checkpoint:human-verify | — | — |

### Sampling Rate
- **Per task commit:** the quick run above.
- **Per wave merge:** full suite with `REQUIRE_POSTGRES=1` against :54329.
- **Phase gate:** full suite green (armed baseline maintained or improved) before
  `/gsd:verify-work`; live demonstration recorded.

### Gate mutation plans (the thirteen-vacuous-gates discipline — every gate falsified)
| Gate | Mutation that must turn it red |
|------|-------------------------------|
| Copy byte-fidelity | After copy, `UPDATE new SET embedding = <one component perturbed> WHERE id = (pick one)` → byte join and exact-scan golden both red |
| Owner preservation | Remove `owner` from the copy/insert column list → owner-scoped golden query red |
| created_at preservation | Let target default `now()` → fidelity join finds unmatched rows, red |
| Exact-scan golden equality | Delete one row from the new table → ordered comparison red |
| Tie-freedom self-check | Add two same-vocab notes under one owner → harness self-check red |
| Cost preview | Change the voyage-3.5 rate constant → asserted USD red; delete a model row → command refuses (assert exit ≠ 0, message names the model) |
| Dimension check in migration path | Feed a (dims±1) vector through the re-embed insert → existing ValueError message asserted |
| Non-destructive guarantee | Grep-level is vacuous; instead assert old-table count unchanged after both commands AND after a `--dry-run` |
| Idempotent re-run | Run copy twice → counts equal, no duplicates (mutate: drop the skip clause → red) |

### Wave 0 Gaps
- [ ] `tests/test_migrate.py` — all rows above
- [ ] `src/research_agent/recall_golden.py` — golden data + harness (self-check included)
- [ ] Framework install: none needed

## Project Constraints (from CLAUDE.md)

No `./CLAUDE.md` exists in the repository (verified). User memory constraints that bind
this phase: no throwaway commits on main (work happens on the stacked branch, one PR);
demonstrable beats working — the live copy-zero-delta / re-embed-measured-delta run is the
portfolio artifact and should be written up as such.

## Sources

### Primary (HIGH confidence)
- Project tree read in full: `src/research_agent/migrate.py`, `memory.py`, `usage.py`,
  `db.py`, `sessions.py` (excerpts), `tests/test_store_contract.py`,
  `tests/test_memory_stores.py`, `docs/adr/README.md`, `.planning/ROADMAP.md` §13,
  `.planning/REQUIREMENTS.md`, `.planning/intel/decisions.md` (DEC-10, DEC-12),
  `13-CONTEXT.md`, `.github/workflows/ci.yml`
- Installed-package inspection (project venv): voyageai 0.5.0 `Client.embed`
  (`output_dimension` param), `count_tokens`/`tokenize` source, `EmbeddingsObject.total_tokens`;
  tokenizers 0.23.1 present
- https://docs.voyageai.com/docs/pricing (fetched 2026-08-06) — all model rates, token
  billing unit, free-tier allowances
- https://docs.voyageai.com/docs/embeddings — voyage-3.5 dimensions (1024 default;
  256/512/2048), batch limits (1,000 texts; 320K tokens for 3.5/3.5-lite)
- https://docs.voyageai.com/docs/tokenization — local counting methods, HF-hosted tokenizers
- https://github.com/pgvector/pgvector README — HNSW dim limits (vector ≤2,000;
  halfvec ≤4,000), exact search via `SET LOCAL enable_indexscan = off`, ANN can miss
  results, `hnsw.ef_search` default 40
- Live probe: `pg_isready localhost:54329` accepting connections (2026-08-06)

### Secondary (MEDIUM confidence)
- WebSearch corroboration of voyage-3.5/3.5-lite rates (litellm docs, cloudprice.net) —
  agrees with the primary source

### Tertiary (LOW confidence)
- HNSW build non-determinism (A1) — training knowledge; README silent; design is robust
  to either answer

## Metadata

**Confidence breakdown:**
- migrate.py forensics: HIGH — full file read against current tree
- Voyage pricing & tokenization: HIGH — provider docs fetched this session + installed-source inspection
- Copy-fidelity / exact-scan design: HIGH for the mechanism (pgvector-documented), MEDIUM
  for A3 (join-key uniqueness — mitigated by the extra join-count assertion)
- Cutover mechanics: HIGH — the env vars exist in code and OPERATIONS.md today
- ADR convention: HIGH — README read; the no-record-to-supersede wrinkle resolved by the
  ADR-0006/0007 `Source:` precedent

**Research date:** 2026-08-06
**Valid until:** ~2026-09-05 for code claims (or first merge touching memory.py/migrate.py);
Voyage prices re-verify at plan execution — the table's whole design assumes they drift.
