import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.service import AssistantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

CHAT_FAILED_DETAIL = "The assistant could not process this message. Please try again shortly."


def get_assistant(request: Request) -> AssistantService:
    return request.app.state.assistant


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest, assistant: AssistantService = Depends(get_assistant)
) -> ChatResponse:
    try:
        return await assistant.chat(body.user_id, body.message)
    except Exception:
        logger.exception("Chat turn failed for user_id=%s", body.user_id)
        raise HTTPException(status_code=503, detail=CHAT_FAILED_DETAIL) from None


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest, assistant: AssistantService = Depends(get_assistant)
) -> StreamingResponse:
    """Server-Sent Events: `token`, `tool_call`, then a final `done` (same shape as /chat)."""

    async def events() -> AsyncIterator[str]:
        try:
            async for event, data in assistant.stream_chat(body.user_id, body.message):
                yield format_sse(event, {"text": data} if event == "token" else data)
        except Exception:
            logger.exception("Streaming chat turn failed for user_id=%s", body.user_id)
            yield format_sse("error", {"detail": CHAT_FAILED_DETAIL})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def format_sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data))}\n\n"
