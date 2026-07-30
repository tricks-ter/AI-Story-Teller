import asyncio
import json
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from zai import ZaiClient

load_dotenv()

app = FastAPI(title="GLM Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("ZAI_API_KEY", "")
MODEL = "glm-4.7-flash"


def get_client() -> ZaiClient:
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ZAI_API_KEY is not set. Add it in your Vercel project environment variables.",
        )
    return ZaiClient(api_key=API_KEY)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MessageItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[MessageItem]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    client = get_client()
    history = [{"role": m.role, "content": m.content} for m in request.messages]

    async def generate() -> AsyncGenerator[str, None]:
        # ── Yield immediately so Vercel starts streaming the HTTP response
        # ── right away and doesn't buffer while waiting for the first byte.
        yield f"data: {json.dumps({'type': 'status', 'message': 'connected'})}\n\n"

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def do_stream() -> None:
            """Run the synchronous ZAI streaming call in a thread pool so the
            asyncio event loop stays free and we can enforce a real timeout."""
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
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"type": "thinking", "content": reasoning},
                        )
                    if content:
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"type": "content", "content": content},
                        )
            except Exception as exc:
                raw = str(exc)
                if "429" in raw or "rate limit" in raw.lower() or "1302" in raw:
                    msg = "Rate limit reached — please wait a moment and try again."
                elif "401" in raw or "1002" in raw or "authorization" in raw.lower():
                    msg = "API key error — check that ZAI_API_KEY is set correctly in Vercel."
                elif "timeout" in raw.lower():
                    msg = "The AI took too long to respond. Please try again."
                else:
                    msg = raw
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "message": msg},
                )
            finally:
                # Sentinel — tells the async consumer the stream is over
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = loop.run_in_executor(None, do_stream)

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=50.0)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'The AI did not respond within 50 seconds. Please try again.'})}\n\n"
                    break

                if item is None:  # sentinel
                    break

                yield f"data: {json.dumps(item)}\n\n"
        finally:
            # Always wait for the thread so we don't leak it
            try:
                await asyncio.wait_for(future, timeout=5.0)
            except Exception:
                pass

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


app.include_router(router)
