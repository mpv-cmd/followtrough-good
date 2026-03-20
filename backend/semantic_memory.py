from __future__ import annotations

import threading
from typing import Any, Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.memory_engine import load_memory

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

    workspace = (workspace or "default").strip() or "default"

    with _lock:
        memory = load_memory(workspace)
        meetings = memory.get("meetings", [])

        texts: List[str] = []
        metadata: List[Dict[str, Any]] = []

        for i, m in enumerate(meetings):
            transcript = m.get("transcript", "") or ""
            summary = m.get("summary", "")

            if isinstance(summary, dict):
                summary_text = summary.get("summary") or summary.get("title") or str(summary)
            else:
                summary_text = str(summary) if summary else ""

            if transcript.strip():
                texts.append(transcript)
                metadata.append({"meeting_index": i, "type": "transcript"})

            if summary_text.strip():
                texts.append(summary_text)
                metadata.append({"meeting_index": i, "type": "summary"})

        if not texts:
            _index = None
            _metadata = []
            _workspace_loaded = workspace
            return

        model = get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype="float32")

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        _index = index
        _metadata = metadata
        _workspace_loaded = workspace


# ----------------------------------------------------
# ENSURE INDEX
# ----------------------------------------------------
def ensure_index(workspace: str):
    global _workspace_loaded

    workspace = (workspace or "default").strip() or "default"

    if _workspace_loaded != workspace:
        build_index(workspace)


# ----------------------------------------------------
# SEARCH
# ----------------------------------------------------
def semantic_search(workspace: str, query: str, k: int = 5):
    workspace = (workspace or "default").strip() or "default"
    query = (query or "").strip()

    if not query:
        return []

    ensure_index(workspace)

    if _index is None or not _metadata:
        return []

    model = get_model()
    query_vec = model.encode([query], normalize_embeddings=True)
    query_vec = np.array(query_vec, dtype="float32")

    top_k = min(k, len(_metadata))
    distances, ids = _index.search(query_vec, top_k)

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

        if 0 <= meeting_index < len(meetings):
            results.append(meetings[meeting_index])

    return results


# ----------------------------------------------------
# REBUILD INDEX (WHEN NEW MEETING SAVED)
# ----------------------------------------------------
def refresh_index(workspace: str):
    build_index(workspace)