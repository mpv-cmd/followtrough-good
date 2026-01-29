# --- SAFETY GUARD: prevent HTML/UI code in backend files ---
from dotenv import load_dotenv
load_dotenv()

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8000/auth/google/callback"],
            }
        },
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/google/callback",
    )


def create_event(
    creds,
    title,
    date,
    description,
    start_time: str = "09:00",
    duration_minutes: int = 30,
    timezone: str = "Europe/Rome",
    reminders_minutes: list[int] | None = None,
):
    service = build("calendar", "v3", credentials=creds)

    start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    overrides = []
    mins = reminders_minutes or [30]
    for m in mins:
        try:
            m_int = int(m)
        except Exception:
            continue
        overrides.append({"method": "popup", "minutes": m_int})
        if m_int >= 60:
            overrides.append({"method": "email", "minutes": m_int})

    event = {
        "summary": f"{title} (AI-generated)",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        "reminders": {
            "useDefault": False,
            "overrides": overrides or [{"method": "popup", "minutes": 30}],
        },
    }

    return service.events().insert(calendarId="primary", body=event).execute()