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

load_dotenv()

app = FastAPI(title="GLM Chat API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("ZAI_API_KEY", "")

ALLOWED_MODELS = {
    "glm-4.7-flash",
    "glm-4.5-flash",
    "glm-4-flash",
}
DEFAULT_MODEL = "glm-4.7-flash"

# Maximum retry attempts on rate-limit (429 / code 1302)
MAX_RETRIES = 3
# Base delay in seconds; actual delay = base * 2^attempt + jitter
RETRY_BASE_DELAY = 2.0
RETRY_MAX_DELAY = 30.0


def _friendly_error(raw: str) -> str | None:
    """Return None if this is a rate-limit error (caller will retry),
    otherwise return a human-readable error string."""
    if "429" in raw or "1302" in raw or "rate limit" in raw.lower():
        return None  # signal: rate limited → retry
    if "401" in raw or "1002" in raw or "authorization" in raw.lower():
        return "API key error — check ZAI_API_KEY in your Vercel environment variables."
    if "timeout" in raw.lower():
        return "The AI took too long to respond. Please try again."
    return raw


def get_client() -> ZaiClient:
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ZAI_API_KEY is not set. Add it in Vercel → Settings → Environment Variables.",
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
    model: str = DEFAULT_MODEL
    max_tokens: int = Field(default=4096, ge=256, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=1.5)
    enable_thinking: bool = True


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {
        "status": "ok",
        "models": sorted(ALLOWED_MODELS),
        "default_model": DEFAULT_MODEL,
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    model = request.model if request.model in ALLOWED_MODELS else DEFAULT_MODEL
    client = get_client()
    history = [{"role": m.role, "content": m.content} for m in request.messages]

    async def generate() -> AsyncGenerator[str, None]:
        # ── Flush first byte immediately so Vercel starts streaming ──────────
        yield f"data: {json.dumps({'type': 'status', 'message': 'connected'})}\n\n"

        loop = asyncio.get_event_loop()

        for attempt in range(MAX_RETRIES + 1):
            # Exponential back-off with jitter between retries
            if attempt > 0:
                delay = min(
                    RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0.0, 1.0),
                    RETRY_MAX_DELAY,
                )
                retry_msg = (
                    f"Rate limited. Retrying in {delay:.0f}s "
                    f"(attempt {attempt}/{MAX_RETRIES})…"
                )
                yield f"data: {json.dumps({'type': 'status', 'message': retry_msg})}\n\n"
                await asyncio.sleep(delay)

            queue: asyncio.Queue = asyncio.Queue()
            got_rate_limit = False
            got_content = False

            def do_stream() -> None:
                """Synchronous ZAI API call — runs in a thread pool so the
                asyncio event loop remains free for timeouts and yields."""
                try:
                    kwargs: dict = {
                        "model": model,
                        "messages": history,
                        "stream": True,
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature,
                    }
                    # Reasoning / thinking mode
                    kwargs["thinking"] = {
                        "type": "enabled" if request.enable_thinking else "disabled"
                    }

                    response = client.chat.completions.create(**kwargs)

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
                    friendly = _friendly_error(str(exc))
                    if friendly is None:
                        # Rate-limit — signal the async side to retry
                        loop.call_soon_threadsafe(
                            queue.put_nowait, {"type": "_rate_limit"}
                        )
                    else:
                        loop.call_soon_threadsafe(
                            queue.put_nowait, {"type": "error", "message": friendly}
                        )
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            future = loop.run_in_executor(None, do_stream)

            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=50.0)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'The AI did not respond within 50 s. Please try again.'})}\n\n"
                        got_rate_limit = False
                        break

                    if item is None:  # sentinel — stream finished
                        break

                    if item.get("type") == "_rate_limit":
                        if got_content:
                            # Already sent partial content — don't retry mid-stream
                            yield f"data: {json.dumps({'type': 'error', 'message': 'Rate limited mid-stream. Please retry.'})}\n\n"
                            got_rate_limit = False
                        else:
                            got_rate_limit = True
                        break

                    if item["type"] in ("thinking", "content"):
                        got_content = True

                    yield f"data: {json.dumps(item)}\n\n"
            finally:
                try:
                    await asyncio.wait_for(future, timeout=5.0)
                except Exception:
                    pass

            if not got_rate_limit:
                break  # success or non-retryable error — stop the retry loop
        else:
            # Exhausted all retries
            yield f"data: {json.dumps({'type': 'error', 'message': f'Rate limit still active after {MAX_RETRIES} retries. Please wait a minute and try again.'})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.include_router(router)
