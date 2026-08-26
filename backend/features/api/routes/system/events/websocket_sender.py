"""SoAI - WebSocket sender loop for system events channel [backend/features/api/routes/system/events/websocket_sender.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.concurrency.task_groups import QueueEventWaiter
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError
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
    waiter = QueueEventWaiter(connection.queue, shutdown_event)
    try:
        while True:
            if shutdown_event.is_set():
                break
            retrieved_from_queue = False
            try:
                try:
                    wait_result = await waiter.wait_with_result(timeout=INTERACTIVE_TIMEOUT_SEC)
                except (SoAITimeoutError, TimeoutError):
                    wait_result = None
                if wait_result is None:
                    event_data: JSONDict = build_websocket_event_payload(WebSocketEventTypes.PING)
                else:
                    event_data = (
                        wait_result.event
                        if wait_result.event is not None
                        else build_websocket_event_payload(WebSocketEventTypes.PING)
                    )
                    retrieved_from_queue = wait_result.retrieved_from_queue
                    if shutdown_event.is_set():
                        break
                if shutdown_event.is_set():
                    break
                if not await validate_websocket_session(connection, force=False):
                    shutdown_event.set()
                    break
                if "protocol_version" not in event_data:
                    event_data["protocol_version"] = WEBSOCKET_PROTOCOL_VERSION
                normalized_payload = normalize_for_json(event_data)
                await websocket.send_json(normalized_payload)
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
    finally:
        await waiter.cancel()
