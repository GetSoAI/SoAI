"""SoAI - WebSocket PTY disconnect handler [backend/features/api/routes/system/events/websocket_pty_disconnect.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from features.api.routes.system.events.websocket_pty_events import (
    build_pty_disconnected_payload,
)
from features.api.routes.system.events.websocket_pty_runtime import (
    execute_pty_session_operation,
    resolve_active_pty_terminal_or_enqueue,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.context import ApiContext
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.streaming.websocket import (
    WebsocketConnection,
    WebSocketRequestAdapter,
)

__all__ = ("handle_pty_disconnect",)

LOGGER_NAME = "SoAI.features.api.websocket_pty_disconnect"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_DISCONNECT = (
    "api_system.websocket.system_events.pty.disconnect"
)


async def handle_pty_disconnect(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    request_adapter: WebSocketRequestAdapter,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    resolved_terminal = await resolve_active_pty_terminal_or_enqueue(
        connection=connection,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        require_session=False,
    )
    if resolved_terminal is None:
        return
    terminal, session_id = resolved_terminal
    log_audit_event(
        request_adapter,
        "PTY_SESSION_DISCONNECT",
        f"session={session_id}",
    )
    close_succeeded = await execute_pty_session_operation(
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        logger=get_logger(LOGGER_NAME),
        message="Failed to close PTY session",
        operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_DISCONNECT,
        operation_call=terminal.close_pty_session(session_id),
    )
    if close_succeeded and connection.pty_session_id == session_id:
        connection.pty_session_id = None
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_pty_disconnected_payload(session_id),
            "PTY disconnected",
        )
