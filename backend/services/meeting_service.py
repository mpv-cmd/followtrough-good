# =========================
# FILE: backend/services/meeting_service.py
# =========================

from typing import Dict, Any

from memory_engine import remember_meeting, get_recent_context
from company_brain import build_company_brain

from transcribe import transcribe_file
from summarize_meeting import summarize_meeting
from extract_action import extract_actions


def process_meeting(workspace: str, audio_path: str) -> Dict[str, Any]:

    result = process_meeting(workspace, path)

    transcript = result["transcript"]
    summary = result["summary"]
    actions = result["actions"]

    remember_meeting(
        workspace=workspace,
        transcript=transcript,
        summary=summary,
        actions=actions
    )

    return {
        "transcript": transcript,
        "summary": summary,
        "actions": actions
    }


def build_workspace_brain(workspace: str):

    meetings = get_recent_context(workspace)

    brain = build_company_brain(meetings)

    return brain


def analyze_latest_meeting(workspace: str):

    meetings = get_recent_context(workspace)

    if not meetings:
        return None

    latest = meetings[-1]

    return {
        "transcript": latest.get("transcript"),
        "summary": latest.get("summary"),
        "actions": latest.get("actions")
    }