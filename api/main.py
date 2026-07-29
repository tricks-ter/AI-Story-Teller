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

# Allow all origins so the API works from any frontend origin
# (same-domain Vercel deployment, local dev, or external frontends).
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
    # Full conversation history sent by the client (role + content only).
    # Session storage is handled entirely on the frontend via localStorage.
    messages: list[MessageItem]


# ---------------------------------------------------------------------------
# Router — all routes under /api prefix
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages array must not be empty")

    client = get_client()

    history = [{"role": m.role, "content": m.content} for m in request.messages]

    async def generate() -> AsyncGenerator[str, None]:
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
