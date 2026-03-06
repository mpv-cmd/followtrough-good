from __future__ import annotations

import os
import json
from typing import List, Dict, Any

from openai import OpenAI

client = OpenAI()


def ask_meetings(question: str, meetings: List[Dict[str, Any]]):

    if not meetings:
        return "No meeting history yet."

    context = ""

    for m in meetings[-10:]:

        summary = m.get("summary", "")
        actions = m.get("actions", [])

        context += f"\nMEETING SUMMARY:\n{summary}\n"

        if actions:
            context += "ACTIONS:\n"
            for a in actions:
                context += f"- {a.get('action')} (deadline: {a.get('deadline')})\n"

        context += "\n"

    prompt = f"""
You are an AI assistant helping a team remember decisions and tasks from meetings.

Answer the question using ONLY the meeting history below.

If the answer isn't found say:
"I couldn't find that in the meeting history."

MEETING HISTORY
{context}

QUESTION
{question}

Answer clearly.
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return res.choices[0].message.content