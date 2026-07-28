"""
Real long-term memory: embeddings via Voyage AI, persisted to disk as JSON,
retrieved by cosine similarity.

Requires: pip install voyageai
Requires: VOYAGE_API_KEY set in your environment (separate from your
Anthropic key -- get one at https://www.voyageai.com/)
"""

import json
import os
import numpy as np
import voyageai

EMBEDDING_MODEL = "voyage-3.5"

# Anchored to this file's directory, not the working directory, so the store
# is the same one no matter where you launch from. A relative default would
# silently create a second, empty store when run from elsewhere.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(_MODULE_DIR, "agent_memory_store.json")

voyage_client = voyageai.Client()  # reads VOYAGE_API_KEY from environment


class VectorMemory:
    """
    A minimal persisted vector store.

    Structure on disk: a JSON list of {"text": str, "embedding": [float, ...]}
    In production you'd swap this file-backed store for a real vector DB
    (Pinecone, Chroma, Weaviate) -- the add()/query() interface stays the same.
    """

    def __init__(self, path: str = STORE_PATH):
        self.path = path
        self.entries = self._load()

    def _load(self) -> list:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.entries, f)

    def add(self, text: str):
        """Embed and persist a new fact/note."""
        result = voyage_client.embed([text], model=EMBEDDING_MODEL, input_type="document")
        embedding = result.embeddings[0]
        self.entries.append({"text": text, "embedding": embedding})
        self._save()

    def query(self, query_text: str, top_k: int = 3, min_similarity: float = 0.3) -> list[str]:
        """Retrieve the most relevant stored texts for a query."""
        if not self.entries:
            return []

        result = voyage_client.embed([query_text], model=EMBEDDING_MODEL, input_type="query")
        query_vec = np.array(result.embeddings[0])

        scored = []
        for entry in self.entries:
            vec = np.array(entry["embedding"])
            sim = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
            scored.append((sim, entry["text"]))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [text for sim, text in scored[:top_k] if sim >= min_similarity]


if __name__ == "__main__":
    mem = VectorMemory(path=os.path.join(_MODULE_DIR, "test_memory_store.json"))
    mem.add("LangGraph models agents as an explicit state graph.")
    mem.add("CrewAI organizes agents around named roles like researcher and writer.")
    results = mem.query("Which framework uses a graph structure?")
    print(results)
