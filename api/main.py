import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from zai import ZaiClient

load_dotenv()

app = FastAPI(title="GLM Chat API", version="1.0.0")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DATA_DIR defaults to /tmp so chat_history.json is writable on Vercel
# (only /tmp is writable in Vercel serverless functions).
# Override via env var for persistent storage on other hosts (e.g. DATA_DIR=/data on Render).
_data_dir = Path(os.getenv("DATA_DIR", "/tmp"))
DB_PATH = _data_dir / "chat_history.json"
API_KEY = os.getenv("ZAI_API_KEY", "")
MODEL = "glm-4.7-flash"


def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sessions": {}}


def save_db(data: dict) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_client() -> ZaiClient:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="ZAI_API_KEY is not configured. Please set it in .env")
    return ZaiClient(api_key=API_KEY)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class CreateSessionResponse(BaseModel):
    session_id: str
    created_at: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    title: str
    message_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session():
    db = load_db()
    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db["sessions"][session_id] = {
        "session_id": session_id,
        "created_at": now,
        "title": "New Chat",
        "messages": [],
    }
    save_db(db)
    return {"session_id": session_id, "created_at": now}


@app.get("/sessions")
def list_sessions():
    db = load_db()
    sessions = []
    for s in db["sessions"].values():
        sessions.append({
            "session_id": s["session_id"],
            "created_at": s["created_at"],
            "title": s.get("title", "Chat"),
            "message_count": len(s["messages"]),
        })
    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return {"sessions": sessions}


@app.get("/sessions/{session_id}/messages")
def get_messages(session_id: str):
    db = load_db()
    session = db["sessions"].get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": session["messages"]}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    db = load_db()
    if session_id not in db["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    del db["sessions"][session_id]
    save_db(db)
    return {"status": "deleted"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    db = load_db()

    # Create session if not provided
    if not request.session_id or request.session_id not in db["sessions"]:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        db["sessions"][session_id] = {
            "session_id": session_id,
            "created_at": now,
            "title": request.message[:40] + ("..." if len(request.message) > 40 else ""),
            "messages": [],
        }
    else:
        session_id = request.session_id

    session = db["sessions"][session_id]

    # Build message history for the API
    history = [{"role": m["role"], "content": m["content"]} for m in session["messages"]]
    history.append({"role": "user", "content": request.message})

    # Persist user message immediately
    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    session["messages"].append(user_msg)

    # Update title from first user message
    if len(session["messages"]) == 1:
        session["title"] = request.message[:50] + ("..." if len(request.message) > 50 else "")

    save_db(db)

    client = get_client()

    async def generate() -> AsyncGenerator[str, None]:
        # Send session_id first so the client can track it
        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

        full_content = ""
        thinking_content = ""

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=history,
                stream=True,
                max_tokens=4096,
                temperature=0.7,
            )

            for chunk in response:
                delta = chunk.choices[0].delta

                reasoning = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)

                if reasoning:
                    thinking_content += reasoning
                    yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning})}\n\n"

                if content:
                    full_content += content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Persist assistant message
        assistant_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": full_content,
            "thinking": thinking_content or None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        db2 = load_db()
        db2["sessions"][session_id]["messages"].append(assistant_msg)
        save_db(db2)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
