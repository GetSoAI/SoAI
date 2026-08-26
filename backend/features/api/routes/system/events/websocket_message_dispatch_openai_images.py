"""SoAI - WebSocket dispatching for OpenAI images messages [backend/features/api/routes/system/events/websocket_message_dispatch_openai_images.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_openai_images.generation_cancel import (
    handle_openai_images_generation_cancel,
)
from features.api.routes.system.events.websocket_openai_images.generation_handlers import (
    handle_openai_images_generation_start,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_openai_images_message",)


async def try_handle_openai_images_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.OPENAI_IMAGES_GENERATION_START:
            await handle_openai_images_generation_start(
                data,
                trace_id=runtime_context.trace_id,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                stream_dependencies=runtime_context.stream_dependencies,
                api_context=runtime_context.api_context,
                request_context=runtime_context.request.state.context,
                connection=runtime_context.connection,
                shutdown_event=runtime_context.shutdown_event,
            )
            return True
        case WebSocketMessageTypes.OPENAI_IMAGES_GENERATION_CANCEL:
            await handle_openai_images_generation_cancel(
                data,
                api_context=runtime_context.api_context,
                connection=runtime_context.connection,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
            )
            return True
        case _:
            return False
