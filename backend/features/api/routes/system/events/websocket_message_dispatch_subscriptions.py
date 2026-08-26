"""SoAI - WebSocket dispatching for subscriptions and snapshots [backend/features/api/routes/system/events/websocket_message_dispatch_subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_message_handlers import (
    handle_log_stream_subscribe_message,
    handle_log_stream_unsubscribe_message,
)
from features.api.routes.system.events.websocket_resource_interests import (
    apply_websocket_resource_interests,
)
from features.api.routes.system.events.websocket_snapshot_tasks import (
    schedule_snapshot_request,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_subscription_message",)


async def try_handle_subscription_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.REQUEST_SNAPSHOT:
            schedule_snapshot_request(
                data,
                runtime_context=runtime_context,
            )
            return True
        case WebSocketMessageTypes.SET_RESOURCE_INTERESTS:
            await apply_websocket_resource_interests(
                data,
                runtime_context=runtime_context,
            )
            return True
        case WebSocketMessageTypes.SUBSCRIBE_LOG_STREAM:
            await handle_log_stream_subscribe_message(
                data,
                connection=runtime_context.connection,
                shutdown_event=runtime_context.shutdown_event,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.UNSUBSCRIBE_LOG_STREAM:
            await handle_log_stream_unsubscribe_message(
                data,
                connection=runtime_context.connection,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case _:
            return False
