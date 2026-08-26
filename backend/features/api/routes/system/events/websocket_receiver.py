"""SoAI - WebSocket receiver loop for system events channel [backend/features/api/routes/system/events/websocket_receiver.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import is_json_dict
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import (
    enqueue_websocket_error,
    enqueue_websocket_soai_error,
)
from features.api.routes.system.events.websocket_event_context import (
    WebsocketEventRuntimeContext,
)
from features.api.routes.system.events.websocket_event_subscriptions import (
    reconcile_websocket_event_subscriptions,
)
from features.api.routes.system.events.websocket_message_dispatch import (
    handle_websocket_message,
)
from features.api.routes.system.events.websocket_permission_refresh import (
    refresh_websocket_effective_actions,
)
from features.api.routes.system.events.websocket_session_validation import (
    validate_websocket_session,
)
from features.api.routes.system.events.websocket_transport_lifecycle import (
    WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS,
)

__all__ = ("run_websocket_receiver",)

LOGGER_NAME = "SoAI.features.api.websocket_receiver"
OPERATION = "api_system.websocket.system_events.receiver"


async def run_websocket_receiver(
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    while not runtime_context.shutdown_event.is_set():
        try:
            data = await runtime_context.websocket.receive_json()
            session_valid = await validate_websocket_session(
                runtime_context.connection,
                force=True,
            )
            if not session_valid:
                runtime_context.shutdown_event.set()
                return
            if runtime_context.shutdown_event.is_set():
                return
            await refresh_websocket_effective_actions(runtime_context.connection)
            event_handler = runtime_context.connection.event_handler
            if event_handler is not None:
                reconcile_websocket_event_subscriptions(
                    event_bus=runtime_context.api_context.dependencies.event_bus,
                    connection=runtime_context.connection,
                    event_handler=event_handler,
                )
            if not is_json_dict(data):
                await enqueue_websocket_error(
                    runtime_context.enqueue_warning_tracker,
                    runtime_context.connection.queue,
                    runtime_context.trace_id,
                    WebSocketEventTypes.INVALID_REQUEST,
                    "WebSocket message must be a JSON object.",
                    code="invalid_request_error",
                    details={"received_type": type(data).__name__},
                )
                continue
            await handle_websocket_message(
                data,
                runtime_context=runtime_context,
            )
        except SoAIError as exception:
            if int(exception.http_status) >= 500:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="WebSocket receiver task server error.",
                    operation=OPERATION,
                    details={
                        "username": runtime_context.connection.user.get("username", "unknown"),
                    },
                    level="warning",
                )
                runtime_context.shutdown_event.set()
                break
            await enqueue_websocket_soai_error(
                runtime_context.enqueue_warning_tracker,
                runtime_context.connection.queue,
                runtime_context.trace_id,
                exception,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="WebSocket receiver task error (connection will be closed).",
                operation=OPERATION,
                details={"username": runtime_context.connection.user.get("username", "unknown")},
                level="warning",
            )
            runtime_context.shutdown_event.set()
            break
        except WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS:
            runtime_context.shutdown_event.set()
            return
