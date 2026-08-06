# Operations

Running this in production: deployment, configuration, CI, and the migration
to Postgres. For what the system is, see the [README](../README.md); for why
it's built this way, [DESIGN.md](DESIGN.md).

## Container

```bash
cp .env.example .env
docker compose up --build
curl localhost:8000/health
```

The image runs as a non-root user, installs the `[service]` extra only,
and excludes `tests/` and `evals/` — the eval dataset contains scripted model
output, which has no business inside a production image.

**Mount a volume at `/data`.** Both SQLite databases and the vector store live
there. Without it, every follow-up thread and every stored note dies with the
container, and the memory feature quietly becomes a no-op.

**Credentials never reach an image layer.** `.env` is in `.dockerignore`,
compose passes keys through from the environment, and Fly uses `fly secrets`.
`/health` reports whether each key is *present*, never its value.

## Fly.io

```bash
fly volumes create agent_data --size 1 -a research-agent
fly secrets set ANTHROPIC_API_KEY=... VOYAGE_API_KEY=... -a research-agent
fly secrets set IDENTITY_SIGNING_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')" -a research-agent
fly deploy -a research-agent
```

Fly secrets are app-wide, which is the point of that third line: every machine
gets the same signing key, so an identity cookie minted by one verifies on the
other. Leave it unset and each process invents its own ephemeral secret — the
demo still works, but a caller bounced between machines becomes a new visitor
and loses their sessions. `/health` reports `credentials.identity_signing` so
you can tell which of the two you are running, without exposing the value.

`fly.toml` pins `min_machines_running = 1` on purpose: SQLite with a single
writer and a per-machine volume does not scale horizontally, because a second
machine would hold its own database and 404 on sessions that demonstrably
exist. Setting `DATABASE_URL` lifts that constraint — see below.

> **Don't merge Fly's "New files from Fly.io Launch" pull requests.** They
> regenerate `fly.toml` from the web UI's defaults and have twice broken this
> deploy: once by pointing `app` at the Postgres cluster, and once by setting
> `internal_port` to `8080` while the container listens on `8000`. The second
> is the nastier one — it touches a line `fly.toml` hasn't changed since the
> branch point, so it merges with **no conflict shown** and surfaces only as
> every request failing. Copy any value you want out by hand and close the PR.
> `tests/test_deploy_config.py` fails the build on both cases.

**Deploys are manual.** Fly is not wired to this repository, and there is no
deploy job in CI — nothing ships on push, on merge, or on tag.
Releases are cut by hand with `fly deploy -a research-agent` from a working
tree the operator has tested; `fly releases -a research-agent` is the evidence —
every release is attributed to the owner's personal account, not to a machine
token. So nothing can deploy a failing tree, but equally, merging to `main`
ships nothing until someone runs the command, and `main` and the deployed
release can drift apart silently. Re-run the command after any merge you expect
to be live.

What CI *does* gate is described under [CI](#ci) below, with one caveat worth
stating plainly. `main` is protected with two required checks — `lint · tests ·
evals` and `image build · container smoke test` — under `strict: true`, but
`enforce_admins` is `false`. An admin pushing straight to `main` therefore
succeeds: GitHub records a **bypass** notice rather than blocking the push. The
Phase 10.5 push on 2026-08-04 did exactly that, reporting `Bypassed rule
violations for refs/heads/main: 2 of 2 required status checks are expected`
(verified against `gh api repos/future-beat/research-agent/branches/main/protection`).
The checks gate **pull requests**, not every path to `main`; after a direct push
CI still runs, but only after the fact.

## Going stateless

One volume on one machine means downtime during host maintenance and up to 24h
of data loss between snapshots. Moving state to Postgres removes both.

The database is an **external** managed Postgres, not a Fly one. Fly's CLI now
prints that unmanaged Fly Postgres *"is not supported by Fly.io Support and
users are responsible for operations, management, and disaster recovery"*, so
the commands this runbook used to carry are a dead path. There is no attach
step any more: `fly secrets set DATABASE_URL=…` is the whole wiring.

### Why Supabase and not Neon

This is a design consequence, not a coin flip. `/health` is the liveness probe
and deliberately queries all three stores; Fly runs it every 30s per machine,
so with two machines the database is queried roughly four times a minute,
forever. Neon's free plan meters compute at **100 CU-hours per project per
month** — about 400 hours at 0.25 CU — and a compute that those probes keep
permanently awake bills ~730 hours a month. The project would be suspended
around day 16 of every month, which drops existing connections and refuses new
ones. Neon's scale-to-zero can't rescue it: the probes are exactly what stops
it firing. Supabase's free tier has **no compute meter**, and its only idle
hazard — a pause after ~7 days of low activity — is *prevented* by the same
probes. The design that disqualifies one provider is the design that keeps the
other alive.

The cost of that choice is a networking wrinkle: Supabase's direct endpoint is
IPv6-only on the free tier, so the DSN points at the **session-mode Supavisor
pooler** (`aws-<n>-ap-southeast-2.pooler.supabase.com:5432`), which is IPv4.
Session mode, not transaction mode (`:6543`) — transaction mode is for
transient serverless clients and breaks prepared statements and session state,
and this is a persistent backend holding its own pool.

### The cutover, in order

The order is load-bearing. A machine with neither a volume nor a reachable
database is a broken machine, so the mount comes out only after the database
has been proven serving live traffic.

1. **Create the Supabase project**, region **Oceania (Sydney) `ap-southeast-2`**
   — next to Fly's `syd`, because every store probe pays that hop. The project
   region cannot be changed after creation.
2. **Enable the `vector` extension** (Database → Extensions, or
   `create extension vector`). Required for the pgvector notes backend.
3. **Set the DSN as a secret.** This triggers a deploy on its own.
   ```bash
   fly secrets set -a research-agent \
     DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-<n>-ap-southeast-2.pooler.supabase.com:5432/postgres?sslmode=require'
   ```
4. **Verify before going further.** `curl https://research-agent.fly.dev/health`
   must show all three stores on their Postgres backends and
   `dependencies: "ok"`. Create a session and read it back. The volume is still
   mounted at this point and the SQLite data is intact underneath, just unused —
   so this step is fully reversible with `fly secrets unset`.
5. **Only now, remove the local-state config**, in a single edit: delete the
   `[[mounts]]` block and the three `*_DB_PATH` vars, **and add the three
   fail-closed pins** — `SESSION_BACKEND=postgres`, `METRICS_BACKEND=postgres`,
   `VECTOR_STORE=pgvector` — in the same edit. Deploy. This is the point of no
   return for per-machine state.
6. **Confirm the volume survived**, unattached: `fly volumes list -a research-agent`.
   A machine that does not require a volume never attaches itself to one.
7. **Scale out.** Raise `min_machines_running` to `2` in `fly.toml`, then
   `fly scale count 2 -a research-agent`.

Steps 1–4 are reversible and leave production untouched.

**Measured Fly-syd → Supabase-ap-southeast-2 round trip** (release v5, from inside
the machine, against the real DSN): `connect+TLS 119.2 ms, query p50 2.73 ms,
p95 6.37 ms`. The three `/health` store probes cost 2.84 / 3.23 / 3.39 ms at the
p50, worst observed 6.90 ms — against a `HEALTH_PROBE_BUDGET` of 3000 ms, roughly
435× headroom at the worst sample. Doubling the fleet does not threaten that
arithmetic; there is no need to re-derive the `/health` budget before scaling.

The one number worth carrying is **connect+TLS at 119.2 ms**, two orders of
magnitude above the query cost. That is the pooler handshake, and it is why
`PG_POOL_MIN_SIZE=1` holding a warm connection matters — a cold checkout pays
119 ms before it runs anything. Sizing the pool to zero would make that term
dominate.

**The rollback is untested.** `fly secrets unset DATABASE_URL -a research-agent`
is the documented escape hatch and it has never been exercised — reverting a
working cutover to prove a mechanism was judged not worth it. Everything it
depends on is verified (the volume exists, its SQLite data is intact at the row
level), but do not describe it as a proven path. Note also that rolling back is
a **four-part** change: restore `[[mounts]]`, restore the three `*_DB_PATH` vars,
**delete the three pins**, and `fly scale count 1`. Restoring the mount while
leaving the pins in place gives a machine that still refuses to boot without a
DSN.

`tests/test_deploy_config.py` guards the pairing in both directions: with a
mount it requires one machine and local paths under `/data`; without one it
requires the three pins, no `*_DB_PATH` keys, and at least two machines. Neither
arm skips, so deleting the mount cannot silently disarm them.

**Do not destroy the volume.** Detaching is reversible — the volume still exists
and can be re-attached by restoring the `[[mounts]]` block — and
`fly volumes destroy` is not. It is not part of this procedure at any point;
the volume is the backup.

### Why the pins matter

Removing the `*_DB_PATH` vars is not enough on its own. `sessions.py` defaults
`SESSION_DB_PATH` to a file beside the module, and the backend selector returns
`sqlite` whenever no DSN is configured. So a mount-less deploy with an unset or
empty `DATABASE_URL` doesn't surface as a degraded `/health` — each machine
falls back to its own container-local SQLite and JSON, `/health` reports
`dependencies: "ok"` because SQLite is perfectly reachable, Fly's check passes,
and the only visible difference is a backend class name that no automated check
reads. You would find out when a user's follow-up 404s.

With the pins set, the same situation raises at store construction and the app
does not come up. The tradeoff, plainly: a missing DSN now takes the service
down instead of quietly serving per-machine data that vanishes on restart. For
a configuration error that is the intended behaviour.

### Starting clean

**This cutover starts against an empty database. There is no data migration.**
What is knowingly given up is the cumulative `/metrics` history; the two
orphaned notes and the old demo sessions are disposable. The volume is kept as
the backup, so nothing is destroyed — it is simply left behind.

`python -m research_agent.migrate` therefore plays no part in this cutover —
there is nothing to migrate.

**It is no longer an unproven tool, though: since Phase 13 it is covered by
tests.** Leaving it unproven turned out to
cost something: read against the Phase 12 schema, `migrate_notes` was inserting
only `(text, embedding)`, so every migrated note would have landed on
`owner=''` — belonging to nobody, since a real identity is a 32-hex uuid — with
`created_at` defaulting to `now()` and its seven-day TTL restarted.
`migrate_sessions` dropped `owner` the same way. Both are fixed, and
`tests/test_migrate.py` now asserts field-level owner and timestamp fidelity
across a real SQLite-to-Postgres round trip.

That is a proof about the *code*, not about your data. It has still never been
run against the volume, so dry-run first. The same command's `embeddings`
subcommands are what a model change goes through — see
[Changing the embedding model or dimension](#changing-the-embedding-model-or-dimension).

### Supabase specifics

**`sslmode=require` is mandatory and nothing adds it for you.** libpq's default
is `prefer`, which silently accepts a plaintext connection, and `db.py` passes
the DSN through untouched — whatever is in the secret is what is used. A DSN
copied from the dashboard may not carry it. Append it.

**pgvector lives in the `extensions` schema on Supabase**, not `public`, so an
unqualified `::vector` cast does not resolve by default. `db.py` sets a
connection-level `search_path` that includes it.

**A paused free-tier project** — the state Supabase enters after ~7 days of
inactivity, which this deployment's health probes prevent — is restored
manually from the dashboard and loses no data.

**Connection budget.** `hard_limit = 16` × 2 machines = up to 32 in-flight
requests against one database, but the app pool caps connections at
`PG_POOL_MAX_SIZE` (5), so the fleet holds at most 10 of Supabase Nano's 60.
Requests past that queue on a bounded checkout rather than opening an eleventh
connection.

## Changing the embedding model or dimension

A pgvector column has its width fixed at creation, so a new embedding model — or
the same model at a different `output_dimension` — needs a **new table**. This is
the procedure that builds one and switches to it. It is reversible at every step
and nothing here ever drops a table.

**Read the scale note first.** Notes expire seven days after they are written, so
the live corpus is small and self-cleaning. This procedure is not corpus rescue and
should not be sold as such — its value is that changing embedding model becomes a
decision an operator can take in an afternoon instead of a migration project. At a
few thousand notes it is also the whole story; at a few million it would need
batching, resumption and a maintenance window this tooling has not been asked for.

### 1. Quiesce

Stop the service, or leave it idle, for the duration. `fly scale count 0 -a
research-agent` if you want it certain.

**Why there is no dual-write machinery, stated plainly rather than left as a
gap:** the corpus is at most seven days of notes by construction. A note written
during the migration and missed by it expires on its own within a week. Building
dual-write for a self-erasing corpus is engineering theatre, so it was
deliberately not built. What you are accepting is the loss of notes written in the
window between the migrate and the flip — bounded, self-healing, and cheaper to
accept than to engineer around at this size.

### 2. Migrate

Two commands, and which one you want depends on which variable is changing. Never
both at once — that is the whole design (see
[ADR-0008](adr/0008-embedding-migration-two-commands.md)).

**Same model, new table** — an infrastructure-only move. Same vectors, no spend, no
network:

```
python -m research_agent.migrate embeddings copy \
  --from research_notes --to research_notes_v2 [--dry-run]
```

**New model or new width** — the vectors are recomputed, and this one costs money:

```
python -m research_agent.migrate embeddings re-embed \
  --from research_notes --to research_notes_v2 \
  --model voyage-3.5 [--dimensions 1024] [--batch-size 128] [--dry-run] [--yes]
```

The cost preview **always** prints — model, width, row count, tokens, the rate with
the date it was verified, and the estimated dollars. Without `--yes` the command
stops there and exits nonzero; `--dry-run` beats `--yes` if you pass both. An
unpriced model refuses rather than quoting `$0.00`, and it refuses before it opens
the database, so discovering that a model is unpriced costs nothing.

**The first `count_tokens` call downloads a tokenizer from the Hugging Face hub.**
Voyage's client fetches it once and caches it, so the first preview on a fresh
machine or a fresh container needs outbound network and takes a few seconds
longer than you expect. Subsequent calls are offline. If the box has no egress to
`huggingface.co`, the preview is where it will fail.

### 3. Verify

Both commands print their own numbers and exit nonzero if the numbers are wrong —
read them rather than trusting the exit code alone.

`copy` prints row counts on both sides, how many source rows matched on
`(text, owner, created_at)`, how many were unmatched, and how many embeddings
differ byte-for-byte. All four should read as a clean move; a nonzero
byte-difference, or a matched count below the source count, means stop.

`re-embed` prints predicted versus billed tokens and the billed cost. A large gap
between the two means the preview's token count is drifting from Voyage's own,
which is worth knowing before the next run rather than after.

Then check recall yourself if the model changed. There is a frozen golden query
set in `src/research_agent/recall_golden.py` and a `recall_delta` over it; a copy
must show **zero** delta, which is what makes any delta a re-embed shows
attributable to the model rather than to the move. Note that a new model re-scores
everything, so `assert_tie_free` has to be re-run against the re-embedded table
before an ordered comparison over it means anything.

### 4. Flip

Cutover is the config that already existed:

```
fly secrets set PGVECTOR_TABLE=research_notes_v2 -a research-agent
# after a re-embed that changed the width, set both in one call:
fly secrets set PGVECTOR_TABLE=research_notes_v2 VECTOR_DIMENSIONS=1024 -a research-agent
```

Setting a secret restarts the machines, which is what the flip needs: both
variables are read once at import in `memory.py` and become the store
constructor's defaults, so a running process keeps talking to the old table until
it restarts.

**Rollback is pointing back.** `fly secrets set PGVECTOR_TABLE=research_notes`
(and `VECTOR_DIMENSIONS` back to its previous value) puts you on the old table
again, with all of its data, because nothing in this procedure wrote to it. Both
directions are covered by a test — `pytest tests/test_migrate.py -k
cutover_reversible` flips a store forward and back and asserts the old table's
full contents, embeddings included, are unchanged after every step.

Bring the service back up (`fly scale count 2 -a research-agent`) and confirm
`/health` reports the store healthy before you consider the flip done.

### 5. Drop the old table — by hand, later, or never

**No command in this tooling drops anything.** Keeping the old table is what makes
step 4 reversible, so deleting it is a deliberate operator act taken after the new
table has been live long enough to trust:

```sql
DROP TABLE research_notes;  -- only once you are certain
```

There is no automation for this and there should not be. Once it is gone,
rollback is gone with it.

### 6. The dimension ceiling

`re-embed` refuses `--dimensions` above **2000**. That is pgvector's HNSW index
limit for the `vector` type, and it is a real constraint rather than a
hypothetical one: voyage-3.5 offers `output_dimension=2048`, so asking for the
model's largest width is an easy mistake to make. The refusal happens before any
DDL and before any spend, and it names `halfvec` — pgvector's documented path to
wider indexed columns, which this codebase has not built. If you need 2048, that
path is the work, not a flag.

## CI

```
lint · tests · evals            ruff, 470 tests, 12 offline eval cases
image build · smoke test        docker build, boot the container, probe it
```

Every gate runs with `ANTHROPIC_API_KEY=""`. A CI suite that needs a live key
breaks on forks, on key rotation, and during someone else's outage — and bills
you for every push. The offline eval step doubles as a guard on the lazy-client
decision: if a client ever becomes eager again, that step is what fails.

The smoke test boots the built image and probes `/health`, `/metrics`,
`/pricing`, and `/openapi.json`, then waits for Docker's own `HEALTHCHECK`. A
Dockerfile that builds but whose entrypoint crashes on startup passes a
build-only check and fails in production instead.

Postgres and pgvector run for real against a `pgvector/pgvector` service
container, with a guard test that **fails** rather than skips when the database
is missing — so the build can't go green over an untested backend.

`main` is protected: both checks must pass before a pull request can merge, and
force pushes and branch deletion are blocked.

## Configuration

Tunable in code:

| Knob | Where | Default |
|---|---|---|
| `MAX_REVISIONS` | `graph.py` | `2` |
| `MAX_ITERATIONS` | derived from `MAX_REVISIONS` | `12` |
| `MODEL` | `graph.py` | `claude-sonnet-5` |
| Effort / thinking | per-node `output_config` | `medium` / `adaptive` (`disabled` on the classifier) |
| `min_similarity` | `MemoryStore.query()` | `0.3` |

Environment variables:

| Variable | Does | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` · `VOYAGE_API_KEY` | Required for real runs | — |
| `DATABASE_URL` | Postgres DSN. **Setting it moves all three stores.** | *(unset)* |
| `VECTOR_STORE` | `json`, `memory`, `chroma`, `pgvector` | follows `DATABASE_URL` locally; **pinned to `pgvector` in production** |
| `SESSION_BACKEND` · `METRICS_BACKEND` | `sqlite` or `postgres` | follows `DATABASE_URL` locally; **pinned to `postgres` in production** |
| `VECTOR_STORE_PATH` · `SESSION_DB_PATH` · `METRICS_DB_PATH` | Local store locations | beside the code |
| `PGVECTOR_TABLE` · `VECTOR_DIMENSIONS` | pgvector table and column width | `research_notes` / `1024` |
| `PG_CONNECT_TIMEOUT` | Bounds **one libpq connect attempt**, made by a pool background worker — no longer how long a caller waits | `3` |
| `PG_POOL_MIN_SIZE` · `PG_POOL_MAX_SIZE` | Warm connections held open; ceiling per machine | `1` / `5` |
| `PG_POOL_TIMEOUT` | Seconds a caller waits for a pool **checkout**, and nothing after it | `2.0` |
| `PG_STATEMENT_TIMEOUT` | Server-side statement bound, ms; `0` disables | `10000` |
| `PG_TCP_USER_TIMEOUT` | Milliseconds of unACKed data before the socket is dropped; `0` disables | `2000` |
| `HEALTH_PROBE_BUDGET` | Wall-clock seconds one `/health` store probe may take, end to end | `3.0` |
| `CHROMA_PATH` · `CHROMA_COLLECTION` | Chroma location and collection | `chroma_store` / `research_notes` |
| `VOYAGE_EMBEDDING_MODEL` | Embedding model | `voyage-3.5` |
| `AGENT_MAX_RUN_COST_USD` | Per-run spend cap; `0` disables | `1.00` |
| `AGENT_MAX_ATTEMPTS` | Attempts per node, including the first | `4` |
| `AGENT_RETRY_BASE_DELAY` · `AGENT_RETRY_MAX_DELAY` | Backoff bounds, seconds | `1.0` / `30.0` |
| `DEMO_DAILY_USD_CAP` | Rolling 24h ceiling across all callers; `0` disables | `5.00` |
| `DEMO_RATE_LIMIT_PER_HOUR` | Requests per **caller identity** (the signed cookie), not per IP; `0` disables | `10` |
| `DEMO_RESERVED_RUN_USD` | What a starting run claims against the daily cap up front, settled to the real cost when it ends; `0` reserves nothing | `0.20` |
| `IDENTITY_SIGNING_SECRET` | Signs the anonymous caller-identity cookie. Set app-wide so a cookie minted by one machine verifies on the other; unset, each process invents an ephemeral one and identities don't survive a bounce | *(unset)* |
| `DEMO_TOKEN` | When set, write endpoints need an `X-Demo-Token` header. Also accepted as a fallback for `SESSIONS_TOKEN` | *(unset)* |
| `SESSIONS_TOKEN` | Operator credential, sent as `X-Demo-Token`: lists and deletes **every** owner's sessions. While unset, only the operator view is closed — callers still reach their own | *(unset)* |
| `SESSION_TTL_DAYS` | A session stops resolving this long after its last turn, and is swept on the next run. Reads don't renew it | `7` |
| `NOTE_TTL_DAYS` | A stored note stops being recalled this long after it was written, and is swept on the next `add()`. Same value and same mechanics as sessions, on all four vector backends | `7` |
| `TRUST_FORWARDED_FOR` | Believe `X-Forwarded-For` for the client IP in **log lines only** — since Phase 12 nothing keys fairness on it (ADR-0007) | `false` |
| `LOG_FORMAT` · `LOG_LEVEL` | `json` or `text`; level | `json` / `INFO` |
| `OTEL_ENABLED` | Emit OpenTelemetry spans when the package is installed | `true` |

### The four Postgres timeouts are four different things

They read like variations on one knob and they are not; each bounds a different
segment of a request, and only one of them bounds a whole operation. In order:
`PG_CONNECT_TIMEOUT` bounds a single libpq connect attempt, which since the
pool landed is made by a **background worker**, so it no longer bounds how long
a caller waits for anything. `PG_POOL_TIMEOUT` bounds how long a caller waits
for a **checkout** — and nothing that happens after it. `PG_STATEMENT_TIMEOUT`
and `PG_TCP_USER_TIMEOUT` bound what happens once a connection is in hand: a
server that is slow, and a peer that stops ACKing, respectively.
`HEALTH_PROBE_BUDGET` is the only one that bounds a probe **end to end**, and
is therefore the source of `/health`'s guaranteed ceiling.

That ceiling is **3 probes × 3.0s = 9s**, inside Fly's 15s check timeout, and
it holds whether the pool is cold, warm or partitioned. The ordinary cold-pool
cost is 3 × `PG_POOL_TIMEOUT` ≈ 6s, but that is a typical figure and not a
bound — a warm pool holding a connection to a peer that has gone away returns
from checkout instantly and then blocks on the socket, at which point the
checkout timeout is already spent. The case none of the libpq bounds catch is a
peer that keeps the socket alive and never answers: `statement_timeout` needs
the server to be listening and `tcp_user_timeout` needs unACKed data. That case
is why the wall-clock deadline exists. Measured: 0.32s against a store that
never answers, versus 31.4s with the deadline removed.

**Concurrency and the spend cap used to interact badly; Phase 12 fixed it.**
The rolling daily cap once counted only *completed* runs, so a burst of 16 could
overshoot `DEMO_DAILY_USD_CAP` by roughly 3×, and two machines each holding the
count in process memory doubled that again. Both halves are closed. A starting
run now **reserves** `DEMO_RESERVED_RUN_USD` against the cap before it does any
work and settles to the real figure when it finishes, so in-flight runs count;
the check and the reservation share one transaction holding a Postgres advisory
lock, so two concurrent guards cannot both pass; and the state lives in Postgres
rather than per-machine memory, so the fleet reads one number. What remains is
smaller and bounded: a run whose process dies keeps its reservation for 900s
before it is reclaimed, and a wrong estimate makes the cap fire slightly early or
slightly late, never not at all.

The two tokens are not interchangeable in production, and since Phase 12 they
no longer do comparable jobs. A session now records the identity that created
it, and `GET /sessions`, `/sessions/{id}`, `/{id}/trace` and
`DELETE /sessions/{id}` serve that identity its own and refuse everyone else's
with a 404 identical to a missing one — no token involved either way.
`SESSIONS_TOKEN` buys the one thing an identity cannot: the unscoped view
across all owners, for debugging, plus delete on any session. `DEMO_TOKEN`
still fronts `POST /research/stream`, which the demo page calls with no header
— setting it on the public app 401s every anonymous visitor and takes the demo
offline.

Note what this changed about failing closed. `SESSIONS_TOKEN` used to refuse
everyone with 403 while unset, so that forgetting the secret could not silently
reopen the world-readable leak of Phase 10.5. Forgetting it is now survivable
for a different reason: what keeps a stranger out is ownership, not the secret,
and ownership cannot be left unset. An unset `SESSIONS_TOKEN` costs you the
operator view and nothing else.

Both are secrets: `fly secrets set SESSIONS_TOKEN=… -a research-agent`, never
`fly.toml`'s `[env]` block — that file is committed.

Switching backends does **not** migrate existing data — each store owns its
own. `VECTOR_STORE=chroma` additionally needs the `[chroma]` extra.

Research strategies and critic rubrics live in the `RESEARCH_STRATEGY` and
`CRITIC_RUBRIC` dicts; add a topic type by adding a key to both.

## Project layout

```
src/research_agent/
    graph.py            nodes, supervisor, routing, compile
    service.py          FastAPI surface: blocking + SSE, sessions, ops
    chat.py             terminal REPL with streamed progress
    static/index.html   the demo page — one self-contained file, no build step

    memory.py           Embedder + MemoryStore seams and four backends
    sessions.py         conversation sessions (SQLite / Postgres)
    metrics.py          runs table and the /metrics aggregation
    db.py               reconnecting Postgres connection shared by the stores

    usage.py            effective-dated price table and cost accounting
    limits.py           demo token, rate limit, rolling spend cap
    retry.py            retryable-error classification, backoff, node decorator
    observability.py    JSON logging and the optional OpenTelemetry seam

evals/                  golden dataset, graders, runner, CLI
tests/                  pytest suite (no keys, no network)
docs/                   this file and DESIGN.md
pyproject.toml          dependencies, extras, pytest and ruff config
```

`src/` layout: the package is only importable once installed
(`pip install -e '.[dev]'`), so a passing test run can't be relying on a
module that happens to sit in the working directory but would never reach
the image. `evals/` and `tests/` stay outside it — they're dev-only, and
keeping them out of the package is what keeps the eval dataset's scripted
model output out of production.

`service.py` is deliberately thin: it validates input, picks a state
constructor, runs the graph, and persists the result. No routing logic lives
there — any that did would mean the supervisor is no longer the single place
deciding what runs next.
