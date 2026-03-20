from __future__ import annotations

import json
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from backend import db
from ..services.meeting_service import process_meeting

router = APIRouter(prefix="/meetings", tags=["Meetings"])

UPLOAD_DIR = "uploads"


def _process_in_background(workspace: str, file_path: str, upload_id: str) -> None:
    try:
        process_meeting(workspace, file_path, upload_id=upload_id)
    except Exception as e:
        print("Background processing failed:", e)


@router.post("/upload")
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace: str = "default",
):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    workspace = (workspace or "default").strip() or "default"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    upload_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "wav"
    file_path = os.path.join(UPLOAD_DIR, f"{upload_id}.{file_ext}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db.create_upload_record(
            workspace_id=workspace,
            upload_id=upload_id,
            filename=file.filename,
            audio_path=file_path,
        )

        background_tasks.add_task(_process_in_background, workspace, file_path, upload_id)

        return {
            "success": True,
            "message": "Upload received. Processing started.",
            "upload_id": upload_id,
            "workspace": workspace,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    finally:
        file.file.close()


@router.get("/status/{upload_id}")
async def get_upload_status(upload_id: str, workspace: str = "default"):
    workspace = (workspace or "default").strip() or "default"

    record = db.get_upload_status(workspace, upload_id)
    if not record:
        raise HTTPException(status_code=404, detail="Upload not found")

    actions = db.get_actions(upload_id)

    summary = None
    raw_summary = record.get("summary_json")
    if raw_summary:
        try:
            summary = json.loads(raw_summary)
        except Exception:
            summary = raw_summary

    return {
        "success": True,
        "upload_id": record["id"],
        "workspace": record["workspace_id"],
        "filename": record["filename"],
        "created_at": record["created_at"],
        "status": record["status"],
        "error": record.get("error_message"),
        "data": {
            "transcript": record.get("transcript"),
            "summary": summary,
            "actions": actions,
        },
    }