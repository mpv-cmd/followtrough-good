from __future__ import annotations

import json

from fastapi import APIRouter, Query

from backend import db
from backend.company_brain import build_company_brain
from backend.memory_engine import get_recent_context

router = APIRouter(tags=["Dashboard"])


def _safe_workspace(workspace: str | None) -> str:
    return (workspace or "default").strip() or "default"


def _parse_summary(raw_summary: str | None):
    if not raw_summary:
        return None

    try:
        return json.loads(raw_summary)
    except Exception:
        return raw_summary


@router.get("/dashboard")
def dashboard(workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)

    upload_id = db.latest_upload_id(workspace)
    if not upload_id:
        return {
            "success": True,
            "workspace": workspace,
            "latest_upload": None,
            "summary": None,
            "transcript": None,
            "actions": [],
            "message": "No uploads yet",
        }

    upload = db.get_upload_status(workspace, upload_id)
    actions = db.get_actions(upload_id)

    summary = _parse_summary(upload.get("summary_json"))
    transcript = upload.get("transcript")

    latest_upload = {
        "id": upload.get("id"),
        "workspace_id": upload.get("workspace_id"),
        "filename": upload.get("filename"),
        "created_at": upload.get("created_at"),
        "status": upload.get("status"),
        "error_message": upload.get("error_message"),
    }

    return {
        "success": True,
        "workspace": workspace,
        "latest_upload": latest_upload,
        "summary": summary,
        "transcript": transcript,
        "actions": actions,
    }


@router.get("/timeline")
def timeline(workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)

    meetings = get_recent_context(workspace, limit=20)

    items = []
    for i, meeting in enumerate(meetings, start=1):
        summary = meeting.get("summary")
        if isinstance(summary, dict):
            title = summary.get("title") or summary.get("summary") or f"Meeting {i}"
        else:
            title = str(summary or f"Meeting {i}")

        items.append(
            {
                "id": meeting.get("id", i),
                "title": title,
                "summary": summary,
                "actions": meeting.get("actions", []),
            }
        )

    return {
        "success": True,
        "workspace": workspace,
        "timeline": items,
    }


@router.get("/insights")
def insights(workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)

    meetings = get_recent_context(workspace, limit=20)
    brain = build_company_brain(meetings)

    return {
        "success": True,
        "workspace": workspace,
        "insights": brain,
    }