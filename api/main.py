"""
GLM Chat API — FastAPI backend
Supports: chat completion, web search (Z.AI API), web reader (Z.AI API),
          function calling with agentic loop, exponential-backoff retry on 429.
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

load_dotenv()

app = FastAPI(title="GLM Chat API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_API_BASE = "https://api.z.ai/api"

ALLOWED_MODELS = {"glm-4.7-flash", "glm-4.5-flash", "glm-4-flash"}
DEFAULT_MODEL = "glm-4.7-flash"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
RETRY_MAX_DELAY = 30.0
MAX_TOOL_ITERATIONS = 3   # max agentic steps before forcing final answer
WEB_CONTENT_LIMIT = 6000  # chars — cap reader output to limit token usage

# ---------------------------------------------------------------------------
# Tool schemas passed to the model
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for real-time information. Use this for current events, "
            "news, facts that may have changed recently, prices, scores, or any topic "
            "that needs up-to-date data from the internet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query — be specific for better results.",
                }
            },
            "required": ["query"],
        },
    },
}

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

# ---------------------------------------------------------------------------
# Tool execution helpers (synchronous — called inside thread pool)
# ---------------------------------------------------------------------------

def _zai_headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def execute_web_search(query: str) -> dict:
    """Call Z.AI Web Search API and return structured results."""
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{ZAI_API_BASE}/paas/v4/web_search",
                headers=_zai_headers(),
                json={
                    "search_engine": "search-prime",
                    "search_query": query,
                    "count": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_results = data.get("search_result", [])
            results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "summary": r.get("content", ""),
                    "date": r.get("publish_date", ""),
                }
                for r in raw_results[:5]
            ]
            return {"success": True, "query": query, "results": results}
    except Exception as exc:
        return {"success": False, "error": str(exc), "query": query, "results": []}


def execute_web_reader(url: str) -> dict:
    """Call Z.AI Web Reader API and return page content."""
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{ZAI_API_BASE}/paas/v4/reader",
                headers=_zai_headers(),
                json={
                    "url": url,
                    "return_format": "markdown",
                    "retain_images": False,
                    "with_links_summary": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            reader_result = data.get("reader_result", {})
            content = reader_result.get("content", "")
            if len(content) > WEB_CONTENT_LIMIT:
                content = content[:WEB_CONTENT_LIMIT] + "\n\n[Content truncated]"
            return {
                "success": True,
                "url": url,
                "title": reader_result.get("title", ""),
                "description": reader_result.get("description", ""),
                "content": content,
            }
    except Exception as exc:
        return {"success": False, "error": str(exc), "url": url, "content": ""}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _friendly_error(raw: str) -> str | None:
    """None means 'rate limited — retry'. Otherwise returns user-facing message."""
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
    enable_web_search: bool = False   # opt-in (costs $0.01/use)
    enable_web_reader: bool = False   # opt-in


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
        "tools": ["web_search", "web_reader"],
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    model = request.model if request.model in ALLOWED_MODELS else DEFAULT_MODEL
    client = get_client()
    history = [{"role": m.role, "content": m.content} for m in request.messages]

    # Build the tool list based on user settings
    active_tools: list[dict] = []
    if request.enable_web_search:
        active_tools.append(WEB_SEARCH_TOOL)
    if request.enable_web_reader:
        active_tools.append(WEB_READER_TOOL)

    async def generate() -> AsyncGenerator[str, None]:
        # ── Flush first byte immediately to prevent Vercel buffering ──────────
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

            queue: asyncio.Queue = asyncio.Queue()
            got_rate_limit = False
            got_content = False

            # ── Captured variables for the thread ────────────────────────────
            _model = model
            _history = list(history)
            _request = request
            _active_tools = list(active_tools)
            _client = client

            def do_stream() -> None:
                """
                Agentic loop running in a thread:
                1. If tools enabled: make non-streaming calls to detect tool_calls.
                2. Execute tools (web_search / web_reader) and add results.
                3. Repeat until model stops calling tools or MAX_TOOL_ITERATIONS.
                4. Make a final STREAMING call for the model's answer.
                """
                nonlocal got_content
                working_messages = list(_history)
                pending_sources: list[dict] = []

                def send(event: dict) -> None:
                    loop.call_soon_threadsafe(queue.put_nowait, event)

                def finish_with_rate_limit() -> None:
                    send({"type": "_rate_limit"})

                def finish_with_error(msg: str) -> None:
                    send({"type": "error", "message": msg})

                try:
                    # ── Agentic loop ─────────────────────────────────────────
                    for iteration in range(MAX_TOOL_ITERATIONS + 1):

                        if iteration == MAX_TOOL_ITERATIONS or not _active_tools:
                            # Final pass: always streaming, no tools
                            _do_streaming_pass(
                                _client, _model, working_messages,
                                _request, send, pending_sources
                            )
                            break

                        # ── Non-streaming tool-detection pass ─────────────────
                        kwargs = {
                            "model": _model,
                            "messages": working_messages,
                            "max_tokens": min(_request.max_tokens, 1024),  # short pass
                            "temperature": _request.temperature,
                            "tools": _active_tools,
                            "tool_choice": "auto",
                        }
                        resp = _client.chat.completions.create(**kwargs)
                        choice = resp.choices[0]
                        msg = choice.message

                        has_tool_calls = bool(getattr(msg, "tool_calls", None))

                        if has_tool_calls:
                            # Add assistant message to history
                            asst_entry: dict = {
                                "role": "assistant",
                                "content": msg.content or "",
                            }
                            asst_entry["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in msg.tool_calls
                            ]
                            working_messages.append(asst_entry)

                            # Execute each tool call
                            for tc in msg.tool_calls:
                                fn = tc.function.name
                                try:
                                    args = json.loads(tc.function.arguments)
                                except Exception:
                                    args = {}

                                send({"type": "tool_call", "tool": fn, "args": args})

                                if fn == "web_search":
                                    result = execute_web_search(args.get("query", ""))
                                    # Accumulate sources for citation display
                                    if result.get("success") and result.get("results"):
                                        pending_sources.extend(result["results"])
                                    send({
                                        "type": "tool_result",
                                        "tool": "web_search",
                                        "count": len(result.get("results", [])),
                                        "success": result.get("success", False),
                                    })
                                elif fn == "web_reader":
                                    result = execute_web_reader(args.get("url", ""))
                                    send({
                                        "type": "tool_result",
                                        "tool": "web_reader",
                                        "title": result.get("title", args.get("url", "")),
                                        "success": result.get("success", False),
                                    })
                                else:
                                    result = {"error": f"Unknown tool: {fn}"}
                                    send({"type": "tool_result", "tool": fn, "success": False})

                                working_messages.append({
                                    "role": "tool",
                                    "content": json.dumps(result, ensure_ascii=False),
                                    "tool_call_id": tc.id,
                                })

                            # Continue loop to check if model wants more tools
                            continue

                        else:
                            # Model didn't call any tools → stream the final answer
                            _do_streaming_pass(
                                _client, _model, working_messages,
                                _request, send, pending_sources
                            )
                            break

                except Exception as exc:
                    raw = str(exc)
                    friendly = _friendly_error(raw)
                    if friendly is None:
                        finish_with_rate_limit()
                    else:
                        finish_with_error(friendly)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            def _do_streaming_pass(
                client, model, messages, req, send_fn, sources
            ) -> None:
                """Stream the model's final answer after any tool calls."""
                nonlocal got_content
                kwargs = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                }
                if req.enable_thinking:
                    kwargs["thinking"] = {"type": "enabled"}

                response = client.chat.completions.create(**kwargs)
                for chunk in response:
                    delta = chunk.choices[0].delta
                    reasoning = getattr(delta, "reasoning_content", None)
                    content = getattr(delta, "content", None)

                    if reasoning:
                        send_fn({"type": "thinking", "content": reasoning})
                    if content:
                        got_content = True
                        send_fn({"type": "content", "content": content})

                # After streaming is done, emit sources if any
                if sources:
                    send_fn({"type": "sources", "sources": sources})

            future = loop.run_in_executor(None, do_stream)

            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=50.0)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'The AI did not respond within 50 s. Please try again.'})}\n\n"
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

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.include_router(router)
