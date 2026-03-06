# backend/memory_engine.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any


BASE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = BASE_DIR / "memory"

MEMORY_DIR.mkdir(exist_ok=True)


def _memory_file(workspace: str) -> Path:
    return MEMORY_DIR / f"{workspace}_memory.json"


def load_memory(workspace: str) -> Dict:

    f = _memory_file(workspace)

    if not f.exists():
        return {
            "meetings": [],
            "actions": [],
            "entities": {}
        }

    try:
        return json.loads(f.read_text())
    except Exception:
        return {
            "meetings": [],
            "actions": [],
            "entities": {}
        }


def save_memory(workspace: str, data: Dict):

    f = _memory_file(workspace)

    f.write_text(json.dumps(data, indent=2))


def remember_meeting(
    workspace: str,
    transcript: str,
    summary: Dict,
    actions: List[Dict],
):

    memory = load_memory(workspace)

    memory["meetings"].append({
        "id": len(memory["meetings"]) + 1,
        "title": summary.get("title") if isinstance(summary, dict) else "Meeting",
        "transcript": transcript,
        "summary": summary,
        "actions": actions
    })

    for a in actions:

        action = a.get("action")

        if action:
            memory["actions"].append(action)

    save_memory(workspace, memory)


def get_recent_context(workspace: str, limit: int = 5):

    memory = load_memory(workspace)

    meetings = memory.get("meetings", [])

    if not meetings:
        return []

    return meetings[-limit:]