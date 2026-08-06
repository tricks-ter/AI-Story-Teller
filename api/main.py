"""
GLM Chat API — FastAPI backend v4
  - Built-in Z.AI web search tool (type: "web_search") → zero extra API calls
  - Web reader via function calling + agentic loop (1 iteration max)
  - Exponential-backoff retry on 429 rate limits
"""
import asyncio
import json
import os
import random
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from zai import ZaiClient
from database import db

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="GLM Chat API", version="4.0.0")

app = FastAPI(title="GLM Chat API", version="2.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

API_KEY      = os.getenv("ZAI_API_KEY", "")
ZAI_API_BASE = "https://api.z.ai/api"

ALLOWED_MODELS = {"glm-4.7-flash", "glm-4.5-flash", "glm-4-flash"}
DEFAULT_MODEL  = "glm-4.7-flash"

MAX_RETRIES        = 3
RETRY_BASE_DELAY   = 2.0
RETRY_MAX_DELAY    = 30.0
MAX_READER_ITERS   = 2    # max tool-call iterations for web reader
WEB_CONTENT_LIMIT  = 6000 # chars — cap reader output to limit tokens

# ── Built-in web search tool (handled natively by Z.AI, not a function call) ──
def _make_web_search_tool() -> dict:
    return {
        "type": "web_search",
        "web_search": {
            "enable": "True",
            "search_engine": "search-prime",
            "search_result": "True",
            "count": "5",
        },
    }

# ── Web reader as a function-call tool ────────────────────────────────────────
WEB_READER_TOOL = {
    "type": "function",
    "function": {
        "name": "web_reader",
        "description": (
            "Read and extract the full text content from a URL or webpage. "
            "Use this when the user shares a URL and asks about its content, "
            "or when you need to read a specific webpage in detail."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to read (must start with http:// or https://).",
                }
            },
            "required": ["url"],
        },
    },
}


# ── Tool executor ──────────────────────────────────────────────────────────────

def execute_web_reader(url: str) -> dict:
    """Call Z.AI Web Reader API and return page markdown content."""
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{ZAI_API_BASE}/paas/v4/reader",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "return_format": "markdown",
                    "retain_images": False,
                    "with_links_summary": False,
                },
            )
            data = resp.json()
            if "error" in data:
                return {
                    "success": False,
                    "error": data["error"].get("message", "Reader API error"),
                    "url": url,
                    "content": f"Could not read this URL. Error: {data['error'].get('message', 'unknown')}",
                }
            resp.raise_for_status()
            reader_result = data.get("reader_result", {})
            content = reader_result.get("content", "")
            if len(content) > WEB_CONTENT_LIMIT:
                content = content[:WEB_CONTENT_LIMIT] + "\n\n[Content truncated]"
            return {
                "success": True,
                "url": url,
                "title": reader_result.get("title", ""),
                "description": reader_result.get("description", ""),
                "content": content or "No content extracted from this URL.",
            }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "url": url,
            "content": f"Failed to read URL: {exc}",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _friendly_error(raw: str) -> str | None:
    """Return None → rate limited (retry). Otherwise return user-facing message."""
    if "429" in raw or "1302" in raw or "rate limit" in raw.lower():
        return None
    if "401" in raw or "1002" in raw or "authorization" in raw.lower():
        return "API key error — check ZAI_API_KEY in Vercel environment variables."
    if "timeout" in raw.lower():
        return "The AI took too long to respond. Please try again."
    return raw


def get_client() -> ZaiClient:
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ZAI_API_KEY is not set — add it in Vercel → Settings → Environment Variables.",
        )
    return ZaiClient(api_key=API_KEY)


# ── Pydantic models ───────────────────────────────────────────────────────────

class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages:           list[MessageItem]
    model:              str   = DEFAULT_MODEL
    max_tokens:         int   = Field(default=4096, ge=256, le=8192)
    temperature:        float = Field(default=0.7, ge=0.0, le=1.5)
    enable_thinking:    bool  = True
    enable_web_search:  bool  = False  # built-in tool — $0.01/use on Z.AI
    enable_web_reader:  bool  = False  # function-call tool — reads URLs


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {
        "status": "ok",
        "models": sorted(ALLOWED_MODELS),
        "default_model": DEFAULT_MODEL,
        "tools": ["web_search (built-in)", "web_reader (function-call)"],
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages: raise HTTPException(status_code=400, detail="messages must not be empty")
    last_msg = request.messages[-1]
    if last_msg.role == "user":
        db.ensure_session(request.session_id, last_msg.content[:50] if len(last_msg.content) > 50 else "New Chat")
        db.add_message(request.session_id, "user", last_msg.content)

    model  = request.model if request.model in ALLOWED_MODELS else DEFAULT_MODEL
    client = get_client()
    history = [{"role": m.role, "content": m.content} for m in request.messages]
    full_content = ""

    async def generate() -> AsyncGenerator[str, None]:
        # ── Flush first byte so Vercel starts streaming immediately ───────────
        yield f"data: {json.dumps({'type': 'status', 'message': 'connected'})}\n\n"

        loop = asyncio.get_event_loop()

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                delay = min(
                    RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0.0, 1.0),
                    RETRY_MAX_DELAY,
                )
                yield f"data: {json.dumps({'type': 'status', 'message': f'Rate limited. Retrying in {delay:.0f}s (attempt {attempt}/{MAX_RETRIES})…'})}\n\n"
                await asyncio.sleep(delay)

            queue:          asyncio.Queue = asyncio.Queue()
            got_rate_limit: bool          = False
            got_content:    bool          = False

            _model      = model
            _history    = list(history)
            _request    = request
            _client     = client

            def do_stream() -> None:
                nonlocal got_content

                working_messages = list(_history)

                def send(ev: dict) -> None:
                    loop.call_soon_threadsafe(queue.put_nowait, ev)

                try:
                    # ── Build tool list ───────────────────────────────────────
                    # Built-in web_search: passed directly to chat completion
                    # web_reader: function-call tool requiring an agentic loop
                    builtin_tools   = [_make_web_search_tool()] if _request.enable_web_search else []
                    function_tools  = [WEB_READER_TOOL]         if _request.enable_web_reader  else []

                    # ── Web-reader agentic loop ───────────────────────────────
                    if function_tools:
                        for iteration in range(MAX_READER_ITERS):
                            # Non-streaming pass to detect function tool_calls
                            kwargs: dict = {
                                "model":       _model,
                                "messages":    working_messages,
                                "max_tokens":  min(_request.max_tokens, 2048),
                                "temperature": _request.temperature,
                                "tools":       function_tools + builtin_tools,
                                "tool_choice": "auto",
                            }
                            resp  = _client.chat.completions.create(**kwargs)
                            choice = resp.choices[0]
                            msg    = choice.message

                            fn_calls = [
                                tc for tc in (getattr(msg, "tool_calls", None) or [])
                                if tc.function.name == "web_reader"
                            ]

                            if fn_calls:
                                # Add assistant message with tool_calls
                                asst: dict = {
                                    "role":    "assistant",
                                    "content": msg.content or "",
                                    "tool_calls": [
                                        {
                                            "id": tc.id,
                                            "type": "function",
                                            "function": {
                                                "name":      tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                        for tc in fn_calls
                                    ],
                                }
                                working_messages.append(asst)

                                for tc in fn_calls:
                                    try:
                                        args = json.loads(tc.function.arguments)
                                    except Exception:
                                        args = {}
                                    url = args.get("url", "")

                                    send({"type": "tool_call", "tool": "web_reader", "args": {"url": url}})
                                    result = execute_web_reader(url)
                                    send({
                                        "type":    "tool_result",
                                        "tool":    "web_reader",
                                        "title":   result.get("title", url),
                                        "success": result.get("success", False),
                                    })
                                    working_messages.append({
                                        "role":        "tool",
                                        "content":     json.dumps(result, ensure_ascii=False),
                                        "tool_call_id": tc.id,
                                    })

                                if iteration < MAX_READER_ITERS - 1:
                                    continue  # give model another pass
                            # No function tool calls — fall through to final stream
                            break

                    # ── Final streaming pass ──────────────────────────────────
                    # Include built-in web_search here so the model can search
                    # during generation (the API handles it internally).
                    stream_kwargs: dict = {
                        "model":       _model,
                        "messages":    working_messages,
                        "stream":      True,
                        "max_tokens":  _request.max_tokens,
                        "temperature": _request.temperature,
                    }
                    if _request.enable_thinking:
                        stream_kwargs["thinking"] = {"type": "enabled"}
                    if builtin_tools:
                        stream_kwargs["tools"] = builtin_tools

                    stream_resp = _client.chat.completions.create(**stream_kwargs)

                    if _request.enable_web_search:
                        send({"type": "tool_call", "tool": "web_search", "args": {"query": "…"}})

                    for chunk in stream_resp:
                        delta     = chunk.choices[0].delta
                        reasoning = getattr(delta, "reasoning_content", None)
                        content   = getattr(delta, "content",           None)

                        if reasoning:
                            send({"type": "thinking", "content": reasoning})
                        if content:
                            got_content = True
                            send({"type": "content",  "content": content})

                    if _request.enable_web_search:
                        # Notify frontend that web search completed (results are inline)
                        send({"type": "tool_result", "tool": "web_search", "inline": True, "success": True})

                except Exception as exc:
                    raw     = str(exc)
                    friendly = _friendly_error(raw)
                    if friendly is None:
                        loop.call_soon_threadsafe(queue.put_nowait, {"type": "_rate_limit"})
                    else:
                        loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": friendly})
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            future = loop.run_in_executor(None, do_stream)

            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=55.0)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'The AI did not respond within 55 s. Please try again.'})}\n\n"
                        got_rate_limit = False
                        break

                    if item is None:
                        break

                    if item.get("type") == "_rate_limit":
                        if got_content:
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
                break
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Rate limit still active after {MAX_RETRIES} retries. Please wait a minute and try again.'})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

app.include_router(router)
