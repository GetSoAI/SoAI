"""SoAI - WebSocket chat stream command error utilities [backend/features/api/routes/system/events/chat_stream/command_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.public_projection import project_public_error_code
from core.system_api.websocket_payloads import build_websocket_event_payload
from features.api.routes.system.events.chat_error_payload_metadata import (
    build_chat_error_payload_metadata,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.runtime.event_enqueue import enqueue_event_must_deliver

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "build_chat_command_error_payload",
    "enqueue_chat_stream_command_error",
    "enqueue_chat_stream_start_error",
)


def build_chat_command_error_payload(
    *,
    event_type: str,
    conv_id: str,
    request_id: str,
    code: str,
    message: str,
    include_usage_preview: bool,
    phase: str | None = None,
    trace_id: str | None = None,
    include_trace_id: bool = False,
) -> JSONDict:
    public_error = project_public_error_code(
        code=code,
        message=message,
        trace_id=trace_id,
    )
    event_payload: JSONDict = {
        "conv_id": conv_id,
        "request_id": request_id,
    }
    if phase is not None:
        event_payload["phase"] = phase
    event_payload["code"] = str(public_error.code)
    event_payload["message"] = public_error.message
    if include_trace_id or trace_id is not None:
        event_payload["trace_id"] = trace_id
    payload = build_websocket_event_payload(event_type, event_payload)
    payload.update(
        build_chat_error_payload_metadata(
            message=public_error.message,
            include_usage_preview=include_usage_preview,
        ),
    )
    return payload


async def enqueue_chat_stream_command_error(
    connection: WebsocketConnection,
    conv_id: str,
    request_id: str,
    phase: str,
    code: str,
    message: str,
) -> None:
    payload = build_chat_command_error_payload(
        event_type=WebSocketEventTypes.CHAT_STREAM_COMMAND_ERROR,
        conv_id=conv_id,
        request_id=request_id,
        phase=phase,
        code=code,
        message=message,
        include_usage_preview=False,
    )
    queue_label = f"WebSocket for {connection.user.get('username', 'unknown')}"
    await enqueue_event_must_deliver(
        connection.queue,
        payload,
        queue_label,
    )


async def enqueue_chat_stream_start_error(
    connection: WebsocketConnection,
    conv_id: str,
    request_id: str,
    code: str,
    message: str,
) -> None:
    await enqueue_chat_stream_command_error(
        connection,
        conv_id=conv_id,
        request_id=request_id,
        phase="start",
        code=code,
        message=message,
    )
