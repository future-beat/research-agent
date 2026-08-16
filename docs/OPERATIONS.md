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
`/health` reports two separate facts about each key and never the value itself:
whether it is **present**, and whether it actually **works** (`anthropic_valid`
and `voyage_valid`, with a `_checked_at` and a `_error` beside each). A key that
is present but revoked or expired therefore stops looking healthy — the case
that cost this service an outage in Phase 11, when presence was all `/health`
could see.

The validity half comes from a probe the endpoint kicks off in the background
and never waits for; the answer is served from a cache and refreshed no more
often than `CREDENTIAL_PROBE_TTL`, so a key that goes bad surfaces within one
TTL rather than on the next real run. **The check still never blocks on
Anthropic or Voyage**, which is the property to preserve if you touch this: a
provider outage must leave `valid` as `null` — "could not determine", which is
also what an absent key reads — and never turn into a restart loop on a
container that is perfectly healthy. `false` means the provider actually
rejected the key, and only that.

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

**Deploys are manual.** Releases are cut by hand with
`fly deploy -a research-agent` from a tested working tree.
`fly releases -a research-agent` is the evidence: every release is attributed to
the owner's personal account, never a machine token.

**Auto-deploy was tried and turned back off, 2026-08-12.** While it was enabled,
three merges to `main` — PRs #19, #20 and #21, all with green CI — produced **no
release**: `fly releases` stayed on v12 from the previous day, the live service
kept serving pre-merge code, and GitHub's deployments API showed nothing since
2026-08-01. A hand-run `fly deploy` produced v13 immediately. The setting was
switched off the same day rather than left on and unreliable, which is the right
call: a deploy path that fires sometimes is worse than one that never fires,
because the first teaches you to stop checking.

**A deploy can fail and still look fine, which is the other reason to confirm.**
On 2026-08-12 a run died at `dial tcp: lookup api.machines.dev: no such host` —
a transient resolution failure, not a config problem; the same lookup succeeded
seconds later and the retry deployed. Two traps in that one incident. First, the
running service was entirely healthy throughout, because the failure was flyctl
reaching Fly's API rather than anything wrong with the app — so "the site is up"
is not evidence the deploy landed. Second, `fly deploy | tail` reports **`tail`'s**
exit status, so a failed deploy through a pipe exits 0. Redirect instead of
piping if you need the status:

```
fly deploy -a research-agent > deploy.log 2>&1; echo "exit=$?"
```

**An interrupted deploy splits the fleet, and health checks will not tell you.**
Also on 2026-08-12, a deploy was killed partway through its rollout. It left the
release stuck in `running` and the two machines on *different versions*, while
every health check passed and every endpoint returned 200 — because that
particular image differed only in a comment. Had it carried a behavioural
change, two machines would have been serving different code with nothing
complaining. The fix is another `fly deploy`, which converges both machines onto
a fresh release; the abandoned release stays listed as `running` forever and can
be ignored. **`fly status` is the check that catches this — compare the VERSION
column across machines. `/health` cannot see it.**

**The operational consequence:** merging to `main` ships nothing. Run the command
after any merge you expect to be live, and confirm:

```
fly deploy -a research-agent
fly releases -a research-agent      # new version, dated after the merge
```

This distinction is not pedantry here. This document claimed
GitHub-integration deploys once before, it was false, and Phase 10 spent a plan
correcting it. A deploy method believed but not observed is how `main` and the
deployed release drift apart silently — and that is the same failure in either
direction: assuming a merge shipped when it did not, or assuming it did not when
it did.

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

### Row level security

Every table this service creates sits in `public`, and Supabase can expose that
schema over PostgREST — an HTTP API whose `anon` key is public by design, with
RLS as the intended control. This service never uses PostgREST; it connects
directly with psycopg. So the API is pure attack surface here.

**The application enables RLS itself.** Each Postgres schema constant ends with
`ALTER TABLE … ENABLE ROW LEVEL SECURITY`, applied under the same advisory lock
as the rest of the DDL, so it lands on the next deploy with no manual step and
covers tables created later — including the corpus table
`migrate.py embeddings re-embed --to` builds on demand. `ENABLE`, never
`FORCE`: RLS exempts a table's owner, that owner is the `DATABASE_URL` role
because it ran the DDL, and the exemption is what makes an empty policy set safe.
`FORCE` would remove it and every query would return zero rows *silently*.
`tests/test_row_level_security.py` pins both halves.

**One thing the application cannot do: revoke the grants.** Supabase's default
privileges hand `anon` and `authenticated` table access, and those roles do not
exist on a plain Postgres — the statement would fail here and in CI. Run this
once, in the Supabase SQL editor, per database:

```sql
-- STEP 0 — pre-flight, read-only. Two jobs: table_owner must match the
-- DATABASE_URL role (or RLS makes the service read zero rows), and the value
-- it prints is the role name step 2 requires.
SELECT DISTINCT pg_get_userbyid(c.relowner) AS table_creating_role
FROM   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE  n.nspname = 'public' AND c.relkind = 'r';

-- STEP 1 — revoke what is already granted.
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON SCHEMA public FROM anon, authenticated;

-- STEP 2 — stop FUTURE tables being granted. `FOR ROLE` is MANDATORY and must
-- name the role step 0 printed. Default privileges are per granting role, so
-- the bare form silently governs only the role that runs it: measured
-- 2026-08-12, running it as `postgres` left a table later created by a
-- different role holding all seven privileges for anon. Substitute the role
-- below if step 0 printed something other than `postgres`.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON FUNCTIONS FROM anon, authenticated;

-- STEP 3 — verify. Both must report none.
SELECT COALESCE(string_agg(DISTINCT grantee, ', '), '(none - correct)')
FROM   information_schema.role_table_grants
WHERE  table_schema = 'public' AND grantee IN ('anon', 'authenticated');

SELECT COALESCE(string_agg(DISTINCT pg_get_userbyid(d.defaclrole)
                           || ' -> ' || d.defaclacl::text, '; '),
                '(none - correct)')
FROM   pg_default_acl d JOIN pg_namespace n ON n.oid = d.defaclnamespace
WHERE  n.nspname = 'public' AND d.defaclacl::text LIKE '%anon%';
```

Verified end to end on a local stand-in reproducing Supabase's default posture
(14 grant rows → none; a table created *after* the script receives no grants;
`anon` then gets `permission denied for table sessions` on both read and write).

**Reading step 3's second result — `supabase_admin` rows are expected and are
not yours to remove.** Run against the live project on 2026-08-12, that query
returned three rows all granted by `supabase_admin` (tables `arwdDxtm`,
sequences `rwU`, functions `X`) and **no row granted by `postgres`**. That
absence is the success signal: default privileges are per granting role, a
`postgres` row is what would grant `anon` on future app tables, and a successful
revoke deletes the row outright rather than emptying it. The `supabase_admin`
entries govern only objects *that* role creates — platform-managed, not the
app's tables — and `postgres` is not a member of `supabase_admin`, so trying to
alter them errors rather than helping.

The end state, confirmed with one query:

```sql
SELECT c.relname AS table_name,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity AS rls_on,
       COALESCE((SELECT string_agg(DISTINCT g.grantee, ',')
                 FROM information_schema.role_table_grants g
                 WHERE g.table_schema = 'public' AND g.table_name = c.relname
                   AND g.grantee IN ('anon','authenticated')), '(none)') AS api_grants
FROM   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE  n.nspname = 'public' AND c.relkind = 'r'
ORDER  BY 1;
```

Five rows, every one `owner = postgres`, `rls_on = t`, `api_grants = (none)`.

**`service_role` is deliberately untouched, and it bypasses all of this.** That
role carries `BYPASSRLS`, so its key reads and writes everything regardless of
RLS or grants. Unlike the anon key it is a genuine secret — it must never reach
a browser, a client bundle, or this repository.

**Stronger still: turn the Data API off** in Settings → API. Nothing here uses
it. Do that and the whole surface goes away, RLS included as a second layer.
Verify from Advisors → Security, which is the authoritative view — probing
`/rest/v1/<table>` from outside cannot distinguish "Data API off" from "gateway
rejected a missing key", so it is not a check worth trusting.

**Confirmed 2026-08-12:** the Data API was turned off and Fly release v13 carried
the RLS DDL. Advisors → Security then reported the five
`rls_disabled_in_public` errors and the `sensitive_columns_exposed` error on
`runs` **cleared**.

### Do not "fix" the five `rls_enabled_no_policy` notices

Advisors now reports five `INFO` findings — one per table — saying RLS is
enabled but no policies exist. **That is this design working, not a defect, and
the linter's suggested remediation would undo the phase that put it there.**

The linter assumes the normal Supabase shape, where `anon` and `authenticated`
reach tables through PostgREST and policies decide which rows they see. Here
nothing should reach these tables through PostgREST at all. RLS with zero
policies denies every role except the table's owner, and the owner is the
`DATABASE_URL` role — so the service works and everyone else gets nothing.
Adding a policy is the only way to grant access back, and a permissive one
(`USING (true)`, which is what a quick fix reaches for) would restore exactly
the exposure measured on 2026-08-12: readable session text and identity hashes,
and a deletable `runs` table with the spend cap's only input in it.

The finding is `INFO`, it stays, and it stays for a reason. If a future change
genuinely needs PostgREST access, that is a design decision with its own record,
not a linter notice to clear.

**Why this is not merely a privacy matter.** `runs` is the daily spend cap's
only input: `spend_since` sums it. Measured on a local stand-in against the real
DDL, a role with the default `anon` grants deleted every row of `runs` without
error. An emptied ledger reads as $0 spent, and the one control bounding the
Anthropic bill stops bounding it.

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

Either command creates the target through the pgvector store, so the new table
carries row level security the moment it exists — see
[Row level security](#row-level-security). Nothing to remember here, which is
the point: a table born after the last manual fix is exactly the one a manual
fix misses.

The cost preview **always** prints — model, width, row count, tokens, the rate with
the date it was verified, and the estimated dollars. Without `--yes` the command
stops there and exits nonzero; `--dry-run` beats `--yes` if you pass both. An
unpriced model refuses rather than quoting `$0.00`, and it refuses before it opens
the database, so discovering that a model is unpriced costs nothing.

**The first `count_tokens` call downloads a tokenizer from the Hugging Face hub.**
Voyage's client fetches it once and caches it, so the first preview on a fresh
machine or a fresh container needs outbound network and takes a few seconds
longer than you expect. Subsequent calls are offline. If the box has no egress to
`huggingface.co`, the preview is where it will fail. Measured 2026-08-09 on a
cold cache: first call 2.4s, second 0.4s, and each *model* fetches its own
tokenizer — switching from `voyage-3.5` to `voyage-3.5-lite` pays the download
again.

**Raise the pool timeouts if you are running this from a laptop.** The connection
defaults (`PG_POOL_TIMEOUT=2.0`, `PG_CONNECT_TIMEOUT=3`) are tuned for the Fly
machines, which sit in the same region as the database. From a developer machine
the handshake to the Supabase session pooler was measured on 2026-08-09 at
0.43s–5.63s — straddling the default — and the commands then fail intermittently
with `psycopg_pool.PoolTimeout` before they touch any data. This is a distance
problem, not a fault:

```
PG_POOL_TIMEOUT=30 PG_CONNECT_TIMEOUT=15 \
  python -m research_agent.migrate embeddings copy --from ... --to ...
```

A `PoolTimeout` is always safe to retry: it is raised acquiring the connection,
before any statement is sent.

### 3. Verify

Both commands print their own numbers and exit nonzero if the numbers are wrong —
read them rather than trusting the exit code alone.

`copy` prints row counts on both sides, how many source rows matched on
`(text, owner, created_at)`, how many were unmatched, and how many embeddings
differ byte-for-byte. All four should read as a clean move; a nonzero
byte-difference, or a matched count below the source count, means stop.

`re-embed` prints the predicted token count, the count Voyage's response
reported, and what the second one comes to at list price.

**Neither number is an invoice, and they are expected to disagree.** Measured
2026-08-09: a 12-note corpus the local tokenizer counted at **40** tokens came
back from the API reported as **25**, and a single one-word document came back
as **0** — which nothing that returns an embedding can actually have cost. Read
the predicted figure as an honest upper bound, the reported figure as what the
response said, and **Voyage's usage dashboard as the only authority on what you
were billed**. Embedding spend is still absent from `/metrics` entirely.

Then check recall yourself if the model changed. There is a frozen golden query
set in `src/research_agent/recall_golden.py` and a `recall_delta` over it; a copy
must show **zero** delta, which is what makes any delta a re-embed shows
attributable to the model rather than to the move.

Two things will quietly make that comparison lie, and both have been measured:

- **A new model re-scores everything**, so `assert_tie_free` has to be re-run
  against the re-embedded table before an ordered comparison over it means
  anything. If it fails, the delta is unmeasurable — report that rather than a
  number.
- **The query vector is a variable too.** `recall_delta` runs each golden query
  once per table, and the real API does not guarantee a bit-identical vector for
  the same text on two calls. On 2026-08-09 the live source table compared with
  *itself* deltaed on 2 of 8 queries for that reason alone. Wrap the embedder in
  `recall_golden.FrozenQueryEmbedder` so each query text is embedded once and
  reused; across a model change, use one wrapper per model.

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
lint · tests · evals            ruff, 806 tests, 59 offline eval cases
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
| `CREDENTIAL_PROBE_TTL` | Seconds a provider credential verdict is served from cache before a refresh is kicked off — how **often** a provider is asked anything at all, where `HEALTH_PROBE_BUDGET` bounds how **long** one store probe may take. Floored at 30s, so probe volume tracks this value rather than request volume | `300.0` |
| `CHROMA_PATH` · `CHROMA_COLLECTION` | Chroma location and collection | `chroma_store` / `research_notes` |
| `VOYAGE_EMBEDDING_MODEL` | Embedding model | `voyage-3.5` |
| `CRITIC_MODEL` | The model the in-graph critic runs on, read per call. Unset or blank means the critic runs on `MODEL`, exactly as before Phase 16. **Production pins `claude-opus-5`** (fly.toml `[env]`) — see below | *(unset — the critic runs on `MODEL`)* |
| `CLASSIFIER_MODEL` | The model the classifier runs on, read per call. The default is **inverted** from `CRITIC_MODEL`'s: unset or blank means `claude-opus-5`, not `MODEL`, because there the default *is* the measured production choice (ADR-0013). Setting it is the emergency downgrade. fly.toml carries a matching, deliberately non-load-bearing line | *(unset — the classifier runs on `claude-opus-5`)* |
| `AGENT_MAX_RUN_COST_USD` | Per-run spend cap; `0` disables. Bounds **multiplied** cost since Phase 14 — see below | `1.00` |
| `COST_DISCOUNT_FACTOR` | Negotiated discount applied to computed Anthropic cost, including the per-search fee. `≤ 0` or unparseable falls back to `1.0`, so a typo cannot disarm the spend caps by costing every run at $0.00 | `1.0` |
| `INFERENCE_GEO_MULTIPLIER` | The **rate** charged when a response reports `usage.inference_geo == "us"`; applicability is observed from the API per call, never declared here. Same clamp as the discount | `1.1` |
| `AGENT_MAX_ATTEMPTS` | Attempts per node, including the first | `4` |
| `AGENT_RETRY_BASE_DELAY` · `AGENT_RETRY_MAX_DELAY` | Backoff bounds, seconds | `1.0` / `30.0` |
| `DEMO_DAILY_USD_CAP` | Rolling 24h ceiling across all callers; `0` disables | `5.00` |
| `DEMO_RATE_LIMIT_PER_HOUR` | Requests per **caller identity** (the signed cookie), not per IP; `0` disables | `10` |
| `DEMO_RESERVED_RUN_USD` | What a starting run claims against the daily cap up front, settled to the real cost when it ends; `0` reserves nothing | `0.30` |
| `IDENTITY_SIGNING_SECRET` | Signs the anonymous caller-identity cookie. Set app-wide so a cookie minted by one machine verifies on the other; unset, each process invents an ephemeral one and identities don't survive a bounce | *(unset)* |
| `DEMO_TOKEN` | When set, write endpoints need an `X-Demo-Token` header. Also accepted as a fallback for `SESSIONS_TOKEN` | *(unset)* |
| `SESSIONS_TOKEN` | Operator credential, sent as `X-Demo-Token`: lists and deletes **every** owner's sessions. While unset, only the operator view is closed — callers still reach their own | *(unset)* |
| `SESSION_TTL_DAYS` | A session stops resolving this long after its last turn, and is swept on the next run. Reads don't renew it | `7` |
| `NOTE_TTL_DAYS` | A stored note stops being recalled this long after it was written, and is swept on the next `add()`. Same value and same mechanics as sessions, on all four vector backends | `7` |
| `NOTE_CAP_PER_OWNER` | The second bound on notes, beside the TTL: one owner holds at most this many live notes, and adding past the cap evicts that owner's oldest inside the same `add()` that already sweeps expiry — identically on all four vector backends, and never across owners. `≤ 0` or unparseable falls back to `100`, so a typo cannot silently switch recall off by making every write evict the note it just made; an operator who wants no cap leaves this unset. It bounds **every** `add()`, including the notes the eval harness seeds, so a future large-corpus eval case would be truncated to the cap | `100` |
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

**The credential probe adds nothing to that ceiling.** It calls Anthropic and
Voyage, which are far slower and far less reliable than any of the stores — but
it runs on a pool thread the request never joins, so it contributes exactly zero
to the bound above. The 9s figure is still the whole story. If a future change
ever makes `/health` *wait* for a credential verdict, this paragraph stops being
true and Fly's 15s check timeout becomes a provider's to spend.

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

### The two cost multipliers, and what they do to the caps

`COST_DISCOUNT_FACTOR` and `INFERENCE_GEO_MULTIPLIER` both scale computed cost
and neither touches the price table — list prices stay list prices and
effective-dating resolves exactly as before. Both apply in one function,
`CallUsage.cost_usd`, which every consumer already reads: the per-run cap, the
runs table, `/metrics`, the daily-cap reserve math, the API payload, the evals
harness and the demo badge all inherit them without a line of their own.
`/pricing` reports both values in effect, and multiplies nothing.

**They are not the same kind of knob.** The discount is a fact about your
contract that the API cannot report, so you declare it. The geo multiplier is a
fact about where a particular call ran, which the API *does* report, so the env
var sets only the **rate** and the response's `usage.inference_geo` decides
whether it applies at all. Unset the geo variable and nothing changes; set it to
anything you like and still nothing changes until a response says a call ran in
a billed geo. This is deliberate: a workspace `default_inference_geo` can put
requests in a billed geo with no code change, and an env-only flag would then
disagree with the invoice in one direction or the other. An unrecognised geo
value is not billed at 1.0 — it raises, and lands as `pricing_unknown`, the same
way an unpriced model does.

Both clamp to their default on `≤ 0` or an unparseable value. The reason is the
caps, not tidiness: `COST_DISCOUNT_FACTOR=0` is a plausible typo and a plausible
reading of "no discount", and honouring it would cost every run at $0.00, which
a per-run or daily cap compared against $0.00 never fires on.

**What this does to `DEMO_RESERVED_RUN_USD`.** A research run measures
**$0.21–0.32** against a **$0.30** reservation, so a busy run at the top of that
band is already at the estimate and the published `1.1` geo multiplier can carry
it past — which is the by-design tail below, not a hole. A discount at or below
`1.0` moves the other way and makes the reservation *more* conservative, so the
cap binds slightly sooner during a burst and never overshoots. Revisit the
default if a future pricing dimension pushes a typical run above $0.30 — raise
`DEMO_RESERVED_RUN_USD` proportionally rather than adjusting anything else.

`AGENT_MAX_RUN_COST_USD` now bounds **multiplied** cost, which is the correct
semantics rather than a side effect: a discounted deployment gets more work per
capped dollar because the cap bounds *spend*, not calls.

### `CRITIC_MODEL` and the reservation, together

Since Phase 16 the in-graph critic runs on its own model, and production pins
`CRITIC_MODEL = 'claude-opus-5'` in fly.toml `[env]` — committed configuration
rather than a secret, so the stance is visible in the repo. The stance: **the
critic that gates a draft is deliberately more capable than the writer that
produced it** (ADR-0010). Unset the variable and the critic goes back to
`MODEL` with no other change.

Since Phase 21.5 the classifier joined the per-node models, at
**+$0.0005 a run** (~140 input tokens, ~5 output, thinking disabled) — about
0.2% of a run and two orders of magnitude below the critic's share, so it moves
no reservation and no trigger below. Its knob's default is the inverse of this
one's (ADR-0013). The writer and researcher are what stay on `MODEL` (Sonnet 5).

**What it costs, and what finally moved the reservation.** The critic is a small
part of the bill and was never the reason to resize: on the first live run after
the cutover it was **$0.0219** of a **$0.2093** run — about 12% — while the
researcher node alone was **$0.173**. Phase 17 then moved a whole class of run
across the line rather than moving the line: a follow-up whose notes cannot
answer the question now runs one research pass before answering, so those turns
cost like a research run rather than the pennies a notes-only answer costs.

What actually moved the number was measuring the result of both. Two live runs:

| When | Release | Run | Cost |
|---|---|---|---|
| 2026-08-10 | v10 | research, 1 critic call | **$0.2093** |
| 2026-08-11 | v11 | research at 9 iterations | **$0.25–0.32** |

So `DEMO_RESERVED_RUN_USD` **went from $0.20 to $0.30 on 2026-08-11**, by the
rule already written here rather than by a new one. The literal triggers below
had not fired; the condition they were proxies for — a typical run above the
estimate — had, and a measurement outranks a proxy. A fully-revised run makes at
most 3 critic calls and can reach **~$0.42**, which is *outside* the estimate by
design: the reservation is sized on the typical run, `AGENT_MAX_RUN_COST_USD`
bounds the tail per run, and settlement replaces the estimate with the real
figure at run end.

**Operationally, the resize costs concurrency and buys accuracy.** Against the
default **$5.00** daily cap it is about 16 runs admitted at once instead of 25 —
still far above what a demo sees, and now the cap counts in-flight spend at
roughly what that spend turns out to be.

**There is no dated threshold any more.** This section named **2026-09-01**, when
Sonnet 5's introductory window was to close and lift a typical *unchanged* run by
roughly a third. Anthropic made **$2/$10 per MTok permanent on 2026-08-12**, so
that crossing will not happen and the **~$0.40** it called for is not owed —
**$0.30** stands, on the measured $0.21–0.32 band rather than on a calendar.

Raise `DEMO_RESERVED_RUN_USD` when a threshold is actually crossed: a price rise,
pointing `CRITIC_MODEL` at something priced above Opus, or a measurement putting
a typical run above the estimate. Worth noting which of those has ever fired —
only the measurement. The date was a proxy, it was retired without firing, and
the resize that did happen came from two live runs.

**What is checked and what is not.** Pricing is: a `CRITIC_MODEL` with no row
in the price table costs the run nothing and reports `pricing_unknown` on that
run rather than failing it. API compatibility is **not**: the critic node sends
`thinking` and `output_config` parameters, and a model that rejects them
returns a 400, retries, and fails the run. Supported values are
current-generation models.

**Recorded evals see this too.** A fixture's `models` map records the critic
alongside the pipeline and judge, and the replay staleness gate compares it —
so a recording made before the cutover grades stale in any environment that
sets `CRITIC_MODEL`, which is correct: it describes a pipeline that no longer
exists. CI runs keyless with the variable unset, so the offline suite is
unaffected. Note what the gate compares and what it does not: the pipeline's
model and the critic's — never the judge's, and since Phase 21.5 never the
classifier's either. A fixture's judge verdicts are fixed data replayed as
recorded grades, so moving the judge does not stale a single committed
recording. The classifier's entry is recorded for provenance and left
uncompared for a different reason: its default is non-neutral, so a comparison
would grade every pre-21.5 recording stale in CI rather than only where an
operator opted in (ADR-0013 records the measured nineteen-fixture cascade).

**The collision note, and when it fires.** A record run prints one line only
when the judge and the critic resolve to the *same* model — and since Phase 18
that is no longer what ships. `EVAL_JUDGE_MODEL` defaults to `claude-opus-4-8`
while production pins the critic to `claude-opus-5`, so a production-shaped
record run prints nothing here. Landing both on one model is something an
operator does by moving either knob. That is a legal configuration and the line
does not call it a mistake; it states what those verdicts stop being able to
claim — independence of the critic's model, since what one waves through the
other is likelier to wave through — and points at
[ADR-0012](adr/0012-judge-independent-of-the-critic.md), the record that
separated the two.

`EVAL_JUDGE_MODEL` overrides the model the eval judge runs on, defaulting to
`claude-opus-4-8`. It is read by `python -m evals` and by nothing the service
imports, so it belongs in the shell that runs a recording — not in the
configuration table above, not in `fly.toml`, and not in `.env.example`.

**Deployment:** this ships with the **next deploy** — no dedicated cutover, no
migration step to run by hand. At neutral defaults (both variables unset, and
responses reporting no billed geo) the deployed numbers are unchanged, so there
is nothing to sequence. The runs table gains three embedding columns on first
construction in both backends, idempotently and under the same advisory lock
`ensure_schema` already holds. Smoke it whenever the next deploy happens: one
demo run, then confirm `/metrics` shows a non-zero `cost.embedding_usd` and that
`/pricing` reports the windows and multipliers you expect.

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
