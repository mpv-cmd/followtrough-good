from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = BASE_DIR / "memory"

MEMORY_DIR.mkdir(exist_ok=True)


def _memory_file(workspace: str) -> Path:
    safe_workspace = (workspace or "default").strip() or "default"
    return MEMORY_DIR / f"{safe_workspace}_memory.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_memory() -> Dict[str, Any]:
    return {
        "meetings": [],
        "actions": [],
        "entities": {},
    }


def load_memory(workspace: str) -> Dict[str, Any]:
    f = _memory_file(workspace)

    if not f.exists():
        return _empty_memory()

    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_memory()

        data.setdefault("meetings", [])
        data.setdefault("actions", [])
        data.setdefault("entities", {})
        return data
    except Exception:
        return _empty_memory()


def save_memory(workspace: str, data: Dict[str, Any]) -> None:
    f = _memory_file(workspace)
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def remember_meeting(
    workspace: str,
    transcript: str,
    summary: Dict[str, Any] | str,
    actions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    memory = load_memory(workspace)
    meetings = memory.setdefault("meetings", [])
    stored_actions = memory.setdefault("actions", [])

    meeting_id = len(meetings) + 1

    if isinstance(summary, dict):
        title = summary.get("title") or "Meeting"
    else:
        title = "Meeting"

    meeting_record = {
        "id": meeting_id,
        "title": title,
        "transcript": transcript or "",
        "summary": summary,
        "actions": actions or [],
        "created_at": _utc_now_iso(),
    }

    meetings.append(meeting_record)

    for i, action_item in enumerate(actions or []):
        if not isinstance(action_item, dict):
            continue

        action_text = (action_item.get("action") or "").strip()
        if not action_text:
            continue

        stored_actions.append(
            {
                "meeting_id": meeting_id,
                "index": i,
                "action": action_text,
                "owner": action_item.get("owner"),
                "deadline": action_item.get("deadline"),
                "source_sentence": action_item.get("source_sentence"),
                "confidence": action_item.get("confidence"),
                "created_at": _utc_now_iso(),
            }
        )

    save_memory(workspace, memory)
    return meeting_record


def get_recent_context(workspace: str, limit: int = 5) -> List[Dict[str, Any]]:
    memory = load_memory(workspace)
    meetings = memory.get("meetings", [])

    if not meetings:
        return []

    return meetings[-limit:]


def get_all_actions(workspace: str) -> List[Dict[str, Any]]:
    memory = load_memory(workspace)
    return memory.get("actions", [])