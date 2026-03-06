# =========================
# FILE: backend/semantic_memory.py
# =========================

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

from memory_engine import load_memory

model = SentenceTransformer("all-MiniLM-L6-v2")


def build_index(workspace: str):

    memory = load_memory(workspace)

    meetings = memory.get("meetings", [])

    texts = []
    metadata = []

    for m in meetings:

        transcript = m.get("transcript", "")
        summary = m.get("summary", "")

        if transcript:
            texts.append(transcript)
            metadata.append({"type": "transcript"})

        if summary:
            texts.append(summary)
            metadata.append({"type": "summary"})

    if not texts:
        return None, None

    embeddings = model.encode(texts)

    dim = embeddings.shape[1]

    index = faiss.IndexFlatL2(dim)

    index.add(np.array(embeddings))

    return index, metadata


def semantic_search(workspace: str, query: str, k: int = 3):

    index, metadata = build_index(workspace)

    if index is None:
        return []

    query_vec = model.encode([query])

    distances, ids = index.search(np.array(query_vec), k)

    results = []

    memory = load_memory(workspace)

    meetings = memory.get("meetings", [])

    for idx in ids[0]:

        if idx >= len(meetings):
            continue

        results.append(meetings[idx])

    return results