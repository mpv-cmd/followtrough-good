# --- SAFETY GUARD: prevent HTML/UI code in backend files ---
import pathlib, sys

BACKEND_DIR = pathlib.Path(__file__).parent
_lt = "<"
_gt = ">"
BAD_MARKERS = [
    _lt + "html" + _gt,
    "<!" + "doctype html",
    _lt + "button" + _gt,
    _lt + "body" + _gt,
    _lt + "head" + _gt,
    _lt + "/html" + _gt,
]

for py in BACKEND_DIR.glob("*.py"):
    try:
        txt = py.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        continue
    if any(m in txt for m in BAD_MARKERS):
        print(f"❌ SAFETY GUARD: HTML detected in backend file: {py.name}")
        sys.exit(1)
# --- END SAFETY GUARD ---

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import os, json, uuid, shutil, re
from datetime import datetime

from transcribe import transcribe_file
from extract_action import extract_actions
from google_calendar import get_flow, create_event

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

LATEST_JSON_PATH = os.path.join(UPLOAD_DIR, "latest.json")
TOKEN_PATH = "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _make_dedupe_key(action: dict, deadline: str) -> str:
    title = (action.get("action") or "").strip()
    return f"{deadline}|{title}"


def _split_combo_actions(actions: list[dict]) -> list[dict]:
    """
    Heuristic: if the model returns one action string containing multiple clauses
    separated by commas/semicolons, split into multiple actions for better UX.
    """
    if not actions or len(actions) != 1:
        return actions

    a0 = actions[0] or {}
    text = str(a0.get("action") or "").strip()
    if not text:
        return actions

    parts = [p.strip() for p in re.split(r"\s*[;,]\s*", text) if p.strip()]
    if len(parts) <= 1:
        return actions

    out: list[dict] = []
    for p in parts:
        item = dict(a0)
        if not p.endswith("."):
            p = p + "."
        item["action"] = p

        lower = p.lower()
        timing_words = [
            "today", "tomorrow",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "next week", "next month",
        ]
        if not any(w in lower for w in timing_words):
            item["deadline"] = None

        m = re.match(r"^([A-Z][a-z]+)\s+will\b", p)
        if m:
            item["owner"] = m.group(1)

        try:
            item["confidence"] = float(item.get("confidence", 0.6)) * 0.9
        except Exception:
            item["confidence"] = 0.54

        out.append(item)

    return out


def _extract_explicit_time(text: str) -> str | None:
    t = (text or "").lower()

    m24 = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t)
    if m24:
        hh = int(m24.group(1))
        mm = int(m24.group(2))
        return f"{hh:02d}:{mm:02d}"

    mampm = re.search(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b", t)
    if mampm:
        hh = int(mampm.group(1))
        mm = int(mampm.group(2) or "00")
        ap = mampm.group(3)
        if ap == "pm" and hh != 12:
            hh += 12
        if ap == "am" and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm:02d}"

    return None


def _suggest_start_time(text: str) -> str:
    explicit = _extract_explicit_time(text)
    if explicit:
        return explicit

    t = (text or "").lower()
    if "eod" in t or "end of day" in t or "by end of day" in t:
        return "17:00"
    if "noon" in t or "midday" in t or "lunch" in t:
        return "12:00"
    if "afternoon" in t:
        return "14:00"
    if "evening" in t or "tonight" in t:
        return "18:00"
    if "morning" in t:
        return "09:00"
    return "09:00"


def _format_event_description(filename: str, action: dict) -> str:
    owner = action.get("owner") or "—"
    src = action.get("source_sentence") or "—"
    return f"File: {filename}\nOwner: {owner}\nSource: {src}\n"


class BulkApproveRequest(BaseModel):
    indices: list[int] = []
    deadlines: dict[str, str] | None = None


@app.post("/upload")
async def upload_meeting(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    transcript = transcribe_file(file_path)
    actions = extract_actions(transcript)
    actions = _split_combo_actions(actions)

    payload = {
        "file_id": file_id,
        "filename": file.filename,
        "actions": actions,
        "approved_keys": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    with open(LATEST_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {"status": "ok", **payload}


@app.get("/latest")
def latest():
    if not os.path.exists(LATEST_JSON_PATH):
        return {"status": "empty"}

    with open(LATEST_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "actions" not in data:
        data["actions"] = []
    if "approved_keys" not in data:
        data["approved_keys"] = []

    return {"status": "ok", "data": data}


@app.get("/auth/google")
def google_auth():
    flow = get_flow()
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)


@app.get("/auth/google/callback")
def google_callback(code: str):
    flow = get_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    return {"status": "connected"}


@app.post("/approve_bulk")
def approve_bulk(req: BulkApproveRequest):
    if not os.path.exists(LATEST_JSON_PATH):
        raise HTTPException(status_code=404, detail="No latest upload found")

    with open(LATEST_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    actions = data.get("actions") or []
    if not actions:
        raise HTTPException(status_code=400, detail="No actions detected")

    approved_keys = set(data.get("approved_keys") or [])

    indices = req.indices or list(range(len(actions)))
    if any(i < 0 or i >= len(actions) for i in indices):
        raise HTTPException(status_code=400, detail="Index out of range")

    if not os.path.exists(TOKEN_PATH):
        raise HTTPException(status_code=400, detail="Google not connected. Visit /auth/google first.")

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    created = []
    failed = []
    deadlines = req.deadlines or {}
    seen_this_request = set()

    for idx in indices:
        action = actions[idx]
        deadline = deadlines.get(str(idx)) or action.get("deadline")

        if not deadline:
            failed.append({"index": idx, "error": "No deadline"})
            continue

        dedupe_key = _make_dedupe_key(action, deadline)

        if dedupe_key in seen_this_request:
            failed.append({"index": idx, "error": "Duplicate in same request"})
            continue
        seen_this_request.add(dedupe_key)

        if dedupe_key in approved_keys:
            failed.append({"index": idx, "error": "Duplicate already created"})
            continue

        try:
            context_text = f"{action.get('action','')} {action.get('source_sentence','')}"
            start_time = _suggest_start_time(context_text)

            event = create_event(
                creds,
                title=action.get("action", "Follow-up"),
                date=deadline,
                description=_format_event_description(data.get("filename", "—"), action),
                start_time=start_time,
                timezone="Europe/Rome",
                reminders_minutes=[30, 1440],
            )
            created.append({"index": idx, "event_id": event.get("id")})
            approved_keys.add(dedupe_key)
        except RefreshError:
            raise HTTPException(status_code=400, detail="Google authorization invalid. Reconnect at /auth/google.")
        except Exception as e:
            failed.append({"index": idx, "error": str(e)})

    data["approved_keys"] = sorted(approved_keys)
    with open(LATEST_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"status": "bulk_done", "created": created, "failed": failed}