"""
Backend tests. A fake embedder replaces Voyage, so these assert the store's
own behaviour -- ranking, thresholds, persistence -- rather than the quality
of somebody else's embedding model.
"""

import json

import pytest

from research_agent import graph
from research_agent import memory as vector_memory
from research_agent import usage as usage_accounting
from research_agent.memory import (
    InMemoryStore,
    JSONMemoryStore,
    MemoryStore,
    get_memory_store,
)


class FakeEmbedder:
    """Maps text to a deterministic vector via a keyword bag, so similarity is
    predictable: documents sharing words score high, unrelated ones score 0."""

    VOCAB = ["langgraph", "chroma", "retry", "voyage", "supervisor"]

    def __init__(self):
        self.documents_embedded = 0
        self.queries_embedded = 0

    def _vector(self, text: str) -> list[float]:
        words = text.lower().split()
        vec = [float(word in words) for word in self.VOCAB]
        return vec if any(vec) else [0.0] * (len(self.VOCAB) - 1) + [1e-6]

    def embed_documents(self, texts):
        self.documents_embedded += len(texts)
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        self.queries_embedded += 1
        return self._vector(text)


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture(params=["memory", "json"])
def store(request, embedder, tmp_path) -> MemoryStore:
    """Every behavioural test runs against both brute-force backends: the
    contract is supposed to be identical."""
    if request.param == "memory":
        return InMemoryStore(embedder=embedder)
    return JSONMemoryStore(path=str(tmp_path / "store.json"), embedder=embedder)


# --------------------------------------------------------------------------
# The shared contract
# --------------------------------------------------------------------------


def test_empty_store_returns_nothing_and_never_embeds(store, embedder):
    assert store.query("langgraph") == []
    assert len(store) == 0
    assert embedder.queries_embedded == 0  # no API call for a store we know is empty


def test_add_then_recall(store):
    store.add("langgraph supervisor pattern")
    assert store.query("langgraph") == ["langgraph supervisor pattern"]
    assert len(store) == 1


def test_results_come_back_most_similar_first(store):
    store.add("chroma")
    store.add("langgraph supervisor")
    store.add("langgraph supervisor retry")

    results = store.query("langgraph supervisor retry", top_k=3, min_similarity=0.0)
    assert results[0] == "langgraph supervisor retry"
    assert results[-1] == "chroma"


def test_top_k_limits_the_result_count(store):
    for text in ("langgraph", "langgraph retry", "langgraph voyage", "langgraph chroma"):
        store.add(text)
    assert len(store.query("langgraph", top_k=2, min_similarity=0.0)) == 2


def test_similarity_floor_keeps_unrelated_notes_out(store):
    """The floor is what stops a past task about something else leaking into
    the current one -- top_k alone would always return *something*."""
    store.add("chroma voyage")
    store.add("langgraph supervisor")

    assert store.query("langgraph", min_similarity=0.3) == ["langgraph supervisor"]


def test_floor_of_zero_lets_everything_through(store):
    store.add("chroma voyage")
    assert store.query("langgraph", min_similarity=0.0) == ["chroma voyage"]


def test_describe_reports_the_count(store):
    store.add("langgraph")
    assert "1 note(s)" in store.describe()


# --------------------------------------------------------------------------
# JSON backend specifics
# --------------------------------------------------------------------------


def test_json_store_survives_a_restart(tmp_path, embedder):
    path = str(tmp_path / "store.json")
    JSONMemoryStore(path=path, embedder=embedder).add("langgraph supervisor")

    reopened = JSONMemoryStore(path=path, embedder=embedder)
    assert len(reopened) == 1
    assert reopened.query("langgraph") == ["langgraph supervisor"]


def test_json_store_writes_text_and_embedding(tmp_path, embedder):
    path = tmp_path / "store.json"
    JSONMemoryStore(path=str(path), embedder=embedder).add("langgraph")

    entries = json.loads(path.read_text())
    assert entries[0]["text"] == "langgraph"
    assert len(entries[0]["embedding"]) == len(FakeEmbedder.VOCAB)


def test_json_store_starts_empty_when_the_file_is_absent(tmp_path, embedder):
    assert len(JSONMemoryStore(path=str(tmp_path / "nope.json"), embedder=embedder)) == 0


def test_json_store_leaves_no_temp_file_behind(tmp_path, embedder):
    """Saves go through a temp file and an atomic rename so an interrupted
    write can't truncate an existing store."""
    JSONMemoryStore(path=str(tmp_path / "store.json"), embedder=embedder).add("langgraph")
    assert [p.name for p in tmp_path.iterdir()] == ["store.json"]


def test_in_memory_store_persists_nothing(tmp_path, embedder, monkeypatch):
    monkeypatch.chdir(tmp_path)
    InMemoryStore(embedder=embedder).add("langgraph")
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# Backend selection
# --------------------------------------------------------------------------


def test_factory_defaults_to_json_with_no_configuration(monkeypatch, embedder):
    """JSON is the default only when nothing is configured at all.

    DATABASE_URL has to be cleared too: since Phase 8 the default follows it,
    so leaving it set here asserted the wrong contract and failed the moment
    CI grew a Postgres service. The DATABASE_URL-driven default is covered in
    tests/test_store_contract.py.
    """
    monkeypatch.delenv("VECTOR_STORE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert isinstance(get_memory_store(embedder=embedder), JSONMemoryStore)


def test_factory_reads_the_environment(monkeypatch, embedder):
    monkeypatch.setenv("VECTOR_STORE", "memory")
    assert isinstance(get_memory_store(embedder=embedder), InMemoryStore)


def test_explicit_argument_beats_the_environment(monkeypatch, embedder):
    monkeypatch.setenv("VECTOR_STORE", "json")
    assert isinstance(get_memory_store("memory", embedder=embedder), InMemoryStore)


@pytest.mark.parametrize("spec", ["MEMORY", " memory "])
def test_backend_names_are_forgiving(spec, embedder):
    assert isinstance(get_memory_store(spec, embedder=embedder), InMemoryStore)


def test_unknown_backend_fails_loudly_and_lists_the_options(embedder):
    with pytest.raises(ValueError, match="chroma"):
        get_memory_store("pinecone", embedder=embedder)


def test_every_backend_implements_the_contract():
    """Adding a backend without implementing add/query is caught here, not in
    production at the first recall."""
    for name, cls in vector_memory.BACKENDS.items():
        assert issubclass(cls, MemoryStore), name
        assert not getattr(cls, "__abstractmethods__", None), name


def test_the_graph_only_uses_the_abstract_interface():
    """graph must never reach past add/query/len/describe -- that is
    the entire premise of the store being swappable."""
    import inspect


    source = inspect.getsource(graph)
    for leak in ("memory().entries", "memory().path", "_memory.entries"):
        assert leak not in source, f"{leak} bypasses the MemoryStore interface"


def test_vector_memory_alias_still_points_at_the_json_store():
    """Kept so existing callers and docs don't break."""
    assert vector_memory.VectorMemory is JSONMemoryStore


# --------------------------------------------------------------------------
# The Voyage seam: what it was billed for
# --------------------------------------------------------------------------


class FakeEmbeddingsObject:
    """Voyage's `EmbeddingsObject`: vectors, and the count they were billed at.

    The second field is the point. The wrapper used to return `.embeddings`
    and drop `.total_tokens` on the floor, which is how an entire provider
    stayed off the cost report.
    """

    def __init__(self, embeddings, total_tokens):
        self.embeddings = embeddings
        self.total_tokens = total_tokens


class FakeVoyageClient:
    def __init__(self, total_tokens=25, error=None):
        self.total_tokens = total_tokens
        # A provider that refuses. None means "behaves exactly as it always
        # did", so every existing caller's requests stay byte-identical.
        self.error = error
        self.calls = []

    def embed(self, texts, model=None, input_type=None, output_dimension=None):
        self.calls.append((list(texts), input_type))
        if self.error is not None:
            raise self.error
        return FakeEmbeddingsObject([[0.1, 0.2]] * len(texts), self.total_tokens)


def voyage_embedder(total_tokens=25, error=None):
    """A VoyageEmbedder wired to a fake client. `_client` is set directly so
    the lazy `client` property never imports voyageai or reads an API key."""
    embedder = vector_memory.VoyageEmbedder(model="voyage-3.5")
    embedder._client = FakeVoyageClient(total_tokens=total_tokens, error=error)
    return embedder


def test_voyage_tokens_captured_at_the_seam():
    """Both embed methods report what they were billed for, to whoever asked.

    25 tokens twice is 50, and the model name travels with them: pricing is
    per model, and a meter that knew the count but not the rate card row would
    be counting in a unit it could not convert.
    """
    embedder = voyage_embedder(total_tokens=25)

    with usage_accounting.embedding_meter() as meter:
        assert embedder.embed_documents(["a note worth keeping"]) == [[0.1, 0.2]]
        assert embedder.embed_query("what did we learn?") == [0.1, 0.2]

    assert meter.total_tokens == 50
    assert meter.requests == 2
    assert meter.model == "voyage-3.5"
    # And the seam still passes the request through unchanged.
    assert [input_type for _, input_type in embedder._client.calls] == ["document", "query"]


def test_the_seam_reports_into_nothing_when_no_one_is_metering():
    """The REPL, the migration CLI and the eval harness all embed outside any
    meter. Reporting has to cost them nothing and raise nothing -- which is the
    whole reason the count travels out of band instead of through the
    `Embedder` protocol's return type."""
    embedder = voyage_embedder(total_tokens=25)

    assert embedder.embed_documents(["a note"]) == [[0.1, 0.2]]
    assert embedder.embed_query("a question") == [0.1, 0.2]


def test_a_zero_token_report_is_still_a_request():
    """Phase 13's live finding, at the seam rather than at the fold: Voyage
    reported 0 tokens for a one-word document and returned a valid embedding.
    The call still happened, so the meter still counts it."""
    embedder = voyage_embedder(total_tokens=0)

    with usage_accounting.embedding_meter() as meter:
        embedder.embed_documents(["hi"])

    assert (meter.total_tokens, meter.requests) == (0, 1)
