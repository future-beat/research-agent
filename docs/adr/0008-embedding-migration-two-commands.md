# ADR-0008 — Embedding migration is two commands: copy-only preserved, re-embed measured

**Status:** Accepted
**Source:** Phase 13 (2026-08-06), `REQ-embedding-model-migration`; reverses the scope of
`DEC-10` in [`.planning/intel/decisions.md`](../../.planning/intel/decisions.md)

## Context

**DEC-10 said migration copies embeddings rather than re-embedding them.** The stated
rationale was that copying is free and exact. The real one was written down alongside it and
is the part that matters: re-embedding during a migration would change recall behaviour at
the same moment the infrastructure changed, leaving *two suspects and no way to separate
them*. A recall regression after such a move is unattributable — the table changed, the
vectors changed, and nothing distinguishes a worse model from a botched copy.

That rule was a prohibition, and it worked as long as nobody needed a new embedding model.
`REQ-embedding-model-migration` is exactly that need. The column width of a pgvector table is
fixed at creation, so a model that emits a different number of dimensions cannot move into an
existing table at all; `PgVectorMemoryStore._check_dimensions` says so loudly and then, before
this phase, could do nothing about it. The README recorded that as a limitation: *the
dimension check fails loudly but can't migrate for you.*

Building a re-embed path re-opens precisely the ambiguity DEC-10 closed. The question this
record answers is therefore not "may we re-embed" but **how a re-embed can exist without
throwing away the reason DEC-10 existed.**

**Honest scale note.** Since Phase 12, notes expire seven days after they are written. The
live corpus is small and self-cleaning, and no realistic operation here is rescuing a large
one. What this phase is worth is the *demonstrable path* — the tooling, the cost preview, the
isolation discipline, and the fact that a model change is now a decision rather than a
migration project. Any framing that implies large-corpus rescue would be overselling it, and
the operator docs say so in the same words.

## Decision

**Migration is two commands, never one.** `python -m research_agent.migrate embeddings copy`
and `python -m research_agent.migrate embeddings re-embed` are siblings under the one
migration surface, and each changes exactly one variable.

### What survives of DEC-10

**The copy-only command *is* DEC-10's operation, preserved verbatim.** Same vectors, free,
exact — a single server-side `INSERT .. SELECT` that carries `text`, `embedding`, `owner` and
`created_at` and never materialises a vector in Python. Nothing about DEC-10's guarantee was
weakened to make room for the second command; it was given a name and a test.

**Its rationale survives too, as a design rule rather than a prohibition.** The two variables
— which table the corpus lives in, and which model produced its vectors — are still never
changed in one command. What changed is the enforcement mechanism: DEC-10 enforced it by
forbidding the second operation, and this record enforces it by *measuring* both. A frozen,
tie-free golden recall set of twelve notes and eight owner-scoped queries runs against the
old table and the new one. The copy-only path must show **zero** delta, which is what makes
the re-embed path's delta attributable to the model by construction. Two operations, two
measurements, one variable each.

**Tenancy and the clock travel with the notes.** Both commands carry `owner` and `created_at`,
so no migrated note arrives belonging to nobody or with its seven-day TTL restarted. This is
not a new principle, but the legacy migration tool had silently violated it since Phase 12 and
was repaired in this phase before either new command was written.

### What is new

**A re-embed path exists at all**, and it is made safe by construction rather than by
prohibition:

- The golden set is measured before and after.
- The copy-only command proves the infrastructure half separately, so a delta observed across
  a re-embed is the model's.
- The cost is previewed on every invocation and `--yes` is required to spend. An unpriced
  model refuses rather than quoting `$0.00` (DEC-12), and a requested width above 2000 refuses
  because pgvector's HNSW index cannot take it.
- Every vector produced by the new model goes through the target store's own
  `_check_dimensions` on the way in — the production check, called on the store instance, not
  a second width comparison living in the CLI.

### What "byte-identical recall" means, exactly

Recorded here because the phrase is easy to overclaim and the overclaim would poison this
record. The claim decomposes into three parts, and the third is **not** part of it:

1. **The vectors are the same bytes** — a SQL join on `(text, owner, created_at)` asserting
   `embedding::text IS DISTINCT FROM` finds nothing, with the join count equal to the source
   row count so a duplicate key cannot fan the comparison out over the wrong row set.
2. **The golden queries agree, under exact scan** — `SET LOCAL enable_indexscan = off` inside
   one transaction, pgvector's documented exact search, compared ordered and score-bearing.
3. **The HNSW index is deliberately outside the claim.** HNSW is approximate by design;
   pgvector's own README says it can miss results, `hnsw.ef_search` defaults to 40, and index
   builds are not guaranteed to produce identical graphs over identical vectors. An
   equality-of-recall assertion made through the index asserts only that an approximation
   agreed with itself twice, which a rebuild can falsify without a byte of data changing.
   Index agreement is checked separately, as **set** equality, labelled scale-bounded, and it
   must never be promoted into the recall claim.

### Writes during a migration: quiesce–migrate–flip

The corpus is at most seven days of notes by construction. A note written during a migration
and missed by it expires within a week on its own. Dual-write machinery for a self-erasing
corpus is engineering theatre, so it is deliberately not built: the operator quiesces the
service, migrates, verifies, and flips. This is a real accepted risk stated plainly rather
than a gap left to be discovered.

### Cutover is the config flip that already existed

No new switch was invented. `PGVECTOR_TABLE` and `VECTOR_DIMENSIONS` are read at import in
`memory.py` and feed `PgVectorMemoryStore`'s constructor defaults, so cutover is
`fly secrets set PGVECTOR_TABLE=<new>` (plus `VECTOR_DIMENSIONS=<N>` after a re-embed) and a
restart. **Rollback is pointing them back**, which works because both tables coexist and
**no command in this tooling ever drops the old one.** Deleting it is a manual operator act
after confirmation. A test flips a store forward to the migrated table and back to the
original, asserting the same golden answers both times and re-comparing the old table's full
contents — embeddings included — after every step.

## Consequences

### Accepted

- **Voyage spend has a priced preview but still no accounting.** `usage.VOYAGE_PRICES` gives
  the preview an effective-dated, verified rate in the same file Claude's prices live in, and
  the command prints predicted-versus-billed tokens after a run. None of that reaches
  `/metrics`, which still tracks only Claude spend. That is a named gap for Phase 14, not an
  oversight; the preview is an estimate at list price, and the README says so.
- **The production model flip remains an operator decision.** This phase builds and proves the
  path and deliberately does not take it. Nothing here changes what the live service embeds
  with.
- **A target above 2000 dimensions is refused.** voyage-3.5 offers `output_dimension=2048`,
  which pgvector's HNSW index cannot build over the `vector` type. The refusal names
  `halfvec` as the documented path and states that it is unbuilt here, so the message points
  at the work rather than at a wall.
- **The re-embed command's own recall delta is measured by the operator, not asserted by the
  test suite.** A new model re-scores everything, so the golden set's tie-freedom does not
  travel across a model change and must be re-established against the re-embedded table before
  any comparison over it means anything. The tooling makes the measurement possible; it cannot
  make a threshold decision on the operator's behalf.
- **The old table survives until someone deletes it by hand.** That is the cost of reversible:
  storage for two copies of a corpus, and a manual cleanup step that can be forgotten. At this
  corpus size the trade is not close.

### Rejected alternative

**One do-everything `migrate` command that moves the corpus and changes the model together.**
It is the obvious ergonomic choice and it is precisely the arrangement DEC-10 forbade. A
single command re-confounds the two variables DEC-10 separated: a recall regression after it
runs has two suspects again, and the golden set — the whole mechanism that makes the re-embed
path safe — would have nothing to attribute a delta to. The ergonomics saved are one extra
command; what is lost is the only reason it is safe to re-embed at all.

**An in-place `ALTER TABLE ... ALTER COLUMN embedding TYPE vector(N)`.** This is the "new
setting instead of a new table" that `_check_dimensions`' error message exists to forbid, and
it is destructive and irreversible in the one dimension that matters: there is no old table to
point back at.
