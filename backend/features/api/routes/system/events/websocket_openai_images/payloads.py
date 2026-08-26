"""SoAI - WebSocket payload builders for OpenAI images commands [backend/features/api/routes/system/events/websocket_openai_images/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.system_api.websocket_run_events import (
    build_websocket_run_error_event,
    build_websocket_run_event,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.streaming.sse_responses import SSE_MEDIA_TYPE

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_openai_images_generation_cancelled",
    "build_openai_images_generation_completed",
    "build_openai_images_generation_error",
    "build_openai_images_generation_started",
    "build_openai_images_generation_stream_chunk",
)


def build_openai_images_generation_started(
    *,
    run_id: str,
    task_id: str,
    stream: bool,
) -> JSONDict:
    fields: JSONDict = {"stream": stream}
    if stream:
        fields["content_type"] = SSE_MEDIA_TYPE
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_IMAGES_GENERATION_STARTED,
        run_id=run_id,
        task_id=task_id,
        fields=fields,
    )


def build_openai_images_generation_stream_chunk(
    *,
    run_id: str,
    sequence: int,
    chunk: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_IMAGES_GENERATION_STREAM_CHUNK,
        run_id=run_id,
        fields={"sequence": sequence, "chunk": chunk},
    )


def build_openai_images_generation_completed(
    *,
    run_id: str,
    task_id: str,
    chunk_count: int,
    result: JSONValue | None = None,
) -> JSONDict:
    payload = build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_IMAGES_GENERATION_COMPLETED,
        run_id=run_id,
        task_id=task_id,
        fields={"chunk_count": chunk_count},
    )
    if result is not None:
        payload["result"] = result
    return payload


def build_openai_images_generation_cancelled(
    *,
    run_id: str,
    reason: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_IMAGES_GENERATION_CANCELLED,
        run_id=run_id,
        fields={"reason": reason},
    )


def build_openai_images_generation_error(
    *,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> JSONDict:
    return build_websocket_run_error_event(
        event_type=WebSocketEventTypes.OPENAI_IMAGES_GENERATION_ERROR,
        run_id=run_id,
        message=message,
        code=code,
        task_id=task_id,
    )
