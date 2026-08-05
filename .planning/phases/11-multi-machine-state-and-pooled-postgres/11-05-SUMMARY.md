---
phase: 11-multi-machine-state-and-pooled-postgres
plan: 05
subsystem: deployment
tags: [fly, stateless, fail-closed, validation, scale-out, blocked]

# Dependency graph
requires:
  - phase: 11-03
    provides: "The two-armed deploy guards whose stateless arm this plan exercised for the first time"
  - phase: 11-04
    provides: "Production verified on Supabase Postgres (release v5/v6) -- the precondition for removing the mount"
provides:
  - "fly.toml declaring a stateless two-machine topology with the three Postgres backend pins"
  - "The fail-closed mechanism proved at runtime: absent DSN raises at store construction"
  - "11-VALIDATION.md reconciled -- real task IDs, real waves, runnable gates, amended skip count, labelled anti-pattern guards"
  - "The measured Fly->Supabase latency recorded in docs/OPERATIONS.md"
affects: [phase-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pin the backend rather than delete the path -- deletion does not prevent a fallback, pinning makes it fail closed"
    - "Assert on the parsed [env] table, never file text, when one key name is a substring of another"

key-files:
  created:
    - .planning/phases/11-multi-machine-state-and-pooled-postgres/11-05-SUMMARY.md
  modified:
    - fly.toml
    - docs/OPERATIONS.md
    - .planning/phases/11-multi-machine-state-and-pooled-postgres/11-VALIDATION.md

key-decisions:
  - "Stopped after three failed deploy attempts rather than reaching for `fly machine destroy`. That command is outside this plan's authorisation and it is the one step that could put the volume at risk; the plan's own constraint says to report rather than improvise if the scale-out fails."
  - "Did NOT mark SC-3 or SC-2's live half green in 11-VALIDATION.md, and withheld Approval. Every repository-side gate is green, but the phase's headline claim is unproven and a green tick would misrepresent that."
  - "Did NOT delete the `fly volumes destroy` prohibitions to satisfy the plan's grep-returns-0 criterion. Both occurrences are warnings, not instructions; deleting them to make a gate pass would remove the mitigation for T-11-20."
  - "Did NOT tick README's Phase 11 checklist line. The phase has not shipped."

requirements-completed: []

# Metrics
duration: 105min
completed: 2026-08-05
---

# Phase 11 Plan 05: Going stateless — Summary

**`fly.toml` now declares the stateless two-machine topology and the fail-closed backend pins, both
deploy guards ran their stateless arm for the first time and passed, and `11-VALIDATION.md` is
reconciled. But the phase's headline claim is NOT proven: `fly deploy` cannot complete the
mount-removal release non-interactively on flyctl v0.4.78, so production still runs ONE machine on
release v6 with the volume attached. SC-2's live half and SC-3 are blocked on an operator-run
deploy. Nothing was damaged — three failed attempts left production byte-identical and healthy.**

## Performance

- **Duration:** ~105 min (the bulk of it on the blocked deploy)
- **Tasks:** 4 planned — 2 complete (T1, T4), 2 blocked (T2, T3)
- **Commits:** 3
- **Files modified:** 3 (`fly.toml`, `docs/OPERATIONS.md`, `11-VALIDATION.md`)

## Task status

| Task | What | Status |
|---|---|---|
| 1 | Drop the mount, pin the backends, lift the ceiling | ✅ **Done** — `e88e99d` |
| 2 | Deploy, scale to two, confirm the volume survived | 🚫 **BLOCKED** — see § The blocker |
| 3 | Prove SC-3 across two machines, close the docs | 🚫 **BLOCKED** — depends on Task 2. Its one independent item (record the measured latency) was done |
| 4 | Reconcile `11-VALIDATION.md` | ✅ **Done** — `7bd2016` |

Commits:
- `e88e99d` — `feat(11-05): drop the mount, pin the backends, lift the machine ceiling`
- `7bd2016` — `docs(11-05): reconcile the validation map and record the measured latency`
- (final metadata commit for this summary and STATE.md)

---

## Task 1 — the four-part change, and why it is four parts

`fly.toml` went from a mounted single machine to a mountless pair:

| | Before | After |
|---|---|---|
| `[[mounts]]` | 1 block | **gone** |
| `SESSION_DB_PATH` / `METRICS_DB_PATH` / `VECTOR_STORE_PATH` | all three in `[env]` | **gone** |
| `SESSION_BACKEND` / `METRICS_BACKEND` / `VECTOR_STORE` | absent | **`postgres` / `postgres` / `pgvector`** |
| `min_machines_running` | 1 | **2** |
| `auto_stop_machines` / `primary_region` / concurrency | `suspend` / `syd` / 16-8 | **unchanged** |

The pins are the load-bearing half and the reason this is four parts rather than two. Deleting the
`*_DB_PATH` vars does **not** prevent the SQLite fallback the phase exists to end: `sessions.py:43`
defaults `SESSION_DB_PATH` to a file beside the module, and `default_backend()` returns `sqlite`
whenever `db.postgres_configured()` is false. Unpinned, two mountless machines would each boot on
their own container-local database, `/health` would report `dependencies: "ok"` (SQLite is
perfectly reachable), Fly's check would pass, and the only difference on the wire would be a
backend class name nothing reads.

**Fail-closed spot check** — the mechanism proved at runtime, not just declared:

```
$ env -u DATABASE_URL SESSION_BACKEND=postgres .venv/bin/python -c \
    "from research_agent.sessions import get_session_store; get_session_store()"
  File "src/research_agent/db.py", line 168, in database_url
    raise RuntimeError(
RuntimeError: DATABASE_URL is not set. Postgres-backed stores need it, e.g. postgresql://user:pass@host:5432/dbname
EXIT=1
```

Only an **absent** DSN fails closed. A reachability *outage* (DSN present, server down) still comes
up and reports the unreachable store in `/health`'s body, because `Database.__init__` does no I/O.
That distinction is written into `fly.toml` above the pins so it is not mistaken for
belt-and-braces.

### The guards took their second arm

This was the first live-fire test of 11-03's inversion. Both guards ran their stateless arm:

```
$ .venv/bin/pytest tests/test_deploy_config.py -v
12 passed in 0.82s
```

**0 failed and 0 skipped.** A skipping guard here is precisely the failure SC-5 exists to prevent —
before 11-03, deleting `[[mounts]]` would have turned both into no-ops with CI still green.

### Config gates

```
grep -v '^[[:space:]]*#' fly.toml | grep -c '\[\[mounts\]\]'                                   -> 0  (was 1)
grep -v '^[[:space:]]*#' fly.toml | grep -c 'SESSION_DB_PATH\|METRICS_DB_PATH\|VECTOR_STORE_PATH' -> 0  (was 3)
python3 ... tomllib assertion                                                   -> stateless topology confirmed
python3 ... suspend + syd assertion                                             -> unchanged bits intact
```

The comment filter matters: a bare `grep -c '\[\[mounts\]\]' fly.toml` counts the runbook footer's
prose. And the `tomllib` form is authoritative because `grep -c 'VECTOR_STORE' fly.toml` matches
`VECTOR_STORE_PATH` and cannot tell the two apart.

---

## The blocker

**`fly deploy` cannot complete this release non-interactively on flyctl v0.4.78.**

Removing `[[mounts]]` while a machine still holds the volume makes flyctl stop and ask:

```
Warning! machine 78156d2c32d738 [app] has a volume mounted but app config does not specify a volume.
This usually indicates a misconfiguration.
? Do you still want to continue and detach the volume? This will replace the machine. (y/N)
```

That is the *correct* prompt and the *intended* answer — detach, not destroy; the volume survives
and the machine is replaced. The problem is purely that it cannot be answered from a script.

Three attempts, each leaving production untouched:

| # | Approach | Result |
|---|---|---|
| 1 | `fly deploy -a research-agent --yes`, then `-y` | **Refused.** `Error: yes flag must be specified when not running interactively` — flyctl accepts the flag and then ignores it on this path, which calls `prompt.Confirm` directly. This is a flyctl bug, not a usage error |
| 2 | pty via `script`, stdin fed by `yes` | **flyctl panic.** The flood collided with survey's `ESC[6n` cursor-position handshake (the log shows the prompt receiving `78y` — the cursor report interleaved with the keystrokes), then `runtime error: invalid memory address or nil pointer dereference` at `internal/command/deploy/machines.go:321` |
| 3 | pty via `expect`, one deliberate `y\r` sent only when the prompt matched | **Hung.** The confirmation was accepted cleanly this time (`(y/N) y` in the log, no interleaving), and then flyctl produced no further output for the full 900 s timeout. No release was created |

After attempt 3 I stopped. That is the plan's own instruction — *"If the scale-out fails, the volume
and its SQLite data are intact — report rather than improvise"* — and the three-attempt limit.

### What I deliberately did not do

The obvious next move is to remove the machine so the deploy has nothing to replace: destroy
`78156d2c32d738` (which detaches the volume without destroying it), then deploy into an empty app.
**I did not do this.** `fly machine destroy` is not in this plan's authorisation, and it is the one
step in the neighbourhood that touches the volume's attachment — exactly the class of action the
plan reserved for the operator. Improvising a destroy to satisfy a checklist would invert the
priority the whole phase is built around.

### Production is unharmed

Verified after the third attempt:

```
$ fly releases -a research-agent | head -2
 v6      │ complete │ Release │ hessam.abbaszadi@gmail.com │ 1h3m ago

$ fly machines list -a research-agent
 78156d2c32d738 │ polished-hill-1870 │ started │ 1/1 │ syd │ ... │ vol_vdegz1021w669gx4

$ fly volumes list -a research-agent
 vol_vdegz1021w669gx4 │ created │ agent_data │ 1GB │ syd │ bd82 │ true │ 78156d2c32d738 │ 3 days ago

$ curl -s https://research-agent.fly.dev/health
status ok | machine 78156d2c32d738 | deps ok | sessions PostgresSessionStore
        | metrics PostgresMetricsStore | memory PgVectorMemoryStore
```

Still release v6, still one machine, volume still attached, all three Postgres backends healthy.
No release was created by any of the three attempts. **`fly volumes destroy` was never run.**

Endpoints, all 200:

```
/         HTTP 200  0.304604s
/health   HTTP 200  0.297830s
/demo     HTTP 200  0.301980s
/metrics  HTTP 200  0.298681s
```

`/demo` reports `token_required: False` — `DEMO_TOKEN` remains unset, per ADR-0006. Secrets:
`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `SESSIONS_TOKEN`, `DATABASE_URL` all `Deployed`;
**`DEMO_TOKEN` absent**, as required (T-11-22).

### What is still owed

1. Land the mount-removal deploy (operator, interactively — the prompt answers fine from a real
   terminal).
2. `fly scale count 2 -a research-agent`; confirm two `started` machines in `syd`, neither with a
   volume, and `agent_data` still listed as unattached.
3. `SELECT count(*) FROM pg_stat_activity` — expect ~21–26 of Nano's 60 (11-04 measured 15–16 at
   one machine; 2 × `max_size` 5 = 10 app connections).
4. Prove SC-3 over HTTP with both machine ids recorded.
5. Tick README's Phase 11 checklist line and flip `11-VALIDATION.md`'s two blocked rows and its
   Approval.

---

## SC-3 is NOT proven

**No machine ids are recorded in this summary, because only one machine exists.** There is no
session id proving cross-machine resolution.

This must not be papered over with the store-layer evidence from 11-04. That plan proved a session
round-trips against Supabase through `fly ssh console`, and said plainly that it was not an HTTP
proof. 11-02 proved the *mechanism* in CI —
`test_a_session_written_on_one_instance_resolves_on_a_cross_instance_read`. Neither can prove what
SC-3 actually claims: that the Fly proxy routes to two machines, that both hold the secret, that
neither holds a volume, and that a session created against one resolves from the other. That needs
two machines and it needs `fly-force-instance-id`. It is the phase's headline claim and it remains
outstanding.

---

## Task 4 — the validation map

`11-VALIDATION.md` had drifted four ways and is now reconciled. Details are in the commit message;
the substantive corrections:

- **Task IDs and waves filled.** Every row read `TBD` and the Wave column stopped at 4. Two kinds of
  row moved to wave 5: the `[[mounts]]` / `*_DB_PATH` config gates belong to **11-05-T1**, not wave
  3, because the topology is not touched until the database is proven; and SC-3 live is **11-05-T3**.
- **Two comment-blind config gates replaced.** Both counted prose — and 11-03 Task 2 had *added*
  runbook prose naming the very strings they grep for, so both would have gone green over an
  entirely unchanged topology.
- **The vacuous SC-6 gate replaced** with 11-03's three falsifiable parts. The original returned `1`
  on the untouched tree.
- **Three stale criteria rewritten** (lines 64, 65, 67 of the old file): the deleted
  `match="(?i)connect"` string-match, `/health`'s budget row split into cold-pool
  (`health_within_budget`) versus the general per-probe ceiling (`health_probe_deadline`), and the
  false claim that removing `*_DB_PATH` is what prevents the SQLite fallback.
- **Skip-count amendment recorded in the file**, not just in a plan body: 28 → **34**, the six new
  Postgres-gated tests named, with CI's `0 skipped` under `REQUIRE_POSTGRES=1` restated as the
  clause that actually guards coverage.
- **Anti-pattern guards split into their own labelled table.** They pass against the pre-phase tree,
  so a green there means nothing regressed rather than that work was done.
- **Wave 1's `search_path` rationale corrected** — see below.

### A gate in the plan that was itself wrong

The plan asserted `grep -c 'fly volumes destroy' fly.toml docs/OPERATIONS.md README.md` returns `0`
across all three, describing the string as "already absent from all three files today". It is not:

```
fly.toml:1
docs/OPERATIONS.md:1
README.md:0
```

Both occurrences are **prohibitions** written by 11-03 — *"`fly volumes destroy` is not part of this
procedure at any point"*. Satisfying the plan's `0` would have meant deleting the exact warning that
mitigates T-11-20. I left them and corrected the criterion instead: no occurrence is an instruction,
and the command was never run.

### Wave 1's `search_path` rationale, corrected

11-04 measured Supabase's default `search_path` and found it **already contains `extensions`**, so
`memory.py`'s unqualified `::vector` casts resolve without 11-01's `configure` callback. The
callback stays — explicit beats inheriting a provider default that Supabase can change without
telling us, and it is what makes the code portable to a provider whose default omits `extensions`.
But the honest framing is **insurance that has not yet been needed**, not a fix for an observed
break. Recorded in `11-VALIDATION.md` so nobody later reads 11-01's rationale as describing a real
failure.

---

## An edit to publicly reported numbers

**A row was deleted from the production `metrics` table, and it changed what `/metrics` advertises
to the public.** Recording it plainly, because it is an edit to reported numbers and should not look
incidental.

- **What:** the single run row from 11-04, `error_type: AuthenticationError`, cost `0`.
- **Who and why:** deleted by the operator, deliberately and with consent, on the grounds that it
  recorded a *credential outage* (`ANTHROPIC_API_KEY` was revoked) rather than a pipeline failure.
- **Effect on the public endpoint:** `/metrics` went from `{"total": 1, "completed": 0, "failed": 1,
  "failure_rate": 1.0}` to `{"total": 1, "completed": 1, "failed": 0, "failure_rate": 0.0}`. The
  advertised failure rate went from 100% to 0%.
- **The row that remains** is a genuine end-to-end research run on Postgres after the key was
  rotated: session `f14905b2fce8438eb716842c9a3b6c92`, approved, 3443-character answer, `$0.204266`
  — consistent with `/demo`'s current `spent_24h_usd: 0.2043`.

This is defensible — a revoked third-party credential is not a defect of the pipeline the metric
describes — but it is a judgement call, not a neutral cleanup, and a `failure_rate` of 0.0 now rests
on a table of one row from which one row was removed. Anyone citing that number should know its
denominator was edited. It also sits in tension with 11-04's own stated position
(*"Deleting real data to make a metrics table look tidy is the opposite of the point"*), which is
exactly why it belongs in the record rather than in a footnote.

`ANTHROPIC_API_KEY` has been **rotated** — digest `35d77d861c484d1a` → `9704aee92910b5e7` — so
11-04's blocking authentication gate is cleared.

## The cumulative `/metrics` history is gone

Stated plainly rather than left to be inferred: **this phase gave up the cumulative `/metrics`
history by starting clean.** CONTEXT locked that trade ("start clean, keep the volume as backup")
and named the history as the one genuinely irreplaceable thing surrendered. It is surrendered. The
pre-cutover SQLite tables (1 session, 3 runs, 3 notes) still sit on the unattached volume, but
nothing reads them and no code path merges them into the Postgres tables.

## `research_agent.migrate` is an unproven path

`src/research_agent/migrate.py` exists and **has never been run against this data, in production or
anywhere else.** No plan in this phase exercised it; the cutover started clean precisely so that it
would not have to. A later phase must not assume it works — treat it as unverified code until
someone runs it end to end against a real SQLite file and a real Postgres, and records the result.

---

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 — Blocking, NOT RESOLVED] `fly deploy` cannot answer its own volume-detach prompt**
- **Found during:** Task 2
- **Issue:** flyctl v0.4.78 ignores `-y`/`--yes` on the volume-detach confirmation.
- **Attempted:** `-y`; pty + `yes` flood (flyctl panic); pty + `expect` single keystroke (hung 900 s).
- **Outcome:** **unresolved after three attempts.** Stopped rather than escalating to
  `fly machine destroy`, which is outside authorisation. Production left untouched.
- **Files modified:** none

### Judgement calls where I did not follow the plan literally

**2. Did not delete the `fly volumes destroy` prohibitions** to satisfy a `grep`-returns-`0`
criterion that was factually wrong about the tree. Corrected the criterion instead. Deleting the
warning to make a gate green would have removed the mitigation for T-11-20.

**3. Did not mark SC-2's live half or SC-3 green, and withheld Approval** in `11-VALIDATION.md`,
despite Task 4's instruction to set `status: complete` and mark every row. `status: blocked` is
recorded instead. `nyquist_compliant: true` and `wave_0_complete: true` *were* set — those describe
gate coverage and wave-0 deliverables, both genuinely true.

**4. Did not tick README's Phase 11 checklist line** (Task 3, item 6). The phase has not shipped.
The other independent half of that item — recording the measured latency in `docs/OPERATIONS.md` —
was done.

**Total:** 1 unresolved blocker, 3 deliberate departures, all recorded above.

## Authentication gates

None encountered in this plan. 11-04's blocking gate (revoked `ANTHROPIC_API_KEY`) was cleared by
the operator between plans via a key rotation; a full research run has since completed on Postgres.

## Success criteria

| Criterion | Status |
|---|---|
| `[[mounts]]` gone, three `*_DB_PATH` gone, three pins present, `min_machines_running` ≥ 2 — via `tomllib` | ✅ |
| Missing `DATABASE_URL` raises at store construction | ✅ spot check exits 1 with `RuntimeError` naming `DATABASE_URL` |
| Both deploy guards run their stateless arm | ✅ 12 passed, **0 skipped** |
| `fly scale count 2`; `fly status` shows two started machines | ❌ **BLOCKED** — one machine, release v6 |
| SC-3 proved over HTTP with both machine ids recorded | ❌ **BLOCKED** — no second machine exists |
| `/`, `/health`, `/demo`, `/metrics` all 200; `/demo` `token_required: false` | ✅ |
| `SESSIONS_TOKEN` set, `DEMO_TOKEN` unset | ✅ |
| The volume still exists | ✅ `vol_vdegz1021w669gx4`, still attached (not yet detached, since the deploy did not land) |
| Measured latency recorded in `docs/OPERATIONS.md` | ✅ `p95` gate returns 1 |
| `11-VALIDATION.md` reconciled; search_path rationale corrected | ✅ |
| README reflects the shipped state | ⏸️ deliberately not ticked — nothing new shipped |
| Bare `.venv/bin/pytest` green; `ruff` clean | ✅ **436 passed, 34 skipped**; `All checks passed!` |

## Issues encountered

**flyctl v0.4.78 cannot script a volume-detaching deploy.** Worth an upstream issue: `-y` is
accepted and ignored on this path, and the pty fallback either panics
(`machines.go:321`, nil pointer) or hangs indefinitely after the confirmation is accepted. For this
repo it means the mount-removal deploy is an interactive, operator-run step — which is worth
writing into `docs/OPERATIONS.md` once the deploy has actually landed and the behaviour is
confirmed from a real terminal.

**`/health` still cannot see a revoked model credential.** Carried from 11-04, unchanged:
`credentials.anthropic` checks presence, not validity. Phase 12 material.

## Known stubs

None introduced by this plan.

## Next phase readiness

**Not ready.** Phase 11 cannot be verified until the deploy lands and SC-3 is proven. The
repository is in the correct end state and every repository-side gate is green — the outstanding
work is entirely operational, and it is listed under § What is still owed.

## Self-Check: PASSED

- `.planning/phases/11-multi-machine-state-and-pooled-postgres/11-05-SUMMARY.md` — created (this file)
- `.planning/phases/11-multi-machine-state-and-pooled-postgres/11-VALIDATION.md` — modified, gates verified (`TBD` 0, `⬜ pending` 1)
- `fly.toml` — modified, `tomllib` assertion passes
- `docs/OPERATIONS.md` — modified, `p95` gate returns 1
- Commit `e88e99d` exists — `git log`
- Commit `7bd2016` exists — `git log`
- Every command output, JSON body and count quoted above is literal output captured this session
- **Claims deliberately NOT made:** no machine ids, no SC-3 proof, no two-machine fleet, no
  detached volume, no `status: complete`

---
*Phase: 11-multi-machine-state-and-pooled-postgres*
*Completed: 2026-08-05 — partial, blocked at Task 2*
