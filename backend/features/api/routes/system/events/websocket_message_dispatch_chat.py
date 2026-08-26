"""SoAI - WebSocket dispatching for chat-related messages [backend/features/api/routes/system/events/websocket_message_dispatch_chat.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.chat_stream.cancel import (
    handle_chat_stream_cancel,
)
from features.api.routes.system.events.chat_stream.start_command_handler import (
    handle_chat_stream_start,
)
from features.api.routes.system.events.conversation_attention import (
    handle_conversation_attention_mark_seen,
)
from features.api.routes.system.events.conversation_presence import (
    handle_conversation_presence_update,
)
from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_chat_token_count.handler import (
    handle_chat_token_count,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_chat_message",)


async def try_handle_chat_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.CHAT_STREAM_START:
            await handle_chat_stream_start(
                data,
                request=runtime_context.request,
                api_context=runtime_context.api_context,
                connection=runtime_context.connection,
                stream_dependencies=runtime_context.stream_dependencies,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.CHAT_STREAM_CANCEL:
            await handle_chat_stream_cancel(
                data,
                request=runtime_context.request,
                api_context=runtime_context.api_context,
                connection=runtime_context.connection,
            )
            return True
        case WebSocketMessageTypes.CHAT_TOKEN_COUNT:
            await handle_chat_token_count(
                data,
                request=runtime_context.request,
                api_context=runtime_context.api_context,
                connection=runtime_context.connection,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.CONVERSATION_PRESENCE_UPDATE:
            await handle_conversation_presence_update(
                data,
                runtime_context=runtime_context,
            )
            return True
        case WebSocketMessageTypes.CONVERSATION_ATTENTION_MARK_SEEN:
            await handle_conversation_attention_mark_seen(
                data,
                runtime_context=runtime_context,
            )
            return True
        case _:
            return False
