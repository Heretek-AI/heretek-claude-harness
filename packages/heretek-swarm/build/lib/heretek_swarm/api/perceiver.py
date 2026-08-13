"""
Perceiver REST API

Provides endpoints for:
- POST /api/perceiver/analyze — submit a file for multi-modal perception analysis

The endpoint routes through the PerceiverAgent actor in the supervisor,
decoding uploaded files and returning structured features per detected modality.
"""

import asyncio
import base64
import mimetypes
import types
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from heretek_swarm.actors.base import ActorMessage
from heretek_swarm.actors.supervisor import get_supervisor
from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/perceiver", tags=["perceiver"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class PerceiverResponse(BaseModel):
    """Structured response from the Perceiver analysis endpoint."""

    input_id: str = Field(
        ..., description="Unique identifier for this input"
    )
    modality: str = Field(
        ..., description="Detected or provided modality (text, image, audio, video, document)"
    )
    features: dict[str, Any] = Field(
        ..., description="Extracted features per modality"
    )
    quality_score: float = Field(
        ..., description="Input quality assessment (0.0 - 1.0)"
    )
    llm_description: str | None = Field(
        None, description="Optional LLM-generated description of the input"
    )
    timestamp: str = Field(..., description="ISO-8601 processing timestamp")


class PerceiverError(BaseModel):
    """Structured error response."""

    error: str = Field(..., description="Human-readable error message")
    detail: str | None = Field(None, description="Additional error context")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_mime_type(filename: str) -> str:
    """Infer MIME type from filename extension via stdlib mimetypes."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def _format_from_filename(filename: str) -> str | None:
    """Extract lower-cased file extension from a filename, or None."""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return None


def _build_data_url(file_bytes: bytes, mime_type: str) -> str:
    """Encode raw bytes as a ``data:...;base64,...`` URL string."""
    b64 = base64.b64encode(file_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=PerceiverResponse,
    responses={
        200: {"description": "Successful analysis"},
        400: {"model": PerceiverError, "description": "Missing or empty file"},
        500: {"model": PerceiverError, "description": "Processing failure"},
        503: {"model": PerceiverError, "description": "Perceiver agent not available"},
    },
)
async def analyze_file(
    authenticated: str = Depends(verify_auth),
    file: UploadFile = File(
        ..., description="File to analyze (text, image, audio, video, or document)"
    ),
    modality: str | None = Form(
        None,
        description="Optional modality hint (text, image, audio, video, document)",
    ),
) -> PerceiverResponse:
    """
    Submit a file for multi-modal perception analysis.

    Reads the uploaded file, detects modality from extension/content,
    routes through the PerceiverAgent actor, and returns structured features.

    **Example (curl):**

        curl -X POST http://localhost:8000/api/perceiver/analyze \\
             -F 'file=@test.jpg' \\
             -F 'modality=image'

    **Response:**

    ```json
    {
      "input_id": "input_image_20250101000000_abc123def",
      "modality": "image",
      "features": {
        "dimensions": {"width": 1920, "height": 1080},
        "mode": "RGB",
        "channels": 3,
        "color_stats": {...},
        "dominant_color_rgb": [120, 80, 60]
      },
      "quality_score": 1.0,
      "llm_description": null,
      "timestamp": "2025-01-01T00:00:00+00:00"
    }
    ```
    """
    # 1. Read file content
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "No filename provided", "detail": None},
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        logger.exception("perceiver_file_read_failed", filename=file.filename)
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to read uploaded file: {exc}", "detail": str(exc)},
        ) from exc

    if not file_bytes:
        raise HTTPException(status_code=400, detail={"error": "Empty file", "detail": None})

    # 2. Determine format hint and MIME type
    fmt_hint = _format_from_filename(file.filename)
    mime_type = _detect_mime_type(file.filename)

    # 3. Look up PerceiverAgent from supervisor
    supervisor = get_supervisor()
    perceiver = supervisor.actors.get("perceiver")
    if perceiver is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Perceiver agent not available",
                "detail": "Agent has not been spawned yet",
            },
        )

    # 4. Build data URL for the agent
    input_data = _build_data_url(file_bytes, mime_type)

    # 5. Construct ActorMessage for the perceiver
    task = asyncio.current_task()
    task_name = task.get_name() if task else "unknown"
    reply_topic = f"api:perceiver:{id(file)}:{task_name}"

    message = ActorMessage(
        sender="api:perceiver",
        message_type="process_input",
        content={
            "input_data": input_data,
            "modality": modality,
            "format": fmt_hint,
            "metadata": {
                "source": "rest_api",
                "filename": file.filename,
                "mime_type": mime_type,
                "size_bytes": len(file_bytes),
            },
            "reply_to": reply_topic,
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    # 6. Capture the response sent by the handler via send()
    response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
    original_send = perceiver.send

    async def _capturing_send(
        self: Any,
        topic: str,
        content: dict[str, Any],
        message_type: str = "default",
        reply_to: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        msg_type = content.get("message_type", "")
        if msg_type in ("input_processed", "error_response") and topic == reply_topic:
            await response_queue.put(content)
        return await original_send(
            topic,
            content,
            message_type=message_type,
            reply_to=reply_to,
            correlation_id=correlation_id,
            metadata=metadata,
        )

    try:
        perceiver.send = types.MethodType(_capturing_send, perceiver)

        # 7. Route through process_message (which dispatches to _handle_process_input)
        await perceiver.process_message(message)

        # 8. Await response with timeout
        try:
            response_content = await asyncio.wait_for(response_queue.get(), timeout=120.0)
        except TimeoutError:
            logger.error("perceiver_response_timeout", filename=file.filename)
            raise HTTPException(
                status_code=500,
                detail={"error": "Processing timed out after 120s", "detail": None},
            ) from None

        # 9. Check for error response
        if response_content.get("message_type") == "error_response":
            error_msg = response_content.get("error", "Unknown processing error")
            logger.warning(
                "perceiver_analysis_error",
                filename=file.filename,
                error=error_msg,
            )
            raise HTTPException(
                status_code=500,
                detail={"error": error_msg, "detail": None},
            )

        # 10. Extract and return structured response
        features = response_content.get("features", {})
        llm_description = features.pop("description", None) if isinstance(features, dict) else None

        return PerceiverResponse(
            input_id=response_content.get("input_id", "unknown"),
            modality=response_content.get("modality", "unknown"),
            features=features,
            quality_score=float(response_content.get("quality_score", 1.0)),
            llm_description=llm_description,
            timestamp=response_content.get("timestamp", datetime.now(UTC).isoformat()),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("perceiver_analysis_unexpected_error", filename=file.filename)
        raise HTTPException(
            status_code=500,
            detail={"error": f"Unexpected processing failure: {exc}", "detail": str(exc)},
        ) from exc
    finally:
        # Restore original send method
        perceiver.send = original_send
