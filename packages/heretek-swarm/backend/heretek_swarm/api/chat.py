"""Chat streaming endpoint for the dashboard's Vercel AI SDK surface.

Provides an SSE endpoint that streams an agent's LLM output as
plain-text chunks, matching the ``TextStreamChatTransport`` contract
from the Vercel AI SDK. The endpoint delegates to the pydantic-ai-backed
``ModelGarage.stream`` so the LLM path stays consistent with the rest
of the swarm (no separate transport).

The endpoint is additive: existing ``/api/...`` routers are unchanged.
If the swarm has no LLM providers configured, the endpoint responds
with a clear SSE error frame rather than crashing.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from heretek_swarm_core.llm.model_garage import (
    ChatMessage,
    LLMRequest,
    ModelGarage,
    get_model_garage,
)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatTurn(BaseModel):
    """A single turn in the chat conversation."""

    role: str = Field(..., description="system|user|assistant")
    content: str


class ChatRequest(BaseModel):
    """Request body for the chat SSE endpoint.

    The frontend's ``TextStreamChatTransport`` sends the message list
    under a single key (configurable via ``prepareSendMessagesRequest``);
    this endpoint accepts a flat ``messages`` list of ``{role, content}``
    pairs to keep the contract minimal.
    """

    messages: list[ChatTurn]
    model: str | None = None
    provider_id: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


def _sse_format(event: str, data: str) -> str:
    """Format a single SSE frame."""
    return f"event: {event}\ndata: {data}\n\n"


async def _stream_chat(req: ChatRequest, garage: ModelGarage) -> AsyncIterator[str]:
    """Yield SSE frames for one chat turn.

    Yields ``token`` frames containing raw text chunks (compatible with
    ``TextStreamChatTransport``), then a final ``done`` frame.
    On error, yields a single ``error`` frame and exits.
    """
    if not req.messages:
        yield _sse_format("error", json.dumps({"message": "messages is required"}))
        return

    messages = [
        ChatMessage(role=m.role, content=m.content) for m in req.messages
    ]
    request = LLMRequest(
        messages=messages,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )

    try:
        async for token in garage.stream(
            messages=request.messages,
            model=request.model,
            provider_id=req.provider_id,
        ):
            yield _sse_format("token", token)
    except Exception as exc:  # noqa: BLE001 - surfaced to client via SSE
        yield _sse_format("error", json.dumps({"message": str(exc)}))
        return

    yield _sse_format("done", json.dumps({"ok": True}))


@router.post("/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream an agent's LLM output via SSE.

    Compatible with the Vercel AI SDK's ``TextStreamChatTransport``:
    each token is emitted as ``event: token / data: <chunk>``, and the
    stream terminates with a ``done`` frame.
    """
    try:
        garage = get_model_garage()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"LLM stack unavailable: {exc}",
        ) from exc

    return StreamingResponse(
        _stream_chat(req, garage),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
