# Phase 20: Note count bound - Research

**Researched:** 2026-08-14
**Domain:** Per-owner bounded storage across four hand-written backend dialects (in-memory list, JSON file, Chroma, pgvector)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**The cap is an env knob, default 100 — user-ratified today**
- `NOTE_CAP_PER_OWNER` (exact name at planner's discretion, following the codebase's
  env-knob naming conventions), **default 100**, read per call like every other knob in
  this codebase (the `session_ttl_seconds()` convention — monkeypatch-able in tests,
  never cached in a module constant).
- Rationale accepted with the choice: a research run writes a handful of notes; 100 is
  weeks of heavy use for one identity, and the 7-day TTL already prunes. The knob exists
  so the operator can tighten it for the free-tier database without a deploy.
- Floor/validation semantics (what does 0 mean? negative? — probably "invalid reads as
  default" per the `session_ttl_seconds` fallback style) are the researcher's question.

**Oldest-first eviction, at write time**
- Eviction is FIFO by `created_at` within one owner: adding note N+1 past the cap evicts
  the oldest. Every backend already carries `owner` and `created_at` (Phase 12), which is
  exactly why this bound is implementable where semantic dedup is not.
- Eviction happens on `add()` — the same place the TTL sweep already runs — so no
  scheduler is needed and the bound holds as an invariant after every write, not
  eventually.
- Owner matching is EXACT, per the Phase 12 convention: `owner=""` (legacy rows) is its
  own bucket, never a wildcard. Eviction must never cross owners.

**Byte-identical across four backends, proven not asserted**
- The claim being defended (the README bullet's own words): identical behaviour across
  json, memory, chroma, and pgvector. The 4-arm contract suite is where that's proven —
  same inputs, same eviction outcome, all four arms.
- Tie-breaking when `created_at` collides must be DEFINED and identical (the researcher
  should check what orderings each backend can actually guarantee — this is exactly where
  byte-identical claims die).

### Claude's Discretion
- Where the eviction lives per backend (a shared helper vs per-store implementations —
  whatever keeps the four honest; the contract suite is the referee either way).
- Whether eviction of expired-but-unswept rows counts against the cap before or after the
  TTL sweep (define the order: sweep first, then count — probably — but verify it's
  identical everywhere).
- Whether `add()` returns anything about eviction (probably not — no caller needs it —
  but if a trace entry is cheap and honest, planner's call).

### Deferred Ideas (OUT OF SCOPE)
- Semantic dedup / summarisation — permanently out (recorded in REQUIREMENTS Out of Scope).
- README Limitations rewrite — Phase 22.
- The record run — Phase 21.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-note-count-bound | Notes carry a per-owner count bound with oldest-first eviction, with byte-identical semantics across json, memory, chroma, and pgvector, proven by the shared 4-arm contract suite. Notes are then bounded by expiry *and* count, which kills the README bullet rather than narrowing it. | Findings 1–7 below give per-backend eviction mechanics, the tie-break design, the sweep-then-evict composition, the env-knob convention, the contract-suite arithmetic, and the blast-radius audit that shows no existing caller of `add()` writes more than 12 notes at once. |
</phase_requirements>

## Summary

`memory.py`'s `MemoryStore.add()` already has one physical bound (the TTL sweep, Phase 12)
running identically — by convention, not by shared code — across four backends:
`_BruteForceStore` (json/memory, a Python list), `ChromaMemoryStore` (metadata + ANN
index), and `PgVectorMemoryStore` (Postgres). This phase adds a second, independent bound
in the same place: after the sweep, after the write, if the **owner's** live note count
exceeds `NOTE_CAP_PER_OWNER` (default 100), delete the oldest until it doesn't.

The mechanics are backend-specific but the shape is identical everywhere: **sweep (TTL,
unconditional) → insert the new note → evict-if-over-cap (owner-scoped, oldest-first)**.
That ordering is not incidental — it is the only ordering that keeps the *existing*,
already-tested guarantee that `add()` physically removes expired rows even when the owner
is nowhere near the cap (`test_note_ttl`'s `len()` assertion). Folding the sweep into the
cap check would silently stop sweeping owners who never hit 100 notes.

The tie-break question is where this research spent most of its effort, because it is
empirically, not theoretically, dangerous: `time.time()` on this machine produced only 14
unique values across 200 rapid calls [VERIFIED: measured this session], so any contract
test that adds >100 notes in a tight loop (exactly the eviction test the plan needs) will
produce `created_at` collisions on every backend. Two of the four backends already carry a
collision-proof secondary key for free — the Python list's insertion order (json/memory)
and Postgres's `BIGSERIAL id` (pgvector). Chroma does not; it needs one added deliberately,
because `collection.get()`'s return order is not a documented API contract even though it
was observed to preserve insertion order across 1.4.1 in this session's testing.

Every existing caller of `add()` was audited. There is exactly **one** production call site
(`graph.py:368`, `researcher_node`, one note per pass). `migrate.py`'s three write paths
(`migrate_notes`, `copy_embeddings`, `reembed_notes`) and `recall_golden.py`'s `seed()`
**all bypass `store.add()` by design already**, writing through raw `INSERT`/`db.execute`
calls for reasons predating this phase (deterministic `created_at`, no TTL-sweep
side-effect on a migration). This means the cap introduces **zero** risk of silently
evicting rows during a migration or eval-fixture seed — a risk this research set out to
rule in or out, and ruled out by reading the code, not by assuming the good outcome.

**Primary recommendation:** implement a `note_cap_per_owner()` reader in `memory.py`
mirroring `note_ttl_seconds()`'s per-call, monkeypatch-friendly shape, but clamp invalid
*and* non-positive input to the default (the `cost_discount_factor()` pattern, not the
`session_ttl_seconds()` floor-at-zero pattern) — because unlike a TTL, `NOTE_CAP_PER_OWNER=0`
read literally makes every `add()` evict the note it just wrote, which is a silent,
confusing way to disable memory recall rather than a legitimate configuration. Implement
eviction as a small per-backend addition inside `add()` (not a shared helper — the four
backends' storage shapes are different enough that a shared helper would just be an
`if/elif` over backend type), landing in the same lock/transaction scope the sweep already
uses. Prove it with 3–4 new contract-suite cases per note-related behaviour, each running
identically on all four `notes` fixture arms.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-owner count enforcement (eviction) | Database / Storage | — | Lives entirely inside `MemoryStore.add()`, the storage seam; the graph (API/Backend tier) never learns eviction happened — it only ever calls `store.add()` and moves on, exactly as it does for the TTL sweep today |
| Env-knob resolution (`NOTE_CAP_PER_OWNER`) | API / Backend | Database / Storage | The knob is read by application code (`memory.py`, imported by the service process) but its *effect* is a storage-layer invariant, same split as `NOTE_TTL_DAYS` today |
| Cross-backend behavioural parity | Database / Storage | — | Enforced by `tests/test_store_contract.py`'s shared `notes` fixture, not by any runtime code — there is no tier that verifies parity at request time, only the test suite |

## Standard Stack

No new external dependency. This phase extends existing code in `src/research_agent/memory.py`
using only the standard library (`os`, `time`) and each backend's already-imported client
(`psycopg` via `db.Database`, `chromadb`). `chromadb==1.4.1` is already pinned
[VERIFIED: pyproject.toml:45] and is the version this research's empirical Chroma findings
were measured against.

### Installation
No install step. This phase adds no line to `pyproject.toml`.

## Package Legitimacy Audit

N/A — this phase installs no new packages. No audit table is produced.

## Architecture Patterns

### System Architecture Diagram

```
researcher_node (graph.py:368)
        │
        │  store.add(text, owner=state["owner"])
        ▼
MemoryStore.add()  ── the one seam every backend implements ──
        │
        ├─► [1] TTL SWEEP (existing, Phase 12, unconditional)
        │       remove every row for ANY owner past NOTE_TTL_DAYS
        │
        ├─► [2] INSERT the new note (owner, text, embedding, created_at)
        │
        └─► [3] CAP EVICT (new, this phase — owner-scoped)
                count THIS owner's live notes
                if count > NOTE_CAP_PER_OWNER:
                    delete (count - cap) oldest, THIS owner only
                        tie-break: insertion order (list index / BIGSERIAL id /
                        explicit seq — never created_at alone)

Four implementations of [1]→[2]→[3], one per backend, verified identical by
tests/test_store_contract.py's `notes` fixture (json, memory, chroma, pgvector).
No new caller reaches this path: migrate.py and recall_golden.py write via raw
SQL, bypassing add() (and therefore the cap) entirely, by pre-existing design.
```

### Recommended Project Structure
No new files. All changes land in:
```
src/research_agent/memory.py       # note_cap_per_owner(), per-backend eviction
tests/test_store_contract.py        # new cases in the `notes` fixture section
docs/OPERATIONS.md                  # new row in the Configuration table
```

### Pattern 1: The env-knob reader (`note_cap_per_owner()`)
**What:** A per-call, unparsed-value-falls-back-to-default reader, matching the shape of
every other knob in this codebase, but with the `cost_discount_factor()` clamp direction
(≤0 or unparseable → default) rather than the `note_ttl_seconds()` floor-at-zero direction.

**When to use:** Called once per `add()`, never cached.

**Why this clamp and not the TTL one** [CITED: src/research_agent/usage.py:236-251,
verbatim quote below] — `note_ttl_seconds()`'s `max(days, 0.0)` treats `0` as a real,
meaningful value (immediate expiry — deliberately used by `test_note_ttl`,
`monkeypatch.setenv("NOTE_TTL_DAYS", "0")`, to force a note past the cutoff without
sleeping seven days). A note-count cap has no equivalent meaningful zero: a store that
evicts the note it just wrote on every call is not "a cap of zero," it is memory recall
silently disabled, with no error and no log line. `usage.py`'s `cost_discount_factor()`
faces the identical shape of foot-gun for the identical reason:

```python
# Source: src/research_agent/usage.py:236-251 (read this session)
def cost_discount_factor() -> float:
    """Negotiated discount applied to computed cost. Default 1.0 (list price).

    Zero or negative falls back to neutral instead of being honoured. This is
    not tidiness: the budget guardrails read the number this factor scales, so
    `COST_DISCOUNT_FACTOR=0` -- a plausible typo, and a plausible reading of
    "disable the discount" -- would cost every run at $0.00, and a per-run cap
    compared against $0.00 never fires. That is DEC-12's fail-open scenario
    arriving through a new door, so a misconfiguration fails toward reporting
    *more* cost, never less.
    """
    try:
        factor = float(os.environ.get("COST_DISCOUNT_FACTOR", "1.0"))
    except ValueError:
        return DEFAULT_COST_DISCOUNT_FACTOR
    return factor if factor > 0 else DEFAULT_COST_DISCOUNT_FACTOR
```

**Recommended implementation** (mirrors the quoted shape, `int` in place of `float`):

```python
# memory.py, alongside NOTE_TTL_DAYS_DEFAULT
NOTE_CAP_PER_OWNER_DEFAULT = 100


def note_cap_per_owner() -> int:
    """How many live notes one owner may hold before the oldest is evicted.

    Read per call, the note_ttl_seconds() convention. Unparseable OR <= 0
    falls back to the default rather than being honoured -- the
    cost_discount_factor() clamp, not the TTL floor-at-zero clamp: a literal
    "cap of zero" would make add() evict the note it just wrote on every
    call, which is memory recall silently disabled rather than a legitimate
    operator choice. An operator who wants no cap does not set this variable.
    """
    raw = os.environ.get("NOTE_CAP_PER_OWNER", "").strip()
    try:
        cap = int(raw) if raw else NOTE_CAP_PER_OWNER_DEFAULT
    except ValueError:
        return NOTE_CAP_PER_OWNER_DEFAULT
    return cap if cap > 0 else NOTE_CAP_PER_OWNER_DEFAULT
```

### Pattern 2: `_BruteForceStore` (json, memory) eviction — no new field needed
**What:** `self.entries` is a Python list, mutated only by the sweep's list-comprehension
filter and by `.append()` [VERIFIED: src/research_agent/memory.py:260-276, read this
session — the `add()` body is `self.entries = [e for e in self.entries if ...]` followed
by `self.entries.append({...})`, both under `self._lock`]. This means **list index order
already equals insertion order** for any one owner's notes — no timestamp comparison is
needed to break a `created_at` tie; the tie is already broken by construction.

**When to use:** Both `InMemoryStore` and `JSONMemoryStore` share this via `_BruteForceStore`.

**Example (inside the existing locked block, after `.append()`, before `_persist()`):**
```python
# Source: pattern derived from memory.py:260-276 (read this session)
def add(self, text: str, owner: str = "") -> None:
    embedding = self.embedder.embed_documents([text])[0]
    now = time.time()
    cutoff = now - note_ttl_seconds()
    with self._lock:
        self.entries = [e for e in self.entries if e.get("created_at", 0.0) > cutoff]
        self.entries.append(
            {"text": text, "embedding": list(embedding), "owner": owner, "created_at": now}
        )
        # NEW: cap eviction. owner_idx is already insertion-ordered because
        # self.entries only ever grows by append() -- no sort, no timestamp
        # comparison, needed to find "oldest": it's whatever comes first.
        cap = note_cap_per_owner()
        owner_idx = [i for i, e in enumerate(self.entries) if e.get("owner", "") == owner]
        if len(owner_idx) > cap:
            drop = set(owner_idx[: len(owner_idx) - cap])
            self.entries = [e for i, e in enumerate(self.entries) if i not in drop]
        self._persist()
```

### Pattern 3: `ChromaMemoryStore` eviction — needs an explicit tie-break field
**What:** Chroma has no column analogous to a list index or `BIGSERIAL`. `ids` are
`uuid4().hex` [VERIFIED: src/research_agent/memory.py:412, read this session — the
comment there explains *why* ids stopped being `count()`-derived: "count() is no longer
monotonic" once the sweep can shrink the collection] — not sortable by insertion order.
`created_at` in metadata is a `time.time()` float, subject to the same collision risk
measured below.

**Empirical finding** [VERIFIED: measured this session against the pinned `chromadb==1.4.1`,
`PersistentClient`]: `collection.get(include=["metadatas"])` returned items in exact
insertion order in two separate local tests — one with 10 sequential adds, one with 5
adds → 1 delete (simulating a TTL sweep) → 2 more adds, where the surviving 6 items still
came back in original insertion order. This is **not a documented Chroma API guarantee**
(no ordering promise appears in Chroma's `get()` reference), so treat it as an
implementation detail of 1.4.1 that could change on a version bump, not a contract to
build the "byte-identical" claim on.

**Recommendation:** add an explicit monotonic `seq` integer to each note's metadata,
computed from the survivors already fetched by the existing `_sweep()` call — no extra
round trip, and it does not depend on `get()`'s return order (only on scanning all
returned metadata for a max, which requires completeness, not ordering):

```python
# Source: pattern derived from memory.py:382-416 (read this session)
def _sweep(self, cutoff: float) -> tuple[list[dict], int]:
    """Delete expired notes; return survivors' metadata and the next seq value."""
    got = self._collection.get(include=["metadatas"])
    ids = got.get("ids") or []
    metadatas = got.get("metadatas") or []
    stale = [nid for nid, m in zip(ids, metadatas, strict=True)
             if float((m or {}).get("created_at", 0.0)) <= cutoff]
    if stale:
        self._collection.delete(ids=stale)
    survivors = [m for nid, m in zip(ids, metadatas, strict=True) if nid not in set(stale)]
    next_seq = max((int((m or {}).get("seq", 0)) for m in survivors), default=0) + 1
    return survivors, next_seq

def add(self, text: str, owner: str = "") -> None:
    embedding = self.embedder.embed_documents([text])[0]
    now = time.time()
    survivors, next_seq = self._sweep(now - note_ttl_seconds())
    self._collection.add(
        ids=[uuid.uuid4().hex],
        documents=[text],
        embeddings=[list(embedding)],
        metadatas=[{"owner": owner, "created_at": now, "seq": next_seq}],
    )
    # NEW: cap eviction, owner-scoped, tie-broken by seq (not created_at).
    cap = note_cap_per_owner()
    owned = [m for m in survivors if (m or {}).get("owner", "") == owner]
    owned.append({"owner": owner, "seq": next_seq})  # the note just written
    if len(owned) > cap:
        owned.sort(key=lambda m: int(m.get("seq", 0)))
        excess = len(owned) - cap
        # Re-fetch ids for the notes being dropped -- `survivors`/`owned` here
        # carry metadata only; the real implementation must keep the id
        # alongside each metadata dict from the _sweep() fetch to delete by id.
```
*(The exact re-fetch-ids-alongside-metadata plumbing is an implementation detail for the
planner to spell out as a task — the important verified facts are: `seq` must be explicit,
`_sweep()`'s existing `get()` call is the right place to compute it, and `get()`'s order
must not be load-bearing for correctness.)*

### Pattern 4: `PgVectorMemoryStore` eviction — `BIGSERIAL id` is the tie-break
**What:** `id BIGSERIAL PRIMARY KEY` [VERIFIED: src/research_agent/memory.py:506, read
this session — `CREATE TABLE IF NOT EXISTS {self.table} (id BIGSERIAL PRIMARY KEY, ...)`]
is allocated by Postgres at insert time, strictly increasing regardless of clock
resolution or concurrent writers (Postgres sequence allocation is atomic). This is exactly
the tie-break json/memory get for free from list order.

**Postgres syntax note, verified against this session's reading of the file**: `DELETE ...
ORDER BY ... LIMIT` is **not valid Postgres syntax** (that is a MySQL extension); Postgres
requires the ordering/limiting to happen in a subquery, matched back via a key column —
the same shape the file already uses for the TTL sweep's simpler unordered `DELETE FROM
{table} WHERE created_at <= ...` [VERIFIED: src/research_agent/memory.py:560-563].

**Recommended SQL**, run after the `INSERT`, inside the same parameterized-value style the
file already uses (table name pre-validated by `validate_table_name`, values bound):
```python
# Source: pattern derived from memory.py:552-567 (read this session)
def add(self, text: str, owner: str = "") -> None:
    embedding = self.embedder.embed_documents([text])[0]
    self._check_dimensions(embedding)
    self.db.execute(
        f"DELETE FROM {self.table} WHERE created_at <= now() - (%s * interval '1 second')",
        (note_ttl_seconds(),),
    )
    self.db.execute(
        f"INSERT INTO {self.table} (text, embedding, owner) VALUES (%s, %s::vector, %s)",
        (text, self._literal(embedding), owner),
    )
    # NEW: cap eviction, owner-scoped. OFFSET on the newest-first subquery
    # keeps everything past the newest `cap` rows -- i.e. exactly the excess
    # oldest rows -- and deletes them by id, since Postgres cannot ORDER BY /
    # LIMIT / OFFSET directly on a DELETE target.
    self.db.execute(
        f"""
        DELETE FROM {self.table}
        WHERE id IN (
            SELECT id FROM {self.table}
            WHERE owner = %s
            ORDER BY created_at DESC, id DESC
            OFFSET %s
        )
        """,
        (owner, note_cap_per_owner()),
    )
```
No new RLS surface: this is a `DELETE` against the existing `{self.table}`, already under
`ENABLE ROW LEVEL SECURITY` with no policy from Phase 17.5 [VERIFIED:
src/research_agent/memory.py:528, read this session]. No new table, no new DDL, so no new
policy question.

**Concurrency note (accepted, not new):** all three statements (sweep, insert, evict) are
separate autocommitted statements [VERIFIED: src/research_agent/db.py:224-227, `autocommit:
True` in `_connect_kwargs`, read this session] — there is no transaction wrapping them.
This is the *same* non-atomicity the existing TTL sweep already has relative to the
`INSERT` (Phase 12 shipped it this way). Two concurrent `add()` calls for the same owner
racing the eviction step could, in the worst case, leave the owner one note over or under
cap transiently — an accepted class of race already present in this file, not a new one
this phase introduces. Note this in the plan rather than attempting to fix it; fixing it
would mean wrapping every backend's TTL sweep in a transaction too, which is out of scope.

### Anti-Patterns to Avoid
- **Sorting by `created_at` as the sole/first key when `created_at` can collide.** Measured
  this session: 200 rapid `time.time()` calls on this machine produced only 14 distinct
  values, and `time.time_ns()` fared barely better (22 of 300). A contract test that adds
  >100 notes in a loop (the natural way to test eviction) will produce real collisions,
  not a hypothetical edge case. Every backend must have a tie-break that does **not**
  depend on wall-clock resolution.
- **Merging the cap check into the sweep, or skipping the sweep when under cap.** The TTL
  sweep must remain unconditional. If cap-eviction became the *only* removal mechanism, an
  owner who never exceeds 100 notes would accumulate expired-but-unswept rows forever,
  regressing the existing `test_note_ttl` guarantee (`len()` must shrink on the next
  `add()` regardless of the cap). See Common Pitfalls below for the concrete scenario.
- **A shared cross-backend eviction helper function.** The four backends' storage shapes
  (Python list / Python list / Chroma metadata+ids / SQL rows) are different enough that a
  shared helper would just be an `if backend_type == ...` dispatcher with no real code
  reuse — matching CONTEXT's own framing ("whatever keeps the four honest; the contract
  suite is the referee either way"). Per-backend implementations, one shared behavioural
  test suite, is the existing shape of this file (TTL sweep, owner scoping) and should stay
  the shape for the cap too.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Monotonic ordering under clock collisions | A custom high-resolution timestamp scheme (`time.time_ns()`, a global counter) | The storage-native sequence each backend already has or can cheaply add (list index, `BIGSERIAL id`, an explicit `seq` field derived from a completeness scan) | Measured this session: neither `time.time()` nor `time.time_ns()` is collision-free under a tight loop on this machine; `perf_counter_ns()` is monotonic but not wall-clock-comparable or restart-safe, so it cannot double as `created_at` |
| Cross-backend abstraction for eviction | A shared "evict oldest" utility function parameterized over backend internals | Per-backend code inside each `add()`, proven equivalent by the shared contract suite | The four backends' native "what is oldest" representations are incompatible types (list index vs SQL row vs Chroma metadata) — an abstraction would either leak backend details back out or become dead weight |

**Key insight:** this problem has no shared implementation to hand-roll or avoid
hand-rolling — the entire point of the 4-arm contract suite (already the pattern for TTL
and owner-scoping) is that four independently-written implementations are proven
behaviourally identical by tests, not by a shared code path.

## Common Pitfalls

### Pitfall 1: `created_at` ties are not a hypothetical — they're the default outcome of the obvious test
**What goes wrong:** A contract test that adds 101 notes in a `for` loop to trigger
eviction, then asserts "the oldest note is gone," can pass or fail nondeterministically
(or silently evict the wrong note) if the eviction logic sorts by `created_at` alone.
**Why it happens:** Measured this session: `time.time()` called 200 times in a tight
Python loop on this machine returned only 14 unique values (186 of 199 consecutive diffs
were exactly `0.0`). This is a property of the OS clock's coarse update granularity, not
of Python's float precision — `time.time_ns()` (nanosecond int) fared only marginally
better (22 of 300 unique).
**How to avoid:** Never treat `created_at` as a unique key. json/memory get a free,
exact tie-break from list order; pgvector gets one from `id`; Chroma needs an explicit
`seq` field (Pattern 3 above).
**Warning signs:** A contract test for eviction that passes when run alone but flakes
under `pytest -n auto` or when notes are seeded faster (e.g., a faster machine, a warmer
disk cache) is this pitfall arriving late.

### Pitfall 2: Folding the sweep into the cap check silently un-sweeps low-volume owners
**What goes wrong:** If the sweep is only performed as a side-effect of cap-eviction (e.g.
"count all rows including expired ones, evict oldest until at cap, and expired rows happen
to be oldest so they get removed too") then an owner who is nowhere near the cap (the
common case — CONTEXT itself notes "the live database currently holds 8 notes across 7
sessions") never triggers eviction, so expired rows for that owner are **never physically
removed**, regressing the Phase 12 guarantee tested by `test_note_ttl`'s `len()`
assertion ("add() did not sweep the expired note").
**Why it happens:** It's tempting because, for a *single* owner, "expired" rows are always
a prefix of "oldest" rows (uniform TTL), so at cap-triggering volumes the two orderings
produce the same surviving set — the bug only shows up below the cap, which is exactly
where it's least likely to be tested.
**How to avoid:** Keep the sweep unconditional and first; run the cap check as a
completely separate step afterward, counting only post-sweep survivors.
**Warning signs:** A contract test with the exact composition CONTEXT names — "an expired
row + a full cap + one add(): what survives?" — is the right shape to pin this. Concretely:
seed `cap - 1` live notes plus 1 expired note for one owner (so the owner has `cap` rows on
disk, one of them stale), then `add()` once. Correct result: sweep removes the 1 expired
row, insert brings the owner to exactly `cap` (no eviction fires), and `len()` (or an
unfiltered per-owner count) shows the expired row is gone — proving the sweep ran
independently of whether the cap check ever fired.

### Pitfall 3: Trusting Chroma's `get()` order as if it were documented
**What goes wrong:** Relying on `collection.get()` returning items in insertion order
(observed empirically this session, twice, including across a delete+re-add cycle) without
an explicit tie-break field. A chromadb version bump could silently reorder `get()`'s
results (e.g. if it switches to returning by internal segment/shard order at scale), and
the eviction logic would then evict a wrong-but-plausible note with no error.
**Why it happens:** It's the path of least code — no new metadata field, no extra write.
**How to avoid:** Add the explicit `seq` field (Pattern 3). It costs nothing extra: the
`get()` call it's derived from already runs, for the TTL sweep, on every `add()`.
**Warning signs:** None visible from the outside — this is the kind of gap that stays
invisible until a chromadb upgrade. Worth one dedicated unit test asserting `seq` values
are strictly increasing per owner regardless of `get()`'s returned order (constructible by
stubbing `_collection.get` to return metadata in reverse or shuffled order and asserting
eviction still removes the right note).

### Pitfall 4: `DELETE ... ORDER BY ... LIMIT` against Postgres
**What goes wrong:** Writing the pgvector eviction as `DELETE FROM t WHERE owner = %s
ORDER BY created_at ASC LIMIT %s` — valid MySQL, a syntax error in Postgres.
**Why it happens:** It's the natural first draft when translating "delete the oldest N."
**How to avoid:** Subquery form (Pattern 4): `DELETE ... WHERE id IN (SELECT id ... ORDER
BY ... OFFSET ...)`.
**Warning signs:** Immediate — this fails at `execute()` time with a syntax error, not a
silent bug, so it will not survive past the first test run against a real Postgres
instance. The risk is writing it against SQLite semantics (which does support `ORDER BY
... LIMIT` on `DELETE`) if a developer tests the shape mentally against SQLite muscle
memory from `sessions.py`/`metrics.py` before running it against Postgres.

## Code Examples

See Patterns 1–4 above (Architecture Patterns section) — each pattern includes a complete,
directly-adaptable code example sourced from the exact lines of `memory.py` and `usage.py`
read this session.

## Runtime State Inventory

N/A — this is not a rename, refactor, or migration phase. No string, key, or identifier is
being renamed; a new bound is being added to an existing seam. Omitted per the researcher
protocol's own trigger condition.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `NOTE_CAP_PER_OWNER` is the right exact env var name | Pattern 1 | Low — CONTEXT itself names this as the illustrative name and leaves the exact string to planner's discretion; changing it before shipping costs nothing since nothing depends on it yet |
| A2 | The `≤0 or unparseable → default` clamp (matching `cost_discount_factor()`) is the right choice over the `session_ttl_seconds()` floor-at-zero clamp | Pattern 1 | Medium — this is a design recommendation grounded in a real in-repo precedent and a stated rationale (0 is a silent recall-disabling foot-gun, not a meaningful state), but it is this research's synthesis, not something the codebase has done before for a *count* knob. If the planner or a later reviewer prefers "0 disables the cap" (matching `DEMO_RATE_LIMIT_PER_HOUR`'s "0 disables" convention instead), that is a legitimate alternative reading worth a one-line decision in the plan, not a re-research |
| A3 | Chroma's `collection.get()` preserving insertion order is 1.4.1-specific behaviour, not a documented guarantee | Pattern 3 | Low if the `seq` field is implemented as recommended (order becomes irrelevant); High if a future implementer skips `seq` and trusts `get()` order directly — this assumption is exactly why Pattern 3 recommends the explicit field rather than relying on the observed behaviour |

## Open Questions

1. **Does `add()` need a per-owner introspection method for testing, beyond `query()`?**
   - What we know: the contract suite can already assert per-owner counts via
     `query(text, top_k=<large>, min_similarity=0.0, owner=...)`, since `query()` is
     already owner-scoped and TTL-filtered [VERIFIED: memory.py:211-219, the abstract
     method signature, read this session].
   - What's unclear: whether `FakeEmbedder`'s vocabulary-collision behavior (many
     evenly-worded notes embed identically, see below) makes similarity-ranked `query()`
     awkward for an eviction test that wants to assert *which* notes survive by exact
     text/content rather than by score.
   - Recommendation: identify notes by unique substrings drawn from `FakeEmbedder.VOCAB`
     combined with a numeric suffix in the note text itself (e.g. `"langgraph note 037"`),
     and assert on the returned text list's *membership*, not its order — `query()`'s
     ordering among score-tied notes is backend-defined and not part of this phase's
     byte-identical claim (only *which set of notes survives eviction* is).
2. **Should `evals/harness.py:300`'s `store.add(note, owner="")` (seeded notes) ever be
   audited again if a case's `seeded_notes` list grows past 100?**
   - What we know: today's usage is small (a handful of notes per case)
     [VERIFIED: evals/harness.py:270-300, read this session — a fresh store per case, no
     shared accumulation].
   - What's unclear: nothing structurally risky today; flagged only so a future dataset
     author doesn't add a 150-note stress-test case and get silently truncated to 100.
   - Recommendation: no action this phase; worth one sentence in the contract test's
     docstring or in `OPERATIONS.md` noting the cap applies to seeded notes too if anyone
     builds a large-corpus eval case later.

## Environment Availability

N/A — no new external dependency. `chromadb==1.4.1` is already installed and pinned
[VERIFIED: pyproject.toml:45, read this session]; Postgres availability for the pgvector
arm is exactly as before (`DATABASE_URL`-gated, `HAS_POSTGRES = db.postgres_configured()`
[VERIFIED: tests/test_store_contract.py:44, read this session]).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest, already configured |
| Config file | `pyproject.toml` (existing `[tool.pytest...]` section, unmodified by this phase) |
| Quick run command | `pytest tests/test_store_contract.py -k "note" -q` |
| Full suite command | `pytest tests/ -q` |

**Baseline measured this session** (keyless, `DATABASE_URL` unset locally): `771 passed,
67 skipped, 1 failed` in `pytest tests/ -q` — the one failure
(`test_service.py::test_health_credential_valid_true_after_the_probe_lands`) is a
pre-existing environmental artifact of this dev machine having a real `VOYAGE_API_KEY` set
(unrelated to Phase 20's scope; Phase 19's credential-probe test infers `voyage: True`
from actual env state). `771 passed + 1 environment-caused failure` reconciles with
`STATE.md`'s last recorded `772 passed / 67 skipped` from Phase 19. `tests/test_store_contract.py`
alone collects **102 tests** today [VERIFIED: measured this session via `pytest
tests/test_store_contract.py --collect-only -q`], matching CONTEXT's own figure. The
`notes` fixture (json/memory/chroma/pgvector) currently backs 8 shared behavioural
functions (`test_empty_memory_returns_nothing`, `test_notes_are_recalled`,
`test_recall_is_ordered_most_similar_first`, `test_top_k_bounds_the_result_count`,
`test_the_relevance_floor_excludes_unrelated_notes`, `test_describe_reports_the_count`,
`test_note_scoping`, `test_note_ttl`) [VERIFIED: tests/test_store_contract.py:493-611, read
this session] — 8 functions × 4 arms = 32 collected note-store test items today, out of
the file's 102.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-note-count-bound | Adding the (cap+1)-th note for one owner evicts the oldest, all 4 arms | contract | `pytest tests/test_store_contract.py -k "cap" -q` | ❌ new case, Wave 0 |
| REQ-note-count-bound | Eviction never crosses owners (owner A at cap, owner B adds — A untouched) | contract | `pytest tests/test_store_contract.py -k "cap_owner" -q` | ❌ new case, Wave 0 |
| REQ-note-count-bound | Sweep runs before the cap check (expired-but-unswept row + full cap + one add) | contract | `pytest tests/test_store_contract.py -k "cap_and_ttl" -q` | ❌ new case, Wave 0 |
| REQ-note-count-bound | `NOTE_CAP_PER_OWNER` is read per call and is monkeypatch-able, invalid input falls back to default | unit | `pytest tests/test_memory_stores.py -k "cap" -q` | ❌ new case, Wave 0 |
| REQ-note-count-bound | Chroma's `seq`-based tie-break survives out-of-order `get()` results | unit | `pytest tests/test_memory_stores.py -k "chroma_seq" -q` | ❌ new case, Wave 0 |
| REQ-note-count-bound | OPERATIONS.md configuration table documents the new knob | doc | manual review (grep for `NOTE_CAP_PER_OWNER` in `docs/OPERATIONS.md`) | ❌ Wave 0 doc task |

### Sampling Rate
- **Per task commit:** `pytest tests/test_store_contract.py -k "note or cap" -q`
- **Per wave merge:** `pytest tests/ -q` (full suite, keyless)
- **Phase gate:** Full suite green before `/gsd-verify-work`; pgvector arm requires
  `DATABASE_URL` locally or runs in CI where it is provisioned (unchanged from today).

### Wave 0 Gaps
- [ ] `note_cap_per_owner()` in `memory.py` — no test file gap, lands beside
      `note_ttl_seconds()` in the same module.
- [ ] New contract-suite cases in `tests/test_store_contract.py`'s existing "note ownership
      and expiry" section (lines 534–611) — extend in place, same fixture, same style.
- [ ] A Chroma-specific unit test in `tests/test_memory_stores.py` (or a new
      `test_memory_stores.py`-adjacent test) asserting `seq` assignment is correct under a
      stubbed/reordered `get()` return, since this is the one property the shared contract
      suite cannot exercise (it only ever sees `chromadb`'s real, currently-cooperative
      ordering).
- [ ] `docs/OPERATIONS.md`'s Configuration table (line 674, immediately after
      `NOTE_TTL_DAYS`) — new row for `NOTE_CAP_PER_OWNER`.

### Mutation probes (Nyquist)
- **Cap ignored entirely** (comment out the eviction call) → the new "evicts the oldest at
  cap+1" contract test must go red on all 4 arms, not just one — a mutation that reds only
  the json/memory arm would mean the chroma/pgvector implementations were never actually
  exercised by that test.
- **Eviction crosses owners** (drop the `owner ==` filter from the eviction query/subquery)
  → the "never crosses owners" test must go red; this is the isolation property Phase 12
  already established for `query()` and this phase must not regress for `add()`.
- **Tie-break nondeterministic** (sort purely by `created_at` with no secondary key) → a
  test seeding many notes with the SAME forced `created_at` (via a fake clock or
  monkeypatched `time.time`) then asserting a *specific* note is the one evicted must go
  red — this is the test that would have caught Pitfall 1 before it shipped.
- **Sweep/count order flipped** (evaluate the cap against the pre-sweep row count, or skip
  the sweep when under cap) → the composition test from Pitfall 2 (expired row + full cap +
  one add, asserted via unfiltered `len()`/count) must go red.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | Eviction must be strictly owner-scoped (exact match, never a wildcard on `owner=""`), the same invariant Phase 12 established for `query()`. A cross-owner eviction bug is a data-loss/isolation defect, not an authorization bypass, but sits in the same threat family this codebase already treats seriously (`test_note_scoping`). |
| V5 Input Validation | yes | `NOTE_CAP_PER_OWNER` is parsed defensively (unparseable/non-positive → default), matching `cost_discount_factor()`'s and `note_ttl_seconds()`'s existing pattern — never trusted as a raw int without a fallback. |
| V6 Cryptography | no | No cryptographic material touched by this phase. |
| V2 Authentication / V3 Session Management | no | This phase does not touch identity or session lifecycle; `owner` is an opaque, already-authenticated string by the time it reaches `MemoryStore.add()`. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-owner eviction (a bug removes owner B's notes while adding owner A's) | Tampering / Information Disclosure (of the *absence* kind — silent data loss) | Owner-exact-match filter on every eviction query, mirrored across all 4 backends, proven by the contract suite's dedicated "never crosses owners" case |
| SQL injection via table name in the eviction `DELETE` | Tampering | Already mitigated pre-existing: `validate_table_name()` runs in `__init__` before any query is built [VERIFIED: memory.py:457-470, read this session]; the eviction SQL adds no new interpolated value beyond the already-validated `self.table` |
| A misconfigured `NOTE_CAP_PER_OWNER` silently disabling recall (cap=0 read literally) | Denial of Service (of the "feature quietly stops working" kind, not availability) | The `≤0 → default` clamp (Pattern 1) — the same class of mitigation `cost_discount_factor()` already uses for an analogous "0 is a plausible-but-dangerous typo" risk |

## Sources

### Primary (HIGH confidence — read/measured this session)
- `src/research_agent/memory.py` (full file, 664 lines) — all four backend `add()`
  implementations, the TTL sweep, `validate_table_name`, the pgvector schema/RLS DDL
- `src/research_agent/sessions.py:95-121` — `session_ttl_seconds()`, the per-call env-knob
  convention this phase's `note_cap_per_owner()` mirrors
- `src/research_agent/usage.py:225-271` — `cost_discount_factor()` /
  `inference_geo_multiplier()`, the `≤0 → default` clamp precedent
- `src/research_agent/limits.py:1-115` — `_env_int`/`_env_float`, `rate_limit_per_hour()`
  ("0 disables"), `reserved_run_usd()` (floor-at-zero) — the two other existing clamp
  styles, read to justify choosing the `usage.py` style over them
- `src/research_agent/db.py:224-227` — `autocommit: True` in `_connect_kwargs`, the basis
  for the concurrency note in Pattern 4
- `src/research_agent/migrate.py` (full file, 847 lines) — confirmed `migrate_notes`,
  `copy_embeddings`, `reembed_notes` all write via raw `db.execute`/`INSERT`, never
  `store.add()`
- `src/research_agent/recall_golden.py:179-218` — confirmed `seed()` bypasses `add()` by
  pre-existing design (docstring explains why, unrelated to this phase)
- `src/research_agent/graph.py:315-380` — confirmed `researcher_node` is the only
  production caller of `store.add()`
- `evals/harness.py:265-301` — confirmed `store.add(note, owner="")` in the eval harness
  seeds a small, fresh, per-case store, no accumulation risk
- `tests/test_store_contract.py` (full file, 1128 lines) — the `notes` fixture, the 8
  existing note-behavioural tests, current 102-test collection count
- `tests/test_memory_stores.py` (full file) — `FakeEmbedder`, its vocabulary-collision
  behavior for out-of-vocab text
- `docs/OPERATIONS.md:630-678` — the Configuration table's existing format and the
  `NOTE_TTL_DAYS` row this phase's new row sits beside
- `README.md:277-291` — the exact "Notes are bounded by expiry alone" bullet this phase
  falsifies (left in place per CONTEXT, Phase 22's to remove)
- Empirical measurement this session: `time.time()` clock resolution (14/200 unique),
  `time.time_ns()` (22/300 unique), `time.perf_counter_ns()` (300/300 unique but not
  wall-clock-comparable) — Python 3.14, this machine
- Empirical measurement this session: `chromadb==1.4.1` `PersistentClient`,
  `collection.get()` insertion-order preservation across two scenarios (plain sequential
  add, and delete-then-add)
- `pytest tests/ -q` and `pytest tests/test_store_contract.py --collect-only -q`, run this
  session — baseline counts (771 passed / 67 skipped / 1 environment-caused failure; 102
  collected in the contract file)

### Secondary (MEDIUM confidence)
None used — every claim in this document is either read directly from the repository this
session or measured directly this session. No web search was needed: this phase is an
internal extension of an existing, fully-documented in-repo pattern, not a new external
integration.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, nothing to verify against a registry
- Architecture: HIGH — every pattern is derived from code read this session, not from
  memory or assumption
- Pitfalls: HIGH — the two most load-bearing pitfalls (clock collision, sweep/cap
  composition) are backed by empirical measurement, not inference
- Tie-break design (Chroma `seq`): MEDIUM — the design is sound and the underlying risk
  (undocumented `get()` ordering) is verified, but the exact metadata-field approach is
  this research's synthesis, not something already proven in this codebase; flagged in the
  Assumptions Log

**Research date:** 2026-08-14
**Valid until:** No external time pressure — this is an internal-only extension with no
external API surface to go stale. Re-verify only if `chromadb`'s pinned version changes
(re-run the empirical `get()`-ordering check against the new version before trusting it).
