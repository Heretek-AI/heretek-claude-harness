# =============================================================================
"""JetStream management endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger()
router = APIRouter()


def get_jetstream_manager() -> Any | None:
    """Dependency to get the JetStream manager."""
    try:
        from heretek_swarm.gateway.jetstream_manager import get_jetstream_manager as get_js

        return get_js()
    except ImportError:
        return None


class JetStreamConfigCreate(BaseModel):
    """Request model for creating a JetStream."""

    stream_name: str = Field(..., description="Stream name")
    subjects: list[str] = Field(..., description="List of subjects to capture")
    retention: str = Field(
        default="limits", description="Retention policy (limits, interest, workqueue)"
    )
    max_messages: int = Field(default=1000000, description="Maximum messages to retain")
    max_age: str = Field(default="72h", description="Maximum age (e.g., 72h, 7d)")
    storage: str = Field(default="file", description="Storage type (file, memory)")
    replicas: int = Field(default=1, description="Number of replicas")
    max_bytes: int = Field(default=1073741824, description="Maximum size in bytes")
    description: str | None = Field(None, description="Stream description")


class JetStreamConsumerCreate(BaseModel):
    """Request model for creating a durable consumer."""

    durable_name: str = Field(..., description="Durable consumer name")
    stream_name: str = Field(..., description="Source stream name")
    deliver_policy: str = Field(default="all", description="Delivery policy")
    ack_policy: str = Field(default="explicit", description="Acknowledgment policy")
    filter_subject: str | None = Field(None, description="Subject filter")


class StreamInfoResponse(BaseModel):
    """Response model for stream information."""

    name: str
    subjects: list[str]
    retention: str
    max_messages: int
    max_age: str
    storage: str
    replicas: int
    max_bytes: int
    description: str | None
    state: dict[str, Any]
    created_at: str | None


class StreamListResponse(BaseModel):
    """Response model for listing streams."""

    streams: list[StreamInfoResponse]
    total: int


@router.get("/jetstream/streams")
async def list_jetstream_streams(
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> StreamListResponse:
    """
    List all JetStream streams.

    Returns:
        List of stream information
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        streams = await js_manager.list_streams()

        return StreamListResponse(
            streams=[
                StreamInfoResponse(
                    name=s.name,
                    subjects=s.config.subjects,
                    retention=s.config.retention.value,
                    max_messages=s.config.max_messages,
                    max_age=s.config.max_age,
                    storage=s.config.storage.value,
                    replicas=s.config.replicas,
                    max_bytes=s.config.max_bytes,
                    description=s.config.description,
                    state=s.state,
                    created_at=s.created_at.isoformat() if s.created_at else None,
                )
                for s in streams
            ],
            total=len(streams),
        )
    except Exception as e:
        logger.exception("Failed to list streams: {e}")
        raise HTTPException(500, f"Failed to list streams: {e!s}") from e


@router.get("/jetstream/streams/{stream_name}")
async def get_jetstream_stream(
    stream_name: str,
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> StreamInfoResponse:
    """
    Get information about a specific stream.

    Args:
        stream_name: Stream name
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        info = await js_manager.get_stream_info(stream_name)

        if not info:
            raise HTTPException(404, f"Stream '{stream_name}' not found")

        return StreamInfoResponse(
            name=info.name,
            subjects=info.config.subjects,
            retention=info.config.retention.value,
            max_messages=info.config.max_messages,
            max_age=info.config.max_age,
            storage=info.config.storage.value,
            replicas=info.config.replicas,
            max_bytes=info.config.max_bytes,
            description=info.config.description,
            state=info.state,
            created_at=info.created_at.isoformat() if info.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get stream info: {e}")
        raise HTTPException(500, f"Failed to get stream info: {e!s}") from e


@router.post("/jetstream/streams")
async def create_jetstream_stream(
    config_data: JetStreamConfigCreate,
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Create a new JetStream.

    Args:
        config_data: Stream configuration
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        from heretek_swarm.gateway.jetstream_manager import (
            JetStreamConfig,
            RetentionPolicy,
            StorageType,
        )

        config = JetStreamConfig(
            stream_name=config_data.stream_name,
            subjects=config_data.subjects,
            retention=RetentionPolicy(config_data.retention),
            max_messages=config_data.max_messages,
            max_age=config_data.max_age,
            storage=StorageType(config_data.storage),
            replicas=config_data.replicas,
            max_bytes=config_data.max_bytes,
            description=config_data.description,
        )

        success = await js_manager.create_stream(config)

        if not success:
            raise HTTPException(500, "Failed to create stream")

        logger.info(
            "jetstream_stream_created",
            stream_name=config_data.stream_name,
            subjects=config_data.subjects,
        )

        return {
            "status": "success",
            "stream_name": config_data.stream_name,
            "subjects": config_data.subjects,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create stream: {e}")
        raise HTTPException(500, f"Failed to create stream: {e!s}") from e


@router.delete("/jetstream/streams/{stream_name}")
async def delete_jetstream_stream(
    stream_name: str,
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, str]:
    """
    Delete a JetStream.

    Args:
        stream_name: Stream name
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        success = await js_manager.delete_stream(stream_name)

        if not success:
            raise HTTPException(404, f"Stream '{stream_name}' not found or delete failed")

        logger.info("jetstream_stream_deleted", stream_name=stream_name)

        return {"status": "success", "message": f"Deleted stream '{stream_name}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete stream: {e}")
        raise HTTPException(500, f"Failed to delete stream: {e!s}") from e


@router.post("/jetstream/streams/{stream_name}/replay")
async def replay_stream_messages(
    stream_name: str,
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
    start_sequence: int | None = None,
    end_sequence: int | None = None,
    subject_filter: str | None = None,
) -> dict[str, Any]:
    """
    Replay messages from a stream.

    Args:
        stream_name: Stream name
        start_sequence: Start sequence number
        end_sequence: End sequence number
        subject_filter: Subject pattern filter
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        messages = await js_manager.replay_messages(
            stream_name=stream_name,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            subject_filter=subject_filter,
        )

        return {
            "stream_name": stream_name,
            "messages_replayed": len(messages),
            "messages": messages[:100],  # Limit response size
        }
    except Exception as e:
        logger.exception("Failed to replay messages: {e}")
        raise HTTPException(500, f"Failed to replay messages: {e!s}") from e


@router.get("/jetstream/stats")
async def get_jetstream_stats(
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get JetStream manager statistics.

    Returns:
        Manager statistics
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        return await js_manager.get_stats()
    except Exception as e:
        logger.exception("Failed to get JetStream stats: {e}")
        raise HTTPException(500, f"Failed to get JetStream stats: {e!s}") from e


@router.post("/jetstream/initialize")
async def initialize_jetstream(
    js_manager: Annotated[Any | None, Depends(get_jetstream_manager)],
    authenticated: Annotated[str, Depends(verify_auth)],
    create_defaults: bool = True,
) -> dict[str, Any]:
    """
    Initialize JetStream with default streams.

    Args:
        create_defaults: Create default stream configurations

    Returns:
        Creation results for each stream
    """
    if not js_manager:
        raise HTTPException(503, "JetStream manager not available")

    try:
        results = await js_manager.initialize_default_streams()

        logger.info("JetStream default streams initialized", results=results)

        return {
            "status": "success",
            "streams": results,
            "total_created": sum(1 for v in results.values() if v),
        }
    except Exception as e:
        logger.exception("Failed to initialize JetStream: {e}")
        raise HTTPException(500, f"Failed to initialize JetStream: {e!s}") from e
