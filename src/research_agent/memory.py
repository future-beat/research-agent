"""
Pluggable long-term memory for the research agent.

There are two independent seams here, and keeping them separate is the whole
point of this module:

    Embedder     text -> vector.  VoyageEmbedder is the default; anything with
                 embed_documents()/embed_query() works.
    MemoryStore  add() / query().  JSONMemoryStore (file-backed, the original
                 behaviour), InMemoryStore (ephemeral), ChromaMemoryStore
                 (a real ANN-indexed vector DB).

The graph only ever touches add() / query() / len() / describe(), so swapping
the backend never reaches graph.py.

Select a backend at runtime:

    VECTOR_STORE=json      # default; JSON file next to this module
    VECTOR_STORE=memory    # nothing persisted; useful for tests and workers
    VECTOR_STORE=chroma    # persistent Chroma collection (pip install chromadb)

Requires: pip install voyageai numpy
Requires: VOYAGE_API_KEY set in your environment (separate from your
Anthropic key -- get one at https://www.voyageai.com/)
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from research_agent import db, usage

EMBEDDING_MODEL = os.environ.get("VOYAGE_EMBEDDING_MODEL", "voyage-3.5")

# Anchored to this file's directory, not the working directory, so the store
# is the same one no matter where you launch from. A relative default would
# silently create a second, empty store when run from elsewhere.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.environ.get(
    "VECTOR_STORE_PATH", os.path.join(_MODULE_DIR, "agent_memory_store.json")
)
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(_MODULE_DIR, "chroma_store"))
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "research_notes")

# pgvector needs a fixed column width, and voyage-3.5 emits 1024 dimensions.
# Validated on the first write rather than trusted: a mismatch would otherwise
# surface as a Postgres type error deep inside an insert, which is a miserable
# way to find out you changed embedding model.
PGVECTOR_TABLE = os.environ.get("PGVECTOR_TABLE", "research_notes")
VECTOR_DIMENSIONS = int(os.environ.get("VECTOR_DIMENSIONS", "1024"))

DEFAULT_TOP_K = 3
DEFAULT_MIN_SIMILARITY = 0.3

NOTE_TTL_DAYS_DEFAULT = 7.0
NOTE_CAP_PER_OWNER_DEFAULT = 100


def note_ttl_seconds() -> float:
    """How long a note survives its creation, in seconds.

    Seven days, matching SESSION_TTL_DAYS: notes and sessions are the same
    hygiene problem wearing different hats, and two different answers to "how
    long does the demo remember you" would be a thing to keep in sync rather
    than a decision.

    Notes are written once and never updated, so created_at *is* last activity
    -- there is no "expires after a week of inactivity" / "a week after
    creation" distinction to get wrong here, unlike sessions.

    Read per call rather than cached, the convention every env-driven knob in
    this codebase uses, so a test can flip it with monkeypatch.setenv.
    """
    raw = os.environ.get("NOTE_TTL_DAYS", "").strip()
    try:
        days = float(raw) if raw else NOTE_TTL_DAYS_DEFAULT
    except ValueError:
        days = NOTE_TTL_DAYS_DEFAULT
    return max(days, 0.0) * 86400.0


def note_cap_per_owner() -> int:
    """How many live notes one owner may hold before the oldest is evicted.

    The second bound, and independent of the first: the TTL answers how long a
    note survives, this answers how many an identity may accumulate. Read per
    call, the note_ttl_seconds() convention, so a test can flip it with
    monkeypatch.setenv and a reconfigured process answers the new number.

    Unparseable OR <= 0 falls back to the default rather than being honoured.
    Deliberately NOT note_ttl_seconds()'s floor-at-zero: there, zero is a
    meaningful value the TTL tests use on purpose to put a note past the
    cutoff without sleeping a week. A cap of zero has no such meaning -- every
    add() would evict the note it just wrote, so memory recall would be
    silently off with no error and no log line. That is the same shape of
    foot-gun cost_discount_factor() clamps for the same reason. An operator who
    wants no cap does not set this variable.
    """
    raw = os.environ.get("NOTE_CAP_PER_OWNER", "").strip()
    try:
        cap = int(raw) if raw else NOTE_CAP_PER_OWNER_DEFAULT
    except ValueError:
        return NOTE_CAP_PER_OWNER_DEFAULT
    return cap if cap > 0 else NOTE_CAP_PER_OWNER_DEFAULT


# --------------------------------------------------------------------------
# Embedder seam
# --------------------------------------------------------------------------


class Embedder(Protocol):
    """Anything that turns text into vectors. Two methods, because most
    embedding APIs (Voyage included) want to know whether a string is a
    document being stored or a query being matched against documents."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VoyageEmbedder:
    """Voyage AI embeddings.

    The client is built on first use rather than at import time: constructing
    it eagerly would make this module unimportable without VOYAGE_API_KEY,
    which in turn would make the graph untestable.
    """

    def __init__(self, model: str = EMBEDDING_MODEL, output_dimension: int | None = None):
        self.model = model
        # None means "whatever the model emits by default" -- which is what
        # every existing caller asked for implicitly, so leaving it None makes
        # their requests byte-identical to what they sent before. Only the
        # re-embedding migration passes a value, and only to ask a model for a
        # width other than its default (voyage-3.5 offers 256/512/1024/2048).
        self.output_dimension = output_dimension
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import voyageai  # imported lazily for the same reason

            self._client = voyageai.Client()  # reads VOYAGE_API_KEY
        return self._client

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        response = self.client.embed(
            list(texts),
            model=self.model,
            input_type="document",
            output_dimension=self.output_dimension,
        )
        self._report(response)
        return response.embeddings

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embed(
            [text],
            model=self.model,
            input_type="query",
            output_dimension=self.output_dimension,
        )
        self._report(response)
        return response.embeddings[0]

    def _report(self, response) -> None:
        """Hand the billed token count to whoever is metering this scope.

        The `Embedder` seam stays vectors-in-vectors-out -- widening it would
        touch a Protocol, an ABC, four backends and every test fake to carry a
        number three of them would immediately discard. Instead the count goes
        out of band to `usage.report_embedding`, which is a no-op unless a
        caller opened a meter. Without this the response's `total_tokens`
        arrived here and was dropped on the floor, which is how a whole
        provider stayed off the cost report.

        Read defensively, exactly as `migrate.py` reads the same field: an
        absent count means "nothing to report", not a crash halfway through a
        run that has already been billed for.
        """
        usage.report_embedding(self.model, getattr(response, "total_tokens", 0))


# --------------------------------------------------------------------------
# Store seam
# --------------------------------------------------------------------------


class MemoryStore(ABC):
    """The entire contract the graph depends on.

    `owner` is the caller identity a note belongs to, and it is the reason
    this module changed in Phase 12. Notes used to go into one communal store
    and be recalled into *other* visitors' runs, where the researcher pastes
    them into a prompt the critic then reads -- so a note one visitor caused
    to be written could steer another visitor's report. Scoping recall to the
    caller closes that path.

    Three properties every backend must implement identically, because the
    behavioural suite asserts them on all four:

    * Owner matching is EXACT. `owner=""` retrieves only `owner=""` notes; it
      is never a wildcard. Pre-Phase-12 rows carry the empty owner and so
      belong to nobody, which is the intended answer for them.
    * A note older than NOTE_TTL_DAYS is not recalled, and is physically
      removed by the next add(). Lazy filter plus opportunistic sweep, exactly
      as sessions do it -- the filter is what makes expiry immediate, the
      sweep is what stops an abandoned identity's notes outliving them.
    * One owner holds at most NOTE_CAP_PER_OWNER live notes. Writing past the
      cap evicts that owner's oldest, oldest-first, inside the same add() that
      wrote the new one -- so the bound holds after every write rather than
      eventually, and no scheduler is involved. Eviction is owner-scoped by
      the same exact match recall uses: filling one identity's bucket never
      touches another's. "Oldest" is decided by each backend's insertion-
      ordered key (list index, an explicit seq, BIGSERIAL id) and never by
      created_at alone, because a tight write loop collides on the wall clock
      and four backends breaking that tie differently is precisely how
      "identical behaviour" stops being true.

    Deliberately NOT here: dedup-on-write. It is one unique index in pgvector
    and four different hand-rolled approximations everywhere else, which is
    precisely the "backends quietly disagree" failure this suite exists to
    prevent. Expiry and the count cap are the two bounds; there is no third,
    and no semantic one.
    """

    @abstractmethod
    def add(self, text: str, owner: str = "") -> None:
        """Embed and store one note for `owner`.

        Three steps in one fixed order on every backend: sweep expired notes
        (unconditionally -- an owner nowhere near the cap still gets their
        stale rows removed), insert the new note, then evict this owner's
        oldest while they hold more than NOTE_CAP_PER_OWNER. The sweep runs
        first so the cap counts only live notes.

        The default keeps the REPL, the __main__ demo and the eval harness --
        none of which have a caller -- working unchanged; the service always
        passes a real identity.

        Returns nothing about eviction: no caller needs it, and widening the
        return type would move the one seam graph.py depends on.
        """

    @abstractmethod
    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        owner: str = "",
    ) -> list[str]:
        """Return up to top_k of `owner`'s unexpired notes scoring at or above
        min_similarity, most similar first."""

    @abstractmethod
    def __len__(self) -> int:
        """How many notes are stored."""

    @abstractmethod
    def describe(self) -> str:
        """One line naming the backend and where it lives, for the REPL."""

    def close(self) -> None:  # noqa: B027 - a deliberate no-op default
        """Release any connection.

        Not abstract: three of the four backends hold nothing to close, and
        forcing each to write an empty method would be noise. Callers get to
        call close() without asking which kind of store they were handed.
        """


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class _BruteForceStore(MemoryStore):
    """Shared scoring for the backends that keep every vector in a Python list
    and scan all of them. Exact cosine ranking, O(n) per query -- correct at
    hundreds of notes, the wrong shape at hundreds of thousands. That's what
    ChromaMemoryStore is for."""

    def __init__(self, embedder: Embedder | None = None):
        self.embedder = embedder or VoyageEmbedder()
        self.entries: list[dict] = []
        # The service runs graph nodes in a thread pool, so two researchers can
        # be adding notes while a third reads. The lock covers the list and the
        # file together -- without it, a save could serialize a half-appended
        # list, or a query could scan entries mid-mutation.
        self._lock = threading.RLock()

    def add(self, text: str, owner: str = "") -> None:
        # Embedding is a network call; deliberately outside the lock so a slow
        # Voyage response doesn't block every concurrent reader.
        embedding = self.embedder.embed_documents([text])[0]
        now = time.time()
        cutoff = now - note_ttl_seconds()
        with self._lock:
            # Opportunistic sweep on the rare expensive event rather than on a
            # timer, mirroring the session store. A lazy filter alone hides
            # expired notes; this is what physically removes them. It runs
            # unconditionally and BEFORE the cap check below, so an owner
            # nowhere near the cap still gets their stale rows collected --
            # folding the two together would leave low-volume owners unswept.
            # Entries written before Phase 12 have no created_at, read as 0,
            # and are collected here -- which is how the orphaned notes go.
            self.entries = [e for e in self.entries if e.get("created_at", 0.0) > cutoff]
            self.entries.append(
                {"text": text, "embedding": list(embedding), "owner": owner, "created_at": now}
            )
            # The count bound, applied to this owner only and to the survivors
            # of the sweep above -- never to expired rows, which are already
            # gone. No timestamp is consulted to find "oldest": self.entries
            # only ever grows by append() and shrinks by filters that preserve
            # order, so list index order IS insertion order and the tie-break
            # created_at cannot provide comes free by construction.
            cap = note_cap_per_owner()
            owned = [i for i, e in enumerate(self.entries) if e.get("owner", "") == owner]
            if len(owned) > cap:
                drop = set(owned[: len(owned) - cap])
                self.entries = [e for i, e in enumerate(self.entries) if i not in drop]
            self._persist()

    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        owner: str = "",
    ) -> list[str]:
        cutoff = time.time() - note_ttl_seconds()
        with self._lock:
            # Exact owner match, never "empty means all": a legacy entry with
            # no owner key reads as "" and so belongs to nobody.
            snapshot = [
                entry
                for entry in self.entries
                if entry.get("owner", "") == owner and entry.get("created_at", 0.0) > cutoff
            ]
        if not snapshot:
            return []

        query_vec = np.array(self.embedder.embed_query(query_text))
        scored = [
            (_cosine(query_vec, np.array(entry["embedding"])), entry["text"])
            for entry in snapshot
        ]
        scored.sort(reverse=True, key=lambda pair: pair[0])
        return [text for sim, text in scored[:top_k] if sim >= min_similarity]

    def __len__(self) -> int:
        with self._lock:
            return len(self.entries)

    def _persist(self) -> None:
        """No-op unless the subclass is durable."""


class InMemoryStore(_BruteForceStore):
    """Nothing touches disk. Used by the test suite, and by any deployment
    that wants recall within a process but no shared state between them."""

    def describe(self) -> str:
        return f"{len(self)} note(s) in an ephemeral in-memory store (nothing persisted)"


class JSONMemoryStore(_BruteForceStore):
    """The original behaviour: a JSON list of {"text", "embedding"} on disk.

    Rewrites the whole file on every add. Fine for a single-process agent;
    it is also exactly why this is not the production default at scale.
    """

    def __init__(self, path: str = STORE_PATH, embedder: Embedder | None = None):
        super().__init__(embedder)
        self.path = path
        self.entries = self._load()

    def _load(self) -> list[dict]:
        if os.path.exists(self.path):
            with open(self.path) as f:
                return json.load(f)
        return []

    def _persist(self) -> None:
        # Write-then-rename so an interrupted save can't truncate the store.
        # Called under the store lock.
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(self.entries, f)
        os.replace(tmp, self.path)

    def describe(self) -> str:
        return f"{len(self)} note(s) in JSON store at {self.path}"


class ChromaMemoryStore(MemoryStore):
    """Chroma-backed store: same cosine ranking, but with an ANN index and
    without loading every vector into this process.

    Requires `pip install chromadb`. Embeddings are still produced by our own
    Embedder, so switching stores never silently switches embedding models --
    that would invalidate every vector already written.
    """

    def __init__(
        self,
        path: str = CHROMA_PATH,
        collection: str = CHROMA_COLLECTION,
        embedder: Embedder | None = None,
    ):
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "VECTOR_STORE=chroma requires chromadb. Install it with "
                "`pip install chromadb`, or use VECTOR_STORE=json."
            ) from exc

        self.embedder = embedder or VoyageEmbedder()
        self.path = path
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )

    def _sweep(self, cutoff: float) -> tuple[list[tuple[str, dict]], int]:
        """Delete notes created at or before `cutoff`; report what survived.

        Read back and filtered in Python rather than expressed as a chroma
        `where` clause on created_at. The TTL comparison then has exactly one
        implementation per store rather than one for the sweep and another for
        the filter, and the four backends stay observably identical -- which
        is the only claim the shared suite can make.

        The survivors come back as (id, metadata) pairs, and with them the
        next `seq` to hand out, because add()'s cap eviction needs both and
        this get() is the only scan it may rely on. Re-fetching to find the
        ids of the notes being evicted would put get()'s *return order* on the
        critical path; deriving next_seq as a max over the survivors needs the
        scan to be COMPLETE, which chroma does promise, rather than ORDERED,
        which it does not.
        """
        got = self._collection.get(include=["metadatas"])
        ids = got.get("ids") or []
        metadatas = got.get("metadatas") or []
        stale = [
            note_id
            for note_id, meta in zip(ids, metadatas, strict=True)
            if float((meta or {}).get("created_at", 0.0)) <= cutoff
        ]
        if stale:
            self._collection.delete(ids=stale)
        dead = set(stale)
        survivors = [
            (note_id, meta or {})
            for note_id, meta in zip(ids, metadatas, strict=True)
            if note_id not in dead
        ]
        next_seq = max((int(meta.get("seq", 0)) for _, meta in survivors), default=0) + 1
        return survivors, next_seq

    def add(self, text: str, owner: str = "") -> None:
        embedding = self.embedder.embed_documents([text])[0]
        now = time.time()
        survivors, next_seq = self._sweep(now - note_ttl_seconds())
        # A uuid rather than the old f"note-{count}-{hash(text)}". Once the
        # sweep can shrink the collection, count() is no longer monotonic,
        # so the same text added after an eviction could reproduce an id
        # already in use -- and chroma treats a repeated id as an upsert,
        # which would silently overwrite a live note instead of adding one.
        note_id = uuid.uuid4().hex
        self._collection.add(
            ids=[note_id],
            documents=[text],
            embeddings=[list(embedding)],
            # `seq` is this backend's answer to the tie-break the other three
            # get for free (a list index, a BIGSERIAL id). It is not
            # redundant with created_at: a tight write loop produces identical
            # wall-clock stamps, and chroma's get() returning items in
            # insertion order is observed behaviour of 1.4.1, not an API
            # contract, so it must not be what decides which note is evicted.
            metadatas=[{"owner": owner, "created_at": now, "seq": next_seq}],
        )
        # The count bound, over this owner's post-sweep survivors plus the note
        # just written. Rows predating this field read seq 0 -- correct, since
        # they genuinely are the oldest, and transient, since the TTL retires
        # them within a week.
        cap = note_cap_per_owner()
        owned = [(nid, meta) for nid, meta in survivors if meta.get("owner", "") == owner]
        owned.append((note_id, {"owner": owner, "created_at": now, "seq": next_seq}))
        if len(owned) > cap:
            owned.sort(key=lambda pair: int(pair[1].get("seq", 0)))
            self._collection.delete(ids=[nid for nid, _ in owned[: len(owned) - cap]])

    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        owner: str = "",
    ) -> list[str]:
        count = self._collection.count()
        if not count:
            return []

        result = self._collection.query(
            query_embeddings=[list(self.embedder.embed_query(query_text))],
            n_results=min(top_k, count),
            where={"owner": owner},
            include=["documents", "distances", "metadatas"],
        )
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        cutoff = time.time() - note_ttl_seconds()
        # Chroma reports cosine *distance* (1 - similarity) in a cosine space.
        return [
            doc
            # strict=True: these come from one query and must be the same
            # length. A mismatch means the filter below is comparing a document
            # against another document's distance, which is worse than raising.
            for doc, dist, meta in zip(documents, distances, metadatas, strict=True)
            if (1.0 - dist) >= min_similarity
            and float((meta or {}).get("created_at", 0.0)) > cutoff
        ]

    def __len__(self) -> int:
        return self._collection.count()

    def describe(self) -> str:
        return f"{len(self)} note(s) in Chroma collection at {self.path}"


def validate_table_name(table: str) -> str:
    """The one rule for a notes table name, in the one place that owns it.

    Table names are interpolated into DDL and into every query, because
    identifier quoting is not available through psycopg's parameter binding --
    so they must not be attacker-controlled and they are validated rather than
    trusted. The name normally comes from an env var set by whoever runs the
    service; since Phase 13 the migration CLI also takes one from operator
    argv, which is why this moved out of the constructor: two callers, and a
    second hand-typed copy of the rule is how the two drift apart.
    """
    if not table.replace("_", "").isalnum():
        raise ValueError(f"PGVECTOR_TABLE {table!r} must be alphanumeric or underscores.")
    return table


class PgVectorMemoryStore(MemoryStore):
    """Notes in Postgres, retrieved by an indexed cosine search.

    Two things this fixes at once. It is *shared*, so every machine recalls
    everything the agent has learned rather than only what it personally
    wrote. And it is *indexed*: the brute-force stores score every stored note
    on every query, which is exact but O(n) and pulls the whole corpus into
    the agent process. HNSW keeps the same cosine ranking and stops doing
    either.

    Requires the `vector` extension. Most managed Postgres offerings ship it;
    `CREATE EXTENSION` here is a no-op when it already exists.
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        dsn: str | None = None,
        table: str = PGVECTOR_TABLE,
        dimensions: int = VECTOR_DIMENSIONS,
        database: db.Database | None = None,
    ):
        self.embedder = embedder or VoyageEmbedder()
        self.dimensions = dimensions
        self.table = validate_table_name(table)
        self.db = database or db.Database(dsn)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.db.ensure_schema(
            f"""
            CREATE EXTENSION IF NOT EXISTS vector;
            CREATE TABLE IF NOT EXISTS {self.table} (
                id         BIGSERIAL PRIMARY KEY,
                text       TEXT NOT NULL,
                embedding  vector({self.dimensions}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS {self.table}_embedding_hnsw
                ON {self.table} USING hnsw (embedding vector_cosine_ops);
            -- Phase 12. created_at was already here, so only owner is new;
            -- ADD COLUMN IF NOT EXISTS with a default migrates the live rows
            -- in place, under the same advisory lock the rest of the DDL
            -- takes, so both machines can run it and only one does. The two
            -- pre-Phase-12 notes land on '' -- claimed by nobody, since a real
            -- identity is a 32-hex uuid -- and the TTL collects them.
            ALTER TABLE {self.table} ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT '';
            CREATE INDEX IF NOT EXISTS {self.table}_owner ON {self.table} (owner);
            -- Phase 17.5. This is the one schema in the codebase whose table
            -- name is a variable, which is exactly why RLS belongs here rather
            -- than in a runbook: `migrate.py embeddings re-embed --to` creates
            -- a new corpus table on demand, and a one-time manual fix would
            -- protect the old table and silently miss the new one. Notes carry
            -- researched text and the identity that owns them. Rationale in
            -- metrics.py.
            ALTER TABLE {self.table} ENABLE ROW LEVEL SECURITY;
            """
        )

    @staticmethod
    def _literal(vector: Sequence[float]) -> str:
        """pgvector's text input format.

        Formatting the vector by hand rather than taking the `pgvector` python
        package as a dependency: this is the only place a vector crosses the
        boundary, embeddings are never read back, and one fewer dependency in
        the runtime image is worth more than the adapter.
        """
        return "[" + ",".join(repr(float(x)) for x in vector) + "]"

    def _check_dimensions(self, vector: Sequence[float]) -> None:
        if len(vector) != self.dimensions:
            raise ValueError(
                f"Embedder returned {len(vector)} dimensions but the {self.table} column "
                f"is vector({self.dimensions}). Set VECTOR_DIMENSIONS to match the "
                f"embedding model, and note that an existing table keeps its original "
                f"width -- changing model means a new table, not just a new setting."
            )

    def add(self, text: str, owner: str = "") -> None:
        embedding = self.embedder.embed_documents([text])[0]
        self._check_dimensions(embedding)
        # Opportunistic sweep, same shape as the session store's. The interval
        # is bound as a parameter rather than interpolated into the SQL: the
        # TTL comes from an environment variable, and the one other thing this
        # class interpolates (the table name) is validated in __init__ for
        # exactly that reason.
        self.db.execute(
            f"DELETE FROM {self.table} WHERE created_at <= now() - (%s * interval '1 second')",
            (note_ttl_seconds(),),
        )
        self.db.execute(
            f"INSERT INTO {self.table} (text, embedding, owner) VALUES (%s, %s::vector, %s)",
            (text, self._literal(embedding), owner),
        )
        # The count bound. Written as a subquery because Postgres has no
        # ORDER BY / LIMIT / OFFSET on a DELETE target -- that is a MySQL
        # extension, and the natural first draft of "delete the oldest N" is a
        # syntax error here. Newest-first with OFFSET cap keeps exactly the
        # newest `cap` rows and deletes precisely the excess oldest.
        #
        # `id DESC` is not decoration: created_at is a server clock with finite
        # resolution and several notes written in one loop share a value, so
        # the BIGSERIAL -- allocated atomically at insert, monotonic regardless
        # of clock or concurrent writers -- is what makes "oldest" mean the
        # same thing here as list order does in the brute-force stores.
        #
        # Owner and cap are bound; the only interpolation is self.table, which
        # validate_table_name() checked in __init__ for exactly this reason.
        # The three statements are separately autocommitted, deliberately: that
        # is the same non-atomicity the sweep above has always had relative to
        # the insert, and inheriting it is in the threat register rather than
        # being fixed here by wrapping every backend's sweep in a transaction.
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

    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        owner: str = "",
    ) -> list[str]:
        if not len(self):
            return []

        embedding = self.embedder.embed_query(query_text)
        self._check_dimensions(embedding)
        literal = self._literal(embedding)
        # `<=>` is cosine distance, so similarity is 1 - distance. Ordering by
        # the raw operator is what lets the HNSW index serve the query; the
        # relevance floor is applied as a filter on the same expression.
        #
        # The owner and TTL predicates are evaluated by the database, so the
        # expiry line is the *database's* clock -- two machines cannot disagree
        # about what has expired, the same reason the session store computes
        # its cutoff server-side.
        rows = self.db.fetchall(
            f"""
            SELECT text, 1 - (embedding <=> %s::vector) AS similarity
            FROM {self.table}
            WHERE 1 - (embedding <=> %s::vector) >= %s
              AND owner = %s
              AND created_at > now() - (%s * interval '1 second')
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, literal, min_similarity, owner, note_ttl_seconds(), literal, top_k),
        )
        return [row["text"] for row in rows]

    def __len__(self) -> int:
        return self.db.fetchone(f"SELECT COUNT(*) AS n FROM {self.table}")["n"]

    def describe(self) -> str:
        from research_agent.sessions import _describe_dsn

        return f"{len(self)} note(s) in pgvector table {self.table} at {_describe_dsn(self.db.dsn)}"

    def close(self) -> None:
        self.db.close()


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

BACKENDS = {
    "json": JSONMemoryStore,
    "memory": InMemoryStore,
    "chroma": ChromaMemoryStore,
    "pgvector": PgVectorMemoryStore,
}


def default_backend() -> str:
    """pgvector when a Postgres DSN is configured, JSON otherwise.

    Same reasoning as the session store: a deploy that provisions a database
    should get shared notes without a second setting to forget. Forgetting it
    is how two machines end up with two disjoint memories, each recalling
    half of what the agent has learned.
    """
    return os.environ.get("VECTOR_STORE", "").strip().lower() or (
        "pgvector" if db.postgres_configured() else "json"
    )


def get_memory_store(
    backend: str | None = None, *, embedder: Embedder | None = None
) -> MemoryStore:
    """Build the configured store. `backend` defaults to $VECTOR_STORE."""
    name = (backend or default_backend()).strip().lower()
    try:
        cls = BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Unknown VECTOR_STORE {name!r}. Choose one of: {', '.join(sorted(BACKENDS))}."
        ) from None
    return cls(embedder=embedder)


# Backwards-compatible alias: VectorMemory() still means "the file-backed store".
VectorMemory = JSONMemoryStore


if __name__ == "__main__":
    mem = JSONMemoryStore(path=os.path.join(_MODULE_DIR, "test_memory_store.json"))
    mem.add("LangGraph models agents as an explicit state graph.")
    mem.add("CrewAI organizes agents around named roles like researcher and writer.")
    print(mem.query("Which framework uses a graph structure?"))
    print(mem.describe())
