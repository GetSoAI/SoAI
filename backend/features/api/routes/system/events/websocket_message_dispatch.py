"""SoAI - WebSocket message dispatching for system events channel [backend/features/api/routes/system/events/websocket_message_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from features.api.routes.system.events.internal_protocols import (
    WEBSOCKET_PROTOCOL_VERSION,
    WebSocketEventTypes,
    WebSocketMessageTypes,
)
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_event_context import (
    WebsocketEventRuntimeContext,
)
from features.api.routes.system.events.websocket_latency_probe import (
    handle_latency_probe_message,
)
from features.api.routes.system.events.websocket_message_dispatch_admin import (
    try_handle_admin_message,
)
from features.api.routes.system.events.websocket_message_dispatch_admin_tasks import (
    try_handle_admin_task_message,
)
from features.api.routes.system.events.websocket_message_dispatch_chat import (
    try_handle_chat_message,
)
from features.api.routes.system.events.websocket_message_dispatch_model_test import (
    try_handle_model_test_message,
)
from features.api.routes.system.events.websocket_message_dispatch_openai_audio import (
    try_handle_openai_audio_message,
)
from features.api.routes.system.events.websocket_message_dispatch_openai_images import (
    try_handle_openai_images_message,
)
from features.api.routes.system.events.websocket_message_dispatch_pty import (
    try_handle_pty_message,
)
from features.api.routes.system.events.websocket_message_dispatch_subscriptions import (
    try_handle_subscription_message,
)
from features.api.routes.system.events.websocket_run_payloads import resolve_run_id

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_websocket_message",)


async def handle_websocket_message(
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    protocol_version_value = data.get("protocol_version")
    if (
        not is_strict_int(protocol_version_value)
        or int(protocol_version_value) != WEBSOCKET_PROTOCOL_VERSION
    ):
        await enqueue_websocket_error(
            runtime_context.enqueue_warning_tracker,
            runtime_context.connection.queue,
            runtime_context.trace_id,
            WebSocketEventTypes.INVALID_REQUEST,
            "Unsupported websocket protocol version.",
            code="invalid_request_error",
        )
        runtime_context.shutdown_event.set()
        return
    message_type = data.get("type")
    if not isinstance(message_type, str):
        message_type = ""

    if message_type == WebSocketMessageTypes.PONG:
        return
    if message_type == WebSocketMessageTypes.LATENCY_PROBE:
        await handle_latency_probe_message(data, runtime_context=runtime_context)
        return
    if await try_handle_subscription_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_chat_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_model_test_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_pty_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_admin_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_admin_task_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_openai_audio_message(message_type, data, runtime_context=runtime_context):
        return
    if await try_handle_openai_images_message(message_type, data, runtime_context=runtime_context):
        return
    await enqueue_websocket_error(
        runtime_context.enqueue_warning_tracker,
        runtime_context.connection.queue,
        runtime_context.trace_id,
        WebSocketEventTypes.UNKNOWN_MESSAGE,
        f"Unknown message type: {message_type}",
        code="invalid_request_error",
        run_id=resolve_run_id(data),
    )
