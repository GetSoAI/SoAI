"""SoAI - Streaming helpers for orchestrator executor [backend/orchestrator/execution/streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAITimeoutError, StateError, ValidationError
from core.openai.stream_chunk_bytes import coerce_stream_chunk_to_bytes

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "ChunkDeliveryTimeoutError",
    "InvalidStreamingChunk",
    "StreamingIdleTimeoutError",
    "StreamingSourceTimeoutError",
    "build_stream_timeout_error",
    "coerce_stream_chunk",
)

STREAMING_CHUNK_DELIVERY_TIMEOUT_DEFAULT: float = 120.0
STREAMING_CHUNK_DELIVERY_TIMEOUT_MINIMUM: float = 1.0
STREAMING_IDLE_TIMEOUT_MINIMUM: float = 1.0


class InvalidStreamingChunk(StateError):
    def __init__(self, chunk_type: str) -> None:
        super().__init__(
            f"Invalid streaming chunk type: {chunk_type}",
            operation="orchestrator.stream_chunk",
        )


class StreamingIdleTimeoutError(SoAITimeoutError):
    def __init__(self, idle_timeout_seconds: float) -> None:
        super().__init__(
            f"Plugin stream stalled: no meaningful output received for {idle_timeout_seconds:.1f}s.",
            operation="orchestrator.streaming_idle_timeout",
        )


class StreamingSourceTimeoutError(SoAITimeoutError):
    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(
            f"Plugin stream raised a timeout while producing a chunk (configured wait limit: {timeout_seconds:.1f}s).",
            operation="orchestrator.streaming_source_timeout",
        )


class ChunkDeliveryTimeoutError(SoAITimeoutError):
    def __init__(self, delivery_timeout_seconds: float) -> None:
        super().__init__(
            f"Timed out delivering streaming chunk after {delivery_timeout_seconds:.1f}s.",
            operation="orchestrator.stream_chunk_delivery",
        )


def build_stream_timeout_error(
    timeout_scope: asyncio.Timeout,
    timeout_seconds: float,
) -> StreamingIdleTimeoutError | StreamingSourceTimeoutError:
    if timeout_scope.expired():
        return StreamingIdleTimeoutError(timeout_seconds)
    return StreamingSourceTimeoutError(timeout_seconds)


def coerce_stream_chunk(chunk: StreamChunk) -> bytes:
    try:
        return coerce_stream_chunk_to_bytes(chunk)
    except ValidationError as exception:
        raise InvalidStreamingChunk(type(chunk).__name__) from exception
