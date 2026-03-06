from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import db
from api import meetings
from api import tasks
from api import company
from api import agent
from api import analytics
from memory_engine import get_recent_context
from semantic_memory import semantic_search

load_dotenv()

app = FastAPI(
    title="FollowThrough AI",
    version="1.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _safe_workspace(name: str) -> str:
    if not name:
        return "default"
    return name.strip() or "default"


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/")
def root():
    return {
        "service": "FollowThrough API",
        "status": "running",
        "env": os.getenv("ENV", "dev"),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"ready": True}


@app.post("/copilot")
async def copilot(payload: Dict[str, Any], workspace: str = "default"):
    question = (payload.get("question") or "").strip()

    if not question:
        raise HTTPException(status_code=400, detail="Missing question")

    ws = _safe_workspace(workspace)

    # Use semantic search first for better relevance and speed
    meetings = semantic_search(ws, question, k=5)

    # Fallback if semantic memory is empty
    if not meetings:
        meetings = get_recent_context(ws, limit=5)

    if not meetings:
        return {"answer": "No meetings found yet."}

    context_blocks = []

    for m in meetings:
        summary = m.get("summary", "")
        actions = m.get("actions", [])
        transcript = m.get("transcript", "")

        if isinstance(summary, dict):
            summary_text = summary.get("summary") or str(summary)
        else:
            summary_text = str(summary)

        actions_text = "\n".join(
            f"- {a.get('action', 'Unknown action')}"
            for a in actions
            if isinstance(a, dict)
        )

        snippet = transcript[:1500] if transcript else ""

        context_blocks.append(
            f"""
Meeting Summary:
{summary_text}

Actions:
{actions_text if actions_text else "None"}

Transcript Snippet:
{snippet if snippet else "None"}
""".strip()
        )

    context_text = "\n\n---\n\n".join(context_blocks)

    prompt = f"""
You are FollowThrough AI, an assistant for company meetings.

Use only the meeting knowledge below to answer the question.
If the answer is not in the context, say you are not sure.

MEETING KNOWLEDGE:
{context_text}

QUESTION:
{question}

Answer clearly, concisely, and practically.
""".strip()

    from openai import OpenAI

    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You analyze company meeting knowledge."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    answer = response.choices[0].message.content or "No answer generated."

    return {"answer": answer}


# ROUTERS
app.include_router(meetings.router)
app.include_router(tasks.router)
app.include_router(company.router)
app.include_router(agent.router)
app.include_router(analytics.router)