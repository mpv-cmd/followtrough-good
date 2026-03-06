# backend/summarize_meeting.py

from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional


DEFAULT_MODEL = os.getenv("FOLLOWTHROUGH_SUMMARY_MODEL", "gpt-4o-mini")


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def summarize_meeting(transcript: str) -> Optional[Dict[str, Any]]:
    """
    Generates structured meeting summary.

    Returns:
    {
        summary: str
        decisions: list[str]
        risks: list[str]
        key_points: list[str]
    }
    """

    if not transcript or not transcript.strip():
        return None

    if not _has_openai_key():
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI()

    schema = {
        "summary": "short paragraph",
        "decisions": ["list of decisions"],
        "key_points": ["important discussion points"],
        "risks": ["potential risks or blockers"]
    }

    prompt = f"""
Summarize this meeting transcript.

Return JSON only.

Structure:

{json.dumps(schema, ensure_ascii=False)}

Rules:
• Summary should be concise
• Decisions should be concrete outcomes
• Key points are important topics discussed
• Risks are blockers or unresolved problems

Transcript:
\"\"\"
{transcript}
\"\"\"
"""

    try:

        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You summarize meetings clearly and concisely."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = resp.choices[0].message.content or "{}"

        data = json.loads(content)

        return {
            "summary": data.get("summary", ""),
            "decisions": data.get("decisions", []),
            "key_points": data.get("key_points", []),
            "risks": data.get("risks", [])
        }

    except Exception as e:

        print("Meeting summary failed:", e)

        return None