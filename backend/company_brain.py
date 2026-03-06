# =========================
# FILE: backend/company_brain.py
# =========================
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Tuple


# -------------------------
# Text helpers
# -------------------------
_STOP = {
    "the","a","an","and","or","but","if","then","so","because","as","at","by","for","from","in","into","is","it",
    "of","on","to","we","i","you","they","he","she","this","that","these","those","our","your","their","with","without",
    "are","was","were","be","been","being","will","would","can","could","should","may","might","do","did","done","does",
    "not","no","yes","ok","okay","thanks","thank","please","also","just","like","got","have","has","had","more","less",
    "today","tomorrow","yesterday","week","next","meeting","call","sync","standup","review",
    "monday","tuesday","wednesday","thursday","friday","saturday","sunday",
}

_PERSON_TOKEN = re.compile(r"\b[A-Z][a-z]{2,}\b")
_FALSE_NAMES = {
    "Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday",
    "January","February","March","April","May","June","July","August","September","October","November","December",
    "Google","Calendar","Zoom","Teams","Slack","Notion","Figma","Drive","Docs","Doc",
    "FollowThrough","Action","Actions","Meeting","Meetings","Ok","Okay","Yes","No",
}


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _short(s: str, n: int = 160) -> str:
    s = _norm_ws(s)
    return s if len(s) <= n else (s[: n - 1] + "…")


def _extract_people(text: str) -> List[str]:
    if not text:
        return []

    hits = _PERSON_TOKEN.findall(text)
    cleaned: List[str] = []

    for h in hits:
        if h in _FALSE_NAMES:
            continue
        cleaned.append(h)

    c = Counter(cleaned)
    ranked = [n for n, _ in c.most_common() if c[n] >= 1]

    seen = set()
    out: List[str] = []
    for n in ranked:
        if n not in seen:
            seen.add(n)
            out.append(n)

    return out[:30]


def _extract_topics(text: str) -> List[Tuple[str, int]]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", (text or "").lower())
    words = [w for w in words if w not in _STOP and len(w) <= 24]
    c = Counter(words)
    return c.most_common(20)


def _extract_summary_text(summary: Any) -> str:
    if isinstance(summary, str):
        return summary

    if isinstance(summary, dict):
        parts: List[str] = []

        for key in ("summary", "title", "overview"):
            value = summary.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())

        for key in ("key_points", "decisions", "risks", "insights"):
            value = summary.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        parts.append(item.strip())
                    elif isinstance(item, dict):
                        txt = item.get("text") or item.get("title") or item.get("detail")
                        if isinstance(txt, str) and txt.strip():
                            parts.append(txt.strip())

        return " ".join(parts)

    return _safe_str(summary)


def _extract_meeting_title(summary: Any, fallback: str = "Meeting") -> str:
    if isinstance(summary, dict):
        for key in ("title", "meeting_title", "name"):
            value = summary.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


# -------------------------
# Public API
# -------------------------
def build_company_brain(meetings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    meetings: list of dicts (from memory_engine.get_recent_context)
    expects keys (best-effort): transcript, summary, actions/tasks, decisions
    """

    people: List[str] = []
    decisions: List[str] = []
    tasks: List[Dict[str, Any]] = []
    all_text_parts: List[str] = []

    for idx, m in enumerate(meetings or []):
        if not isinstance(m, dict):
            continue

        raw_summary = m.get("summary")
        transcript = _safe_str(m.get("transcript") or "")
        summary_text = _extract_summary_text(raw_summary)

        meeting_id = m.get("id") or m.get("meeting_id") or f"meeting-{idx + 1}"
        meeting_title = (
            m.get("title")
            or m.get("name")
            or _extract_meeting_title(raw_summary, fallback=f"Meeting {idx + 1}")
        )

        if transcript:
            all_text_parts.append(transcript)
        if summary_text:
            all_text_parts.append(summary_text)

        # People
        people.extend(_extract_people(transcript))
        people.extend(_extract_people(summary_text))

        # Tasks / Actions
        acts = m.get("actions") or m.get("tasks") or []
        if isinstance(acts, list):
            for a in acts:
                if not isinstance(a, dict):
                    continue

                action_text = _norm_ws(_safe_str(a.get("action") or a.get("title") or ""))
                if not action_text:
                    continue

                source_sentence = _safe_str(
                    a.get("source_sentence")
                    or a.get("source")
                    or ""
                )

                tasks.append({
                    "action": action_text,
                    "owner": a.get("owner"),
                    "deadline": a.get("deadline"),
                    "confidence": a.get("confidence"),
                    "source": _short(source_sentence) if source_sentence else "",
                    "meeting_id": meeting_id,
                    "meeting_title": meeting_title,
                })

        # Decisions
        decs = m.get("decisions") or []
        if isinstance(decs, list):
            for d in decs:
                if isinstance(d, str):
                    s = _short(d)
                    if s:
                        decisions.append(s)
                elif isinstance(d, dict):
                    s = _short(_safe_str(d.get("decision") or d.get("text") or ""))
                    if s:
                        decisions.append(s)

        # Fallback signal from transcript
        low = transcript.lower()
        if ("we decided" in low) or ("we agreed" in low) or ("decision:" in low):
            t = _short(transcript)
            if t:
                decisions.append(t)

    # De-dupe people
    ppl_seen = set()
    people_unique: List[str] = []
    for p in people:
        p2 = _norm_ws(_safe_str(p))
        if not p2:
            continue
        if p2 in ppl_seen:
            continue
        ppl_seen.add(p2)
        people_unique.append(p2)

    # De-dupe decisions
    dec_seen = set()
    decisions_unique: List[str] = []
    for d in decisions:
        d2 = _norm_ws(_safe_str(d))
        if not d2:
            continue
        k = d2.lower()
        if k in dec_seen:
            continue
        dec_seen.add(k)
        decisions_unique.append(d2)

    # Topics
    all_text = "\n".join([t for t in all_text_parts if t])
    topics = _extract_topics(all_text)

    # -------------------------
    # Build graph with strict uniqueness
    # -------------------------
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    edges_set = set()
    edges: List[Dict[str, Any]] = []

    def add_node(node_id: str, kind: str, label: Any, meta: Dict[str, Any] | None = None):
        if not node_id:
            return

        label_str = _safe_str(label) or node_id

        if node_id in nodes_by_id:
            if meta:
                nodes_by_id[node_id].setdefault("meta", {})
                for k, v in meta.items():
                    if k not in nodes_by_id[node_id]["meta"] and v is not None:
                        nodes_by_id[node_id]["meta"][k] = v
            return

        nodes_by_id[node_id] = {
            "id": node_id,
            "kind": kind,
            "label": label_str,
            "meta": meta or {},
        }

    def add_edge(src: str, rel: str, dst: str, meta: Dict[str, Any] | None = None):
        if not src or not dst or not rel:
            return

        key = (src, rel, dst)
        if key in edges_set:
            return

        edges_set.add(key)
        edges.append({
            "src": src,
            "rel": rel,
            "dst": dst,
            "meta": meta or {},
        })

    # Base nodes
    add_node("team:all", "team", "Team")

    for p in people_unique[:30]:
        add_node(f"person:{p}", "person", p)

    for w, c in topics[:20]:
        add_node(f"topic:{w}", "topic", w, {"count": c})

    # Task nodes + links
    for i, t in enumerate(tasks[:80]):
        tid = f"task:{i}"
        task_label = _safe_str(t.get("action"))

        add_node(
            tid,
            "task",
            task_label,
            {
                "owner": t.get("owner"),
                "deadline": t.get("deadline"),
                "confidence": t.get("confidence"),
                "source": t.get("source"),
                "meeting_id": t.get("meeting_id"),
                "meeting_title": t.get("meeting_title"),
            },
        )

        owner = t.get("owner")
        if isinstance(owner, str) and owner.strip():
            on = owner.strip()
            add_node(f"person:{on}", "person", on)
            add_edge(f"person:{on}", "owns", tid)

        deadline = t.get("deadline")
        if deadline:
            did = f"date:{deadline}"
            add_node(did, "date", str(deadline))
            add_edge(tid, "due", did)

        text = task_label.lower()
        for w, _c in topics[:20]:
            if w in text:
                add_edge(tid, "mentions", f"topic:{w}")

    # Decision nodes + links
    for i, d in enumerate(decisions_unique[:40]):
        did = f"decision:{i}"
        add_node(did, "decision", d)
        add_edge("team:all", "decided", did)

        text = _safe_str(d).lower()
        for w, _c in topics[:20]:
            if w in text:
                add_edge(did, "mentions", f"topic:{w}")

    # Project nodes from top topics
    for w, c in topics[:8]:
        pid = f"project:{w}"
        add_node(pid, "project", w.title(), {"count": c})
        add_edge(pid, "about", f"topic:{w}")

        for nid, n in list(nodes_by_id.items()):
            if n["kind"] not in ("task", "decision"):
                continue

            label = _safe_str(n.get("label"))
            if w in label.lower():
                add_edge(nid, "relates_to", pid)

    nodes = list(nodes_by_id.values())

    summary = {
        "people_count": len(people_unique),
        "task_count": len(tasks),
        "decision_count": len(decisions_unique),
        "top_topics": [w for w, _ in topics[:10]],
    }

    return {
        "summary": summary,
        "people": people_unique[:30],
        "tasks": tasks[:80],
        "decisions": decisions_unique[:40],
        "topics": [{"topic": w, "count": c} for w, c in topics[:20]],
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
    }