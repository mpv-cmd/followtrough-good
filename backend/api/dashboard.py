from __future__ import annotations

from fastapi import APIRouter, Query

from backend import db
from backend.company_brain import build_company_brain
from backend.memory_engine import get_recent_context

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
def dashboard(workspace: str = Query(default="default")):
    workspace = (workspace or "default").strip() or "default"

    upload_id = db.latest_upload_id(workspace)
    if not upload_id:
        return {
            "success": True,
            "workspace": workspace,
            "latest_upload": None,
            "actions": [],
            "message": "No uploads yet",
        }

    upload = db.get_upload_status(workspace, upload_id)
    actions = db.get_actions(upload_id)

    return {
        "success": True,
        "workspace": workspace,
        "latest_upload": upload,
        "actions": actions,
    }


@router.get("/timeline")
def timeline(workspace: str = Query(default="default")):
    workspace = (workspace or "default").strip() or "default"

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
    workspace = (workspace or "default").strip() or "default"

    meetings = get_recent_context(workspace, limit=20)
    brain = build_company_brain(meetings)

    return {
        "success": True,
        "workspace": workspace,
        "insights": brain,
    }