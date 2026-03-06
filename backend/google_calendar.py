# backend/google_calendar.py

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

BASE_DIR = Path(__file__).resolve().parent
WORKSPACES_DIR = BASE_DIR / "workspaces"
WORKSPACES_DIR.mkdir(exist_ok=True)

CLIENT_SECRET_PATH = Path(
    os.getenv("GOOGLE_CLIENT_SECRET_FILE", str(BASE_DIR / "client_secret.json"))
).expanduser()


def _safe_workspace(ws: str) -> str:
    ws = (ws or "default").strip()
    keep = []
    for ch in ws:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep) or "default"


def _workspace_dir(workspace: str) -> Path:
    d = WORKSPACES_DIR / _safe_workspace(workspace)
    d.mkdir(parents=True, exist_ok=True)
    return d


def token_path(workspace: str) -> Path:
    return _workspace_dir(workspace) / "google_token.json"


def _load_client_config() -> Dict[str, Any]:
    if not CLIENT_SECRET_PATH.exists():
        raise RuntimeError(f"Missing Google OAuth client secret JSON at: {CLIENT_SECRET_PATH}")

    cfg = json.loads(CLIENT_SECRET_PATH.read_text(encoding="utf-8"))

    if "web" in cfg:
        return {"web": cfg["web"]}
    if "installed" in cfg:
        return {"installed": cfg["installed"]}
    raise RuntimeError("client_secret.json must contain 'web' or 'installed'")


def get_flow(workspace: str) -> Flow:
    client_config = _load_client_config()
    redirect_uri = "http://127.0.0.1:8000/auth/google/callback"
    return Flow.from_client_config(client_config=client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def _load_creds(workspace: str) -> Optional[Credentials]:
    tp = token_path(workspace)
    if not tp.exists():
        return None

    try:
        info = json.loads(tp.read_text(encoding="utf-8"))
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    except Exception:
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            tp.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            return None

    if not creds or not creds.valid:
        return None
    return creds


def calendar_connected(workspace: str) -> bool:
    return _load_creds(workspace) is not None


def _service(workspace: str):
    creds = _load_creds(workspace)
    if not creds:
        raise RuntimeError("Google not connected for this workspace.")
    return build("calendar", "v3", credentials=creds)


# -----------------------------
# Calendar Brain helpers
# -----------------------------

def list_events_for_day(
    workspace: str,
    date: str,  # YYYY-MM-DD
    timezone: str = "Europe/Rome",
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """
    Returns a simplified list of calendar events for the given day.
    """
    svc = _service(workspace)

    start = datetime.fromisoformat(f"{date}T00:00:00")
    end = start + timedelta(days=1)

    out = svc.events().list(
        calendarId=calendar_id,
        timeMin=start.isoformat() + "Z" if "Z" not in start.isoformat() else start.isoformat(),
        timeMax=end.isoformat() + "Z" if "Z" not in end.isoformat() else end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    items = out.get("items", []) or []

    events: List[Dict[str, Any]] = []
    for ev in items:
        start_info = ev.get("start", {})
        end_info = ev.get("end", {})
        # Can be dateTime or all-day date
        s = start_info.get("dateTime") or start_info.get("date")
        e = end_info.get("dateTime") or end_info.get("date")
        events.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary", "(no title)"),
                "start": s,
                "end": e,
                "location": ev.get("location", None),
            }
        )

    return events


def find_free_slot(
    svc,
    date: str,
    duration_minutes: int = 30,
    timezone: str = "Europe/Rome",
) -> str:
    start_of_day = datetime.fromisoformat(f"{date}T08:00:00")
    end_of_day = datetime.fromisoformat(f"{date}T18:00:00")

    body = {
        "timeMin": start_of_day.isoformat(),
        "timeMax": end_of_day.isoformat(),
        "timeZone": timezone,
        "items": [{"id": "primary"}],
    }

    events = svc.freebusy().query(body=body).execute()
    busy = events["calendars"]["primary"]["busy"]
    current = start_of_day

    for slot in busy:
        busy_start = datetime.fromisoformat(slot["start"])
        busy_end = datetime.fromisoformat(slot["end"])

        if (busy_start - current) >= timedelta(minutes=duration_minutes):
            return current.strftime("%H:%M")

        current = max(current, busy_end)

    return current.strftime("%H:%M")


def create_event(
    workspace: str,
    title: str,
    date: str,
    description: str = "",
    start_time: str | None = None,
    duration_minutes: int = 30,
    timezone: str = "Europe/Rome",
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    svc = _service(workspace)

    if not start_time:
        start_time = find_free_slot(svc, date, duration_minutes, timezone)

    start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    body = {
        "summary": title,
        "description": description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
    }

    return svc.events().insert(calendarId=calendar_id, body=body).execute()


def delete_event(workspace: str, event_id: str, calendar_id: str = "primary") -> None:
    svc = _service(workspace)
    svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def event_edit_link(event_id: str) -> str:
    return f"https://calendar.google.com/calendar/u/0/r/eventedit/{event_id}"