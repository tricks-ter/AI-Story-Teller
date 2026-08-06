# api/main.py
import asyncio
import json
import os
import random
from typing import AsyncGenerator
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from zai import ZaiClient
from database import db

load_dotenv()

app = FastAPI(title="GLM Chat API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

API_KEY = os.getenv("ZAI_API_KEY", "")
ALLOWED_MODELS = {"glm-4.7-flash", "glm-4.5-flash", "glm-4-flash"}
DEFAULT_MODEL = "glm-4.7-flash"
MAX_RETRIES = 3

def _friendly_error(raw: str) -> str | None:
    if "429" in raw or "1302" in raw or "rate limit" in raw.lower(): return None
    if "401" in raw or "1002" in raw: return "API key error."
    return raw

def get_client() -> ZaiClient:
    if not API_KEY: raise HTTPException(status_code=500, detail="ZAI_API_KEY not set")
    return ZaiClient(api_key=API_KEY)

class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str = "default-session"
    messages: list[MessageItem]
    model: str = DEFAULT_MODEL
    max_tokens: int = Field(default=4096, ge=256, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=1.5)
    enable_thinking: bool = True

router = APIRouter(prefix="/api")

@app.on_event("startup")
def startup_event():
    try: db.init_tables()
    except Exception as e: print(f"DB Init Warning: {e}")

@router.get("/health")
def health():
    return {"status": "ok", "db_enabled": db.database_url is not None}

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages: raise HTTPException(status_code=400, detail="messages must not be empty")

    # Save user message
    last_msg = request.messages[-1]
    if last_msg.role == "user":
        title = last_msg.content[:50] if len(last_msg.content) > 50 else "New Chat"
        db.ensure_session(request.session_id, title)
        db.add_message(request.session_id, "user", last_msg.content)

    model = request.model if request.model in ALLOWED_MODELS else DEFAULT_MODEL
    client = get_client()
    history = [{"role": m.role, "content": m.content} for m in request.messages]
    full_assistant_content = ""

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal full_assistant_content
        yield f"data: {json.dumps({'type': 'status', 'message': 'connected'})}\n\n"
        loop = asyncio.get_event_loop()

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                delay = min(2.0 * (2 ** (attempt - 1)) + random.uniform(0.0, 1.0), 30.0)
                yield f"data: {json.dumps({'type': 'status', 'message': f'Retrying in {delay:.0f}s...'})}\n\n"
                await asyncio.sleep(delay)

            queue: asyncio.Queue = asyncio.Queue()
            got_rate_limit = False
            got_content = False

            def do_stream() -> None:
                try:
                    response = client.chat.completions.create(
                        model=model, messages=history, stream=True,
                        max_tokens=request.max_tokens, temperature=request.temperature,
                        thinking={"type": "enabled" if request.enable_thinking else "disabled"}
                    )
                    for chunk in response:
                        delta = chunk.choices[0].delta
                        content = getattr(delta, "content", None)
                        if content: loop.call_soon_threadsafe(queue.put_nowait, {"type": "content", "content": content})
                except Exception as exc:
                    friendly = _friendly_error(str(exc))
                    if friendly is None: loop.call_soon_threadsafe(queue.put_nowait, {"type": "_rate_limit"})
                    else: loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": friendly})
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            future = loop.run_in_executor(None, do_stream)
            try:
                while True:
                    item = await asyncio.wait_for(queue.get(), timeout=50.0)
                    if item is None: break
                    if item.get("type") == "_rate_limit":
                        got_rate_limit = True if not got_content else False
                        break
                    if item.get("type") == "content":
                        full_assistant_content += item.get("content", "")
                        got_content = True
                    yield f"data: {json.dumps(item)}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout'})}\n\n"
            finally:
                try: await asyncio.wait_for(future, timeout=5.0)
                except Exception: pass

            if not got_rate_limit: break
        
        # Save assistant message
        if full_assistant_content:
            db.add_message(request.session_id, "assistant", full_assistant_content)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

app.include_router(router)
