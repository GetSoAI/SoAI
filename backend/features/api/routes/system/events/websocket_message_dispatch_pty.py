"""SoAI - WebSocket dispatching for PTY messages [backend/features/api/routes/system/events/websocket_message_dispatch_pty.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_message_handlers import (
    resolve_pty_cols_rows,
)
from features.api.routes.system.events.websocket_pty_connect import handle_pty_connect
from features.api.routes.system.events.websocket_pty_disconnect import (
    handle_pty_disconnect,
)
from features.api.routes.system.events.websocket_pty_session_io import (
    handle_pty_input,
    handle_pty_resize,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_pty_message",)


async def try_handle_pty_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.PTY_CONNECT:
            cols, rows = resolve_pty_cols_rows(data, default_cols=80, default_rows=24)
            shell_value = data.get("shell")
            shell = shell_value if isinstance(shell_value, str) else None
            await handle_pty_connect(
                cols,
                rows,
                shell,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                request_adapter=runtime_context.request_adapter,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.PTY_INPUT:
            input_value = data.get("data")
            input_data = input_value if isinstance(input_value, str) else ""
            await handle_pty_input(
                input_data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.PTY_RESIZE:
            cols, rows = resolve_pty_cols_rows(data, default_cols=80, default_rows=24)
            await handle_pty_resize(
                cols,
                rows,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.PTY_DISCONNECT:
            await handle_pty_disconnect(
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                request_adapter=runtime_context.request_adapter,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case _:
            return False
