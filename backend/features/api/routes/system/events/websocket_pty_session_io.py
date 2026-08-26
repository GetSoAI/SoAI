"""SoAI - WebSocket PTY input and resize handlers [backend/features/api/routes/system/events/websocket_pty_session_io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.serialization.base64_values import decode_base64_ascii
from core.terminal.pty_validation import resolve_default_pty_dimensions
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_pty_runtime import (
    ensure_terminal_access_or_close,
    execute_pty_session_operation,
    resolve_active_pty_terminal_or_enqueue,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.context import ApiContext
from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "handle_pty_input",
    "handle_pty_resize",
)

LOGGER_NAME = "SoAI.features.api.websocket_pty_session_io"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_INPUT_DECODE = (
    "api_system.websocket.system_events.pty.input.decode"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_INPUT_WRITE = (
    "api_system.websocket.system_events.pty.input.write"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_RESIZE = (
    "api_system.websocket.system_events.pty.resize"
)


async def handle_pty_input(
    data: str,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    if not await ensure_terminal_access_or_close(
        connection=connection,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
    ):
        return
    try:
        raw_data = decode_base64_ascii(data, error_message="Invalid PTY input base64.")
    except ValidationError as decode_err:
        log_exception(
            get_logger(LOGGER_NAME),
            decode_err,
            message="Failed to decode PTY input",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_INPUT_DECODE,
        )
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.PTY_ERROR,
            "Invalid input data encoding.",
            code="invalid_request_error",
        )
        return
    resolved_terminal = await resolve_active_pty_terminal_or_enqueue(
        connection=connection,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        require_session=True,
    )
    if resolved_terminal is None:
        return
    terminal, session_id = resolved_terminal
    await execute_pty_session_operation(
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        logger=get_logger(LOGGER_NAME),
        message="Failed to write to PTY",
        operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_INPUT_WRITE,
        operation_call=terminal.write_pty_input(session_id, raw_data),
    )


async def handle_pty_resize(
    cols: int,
    rows: int,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    if not await ensure_terminal_access_or_close(
        connection=connection,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
    ):
        return
    resolved_terminal = await resolve_active_pty_terminal_or_enqueue(
        connection=connection,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        require_session=True,
    )
    if resolved_terminal is None:
        return
    terminal, session_id = resolved_terminal
    resolved_cols, resolved_rows = resolve_default_pty_dimensions(cols, rows)
    await execute_pty_session_operation(
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        logger=get_logger(LOGGER_NAME),
        message="Failed to resize PTY",
        operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_RESIZE,
        operation_call=terminal.resize_pty(session_id, resolved_cols, resolved_rows),
    )
