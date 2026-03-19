# =========================
# FILE: backend/services/meeting_service.py
# =========================

from typing import Dict, Any

from backend.memory_engine import remember_meeting, get_recent_context
from backend.company_brain import build_company_brain

from backend.transcribe import transcribe_file
from backend.summarize_meeting import summarize_meeting
from backend.extract_action import extract_actions


def process_meeting(workspace: str, audio_path: str) -> Dict[str, Any]:

    # 1️⃣ Transcribe audio
    transcript = transcribe_file(audio_path)

    # 2️⃣ Generate summary
    summary = summarize_meeting(transcript)

    # 3️⃣ Extract actions
    actions = extract_actions(transcript)

    # 4️⃣ Store in memory
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
