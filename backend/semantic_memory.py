# =========================
# FILE: backend/semantic_memory.py
# Optimized Cloud Version
# =========================

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import threading

from memory_engine import load_memory

# ----------------------------------------------------
# GLOBALS
# ----------------------------------------------------

_model = None
_index = None
_metadata = None
_workspace_loaded = None
_lock = threading.Lock()


# ----------------------------------------------------
# LOAD MODEL (LAZY)
# ----------------------------------------------------
def get_model():

    global _model

    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")

    return _model


# ----------------------------------------------------
# BUILD INDEX
# ----------------------------------------------------
def build_index(workspace: str):

    global _index
    global _metadata
    global _workspace_loaded

    with _lock:

        memory = load_memory(workspace)
        meetings = memory.get("meetings", [])

        texts = []
        metadata = []

        for i, m in enumerate(meetings):

            transcript = m.get("transcript", "")
            summary = m.get("summary", "")

            if transcript:
                texts.append(transcript)
                metadata.append({"meeting_index": i, "type": "transcript"})

            if summary:
                texts.append(summary)
                metadata.append({"meeting_index": i, "type": "summary"})

        if not texts:
            _index = None
            _metadata = None
            return

        model = get_model()

        embeddings = model.encode(texts, normalize_embeddings=True)

        dim = embeddings.shape[1]

        index = faiss.IndexFlatIP(dim)

        index.add(np.array(embeddings))

        _index = index
        _metadata = metadata
        _workspace_loaded = workspace


# ----------------------------------------------------
# ENSURE INDEX
# ----------------------------------------------------
def ensure_index(workspace: str):

    global _workspace_loaded

    if _workspace_loaded != workspace:
        build_index(workspace)


# ----------------------------------------------------
# SEARCH
# ----------------------------------------------------
def semantic_search(workspace: str, query: str, k: int = 5):

    ensure_index(workspace)

    if _index is None:
        return []

    model = get_model()

    query_vec = model.encode([query], normalize_embeddings=True)

    distances, ids = _index.search(np.array(query_vec), k)

    memory = load_memory(workspace)
    meetings = memory.get("meetings", [])

    results = []

    seen = set()

    for idx in ids[0]:

        if idx < 0 or idx >= len(_metadata):
            continue

        meeting_index = _metadata[idx]["meeting_index"]

        if meeting_index in seen:
            continue

        seen.add(meeting_index)

        if meeting_index < len(meetings):
            results.append(meetings[meeting_index])

    return results


# ----------------------------------------------------
# REBUILD INDEX (WHEN NEW MEETING SAVED)
# ----------------------------------------------------
def refresh_index(workspace: str):

    build_index(workspace)