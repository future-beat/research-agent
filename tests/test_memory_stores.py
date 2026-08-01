"""
Backend tests. A fake embedder replaces Voyage, so these assert the store's
own behaviour -- ranking, thresholds, persistence -- rather than the quality
of somebody else's embedding model.
"""

import json

import pytest

import vector_memory
from vector_memory import (
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


def test_factory_defaults_to_json(monkeypatch, embedder):
    monkeypatch.delenv("VECTOR_STORE", raising=False)
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
    """research_agent must never reach past add/query/len/describe -- that is
    the entire premise of the store being swappable."""
    import inspect

    import research_agent

    source = inspect.getsource(research_agent)
    for leak in ("memory().entries", "memory().path", "_memory.entries"):
        assert leak not in source, f"{leak} bypasses the MemoryStore interface"


def test_vector_memory_alias_still_points_at_the_json_store():
    """Kept so existing callers and docs don't break."""
    assert vector_memory.VectorMemory is JSONMemoryStore
