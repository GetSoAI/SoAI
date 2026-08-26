"""SoAI - WebSocket PTY connection handler [backend/features/api/routes/system/events/websocket_pty_connect.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.serialization.base64_values import encode_base64_ascii
from core.terminal.pty_validation import resolve_default_pty_dimensions
from core.terminal.requests import CreatePTYSessionRequest
from features.api.routes.system.events.websocket_errors import (
    enqueue_pty_websocket_error,
    enqueue_pty_websocket_server_error,
    enqueue_pty_websocket_soai_error,
)
from features.api.routes.system.events.websocket_pty_events import (
    build_pty_busy_payload,
    build_pty_connected_payload,
    build_pty_exited_payload,
    build_pty_output_payload,
)
from features.api.routes.system.events.websocket_pty_runtime import ensure_terminal_access_or_close
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.context import ApiContext
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.feature_flags import terminal_feature_enabled
from features.api.streaming.websocket import (
    WebsocketConnection,
    WebSocketRequestAdapter,
)

__all__ = ("handle_pty_connect",)

LOGGER_NAME = "SoAI.features.api.websocket_pty_connect"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_CONNECT = (
    "api_system.websocket.system_events.pty.connect"
)


async def handle_pty_connect(
    cols: int,
    rows: int,
    shell: str | None,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    request_adapter: WebSocketRequestAdapter,
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
    config = api_context.dependencies.config
    if not terminal_feature_enabled(config):
        await enqueue_pty_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "Terminal feature is disabled.",
            code="feature_disabled",
        )
        return
    if connection.pty_session_id:
        await enqueue_pty_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "PTY session already active.",
            code="conflict_error",
        )
        return
    terminal = api_context.dependencies.terminal
    if terminal is None:
        await enqueue_pty_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "Terminal service unavailable.",
            code="service_unavailable",
        )
        return
    session_id = create_prefixed_hex_id("pty", length=12)
    resolved_cols, resolved_rows = resolve_default_pty_dimensions(cols, rows)
    log_audit_event(
        request_adapter,
        "PTY_SESSION_CONNECT",
        f"session={session_id}",
    )

    def output_callback(data: bytes) -> None:
        encoded = encode_base64_ascii(data)
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_pty_output_payload(session_id, encoded),
            "PTY output",
        )

    def exit_callback(exited_session_id: str, exit_code: int) -> None:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_pty_exited_payload(exited_session_id, exit_code),
            "PTY exited",
        )

    def busy_callback(busy_session_id: str, busy: bool) -> None:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_pty_busy_payload(busy_session_id, busy),
            "PTY busy",
        )

    try:
        result = await terminal.create_pty_session(
            CreatePTYSessionRequest(
                session_id=session_id,
                cols=resolved_cols,
                rows=resolved_rows,
                user_id=request_adapter.state.context.user_id,
                shell=shell,
                output_callback=output_callback,
                exit_callback=exit_callback,
                busy_callback=busy_callback,
            ),
        )
        connection.pty_session_id = session_id
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_pty_connected_payload(result),
            "PTY connected",
        )
    except ValidationError as exception:
        connection.pty_session_id = None
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to create PTY session",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_CONNECT,
        )
        await enqueue_pty_websocket_soai_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            exception,
        )
    except (SoAIError, TimeoutError) as exception:
        connection.pty_session_id = None
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to create PTY session",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_PTY_CONNECT,
        )
        await enqueue_pty_websocket_server_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
        )
