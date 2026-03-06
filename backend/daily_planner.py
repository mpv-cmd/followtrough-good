# backend/daily_planner.py
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, date as date_type
from typing import Any, Dict, List, Optional, Tuple

from google_calendar import list_events_for_day


DEFAULT_MODEL = os.getenv("FOLLOWTHROUGH_PLANNER_MODEL", "gpt-4o-mini")


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _today_iso(tz: str = "Europe/Rome") -> str:
    # backend runs locally; using local date is fine for your case
    return datetime.now().date().isoformat()


def _tomorrow_iso() -> str:
    return (datetime.now().date() + timedelta(days=1)).isoformat()


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _normalize_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep only what we need; tolerate messy shapes.
    """
    out: List[Dict[str, Any]] = []
    for a in actions or []:
        if not isinstance(a, dict):
            continue
        out.append(
            {
                "action": _safe_str(a.get("action")).strip(),
                "owner": a.get("owner", None),
                "deadline": a.get("deadline", None),
                "confidence": a.get("confidence", None),
                "source_sentence": _safe_str(a.get("source_sentence") or "").strip(),
                "dedupe_key": _safe_str(a.get("dedupe_key") or "").strip(),
                "priority": a.get("priority", None),
                "duration": a.get("duration", None),
            }
        )
    return out


def _as_planner_prompt(
    *,
    day_iso: str,
    timezone: str,
    events: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
) -> str:
    schema_hint = {
        "date": "YYYY-MM-DD",
        "timezone": timezone,
        "plan": [
            {
                "start": "HH:MM",
                "end": "HH:MM",
                "title": "string",
                "type": "meeting|task|break",
                "source": "calendar|followthrough",
                "action_dedupe_key": "string or null (only for tasks)",
                "notes": "string (optional)",
            }
        ],
        "top_priorities": ["string"],
        "carry_over": ["string (dedupe_key)"],
        "warnings": ["string"],
    }

    return f"""
You are a pragmatic daily planner.

Goal:
- Produce a realistic time-blocked plan for the day.
- Respect existing calendar events.
- Place tasks in the gaps.

Rules:
- Working hours: 08:00-18:00 local time ({timezone}).
- Do NOT overlap meetings.
- Add a 10 minute buffer after each meeting.
- Tasks: use duration hints if present; otherwise assume 30 minutes.
- Put the most urgent tasks earlier.
- Include at least one short break if the day is dense.
- Output STRICT JSON only.

Return JSON only with this exact shape:
{json.dumps(schema_hint, ensure_ascii=False)}

Input calendar events:
{json.dumps(events, ensure_ascii=False)}

Candidate tasks (from FollowThrough approvals/actions):
{json.dumps(actions, ensure_ascii=False)}
""".strip()


def generate_daily_plan(
    *,
    workspace: str,
    day_iso: Optional[str] = None,
    timezone: str = "Europe/Rome",
    calendar_id: str = "primary",
    candidate_actions: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Uses calendar events + candidate tasks to generate a day plan.

    candidate_actions should be a list of dict actions (preferably enriched w/ duration/priority).
    If OpenAI not configured, returns None.
    """
    if not _has_openai_key():
        return None

    if not day_iso:
        day_iso = _today_iso(timezone)

    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    # Pull calendar events for the day
    events = list_events_for_day(
        workspace=workspace,
        date=day_iso,
        timezone=timezone,
        calendar_id=calendar_id,
    )

    actions = _normalize_actions(candidate_actions or [])

    prompt = _as_planner_prompt(
        day_iso=day_iso,
        timezone=timezone,
        events=events,
        actions=actions,
    )

    client = OpenAI()

    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You output strict JSON plans. No prose."},
                {"role": "user", "content": prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        # Minimal normalization/guardrails
        if not isinstance(data, dict):
            return None
        if "plan" not in data or not isinstance(data.get("plan"), list):
            data["plan"] = []
        data.setdefault("date", day_iso)
        data.setdefault("timezone", timezone)
        data.setdefault("top_priorities", [])
        data.setdefault("carry_over", [])
        data.setdefault("warnings", [])

        return data
    except Exception:
        return None