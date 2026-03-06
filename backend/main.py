from __future__ import annotations

import os
import logging
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import db
from backend.api import meetings
from backend.api import tasks
from backend.api import company
from backend.api import agent
from backend.api import analytics
from backend.memory_engine import get_recent_context

try:
    from backend.semantic_memory import semantic_search
except Exception:
    semantic_search = None


load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("followthrough")

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
    name = name.strip()
    return name or "default"


def _build_context(meetings_data: List[Dict[str, Any]]) -> str:
    context_blocks = []

    for m in meetings_data:
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

        transcript_snippet = transcript[:1200] if transcript else ""

        context_blocks.append(
            f"""
Meeting Summary:
{summary_text}

Actions:
{actions_text if actions_text else "None"}

Transcript Snippet:
{transcript_snippet if transcript_snippet else "None"}
""".strip()
        )

    return "\n\n---\n\n".join(context_blocks)


@app.on_event("startup")
def startup():
    logger.info("Starting FollowThrough API")
    db.init_db()
    logger.info("Database initialized")


@app.get("/")
def root():
    return {
        "service": "FollowThrough API",
        "status": "running",
        "environment": os.getenv("ENV", "dev"),
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

    logger.info(f"Copilot question received (workspace={ws})")

    meetings_data: List[Dict[str, Any]] = []

    if semantic_search:
        try:
            meetings_data = semantic_search(ws, question, k=5)
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")

    if not meetings_data:
        try:
            meetings_data = get_recent_context(ws, limit=5)
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")

    if not meetings_data:
        return {"answer": "No meetings found yet."}

    context_text = _build_context(meetings_data)

    prompt = f"""
You are FollowThrough AI, an assistant for company meetings.

Use ONLY the meeting knowledge below to answer the question.
If the answer is not in the context, say you are not sure.

MEETING KNOWLEDGE:
{context_text}

QUESTION:
{question}

Provide a clear, concise, practical answer.
""".strip()

    try:
        from openai import OpenAI

        client = OpenAI()

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You analyze company meeting knowledge."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        answer = response.choices[0].message.content or "No answer generated."
        return {"answer": answer}

    except Exception as e:
        logger.error(f"OpenAI request failed: {e}")
        raise HTTPException(status_code=500, detail="AI response failed")


app.include_router(meetings.router)
app.include_router(tasks.router)
app.include_router(company.router)
app.include_router(agent.router)
app.include_router(analytics.router)