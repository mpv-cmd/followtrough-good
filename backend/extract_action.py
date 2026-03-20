from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from backend.ai_action_extractor import ai_extract_actions
except Exception:
    ai_extract_actions = None


COMMITMENT_VERBS = [
    "we'll",
    "we will",
    "i'll",
    "i will",
    "need to",
    "let's",
    "lets",
    "should",
    "will",
    "must",
    "have to",
]

DAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _next_weekday(from_date: datetime, weekday: int) -> datetime:
    days_ahead = (weekday - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)


def _parse_deadline(text: str) -> Optional[str]:
    t = (text or "").lower()
    now = datetime.now()

    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", t)
    if iso:
        return iso.group(1)

    if "today" in t:
        return now.date().isoformat()

    if "tomorrow" in t:
        return (now + timedelta(days=1)).date().isoformat()

    for name, idx in DAY_MAP.items():
        if name in t:
            return _next_weekday(now, idx).date().isoformat()

    if "next week" in t:
        return (now + timedelta(days=7)).date().isoformat()

    return None


def _extract_owner(sentence: str) -> Optional[str]:
    m = re.match(r"^\s*([A-Z][a-zA-Z]+)\s*:\s*", sentence)
    if m:
        return m.group(1)

    m = re.search(r"\b([A-Z][a-zA-Z]+)\s+(will|to|should|needs to)\b", sentence)
    if m:
        return m.group(1)

    return None


def _split_tasks(sentence: str) -> List[str]:
    parts = re.split(r"\band\b|\bthen\b|\balso\b", sentence, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _normalize_action(action: Dict[str, Any], source_sentence: str = "") -> Dict[str, Any]:
    return {
        "action": str(action.get("action") or "").strip(),
        "owner": action.get("owner"),
        "deadline": action.get("deadline"),
        "source_sentence": str(action.get("source_sentence") or source_sentence or "").strip(),
        "confidence": float(action.get("confidence", 0.65)),
    }


def extract_actions(transcript: str) -> List[Dict[str, Any]]:
    transcript = (transcript or "").strip()

    if not transcript:
        return []

    if ai_extract_actions:
        try:
            ai = ai_extract_actions(transcript)
            if ai:
                normalized = []
                for item in ai:
                    if isinstance(item, dict) and str(item.get("action") or "").strip():
                        normalized.append(_normalize_action(item))
                if normalized:
                    return normalized[:20]
        except Exception:
            pass

    actions: List[Dict[str, Any]] = []
    sentences = re.split(r"(?<=[.!?])\s+", transcript)

    for s in sentences:
        sentence = s.strip()
        if not sentence:
            continue

        lowered = sentence.lower()
        if not any(v in lowered for v in COMMITMENT_VERBS):
            continue

        tasks = _split_tasks(sentence)

        for task in tasks:
            task_text = task.strip()
            if not task_text:
                continue

            owner = _extract_owner(task_text)
            deadline = _parse_deadline(task_text)

            actions.append(
                {
                    "action": task_text,
                    "owner": owner,
                    "deadline": deadline,
                    "source_sentence": sentence,
                    "confidence": 0.65,
                }
            )

    return actions[:20]


def extract_single_action(transcript: str) -> Optional[Dict[str, Any]]:
    acts = extract_actions(transcript)
    return acts[0] if acts else None