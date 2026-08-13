# Phase 11: Multi-machine state and pooled Postgres - Context

**Gathered:** 2026-08-05
**Status:** Ready for research
**Source:** Decisions taken directly with the user before planning

<domain>
## Phase Boundary

This phase moves all three stores off the per-machine volume and onto a shared Postgres,
replaces the single lock-guarded connection with a real pool, and runs the service on more
than one machine.

It is the first phase of milestone v1.1 that changes production infrastructure. Nothing about
caller identity, session ownership or note lifecycle belongs here — that is Phase 12.

</domain>

<decisions>
## Implementation Decisions

### Database: external Postgres (Neon or Supabase), not Fly Postgres

- **Locked:** the service points at an **external managed Postgres** via `DATABASE_URL`.
  Neon or Supabase — the researcher should recommend one on the evidence below, but the
  decision to go external is settled.
- **Why not Fly Postgres:** `fly postgres create` — the command this repo's own `fly.toml`
  runbook documents — is now the **unsupported** path. Fly's CLI prints: "Unmanaged Fly
  Postgres is not supported by Fly.io Support and users are responsible for operations,
  management, and disaster recovery." Its supported replacement is `fly mpg`.
- **Why external over `fly mpg`:** generous free tiers, pgvector available, and the database
  survives independently of Fly. The cost is cross-provider latency and a second vendor to
  explain in the README.
- **Hard requirement:** the chosen provider must support **pgvector**, because
  `VECTOR_STORE=pgvector` is one of the four `MemoryStore` backends and the phase moves the
  note store too.
- **Region matters:** the app runs in Fly `syd`. Pick the provider region closest to Sydney
  and record the measured latency, because every store probe on `/health` pays it.

### The two-pool problem — the phase's main technical risk

Neon and Supabase both front Postgres with **PgBouncer**. REQ-connection-pool adds an
*application-side* pool on top. These interact and must be designed together, not stacked:

- Transaction-mode pooling breaks server-side prepared statements and session-level state.
  `psycopg` 3 uses prepared statements automatically after a threshold — this is a real
  failure mode, not a theoretical one.
- The researcher must establish which endpoint to use (pooled vs direct), what
  `psycopg_pool` settings are correct behind PgBouncer, and whether `prepare_threshold`
  must be disabled.
- **`sslmode=require`** is mandatory for both providers; confirm how the existing connection
  code passes it.

### Data: start clean, keep the volume as a backup

- **Locked:** point at an empty Postgres and let new data accumulate. Do **not** run a
  migration.
- The volume `agent_data` is **kept, not destroyed**, as the backup. Detaching is reversible;
  destroying is not.
- What is knowingly given up: the cumulative `/metrics` history. It is the only genuinely
  irreplaceable thing on the volume — the two orphaned notes and the old demo sessions are
  disposable. Say this in the phase summary rather than letting it look like an oversight.
- `research_agent.migrate` is **not** exercised by this phase. That is a deliberate choice,
  not a gap; note it so a later phase does not assume the path is proven.

### Scale: two machines

- **Locked:** `fly scale count 2`. SC-2 and SC-3 require it, and "runs on more than one
  machine" must be demonstrable to a stranger, not merely asserted in tests.
- `min_machines_running` rises from 1; `auto_stop_machines = 'suspend'` stays, which bounds
  idle cost.
- The `[[mounts]]` block is removed **only after** `DATABASE_URL` is confirmed working —
  a machine with neither a volume nor a reachable database is a broken machine.

### Concurrency, and why the pool is justified

- REQ-connection-pool is a **mild reversal** of a sizing judgement: the single lock-guarded
  connection was called "right when a run occupies a worker for tens of seconds."
- `fly.toml` already sets `hard_limit = 16`, `soft_limit = 8`. With two machines that is up
  to 32 in-flight requests against one database. The pool is justified by the machine count
  rising, and the phase must state that link explicitly — pooling without a concurrency
  story is the reversal being unjustified.

### Claude's Discretion

- Neon vs Supabase, on the researcher's evidence.
- Pool min/max sizes and their env var names, provided they are configurable.
- Whether `PG_CONNECT_TIMEOUT` keeps its name in the pooled case.
- Test structure, following the repo's existing conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope
- `.planning/ROADMAP.md` § Phase 11 — six success criteria and the discuss-phase notes
- `.planning/REQUIREMENTS.md` — `REQ-multi-machine-state`, `REQ-connection-pool`

### The code being changed
- `src/research_agent/db.py` — the single lock-guarded connection being replaced
- `src/research_agent/sessions.py`, `metrics.py`, `memory.py` — the three stores
- `src/research_agent/migrate.py` — deliberately NOT exercised this phase
- `pyproject.toml` — `psycopg[binary]==3.3.4` is already pinned; `psycopg_pool` is not

### Deployment
- `fly.toml` — `[[mounts]]`, `min_machines_running`, the concurrency block, and the
  "Going stateless (Phase 8)" runbook comment at the foot, which documents the now-
  **unsupported** `fly postgres create` and must be corrected by this phase
- `docs/OPERATIONS.md` — deploys are manual; corrected in Phase 10
- `tests/test_deploy_config.py` — guards port, volume and machine-count invariants; must be
  updated to guard the new topology rather than the old one

### Conventions
- `.planning/codebase/CONVENTIONS.md`, `TESTING.md`, `ARCHITECTURE.md`
- No `conftest.py` — shared fakes live in the owning test module, resolved via
  `pythonpath = [".", "src", "tests"]`

</canonical_refs>

<specifics>
## Specific Ideas

- Deploys are **manual** (`fly deploy -a research-agent`) and `enforce_admins` is `false`, so
  a direct push to `main` bypasses the required checks. Plan the cutover as a deliberate
  sequence, and prefer a PR.
- Current live state: one machine `78156d2c32d738` in `syd`, release v4, volume `agent_data`
  at `/data`, `/health` passing.
- `SESSIONS_TOKEN` is a live Fly secret. `DEMO_TOKEN` must stay **unset** in production —
  see `docs/adr/0006-separate-sessions-token-fails-closed.md`.
- `primary_region` is pinned to the volume. Once the volume is detached that constraint
  relaxes, but changing region is out of scope here.
- Every store probe on `/health` is bounded by `PG_CONNECT_TIMEOUT` (3s), and the Fly health
  check allows 15s for three probes. Cross-provider latency eats into that budget — re-check
  the arithmetic rather than assuming it still holds.

</specifics>

<deferred>
## Deferred Ideas

- **Caller identity, session ownership, expiry, note lifecycle** — Phase 12.
- **Exercising `research_agent.migrate`** — deliberately skipped; a later phase that needs a
  real migration cannot assume this path is proven.
- **Changing `primary_region`** — possible once stateless, but not this phase.
- **The spend-cap race** (cap counts completed runs only, so ~16 concurrent runs can
  overshoot ~3×) — becomes *worse* at 32 concurrent requests across two machines. Not in
  scope here, but the phase should note the interaction rather than silently making it worse.

</deferred>

---

*Phase: 11-multi-machine-state-and-pooled-postgres*
*Context recorded: 2026-08-05 — user-approved before research*
