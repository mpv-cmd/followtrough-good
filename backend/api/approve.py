from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from backend import db

router = APIRouter(prefix="/approve", tags=["Approvals"])


def _safe_workspace(workspace: str | None) -> str:
    return (workspace or "default").strip() or "default"


def _safe_dedupe_key(action: Dict[str, Any]) -> str:
    action_text = str(action.get("action") or "").strip()
    deadline = str(action.get("deadline") or "").strip()
    return f"{deadline}|{action_text}"


@router.get("/latest")
def latest_actions_for_approval(workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)

    upload_id = db.latest_upload_id(workspace)
    if not upload_id:
        return {
            "success": True,
            "workspace": workspace,
            "upload_id": None,
            "actions": [],
            "approved_keys": [],
            "approved_map": {},
            "message": "No uploads yet",
        }

    upload = db.get_upload(workspace, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Latest upload not found")

    actions = db.get_actions(upload_id)
    approvals_map = db.get_approvals_map(workspace)

    normalized_actions: List[Dict[str, Any]] = []
    approved_keys: List[str] = []

    for idx, action in enumerate(actions):
        dedupe_key = str(action.get("dedupe_key") or "").strip()
        if not dedupe_key:
            dedupe_key = _safe_dedupe_key(action)

        normalized = {
            "index": idx,
            "action": action.get("action"),
            "owner": action.get("owner"),
            "deadline": action.get("deadline"),
            "source_sentence": action.get("source_sentence"),
            "confidence": action.get("confidence"),
            "dedupe_key": dedupe_key,
            "approved": dedupe_key in approvals_map,
        }

        if dedupe_key in approvals_map:
            approved_keys.append(dedupe_key)

        normalized_actions.append(normalized)

    return {
        "success": True,
        "workspace": workspace,
        "upload_id": upload_id,
        "filename": upload.get("filename"),
        "status": upload.get("status"),
        "actions": normalized_actions,
        "approved_keys": approved_keys,
        "approved_map": approvals_map,
    }


@router.post("/bulk")
def approve_bulk(payload: Dict[str, Any], workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)

    upload_id = str(payload.get("upload_id") or "").strip()
    selected = payload.get("selected") or []

    if not upload_id:
        raise HTTPException(status_code=400, detail="Missing upload_id")

    upload = db.get_upload(workspace, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    actions = db.get_actions(upload_id)
    if not actions:
        return {
            "success": True,
            "workspace": workspace,
            "upload_id": upload_id,
            "approved": [],
            "skipped": [],
            "message": "No actions to approve",
        }

    selected_map = {}
    for item in selected:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if idx is None:
            continue
        selected_map[int(idx)] = item

    approved: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for idx, action in enumerate(actions):
        if idx not in selected_map:
            continue

        selected_item = selected_map[idx]

        action_text = str(action.get("action") or "").strip()
        deadline = str(
            selected_item.get("deadline")
            or action.get("deadline")
            or ""
        ).strip()

        if not action_text:
            skipped.append(
                {
                    "index": idx,
                    "reason": "Missing action text",
                }
            )
            continue

        if not deadline:
            skipped.append(
                {
                    "index": idx,
                    "reason": "Missing deadline",
                    "action": action_text,
                }
            )
            continue

        dedupe_key = str(action.get("dedupe_key") or "").strip()
        if not dedupe_key:
            dedupe_key = f"{deadline}|{action_text}"

        try:
            db.insert_approval(
                workspace_id=workspace,
                dedupe_key=dedupe_key,
                upload_id=upload_id,
                action_idx=idx,
                action_text=action_text,
                deadline=deadline,
                event_id="",
            )
            approved.append(
                {
                    "index": idx,
                    "action": action_text,
                    "deadline": deadline,
                    "dedupe_key": dedupe_key,
                }
            )
        except Exception:
            skipped.append(
                {
                    "index": idx,
                    "reason": "Already approved or insert failed",
                    "action": action_text,
                    "deadline": deadline,
                    "dedupe_key": dedupe_key,
                }
            )

    return {
        "success": True,
        "workspace": workspace,
        "upload_id": upload_id,
        "approved": approved,
        "skipped": skipped,
        "approved_map": db.get_approvals_map(workspace),
    }


@router.post("/reset")
def reset_all_approvals(workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)
    db.reset_approvals(workspace)

    return {
        "success": True,
        "workspace": workspace,
        "message": "Approvals reset",
        "approved_map": {},
    }


@router.delete("/{dedupe_key}")
def delete_approval(dedupe_key: str, workspace: str = Query(default="default")):
    workspace = _safe_workspace(workspace)

    deleted = db.delete_approval(workspace, dedupe_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {
        "success": True,
        "workspace": workspace,
        "deleted": dedupe_key,
        "approved_map": db.get_approvals_map(workspace),
    }