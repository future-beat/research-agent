"""
A frozen recall set, and the only honest way to compare two pgvector tables.

The phase this belongs to changes two things that both move recall: the table
the notes live in (infrastructure) and the model that produced their vectors
(the model itself). Changing both at once and then asking "did recall get
worse?" leaves two suspects and no way to separate them. So each operation is
measured against the same frozen corpus and the same frozen queries: the
copy-only path must show *zero* delta, which is what makes the re-embed path's
delta attributable to the model by construction.

WHY THE INDEX IS NOT ALLOWED INSIDE THE CLAIM. `PgVectorMemoryStore` searches
through an HNSW index, which is approximate by design -- pgvector's own README
says it can miss results, and `hnsw.ef_search` defaults to 40. Its build is
parallelised and its level assignment randomized, so two builds over identical
vectors are not guaranteed to produce identical graphs. An equality-of-recall
assertion made through the index therefore asserts "the approximation agreed
twice", which a rebuild can falsify without a single byte of data having
changed. `exact_scan_results` turns the index off for the duration of one
transaction (`SET LOCAL enable_indexscan = off`, pgvector's documented exact
search) so the comparison is over the vectors themselves, where identical bytes
force identical distances and identical order.

`indexed_results` exists for the *separate*, weaker, honestly-labelled check
that the indexed path agrees with the exact scan as a set at this corpus size.
Never use it in an equality-of-recall assertion.

ORDER IS ONLY DETERMINISTIC IF THERE ARE NO TIES. The production query orders
by `embedding <=> q` with no tiebreak, so two rows at the same distance come
back in whatever order the executor produced them. That is a property of the
*data*, not of the store, and this module fixes it in the data rather than by
touching production SQL: `assert_tie_free` is a required part of using the
golden set, not an optional extra. With the 5-dimensional binary bag-of-words
vectors the test embedder produces, ties are easy to create by accident --
distinct vocabulary sets are NOT enough, since similarity depends only on
(overlap, size) and e.g. {chroma,retry} and {chroma,voyage} sit at exactly the
same distance from the query "chroma".

AND THE QUERY VECTOR HAS TO BE HELD STILL TOO. The index and the ties are both
properties of the stored side. The third source of variance is the *query*
side: comparing two tables means asking each golden query twice, and a real
embedding API does not guarantee a bit-identical vector for the same text on
two separate calls. Measured live on 2026-08-09, the source table compared
with ITSELF deltaed on 2 of the 8 golden queries for exactly that reason.
Wrap the embedder in `FrozenQueryEmbedder` for any comparison whose embedder
is not provably deterministic; see its docstring.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from research_agent import db
from research_agent.memory import PgVectorMemoryStore

# --------------------------------------------------------------------------
# The frozen corpus
# --------------------------------------------------------------------------
#
# Written over the test embedder's five-word vocabulary
# (langgraph, chroma, retry, voyage, supervisor) because the thing being
# measured is the *store's* behaviour across a migration, not the quality of
# somebody's embedding model -- the same argument test_memory_stores.py makes.
#
# Three owners: two real ones and `''`, which under Phase 12 scoping is the
# owner nobody has (a real identity is a 32-hex uuid). Within a single owner
# every note carries a distinct set of vocabulary words, because the embedder
# maps a set to a vector: two notes with the same set are the same point, and
# any query would then have to break a tie between them. Distinct sets are
# necessary and not sufficient -- see assert_tie_free.
#
# "chroma retry" appears under BOTH alice and bob on purpose. It is the
# tenancy probe: a migration that drops the owner column merges these two rows
# into one recall result set, and GOLDEN_QUERIES asks each owner for it.

GOLDEN_NOTES: list[dict[str, str]] = [
    # alice -- vocab sets {C,R} {L} {R,S,V} {C,L,S,V} {C,S}
    {"text": "chroma retry", "owner": "alice"},
    {"text": "langgraph", "owner": "alice"},
    {"text": "voyage supervisor retry", "owner": "alice"},
    {"text": "langgraph chroma voyage supervisor", "owner": "alice"},
    {"text": "chroma supervisor", "owner": "alice"},
    # bob -- vocab sets {C,R} {V} {C,L,S} {L,R}
    {"text": "chroma retry", "owner": "bob"},
    {"text": "voyage", "owner": "bob"},
    {"text": "langgraph chroma supervisor", "owner": "bob"},
    {"text": "langgraph retry", "owner": "bob"},
    # '' -- vocab sets {S} {L,V} {L,S,V}. Deliberately no `chroma` and no
    # `retry` anywhere under this owner, which is what makes the below-floor
    # query below return nothing rather than merely returning little.
    {"text": "supervisor", "owner": ""},
    {"text": "langgraph voyage", "owner": ""},
    {"text": "langgraph voyage supervisor", "owner": ""},
]

# top_k and min_similarity are per-query rather than global so the set can hold
# both an ordering query (generous k, ordinary floor) and a query whose whole
# point is that it returns nothing.
GOLDEN_QUERIES: list[dict[str, Any]] = [
    # The tenancy probe, asked once per owner. Alice and bob each store the
    # text "chroma retry"; each must see their own row and none of the other's
    # neighbours. A copy that drops `owner` merges the two result sets.
    {"query": "chroma retry", "owner": "alice", "top_k": 3, "min_similarity": 0.3},
    {"query": "chroma retry", "owner": "bob", "top_k": 3, "min_similarity": 0.3},
    # Same query, the unowned bucket: nothing under '' contains either word,
    # so every candidate is below the floor and the result is []. An empty
    # result is a real assertion here -- a copy that lost `owner` would drop
    # alice's and bob's rows into this bucket and it would stop being empty.
    {"query": "chroma retry", "owner": "", "top_k": 3, "min_similarity": 0.3},
    # Relevance ordering within one owner.
    {"query": "langgraph", "owner": "alice", "top_k": 3, "min_similarity": 0.3},
    {"query": "voyage supervisor", "owner": "alice", "top_k": 4, "min_similarity": 0.3},
    {"query": "chroma supervisor", "owner": "bob", "top_k": 3, "min_similarity": 0.3},
    {"query": "langgraph retry", "owner": "bob", "top_k": 3, "min_similarity": 0.3},
    # The empty-owner bucket, returning rows this time.
    {"query": "supervisor", "owner": "", "top_k": 3, "min_similarity": 0.3},
]


class Embedder(Protocol):  # pragma: no cover - structural typing only
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FrozenQueryEmbedder:
    """Embed each query text once, then reuse that vector for every table.

    THE SECOND VARIABLE NOBODY WAS LOOKING FOR. `recall_delta` compares
    `run_golden(old)` with `run_golden(new)`, and each of those calls
    `embed_query` on the same text again -- so a comparison meant to isolate
    one variable actually contains two: the table, and whatever the embedder
    returned the second time it was asked.

    Under a deterministic test embedder that is free, which is why every local
    gate in this phase was green without it. Against a real embedding API it is
    not: on 2026-08-09, comparing the live Supabase source table with ITSELF
    produced a nonzero delta on 2 of the 8 golden queries -- same notes, same
    order, similarities differing around the fourth decimal, because the two
    runs got query vectors that were not bit-identical. Repeated back-to-back
    calls often DO agree, which is worse than if they never did: the artefact
    is intermittent, so a run that happens to come back clean is not evidence
    that the next one will.

    Wrapping the embedder in this makes the query vector a constant of the
    measurement instead of a fresh sample per table, which is what "one
    variable at a time" required all along. Use it for any comparison across
    two tables whose embedder is not provably deterministic -- and note that
    across a MODEL change each model needs its own wrapper, since the point
    there is that the two query vectors differ.

    `embed_documents` is delegated rather than cached: seeding is not a
    repeated question about the same text, and pretending otherwise would hide
    a corpus being written twice.
    """

    def __init__(self, inner: Embedder):
        self.inner = inner
        self._cache: dict[str, list[float]] = {}
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        if text not in self._cache:
            self.calls += 1
            self._cache[text] = self.inner.embed_query(text)
        return self._cache[text]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self.inner.embed_documents(texts)


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------


def seed(
    database: db.Database,
    table: str,
    embedder: Embedder,
    dimensions: int,
) -> int:
    """Create `table` and write the golden corpus into it. Returns the count.

    Deliberately NOT through `store.add()`. That method stamps `created_at`
    with the server's `now()` and runs a TTL sweep on every call, so the same
    corpus seeded twice would differ in the column this module later joins on.
    Here each note gets a fixed place on a descending minute ladder: distinct
    per note (so `(text, owner, created_at)` is a key even for the two rows
    that share a text), recent enough that the 7-day note TTL is vacuous, and
    identical in shape between any two runs.

    The DDL goes through `PgVectorMemoryStore` rather than a hand-written
    CREATE TABLE so the table this measures is the table production uses --
    same columns, same HNSW index, same advisory-locked ensure_schema path.
    The store gets its own `Database` on the caller's DSN on purpose: a
    `Database` applies at most one schema block in its lifetime, so handing it
    the caller's handle would silently skip the DDL whenever that handle had
    already created some other table.
    """
    ensure_table(database, table, dimensions, embedder)

    vectors = embedder.embed_documents([note["text"] for note in GOLDEN_NOTES])
    base = datetime.now(timezone.utc)
    for offset, (note, vector) in enumerate(zip(GOLDEN_NOTES, vectors, strict=True)):
        database.execute(
            f"INSERT INTO {table} (text, embedding, owner, created_at) "
            f"VALUES (%s, %s::vector, %s, %s)",
            (
                note["text"],
                PgVectorMemoryStore._literal(vector),
                note["owner"],
                base - timedelta(minutes=offset),
            ),
        )
    return len(GOLDEN_NOTES)


def ensure_table(
    database: db.Database,
    table: str,
    dimensions: int,
    embedder: Embedder | None = None,
) -> None:
    """Create `table` with the production schema, on `database`'s DSN."""
    store = PgVectorMemoryStore(
        table=table,
        dimensions=dimensions,
        embedder=embedder,
        database=db.Database(dsn=database.dsn),
    )
    store.close()


# --------------------------------------------------------------------------
# Querying
# --------------------------------------------------------------------------

# The production SELECT from PgVectorMemoryStore.query(), minus the TTL
# predicate: the golden rows are minutes old, so the predicate is vacuous, and
# leaving it in would make every comparison depend on the wall clock. Every
# other clause is byte-for-byte the production shape, because the point of the
# measurement is production semantics and a parallel re-implementation can
# agree with itself while disagreeing with the store.
_QUERY_SQL = """
    SELECT text, 1 - (embedding <=> %s::vector) AS similarity
    FROM {table}
    WHERE 1 - (embedding <=> %s::vector) >= %s
      AND owner = %s
    ORDER BY embedding <=> %s::vector
    LIMIT %s
"""


def exact_scan_results(
    database: db.Database,
    table: str,
    embedder: Embedder,
    query: str,
    owner: str,
    top_k: int,
    min_similarity: float,
) -> list[tuple[str, float]]:
    """The production query with the ANN index taken out of the loop.

    `SET LOCAL enable_indexscan = off` is pgvector's documented exact-search
    switch and is scoped to the surrounding transaction, which is why this goes
    through `Database.transaction()` rather than the autocommit helpers: under
    autocommit a `SET LOCAL` has no transaction to be local to and would either
    leak onto a pooled connection or evaporate.

    This is the ONLY runner an equality-of-recall assertion may use.
    """
    literal = PgVectorMemoryStore._literal(embedder.embed_query(query))
    with database.transaction() as cur:
        cur.execute("SET LOCAL enable_indexscan = off")
        cur.execute(
            _QUERY_SQL.format(table=table),
            (literal, literal, min_similarity, owner, literal, top_k),
        )
        return [(row[0], float(row[1])) for row in cur.fetchall()]


def indexed_results(
    database: db.Database,
    table: str,
    embedder: Embedder,
    query: str,
    owner: str,
    top_k: int,
    min_similarity: float,
) -> list[tuple[str, float]]:
    """The same query left to the planner, i.e. the path production takes.

    For the index-sanity check only, and only as a SET comparison. See the
    module docstring for why its ordering is not something to assert on.
    """
    literal = PgVectorMemoryStore._literal(embedder.embed_query(query))
    rows = database.fetchall(
        _QUERY_SQL.format(table=table),
        (literal, literal, min_similarity, owner, literal, top_k),
    )
    return [(row["text"], float(row["similarity"])) for row in rows]


def query_key(spec: dict[str, Any]) -> str:
    """A stable identifier for one golden query, for delta reporting."""
    return f"{spec['query']!r}@{spec['owner']!r}"


def run_golden(
    database: db.Database,
    table: str,
    embedder: Embedder,
    runner=exact_scan_results,
) -> dict[str, list[tuple[str, float]]]:
    """Every golden query against `table`, keyed for comparison."""
    return {
        query_key(spec): runner(
            database,
            table,
            embedder,
            spec["query"],
            spec["owner"],
            spec["top_k"],
            spec["min_similarity"],
        )
        for spec in GOLDEN_QUERIES
    }


# --------------------------------------------------------------------------
# Comparison -- store-agnostic on purpose: it speaks (text, score) pairs and
# knows nothing about Postgres, so a future backend can be measured the same
# way. Only the two runners above are pgvector-specific.
# --------------------------------------------------------------------------


def recall_delta(
    old_results: dict[str, list[tuple[str, float]]],
    new_results: dict[str, list[tuple[str, float]]],
) -> list[dict[str, Any]]:
    """Per-query ordered comparison including scores. Empty == identical.

    Ordered and score-bearing rather than set-of-texts: a migration that
    preserved *which* notes come back while reordering them, or while shifting
    their similarities, has changed recall and should say so.
    """
    delta: list[dict[str, Any]] = []
    for key in sorted(set(old_results) | set(new_results)):
        old = old_results.get(key)
        new = new_results.get(key)
        if old == new:
            continue
        delta.append({"query": key, "old": old, "new": new})
    return delta


# --------------------------------------------------------------------------
# The self-check
# --------------------------------------------------------------------------


def assert_tie_free(database: db.Database, table: str, embedder: Embedder) -> None:
    """Raise unless every golden query's answer is uniquely ordered.

    For each query, every row under the queried owner is scored by exact scan
    and the ones at or above that query's floor are checked for duplicate
    similarities. Two rows at the same distance are ordered arbitrarily by the
    production SQL (no tiebreak, and none is being added -- changing recall
    semantics is out of scope), so an ordered comparison over them would flake
    between runs on identical data and the copy gate would be measuring the
    executor rather than the migration.

    The floor is part of the check, not an omission from it: rows the query
    cannot return cannot affect its order, and requiring global tie-freedom
    over 5-dimensional binary vectors is not merely strict but impossible --
    any two notes sharing no word with the query both sit at similarity 0.
    """
    problems = []
    for spec in GOLDEN_QUERIES:
        literal = PgVectorMemoryStore._literal(embedder.embed_query(spec["query"]))
        with database.transaction() as cur:
            cur.execute("SET LOCAL enable_indexscan = off")
            cur.execute(
                f"SELECT text, 1 - (embedding <=> %s::vector) AS similarity "
                f"FROM {table} WHERE owner = %s",
                (literal, spec["owner"]),
            )
            scored = [(row[0], float(row[1])) for row in cur.fetchall()]
        eligible = [pair for pair in scored if pair[1] >= spec["min_similarity"]]
        seen: dict[float, str] = {}
        for text, similarity in eligible:
            if similarity in seen:
                problems.append(
                    f"{query_key(spec)}: {seen[similarity]!r} and {text!r} both score "
                    f"{similarity!r} -- the order between them is arbitrary"
                )
            seen[similarity] = text
    if problems:
        raise ValueError(
            "The golden set is not tie-free, so ordered recall comparison over it "
            "would measure the query executor rather than the migration:\n  "
            + "\n  ".join(problems)
        )
