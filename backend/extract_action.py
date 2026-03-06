# backend/extract_action.py

import re
from datetime import datetime, timedelta

try:
    from ai_action_extractor import ai_extract_actions
except Exception:
    ai_extract_actions = None


COMMITMENT_VERBS = [
    "we'll","we will","i'll","i will",
    "need to","let's","lets","should",
    "will","must","have to"
]

DAY_MAP = {
    "monday":0,"tuesday":1,"wednesday":2,
    "thursday":3,"friday":4,"saturday":5,"sunday":6
}


def _next_weekday(from_date, weekday):

    days_ahead = (weekday - from_date.weekday()) % 7

    if days_ahead == 0:
        days_ahead = 7

    return from_date + timedelta(days=days_ahead)


def _parse_deadline(text):

    t = (text or "").lower()

    now = datetime.now()

    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", t)

    if iso:
        return iso.group(1)

    if "today" in t:
        return now.date().isoformat()

    if "tomorrow" in t:
        return (now + timedelta(days=1)).date().isoformat()

    for name,idx in DAY_MAP.items():
        if name in t:
            return _next_weekday(now,idx).date().isoformat()

    if "next week" in t:
        return (now + timedelta(days=7)).date().isoformat()

    return None


def _extract_owner(sentence):

    m = re.match(r"^\s*([A-Z][a-zA-Z]+)\s*:\s*", sentence)

    if m:
        return m.group(1)

    m = re.search(r"\b([A-Z][a-zA-Z]+)\s+(will|to|should|needs to)", sentence)

    if m:
        return m.group(1)

    return None


def _split_tasks(sentence):

    parts = re.split(r"\band\b|\bthen\b|\balso\b", sentence)

    return [p.strip() for p in parts if p.strip()]


def extract_actions(transcript):

    transcript = transcript or ""

    if ai_extract_actions:

        try:
            ai = ai_extract_actions(transcript)

            if ai:
                return ai

        except Exception:
            pass

    actions = []

    sentences = re.split(r"(?<=[.!?])\s+", transcript)

    for s in sentences:

        if not any(v in s.lower() for v in COMMITMENT_VERBS):
            continue

        tasks = _split_tasks(s)

        for t in tasks:

            owner = _extract_owner(t)

            deadline = _parse_deadline(t)

            actions.append({
                "action": t.strip(),
                "owner": owner,
                "deadline": deadline,
                "source_sentence": s,
                "confidence": 0.65
            })

    return actions[:20]


def extract_single_action(transcript):

    acts = extract_actions(transcript)

    return acts[0] if acts else None