"""SoAI - WebSocket dispatching for model test streaming [backend/features/api/routes/system/events/websocket_message_dispatch_model_test.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_model_test_stream.handlers import (
    handle_model_test_stream_cancel,
    handle_model_test_stream_start,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_model_test_message",)


async def try_handle_model_test_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.MODEL_TEST_STREAM_START:
            await handle_model_test_stream_start(
                data,
                trace_id=runtime_context.trace_id,
                stream_dependencies=runtime_context.stream_dependencies,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                request=runtime_context.request,
            )
            return True
        case WebSocketMessageTypes.MODEL_TEST_STREAM_CANCEL:
            await handle_model_test_stream_cancel(
                data,
                request=runtime_context.request,
                api_context=runtime_context.api_context,
                connection=runtime_context.connection,
            )
            return True
        case _:
            return False
