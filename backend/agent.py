# =========================
# FILE: backend/agent.py
# =========================
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional
from semantic_memory import semantic_search

from openai import OpenAI

# Pick a small/fast model first. Upgrade later if you want.
_DEFAULT_MODEL = os.getenv("FOLLOWTHROUGH_AGENT_MODEL", "gpt-4o-mini")


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _json_or_raise(text: str) -> Dict[str, Any]:
    """
    The Responses API sometimes returns extra whitespace.
    This tries to parse the whole string as JSON.
    """
    text = text.strip()
    return json.loads(text)


def run_meeting_agent(
    *,
    transcript: str,
    summary: str = "",
    actions: Optional[List[Dict[str, Any]]] = None,
    decisions: Optional[List[Any]] = None,
    workspace: str = "default",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produces:
      - exec_recap
      - risks (list)
      - followups (list)
      - comms (slack_update + email_draft)
      - metadata
    """
    client = OpenAI()

    model = model or _DEFAULT_MODEL
    actions = _as_list(actions)
    decisions = _as_list(decisions)

    # Keep context tight to reduce cost + latency.
    # (If transcript is huge, you should chunk + summarize first.)
    # Retrieve relevant past meetings
    memory_context = semantic_search(workspace, summary or transcript[:500], k=3)

    memory_text = ""

    for m in memory_context:
        s = m.get("summary", "")
        acts = m.get("actions", [])

        memory_text += f"\nPrevious meeting summary:\n{s}\n"

        if acts:
            memory_text += "Tasks mentioned:\n"
            for a in acts:
                memory_text += f"- {a.get('action')}\n"

    payload = {
        "workspace": workspace,
        "summary": _safe_str(summary),
        "actions": actions[:60],
        "decisions": decisions[:40],
        "transcript": _safe_str(transcript)[:18000],
        "related_meetings": memory_text,
    }

    system = """You are FollowThrough, an autonomous meeting agent.
You produce structured JSON only. No markdown. No prose outside JSON.
Be concrete, actionable, and conservative with claims.
If information is missing, say "unknown" instead of guessing."""

    user = f"""Analyze this meeting and return ONLY JSON with this exact shape:

{{
  "exec_recap": {{
    "one_liner": string,
    "what_changed": [string],
    "key_decisions": [string],
    "open_questions": [string]
  }},
  "risks": [
    {{
      "title": string,
      "severity": "low"|"medium"|"high",
      "why": string,
      "signal": string,
      "mitigation": string
    }}
  ],
  "followups": [
    {{
      "action": string,
      "owner": string,
      "deadline": string,
      "priority": "low"|"medium"|"high",
      "source": string
    }}
  ],
  "comms": {{
    "slack_update": string,
    "email_draft": {{
      "subject": string,
      "body": string
    }}
  }},
  "metadata": {{
    "confidence": number,
    "assumptions": [string]
  }}
}}

Relevant previous meetings:
{memory_text}

Meeting input:
{json.dumps(payload, ensure_ascii=False)}
"""

    # OpenAI Python SDK 2.x (Responses API)
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )

    # Collect text output
    out_text = ""
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    out_text += c.text

    data = _json_or_raise(out_text)

    # Minimal sanity guardrails so UI doesn't explode
    if not isinstance(data, dict):
        raise ValueError("Agent returned non-object JSON.")

    data.setdefault("exec_recap", {})
    data.setdefault("risks", [])
    data.setdefault("followups", [])
    data.setdefault("comms", {})
    data.setdefault("metadata", {})

    # clamp sizes
    data["risks"] = data["risks"][:12] if isinstance(data["risks"], list) else []
    data["followups"] = data["followups"][:20] if isinstance(data["followups"], list) else []

    return data