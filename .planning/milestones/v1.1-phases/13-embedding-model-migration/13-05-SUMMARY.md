---
phase: 13-embedding-model-migration
plan: 05
subsystem: database
tags: [migration, pgvector, embeddings, voyage, live-demo, cost-preview, recall, gate-discipline]

# Dependency graph
requires:
  - phase: 13-embedding-model-migration
    plan: 04
    provides: "the cutover proof, ADR-0008, and the OPERATIONS runbook this wave ran as written and then corrected"
  - phase: 13-embedding-model-migration
    plan: 03
    provides: "`embeddings re-embed`, VOYAGE_PRICES, the --yes spend gate, and the two never-executed functions this wave executed first"
  - phase: 13-embedding-model-migration
    plan: 02
    provides: "recall_golden (seed / exact_scan_results / run_golden / recall_delta / assert_tie_free) and `embeddings copy`"
provides:
  - "The live demonstration: real voyage-3.5 corpus on production Supabase, copied at zero recall delta, re-embedded to voyage-3.5-lite with the delta measured, and dropped with catalog proof"
  - "recall_golden.FrozenQueryEmbedder — the query vector held still, so a two-table comparison is a comparison of two tables"
  - "An honest reconciliation line: `reported`, not `billed`, and a reported 0 is a receipt"
  - "SC-5 complete: both halves measured live, one variable each"
affects: [phase 14 (Voyage spend accounting), docs/OPERATIONS.md, README.md]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase
  patterns:
    - "A comparison harness has as many variables as it has non-deterministic inputs. The index and the ties were both guarded; the query embedder was the one nobody counted, because every local gate used a deterministic fake"
    - "The control for 'did the migration change recall?' is the source table against ITSELF. If that is not clean, nothing measured against the target means anything"
    - "A provider's `total_tokens` is telemetry, not an invoice — demonstrated by it returning 0 for a document that was successfully embedded"

key-files:
  created: []
  modified:
    - src/research_agent/recall_golden.py
    - src/research_agent/migrate.py
    - tests/test_migrate.py
    - docs/OPERATIONS.md
    - README.md
    - .planning/phases/13-embedding-model-migration/13-VALIDATION.md

key-decisions:
  - "The seed used `_ReembedEmbedder(model='voyage-3.5')` rather than a bare `VoyageEmbedder()`. It is a subclass sending a byte-identical request; the difference is that it keeps `response.total_tokens`, and the plan asked that the seeding spend be noted. A bare VoyageEmbedder discards it, so the seed would have been a spend with no receipt."
  - "The copy leg's zero-delta claim is stated for the FROZEN-query measurement, and the unfrozen run that preceded it is reported too rather than discarded. The unfrozen run is the evidence that the artefact exists; deleting it would have left the fix looking unmotivated."
  - "The re-embed delta is reported as a number because `assert_tie_free` PASSED against the re-embedded table under voyage-3.5-lite. Had it failed, the delta would have been reported unmeasurable — that branch was written before the result was known."
  - "`PG_POOL_TIMEOUT` was raised for the demo rather than treated as a bug in the pool. The measured handshake straddles the default from a laptop; the knob exists for exactly this and the runbook now says so."
  - "Cleanup was confirmed twice, through the app's own client and through `psql`, because a cleanup claim verified only by the process that did the dropping is a claim about one code path."

# Metrics
duration: 65min
completed: 2026-08-09
---

# Phase 13 Plan 05: The path, demonstrated live Summary

**One-liner:** The whole migration path ran once against the production Supabase with real Voyage money — copy at zero recall delta, re-embed to voyage-3.5-lite with 8 of 8 golden queries moved, scratch tables dropped with catalog proof — and the run found four things three waves of green local gates could not, including a second variable hiding inside the recall comparison itself.

## Task 13-05.1 — the live demonstration

Driven by the executor with the operator's explicit authorisation, against the prod-shaped
Supabase (session pooler, `prepare_threshold=None`, `search_path = public, extensions`). Every
table carried the `migration_demo_` prefix. **`research_notes` appears in no executed command**;
the only production-adjacent statements were `pg_tables` catalog queries.

### Pre-flight

```
server       PostgreSQL 17.6 on x86_64-pc-linux-gnu, compiled by gcc (GCC) 15.2.0, 64-bit
database     postgres
search_path  public, extensions
vector ext   {'s': 'extensions', 'v': '0.8.2'}

public tables (catalog only, no rows read):
    rate_hits
    research_notes
    run_reservations
    runs
    sessions

migration_demo_% tables BEFORE: []
```

### First execution of `_default_token_counter`, ever

13-03 and 13-04 both recorded that no test calls it. Cold HF cache, verified absent first:

```
12 golden note texts, 208 characters total
HF cache exists before: False
call 1  voyage-3.5       40 tokens   2.378s
call 2  voyage-3.5       40 tokens   0.439s
call 3  voyage-3.5-lite  40 tokens   1.314s
HF cache exists after:  True
agreement call1 == call2: True
```

It works. The download is real (2.378s → 0.439s), it is per-**model** (voyage-3.5-lite paid its
own fetch), and repeated calls agree. Now in the runbook.

### Seed — 12 owner-scoped notes at vector(1024)

```
seed predicted   40 token(s) -> $0.00000240
seed billed      25 token(s) -> $0.00000150
seeded           12 note(s) into migration_demo_notes_src

rows        12
vector_dims 1024
owners      [{'owner': '', 'n': 3}, {'owner': 'alice', 'n': 5}, {'owner': 'bob', 'n': 4}]
created_at span {'lo': ...2026-08-09 08:00:12.209372+00:00, 'hi': ...2026-08-09 08:11:12.209372+00:00}
```

**Predicted 40, reported 25.** That gap is the phase's headline risk arriving on schedule, and
it got chased rather than noted — see § The cost finding.

### Copy leg — `embeddings copy`

```
$ python -m research_agent.migrate embeddings copy --from migration_demo_notes_src --to migration_demo_notes_copy --dry-run
DRY RUN — nothing will be written

  source     migration_demo_notes_src (12 row(s), vector(1024))
  target     migration_demo_notes_copy
  to copy    12 row(s)

Re-run without --dry-run to apply. It is safe to run more than once.
exit=0

$ python -m research_agent.migrate embeddings copy --from migration_demo_notes_src --to migration_demo_notes_copy
copied 12 row(s) into migration_demo_notes_copy (0 already present)

fidelity
  rows         12 in migration_demo_notes_src, 12 in migration_demo_notes_copy
  matched      12 of 12 on (text, owner, created_at)
  unmatched    0
  byte-differing embeddings  0

migration_demo_notes_src is untouched. Cut over with PGVECTOR_TABLE=migration_demo_notes_copy.
exit=0
```

Four fidelity numbers clean against real 1024-dimensional Voyage vectors on a real pooler.

### Copy leg recall — and the run that was NOT clean

`assert_tie_free(migration_demo_notes_src)` under real voyage-3.5: **PASS**. Anti-vacuity: 8 of
8 golden queries answered, 25 rows returned. Then, following the runbook exactly as written:

```
recall_delta(migration_demo_notes_src, migration_demo_notes_copy) =
  [{'query': "'langgraph'@'alice'",
    'old': [('langgraph', 0.708128175381666), ('langgraph chroma voyage supervisor', 0.643880486488342), ('chroma supervisor', 0.492575020040571)],
    'new': [('langgraph', 0.708354613433916), ('langgraph chroma voyage supervisor', 0.644619524478912), ('chroma supervisor', 0.49324572126593)]}]
COPY LEG DELTA: NONZERO (1 queries)
```

**Nonzero, against a copy whose own byte-diff check said zero.** Same notes, same order,
similarities differing in the fourth decimal — a shape that is not what a corrupted copy looks
like. The control settles it: the source table against **itself**.

```
CONTROL  recall_delta(migration_demo_notes_src, migration_demo_notes_src) = 2 query/queries differ
  'chroma retry'@'alice'
      0.720750341549578 vs 0.721130712099715  'chroma retry'   <-- score differs, same text
      0.514170558105153 vs 0.513821690450807  'chroma supervisor'   <-- score differs, same text
      0.466646428900535 vs 0.466152369976044  'langgraph chroma voyage supervisor'   <-- score differs, same text
  'chroma retry'@'bob'
      0.721090998779654 vs 0.721623387530254  'chroma retry'   <-- score differs, same text
      0.519759416580204 vs 0.521119236946110  'langgraph retry'   <-- score differs, same text
      0.474232402352381 vs 0.474968191977524  'langgraph chroma supervisor'   <-- score differs, same text
```

A table cannot have migrated away from itself. `run_golden` embeds each golden query **once per
table**, and the real API does not return a bit-identical vector for the same text on two
separate calls. So `recall_delta(old, new)` was never comparing two tables — it was comparing
two tables *and* two query embeddings. With one query vector per query text:

```
one query vector per query text (6 embed_query calls for 8 queries x 2 tables)
recall_delta(migration_demo_notes_src, migration_demo_notes_copy) = []
COPY LEG DELTA: ZERO
anti-vacuity: 8 of 8 answered, 25 rows
```

**SC-5's infrastructure half, live: zero.** Both runs are recorded because the dirty one is the
evidence that the artefact is real. Worth stating plainly: three back-to-back `embed_query`
calls on the same text *were* bit-identical when tested directly, so the artefact is
intermittent — a run that comes back clean is not evidence that the next one will.

### Re-embed leg — the refusal first

```
$ python -m research_agent.migrate embeddings re-embed --from migration_demo_notes_src --to migration_demo_notes_reembed --model voyage-3.5-lite
cost preview
  model        voyage-3.5-lite at 1024 dimensions
  source       migration_demo_notes_src (12 row(s))
  to embed     12 note(s), 40 token(s)
  rate         $0.02 per million tokens (verified 2026-08-06)
  estimated    $0.000001

  List price. Voyage bills its own token count, not this one, and the
  voyage-4 family's free-token allowance is not modelled here.

error: --yes is required to spend. 12 note(s) would be sent to voyage-3.5-lite at the rate above; nothing was embedded.
exit=2
```

And the target table was **not created** by the refusal:

```
[{'tablename': 'migration_demo_notes_copy'}, {'tablename': 'migration_demo_notes_src'}]
```

### Re-embed leg — the spend

```
$ python -m research_agent.migrate embeddings re-embed --from migration_demo_notes_src --to migration_demo_notes_reembed --model voyage-3.5-lite --yes
cost preview
  model        voyage-3.5-lite at 1024 dimensions
  source       migration_demo_notes_src (12 row(s))
  to embed     12 note(s), 40 token(s)
  rate         $0.02 per million tokens (verified 2026-08-06)
  estimated    $0.000001
  ...
  embedded 12 of 12 note(s)

re-embedded 12 note(s) into migration_demo_notes_reembed at vector(1024).
  predicted    40 token(s)
  billed       25 token(s)
  actual cost  $0.000000

migration_demo_notes_src is untouched. Cut over with PGVECTOR_TABLE=migration_demo_notes_reembed and VECTOR_DIMENSIONS=1024; roll back by pointing them back.
exit=0
```

**`_ReembedEmbedder.embed_documents` executed inside the command for the first time**, and its
`total_tokens` reconciliation printed a real number. The preview printed before the spend on
both invocations.

### Verification on the re-embedded table

```
rows        12
vector_dims 1024
owners      [{'owner': '', 'n': 3}, {'owner': 'alice', 'n': 5}, {'owner': 'bob', 'n': 4}]
source rows with no (text, owner, created_at) match in target: 0 []
rows whose vector is UNCHANGED from the source: 0 (0 is correct -- a re-embed must change every vector)

assert_tie_free(migration_demo_notes_reembed) under voyage-3.5-lite ... PASS
```

Tenancy and the original clock carried; every vector genuinely changed. **Tie-freedom was
re-checked against the re-embedded table before any ordered comparison over it** — the warning
carried since 13-03, discharged here — and it passed, so the delta below is a number rather
than an "unmeasurable".

### The re-embed delta — SC-5's model half

Each table queried with **its own** model (src with voyage-3.5, reembed with voyage-3.5-lite),
each query text embedded exactly once per model.

```
RE-EMBED LEG DELTA: 8 of 8 golden queries changed
```

Seven of the eight returned the same notes in the same order with only the similarities moving.
**One changed which notes came back:**

```
  'chroma retry'@'alice'
    voyage-3.5       [('chroma retry', 0.721131), ('chroma supervisor', 0.513822), ('langgraph chroma voyage supervisor', 0.466152)]
    voyage-3.5-lite  [('chroma retry', 0.748444), ('voyage supervisor retry', 0.490964), ('chroma supervisor', 0.480361)]
    -> the returned notes or their order CHANGED
```

`voyage supervisor retry` enters at rank 2 and `langgraph chroma voyage supervisor` drops out of
the top 3. **That is the phase's whole thesis in one query:** the copy leg moved nothing, so this
is the model's doing by construction, not the migration's.

### Cleanup — the gated step

```
BEFORE: [{'tablename': 'migration_demo_notes_copy'}, {'tablename': 'migration_demo_notes_reembed'}, {'tablename': 'migration_demo_notes_src'}]

DROP TABLE IF EXISTS migration_demo_notes_src;
DROP TABLE IF EXISTS migration_demo_notes_copy;
DROP TABLE IF EXISTS migration_demo_notes_reembed;

SELECT tablename FROM pg_tables WHERE tablename LIKE 'migration_demo_%';
 -> []
 -> row count: 0

public tables remaining (catalog only):
    rate_hits
    research_notes
    run_reservations
    runs
    sessions
```

Confirmed a second time through a different client:

```
$ psql "$DATABASE_URL" -Atc "SELECT count(*) FROM pg_tables WHERE tablename LIKE 'migration_demo_%';"
0
```

**Zero residue. Production untouched. No `fly secrets`, no `fly deploy`, no model flip.**

### Spend

| Leg | Model | Reported tokens |
|-----|-------|-----------------|
| seed (12 notes) | voyage-3.5 | 25 |
| token-gap characterisation (probes + per-text) | voyage-3.5 | ~96 |
| copy-leg recall (tie-free + 2 runs + control + frozen) | voyage-3.5 | ~79 |
| re-embed (12 notes) | voyage-3.5-lite | 25 |
| re-embed verification (tie-free + 2 runs) | voyage-3.5 / -lite | ~20 |

≈ **245 tokens**, overwhelmingly at voyage-3.5's $0.06/MTok: **≈ $0.000015**, i.e. under two
thousandths of a cent, against an acceptance criterion of "well under $0.01". The demonstration
cost less than the rounding error on the estimate of it — and per the finding below, Voyage's
dashboard is the only authority on what was actually billed.

---

## The cost finding: neither number is an invoice

The plan called a lying preview the phase's headline risk. The preview does not lie, but it is
not what the VALIDATION criterion called it ("exact token count"), and the *reported* number is
worse than inexact.

`count_tokens` says 40 for the corpus. `response.total_tokens` says 25. Chased with the local
tokenizer (free) and then per-text against the API:

```
   3  'chroma retry'          ['chrom', 'a', 'Ġretry']
   2  'langgraph'             ['lang', 'graph']
   ...
count_tokens(all 12)      40
sum of per-text counts    40      <- the local count is self-consistent

  local= 3  api= 2  diff= 1  'chroma retry'
  local= 2  api= 1  diff= 1  'langgraph'
  local= 4  api= 2  diff= 2  'voyage supervisor retry'
  local= 2  api= 0  diff= 2  'voyage'
  local= 2  api= 0  diff= 2  'supervisor'
  ...
sum local           40
sum api (per-text)  25
batch of all 12    api = 25       <- batching is not the cause
```

**A single one-word document reports 0 tokens** while returning a perfectly good 1024-dimensional
embedding. Nothing that returns an embedding costs zero tokens, so `total_tokens` cannot be a
billing figure — it is telemetry. The whole pattern fits `api = (Voyage's own tokenisation) − 1
per text`, where Voyage's tokeniser keeps `voyage` and `supervisor` whole and the HF tokenizer
splits them; but the mechanism matters less than the conclusion:

- the **predicted** figure is an honest **upper bound** (it over-counted by 60% here),
- the **reported** figure is what the response said and is demonstrably not an invoice,
- **Voyage's usage dashboard is the only authority**, and embedding spend is still absent from
  `/metrics` (Phase 14).

All three now stated by the command, the runbook and the README.

---

## Task 13-05.2 — the phase gate battery

### Suite

| Arm | Entering | On exit | Delta |
|-----|----------|---------|-------|
| plain | 529 passed / 61 skipped | **529 passed / 63 skipped** | +2 skipped, 0 new passes |
| armed (`DATABASE_URL`) | 589 passed / 1 skipped | **591 passed / 1 skipped** | +2 passed |
| armed + `REQUIRE_POSTGRES=1` | 590 passed / 0 skipped | **592 passed / 0 skipped** | +2 passed |

Collected 590 → 592 in every arm: this wave's two tests and nothing else. No pre-existing test
changed state. **Both new skips justified** — each seeds a real pgvector table and drives the CLI
against it; with no database there is nothing left to assert and a fake would be measuring the
fake. `ruff check src tests` clean.

### Every VALIDATION row re-run on the final tree

All fourteen automated gates were re-executed rather than inherited from their waves:

```
migrate_preserves_owner          1 passed        golden_set                  1 passed
migrate_legacy_roundtrip         1 passed        copy_fidelity               1 passed
copy_recall_identical            1 passed        index_sanity                1 passed
reembed_carries_tenancy          1 passed        voyage_pricing              2 passed
preview_requires_yes             1 passed        dimension_ceiling           1 passed
dimension_check_still_loud       1 passed        cutover_reversible          1 passed
frozen_query                     1 passed        zero_reported               1 passed
```

Doc gates: 8 ADRs (baseline 7), `Source:` 1, `Promoted from` 0, `Status: Accepted` 1, row-shaped
index gate 1; README old phrase 0, `embeddings re-embed` 1 in README and 1 in OPERATIONS,
`Rollback is pointing back` 1, `not exercised` 0.

13-VALIDATION.md reconciled: every row `✅ done` with its task ID and the mutations that proved
it, the three vacuous clauses 13-04 caught recorded beside the originals rather than replacing
them, Wave 0 checked, sign-off complete, `nyquist_compliant: true`, `status: complete`.

## Gate discipline: four mutations on this wave's two gates, all red

Sixteen vacuous gates across six phases entering. Baseline before mutating: `pytest
tests/test_migrate.py` armed = **16 passed** (waves 1–4), the two new tests green as 17 and 18.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| F1 | `FrozenQueryEmbedder.embed_query` stops caching (calls inner every time) | **RED** | `test_frozen_query_embedder_isolates_the_table:522` — source-against-itself deltas on **all 8** queries, first extra item `'chroma retry'@'alice'` |
| F2 | `DriftingEmbedder`'s nudge set to `0.0` — the control stops being a control | **RED** | `:513` `AssertionError: the control must be dirty, or it is not a control` / `assert [] != []` |
| F3 | `frozen.calls` incremented on every call rather than every distinct text | **RED** | `assert frozen.calls == len({spec["query"] for spec in golden.GOLDEN_QUERIES})` |
| B1 | Restore `if actual_tokens:` truthiness in migrate.py | **RED** | `test_zero_reported_tokens_is_a_receipt_not_a_silence` — `assert 'reported     0 token(s)' in out` |

**F2 is the one worth reading.** It does not mutate the code under test at all — it mutates the
*control* — and it exists because "the source table compared with itself is dirty" is an
assertion that would be silently satisfied by a stand-in that never drifts, leaving the frozen
half of the test proving nothing. This is 13-02's M2/M2′ and 13-03's M4/M4′ pattern applied
before the fact: the assertion that makes the other assertions mean something needs its own
falsification.

All mutations reverted; every revert verified by SHA-1 against a pre-mutation snapshot
(`recall_golden.py` → `5ad96985…`, `test_migrate.py` → `a637fb0a…`, `migrate.py` restored by
byte comparison). `ruff check src tests` clean on the final tree.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — Missing critical functionality] `recall_delta` was comparing two query vectors as well as two tables**
- **Found during:** Task 13-05.1, the copy leg
- **Issue:** `run_golden(old)` and `run_golden(new)` each call `embed_query` on the same text. Under the deterministic `FakeEmbedder` every local gate used, that is free; against a real API it is a second variable, and the live source table compared with **itself** deltaed on 2 of 8 queries. The copy leg's zero-delta claim — SC-5's entire infrastructure half — was being measured through an instrument with its own noise floor, and the runbook told operators to do exactly that.
- **Fix:** `recall_golden.FrozenQueryEmbedder`, the module docstring naming the query side as the third source of variance beside the index and ties, `test_frozen_query_embedder_isolates_the_table` with a dirty control, and the requirement written into the OPERATIONS runbook (one wrapper per model across a model change).
- **Files modified:** `src/research_agent/recall_golden.py`, `tests/test_migrate.py`, `docs/OPERATIONS.md`
- **Commits:** `f284166`, `49c02de`, `15c5491`

**2. [Rule 1 — Bug] A reported token count of 0 printed as "not reported by this embedder"**
- **Found during:** Task 13-05.1, characterising the cost gap
- **Issue:** `if actual_tokens:` is a truthiness test on a number the API demonstrably returns as 0 for a one-word document. A receipt of zero was being displayed as a missing feature.
- **Fix:** `is not None`, and `test_zero_reported_tokens_is_a_receipt_not_a_silence` behind it.
- **Files modified:** `src/research_agent/migrate.py`, `tests/test_migrate.py`
- **Commits:** `578f709`, `49c02de`

**3. [Rule 2 — Misleading output] `billed` overstated what `total_tokens` is**
- **Found during:** Task 13-05.1
- **Issue:** The line printed `billed 25 token(s)` and `actual cost $0.000000` for a field that returns 0 for a document that was successfully embedded. Calling that "billed" and multiplying it into an "actual cost" invites an operator to reconcile against a number that is not an invoice.
- **Fix:** Relabelled `reported`, the disagreement with the prediction printed explicitly, Voyage's usage dashboard named as the only authority, and the preview's caveat given the measured direction (upper bound, 40 vs 25).
- **Files modified:** `src/research_agent/migrate.py`, `docs/OPERATIONS.md`, `README.md`
- **Commits:** `578f709`, `15c5491`

**4. [Rule 3 — Blocking issue] `PoolTimeout` from an operator laptop**
- **Found during:** Task 13-05.1, the copy leg
- **Issue:** The documented commands failed intermittently with `psycopg_pool.PoolTimeout` before touching any data. Measured cause: `PG_POOL_TIMEOUT=2.0` is tuned for the Fly machines in the database's own region, and the handshake from a laptop measured 0.43s–5.63s — straddling the default. Not a code fault; a documentation gap in a runbook whose whole audience is an operator at a keyboard.
- **Fix:** Raised the existing env knobs for the demo (no code change) and added the measurement, the recommended values and the "always safe to retry" note to the runbook.
- **Files modified:** `docs/OPERATIONS.md`
- **Commit:** `15c5491`

### Departures from the plan's written approach

- **The seed used `_ReembedEmbedder(model="voyage-3.5")`** rather than the plan's bare `VoyageEmbedder()`. Same class hierarchy, byte-identical request; the difference is that it retains `response.total_tokens`. The plan asked for the seeding spend to be noted and a bare `VoyageEmbedder` discards the only number that could have noted it.
- **The token gap was characterised, not just recorded.** The plan asks for predicted-vs-actual. Recording "40 vs 25" and moving on would have left the phase's headline risk as an unexplained discrepancy; the per-text probe is what turned it into the finding that `total_tokens` is not a billing figure at all.
- **Both copy-leg runs are reported**, the unfrozen and the frozen. The plan expects one zero-delta number. Reporting only the clean one would have made the fix look unmotivated and hidden the fact that the runbook, as written at the time, produced the dirty one.

### README

**Amended** (commit `15c5491`), per the standing per-phase instruction. The limitation bullet now
records that the path has been run end to end against production Supabase with both legs'
results, and replaces "the preview is an estimate, not accounting" with the measured version:
an upper bound, 40 vs 25, a one-word document reporting 0, and `/metrics` still holding no
embedding spend at all.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-13-17 | mitigate | **Closed.** Every executed command carries the `migration_demo_` prefix; `research_notes` appears in none of them. The only production-adjacent statements were `pg_tables` catalog reads — the production notes table was never queried, let alone written. |
| T-13-18 | mitigate | **Closed, and then some.** Preview transcripts captured before the `--yes` run and again during it; predicted-vs-reported recorded, chased, and the conclusion (neither figure is an invoice) pushed back into the command's own output. |
| T-13-19 | mitigate | **Closed.** Three DROPs, then `SELECT tablename FROM pg_tables WHERE tablename LIKE 'migration_demo_%'` → `[]`, row count 0 — confirmed independently via `psql`. |
| T-13-20 | mitigate | **Closed.** No `fly secrets`, no `fly deploy`, no `PGVECTOR_TABLE` change. `fly` was used exactly once, read-only, to obtain the DSN from a running machine. |

New threat surface: none. No network endpoint, no auth path, no schema change.

## Known Stubs

None. **The two untested-by-construction functions named by 13-03 and 13-04 are no longer
untested by construction** — `_default_token_counter` and `_ReembedEmbedder.embed_documents`
both executed against the real services in this wave, and the second one's reconciliation
output was wrong in two ways that only a real response could have revealed.

## Deferred Issues

- **Voyage spend is still absent from `/metrics`** (Phase 14). This wave sharpens what Phase 14 inherits: the local token count is an upper bound and the API's `total_tokens` is not an invoice, so real accounting needs the usage dashboard or a billing API, not either of these numbers.
- **The frozen-query requirement is a convention, not an enforcement.** `run_golden` still accepts a raw embedder, because forcing the wrapper would break the deterministic-fake callers for whom it is pure overhead. The docstring, the runbook and a test carry the requirement; nothing prevents a future caller from skipping it.
- **`assert_tie_free` under a real embedder is cheap here and will not always be.** It scores every row under each queried owner; at twelve rows that is free, at a real corpus size it is a full scan per query.
- **The intermittency is unbounded.** Three consecutive `embed_query` calls came back bit-identical, so the drift's frequency was not characterised — only its existence and its shape. A run that comes back clean without the wrapper is not evidence the wrapper is unnecessary.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `f284166` | fix | The query vector is a variable too |
| `578f709` | fix | A reported zero is a receipt, not a silence |
| `49c02de` | test | Gate both findings the live run produced |
| `15c5491` | docs | What the live run falsified |

## Self-Check: PASSED

- `src/research_agent/recall_golden.py` — FOUND (modified)
- `src/research_agent/migrate.py` — FOUND (modified)
- `tests/test_migrate.py` — FOUND (modified)
- `docs/OPERATIONS.md` — FOUND (modified)
- `README.md` — FOUND (modified)
- `.planning/phases/13-embedding-model-migration/13-VALIDATION.md` — FOUND (modified)
- Commits `f284166`, `578f709`, `49c02de`, `15c5491` — all four resolve in `git log`
- Supabase: `migration_demo_%` tables = 0, verified twice
