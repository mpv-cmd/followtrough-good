from dotenv import load_dotenv
load_dotenv()
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
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

def create_event(creds, title, date, description, start_time: str = "09:00", duration_minutes: int = 30, timezone: str = "Europe/Rome"):
    """
    Create a timed event on the given date.
    - date: "YYYY-MM-DD"
    - start_time: "HH:MM" (24h)
    - duration_minutes: int
    - timezone: IANA tz name (default Europe/Rome)
    """
    service = build("calendar", "v3", credentials=creds)

    # Build RFC3339 dateTime strings + explicit timeZone for Google Calendar
    start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event = {
        "summary": f"{title} (AI-generated)",
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        },
        # Small polish: popup reminder 30 minutes before
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 30}],
        },
    }

    return service.events().insert(calendarId="primary", body=event).execute()