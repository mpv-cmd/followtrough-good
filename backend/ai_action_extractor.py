# backend/ai_action_extractor.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------

DEFAULT_MODEL = os.getenv("FOLLOWTHROUGH_EXTRACT_MODEL", "gpt-4o-mini")


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


# --------------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------------

def ai_extract_actions(
    transcript: str,
    *,
    max_items: int = 25
) -> Optional[List[Dict[str, Any]]]:
    """
    Extract structured action items using OpenAI.

    Returns:
        list[dict] with:
            action
            owner
            deadline
            source_sentence
            confidence
            priority (optional)

    Returns None if:
        - OpenAI key missing
        - model fails
    """

    if not transcript or not transcript.strip():
        return []

    if not _has_openai_key():
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI()

    schema_hint = {
        "actions": [
            {
                "action": "string",
                "owner": "string or null",
                "deadline": "YYYY-MM-DD or null",
                "source_sentence": "string",
                "confidence": "0-1",
                "priority": "low|medium|high"
            }
        ]
    }

    prompt = f"""
Extract action items from this meeting transcript.

Rules:

• Split combined tasks into separate items
• Normalize actions into concise commands

Examples:
"We'll send the proposal and review it tomorrow"
→
1. Send proposal
2. Review proposal tomorrow

Owner rules:
• If transcript uses "Name:"
• If sentence says "Name will..."
• If sentence says "Name to..."
• Otherwise null

Deadline rules:
• Convert to YYYY-MM-DD
• "tomorrow" → tomorrow
• "next week" → +7 days
• If unknown → null

Confidence:
0–1

Priority:
• high → urgent tasks
• medium → normal
• low → minor tasks

Return JSON ONLY:

{json.dumps(schema_hint, ensure_ascii=False)}

Transcript:
\"\"\"
{transcript.strip()}
\"\"\"
"""

    try:

        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You extract structured action items from meeting transcripts."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        actions = data.get("actions", [])

        if not isinstance(actions, list):
            return []

        cleaned: List[Dict[str, Any]] = []

        for a in actions[:max_items]:

            if not isinstance(a, dict):
                continue

            action = str(a.get("action") or "").strip()

            if not action:
                continue

            cleaned.append({
                "action": action,
                "owner": a.get("owner") if a.get("owner") not in ("", None) else None,
                "deadline": a.get("deadline") if a.get("deadline") not in ("", None) else None,
                "source_sentence": str(a.get("source_sentence") or "").strip() or action,
                "confidence": float(a.get("confidence") or 0.75),
                "priority": a.get("priority", "medium")
            })

        return cleaned

    except Exception as e:

        print("AI extraction failed:", e)

        return None