from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend import db
from backend.company_brain import build_company_brain
from backend.extract_action import extract_actions
from backend.memory_engine import get_recent_context, remember_meeting
from backend.semantic_memory import refresh_index
from backend.summarize_meeting import summarize_meeting
from backend.transcribe import transcribe_file


def process_meeting(
    workspace: str,
    audio_path: str,
    upload_id: Optional[str] = None,
) -> Dict[str, Any]:
    workspace = (workspace or "default").strip() or "default"

    if upload_id:
        db.set_upload_status(upload_id, "processing")

    try:
        transcript = transcribe_file(audio_path)
        summary = summarize_meeting(transcript)
        actions = extract_actions(transcript)

        remember_meeting(
            workspace=workspace,
            transcript=transcript,
            summary=summary,
            actions=actions,
        )

        try:
            refresh_index(workspace)
        except Exception:
            pass

        result = {
            "transcript": transcript,
            "summary": summary,
            "actions": actions,
        }

        if upload_id:
            db.save_upload_result(
                upload_id=upload_id,
                transcript=transcript,
                summary_json=json.dumps(summary or {}, ensure_ascii=False),
                actions=actions,
            )

        return result

    except Exception as e:
        if upload_id:
            db.set_upload_status(upload_id, "failed", str(e))
        raise


def build_workspace_brain(workspace: str) -> Any:
    workspace = (workspace or "default").strip() or "default"
    meetings = get_recent_context(workspace, limit=20)
    return build_company_brain(meetings)


def analyze_latest_meeting(workspace: str) -> Optional[Dict[str, Any]]:
    workspace = (workspace or "default").strip() or "default"
    meetings = get_recent_context(workspace, limit=1)

    if not meetings:
        return None

    latest = meetings[0]

    return {
        "transcript": latest.get("transcript"),
        "summary": latest.get("summary"),
        "actions": latest.get("actions"),
    }