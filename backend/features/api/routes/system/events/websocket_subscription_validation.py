"""SoAI - WebSocket stream subscription field validation [backend/features/api/routes/system/events/websocket_subscription_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "require_history_limit",
    "require_source_name",
)


async def require_source_name(
    data: JSONDict,
    *,
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
    trace_id: str | None,
    action: str,
) -> str | None:
    source_name = data.get("source_name")
    if isinstance(source_name, str) and source_name.strip():
        return source_name
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        WebSocketEventTypes.INVALID_REQUEST,
        f"{action} requires a non-empty source_name.",
        code="invalid_request_error",
    )
    return None


async def require_history_limit(
    data: JSONDict,
    *,
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
    trace_id: str | None,
) -> int | None:
    value = data.get("history_limit")
    if value is None:
        return None
    if is_strict_int(value) and 1 <= int(value) <= 10000:
        return int(value)
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        WebSocketEventTypes.INVALID_REQUEST,
        "subscribe_log_stream history_limit must be an integer between 1 and 10000.",
        code="invalid_request_error",
    )
    return None
