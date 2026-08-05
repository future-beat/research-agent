---
phase: 11-multi-machine-state-and-pooled-postgres
plan: 04
subsystem: deployment
tags: [supabase, postgres, pgvector, fly, cutover, latency, health-check]

# Dependency graph
requires:
  - phase: 11-01
    provides: "The pooled db.Database, prepare_threshold=None, the search_path configure callback, the advisory-locked lazy DDL"
  - phase: 11-02
    provides: "HEALTH_PROBE_BUDGET's 9s ceiling, close_all_pools in the lifespan, the machine key in /health"
  - phase: 11-03
    provides: "The armed deploy guards and the Supabase cutover runbook this plan executed"
provides:
  - "Production running on external managed Postgres: Supabase ap-southeast-2, session-mode pooler, sslmode=require"
  - "Fly release v5 -- all three stores Postgres-backed, dependencies ok, machine id in the body"
  - "The measured Fly-syd -> Supabase-ap-southeast-2 round trip: connect+TLS 119.2 ms, query p50 2.73 ms / p95 6.37 ms"
  - "Assumption A1 (latency) and A2 (connection headroom) both discharged with numbers"
  - "Pitfall 3 (prepared statements) discharged in production over 74 probe-triggering requests"
  - "Proof that Supabase keeps pgvector in the `extensions` schema -- the case 11-02 could not exercise"
affects: [11-05, phase-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cutover with the mount still attached, so `fly secrets unset` is a complete rollback"
    - "Verify the database through the deployed app, never by reading the secret"

key-files:
  created:
    - .planning/phases/11-multi-machine-state-and-pooled-postgres/11-04-SUMMARY.md
  modified: []

key-decisions:
  - "ONE `fly deploy` rather than `fly secrets deploy` then `fly deploy`. The secret was staged, so a single deploy lands the branch code and the DSN in the same release -- and `fly secrets deploy` would have re-released the OLD v4 image with the new DSN, giving Postgres backends running pre-pool code."
  - "The blocked anonymous HTTP run was NOT treated as a cutover failure and did NOT trigger rollback. The 502 is `AuthenticationError` from Anthropic (verified: HTTP 401 `API key is invalid` from api.anthropic.com), with a secret digest unchanged by this deploy. Rolling back the database for a model-provider credential would have discarded a verified-good cutover to fix nothing."
  - "The session round trip was proved at the store layer via `fly ssh console` instead of through HTTP, because every HTTP write path runs the model first. Same stores, same pool, same DSN, same `::vector` cast -- what it does not cover is FastAPI's dependency wiring, which `/health` and `/ready` already exercise on every check."
  - "Probe rows were deleted after the round trip; the one genuine failed production run was left in place. Deleting real data to make a metrics table look tidy is the opposite of the point."

requirements-completed: []

# Metrics
duration: 30min
completed: 2026-08-05
---

# Phase 11 Plan 04: The Supabase cutover Summary

**Production runs on external Postgres as of Fly release v5 — all three stores report their
Postgres classes, `/health` answers in 0.27–0.43 s against a 9 s ceiling, and the Fly-syd →
Supabase-ap-southeast-2 hop measures 2.73 ms p50 / 6.37 ms p95, roughly 880× inside the per-probe
budget. The volume is still mounted with its SQLite data byte-intact, so `fly secrets unset` remains
a complete rollback. One thing is broken and it is not the database: `ANTHROPIC_API_KEY` is revoked,
so no research run can complete — a pre-existing outage this cutover merely surfaced.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-08-05T06:40Z (approx)
- **Deploy:** 06:55:26Z → 06:57:24Z; app healthy 06:57:21Z
- **Tasks:** 2 (Task 1 was completed by the operator before this session)
- **Files modified:** 0 source files — this plan changes production, not the repository

## Task status

| Task | What | Status |
|---|---|---|
| 1 | Provision Supabase, set `DATABASE_URL` | **Done by the operator before this session.** Verified here, not redone |
| 2 | Verify the live cutover and measure the round trip | **Done**, with one criterion blocked — see § The blocked criterion |

## The deploy

`DATABASE_URL` was staged (`fly secrets list` showed `Staged`, not `Deployed`), so a single
`fly deploy -a research-agent` landed both the branch code and the DSN in one release.

This mattered. `fly secrets deploy` — the other obvious command, and the one the plan's Task 1 text
mentions — re-releases the **current image**. That was v4, built before plans 11-01 to 11-03. It
would have produced a machine talking to Supabase through the *pre-pool*, single-`RLock`-connection
code, with no per-probe deadline and no `machine` key: the cutover would have "worked" while
testing none of the phase's actual work.

```
$ fly deploy -a research-agent
> Updating machine config for 78156d2c32d738
> Machine 78156d2c32d738 reached started state
> Running smoke checks on machine 78156d2c32d738
> Checking health of machine 78156d2c32d738
✔ Machine 78156d2c32d738 is now in a good state
EXIT=0

$ fly releases -a research-agent | head -3
 VERSION │ STATUS   │ DESCRIPTION │ USER                       │ DATE
 v5      │ complete │ Release     │ hessam.abbaszadi@gmail.com │ 34s ago
 v4      │ complete │ Release     │ hessam.abbaszadi@gmail.com │ 19h43m ago

$ fly secrets list -a research-agent
 NAME              │ DIGEST           │ STATUS
 ANTHROPIC_API_KEY │ 35d77d861c484d1a │ Deployed
 VOYAGE_API_KEY    │ 8f9b09e2f3c2e557 │ Deployed
 SESSIONS_TOKEN    │ 64ffcc343b6ff637 │ Deployed
 DATABASE_URL      │ 2af0a92c0bc25b87 │ Deployed
```

The deployed release genuinely carries waves 1–3 rather than being assumed to. The startup line is
emitted by the code 11-01/11-02 wrote, and names all three backends:

```
{"ts": "2026-08-05T06:57:20+0000", "level": "INFO", "logger": "graph",
 "message": "service starting", "event": "startup",
 "sessions_backend": "PostgresSessionStore",
 "metrics_backend": "PostgresMetricsStore",
 "memory_backend": "PgVectorMemoryStore"}
```

Pre-deploy, the tree was verified green: `436 passed, 34 skipped` (exactly 11-03's baseline) and
`.venv/bin/ruff check .` → `All checks passed!`.

## `/health`, before and after

**Before (release v4):**

```json
{"status": "ok", "dependencies": "ok", "unreachable": [],
 "sessions": {"backend": "SQLiteSessionStore", "location": "/data/sessions.db", "count": 1},
 "metrics": {"backend": "SQLiteMetricsStore", "location": "/data/metrics.db", "runs_recorded": 3},
 "memory":  {"backend": "JSONMemoryStore", "notes": 3}}
```

Note: no `machine` key at all.

**After (release v5), verbatim:**

```json
{
  "status": "ok",
  "machine": "78156d2c32d738",
  "dependencies": "ok",
  "unreachable": [],
  "sessions": {
    "backend": "PostgresSessionStore",
    "location": "postgres://aws-0-ap-southeast-2.pooler.supabase.com/postgres",
    "reachable": true,
    "count": 0
  },
  "metrics": {
    "backend": "PostgresMetricsStore",
    "location": "postgres://aws-0-ap-southeast-2.pooler.supabase.com/postgres",
    "reachable": true,
    "runs_recorded": 1
  },
  "memory": {
    "backend": "PgVectorMemoryStore",
    "reachable": true,
    "notes": 0
  },
  "credentials": { "anthropic": true, "voyage": true }
}
```

All three moved, not one. `dependencies: "ok"`, `unreachable: []`, `machine` present and non-empty.
The `location` strings carry host and database and **no password** — and note the DSN shape puts the
project ref in the *username* (`postgres.<ref>`), which `urlparse().hostname` discards, so the ref is
absent too. T-11-16 holds against the real DSN, not just the test one.

`ssl_library` reports `OpenSSL` from inside the connection, and the DSN carries `sslmode=require`
per Task 1 — T-11-15 discharged.

### Timings

`curl -s -o /dev/null -w '%{time_total}\n'`, from a laptop in Australia:

| Sample | `/health` |
|---|---|
| 1 | **0.284184 s** |
| 2 | **0.314207 s** |
| 3 | **0.392035 s** |

Eight further samples, taken later: 0.299, 0.291, 0.427, 0.273, 0.270, 0.275, 0.272, 0.285 s.
All eleven are under the plan's 1.0 s criterion; the worst is 0.427 s, and most of that is the
laptop→Fly leg rather than anything the cutover changed.

```
/ready    HTTP 200  0.361387s      <- 200, not 503
/         HTTP 200  0.542505s
/demo     HTTP 200  0.282752s
/metrics  HTTP 200  0.292837s
```

`/demo` still reports `"token_required": false` — `DEMO_TOKEN` remains unset, per ADR-0006.

## Measured latency — Assumption A1 discharged

From **inside** the machine (`fly ssh console`), against the real DSN. The plan's RESEARCH snippet,
plus a warm-connection rerun:

```
connect+TLS  119.2 ms
query p50 2.14 ms  p95 11.22 ms  min 1.92  max 11.22        (20 samples, cold connection)
```

```
SELECT 1 over 40: p50 2.73 ms  p95 6.37 ms  p99 7.59 ms  min 2.03  max 7.59
```

And the statements `/health` actually issues, ten samples each:

| Probe | p50 | max |
|---|---|---|
| sessions (`COUNT` on `sessions`) | **2.84 ms** | 5.70 ms |
| metrics (`COUNT` on `runs`) | **3.23 ms** | 6.90 ms |
| memory (`COUNT` on `research_notes`) | **3.39 ms** | 4.93 ms |

**The plan asked to be told loudly if a single store probe exceeded ~1 s. Nothing is close.** The
worst observed store probe is 6.90 ms against a `HEALTH_PROBE_BUDGET` of 3000 ms — a headroom factor
of about 435×, and about 880× at the p50. Three sequential probes cost roughly **10 ms of database
time** against a 9 s ceiling inside Fly's 15 s check. The `/health` arithmetic does not need redoing
before 11-05, and doubling the fleet does not threaten it.

The one number worth carrying forward is **connect+TLS at 119.2 ms**, two orders of magnitude above
the query cost. That is the pooler handshake, and it is precisely why `PG_POOL_MIN_SIZE=1` holding a
warm connection matters: a cold checkout pays 119 ms before it runs anything. It is still far inside
budget, but it is the term that would dominate if the pool were ever sized to zero.

Server: **PostgreSQL 17.6**.

## Connection headroom — Assumption A2 discharged

```
pg_stat_activity total           : 16      (first measurement)
pg_stat_activity total           : 15      (warm, later)
pg_stat_activity as current_user : 5
  by state : [('active', 1), ('idle', 4)]
```

**15–16 total, against the plan's ceiling of 20 and the tier's 60.** The four idle plus one active
under `current_user` are the app's pool (`PG_POOL_MAX_SIZE=5`) plus the probe's own connection. One
machine × 5 is the expected footprint, and it is exactly what is there.

For 11-05: two machines × 5 = 10 app connections, so the projected total is roughly 21–26. Still
comfortably inside 60, with the non-app consumers (~10) being Supabase's own.

## pgvector — and a finding 11-02 explicitly could not reach

11-02 flagged this as *not proved*: "Supabase's actual `extensions` schema … a server that genuinely
keeps pgvector in `extensions` has not been exercised." It has now been.

```
pgvector installed in schema : extensions
public tables : research_notes, runs, sessions
vector-typed columns : [('research_notes', 'embedding', 'vector', 'extensions'),
                        ('research_notes_embedding_hnsw', 'embedding', 'vector', 'extensions')]
```

Two things follow.

**1. The lazy DDL ran and created the whole schema.** No DDL runs at construction time (SC-4), so
all three tables plus the HNSW index were created on first use, under `pg_advisory_lock`, against an
empty database. The concurrent-DDL path's first production exercise succeeded.

**2. The `search_path` callback turns out not to be load-bearing *on Supabase specifically* — and
this is worth saying plainly rather than quietly claiming a win.**

```
default search_path : "$user", public, extensions
unqualified ::vector on DEFAULT search_path       : RESOLVES
unqualified ::vector with CONFIGURED search_path  : RESOLVES
```

Supabase's own default `search_path` **already includes `extensions`**. So `memory.py`'s unqualified
`::vector` casts would have resolved even if 11-01's `_configure()` callback did not exist. The
callback is not wrong and should stay — it makes the requirement explicit rather than inherited from
a provider default that Supabase can change without telling us, and it is what makes the code
portable to a provider whose default omits it. But the honest statement is that it is **insurance
that has not yet been needed**, not a fix for a break that was observed. Anyone reading 11-01's
rationale should not conclude that the cast was failing before.

The strongest pgvector evidence is not a schema query, though — it is a real insert and a real
similarity search through the app's own code:

```
memory backend    : PgVectorMemoryStore
  describe        : 0 note(s) in pgvector table research_notes at postgres://aws-0-ap-southeast-2.pooler.supabase.com/postgres
notes             : 0 -> 1  (add 1111.4 ms, includes the embedding call)
pgvector query    : 1 hit(s) in 237.6 ms
  sentinel found  : True
```

A note was embedded via Voyage, written with a real 1024-dimension vector, and retrieved by cosine
similarity against a different query string. The `::vector` cast, the HNSW index and the extension
are all exercised end to end. (The 1111 ms and 237 ms are dominated by the Voyage HTTP call, not by
Postgres — compare the 3.39 ms `COUNT` on the same table.)

## The live round trip

A session was created, read back by id, appended to, listed and deleted — through
`PostgresSessionStore` on the deployed machine, against Supabase:

```
sessions backend  : PostgresSessionStore
created session   : 2c737084599646a8b0fcc0ec91c92ab2  (3.2 ms)
read back by id   : HIT  (2.8 ms)
  task matches    : True
  draft matches   : True
after append_turn : draft='second turn 36f36cce' turns=0
list() sees it    : True
metrics backend   : PostgresMetricsStore
metrics runs      : {'total': 1, ...} -> {'total': 2, ...}
delete session    : True
```

**Session id: `2c737084599646a8b0fcc0ec91c92ab2`.** A real write and a real read both landed on
Supabase, and the write was visible to a subsequent independent read.

This went through the store layer via `fly ssh console`, not through HTTP, for the reason in
§ The blocked criterion: every HTTP write path calls the model first. It is the same store classes,
the same pool, the same DSN and the same connection that `/health` uses — what it does not exercise
is FastAPI's dependency wiring, which `/health` and `/ready` cover on every 30 s check.

Probe rows were removed afterwards (`deleted probe notes: 1`, `deleted probe runs: 1`,
`sessions remaining: 0`, `notes remaining: 0`). One row was deliberately **left**: the genuine failed
production run from the 502 below.

```
remaining run : 3d8650566c6d4d29940d5ddfb8982761 research failed AuthenticationError
```

That row is itself evidence — a real HTTP request reached the metrics store and its write landed on
Supabase.

## Prepared statements — Pitfall 3 discharged in production

The plan required this be left for several minutes and at least six `/health` cycles, because
psycopg's default `prepare_threshold` is 5 and the failure appears at the sixth execution.

Over **74** successful `/health` + `/ready` responses (≈222 store probes), spanning the Fly check's
own 30 s cycle plus 40 driven requests, across ~9 minutes after the deploy:

```
prepared statement  : 0
_pg3_               : 0
PoolTimeout         : 0
OperationalError    : 0
AdminShutdown       : 0
ERROR/CRITICAL      : 0
health+ready 200s   : 74
non-200 health/ready: 0
```

`prepare_threshold=None` took effect. This is the endpoint 11-01 set unconditionally so that the
choice of pooler endpoint would stop being load-bearing, and production agrees.

## The blocked criterion — an authentication gate, not a cutover failure

`POST /research` returns **502** in 0.73 s. The cause is not the database:

```
{"level": "WARNING", "logger": "graph", "message": "run failed",
 "event": "run_failed", "run_id": "3d8650566c6d4d29940d5ddfb8982761",
 "mode": "research", "error": "AuthenticationError"}
INFO: "POST /research HTTP/1.1" 502 Bad Gateway
```

Probed directly from inside the machine, printing status codes only and never the key:

```
anthropic GET /v1/models   : HTTP 401 -- {"type":"error","error":{"type":"authentication_error",
                                          "message":"API key is invalid."},"request_id":null}
voyage POST /v1/embeddings : HTTP 200
anthropic key: len=108 prefix=sk-ant-api03 suffix=twAA whitespace=False
voyage key:    len=46  prefix=pa-  whitespace=False
```

**`ANTHROPIC_API_KEY` is revoked or expired.** The key is well-formed, correctly-prefixed and has no
stray whitespace — Anthropic is rejecting it server-side. Voyage is fine, which is why the pgvector
embedding above worked.

**This was not caused by the cutover, and rollback would not fix it.** The evidence:

- The `ANTHROPIC_API_KEY` digest is `35d77d861c484d1a` both **before** and after this deploy —
  captured in the pre-deploy `fly secrets list`. Nothing in this session touched it.
- Plans 11-01 to 11-03 changed `db.py`, `/health`, tests and docs. Nothing on the model-client path.
- The failure is a 401 from `api.anthropic.com`, a third party, for a credential of correct shape.

Rolling the database back would discard a verified-good cutover and leave the demo exactly as broken.
So the correct response was to record it and stop, not to reverse the plan.

**A real gap this exposed, flagged and not fixed:** `/health` reports `"credentials": {"anthropic":
true}` for a revoked key, because it checks *presence*, not *validity*. The liveness probe therefore
cannot see the outage that actually takes the demo down — the one thing a stranger clicking the demo
would notice. Making `/health` validate credentials is a design change (an outbound call on every
probe, with its own budget implications), so it is Rule 4 territory and out of this plan's scope.
Recorded for Phase 12 planning.

## Nothing irreversible happened

| Check | Result |
|---|---|
| `fly volumes list -a research-agent` | `vol_vdegz1021w669gx4 · created · agent_data · 1GB · syd · ATTACHED VM 78156d2c32d738` |
| Machine count | **1** (`78156d2c32d738`, version 5, `1 total, 1 passing`) |
| `[[mounts]]` in `fly.toml` | **present** (1 block) |
| `min_machines_running` | **1** |
| `SESSION_DB_PATH` / `METRICS_DB_PATH` / `VECTOR_STORE_PATH` | all still in `[env]` |
| `git status --porcelain fly.toml` | empty — no diff at all |
| `fly scale count` | **not run** |

The topology is exactly as 11-03 left it. This plan changed no file in the repository except this
summary.

**And the rollback target is verified intact**, not merely assumed:

```
$ fly ssh console -a research-agent -C "ls -la /data"
-rw-r--r-- 1 agent agent 79382 Aug  4 11:25 agent_memory_store.json
-rw-r--r-- 1 agent agent 20480 Aug  5 06:57 metrics.db
-rw-r--r-- 1 agent agent 32768 Aug  5 06:57 sessions.db

sessions.db rows: 1
metrics.db rows: 3
memory json notes: 3
```

Those are **exactly** the pre-cutover `/health` counts (sessions 1, runs_recorded 3, notes 3). The
SQLite data is untouched and sitting underneath, merely unused.

**The escape hatch is `fly secrets unset DATABASE_URL -a research-agent`, and it is UNTESTED.** It
was not exercised, because exercising it would have meant reverting a working cutover to prove a
mechanism. What *is* verified is everything the rollback depends on: the volume is attached, the
mount is in `fly.toml`, all three `*_DB_PATH` vars are still set, no backend is pinned (so the
selectors fall back to `sqlite`/`json` the moment the DSN is empty), and the data is intact at the
row level. State this honestly in 11-05 rather than as a tested path.

## The cost of starting clean, made visible

CONTEXT locked "start clean, keep the volume as backup", and named the cumulative `/metrics` history
as the one genuinely irreplaceable thing given up. It is now given up, and it shows on the wire:

- `/demo` `spent_24h_usd`: **0.2289 → 0.0**
- `/metrics` `runs`: `{"total": 3, ...}` → `{"total": 1, "completed": 0, "failed": 1, "failure_rate": 1.0}`

The single remaining run is the `AuthenticationError` failure from this session, which is why the
public `/metrics` currently advertises a **100% failure rate**. That is accurate, not a bug — but it
is a bad look on a portfolio demo and it will stay that way until a successful run is recorded, which
needs the Anthropic key. Worth knowing before showing anyone the URL.

The three old demo sessions and three notes are still on the volume, disposable as planned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `fly secrets deploy` would have shipped the DSN on the pre-pool image**
- **Found during:** Task 2 setup
- **Issue:** The plan's Task 1 text and the success criteria both mention `fly secrets deploy`. With
  the secret staged, that command re-releases the **current** image — v4, built before plans 11-01
  to 11-03. The result would have been Supabase-backed stores running the single-`RLock`-connection
  code, with no per-probe deadline and no `machine` key, and every claim in this summary would have
  been about untested code.
- **Fix:** A single `fly deploy -a research-agent`, which applies staged secrets *and* the branch
  code in one release. Confirmed the deployed release genuinely contains waves 1–3 via the startup
  log line naming all three Postgres backends and the `machine` key in `/health` — rather than
  assuming it, as the plan's critical constraint 1 required.
- **Files modified:** none
- **Verification:** release v5; `DATABASE_URL` status `Staged` → `Deployed`

**2. [Rule 3 — Blocking] The container has no `curl`, and `fly ssh console -C` cannot take a heredoc**
- **Found during:** Task 2, latency measurement
- **Issue:** RESEARCH's snippet is `fly ssh console -C "python - <<'PY' ... PY"`. `-C` runs a single
  command with no shell, so the heredoc is passed as a literal argument and Python never sees a
  script. A `sh -c` wrapper with `curl` failed too: `sh: 1: curl: not found`.
- **Fix:** base64-encode the script locally and run
  `python -c "import base64;exec(base64.b64decode('...'))"`. Quoting-safe, and it keeps the DSN
  inside the machine — the script reads `os.environ['DATABASE_URL']` and never prints it.
- **Files modified:** none (scratchpad only)

**3. [Rule 1 — Bug] Two probe scripts used wrong attribute/column names**
- **Found during:** Task 2, round trip
- **Issue:** `Session.session_id` does not exist (the field is `Session.id`; `session_id` appears
  only in `summary()`'s dict), and `research_notes`'s text column is `text`, not `content`. Both
  raised after the writes had already landed, leaving a probe session and a probe note behind.
- **Fix:** Corrected both, and the rerun explicitly deletes the stray session
  `6a27bc953f1f4896905802c15658509d` from the failed attempt (`True`) before proceeding. Final state
  confirmed: `sessions remaining: 0`, `notes remaining: 0`.
- **Files modified:** none (scratchpad only)

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 probe bug). None changed the repository.

## Authentication gates

**One, and it is unresolved.** `ANTHROPIC_API_KEY` returns HTTP 401 `API key is invalid` from
`api.anthropic.com`. It blocks the plan's "a session created through the live service is readable
back from it" *via HTTP*, and the orchestrator's "an anonymous run still completes". The database
half of both was proved at the store layer instead. See § The blocked criterion.

Required to clear it: a valid key, then
`fly secrets set -a research-agent ANTHROPIC_API_KEY='sk-ant-...'`, then re-run
`curl -X POST https://research-agent.fly.dev/research -H 'Content-Type: application/json' -d '{"question":"..."}'`
and confirm a 200 with a `session_id`.

## Success criteria

| Criterion | Status |
|---|---|
| Supabase live in `ap-southeast-2` with `vector` enabled | ✅ pgvector confirmed in the `extensions` schema |
| `DATABASE_URL` set against the session-mode pooler, 5432, `sslmode=require` | ✅ host `aws-0-ap-southeast-2.pooler.supabase.com`, `ssl_library: OpenSSL` |
| Deploy completed, release recorded | ✅ **v5** |
| `/health` — three Postgres stores, `dependencies: ok`, `machine` id, no credential | ✅ |
| `/health` under 1.0 s on all samples | ✅ 0.270–0.427 s across 11 samples |
| pgvector working — notes table exists / creatable | ✅ real insert + cosine search, sentinel retrieved |
| `FLY_MACHINE_ID` in the body | ✅ `78156d2c32d738` |
| `/ready` 200, not 503 | ✅ |
| Measured latency recorded | ✅ connect+TLS 119.2 ms; p50 2.73 ms / p95 6.37 ms |
| `pg_stat_activity` under 20 | ✅ 15–16 |
| Zero `prepared statement` errors after ≥6 cycles | ✅ 0 over 74 responses |
| `/`, `/demo`, `/metrics` 200; `/demo` `token_required: false` | ✅ |
| A session round-trips against the new database | ✅ at the store layer — **not** through HTTP |
| An anonymous research run completes | ❌ **BLOCKED** — `ANTHROPIC_API_KEY` revoked, unrelated to the cutover |
| `[[mounts]]` present, machine count 1, volume untouched | ✅ all three |

## Issues Encountered

**`/health` cannot see the outage that matters.** Covered above: `credentials.anthropic: true` for a
revoked key. Phase 12 material.

**`/metrics` publicly advertises a 100% failure rate.** A true statement about a one-row table.
Resolves itself on the first successful run.

**The `search_path` callback is untested insurance, not a proven fix.** Supabase's default
`search_path` already contains `extensions`. Recorded above so nobody later reads 11-01's rationale
as describing an observed break.

**A `PythonFinalizationError` on interpreter shutdown in the ssh probes.** `ConnectionPool.__del__`
tries to join its worker threads during finalization. It is noise from my one-shot scripts exiting
without `close_all_pools()` — the service's lifespan calls it properly — but worth knowing before
someone reads it as a pool bug.

## Next Phase Readiness

Ready for 11-05, with these carried forward:

1. **The `/health` budget has enormous headroom and does not need re-deriving.** Worst store probe
   6.90 ms against a 3000 ms budget. Two machines will not change that; the term to watch is
   connect+TLS at 119.2 ms, which is why `PG_POOL_MIN_SIZE` should not go to 0.
2. **Connection headroom projects to ~21–26 of 60** at two machines. Re-measure after scaling, but
   there is no reason to expect trouble.
3. **The rollback is untested.** Everything it depends on is verified, but `fly secrets unset` was
   never run. Do not describe it as proven.
4. **11-05's `fly.toml` edit is a four-part change** (mount out, three `*_DB_PATH` out, three pins
   in, `min_machines_running` ≥ 2) or `tests/test_deploy_config.py` fails — that is 11-03's intent.
   The stateless arm of both guards gets its first live-fire test there.
5. **`11-VALIDATION.md`'s skip-count invariant still says 28.** It is 34. 11-02 and 11-03 both
   flagged it; still owed, in 11-05 Task 4.
6. **`ANTHROPIC_API_KEY` must be replaced before the phase can claim a working demo.** SC-2/SC-3 are
   about state being shared across machines, which `/health`'s `machine` key demonstrates without a
   model call — so 11-05 is *not* blocked. But "demonstrable to a stranger" is not true until a run
   completes.
7. **The branch is unpushed.** `gsd/phase-11-multi-machine-postgres` holds waves 1–4. The plan calls
   for landing 11-01..11-03 via a **pull request** rather than a push, since `enforce_admins` is
   `false`. Not done here — out of this plan's authorisation.

## Self-Check: PASSED

- `.planning/phases/11-multi-machine-state-and-pooled-postgres/11-04-SUMMARY.md` — created (this file)
- No source file modified; `git status --porcelain fly.toml` empty, as claimed
- Fly release **v5** exists and is `complete` — `fly releases -a research-agent`
- `DATABASE_URL` reports `Deployed`, not `Staged` — `fly secrets list -a research-agent`
- Volume `vol_vdegz1021w669gx4` still attached to `78156d2c32d738` — `fly volumes list -a research-agent`
- Every number, JSON body and log line quoted above is literal command output captured this session,
  not a description of it

---
*Phase: 11-multi-machine-state-and-pooled-postgres*
*Completed: 2026-08-05*
