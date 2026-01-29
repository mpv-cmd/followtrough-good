import re
import calendar
from datetime import datetime, timedelta

COMMITMENT_VERBS = [
    "we'll", "we will", "i'll", "i will",
    "need to", "let's", "lets", "should",
    "will",
]

DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
}

def _next_weekday(from_date: datetime, weekday: int) -> datetime:
    days_ahead = (weekday - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)

def _parse_deadline(text: str) -> str | None:
    t = (text or "").lower().strip()
    now = datetime.now()

    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", t)
    if iso:
        return iso.group(1)

    if "today" in t:
        return now.date().isoformat()
    if "tomorrow" in t or "tmr" in t:
        return (now + timedelta(days=1)).date().isoformat()

    if "next week" in t:
        return (now + timedelta(days=7)).date().isoformat()

    return None

def extract_actions(transcript: str) -> list[dict]:
    actions = []
    sentences = re.split(r"(?<=[.!?])\s+", transcript or "")

    for s in sentences:
        if not any(v in s.lower() for v in COMMITMENT_VERBS):
            continue

        actions.append({
            "action": s.strip(),
            "owner": None,
            "deadline": _parse_deadline(s),
            "source_sentence": s,
            "confidence": 0.65,
        })

    return actions[:10]

def extract_single_action(transcript: str):
    acts = extract_actions(transcript)
    return acts[0] if acts else None