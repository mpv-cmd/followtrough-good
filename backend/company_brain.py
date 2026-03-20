from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Tuple


_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "because", "as", "at", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "to", "we", "i", "you", "they", "he", "she", "this", "that", "these", "those", "our",
    "your", "their", "with", "without", "are", "was", "were", "be", "been", "being", "will", "would", "can", "could",
    "should", "may", "might", "do", "did", "done", "does", "not", "no", "yes", "ok", "okay", "thanks", "thank",
    "please", "also", "just", "like", "got", "have", "has", "had", "more", "less", "today", "tomorrow", "yesterday",
    "week", "next", "meeting", "call", "sync", "standup", "review", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
}

_PERSON_TOKEN = re.compile(r"\b[A-Z][a-z]{2,}\b")
_FALSE_NAMES = {
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
    "Google", "Calendar", "Zoom", "Teams", "Slack", "Notion", "Figma", "Drive", "Docs", "Doc",
    "FollowThrough", "Action", "Actions", "Meeting", "Meetings", "Ok", "Okay", "Yes", "No",
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

    counts = Counter(cleaned)
    ranked = [name for name, _ in counts.most_common()]

    seen = set()
    out: List[str] = []

    for name in ranked:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)

    return out[:30]


def _extract_topics(text: str) -> List[Tuple[str, int]]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", (text or "").lower())
    words = [w for w in words if w not in _STOP and len(w) <= 24]
    counts = Counter(words)
    return counts.most_common(20)


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


def build_company_brain(meetings: List[Dict[str, Any]]) -> Dict[str, Any]:
    people: List[str] = []
    decisions: List[str] = []
    tasks: List[Dict[str, Any]] = []
    all_text_parts: List[str] = []

    for idx, meeting in enumerate(meetings or []):
        if not isinstance(meeting, dict):
            continue

        raw_summary = meeting.get("summary")
        transcript = _safe_str(meeting.get("transcript") or "")
        summary_text = _extract_summary_text(raw_summary)

        meeting_id = meeting.get("id") or meeting.get("meeting_id") or f"meeting-{idx + 1}"
        meeting_title = (
            meeting.get("title")
            or meeting.get("name")
            or _extract_meeting_title(raw_summary, fallback=f"Meeting {idx + 1}")
        )

        if transcript:
            all_text_parts.append(transcript)
        if summary_text:
            all_text_parts.append(summary_text)

        people.extend(_extract_people(transcript))
        people.extend(_extract_people(summary_text))

        acts = meeting.get("actions") or meeting.get("tasks") or []
        if isinstance(acts, list):
            for action in acts:
                if not isinstance(action, dict):
                    continue

                action_text = _norm_ws(_safe_str(action.get("action") or action.get("title") or ""))
                if not action_text:
                    continue

                source_sentence = _safe_str(action.get("source_sentence") or action.get("source") or "")

                tasks.append(
                    {
                        "action": action_text,
                        "owner": action.get("owner"),
                        "deadline": action.get("deadline"),
                        "confidence": action.get("confidence"),
                        "source": _short(source_sentence) if source_sentence else "",
                        "meeting_id": meeting_id,
                        "meeting_title": meeting_title,
                    }
                )

        decs = meeting.get("decisions") or []
        if isinstance(decs, list):
            for decision in decs:
                if isinstance(decision, str):
                    text = _short(decision)
                    if text:
                        decisions.append(text)
                elif isinstance(decision, dict):
                    text = _short(_safe_str(decision.get("decision") or decision.get("text") or ""))
                    if text:
                        decisions.append(text)

        low = transcript.lower()
        if ("we decided" in low) or ("we agreed" in low) or ("decision:" in low):
            text = _short(transcript)
            if text:
                decisions.append(text)

    people_unique: List[str] = []
    people_seen = set()
    for person in people:
        person_clean = _norm_ws(_safe_str(person))
        if not person_clean or person_clean in people_seen:
            continue
        people_seen.add(person_clean)
        people_unique.append(person_clean)

    decisions_unique: List[str] = []
    decisions_seen = set()
    for decision in decisions:
        decision_clean = _norm_ws(_safe_str(decision))
        if not decision_clean:
            continue
        key = decision_clean.lower()
        if key in decisions_seen:
            continue
        decisions_seen.add(key)
        decisions_unique.append(decision_clean)

    all_text = "\n".join([text for text in all_text_parts if text])
    topics = _extract_topics(all_text)

    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    edges_set = set()
    edges: List[Dict[str, Any]] = []

    def add_node(node_id: str, kind: str, label: Any, meta: Dict[str, Any] | None = None) -> None:
        if not node_id:
            return

        label_str = _safe_str(label) or node_id

        if node_id in nodes_by_id:
            if meta:
                nodes_by_id[node_id].setdefault("meta", {})
                for key, value in meta.items():
                    if key not in nodes_by_id[node_id]["meta"] and value is not None:
                        nodes_by_id[node_id]["meta"][key] = value
            return

        nodes_by_id[node_id] = {
            "id": node_id,
            "kind": kind,
            "label": label_str,
            "meta": meta or {},
        }

    def add_edge(src: str, rel: str, dst: str, meta: Dict[str, Any] | None = None) -> None:
        if not src or not rel or not dst:
            return

        key = (src, rel, dst)
        if key in edges_set:
            return

        edges_set.add(key)
        edges.append(
            {
                "src": src,
                "rel": rel,
                "dst": dst,
                "meta": meta or {},
            }
        )

    add_node("team:all", "team", "Team")

    for person in people_unique[:30]:
        add_node(f"person:{person}", "person", person)

    for topic, count in topics[:20]:
        add_node(f"topic:{topic}", "topic", topic, {"count": count})

    for i, task in enumerate(tasks[:80]):
        task_id = f"task:{i}"
        task_label = _safe_str(task.get("action"))

        add_node(
            task_id,
            "task",
            task_label,
            {
                "owner": task.get("owner"),
                "deadline": task.get("deadline"),
                "confidence": task.get("confidence"),
                "source": task.get("source"),
                "meeting_id": task.get("meeting_id"),
                "meeting_title": task.get("meeting_title"),
            },
        )

        owner = task.get("owner")
        if isinstance(owner, str) and owner.strip():
            owner_name = owner.strip()
            add_node(f"person:{owner_name}", "person", owner_name)
            add_edge(f"person:{owner_name}", "owns", task_id)

        deadline = task.get("deadline")
        if deadline:
            date_id = f"date:{deadline}"
            add_node(date_id, "date", str(deadline))
            add_edge(task_id, "due", date_id)

        task_text = task_label.lower()
        for topic, _count in topics[:20]:
            if topic in task_text:
                add_edge(task_id, "mentions", f"topic:{topic}")

    for i, decision in enumerate(decisions_unique[:40]):
        decision_id = f"decision:{i}"
        add_node(decision_id, "decision", decision)
        add_edge("team:all", "decided", decision_id)

        decision_text = decision.lower()
        for topic, _count in topics[:20]:
            if topic in decision_text:
                add_edge(decision_id, "mentions", f"topic:{topic}")

    for topic, count in topics[:8]:
        project_id = f"project:{topic}"
        add_node(project_id, "project", topic.title(), {"count": count})
        add_edge(project_id, "about", f"topic:{topic}")

        for node_id, node in list(nodes_by_id.items()):
            if node["kind"] not in ("task", "decision"):
                continue

            label = _safe_str(node.get("label"))
            if topic in label.lower():
                add_edge(node_id, "relates_to", project_id)

    nodes = list(nodes_by_id.values())

    summary = {
        "people_count": len(people_unique),
        "task_count": len(tasks),
        "decision_count": len(decisions_unique),
        "top_topics": [topic for topic, _ in topics[:10]],
    }

    return {
        "summary": summary,
        "people": people_unique[:30],
        "tasks": tasks[:80],
        "decisions": decisions_unique[:40],
        "topics": [{"topic": topic, "count": count} for topic, count in topics[:20]],
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
    }