from __future__ import annotations

import json
import os
from typing import Any, Dict

DEFAULT_MODEL = os.getenv("FOLLOWTHROUGH_SUMMARY_MODEL", "gpt-4o-mini")


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)

    return out


def _fallback_summary(transcript: str) -> Dict[str, Any]:
    cleaned = " ".join((transcript or "").strip().split())
    short = cleaned[:500]

    return {
        "title": "Meeting Summary",
        "summary": short if short else "No summary available.",
        "decisions": [],
        "key_points": [],
        "risks": [],
        "next_steps": [],
    }


def summarize_meeting(transcript: str) -> Dict[str, Any]:
    """
    Generate a structured meeting summary.

    Returns:
    {
        "title": str,
        "summary": str,
        "decisions": list[str],
        "key_points": list[str],
        "risks": list[str],
        "next_steps": list[str]
    }
    """

    if not transcript or not transcript.strip():
        return _fallback_summary(transcript)

    if not _has_openai_key():
        return _fallback_summary(transcript)

    try:
        from openai import OpenAI
    except Exception:
        return _fallback_summary(transcript)

    client = OpenAI()

    schema = {
        "title": "short meeting title",
        "summary": "short paragraph",
        "decisions": ["list of decisions"],
        "key_points": ["important discussion points"],
        "risks": ["potential risks or blockers"],
        "next_steps": ["clear next steps"],
    }

    prompt = f"""
Summarize this meeting transcript.

Return valid JSON only.

Required structure:
{json.dumps(schema, ensure_ascii=False)}

Rules:
- title: very short and specific
- summary: concise, practical paragraph
- decisions: concrete outcomes only
- key_points: major topics discussed
- risks: blockers, uncertainties, unresolved concerns
- next_steps: actionable follow-up items
- if a section has nothing, return an empty list
- do not include markdown
- do not include any text outside the JSON

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
                    "content": "You summarize business meetings into clean structured JSON.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        return {
            "title": str(data.get("title") or "Meeting Summary").strip() or "Meeting Summary",
            "summary": str(data.get("summary") or "").strip(),
            "decisions": _clean_list(data.get("decisions")),
            "key_points": _clean_list(data.get("key_points")),
            "risks": _clean_list(data.get("risks")),
            "next_steps": _clean_list(data.get("next_steps")),
        }

    except Exception as e:
        print("Meeting summary failed:", e)
        return _fallback_summary(transcript)