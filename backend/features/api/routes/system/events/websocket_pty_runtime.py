"""SoAI - Shared PTY WebSocket runtime helpers [backend/features/api/routes/system/events/websocket_pty_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import request_has_action
from features.api.routes.system.events.websocket_errors import (
    enqueue_pty_websocket_error,
    enqueue_pty_websocket_server_error,
    enqueue_pty_websocket_soai_error,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.context import ApiContext
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.terminal.protocols import TerminalServiceProtocol

__all__ = (
    "enqueue_no_active_pty_session_error",
    "ensure_terminal_access_or_close",
    "enqueue_terminal_service_unavailable",
    "execute_pty_session_operation",
    "resolve_active_pty_terminal_or_enqueue",
    "resolve_terminal_service_or_enqueue_unavailable",
)


async def ensure_terminal_access_or_close(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> bool:
    if await request_has_action(connection.request, AccessAction.TERMINAL_USE):
        return True
    session_id = connection.pty_session_id
    terminal = api_context.dependencies.terminal
    if session_id and terminal is not None:
        await terminal.close_pty_session(session_id)
        connection.pty_session_id = None
    await enqueue_pty_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        "Insufficient permissions for terminal access.",
        code="forbidden_error",
    )
    return False


async def enqueue_terminal_service_unavailable(
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    await enqueue_pty_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        "Terminal service unavailable.",
        code="service_unavailable",
    )


async def resolve_terminal_service_or_enqueue_unavailable(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> TerminalServiceProtocol | None:
    terminal = api_context.dependencies.terminal
    if terminal is not None:
        return terminal
    await enqueue_terminal_service_unavailable(
        connection,
        enqueue_warning_tracker,
        trace_id,
    )
    return None


async def enqueue_no_active_pty_session_error(
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    await enqueue_pty_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        "No active PTY session.",
        code="invalid_request_error",
    )


async def resolve_active_pty_terminal_or_enqueue(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    require_session: bool,
) -> tuple[TerminalServiceProtocol, str] | None:
    session_id = connection.pty_session_id
    if not session_id:
        if require_session:
            await enqueue_no_active_pty_session_error(
                connection,
                enqueue_warning_tracker,
                trace_id,
            )
        return None
    terminal = await resolve_terminal_service_or_enqueue_unavailable(
        connection=connection,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
    )
    if terminal is None:
        return None
    return (terminal, session_id)


async def execute_pty_session_operation(
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    logger: LoggerProtocol,
    message: str,
    operation: str,
    operation_call: Awaitable[None],
) -> bool:
    try:
        await operation_call
        return True
    except ValidationError as exception:
        log_exception(
            logger,
            exception,
            message=message,
            operation=operation,
        )
        await enqueue_pty_websocket_soai_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            exception,
        )
        return False
    except (SoAIError, TimeoutError) as exception:
        log_exception(
            logger,
            exception,
            message=message,
            operation=operation,
        )
        await enqueue_pty_websocket_server_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
        )
        return False
