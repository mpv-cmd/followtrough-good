from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from backend import db
from backend.api.approve import router as approve_router
from backend.api.dashboard import router as dashboard_router
from backend.api.meetings import router as meetings_router
from backend.memory_engine import get_recent_context

try:
    from backend.semantic_memory import semantic_search
except Exception:
    semantic_search = None


load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ENV = os.getenv("ENV", "dev")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("followthrough")


def _parse_cors_origins(raw: str) -> list[str]:
    value = (raw or "*").strip()
    if value == "*":
        return ["*"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


CORS_ORIGINS = _parse_cors_origins(CORS_ORIGINS_RAW)


class CopilotRequest(BaseModel):
    question: str

    model_config = ConfigDict(extra="allow")


class CopilotResponse(BaseModel):
    answer: str


def _safe_workspace(name: str | None) -> str:
    if not name:
        return "default"
    cleaned = name.strip()
    return cleaned or "default"


def _build_context(meetings_data: list[dict[str, Any]]) -> str:
    context_blocks: list[str] = []

    for meeting in meetings_data:
        summary = meeting.get("summary", "")
        actions = meeting.get("actions", [])
        transcript = meeting.get("transcript", "")

        if isinstance(summary, dict):
            summary_text = summary.get("summary") or str(summary)
        else:
            summary_text = str(summary or "")

        actions_lines: list[str] = []
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict):
                    action_text = str(action.get("action", "")).strip()
                    owner = str(action.get("owner", "") or "").strip()
                    deadline = str(action.get("deadline", "") or "").strip()

                    if action_text:
                        extra = []
                        if owner:
                            extra.append(f"owner: {owner}")
                        if deadline:
                            extra.append(f"deadline: {deadline}")

                        if extra:
                            actions_lines.append(f"- {action_text} ({', '.join(extra)})")
                        else:
                            actions_lines.append(f"- {action_text}")

        transcript_text = str(transcript or "")[:1200]

        context_blocks.append(
            "\n".join(
                [
                    "Meeting Summary:",
                    summary_text or "None",
                    "",
                    "Actions:",
                    "\n".join(actions_lines) if actions_lines else "None",
                    "",
                    "Transcript Snippet:",
                    transcript_text or "None",
                ]
            )
        )

    return "\n\n---\n\n".join(context_blocks)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting FollowThrough API")
    db.init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down FollowThrough API")


app = FastAPI(
    title="FollowThrough API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings_router)
app.include_router(dashboard_router)
app.include_router(approve_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "FollowThrough API",
        "status": "running",
        "environment": ENV,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, bool]:
    return {"ready": True}


@app.post("/copilot", response_model=CopilotResponse)
async def copilot(
    payload: CopilotRequest,
    workspace: str = Query(default="default"),
) -> CopilotResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")

    ws = _safe_workspace(workspace)
    logger.info("Copilot question received (workspace=%s)", ws)

    meetings_data: list[dict[str, Any]] = []

    if semantic_search is not None:
        try:
            meetings_data = semantic_search(ws, question, k=5)
        except Exception:
            logger.exception("Semantic search failed for workspace=%s", ws)

    if not meetings_data:
        try:
            meetings_data = get_recent_context(ws, limit=5)
        except Exception:
            logger.exception("Context retrieval failed for workspace=%s", ws)

    if not meetings_data:
        return CopilotResponse(answer="No meetings found yet.")

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
                {
                    "role": "system",
                    "content": "You analyze company meeting knowledge.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = "No answer generated."

        return CopilotResponse(answer=answer)

    except Exception:
        logger.exception("OpenAI request failed")
        raise HTTPException(status_code=500, detail="AI response failed")