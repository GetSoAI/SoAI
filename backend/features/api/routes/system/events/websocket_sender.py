"""SoAI - WebSocket sender loop for system events channel [backend/features/api/routes/system/events/websocket_sender.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.json import normalize_for_json
from core.system_api.websocket_payloads import build_websocket_event_payload
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from features.api.routes.system.events.internal_protocols import (
    WEBSOCKET_PROTOCOL_VERSION,
    WebSocketEventTypes,
)
from features.api.routes.system.events.websocket_session_validation import (
    validate_websocket_session,
)
from features.api.routes.system.events.websocket_transport_lifecycle import (
    WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("run_websocket_sender",)

LOGGER_NAME = "SoAI.features.api.websocket_sender"
OPERATION = "api_system.websocket.system_events.sender"


async def run_websocket_sender(
    *,
    websocket: WebSocket,
    connection: WebsocketConnection,
    shutdown_event: asyncio.Event,
) -> None:
    terminal_error = connection.terminal_error
    while not shutdown_event.is_set():
        retrieved_from_queue = False
        try:
            wait_result = await race_queue_operation_against_signals(
                connection.queue.get(),
                (shutdown_event, terminal_error.requested),
                timeout_seconds=INTERACTIVE_TIMEOUT_SEC,
            )
            retrieved_from_queue = wait_result.outcome is QueueRaceOutcome.OPERATION_COMPLETED
            if shutdown_event.is_set():
                break
            terminal_payload = terminal_error.payload if terminal_error.requested.is_set() else None
            event_data: JSONDict = (
                terminal_payload
                if terminal_payload is not None
                else (
                    wait_result.value
                    if wait_result.value is not None
                    else build_websocket_event_payload(WebSocketEventTypes.PING)
                )
            )
            if not await validate_websocket_session(connection, force=False):
                shutdown_event.set()
                break
            if shutdown_event.is_set():
                break
            if "protocol_version" not in event_data:
                event_data["protocol_version"] = WEBSOCKET_PROTOCOL_VERSION
            normalized_payload = normalize_for_json(event_data)
            await websocket.send_json(normalized_payload)
            if terminal_payload is not None:
                terminal_error.delivered.set()
                shutdown_event.set()
                return
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="WebSocket sender task error.",
                operation=OPERATION,
                details={"username": connection.user.get("username", "unknown")},
                level="warning",
            )
            shutdown_event.set()
            break
        except WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS:
            shutdown_event.set()
            return
        finally:
            if retrieved_from_queue:
                try:
                    connection.queue.task_done()
                except ValueError:
                    get_logger(LOGGER_NAME).trace(
                        "task_done called on empty websocket queue (cleanup race).",
                    )
