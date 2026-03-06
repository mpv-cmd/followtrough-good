# =========================
# FILE: backend/main.py
# =========================
from __future__ import annotations

# ----------------------------------------------------
# ENV
# ----------------------------------------------------
from dotenv import load_dotenv
load_dotenv()

# ----------------------------------------------------
# STANDARD LIBS
# ----------------------------------------------------
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# ----------------------------------------------------
# FASTAPI
# ----------------------------------------------------
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

# ----------------------------------------------------
# INTERNAL
# ----------------------------------------------------
import db
from extract_action import extract_actions
from summarize_meeting import summarize_meeting
from task_intelligence import enrich_task
from daily_planner import generate_daily_plan
from memory_engine import remember_meeting, get_recent_context
from google_calendar import create_event, get_flow, calendar_connected
from transcribe import transcribe_file

from company_brain import build_company_brain
from semantic_memory import semantic_search


# ----------------------------------------------------
# OPTIONAL MODULES (DON'T CRASH APP IF MISSING)
# ----------------------------------------------------
def _optional_import(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception:
        return None

ask_meetings = _optional_import(lambda: __import__("meeting_ai", fromlist=["ask_meetings"]).ask_meetings)
search_meetings = _optional_import(lambda: __import__("meeting_search", fromlist=["search_meetings"]).search_meetings)
generate_weekly_report = _optional_import(lambda: __import__("weekly_report", fromlist=["generate_weekly_report"]).generate_weekly_report)
detect_followups = _optional_import(lambda: __import__("followup_detector", fromlist=["detect_followups"]).detect_followups)
detect_task_risks = _optional_import(lambda: __import__("risk_engine", fromlist=["detect_task_risks"]).detect_task_risks)
detect_task_status = _optional_import(lambda: __import__("task_status_engine", fromlist=["detect_task_status"]).detect_task_status)
generate_dashboard = _optional_import(lambda: __import__("executive_dashboard_ai", fromlist=["generate_dashboard"]).generate_dashboard)
generate_insights = _optional_import(lambda: __import__("insight_engine", fromlist=["generate_insights"]).generate_insights)
predict_project_risks = _optional_import(lambda: __import__("predictive_engine", fromlist=["predict_project_risks"]).predict_project_risks)

# Agent (OpenAI) – optional so the app never crashes if deps/key missing
run_meeting_agent = _optional_import(lambda: __import__("agent", fromlist=["run_meeting_agent"]).run_meeting_agent)


# ----------------------------------------------------
# FASTAPI APP
# ----------------------------------------------------
app = FastAPI()

# IMPORTANT: Tauri dev servers use random localhost ports (you had 127.0.0.1:1430).
# Wildcard "*" is simplest IF you don't need cookies. Your app doesn't need cookies → keep it open.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ----------------------------------------------------
# PATHS
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
WORKSPACES_DIR = BASE_DIR / "workspaces"
WORKSPACES_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------
# HELPERS
# ----------------------------------------------------
DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
}

def _safe_workspace(name: str) -> str:
    if not name:
        return "default"
    name = name.strip().replace(" ", "-")
    name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
    return name or "default"

def _ws_uploads_dir(workspace: str) -> Path:
    ws = _safe_workspace(workspace)
    d = WORKSPACES_DIR / ws / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _dedupe_key(action_text: str, deadline: str) -> str:
    return f"{deadline}|{(action_text or '').strip()}"

def _require(mod: Any, feature: str):
    if mod is None:
        raise HTTPException(status_code=501, detail=f"{feature} not enabled (module missing).")

# ----------------------------------------------------
# REQUEST MODELS
# ----------------------------------------------------
class ApproveBulkRequest(BaseModel):
    indices: List[int]
    deadlines: Any

class UndoRequest(BaseModel):
    index: int

# ----------------------------------------------------
# STARTUP
# ----------------------------------------------------
@app.on_event("startup")
def startup():
    db.init_db()

# ----------------------------------------------------
# HEALTH
# ----------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True, "db": str(db.DB_PATH)}

# ----------------------------------------------------
# GOOGLE AUTH
# ----------------------------------------------------
@app.get("/google_status")
def google_status(workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    return {"connected": bool(calendar_connected(ws)), "workspace": ws}

@app.get("/auth/google")
def google_auth(mode: str = Query("json"), workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    flow = get_flow(ws)

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=ws,
    )

    if mode == "redirect":
        return RedirectResponse(auth_url)

    return JSONResponse({"status": "redirect", "auth_url": auth_url, "workspace": ws})

@app.get("/auth/google/callback")
def google_callback(code: str, state: str = Query("default")):
    ws = _safe_workspace(state)
    flow = get_flow(ws)
    flow.fetch_token(code=code)
    creds = flow.credentials

    if not creds:
        raise HTTPException(status_code=400, detail="No credentials returned")

    db.set_google_token(ws, creds.to_json())

    ws_dir = WORKSPACES_DIR / ws
    ws_dir.mkdir(parents=True, exist_ok=True)

    token_file = ws_dir / "google_token.json"
    token_file.write_text(creds.to_json(), encoding="utf-8")

    return {"status": "connected", "workspace": ws}

# ----------------------------------------------------
# AUDIO UPLOAD
# ----------------------------------------------------
@app.post("/upload_audio")
async def upload_audio(file: UploadFile = File(...), workspace: str = Query("default")):
    ws = _safe_workspace(workspace)

    file_id = str(uuid.uuid4())
    safe_name = file.filename or "audio"
    audio_path = _ws_uploads_dir(ws) / f"{file_id}_{safe_name}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    transcript = transcribe_file(str(audio_path))
    summary = summarize_meeting(transcript)

    actions = extract_actions(transcript) or []
    normalized: List[Dict[str, Any]] = []

    for a in actions:
        if not isinstance(a, dict):
            continue
        action_text = (a.get("action") or "").strip()
        deadline = (a.get("deadline") or "").strip()
        a2 = dict(a)
        a2["dedupe_key"] = _dedupe_key(action_text, deadline) if action_text and deadline else ""
        normalized.append(a2)

    recent_context = get_recent_context(ws)

    followups = None
    if detect_followups is not None:
        try:
            followups = detect_followups(recent_context, normalized)
        except Exception:
            followups = None

    db.save_upload(ws, file_id, safe_name, str(audio_path), normalized)
    approved_map = db.get_approvals_map(ws)

    # Store in memory engine (your "meeting memory")
    remember_meeting(ws, transcript, summary, normalized)

    return {
        "status": "ok",
        "data": {
            "workspace": ws,
            "file_id": file_id,
            "filename": safe_name,
            "audio_path": str(audio_path),
            "summary": summary,
            "followups": followups,
            "actions": normalized,
            "approved_keys": sorted(list(approved_map.keys())),
            "approved_map": approved_map,
        }
    }

# ----------------------------------------------------
# LATEST
# ----------------------------------------------------
@app.get("/latest")
def latest(workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    approved_map = db.get_approvals_map(ws)

    if not upload_id:
        return {"status": "ok", "data": {"workspace": ws, "actions": [], "approved_keys": [], "approved_map": {}}}

    up = db.get_upload(ws, upload_id)
    actions = db.get_actions(upload_id)

    return {
        "status": "ok",
        "data": {
            "workspace": ws,
            "file_id": upload_id,
            "filename": up["filename"],
            "audio_path": up["audio_path"],
            "actions": actions,
            "approved_keys": sorted(list(approved_map.keys())),
            "approved_map": approved_map,
        }
    }

# ----------------------------------------------------
# RE-EXTRACT ACTIONS
# ----------------------------------------------------
@app.post("/reextract")
def reextract(workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    if not upload_id:
        raise HTTPException(status_code=404, detail="No upload found")

    up = db.get_upload(ws, upload_id)
    transcript = transcribe_file(up["audio_path"])
    actions = extract_actions(transcript) or []
    db.overwrite_actions(upload_id, actions)
    return {"status": "ok", "actions": actions}

# ----------------------------------------------------
# RESET APPROVALS
# ----------------------------------------------------
@app.post("/reset_approvals")
def reset_approvals(workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    db.reset_approvals(ws)
    return {"status": "ok"}

# ----------------------------------------------------
# DAILY PLAN
# ----------------------------------------------------
@app.get("/daily_plan")
def daily_plan(workspace: str = Query("default"), day: str = Query(None)):
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    actions = db.get_actions(upload_id) if upload_id else []

    enriched = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        action_text = (a.get("action") or "").strip()
        intel = enrich_task(action_text)
        a2 = dict(a)
        a2["priority"] = intel.get("priority")
        a2["duration"] = intel.get("duration")
        a2["start_time"] = intel.get("start_time")
        enriched.append(a2)

    plan = generate_daily_plan(
        workspace=ws,
        day_iso=day,
        timezone="Europe/Rome",
        candidate_actions=enriched,
    )
    return {"status": "ok", "workspace": ws, "plan": plan}

# ----------------------------------------------------
# APPROVE BULK (CREATE CAL EVENTS)
# ----------------------------------------------------
@app.post("/approve_bulk")
def approve_bulk(req: ApproveBulkRequest, workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    if not upload_id:
        raise HTTPException(status_code=400, detail="No upload loaded")

    actions = db.get_actions(upload_id)
    if not calendar_connected(ws):
        raise HTTPException(status_code=400, detail="Google not connected")

    approved_map = db.get_approvals_map(ws)
    approved_keys = set(approved_map.keys())

    created = []
    failed = []

    for idx in req.indices:
        if idx < 0 or idx >= len(actions):
            failed.append({"index": idx, "error": "Index out of range"})
            continue

        a = actions[idx]
        action_text = (a.get("action") or "").strip()
        deadline = (a.get("deadline") or "").strip()

        if not action_text or not deadline:
            failed.append({"index": idx, "error": "Missing action or deadline"})
            continue

        key = _dedupe_key(action_text, deadline)
        if key in approved_keys:
            failed.append({"index": idx, "error": "Duplicate"})
            continue

        description = (a.get("source_sentence") or "").strip()

        try:
            intel = enrich_task(action_text)
            duration = intel.get("duration") or 30
            start_time = intel.get("start_time") or "09:00"

            ev = create_event(
                workspace=ws,
                title=action_text,
                date=deadline,
                description=description,
                start_time=start_time,
                duration_minutes=duration,
                timezone="Europe/Rome",
            )

            event_id = (ev or {}).get("id")
            if not event_id:
                raise RuntimeError("Missing event id")

            db.insert_approval(ws, key, upload_id, idx, action_text, deadline, str(event_id))
            approved_keys.add(key)

            created.append({"index": idx, "event_id": event_id, "dedupe_key": key})

        except Exception as e:
            failed.append({"index": idx, "error": str(e)})

    return {"status": "bulk_done", "created": created, "failed": failed, "workspace": ws}

# ----------------------------------------------------
# UNDO
# ----------------------------------------------------
@app.post("/undo")
def undo(req: UndoRequest, workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    if not upload_id:
        raise HTTPException(status_code=400, detail="No upload loaded")

    actions = db.get_actions(upload_id)
    idx = int(req.index)
    if idx < 0 or idx >= len(actions):
        raise HTTPException(status_code=400, detail="Index out of range")

    a = actions[idx]
    key = _dedupe_key(a.get("action"), a.get("deadline"))
    removed = db.delete_approval(ws, key)
    return {"status": "ok", "removed": bool(removed), "workspace": ws}

# ----------------------------------------------------
# COMPANY BRAIN (THE BIG UPGRADE)
# ----------------------------------------------------
@app.get("/company_brain")
def company_brain(workspace: str = Query("default")):
    """
    Returns:
      summary, people, tasks, decisions, topics, graph{nodes,edges}
    Uses your stored meeting memory (get_recent_context).
    """
    ws = _safe_workspace(workspace)
    meetings = get_recent_context(ws) or []
    brain = build_company_brain(meetings)
    return {"status": "ok", "workspace": ws, "brain": brain}

@app.get("/company_brain/graph")
def company_brain_graph(workspace: str = Query("default")):
    ws = _safe_workspace(workspace)
    meetings = get_recent_context(ws) or []
    brain = build_company_brain(meetings)
    return {"status": "ok", "workspace": ws, "graph": brain.get("graph", {})}

# ----------------------------------------------------
# AUTONOMOUS AGENT (OPENAI) — SAFE/OPTIONAL
# ----------------------------------------------------
@app.post("/agent/analyze")
def agent_analyze(
    workspace: str = Query("default"),
    payload: Dict[str, Any] = Body(...),
):
    """
    POST JSON:
      {
        "transcript": "...",
        "summary": "...",
        "actions": [...],
        "decisions": [...]
      }
    """
    _require(run_meeting_agent, "agent")
    ws = _safe_workspace(workspace)

    transcript = payload.get("transcript") or ""
    summary = payload.get("summary") or ""
    actions = payload.get("actions") or []
    decisions = payload.get("decisions") or []

    if not str(transcript).strip():
        raise HTTPException(status_code=400, detail="Missing transcript.")

    try:
        report = run_meeting_agent(
            transcript=str(transcript),
            summary=str(summary),
            actions=actions if isinstance(actions, list) else [],
            decisions=decisions if isinstance(decisions, list) else [],
            workspace=ws,
        )
        return {"status": "ok", "workspace": ws, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/analyze_latest")
def agent_analyze_latest(workspace: str = Query("default")):
    """
    Uses meeting memory (get_recent_context) and analyzes the newest meeting.
    No DB coupling, no /latest coupling. Reliable.
    """
    _require(run_meeting_agent, "agent")
    ws = _safe_workspace(workspace)

    meetings = get_recent_context(ws) or []
    if not meetings:
        raise HTTPException(status_code=404, detail="No meetings in memory.")

    m = meetings[-1]  # newest
    transcript = m.get("transcript") or ""
    summary = m.get("summary") or ""
    actions = m.get("actions") or m.get("tasks") or []
    decisions = m.get("decisions") or []

    if not str(transcript).strip():
        raise HTTPException(status_code=404, detail="Latest meeting has no transcript.")

    try:
        report = run_meeting_agent(
            transcript=str(transcript),
            summary=str(summary),
            actions=actions if isinstance(actions, list) else [],
            decisions=decisions if isinstance(decisions, list) else [],
            workspace=ws,
        )
        return {"status": "ok", "workspace": ws, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------
# OPTIONAL ENDPOINTS (SAFE)
# ----------------------------------------------------
@app.post("/ask")
def ask(payload: Dict[str, Any] = Body(...), workspace: str = Query("default")):
    _require(ask_meetings, "ask")
    ws = _safe_workspace(workspace)
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")
    meetings = get_recent_context(ws)
    answer = ask_meetings(question, meetings)
    return {"status": "ok", "answer": answer}

@app.post("/search_meetings")
def search_meetings_api(payload: Dict[str, Any] = Body(...), workspace: str = Query("default")):
    _require(search_meetings, "search_meetings")
    ws = _safe_workspace(workspace)
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")
    meetings = get_recent_context(ws)
    answer = search_meetings(question, meetings)
    return {"status": "ok", "answer": answer}

@app.get("/weekly_report")
def weekly_report(workspace: str = Query("default")):
    _require(generate_weekly_report, "weekly_report")
    ws = _safe_workspace(workspace)
    meetings = get_recent_context(ws)
    report = generate_weekly_report(meetings)
    return {"status": "ok", "report": report}

@app.get("/task_risks")
def task_risks(workspace: str = Query("default")):
    _require(detect_task_risks, "task_risks")
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    if not upload_id:
        return {"status": "ok", "risks": []}
    actions = db.get_actions(upload_id)
    risks = detect_task_risks(actions)
    return {"status": "ok", "risks": risks}

@app.get("/task_status")
def task_status(workspace: str = Query("default")):
    _require(detect_task_status, "task_status")
    ws = _safe_workspace(workspace)
    upload_id = db.latest_upload_id(ws)
    if not upload_id:
        return {"status": "ok", "tasks": []}
    actions = db.get_actions(upload_id)
    statuses = detect_task_status(actions)
    return {"status": "ok", "tasks": statuses}

@app.get("/dashboard")
def dashboard(workspace: str = Query("default")):
    _require(generate_dashboard, "dashboard")
    ws = _safe_workspace(workspace)
    meetings = get_recent_context(ws)
    upload_id = db.latest_upload_id(ws)
    actions = db.get_actions(upload_id) if upload_id else []
    dash = generate_dashboard(meetings, actions)
    return {"status": "ok", "dashboard": dash}

@app.get("/insights")
def insights(workspace: str = Query("default")):
    _require(generate_insights, "insights")
    ws = _safe_workspace(workspace)
    meetings = get_recent_context(ws)
    upload_id = db.latest_upload_id(ws)
    actions = db.get_actions(upload_id) if upload_id else []
    out = generate_insights(meetings, actions)
    return {"status": "ok", "insights": out}

@app.get("/predictions")
def predictions(workspace: str = Query("default")):
    _require(predict_project_risks, "predictions")
    ws = _safe_workspace(workspace)
    meetings = get_recent_context(ws)
    upload_id = db.latest_upload_id(ws)
    actions = db.get_actions(upload_id) if upload_id else []
    out = predict_project_risks(meetings, actions)
    return {"status": "ok", "predictions": out}

# ----------------------------------------------------
# REFRESH ALL (ONE CALL FOR ENTIRE UI)
# ----------------------------------------------------
@app.get("/refresh_all")
def refresh_all(workspace: str = Query("default")):

    ws = _safe_workspace(workspace)

    upload_id = db.latest_upload_id(ws)

    actions = db.get_actions(upload_id) if upload_id else []

    meetings = get_recent_context(ws) or []

    brain = build_company_brain(meetings)

    approved_map = db.get_approvals_map(ws)

    risks = []
    if detect_task_risks is not None and actions:
        try:
            risks = detect_task_risks(actions)
        except Exception:
            risks = []

    task_status = []
    if detect_task_status is not None and actions:
        try:
            task_status = detect_task_status(actions)
        except Exception:
            task_status = []

    insights = []
    if generate_insights is not None:
        try:
            insights = generate_insights(meetings, actions)
        except Exception:
            insights = []

    predictions = []
    if predict_project_risks is not None:
        try:
            predictions = predict_project_risks(meetings, actions)
        except Exception:
            predictions = []

    dashboard = None
    if generate_dashboard is not None:
        try:
            dashboard = generate_dashboard(meetings, actions)
        except Exception:
            dashboard = None

    return {
        "status": "ok",
        "workspace": ws,

        "latest": {
            "upload_id": upload_id,
            "actions": actions,
            "approved_map": approved_map
        },

        "brain": brain,
        "graph": brain.get("graph", {}),

        "risks": risks,
        "task_status": task_status,
        "insights": insights,
        "predictions": predictions,
        "dashboard": dashboard
    }
    
class BrainQuestion(BaseModel):
    question: str


@app.post("/brain/ask")
async def ask_company_brain(q: BrainQuestion, workspace: str = "default"):
    """
    Ask questions about meetings, tasks, decisions, and people.
    """

    kb = _require("kb", "company brain")

    brain = kb.get_company_brain(workspace)

    prompt = f"""
You are an AI assistant for company meetings.

Use the company knowledge below to answer the question.

Company Brain:
{brain}

Question:
{q.question}

Answer clearly and concisely.
"""

    import openai
    client = openai.OpenAI()

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You analyze company knowledge graphs."},
            {"role":"user","content":prompt}
        ]
    )

    return {"answer": r.choices[0].message.content}