---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Closing the limitations list
status: in-progress
stopped_at: "Completed 13-03-PLAN.md (embeddings re-embed, VOYAGE_PRICES, the --yes spend gate; SC-1/SC-2/SC-4 true). Branch gsd/phase-13-embedding-migration. Next: 13-04 (cutover, ADR-0008, OPERATIONS.md)."
last_updated: "2026-08-06T13:20:00.000Z"
last_activity: "2026-08-06 — Phase 13 wave 3 executed: `embeddings re-embed` puts a corpus through a new model at a new width carrying owner and created_at, behind an always-printing cost preview from effective-dated VOYAGE_PRICES, a --yes spend gate proven by counting calls on a fake, and loud refusals for an unpriced model and for >2000 dimensions. Eight mutations, all red, two recorded with caveats. README rewritten — the limitation it stated is now false."
progress:
  total_phases: 19
  completed_phases: 9
  total_plans: 12
  completed_plans: 22
  percent: 61
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-04)

**Core value:** The pipeline never answers from model knowledge when it should be answering from research — and it is demonstrable to a stranger in one click.
**Current focus:** Phase 10 — ADRs and doc correctness (Phase 10.5 hotfix shipped)

## Current Position

Phase: 13 of 17 (Embedding model migration) — **IN PROGRESS**
Plan: 3 of 5 executed · branch `gsd/phase-13-embedding-migration`, rebased onto `main`
(PR #6 merged). Not pushed.
Status: Wave 3 complete — `embeddings re-embed` exists, its money is gated, SC-1/SC-2/SC-4 true.

**Phase 12 shipped** (PR #6 merged, v9 live). Phases 10, 10.5, 11 merged.

Progress: [███████░░░] 71% (12 of 17 phases complete + hotfix; v1.0 shipped)
Phase 13: [██████░░░░] 3 of 5 plans — 13-01, 13-02, 13-03 done

**Carry into execution:**
- ~~`migrate.py` has a LIVE data-loss bug today~~ **FIXED in 13-01.** Notes and sessions
  carry `owner` and `created_at`; dedup keys on `(text, owner, created_at)`; the
  expired-session skip is printed. `tests/test_migrate.py` gates all three.
- `migrate_notes` now takes `table=`/`dimensions=` keyword parameters — waves 2–3 should
  extend that idiom rather than reading module constants inside new functions.
- ~~"Recall byte-identical" is NEVER asserted through the HNSW index~~ **IMPLEMENTED in 13-02.**
  `recall_golden.exact_scan_results` is the only runner an equality-of-recall assertion may
  use; `indexed_results` exists for `test_index_sanity`'s set-equality check alone. Wave 3
  measures the re-embed delta with the same two runners — do not reach for the indexed one.
- `recall_golden.assert_tie_free` checks rows **at or above each query's floor**, not every
  row: with 5-dim binary vectors any two notes sharing no word with the query both sit at
  similarity 0, so global tie-freedom is impossible, and rows a query cannot return cannot
  affect its order. Wave 3 must re-run it against the re-embedded table — a new model
  re-scores everything and tie-freedom does not travel.
- ~~`embeddings copy` is the CLI idiom to extend~~ **EXTENDED in 13-03.** `re-embed` is a
  sibling `sub.add_parser(...)` in `_main_embeddings`; both table names go through
  `memory.validate_table_name()`.
- ~~voyage-3.5 `output_dimension=2048` exceeds pgvector's HNSW limit~~ **ENFORCED in 13-03.**
  Refused before any DDL, naming 2000 and `halfvec`.
- ~~Preview always prints; `--yes` required to spend~~ **IMPLEMENTED in 13-03**, and proven by
  counting calls on an injected fake rather than by reading the code. `main()` takes
  keyword-only `token_counter=`/`embedder_factory=`; use them rather than monkeypatching.
- **Two functions in migrate.py have never executed:** `_default_token_counter` (the real
  `count_tokens`, which downloads an HF tokenizer on first call) and
  `_ReembedEmbedder.embed_documents` (the `total_tokens` reconciliation). Wave 5's live run
  is their first execution, not merely their demonstration.
- **The re-embed recall delta is still unmeasured, and tie-freedom does not travel.** The
  golden set is tie-free under the 5-dim `FakeEmbedder`; a re-embedded table is a different
  scoring, so any `recall_delta` across the model change must call `assert_tie_free` against
  *that* table first or it measures the query executor. 13-03 built the mechanism and gated
  the money; no task asked for the comparison. 13-04 or 13-05 carries it.
- **VOYAGE_PRICES lives in `usage.py`** with `voyage_price_for()`/`preview_cost_usd()`;
  `PriceWindow.price` is now `Price | float`. Voyage spend is still absent from `/metrics`
  (Phase 14) and the README says so.
- Wave 5 is a checkpoint (live Voyage re-embed against Supabase `migration_demo_*` scratch
  tables only; cleanup gated).
- **13-04.3's README gate is already satisfied** — the old phrase is at 0 occurrences and
  `embeddings re-embed` at 1. The `docs/OPERATIONS.md` half of that gate is untouched.
- Local PG17+pgvector on :54329 (scratchpad instance `pg12`; start with LC_ALL set).
  Baselines after 13-03: plain **529/60**, armed **588/1** (`DATABASE_URL` only) or
  **589/0** (with `REQUIRE_POSTGRES=1`). Quote which armed form you mean when comparing —
  13-01's `575/1` and 13-02's `579/1` were both the `DATABASE_URL`-only form.

## Performance Metrics

**Velocity:**

- Total plans completed: 0 under GSD (phases 1–9 predate GSD planning)
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1–9 | pre-GSD | — | — |
| 10 | 5 (10-01, 10-02, 10-03, 10-04, 10-05) | 55min | 11min |
| 11 | 4 of 5 (11-01, 11-02, 11-03, 11-04) | 230min | 58min |
| 12 | 6 of 6 (12-01 … 12-06; 12-06 Task 4 deferred) | 195min | 33min |
| 13 | 3 of 5 (13-01, 13-02, 13-03) | 148min | 49min |

**Recent Trend:**

- Last 5 plans: —
- Trend: — (no GSD-tracked plans yet)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Full ingested set (23, all soft):
`.planning/intel/decisions.md`.

Recent decisions affecting current work:

- [Ingest]: Zero ADRs existed at ingest — all 23 architectural decisions are soft/revisable. Nothing is LOCKED.
- [Phase 10, approved 2026-08-04]: Promote five load-bearing decisions (DEC-01, DEC-02, DEC-04, DEC-14, DEC-22) to numbered ADRs before any reversal lands.
- [Milestone scope, approved]: All nine README Limitations items are in scope for v1.1.
- [Ordering]: REQ-followup-live-search is last (deepest change); REQ-offline-eval-quality precedes both quality-affecting reversals so their effect is observable.
- [Phase 10.5-01]: Session endpoints reuse the `x-demo-token` header rather than a new `x-sessions-token` — one client-side auth story. CONTEXT left the header name to discretion.
- [Phase 13-03]: `PriceWindow`'s payload is annotated `Price | float` rather than Voyage's flat rate being padded into the four-field `Price`. `covers()` is a date comparison that never inspects the payload; a `Price(input=0.06, output=0.0, …)` would have left a fake output price for someone to read as real.
- [Phase 13-03]: The re-embed price is resolved before the tokenizer is touched and before the database is opened, so an unlisted model costs nothing to discover — no HF download, no connection, no embed call (DEC-12).
- [Phase 13-03]: `--dry-run` wins over `--yes`. The flags contradict each other and the safe reading of a contradiction is the one that spends nothing.
- [Phase 13-03]: The dimension ceiling's *message* needed its own mutation. Relaxing the comparison goes red via an unrelated later failure, leaving `assert "halfvec" in err` unfalsified — a refusal's wording is a separate gate from its condition.
- [Phase 12-05]: Notes are bounded by a 7-day TTL and nothing else. Dedup-on-write was evaluated and rejected — it has no semantics that json, memory, chroma and pgvector can implement identically, and identical behaviour is the claim SC-5's shared suite exists to make.
- [Phase 12-05]: `owner=""` is an exact value on every store, never a wildcard. The orphaned notes and sessions therefore belong to nobody the moment the code ships, and are collected by the TTL rather than by a migration script.
- [Phase 12-05]: The service reads the caller through `limits.caller_identity(request)`, not `request.state.identity` directly — 12-03 made it the single reader, and it carries the never-fall-back-to-client_ip reasoning that the raw attribute does not.
- [Phase 12-05]: A structural gate must assert against the parsed CALL, not against the handler's source text. Three of four run-starting handlers pass `owner=` to something else as well, so the substring form stays green when the thing it guards is deleted.
- [Phase 10.5-01]: `require_sessions_token` fails closed (403 when no credential is configured), deliberately diverging from `check_token`'s open-when-unset convention. A control that goes inert on a missing env var is precisely the defect this hotfix exists to fix.
- [Phase 10.5-02]: The four session routes are grouped on an `APIRouter`, not given four per-route dependency lists. The defect was four routes each independently forgetting a credential, so membership had to become structural — a new route on `sessions_router` is guarded by construction.
- [Phase 10.5-02]: `check_rate_limit` on `DELETE /sessions/{id}` only, sharing the research bucket. Reads stay unmetered so the daily cap's "Read-only endpoints still work" message stays true.
- [Phase 10-01]: ADR provenance is a two-form contract — `**Promoted from:**` for the five `docs/DESIGN.md` promotions, `**Source:**` for ADR-0006, which originates in Phase 10.5 and has no DESIGN.md passage. The index says so in prose so no reader hunts for one.
- [Phase 10-01]: Supersession is a status-line edit and nothing else. A superseded record's Context, Decision and Consequences are never rewritten, including claims that stopped being true. `docs/adr/README.md` states this as a verbatim three-step instruction for Phases 12, 16 and 17.
- [Phase 10-01]: Expected supersessions (Phase 16 → ADR-0005, Phase 17 → ADR-0003, Phase 12 → ADR-0006) are carried in the index as italicised forecasts. All six records are `Accepted` today; nothing is marked superseded.
- [Phase 10.5-02]: **Any assertion over `app.routes` must now be recursive.** fastapi 0.141.1 leaves an `_IncludedRouter` in `app.routes` rather than flattening, so a flat scan silently misses every session route. Two pre-existing tests were fixed for this; plan 04's structural test must not repeat the mistake.
- [Phase 10.5-03]: The daily-cap test records real spend and asserts `POST /research` 429s *before* asserting a read is 200. Under the fixture's `DEMO_DAILY_USD_CAP=0`, `check_daily_cap` returns early, so the obvious construction cannot fail even if the cap were wired onto the reads.
- [Phase 10.5-03]: A guard test is not done until the guard has been removed and the test observed failing. All six controls in this phase were mutation-checked individually; the mutation table lives in `10.5-03-SUMMARY.md` and is plan 04's acceptance shortcut.
- [Phase 10.5-04]: `api_routes()` **supersedes** wave 2's private `_served_routes()` walker rather than sitting beside it. Two independent recursive walkers over `fastapi.routing._IncludedRouter` — a private, version-specific internal — is two things to fix on the next FastAPI upgrade and two things that can drift.
- [Phase 10.5-04]: The non-vacuity threshold is **6 route objects across 5 paths**, not 5 — `/sessions/{session_id}` is served by both a GET and a DELETE. Do not "correct" it downward.
- [Phase 10.5-04]: A naive flat route scan does not find *zero* session routes as the obvious analysis suggests — it finds the two `@app.post` ask routes, both of which carry `guard`, and therefore reports a perfectly clean sessions tree. A guard invariant without a count assertion goes green over exactly this phase's defect. Verified by mutation.
- [Phase 10-02]: Each record with a named future reversal carries a `### Expected reversal` subsection, not a passing mention — which phase, which requirement, and what specifically breaks. ADR-0005's is the sharpest: Phase 16 removes the record's *premise* (the critic's shared model), so the stronger-judge rationale must be re-derived rather than inherited.
- [Phase 10-02]: ADR-0006 leads its Consequences with a dedicated heading, `### DEMO_TOKEN must never be set in production`, rather than a bullet. The record exists for that one consequence; a list would bury it, and the refactor it guards against ("tidy the two tokens into one") is the plausible-looking kind.
- [Phase 10-02]: ADR-0006 states all four decision parts with individual reasons because they are separable — a future change is most likely to pick off one (apply `guard` to the reads, or make the credential open-when-unset) without seeing the others.
- [Phase 10-04]: The forward-links point at **ADR-0001…0005 only**. ADR-0006 is not linked from `docs/DESIGN.md` and must not be added: it originates in the Phase 10.5 hotfix and carries `**Source:**`, not `**Promoted from:**`. A link from DESIGN.md would assert a provenance that does not exist.
- [Phase 10-04]: The link text carries both the record number and the path (`Recorded as [ADR-000N](adr/000N-slug.md)`) rather than a bare title link, so a reader scanning the prose gets the identifier that supersession notices will use.
- [Phase 10-04]: The "expires this month" clause was replaced with "is time-boxed" rather than a fresher relative date. Any wording anchored to a writing date decays; the two ISO dates carry the fact.
- [Phase 10-05]: A red gate is recorded as red. SC-5 step 3 failed and the row was marked ❌ with the approval left pending, rather than the criterion being reworded to match the observed state. The Criterion and Automated Command columns of `10-VALIDATION.md` were not touched after the gates ran.
- [Phase 10-05]: Two edits were made to `10-VALIDATION.md` prose that the verify block forced, and neither weakens a gate: the `⬜ pending` token was dropped from the status legend (nothing is pending, so the key entry was dead), and the sign-off item `` `nyquist_compliant: true` set in frontmatter`` was reworded to "Frontmatter marks the phase Nyquist-compliant" so the literal token appears exactly once, in the frontmatter that owns it.
- [Phase 10-05]: `ruff` is not on `PATH` in this environment; `.venv/bin/ruff` is the working invocation, matching the `.venv/bin/pytest` convention. Recorded so a future phase does not read a bare `ruff check .` failure as a lint regression.
- [Phase 10-05]: The non-vacuity control is now four probes, not one — the zero-occurrence search, the file counter, the link resolver and the `Status` gate were each shown to fail on input that must fail. This repo has shipped five vacuous gates across two phases; a gate that has only ever passed is treated as unproven.
- [Phase 11-03]: **A guard that skips is a guard that config deletion disarms.** Two deploy tests `pytest.skip()`d whenever `[[mounts]]` was absent, so removing the mount would have made them no-ops with CI still green. Both are now two-armed — they assert in *both* topologies and skip in neither. The old guard was fed the same scratch file as the new one and returned `Skipped` where the new one raises. Any future mount-conditional or DSN-conditional check should be written this way from the start.
- [Phase 11-03]: **Removing the `*_DB_PATH` vars does not close the SQLite fallback; the pins do.** `sessions.py` defaults its path to a file beside the module and the backend selector returns `sqlite` with no DSN, so a mount-less machine with an unset `DATABASE_URL` boots on container-local SQLite, `/health` reports `dependencies: "ok"` because SQLite is perfectly reachable, and the only difference on the wire is a class name nothing reads. `SESSION_BACKEND`/`METRICS_BACKEND`/`VECTOR_STORE` pinned makes it fail closed at store construction instead. This is the gate `-k fails_closed` deliberately does not provide.
- [Phase 11-03]: **Assert on the parsed `[env]` table, never the file text, when one key name is a substring of another.** `grep -c 'VECTOR_STORE' fly.toml` returns 1 on a file with no `VECTOR_STORE` key at all, because `VECTOR_STORE_PATH` contains it. The inverse also applies: the `-k runbook` guard deliberately *does* read the text, because a comment is precisely what it guards and `tomllib` discards comments.
- [Phase 11-03]: **A test that is red until an edit lands belongs in the task that makes the edit.** The runbook-staleness guard was written in Task 2, not Task 1, because Task 1's verify runs the whole file and would have ended red. Recording the red observation against `git show HEAD:fly.toml` is what makes an absence-asserting gate falsifiable.
- [Phase 11-03]: **Two more vacuous gates caught before running** — bringing this repo to eight across four phases. `PG_CONNECT_TIMEOUT >= 1` and `SESSION_BACKEND >= 1` in `docs/OPERATIONS.md` both already passed on the untouched tree. Replaced with prose-only greps (`grep -v '^|'`), an old-text-is-gone check, a same-paragraph co-occurrence check, and a same-line tie to `pin|cutover`. The rule: state the *measured* baseline in the gate, and if it is not zero, the `>= 1` form proves nothing.
- [Phase 11-03]: **Line-oriented gates need line-oriented prose.** `grep 'X' file | grep -c 'Y'` requires both tokens on one *physical* line, and 80-column reflow kept separating them. The sentence was rewritten to suit the gate rather than the gate weakened to suit the sentence.
- [Phase 11-01]: `check=ConnectionPool.check_connection` is **deliberately not used**, against RESEARCH's own Pattern 1. The check is a server round trip performed *during* checkout and the pool's `timeout` does not interrupt one in flight, so on a partitioned database it adds an unbounded cost to every checkout — on `/health`, the exact endpoint this phase is bounding. Staleness stays covered by the retry-once arm. Gated by `grep -c 'check_connection' src/research_agent/db.py` returning 0, with the reason in a comment so the omission does not read as an oversight.
- [Phase 11-02]: **A local Postgres was built to run the gated suite**, because Docker was unavailable and this phase's plans state explicitly that a green local run is not evidence. It found three `db.py` bugs, two of which no fake could have caught. The rule this establishes: for a phase whose claims are server-shaped, "the Postgres tests skipped locally" is an unverified result, not a pass.
- [Phase 11-02]: **The retry discriminator is the SQLSTATE, not the exception class.** Both obvious rules are wrong. "Any `OperationalError`" retries `QueryCanceled` (57014) and doubles the statement timeout that just fired. "Has a SQLSTATE means the server is alive" refuses to retry `AdminShutdown` (57P01), which is exactly what `pg_terminate_backend` sends. The second rule shipped and was caught only by the real server. `_connection_was_lost()` now retries SQLSTATE `None`, class `08`, and `57P01/02/03`.
- [Phase 11-02]: **Reads retry the whole statement; writes deliberately do not.** A client cannot distinguish "never arrived" from "committed, response lost", so a retried write is at-least-once — a duplicated run in `/metrics` or a `UniqueViolation` over a row that exists. The asymmetry is documented in `_read()` rather than left to be inferred.
- [Phase 11-02]: **`pool.check()` on the failure path is not the `check=` callback 11-01 rejected.** A provider terminates every idle connection at once, so a bare retry-once drew the next dead connection and still failed against a real server. `check()` replaces all broken idle connections, but runs *only* after one has been found dead — so 11-01's objection (a round trip on every checkout, including `/health`'s) does not apply and still stands.
- [Phase 11-02]: **`_probe`'s deadline bounds availability, not execution**, and the docstring says so precisely. A `ThreadPoolExecutor` bounds its *workers*, not its *queue*; abandoned probes against a persistently hung peer are reaped by `tcp_user_timeout`, not by the worker count. `future.cancel()` was deliberately not added so the documented mechanism stays the true one.
- [Phase 11-02]: **The skip-count invariant rises from 28 to 34**, and the operative gate is restated as (1) `0` skipped in CI under `REQUIRE_POSTGRES=1` — actually run, not predicted — and (2) locally, skips rise by exactly 6, each named in the summary. 11-05 Task 4 must mirror this into `11-VALIDATION.md`.
- [Phase 11-02]: Two acceptance greps again tripped on the prose explaining why the forbidden token was removed — the same tension 11-01 logged. Resolved the same way: keep the gate, reword the reason. This is now a repeat pattern and a plan author should expect it.
- [Phase 11-01]: `Database.close()` is a **claim release**, not a disposal, and is idempotent. `service.lifespan` closes sessions and metrics but never the memory store, and the contract suite closes after every parametrised case; a `close()` that disposed a shared pool would break the remaining holders, and a `ConnectionPool` cannot be reopened. `db.close_all_pools()` exists for the lifespan `finally` and is not wired yet — that is 11-02.
- [Phase 11-01]: RESEARCH's Pitfall 7 was **wrong in the safe direction**. `PoolTimeout`'s message is "couldn't get a connection after 0.50 sec", and `test_store_contract.py`'s `match="(?i)connect"` is a `re.search`, which "connection" satisfies. The test needed no edit; do not loosen it later on the strength of the prediction.
- [Phase 11-01]: The retry arm in `cursor()` can only fire on an exception raised at *checkout*. A `@contextmanager` that yields a second time after an exception is thrown in raises `RuntimeError: generator didn't stop after throw()`. This is the pre-existing shape, unchanged by the port — worth knowing before anyone "improves" it.
- [Phase 11-04]: **With a staged secret, use `fly deploy`, never `fly secrets deploy`.** The latter re-releases the *current* image, so it would have shipped the new DSN onto the pre-pool v4 build — Postgres-backed stores running single-`RLock`-connection code with no per-probe deadline and no `machine` key. One `fly deploy` applies staged secrets **and** the branch code in the same release. The deployed release was then confirmed to carry waves 1–3 (the startup log naming all three backends, the `machine` key in `/health`) rather than assumed to.
- [Phase 11-04]: **Supabase's default `search_path` already contains `extensions`**, so `memory.py`'s unqualified `::vector` casts resolve *without* 11-01's `_configure()` callback. Verified both ways on the live database. The callback stays — it makes the requirement explicit rather than inherited from a provider default that can change, and it is what keeps the code portable — but it is **insurance that has not yet been needed**, not a fix for an observed break. Do not read 11-01's rationale as describing a failure that happened.
- [Phase 11-04]: **A provider-credential failure is not a reason to roll back a database cutover.** `POST /research` 502'd on a revoked `ANTHROPIC_API_KEY` minutes after the cutover. The tempting move is `fly secrets unset DATABASE_URL`. It would have discarded a verified-good migration and left the demo exactly as broken. The discriminator was cheap and should be reached for first: the failing secret's digest was unchanged by the deploy, and the 401 came from the third party's own API.
- [Phase 11-04]: **The HTTP round trip and the database round trip are separable, and worth separating when one is blocked.** Every HTTP write path runs the model first, so a dead model key blocks the session round trip through `/research`. Proving it at the store layer over `fly ssh console` — same classes, same pool, same DSN, same `::vector` cast — discharged the database claim honestly, with the gap (FastAPI's dependency wiring, already covered by `/health`) named rather than papered over.
- [Phase 11-04]: **`fly ssh console -C` takes no shell**, so RESEARCH's `python - <<'PY'` heredoc never reaches Python, and the container has no `curl`. base64-encode the script locally and run `python -c "import base64;exec(base64.b64decode('...'))"`. This also keeps credentials inside the machine — the script reads `os.environ['DATABASE_URL']` and never prints it.
- [Phase 10.5-01]: `REQ-live-endpoint-exposure` stays **Pending** until plan 05. Its text says "not reachable without credentials **on the deployed service**" — it cannot be honestly checked off by a plan that wires nothing and deploys nothing. Mark it at the cutover, not before.
- [Phase 13-01]: **A dedup or idempotency gate that only runs once proves nothing about the key.** The plan's own acceptance criterion — "the same text under two owners produced two rows" — is green under a text-only dedup key, because a first pass into an empty table inserts everything whatever the key is. The gate now deletes one owner's row and re-migrates, which is where the key actually applies. **Fourteenth vacuous gate, second consecutive phase** where a structurally sensible assertion was blind to the exact mutation it existed to catch.
- [Phase 13-01]: **Timestamp identity across the SQLite/JSON→Postgres boundary is compared as a `datetime`, never as an epoch float.** `extract(epoch FROM …)` returns a psycopg `Decimal` (never equal to a float), and a ~1.8e9 epoch carrying microseconds needs 16 significant digits where float64 has ~15.95 — so a rounded-epoch dedup key could fail to recognise the row it had just written, turning every re-run into a duplicate insert.
- [Phase 13-01]: **Belt-and-braces writes are honest redundancy, not a caught bug, and the mutation table must say so.** `owner` is written twice in `migrate_sessions` (the `create()` kwarg and the restoring UPDATE), so removing either alone is unobservable and stays green. Only removing both goes red. Recorded as such rather than claiming a red that did not happen.
- [Phase 13-02]: **A tie-freedom check must be scoped to the rows a query can return.** The plan asked for it unfiltered; over 5-dimensional binary bag-of-words vectors that is unsatisfiable, because any two notes sharing no word with the query both sit at similarity 0. The check examines rows at or above each query's `min_similarity` — which is also the property that matters, since a row the query cannot return cannot affect its order. **Distinct vocabulary sets do NOT buy tie-freedom**: similarity depends only on (overlap, size), so `{chroma,retry}` and `{chroma,voyage}` are the same distance from `"chroma"`. Two candidate golden queries were discarded at design time for exactly this.
- [Phase 13-02]: **A self-checking command can hide the gate downstream of it.** Dropping `owner` from the copy column list turns the *command's own* fidelity gate red first (the join key includes `owner`), so the test fails on `assert main(...) == 0` and the golden comparison never runs. The mutation table records a second variant with the return code relaxed, which is what actually demonstrates the golden set can see tenancy loss — all eight queries delta, with alice's and bob's rows surfacing in the unowned bucket. Without it the recorded evidence would have looked stronger than it was.
- [Phase 13-02]: **The plan's `INSERT..SELECT` grep gate was vacuous as written** — `grep -c "INSERT INTO .* SELECT"` returns 1 on the tree *before* the change, matching prose in a docstring, and the real SQL is a multi-line template no single-line grep can see. Replaced with a whitespace-flattened regex requiring the full column and select lists, and recorded as a presence check; the real gate is the byte-diff assertion, falsified by perturbing one copied vector.
- [Phase 13-02]: **A recall-equality assertion needs an anti-vacuity floor.** `recall_delta` over two sets of eight empty results is also `[]`, so a seeding failure or a wrong owner would make the gate green. The test asserts seven of eight queries answered, and at least 12 rows total, before comparing.
- [Phase 13-02]: **A non-destructive gate compares contents, not counts.** A row count is green against `TRUNCATE`+re-`INSERT` and against an `UPDATE` that rewrote every embedding — which is the exact corruption the byte-fidelity mutation simulates. The source is compared as a full `(text, owner, created_at, embedding::text)` set before and after the copy and after a `--dry-run`.
- [Phase 13-02]: `--dry-run` creates **nothing**, not even the target table: it asks `to_regclass` whether the target exists and treats every source row as pending when it does not, rather than running DDL to make its own counting query legal. A dry run that writes is not one.
- [Phase 13-02]: The copy **refuses an empty source**. A copy of nothing satisfies every fidelity check there is.
- [Phase 13-02]: `main()` dispatches on the literal token `embeddings` rather than using a top-level required subparser, which would have turned the bare invocation `docs/OPERATIONS.md` documents into an error about a missing subcommand.
- [Phase 13-01]: A missing or zero `created_at` migrates as **epoch 0** — already expired under the note TTL — rather than as `now()`. That mirrors what the store does with pre-Phase-12 entries; stamping them fresh would resurrect data the service had stopped serving.
- [Phase 12-01]: **The dev extra composes `research-agent[chroma]` rather than repeating the pin.** chromadb==1.4.1 stays pinned once, in the chroma extra; a SQLite/JSON deploy installing `[service]` alone still never pulls it. The contract fixture's chroma arm skips ONLY on a genuinely missing chromadb import — never on HAS_POSTGRES — so CI (which installs dev) collects and runs it.
- [Phase 12-01]: **`CAP_LOCK_KEY` (11165997) is a different advisory-lock key from `SCHEMA_LOCK_KEY` (3895545195)**, and the inequality test is deliberately not Postgres-gated so a keyless local run still catches a collapsed-constants edit. A shared key would serialise cap accounting against schema DDL.
- [Phase 12-01]: **The xact-lock test's held-half is what makes it falsifiable.** `pg_advisory_xact_lock` on an autocommit connection degenerates to a one-statement lock, so a `transaction()` that silently stopped opening a transaction would still pass an after-the-block acquisition check. The test therefore also asserts a rival connection is REFUSED the lock while the block is open. `transaction()` mirrors `cursor()`'s PoolTimeout/PoolClosed-before-OperationalError ordering.
- [Phase 12-01]: **The full-suite baselines moved and are fully explained**: plain 436/34 → 443/37 (+6 chroma-arm, +1 key-inequality; +3 Postgres-gated transaction skips), armed 469/1 → 479/1. README's "470 tests, ~10s" was falsified by this wave and updated to "480 tests, ~25s" in the same wave — the chroma client's startup is most of the wall-clock growth.
- [Phase 12-02]: **The HMAC gate is falsifiable by construction, not by presence.** One test mints under secret A and asserts verify returns the id under A AND None under B on the same token. A `grep -c compare_digest` gate alone proves wiring, not rejection.
- [Phase 12-02]: **Tests authenticate through the real path.** `IdentityMiddleware` is not dependency-overridable, so `mint_cookie(monkeypatch, secret=...)` mints genuine tokens under a pinned `IDENTITY_SIGNING_SECRET` and tests present them as the `ra_id` cookie. Later waves (limits, ownership, note scoping) key on this seam.
- [Phase 12-02]: **`Secure` is unconditional; the tests adapt, never the attribute.** `make_client` uses `base_url="https://testserver"` because httpx's jar withholds a Secure cookie over http — under the default base_url every request silently re-mints and per-identity tests pass vacuously. Do not fork the cookie attributes on env.
- [Phase 12-02]: **A bare ASGI stub cannot sit inside `with TestClient(...)`** — the context manager drives lifespan, which the stub answers with http messages and Starlette asserts. Raw-middleware tests use the client without the context manager.
- [Phase 12-02]: **README's identity narrative is left to the wave that owns it.** "guardrails … don't identify callers" stays true until Wave 3 rekeys the limits; Wave 5 owns the deployed-identity story. Only the falsified test count (480 → 504) was corrected in-wave.
- [Phase 12-03]: **The two halves of `LimitsStore` have deliberately different strictness, and confusing them is the expensive mistake.** `check_rate` is a fairness tool: one statement, one round trip, and a small concurrent-insert overshoot costs nothing. `reserve` is a money tool: check-and-insert inside `db.transaction()` holding `pg_advisory_xact_lock(CAP_LOCK_KEY)`, because a single conditional INSERT is **not** race-free under READ COMMITTED — two guards each evaluate the WHERE against a snapshot excluding the other's uncommitted row and both pass. The reason is written at the seam so nobody "simplifies" the reserve into the rate shape.
- [Phase 12-03]: **`caller_identity()` falls back to one SHARED bucket, never to `client_ip`.** A shared bucket is more restrictive than the truth, which is the safe direction; an address fallback would quietly reinstate the forgeable key this phase removed, and would do it exactly when the identity layer was broken — i.e. when nobody was looking. `client_ip` and `TRUST_FORWARDED_FOR` survive for **logging only**, with a do-not-key-limits-on-this comment.
- [Phase 12-03]: **The cap left `enforce()` rather than gaining a `run_id` parameter there.** A reservation needs state the guard cannot see (the run does not exist until the handler builds it), and a guard that half-enforces the cap is worse than one that visibly does not. `reserve_or_429` raises **synchronously inside the handler**, before any StreamingResponse is constructed, so a capped caller gets a real 429 rather than a 200 whose body turns out to be an error event.
- [Phase 12-03]: **An in-handler control needs two gates, not one.** `reserve_or_429` is not a route dependency, so the `api_routes()` walker structurally cannot see it — the exact ADR-0006 shape, on the same `/sessions` routes that forgot a credential four times. It is held by a parametrized four-route 429 test **and** a structural `inspect.getsource` invariant with a non-vacuity floor asserted first. Falsified, not assumed: deleting the reserve from `ask()` alone turns both red.
- [Phase 12-03]: **Settle goes next to `metrics.record`, never in the handler's `except`.** `_stream` swallows its exception to terminate the SSE cleanly, so the handler's own `except` never runs on a failed stream — a settle placed there leaks a reservation on every stream failure. Four terminal arms, four settles. `limits.settle()` itself never raises: a failed settle must not turn a finished run into a 500 or truncate a stream that already delivered, and `RESERVATION_STALE_SECONDS` (900s) makes the failure survivable while the warning keeps the leak visible.
- [Phase 12-03]: **The process-global `RateLimiter` instance is gone.** It was what made "the rate limit" mean something different on each machine, and a module global is not something a request can be pointed away from. The window now lives in the injected store; `RateLimiter` survives only as `InMemoryLimits`' internals.
- [Phase 12-03]: **Baselines moved and are fully explained**: plain 467/37 → 493/41, armed 503/1 → 533/1, collected 504 → 534. The four extra plain skips are exactly the Postgres-gated `test_limits.py` tests, so **a green plain run is not evidence for the no-overshoot race** — the armed run against `:54329` is. README's falsified spend-cap limitation was corrected by the wave that falsified it; the "rate-limited, not authenticated" line still belongs to Wave 5.
- [Phase 12-04]: **A dependency assertion over routes cannot see WHERE the dependency came from.** Every session handler injects `require_session_access` as a parameter to read its value, so `dependency_names(route)` is satisfied with or without the router-level declaration — deleting `sessions_router`'s own `dependencies=[...]` left the new structural gate GREEN. Observed by mutation, not reasoned about. `service.sessions_router.dependencies` is now asserted directly. Structural membership is the entirety of ADR-0006 part 4; a gate that cannot see it removed is not guarding it.
- [Phase 12-04]: **404 for foreign, expired and missing alike — asserted as an equality between two live responses**, not as two status codes. Equal status, equal key sets, and detail strings differing only in the echoed id. A 403 confirms an id names a real session, and session ids travel in shared URLs and screenshots.
- [Phase 12-04]: **`delete_session` calls `_require` before `store.delete`.** `store.delete` returns True/False, which distinguishes a real id from an invented one even while refusing both — the oracle rebuilt one layer down. Ownership is checked at the same choke point the reads use.
- [Phase 12-04]: **Expiry is derived from `updated_at`, never a second column, and Postgres evaluates it with `EXTRACT(EPOCH FROM now())`.** Two machines then read one clock; a Python-side cutoff would make "expired" mean something slightly different on each. `SESSION_TTL_DAYS` (7) is read per call. Reads must never renew — otherwise "7 days after last activity" silently becomes "7 days after last glance" and the table never shrinks (contract-tested on both backends, the renewal half asserted on a live session *before* the expiry half).
- [Phase 12-04]: **The fail-closed property of `SESSIONS_TOKEN` inverted, and that is the honest reading.** It used to raise 403 when unset because the token was the only thing between a stranger and someone else's research. Ownership is now that thing, and ownership cannot be left unset — so an unset token closes the operator view alone. `require_session_access` never raises. ADR-0007 (Wave 5) records it.
- [Phase 12-04]: **`client.cookies.set(name, value, domain="testserver")` silently does not send the cookie**; hand cookies to the `TestClient` constructor instead. 12-03's `test_delete_rate_limited_check_runs_after_the_token_check` used the broken form, so its stated premise ("carries the VICTIM'S cookie") was false while the test still passed.
- [Phase 12-04]: **Pre-Phase-12 rows need no migration step.** `owner=''` matches no caller (identities are 32-hex uuids), so orphans resolve for nobody the moment the filter lands and are swept once past the seven-day line. Claim-by-nobody-and-expire: no manual deletion, no special case in code, and the operator can still inspect them until they age out.
- [Phase 12-04]: **Baselines moved and are fully explained**: plain 493/41 → 506/45, armed 533/1 → 550/1, collected 534 → 551 (+17 in both arms). The four extra plain skips are exactly the postgres arms of the four new session-contract tests, so the **armed** run is what proves DB-clock expiry. README/OPERATIONS/.env.example corrected for ownership, expiry and `SESSIONS_TOKEN`; the "rate-limited, not authenticated" line at ~210 remains Wave 5's.
- [Phase 12-06]: **A superseding ADR must carry an explicit `### Carried forward` section.** The convention forbids editing a superseded record's Context/Decision/Consequences, so a bare supersession leaves the parts that survived discoverable only by reading a record stamped "Superseded" and guessing which sentences still apply. ADR-0007 names all four of 0006's parts, and records `SESSIONS_TOKEN`'s survival as an **inversion** (it still fails closed; what changed is that failing closed now costs the operator's cross-owner view rather than every visitor's access) — "it survives" alone would be true and useless.
- [Phase 12-06]: **Freeze a measured SET, never a count.** Adding a font size *raises* the number of `font-size:` declarations, so a count-based or `>= 1` gate stays green for exactly the change it exists to catch. The same applies to the escape hatches: the `font:` shorthand carries a size and a weight, and script-set styles bypass CSS entirely — both are gated, and both mutate red.
- [Phase 12-06]: **Freeze the markup's tag census alongside its text.** A textless element — an empty `<button>`, a blank-summary `<details>` — contributes no text run and walks straight past a text-only first-paint gate, while being exactly the "new interactive element reachable before the first question" AC1 forbids. Found by mutating the text gate, not by reading it.
- [Phase 12-06]: **Build-and-insert-when-populated beats declare-and-hide.** The owned-session list is constructed in script and inserted only while it has rows, so there is no empty state to get wrong and no first-paint delta. Consequence for gating: the plan's `grep '<details id="mine">'` **cannot** be satisfied honestly — the literal only exists if the element ships in the first-paint DOM (which criterion 6 forbids) or sits in a comment (which the grep would accept). The gate asserts the construction AND that no `<details` tag appears anywhere in the file.
- [Phase 12-06]: **Badge on field PRESENCE (`in` / `typeof`), never truthiness.** `Number(payload.cost_usd || 0).toFixed(4)` renders a fabricated `$0.0000` for a stored turn that carries no cost, in the same styling as a measured fact; but a truthiness test would also drop a genuine `$0` and a genuine zero-revision run. The presence form is the only one that omits the absent without hiding the real.
- [Phase 12-06]: **The twelfth vacuous gate, and the narrow lesson.** The fix for "the session list is appended unconditionally" searched the whole of `syncMine()` for `"rows &&"` — which the `else if (!rows && …)` branch satisfies, so the gate passed under the exact mutation it had just been written for. A substring gate over a *region* is unsafe whenever the region contains a **negation** of the thing being asserted; assert on the specific line.
- [Phase 12-06]: **Never `git checkout` a file to revert a mutation while uncommitted work sits on it.** A mutation script failed silently (`python` is not on `PATH` in this environment — only `.venv/bin/python`), and the `git checkout --` that "reverted" it discarded a real uncommitted edit instead. Use a file copy as the restore point.
- [Phase 12-06]: **12-06 Task 4 (the live cutover) is deferred by the user and unstarted.** Criterion 6 is therefore proven **statically** against the served file, not in a real browser against the deployed service; two-machine identity continuity is untested; and `IDENTITY_SIGNING_SECRET` is unset in production, so the fleet mints per-process ephemeral identities. `/health`'s new `credentials.identity_signing` is what makes that visible.

### Pending Todos

None yet.

### Blockers/Concerns

- **OPEN — `ANTHROPIC_API_KEY` is revoked; no research run can complete in production.**
  Found by plan 11-04 on 2026-08-05, immediately after the Supabase cutover. `POST /research`
  returns **502** in 0.73s with `{"event": "run_failed", "error": "AuthenticationError"}`. Probed
  from inside the machine: `GET https://api.anthropic.com/v1/models` returns
  **HTTP 401 `{"type":"authentication_error","message":"API key is invalid."}`**. The key is
  well-formed (`len=108`, prefix `sk-ant-api03`, no stray whitespace) — Anthropic is rejecting it
  server-side. `VOYAGE_API_KEY` is fine (HTTP 200), which is why pgvector embedding still works.
  **This is NOT caused by the cutover and rollback would not fix it:** the secret digest
  `35d77d861c484d1a` is identical before and after release v5, and plans 11-01..11-03 touched
  nothing on the model-client path. Fix: `fly secrets set -a research-agent ANTHROPIC_API_KEY='...'`
  then confirm `POST /research` returns 200 with a `session_id`.
  **Does not block 11-05** — SC-2/SC-3 are demonstrated by `/health`'s `machine` key, which needs no
  model call. It does block "demonstrable to a stranger", and it is why `/metrics` currently
  advertises a **100% failure rate** (one row, the failed run above).

- **`/health` cannot see the outage that matters — Phase 12 material.** It reports
  `"credentials": {"anthropic": true}` for a revoked key, because it checks *presence*, not
  *validity*. So the liveness probe was green throughout an outage that takes the public demo down
  completely. Making it validate means an outbound call on every probe with its own budget
  implications — a design decision, deliberately not taken in 11-04.

- **OPEN — `main` is 21 commits ahead of `origin/main`; Phase 10 sign-off waits on a push.**
  Found by plan 10-05's SC-5 re-verification on 2026-08-05, after a `git fetch origin` so the
  count is against a current remote and not a stale tracking ref. `origin/main` sits at
  `804b873` (the Phase 10.5 close); `main` sits at `238d479`. Every one of the 21 commits is
  Phase 10 documentation — `.planning/`, `docs/`, `docs/adr/`, `README.md` — **including the
  phase base `715e9aa` itself**, which is also unpushed.
  `git diff --name-only origin/main..main -- src/ tests/ evals/ pyproject.toml Dockerfile fly.toml`
  returns **0 files**, so the code in Fly release v4, on `origin/main` and on `main` is
  identical and the deployed image is not stale. **This is not a deploy problem and must not be
  answered with `fly deploy`** — `git push` alone turns the row green, after which Phase 10 and
  `REQ-adr-promotion` can both be closed. Recorded as ❌ red in
  `10-VALIDATION.md` § Execution Record with `**Approval:** pending`.

- **LIVE SECURITY EXPOSURE — Phase 10.5.** `GET /sessions`, `GET /sessions/{id}`,
  `GET /sessions/{id}/trace` and `DELETE /sessions/{id}` have no `Depends(guard)`
  (`src/research_agent/service.py:514`, `:519`, `:533`, `:539`). Confirmed against the
  deployed service on 2026-08-04: an unauthenticated `GET /sessions` returned two real
  sessions with full task text, and two `DELETE` calls returned 204 from the open internet.
  `DEMO_TOKEN` does not close this — `check_token` runs only inside `guard`, which these
  paths never reach. The two exposed sessions were backed up and deleted with the owner's
  consent; two orphaned notes remain in the memory store (`/memory` exposes counts only,
  not content). Also: the SSE error handler leaks unredacted `str(exc)`
  (`service.py:263`) while `/health` correctly redacts using a helper that already exists.
  **✅ RESOLVED 2026-08-04 — Fly release v4.** `SESSIONS_TOKEN` was staged and deployed in the
  same release as the code. Verified from the open internet: all four endpoints return **401**
  anonymously and **200** with the token; `/`, `/health`, `/demo`, `/metrics` still 200;
  `/demo` still reports `token_required: false`; an anonymous browser research run still
  completes. The SSE handler redacts and truncates. The cutover also carried Phase 10's three
  pending commits, so the deployed tree now equals `main` and the deploy drift is gone.

  **Residual, owned by Phase 12 — session half RESOLVED 2026-08-05, plan 12-04.** Sessions now
  carry the identity that created them, `GET /sessions` is caller-scoped (a valid `SESSIONS_TOKEN`
  switches to the unscoped operator view), a foreign or expired session returns 404 identical to
  missing, and sessions expire 7 days after their last turn. The two pre-Phase-12 rows carry
  `owner=''`, resolve for nobody, and are swept on the first `create()` past their TTL — no manual
  deletion needed. **Still open:** the two orphaned *notes* from the 2026-08-04 deletions (Wave 4,
  12-05, which scopes and bounds notes), and `_index_json` does not advertise
  `DELETE /sessions/{id}`.

- **Other findings from codebase mapping, not yet phased.** Notes are written to a shared
  store with no tenant scoping (`graph.py:274`) and recalled into other visitors' runs
  (`graph.py:248`), and the critic reads the same untrusted text it polices
  (`graph.py:385`) — so injection can force `APPROVED`. ~~The daily spend cap counts only
  completed runs, so ~16 concurrent runs can overshoot the $5 cap roughly 3×.~~
  **RESOLVED 2026-08-05, plan 12-03** — the cap reserves `DEMO_RESERVED_RUN_USD` per in-flight
  run and check+insert is serialised under `pg_advisory_xact_lock`; a two-thread race against
  real Postgres asserts exactly one of two concurrent reserves is admitted. `pydantic` is unpinned — used by every API model, absent from
  `pyproject.toml`, floating in via FastAPI. `requires-python = ">=3.10"` while Docker and
  CI run 3.14, so the floor is untested. Voyage embedding spend is accounted nowhere.
  Decide in Phase 12 planning which of these belong there versus a later phase.

- **Six requirements are design reversals, not bug fixes.** Each needs a replacement guarantee decided in its own discuss-phase. Two are severe: Phase 17 (REQ-followup-live-search) retires the guarantee DESIGN.md calls "the single failure mode this whole pipeline exists to prevent"; Phase 16 (REQ-independent-critic-model) falsifies README's eval-judge rationale, which must be re-derived rather than inherited. See ROADMAP.md → Reversal register.
- **Docs assert a verified-false fact.** `docs/OPERATIONS.md` (~lines 49–51) says deploys run through Fly's GitHub integration and are not CI-gated. `fly releases -a research-agent` shows 3 releases, all from the owner's personal account — deploys are manual via `fly deploy -a research-agent`. Fixed in Phase 10.
- ~~**Live release is 3 commits behind `main`**~~ — **RESOLVED 2026-08-04.** The Phase 10.5 cutover
  (release v4) carried the README restructure, the `src/` reorganisation and its bugfix. The
  deployed tree now equals `main`. This satisfies Phase 10's SC-5 ahead of schedule; Phase 10 need
  only re-verify rather than redeploy.
- ~~**`docs/DESIGN.md` says three `MemoryStore` backends; there are four**~~ (json, memory, chroma, pgvector) — **RESOLVED 2026-08-05, plan 10-04.** The seams paragraph now reads "four implementations" and names pgvector alongside the other three.
- **Pricing has a shelf life — but the code already handles it.** Verified 2026-08-04:
  `src/research_agent/usage.py:59-76` has contiguous windows (`until=date(2026, 8, 31)` and
  `since=date(2026, 9, 1)`), so no rollover work is needed. What does need a decision before
  2026-09-01: `AGENT_MAX_RUN_COST_USD=1.00` and `DEMO_DAILY_USD_CAP=5.00` in `fly.toml` will
  bind roughly a third sooner once the same workload costs 50% more. Planning docs must not
  quote a single rate as permanent. Touches Phase 14.

- Acceptance criteria in `.planning/intel/requirements.md` are synthesis proposals, **not user-ratified** — firm them up per phase.
- Verified 2026-08-04: nothing cites `/healthz` (which 404s); `/health` is cited correctly. No fix needed, but re-verify in Phase 10 rather than assume.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Docs drift | `docs/OPERATIONS.md` still says the spend cap counts completed runs only and "this is not fixed" (12-03 closed it), describes `DEMO_RATE_LIMIT_PER_HOUR` as per-visitor-IP (12-03 rekeyed it to identity), and omits `DEMO_RESERVED_RUN_USD` from the env table | **CLOSED 2026-08-05 by 12-06 Task 1 (`ab54fb5`)** — all three corrected, plus `IDENTITY_SIGNING_SECRET` added, the `TRUST_FORWARDED_FOR` row marked log-only, and the same per-visitor-IP error found and fixed in `.env.example` | 12-04 |
| Live cutover | **12-06 Task 4** — `fly secrets set IDENTITY_SIGNING_SECRET`, `fly deploy`, then verify `/health` `identity_signing: true` on BOTH machines, cross-machine cookie verification (record both `FLY_MACHINE_ID`s), and criterion 6 in a real cleared-storage browser with the `ra_id` cookie HttpOnly/Secure/SameSite=Lax | Open — **deferred by the user**; unstarted, nothing touched live | 12-06 |

## Session Continuity

Last session: 2026-08-06
Stopped at: **Completed 13-02-PLAN.md — Wave 2 of Phase 13 is in.** Three commits on
`gsd/phase-13-embedding-migration`: `e7e2c06` (`src/research_agent/recall_golden.py` — 12 notes
over three owners with per-owner-distinct vocabulary sets and `"chroma retry"` under both alice and
bob as the tenancy probe; 8 queries including one that must return `[]`; `exact_scan_results`
running the production SELECT inside `Database.transaction()` under `SET LOCAL enable_indexscan =
off`; `indexed_results` for the sanity check alone; a store-agnostic `recall_delta`; and
`assert_tie_free`, which is the module's real guarantee), `5ab6a6e` (`embeddings copy --from --to
[--dry-run]` — one server-side `INSERT..SELECT` carrying text/embedding/owner/created_at, idempotent
on `(text, owner, created_at)`, four printed fidelity numbers with a nonzero exit on any of them,
zero statements against `--from`, no DDL at all in `--dry-run`, and `memory.validate_table_name()`
extracted so the store and the CLI share one rule), and `9262aeb` (the four gates).
Suite: **527 passed / 53 skipped plain, 579 passed / 1 skipped armed** (580/0 with
`REQUIRE_POSTGRES=1`) against 527/49 and 575/1. Collected 576 → 580; the four extra plain skips are
exactly the four new Postgres-gated tests, each `DATABASE_URL is not set` — **the plain run is not
evidence for this plan**. `ruff check` clean. Nothing deployed; no push.
**Falsified, not assumed — six mutations, all red**, tree clean after each. Perturbing one copied
vector, dropping `owner`, dropping `created_at`, deleting a row from the new table, adding two
same-vocabulary notes under one owner, and removing the `NOT EXISTS` skip clause. Two are recorded
with caveats rather than as clean wins: the `owner` mutation trips the *command's own* gate before
the golden comparison is reached (a second variant with the return code relaxed shows all eight
queries deltaing, alice's and bob's rows both surfacing in the unowned bucket), and the idempotency
mutation is red only on the **second** pass — 13-01's lesson applied rather than re-learnt.
**Three gates the plan specified were weaker than they looked and were strengthened before commit:**
the `INSERT..SELECT` grep matches a docstring on the unmodified tree, the recall-equality assertion
is green over two sets of empty results, and a row-count non-destructive check is green against a
table whose contents were replaced.
**README reviewed, deliberately unchanged.** Line 209's "changing embedding model … can't migrate
for you" is still true: this wave copies vectors, it does not re-embed. Wave 3 owns that sentence.
Resume file: None

Superseded — previous session: **Completed 13-01-PLAN.md — migrate.py repaired and proven** (owner
and created_at carried, owner-aware dedup keyed on a datetime, the expired-session skip printed, and
the module's first tests; commits `6516c23`, `33bc377`, `91b59d1`, `7b8b312`; suite 527/49 plain,
575/1 armed; the fourteenth vacuous gate found and repaired).

Superseded — earlier session: **Executed 12-06-PLAN.md Tasks 1–3 — Wave 5's code and docs are in; Task 4 is deferred.**
Three commits on `gsd/phase-12-caller-identity`: `ab54fb5` (**ADR-0007**, `Accepted — supersedes
ADR-0006`, `**Source:** Phase 12` — the reversal, the fairness ceiling, the cookie transport with its
CSRF reasoning, 404-not-403, `TRUST_FORWARDED_FOR` demoted; and a `### Carried forward from ADR-0006`
section naming all four surviving parts, with `SESSIONS_TOKEN` recorded as an **inversion** rather
than a survival. ADR-0006: status line only, a 1-line diff. `docs/adr/README.md`: the 0007 row, both
records' cells, and the "All six records are Accepted" sentence corrected. **README's "rate-limited,
not authenticated" bullet**, deferred by waves 1–4, rewritten. `/health` reports
`credentials.identity_signing`, presence never value. `.env.example` + `docs/OPERATIONS.md`:
`IDENTITY_SIGNING_SECRET`, plus the two claims `deferred-items.md` assigned here and two more found
alongside), `1c79677` (the demo page — footer sentence, a `#limits` line naming both scopes, an
owned-session `<details>` **built in script and inserted only while it has rows**, a side-effect-free
`renderTurnCard()` whose badges are conditional on field *presence* so a stored turn gets none rather
than a fabricated `$0.0000`, and a resume flow that posts follow-ups to the existing
`/sessions/{id}/ask/stream`), and `d7d06e2` (nine criterion-6 static gates).
Suite: **526 passed / 47 skipped plain, 572 passed / 1 skipped armed** against 516/47 and 562/1 —
**+10 in both arms and ZERO new skips**, the first wave of this phase with nothing to justify: 1 new
health test + 9 page gates, all static-file or in-memory. `ruff` clean.
**The two-delta claim is now measured.** The served markup's visible text runs were diffed against the
pre-phase file: the whole phase's markup delta is **one run**, the footer sentence. That baseline is
frozen in `page_first_paint_text_is_frozen`; the `#limits` delta is not a markup delta (the `<p>` ships
empty and is filled from `/demo`) and is gated separately.
**Falsified, not assumed — 25 mutations, 24 red**, tree byte-identical after each batch. Three of the
plan's own gates were vacuous as specified and were fixed before commit: the session list could be
appended unconditionally, `renderTurnCard` could go back to fabricating a cost, and a **textless**
interactive element could be added before the first question — all three stayed green. Then the fix
for the first was **itself** vacuous (searching all of `syncMine()` for `"rows &&"`, which the
`else if (!rows && …)` branch satisfies): this project's **twelfth** vacuous gate and the first written
by the wave that found it. The one mutation that stays green — changing an `--accent` value inside
`:root` — is recorded as correctly green, since AC7 freezes which properties new rules use, not the
palette's values; the falsifying mutation for that gate is *hardcoding* a colour, which is red.
**Task 4 (T-06-4, `checkpoint:human-action`) is DEFERRED BY THE USER and unstarted.** No Fly secret
set, no `fly deploy`, live service untouched, nothing pushed. Consequences: criterion 6 is proven
**statically against the served file, not in a real browser**; two-machine identity continuity is
untested; and with `IDENTITY_SIGNING_SECRET` unset the fleet mints per-process ephemeral identities,
which `/health`'s new field now makes visible. Both `REQ-demo-authentication` and
`REQ-store-lifecycle-and-ownership` therefore stay **Pending** — both are deployed-behaviour
requirements, and 12-05 handed the second one here explicitly noting it depends on the first.
Resume file: None

Superseded — previous session: **Completed 12-05-PLAN.md — Wave 4 of Phase 12 is in.** Three commits on
`gsd/phase-12-caller-identity`: `27e46bc` (`add(text, owner="")` / `query(..., owner="")` on the
`MemoryStore` ABC and all four backends, with owner matching EXACT — `owner=""` retrieves only
`owner=""` notes and never acts as a wildcard; `NOTE_TTL_DAYS` (7, deliberately the same number as
`SESSION_TTL_DAYS`) enforced by a lazy filter in `query()` plus an opportunistic sweep in `add()`;
`owner`/`created_at` keys on the brute-force entry dicts, chroma metadata with a `where` owner
filter and a Python TTL post-filter, and `ALTER TABLE … ADD COLUMN IF NOT EXISTS owner` appended to
pgvector's advisory-locked lazy DDL — `created_at` was already there and is NOT re-added; chroma ids
became uuids because a sweep makes `count()` non-monotonic and a repeated id is an upsert), `bb9e80f`
(`AgentState["owner"]`, `initial_state(task, owner="")`, `followup_state(previous, question,
owner="")` with carry-forward and a `.get` for pre-Phase-12 state blobs, `researcher_node` scoping
BOTH `store.query` and `store.add`, and all four run-starting handlers passing the identity they
already resolve), and `8a8582e` (README's "Notes grow without bound" bullet — false in both halves —
`NOTE_TTL_DAYS` into OPERATIONS and `.env.example`, and the test count in the two places it appears,
one of which had been stale at 480 since 12-01).
Suite: **516 passed / 47 skipped plain, 562 passed / 1 skipped armed** against 506/45 and 550/1.
Collected 551 → 563, +12 in both arms. The two extra plain skips are exactly the **pgvector** arms of
`note_scoping` and `note_ttl` (`DATABASE_URL is not set`); the **chroma** arm collects and passes in
both runs, which is the difference between SC-5 being true and SC-5 being claimed. `ruff` clean.
Nothing deployed; no push.
**Falsified, not assumed — 21 mutations, all reverted:** all nine ways to break the store layer (owner
filter, TTL filter and sweep, per backend family) go red on exactly the arms they own; both
`researcher_node` call sites, the `AgentState` key, the follow-up carry-forward and all four handlers
go red. Two mutations that stayed green are recorded as findings, not holes: renaming a key inside the
shared `_summarise` helper cannot fail a gate that compares two backends, and an unread extra column
in the SQLite query is not read by `_summarise`; the falsifying mutation for that gate is a
one-backend dialect drift, which is red.
**The eleventh vacuous gate, and its second-order form.** The plan's end-to-end injection test, written
over `/research` only, stayed GREEN when `owner=` was deleted from `/research/stream` — the route the
demo page actually calls. It is now parametrized over both. Worse, the obvious structural fix ("the
handler source contains `owner=`") is ALSO vacuous, because three of the four handlers pass
`owner=owner` to `store.create` or `reserve_or_429` as well; the gate parses the state-construction
call with balanced parentheses instead. Both mutations are red.
**Owed to 12-06:** `REQ-store-lifecycle-and-ownership` is now delivered in code in both halves
(sessions in 12-04, notes here) but stays **Pending** — 12-06 carries it in its frontmatter alongside
`REQ-demo-authentication`, which it explicitly depends on and which is only demonstrable at the
deployed cutover. `docs/OPERATIONS.md` still carries the two claims 12-03 falsified (see Deferred
Items). README's "rate-limited, not authenticated" line at ~210 remains Wave 5's, untouched on
purpose. Task 3 of this plan produced no code change: all four route-guard assertions and the
cross-backend metrics invariant already existed, pass after the owner threading, and were mutated red
— and one of its acceptance criteria names `check_daily_cap`, a function 12-03 retired, where the
live assertion covers both current ways to acquire the cap and is strictly stronger.
**A trap worth carrying forward:** `addopts = "-q"` is already set, so passing `-q` again on the
command line makes pytest doubly quiet and it prints **no `N passed` summary line at all**. Run
`.venv/bin/pytest` with no `-q`.
Resume file: None

Superseded — previous session: **Completed 12-04-PLAN.md — Wave 3 of Phase 12 (session owner, derived 7-day expiry, the operator dual-mode, one 404 for missing/expired/foreign; commits `82af2cc`, `b87a088`, `6b52781`; suite 506/45 plain, 550/1 armed; the walker strengthened after its plan-specified form proved vacuous against deleting the router-level dependency).**

Superseded — earlier session: **Completed 12-03-PLAN.md — Wave 2 of Phase 12 is in.** Five commits on
`gsd/phase-12-caller-identity`: `fe50a83` (the `LimitsStore` ABC with `InMemoryLimits` and
`PostgresLimits`; two new tables under the lazy advisory-locked `ensure_schema`; `get_limits_store()`
defaulting on `DATABASE_URL` like sessions and metrics), `9db9125` (`DEMO_RESERVED_RUN_USD`;
`enforce` reduced to token + identity-rate; `reserve_or_429` carrying the verbatim
"Read-only endpoints still work." 429; `app.state.limits` + the `get_limits` accessor; the reserve
in all four spending handlers and `settle` after every `metrics.record` in `_execute` and
`_stream`; `status()` extended additively with `rate_limit_scope` and `reserved_run_usd`),
`40d2de9` (the doubled gate — parametrized four-route 429 plus the `inspect.getsource` structural
invariant with a non-vacuity floor; **falsified by deleting `ask`'s reserve and observing both go
red**), `7fb1c72` (the two-thread `cap_reservation_no_overshoot` race and the stale-reclaim test
against real Postgres on `:54329`, using two `_dsn_tagged` handles so the threads hold separate
pool connections), and `fd5267f` (README: the spend-cap known-limitation entry rewritten to what
is now true plus the residual it leaves — the 900s stale window and estimate accuracy — and
504 → 534 tests).
Suite: **493 passed / 41 skipped plain, 533 passed / 1 skipped armed** against 467/37 and 503/1.
Collected 504 → 534; the four extra plain skips are exactly the Postgres-gated `test_limits.py`
tests, each reporting `DATABASE_URL is not set` — so the plain run is **not** evidence for the
race gate. `ruff` clean. Nothing deployed; no push. `REQ-demo-authentication` stays Pending until
the Wave 5 cutover.
**Owed to 12-04/12-05:** `status()` now exposes `rate_limit_scope` and `reserved_run_usd` for the
UI wave to render, and `README.md`'s "rate-limited, not authenticated" line at ~210 is now
half-false — the limits *do* identify callers — and is Wave 5's to correct.
Resume file: None

Superseded — previous session: **Completed 12-02-PLAN.md — Wave 1 of Phase 12 is in.** Four commits on
`gsd/phase-12-caller-identity`: `ea204cd` (17 failing identity unit tests, TDD RED observed at
collection), `f7e2494` (`identity.py` — stdlib-HMAC `v1.<uuid4hex>.<sha256>` mint/verify with
`compare_digest`, never-raise verify, per-call `IDENTITY_SIGNING_SECRET` with a cached
per-process ephemeral degrade and one warning, `set_cookie_value` with the LOCKED attributes,
and the pure-ASGI `IdentityMiddleware`), `39ea349` (`app.add_middleware(IdentityMiddleware)`;
`make_client` on `base_url="https://testserver"`; `mint_cookie()` seam; 7 API tests proving the
mint lands on the SSE stream, the FileResponse demo page and a JSON route, that a valid cookie
is never re-minted, that a tampered cookie gets 200-not-401 plus a fresh mint, and that
`request.state.identity` is populated before any handler), and `a828ef1` (README 480 → 504).
Suite: 467 passed / 37 skipped plain, 503 passed / 1 skipped armed — +24 in both runs, every one
named (17 unit + 7 API), skip counts unchanged. `ruff` clean. Zero JS changes; nothing deployed;
no push. `REQ-demo-authentication` stays Pending until the Wave 5 cutover proves it deployed.
Resume file: None

Superseded — previous session: **Completed 12-01-PLAN.md — Wave 0 of Phase 12 is in.** Three commits on
`gsd/phase-12-caller-identity`: `0dbf46f` (chromadb into the dev extra by composing the existing
chroma extra, pin unchanged; the notes fixture parametrizes json/memory/chroma/pgvector and the
chroma arm passes all 6 note contract tests locally), `ea1bb8f` (`Database.transaction()` — one
pooled connection, `conn.transaction()`, cursor on that same connection; `CAP_LOCK_KEY` exported
for Wave 2; 4 tests proving commit-visible, rollback-absent, and the advisory lock held against a
rival while open then taken freely afterwards, run green against local Postgres :54329), and
`1cd461f` (README 470 → 480 tests, ~10s → ~25s). Suite: 443 passed / 37 skipped plain,
479 passed / 1 skipped armed — every delta from the 436/34 and 469/1 baselines named. `ruff`
clean. Nothing deployed; no push.
Resume file: None

Superseded — previous session: **Completed 11-04-PLAN.md — production is on Supabase, and every step is still
reversible.** Task 1 (provisioning) was done by the operator beforehand and was verified, not
redone. One `fly deploy -a research-agent` landed the branch code and the staged `DATABASE_URL` in
**release v5** — deliberately *not* `fly secrets deploy`, which would have put the new DSN on the
pre-pool v4 image. `/health` returns `PostgresSessionStore` / `PostgresMetricsStore` /
`PgVectorMemoryStore`, `dependencies: ok`, `unreachable: []`, `machine: 78156d2c32d738`, host
`aws-0-ap-southeast-2.pooler.supabase.com` with no password and no project ref; `/ready` 200;
`/`, `/demo`, `/metrics` 200; `/demo` still `token_required: false`.
**Measured** (Assumptions A1 and A2 discharged): connect+TLS **119.2 ms**, `SELECT 1` p50
**2.73 ms** / p95 **6.37 ms**; the three real store probes 2.84 / 3.23 / 3.39 ms p50, worst
observed 6.90 ms against a 3000 ms `HEALTH_PROBE_BUDGET` — ~435× headroom, so the `/health`
arithmetic needs no redoing before 11-05. `pg_stat_activity` **15–16** of 60 (5 under the app's
user: 4 idle + 1 active, i.e. `PG_POOL_MAX_SIZE=5` exactly). `/health` wall clock 0.270–0.427 s
over eleven samples. **Zero** `prepared statement` / `_pg3_` / `PoolTimeout` / `OperationalError`
errors over **74** probe-triggering responses across ~9 minutes — Pitfall 3 discharged in
production, where psycopg's threshold-of-5 would actually bite.
**pgvector proved properly:** it lives in the `extensions` schema (the case 11-02 flagged as
unreachable), the lazy advisory-locked DDL created `sessions`, `runs`, `research_notes` and the
HNSW index against an empty database, and a real Voyage-embedded note was inserted and retrieved
by cosine similarity. Also found: Supabase's *default* `search_path` already includes
`extensions`, so 11-01's `_configure()` callback is untested insurance rather than a fix for an
observed break — recorded so nobody misreads the rationale.
**Session round trip** proved at the store layer (`fly ssh console`), not through HTTP, because
every HTTP write path runs the model first: session `2c737084599646a8b0fcc0ec91c92ab2` created in
3.2 ms, read back by id in 2.8 ms with task and draft matching, appended to, listed, deleted. All
probe rows cleaned up afterwards; the one genuine failed production run was deliberately left.
**Nothing irreversible:** `git status --porcelain fly.toml` empty, `[[mounts]]` present,
`min_machines_running = 1`, one machine, volume `vol_vdegz1021w669gx4` attached, and `/data` still
holds 1 session / 3 runs / 3 notes — exactly the pre-cutover `/health` counts. The rollback
(`fly secrets unset DATABASE_URL`) is **untested**; everything it depends on is verified.
**Knowingly given up, now visible:** cumulative `/metrics` history. `spent_24h_usd` went
0.2289 → 0.0 and `/metrics` reads `{"total": 1, "failed": 1, "failure_rate": 1.0}`.
**BLOCKED, separately and not by the cutover:** `ANTHROPIC_API_KEY` is revoked (HTTP 401 from
Anthropic), so no research run completes. See Blockers.
Resume file: None

Superseded — previous session: **Completed 11-03-PLAN.md — the deploy guards are armed and the runbook is honest.**
Three tasks, three commits (`9b4afe6`, `53fb6a0`, `1991f7d`). Both mount-conditional guards in
`tests/test_deploy_config.py` used to `pytest.skip()` when `[[mounts]]` was absent, so 11-05's
mount removal would have silenced them with CI green; both now assert in **both** topologies and
`grep -c 'pytest.skip'` is `1` (the `fly` fixture's legitimate no-`fly.toml` skip), down from `3`.
The stateless arm requires more than the absence of the `*_DB_PATH` keys — it requires
`SESSION_BACKEND=postgres`, `METRICS_BACKEND=postgres`, `VECTOR_STORE=pgvector`, asserted on the
parsed `[env]` table because `VECTOR_STORE_PATH` contains the string `VECTOR_STORE`. Two new
guards: `DATABASE_URL` must not appear in the committed `[env]`, and a `-k runbook` test keeps
`fly postgres create`/`attach` out of `fly.toml` (recorded red against `git show HEAD:fly.toml`).
Four falsification checks run against scratch files, all four observed failing, plus a passing
control; check 1 was also fed to the old guard, which returned `Skipped` where the new one raises
`AssertionError` — the disarm-by-deletion demonstrated rather than argued.
`fly.toml`'s footer, health-budget, `auto_stop_machines`, `primary_region` and concurrency
comments were rewritten for the external-Supabase path, and `docs/OPERATIONS.md` carries the
ordered cutover, the fail-closed pins, the start-clean tradeoff, the kept volume and SC-6's
four-way timeout semantics. **Every `fly.toml` change is a comment** — `git diff -U0 fly.toml`
shows no changed non-comment line, and `tomllib` confirms `min_machines_running == 1`, `mounts`
present and `SESSION_DB_PATH` in `[env]`. Suite **436 passed, 34 skipped** (+2 tests, skip count
unchanged); `ruff` clean.
**Owed to 11-05:** removing `[[mounts]]` is now a four-part change or the tests fail — the three
`*_DB_PATH` vars out, the three pins in, `min_machines_running` ≥ 2. And `11-VALIDATION.md`'s
skip-count invariant still says 28; it is 34.
Resume file: None

Superseded — previous session: **Completed 11-01-PLAN.md — `db.py` is pooled.** Three tasks, three commits
(`8c7a145`, `9e46158`, `5df970b`). `psycopg-pool==3.3.1` pinned and installed; five new env
readers (`PG_POOL_MIN_SIZE`, `PG_POOL_MAX_SIZE`, `PG_POOL_TIMEOUT`, `PG_STATEMENT_TIMEOUT`,
`PG_TCP_USER_TIMEOUT`); one `ConnectionPool` per DSN behind a claim-refcounted registry, shared
by all three stores; the RLock and single `_conn` deleted; `prepare_threshold=None`,
`statement_timeout`, `tcp_user_timeout`, keepalives and a `search_path` `configure` callback all
reaching the connection; `PoolTimeout`/`PoolClosed` re-raised ahead of the retry; DDL under
`pg_advisory_lock(3895545195)` on one connection with the unlock's result checked. `tests/test_db.py`
is new (27 tests, no server needed). Suite **415 passed, 28 skipped** against a 388/28 baseline —
skip count unchanged, so Postgres coverage was extended rather than disarmed. `ruff` clean.
`fly.toml` untouched. Both behavioural gates were mutated, observed red and reverted; the table
is in `11-01-SUMMARY.md` § Falsification Checks.
**Owed to 11-02:** `test_the_connection_recovers_from_being_dropped` reaches into `store.db._conn`,
which this plan deletes. It is Postgres-gated so it skips locally, but it **will fail in CI**.
Repairing it, wiring `close_all_pools()` into the lifespan, the `/health` per-probe deadline and
the real-server lock/pgvector tests are all 11-02's.
Resume file: None

Superseded — previous session: **Completed 10-05-PLAN.md — the phase gate battery.** Every gate in
`10-VALIDATION.md` was run as written on macOS and recorded with its literal output: five ADRs
with `Status` lines and Nygard sections, all five citing `docs/DESIGN.md` and all five linked
back from it, ADR-0006 verified separately (exists, `Accepted`, `DEMO_TOKEN` present, zero
`Promoted from`) so the `000[1-5]` globs stayed as written, `GitHub integration` at zero,
`Deploys are manual` and `enforce_admins` present, four backends with `pgvector`, no unpaired
`$2/$10`, `src/` byte-identical to `715e9aa`, the suite at exactly 388 passed / 28 skipped, and
`.venv/bin/ruff check .` clean. Four non-vacuity controls were run and recorded. SC-5 was
re-verified read-only — release v4 `complete` under the owner's personal account, `/`, `/health`,
`/demo`, `/metrics` all 200 — with **nothing redeployed**. One row is ❌ red: SC-5 step 3
returned `21` for `origin/main..main`, so `**Approval:** pending`. ROADMAP's stale Phase 10.5 row
was reconciled to 5/5 Complete. `REQ-adr-promotion` is left Pending with the blocker named.
Resume file: None

Superseded — previous session: **Completed 10-04-PLAN.md.** SC-2, SC-4 and the DESIGN half of SC-6 are done, so
every corrective criterion in Phase 10 has now landed. `docs/DESIGN.md` names four
`MemoryStore` implementations including pgvector; its pricing paragraph carries both windows
as `2026-08-31` / `2026-09-01` on one line with `/pricing` as the live source and no
"this month" phrasing; and its five promoted paragraphs each end with a `Recorded as ADR-000N`
link, with `adr/README.md` linked from the preamble. All five paths resolve on disk and the
reverse citation from each record back to `docs/DESIGN.md` still holds. `docs/OPERATIONS.md`
and `README.md` remain as 10-03 left them; `docs/adr/` remains the complete six-record set
from 10-01/10-02. Only plan 10-05 (phase-wide verification, including the SC-5 live re-check)
remains. (Phase 10.5 remains complete and shipped as Fly release v4.)
Resume file: None

**Carry forward — findings that outlive this phase:**

- **`DEMO_TOKEN` must stay UNSET in production.** `guard` checks it and fronts
  `POST /research/stream`; the demo page sends no token header, so setting it 401s every
  anonymous visitor and takes the public demo offline. Session endpoints use `SESSIONS_TOKEN`
  instead (sent as `x-demo-token`, fails closed at 403 when unset). Any future phase that
  touches auth must not "tidy" these into one variable.

- **Any assertion over `app.routes` must walk recursively.** fastapi 0.141.1 leaves a
  `fastapi.routing._IncludedRouter` in `app.routes` rather than flattening. A flat scan sees
  only the two `@app.post` ask routes — both legitimately guarded — computes an empty
  unguarded list, and reports a *clean* sessions tree while the four leaking routes stay
  invisible. Use `api_routes()` in `tests/test_service.py` and always assert a route count
  first. Two pre-existing tests had this bug.

- **`docs/adr/README.md` is owned by plan 10-01 and is already complete.** It carries index
  rows for all six records with their titles and expected superseders. Plan 10-02 wrote the
  record files 0003–0006 without editing the index; every row now resolves to a file on disk.

- **`docs/DESIGN.md` is now a two-way index into `docs/adr/`.** Any future phase that renames
  an ADR file must update the five `adr/000N-slug.md` links in `docs/DESIGN.md` as well as the
  index rows in `docs/adr/README.md`. The check is
  `for f in $(grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md | sort -u); do test -f "docs/$f" || echo "DANGLING $f"; done`.

- **The `000[1-5]` ADR gates deliberately exclude 0006.** Records 0001–0005 are DESIGN.md
  promotions and are gated for a `DESIGN.md` citation; ADR-0006 has none by design. Widening
  those globs to `000[1-6]` would make the citation gate fail correctly-written work.

- **Deploys are manual and now proven so.** `fly secrets set --stage` then one `fly deploy`
  puts secret and code in the same release — required whenever a control fails closed.

- **A `@contextmanager` cannot retry from inside the caller's `with` body.** Yielding a second
  time after `gen.throw` raises `RuntimeError: generator didn't stop after throw()`, which fails
  the call *and* destroys the original exception. This is why `db.cursor()` retries only the
  checkout and `db._read()` owns the statement-level retry. Anyone "improving" the retry should
  read both docstrings first.

- **`HEALTH_PROBE_BUDGET` is a new tunable**, 3.0s default with a 0.1 floor, and it has no
  `fly.toml` entry on purpose — the default is the intended production value. 11-05 should
  confirm the resulting 9s ceiling against the real check timeout in `fly.toml`.

- **`fly ssh console -C` runs no shell, and the container has no `curl`.** Heredocs are passed as
  literal argv. base64-encode the script and run
  `python -c "import base64;exec(base64.b64decode('...'))"` — quoting-safe, and it keeps any
  credential inside the machine.

- **`Session.id`, not `Session.session_id`.** The `session_id` key exists only in `summary()`'s
  dict. And `research_notes`'s text column is `text`, not `content`. Both cost a failed probe in
  11-04.

- **`addopts = "-q"` is already set in `pyproject.toml`.** Passing `-q` on the command line makes
  pytest doubly quiet and it prints **no `N passed` summary line at all** — a run that looks like it
  produced no result has produced every result except the one you were reading for. Run
  `.venv/bin/pytest` with no `-q`.

- **`python` is not on `PATH` in this environment; `.venv/bin/python` is.** A `python - <<'PY'`
  heredoc fails with `command not found` and, in a `&&` chain, silently skips the step it was meant
  to perform. This cost an uncommitted edit in 12-06 when the "revert" that followed a no-op mutation
  was a `git checkout --`. Restore from a file copy, not from git, while work is uncommitted.

- **The demo page now has a frozen first-paint baseline.** `tests/test_service.py` freezes the served
  markup's visible text runs AND its tag census, plus the font-size/weight/shorthand sets and the
  literal-colour set. Any future phase touching `src/research_agent/static/index.html` must update
  those baselines deliberately — they are measured constants, and a failure is the gate working.

Next: **12-06 Task 4** — the deferred live cutover. Generate the secret, `fly secrets set
IDENTITY_SIGNING_SECRET=…` (app-wide, so both machines verify each other's cookies), `fly deploy`,
then verify `/health` reports `identity_signing: true` on BOTH machines, that a cookie minted on one
verifies on the other (record both `FLY_MACHINE_ID`s), and criterion 6 in a real cleared-storage
browser. Only after that can `REQ-demo-authentication` and `REQ-store-lifecycle-and-ownership` be
checked off. Then the phase PR — one PR for the whole phase, no direct push to `main`.
Note the standing blocker below: `ANTHROPIC_API_KEY` is revoked in production, so a research run
still cannot complete there regardless of this cutover.

Superseded — Next was: **11-05** — remove `[[mounts]]` and the three `*_DB_PATH` vars, add the three backend pins,
raise `min_machines_running` to 2 and `fly scale count 2`. This is the point of no return for
per-machine state, and 11-04 has cleared its precondition: the database is reachable and proven.
`tests/test_deploy_config.py` makes that a four-part change or it fails. Also owed there:
`11-VALIDATION.md`'s skip-count invariant still says 28 and must become 34, and the branch
`gsd/phase-11-multi-machine-postgres` (waves 1–4) is unpushed — land it via a **pull request**,
not a push, since `enforce_admins` is `false`.
