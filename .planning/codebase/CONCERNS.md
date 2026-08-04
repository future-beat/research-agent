# Codebase Concerns

**Analysis Date:** 2026-08-04

Findings are ordered by severity. Each carries a file:line citation. A final
section records the pre-supplied concerns that were **verified as already
handled**, so no one re-opens work that is done.

The service is publicly reachable at `research-agent.fly.dev` with real API
spend attached, so "reachable without a key" is treated as the operative
severity multiplier throughout.

---

## Severity 1 — Critical

### Every session is world-readable, and the service hands out the IDs

**Risk:** Any visitor can read every other visitor's research question, full
report, and entire follow-up conversation.

**Files:**
- `src/research_agent/service.py:514` — `GET /sessions`, no `Depends(guard)`
- `src/research_agent/service.py:519` — `GET /sessions/{session_id}`, no guard
- `src/research_agent/service.py:533` — `GET /sessions/{session_id}/trace`, no guard

**On the guessability question, answered honestly:** session IDs are
`uuid.uuid4().hex` (`src/research_agent/sessions.py:161` and `:248`) — 122 bits
of entropy, cryptographically unguessable, and *not enumerable by brute force*.

That is irrelevant here. `GET /sessions` (`service.py:514`) returns the 50 most
recent session IDs to anyone who asks, so an attacker never has to guess. The
unguessable ID is handed over on request. Two unauthenticated calls — list, then
fetch — dump the service's recent contents.

`Session.summary()` (`sessions.py:82`) is careful to exclude the state blob from
the listing, and the docstring at `sessions.py:83-84` shows the exposure was
considered. But the listing still includes `task` (the verbatim research
question) at `sessions.py:90`, and `GET /sessions/{id}` (`service.py:519-530`)
returns `latest_answer` and the full `conversation` anyway.

**Current mitigation:** None. `guard` is applied only to the four spending
endpoints (`service.py:447`, `:461`, `:473`, `:496`). The read path is
deliberately open — `service.py:136-140` and `limits.py:24-26` both argue
read-only endpoints cost nothing and are needed to diagnose a refusing service.
That reasoning is sound for `/health` and `/metrics`. It was extended to
`/sessions`, which is not an ops endpoint and does not cost nothing to expose.

**The trap:** setting `DEMO_TOKEN` does **not** close this. `check_token()`
(`limits.py:172-180`) runs inside `enforce()` (`limits.py:208`), which is only
reached via `guard`. Locking the demo down still leaves every stored report
readable. Anyone assuming `DEMO_TOKEN` secures the service is wrong.

**Fix approach:** Either return an owner-scoped listing, or drop `GET /sessions`
to IDs the caller already holds, or put the whole `/sessions` tree behind
`guard`. Cheapest correct step for a portfolio demo: gate `GET /sessions`,
`/sessions/{id}` and `/trace` behind `Depends(guard)` and keep `/health`,
`/ready`, `/metrics`, `/demo`, `/pricing` open — that preserves the stated
diagnosability goal exactly while closing the read path.

---

### Anyone can delete anyone's sessions

**Risk:** Unauthenticated, unrate-limited, irreversible destruction of all
stored sessions.

**Files:**
- `src/research_agent/service.py:539` — `@app.delete("/sessions/{session_id}", status_code=204)`

`delete_session` carries no `dependencies=[Depends(guard)]` and no ownership
check. It calls `store.delete()` (`sessions.py:189` SQLite, `:267` Postgres)
directly. Combined with the finding above, the full attack is a two-line script:
`GET /sessions` for the IDs, then `DELETE` each one.

Because it is outside `guard`, it is not even rate-limited — `check_rate_limit`
(`limits.py:183`) never runs for it. There is no soft delete and no backup, so
the sessions are gone.

**Impact for a portfolio project:** a visiting employer clicking through the
demo could find it empty because someone wiped it. This is a visible defect, not
just a theoretical one.

**Fix approach:** Add `dependencies=[Depends(guard)]` at minimum. Correctly,
deletion should require the same ownership proof that reading should.

---

### Web content reaches the writer *and* the critic unfenced, and persists into other visitors' runs

**Risk:** Indirect prompt injection with a cross-visitor persistence channel.

**Files:**
- `src/research_agent/graph.py:260` — researcher enables the `web_search` tool
- `src/research_agent/graph.py:272-273` — raw tool output stored as `research_notes`
- `src/research_agent/graph.py:298` — notes interpolated into the writer prompt
- `src/research_agent/graph.py:385` — the same notes interpolated into the critic prompt
- `src/research_agent/graph.py:349-350` — notes and source report into the responder prompt
- `src/research_agent/graph.py:274` — `store.add(f"[{state['task']}] {notes}")`
- `src/research_agent/graph.py:248` — `store.query(...)` recalls those notes into later runs

Three compounding problems, in increasing order of seriousness.

**1. No fencing.** Fetched page text is f-string-concatenated straight into the
prompt (`graph.py:298`). There is no delimiter, no "treat the following as
untrusted data" instruction, and no structural separation between the notes and
the actual instruction (`"Only state things supported by the research notes"`,
`graph.py:301`). A page that says "ignore previous instructions" is
indistinguishable from a research note.

**2. The critic reads the same poisoned text.** The critic is the safety
control — it decides `approved` at `graph.py:396` by checking
`verdict.startswith("APPROVED")`. But the critic's prompt is built from the same
untrusted notes (`graph.py:385`). Content that can steer the writer can equally
instruct the critic to emit `APPROVED`, which defeats the grounding check that
is the entire premise of the pipeline. The control and the thing it controls
share an attack surface.

**3. Persistence across visitors — the serious one.** Every run writes its notes
into the shared memory store (`graph.py:274`), and every *subsequent* run by
*any* visitor recalls the top-3 nearest notes into its researcher prompt
(`graph.py:248-252`). There is no per-session, per-user, or per-tenant scoping
anywhere in `MemoryStore` (`memory.py:110-141` — the contract is `add`, `query`,
`__len__`, `describe`, with no namespace parameter).

So a single visitor who asks a question that surfaces an attacker-controlled
page plants text that is served into strangers' runs indefinitely. This is
stored injection, not reflected. It outlives the session, survives restarts
(persisted at `memory.py:227-233`), and there is no eviction path to clean it up
(see Severity 2). Clearing it means deleting the store by hand.

**Fix approach:** In rough order of value per unit effort —
(a) fence the notes in the writer/critic/responder prompts with explicit
delimiters and an untrusted-data instruction;
(b) make the critic's verdict parse stricter than `startswith` and consider
giving the critic only the draft plus a hash-checked notes summary;
(c) add a namespace/scope argument to `MemoryStore.add`/`query` so recall cannot
cross session boundaries — this also gives the eviction story somewhere to hang.

---

## Severity 2 — High

### The SSE error event leaks unredacted exception text, including DSN passwords

**Risk:** Credential disclosure over an endpoint reachable without a key.

**Files:**
- `src/research_agent/service.py:263` — `yield _sse("error", {"error": type(exc).__name__, "detail": str(exc)})`
- `src/research_agent/service.py:337-344` — `_redact()`, which is *not* applied here
- `src/research_agent/service.py:356-362` — `_probe()`, which *does* apply it

The codebase already understands this exact risk. `_redact` exists specifically
because "Connection errors echo back the parameters they were given" and "A DSN
password in a health response is a credential leak to anyone who can curl the
service" (`service.py:340-343`). `_probe` applies it and also truncates to 160
characters (`service.py:361`).

The SSE error path does neither. `str(exc)` goes out raw and untruncated. A
`psycopg.OperationalError` raised while persisting a run — exactly the class
`db.py:102` is written to expect — carries the full DSN including the password.
`on_complete` (the session write) runs inside the `try` at `service.py:253`, so
a database failure at persist time lands directly in this handler.

**Test coverage gap that hid it:** `tests/test_service.py:681-689` asserts
redaction works — but only through the `/health` probe path. Nothing asserts the
SSE error event is redacted. The helper is correct and tested; the second call
site was never wired to it.

**Fix approach:** One line — `"detail": _redact(str(exc))[:160]` at
`service.py:263`. Then add the missing test alongside `test_service.py:681`.

---

### The daily spend cap can be overshot several-fold by concurrent runs

**Risk:** Real money. The $5.00 rolling cap is not enforced against in-flight
spend.

**Files:**
- `src/research_agent/limits.py:194-205` — `check_daily_cap` reads `metrics.spend_since(...)`
- `src/research_agent/service.py:222` — the run is recorded **after** `graph.app.invoke` returns
- `src/research_agent/service.py:254` — same, on the streaming path
- `fly.toml:59` — `hard_limit = 16`

`spend_since` (`metrics.py:320` SQLite, `:379` Postgres) sums the `runs` table.
Rows are only written once a run *finishes* (`service.py:222`, `:254`). A
research run takes tens of seconds (`service.py:15`).

So the cap is checked against a figure that excludes everything currently
running. Up to `hard_limit = 16` concurrent requests (`fly.toml:59`) can each
pass the check against the same stale total. With the per-run cap at $1.00
(`fly.toml:29`, `usage.py:201`), worst case is roughly $16 of spend admitted
against a $5.00 cap — a 3x overshoot, and that is per 24h window, repeatable.

The comment at `metrics.py:259-263` explains why spend is read from the table
rather than a counter (a counter drifts across restarts and machines). That
reasoning is right; the gap is that neither approach counts in-flight work.

**Compounding:** the rate limiter is per-process in-memory
(`limits.py:96-98`, acknowledged in its own docstring), so it is not a
meaningful second line either once more than one machine runs.

**Fix approach:** Reserve before spending — insert a `runs` row in a `running`
state at admission and have `spend_since` count reserved rows at their per-run
ceiling, reconciling to actual on completion. That keeps the "read from the
table" property that `metrics.py:259` correctly insists on.

---

### No timeouts on the Anthropic or Voyage clients

**Risk:** A single request can occupy a worker and a Fly concurrency slot for a
very long time.

**Files:**
- `src/research_agent/graph.py:61` — `_client = anthropic.Anthropic()`, no `timeout=`
- `src/research_agent/memory.py:95` — `voyageai.Client()`, no timeout
- `src/research_agent/db.py:81` — Postgres, which *does* bound its connect

Postgres is the only dependency with a bound, and `db.py:22-25` argues
persuasively for why that bound matters. The two network calls that actually
dominate a run's wall-clock have none, so they fall back to the SDK default
(10 minutes for Anthropic).

That interacts badly with the retry layer. `MAX_ATTEMPTS = 4` per node
(`retry.py:48`), `MAX_ITERATIONS = 12` (`graph.py:47`), and `is_retryable`
includes `APITimeoutError` (`retry.py:59`) — so a stalling upstream produces
timeout, backoff, retry, timeout, across many nodes. `AGENT_RETRY_MAX_DELAY`
(30s, `retry.py:50`) bounds the sleeps but nothing bounds the calls.

With `hard_limit = 16` (`fly.toml:59`) on one `shared-cpu-1x` machine
(`fly.toml:78`), a handful of stalled runs saturates the service. No
server-side request deadline exists either.

**Fix approach:** Pass an explicit `timeout=` to both clients, and add a
whole-run deadline the supervisor checks alongside its cost check
(`graph.py:421`) — the structure for that already exists.

---

### Stores grow without bound — confirmed, and worse in the memory store

**Risk:** Unbounded disk and RAM growth, degrading per-run latency and cost.

**Files:**
- `src/research_agent/memory.py:110-141` — `MemoryStore` ABC has no delete, prune, or evict
- `src/research_agent/graph.py:274` — every research run appends a full note
- `src/research_agent/memory.py:219` — `JSONMemoryStore` loads the entire file into RAM
- `src/research_agent/memory.py:227-233` — `_persist` rewrites the whole file on every add
- `src/research_agent/memory.py:186-190` — brute-force O(n) cosine scan per query
- `src/research_agent/sessions.py:45-55` — sessions schema has no TTL or expiry column

**Verified as stated, with detail.** There is genuinely no eviction,
deduplication, or summarisation anywhere. The `MemoryStore` contract does not
even have a method that could remove a note — the seam would need widening
before an eviction policy could be written.

Two aggravating factors not in the original list:

1. **Quadratic write cost on the default backend.** The deployed configuration
   uses `VECTOR_STORE_PATH=/data/agent_memory_store.json` (`fly.toml:39`), so
   the backend is `JSONMemoryStore`. It rewrites the *entire* file on every
   single add (`memory.py:227-233`). The docstring at `memory.py:213` is candid
   about this. Cumulative I/O is O(n²) in notes written. The local store is
   already 54 KB.
2. **The whole corpus lives in the process.** `_load` (`memory.py:221`) reads
   every note and every 1024-float embedding into a Python list, on a 1 GB
   machine (`fly.toml:82`). Each note is ~8 KB of embedding alone as JSON. This
   is the memory ceiling that bites first.

Sessions have no expiry — deletion is by explicit ID only (`sessions.py:189`),
and `GET /sessions` caps the *listing* at 50 (`service.py:47`) without capping
the table.

**No ownership on sessions:** confirmed. There is no user, tenant, or owner
column in either schema (`sessions.py:46-53`, `:61-68`). This is the schema-level
root of the Severity 1 read/delete findings above.

**Fix approach:** Add a `scope`/`owner` column and a `created_at`-based sweep to
both stores. For notes specifically, add `delete`/`prune` to the `MemoryStore`
ABC first — nothing can be fixed until the contract allows removal. Moving the
deployed backend off JSON to pgvector (already implemented,
`memory.py:311-424`) fixes the O(n²) and the RAM ceiling at the same time.

---

## Severity 3 — Medium

### Follow-up conversations grow the prompt without limit

**Files:**
- `src/research_agent/graph.py:176-189` — `conversation` accumulates every turn
- `src/research_agent/graph.py:317-323` — the whole history goes into every responder prompt
- `src/research_agent/sessions.py:172-187` — the whole thread is re-serialised on every turn

Each follow-up appends `{question, answer}` and re-sends the full history plus
the notes plus the source report. Nothing truncates or summarises. Cost and
latency grow with turn count, and each turn rewrites the entire state blob to
the database. `max_tokens=2000` (`graph.py:344`) bounds the *output* per turn,
not the accumulated input.

There is also no cap on the number of turns a session may accumulate.

**Fix approach:** Cap or summarise `conversation` in `_conversation_block`, and
cap turns per session.

---

### Single lock-guarded connection serialises the database, and unauthenticated endpoints can hold it

**Files:**
- `src/research_agent/db.py:64-113` — one connection, one `RLock`, no pool
- `src/research_agent/sessions.py:146-147` — same shape for SQLite
- `src/research_agent/metrics.py:276-277` — same again
- `src/research_agent/metrics.py:309-313` — `/metrics` runs four queries inside one lock hold

**Verified as stated.** The justification (`db.py:11-15`) is reasonable for the
write path: runs take tens of seconds, queries take milliseconds.

What that argument does not cover is the read path. `GET /metrics`
(`service.py:551`) is unauthenticated and ungated, and its `summary()` holds the
lock across four separate queries including two `GROUP BY`s and a full-table
`ORDER BY duration_ms` (`_DURATIONS_SQL`, `metrics.py:238`) that has no index and
no `LIMIT`. As the `runs` table grows, repeated unauthenticated `/metrics` calls
become a cheap way to serialise the whole application's database access.

**Fix approach:** Bound `_DURATIONS_SQL`, or compute percentiles in SQL rather
than pulling every row. A pool is the general answer but is not required to fix
this specific exposure.

---

### `pricing_unknown` is tracked but never surfaced to the caller

**Files:**
- `src/research_agent/usage.py:163-166` — the flag is set and documented
- `src/research_agent/usage.py:177-179` — set when a model has no price on file
- `src/research_agent/metrics.py:117-142` — `RunRecord.from_state` does not read it
- `src/research_agent/metrics.py:193-204` — the `/metrics` cost block never reports it

The flag exists precisely so `cost_usd` can be understood as a floor rather than
a total (`usage.py:164-166`). It is threaded into the run usage dict and then
dropped: no metrics column, no aggregate, no field in `/metrics`. It does reach
`RunResponse.usage` (`service.py:83`) as an opaque dict entry, but nothing
downstream keys on it.

Consequence: if a model is ever swapped to one without a price row, cost
reporting silently under-reports and the one signal designed to catch that is
invisible. Low likelihood today, but it is a defect in an accounting path.

**Fix approach:** Add a `pricing_unknown` column to `RunRecord` and surface a
count in the `/metrics` cost block.

---

### `BaseException` handlers can swallow interpreter-level signals

**Files:**
- `src/research_agent/service.py:207` — `except BaseException as exc:`
- `src/research_agent/retry.py:128` — `except BaseException as exc:`

Both re-raise, so the practical impact is limited to a spurious `FAILED` metrics
row on `KeyboardInterrupt`/`SystemExit` during shutdown. In `retry.py:128` the
`is_retryable` check (`retry.py:130`) returns `False` for those types so they are
re-raised immediately, which is correct behaviour arrived at indirectly.

**Fix approach:** Narrow both to `Exception` and let interpreter-level
exceptions pass untouched.

---

### Rate limiting collapses to a single bucket outside Fly

**Files:**
- `src/research_agent/limits.py:80-89` — `client_ip`

On Fly, `fly-client-ip` is present and trustworthy, and the docstring
(`limits.py:73-78`) is right that `X-Forwarded-For` is correctly gated behind
`TRUST_FORWARDED_FOR`. But the fallback at `limits.py:89` returns the literal
string `"unknown"` when `request.client` is absent. Every such caller then shares
one rate-limit bucket — either locking out legitimate traffic or, depending on
volume, being trivially filled by one client. Only matters off Fly (local Docker,
a different host), so severity is bounded.

---

## Severity 4 — Low

### Unauthenticated `/health` discloses infrastructure detail

`service.py:412-421` returns backend class names, store locations, row counts,
and credential-presence booleans. `store.path` is DSN-redacted
(`sessions.py:305-319`), so no credential leaks — but it does confirm the
database host and name to anyone. Standard for a demo; noting it for
completeness.

`/metrics` (`service.py:551`) similarly publishes total spend and volume
unauthenticated. `/demo` publishing remaining budget is a deliberate,
well-argued choice (`service.py:381-383`).

### `_node_detail` indexes into a possibly empty trace

`service.py:271` reads `state["trace"][-1]` for the researcher node. The
researcher always appends before returning (`graph.py:275`), so this holds
today. It is an unguarded assumption across a module boundary that would fail as
an `IndexError` mid-stream.

### Stray Dockerfile comment with no corresponding instruction

`Dockerfile:53` reads "The demo page. One self-contained file, so this is the
whole frontend." — but there is no `COPY` for it. The page ships via
`[tool.setuptools.package-data]` (`pyproject.toml:48-49`) inside the installed
venv, which is correct and is asserted by
`tests/test_deploy_config.py:113-120`. The comment is a leftover that misleads a
reader into thinking a `COPY` is missing.

### Duplicated comment in the builder stage

`Dockerfile:22-25` states the same layer-caching rationale twice in two
different phrasings.

---

## Verified as Already Handled

Recorded so these are not re-investigated. Each was checked against the code.

**Sonnet 5 pricing rollover — HANDLED. No action needed.**
`src/research_agent/usage.py:60-69` contains both windows: `$2/$10` with
`until=date(2026, 8, 31)`, and `$3/$15` with `since=date(2026, 9, 1)`. The
windows are contiguous with no gap, `covers()` (`usage.py:51-54`) treats `until`
as inclusive, and `price_for` (`usage.py:83-88`) resolves against today's date by
default. The cost reporting will roll over correctly on 2026-09-01. Cache-write
and cache-read rates are stepped too. Unpriced models raise `UnknownModelPricing`
rather than costing at zero (`usage.py:88`).

**Secrets handling — CLEAN.** `.env` is gitignored (`.gitignore:2`), has never
appeared in git history (`git log --all -- .env` is empty), and is excluded from
the build context (`.dockerignore:6`), which `tests/test_deploy_config.py:106`
asserts. A scan of all tracked files for API-key and DSN-credential patterns
returned only test fixtures (`tests/test_service.py:557`,
`tests/test_store_contract.py:398`, `:465`) and placeholders (`.env.example:7-8`,
`.github/workflows/ci.yml:41` — a localhost CI container). Credentials are
reported as booleans, never values (`service.py:417-420`). DSNs are redacted at
`sessions.py:305-319` and `service.py:337-344`. The single exception is the SSE
leak documented under Severity 2.

**Port 8000 mismatch — GUARDED BY TEST.**
`tests/test_deploy_config.py:55-62` cross-checks `fly.toml` `internal_port`
against both `EXPOSE` and the `--port` argument in the Dockerfile `CMD`. All
three are 8000.

**SQLite pins the app to one machine — GUARDED BY TEST.**
`tests/test_deploy_config.py:91-99` fails if a `[[mounts]]` block coexists with
`min_machines_running > 1`. `fly.toml:43-45` and `:55` are consistent.

**`/data` volume required — GUARDED BY TEST, and the stated symptom is wrong.**
`tests/test_deploy_config.py:73-88` asserts every store path sits under the
mount destination. Note the failure mode is *not* a silent no-op: `Dockerfile:57`
creates `/data` and chowns it, so with no volume mounted the writes succeed to
container-local disk and are lost on restart. Data loss, not a no-op — worth
correcting in the docs.

**Embedding-model change needs a new pgvector table — HANDLED WELL.**
`memory.py:371-378` validates dimensions on every read and write and raises a
message that states the constraint explicitly. `migrate.py:114-120` performs the
same check before migrating and refuses with actionable guidance. The table name
is validated against SQL injection before DDL interpolation (`memory.py:339-340`).

**Cost is list-price only — CONFIRMED AS STATED.** `usage.py:59-76` carries
public list rates with no enterprise-discount factor and no `inference_geo`
multiplier. `cost_usd` (`usage.py:132-139`) applies rates directly. Accurate for
this deployment; would need a multiplier under a discounted contract.

**Demo page XSS — NOT PRESENT.** `static/index.html:147` assigns via
`textContent`; there is no `innerHTML` anywhere in the file. Model-generated
report text cannot execute in the browser.

**CORS — NOT CONFIGURED, which is the safe default.** No CORS middleware is
registered in `service.py`, so cross-origin JavaScript cannot read responses. The
demo page is same-origin. This limits how much the Severity 1 read exposure can
be weaponised from a third-party page, though it does nothing against `curl`.

---

## Test Coverage Gaps

**SSE error redaction** — `tests/test_service.py:681-689` covers `_redact` only
through the `/health` probe. Nothing asserts the SSE `error` event is redacted,
which is exactly why the Severity 2 leak survived.

**Authorisation** — there are no tests asserting that any endpoint *refuses*
anonymous access to session data, because no endpoint does. Adding tests here is
the natural companion to the Severity 1 fix.

**Spend cap under concurrency** — `tests/test_limits.py` exercises the cap
sequentially. No test drives concurrent admissions against a stale
`spend_since`, so the overshoot in Severity 2 is invisible to CI.

**Prompt injection** — no test asserts that adversarial text in
`research_notes` fails to flip the critic to `APPROVED`. Given that the critic is
the pipeline's only correctness control, this is the highest-value test to add.

---

*Concerns audit: 2026-08-04*
