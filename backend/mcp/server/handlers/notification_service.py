"""SoAI - MCP server notification emission service [backend/mcp/server/handlers/notification_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_mcp import MCPNotificationEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_NOTIFICATIONS_DROPPED,
    MCP_SERVER_COUNTER_NOTIFICATIONS_FAILURES,
    MCP_SERVER_COUNTER_NOTIFICATIONS_SENT,
)
from mcp.protocol.jsonrpc import build_jsonrpc_notification
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.types.json import JSONDict
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPNotificationService",
    "MCPNotificationServiceDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.notification_service"
OPERATION_MCP_SERVER_NOTIFY_RESOURCE_UPDATED = "mcp.server.notify_resource_updated"


@dataclass(frozen=True, slots=True)
class MCPNotificationServiceDependencies:
    state: MCPServerState
    event_bus: EventBusProtocol
    resolve_session_id: Callable[[str], str]
    emit_client_stream_message: Callable[[str, JSONDict], Awaitable[None]]
    try_emit_client_stream_message: Callable[[str, JSONDict], Awaitable[bool]]
    metrics_manager: MetricsManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPNotificationServiceDependencies",
            emit_client_stream_message=self.emit_client_stream_message,
            event_bus=self.event_bus,
            metrics_manager=self.metrics_manager,
            resolve_session_id=self.resolve_session_id,
            state=self.state,
            try_emit_client_stream_message=self.try_emit_client_stream_message,
        )


class MCPNotificationService:
    def __init__(self, deps: MCPNotificationServiceDependencies) -> None:
        self._state = deps.state
        self._event_bus = deps.event_bus
        self._resolve_session_id = deps.resolve_session_id
        self._emit_client_stream_message = deps.emit_client_stream_message
        self._try_emit = deps.try_emit_client_stream_message
        self._metrics_manager = deps.metrics_manager

    async def notify_resource_updated(self, uri: str) -> None:
        logger = get_logger(LOGGER_NAME)
        registration = self._state.registration
        subscribed_sessions: list[str] = []
        async with registration.resource_subscriptions_lock:
            for session_id, uris in registration.resource_subscriptions.items():
                if uri in uris:
                    subscribed_sessions.append(session_id)
        if not subscribed_sessions:
            return
        notification = build_jsonrpc_notification("notifications/resources/updated", {"uri": uri})
        notification_payload: JSONDict = (
            dict(notification) if isinstance(notification, dict) else {}
        )
        failures = 0
        dropped = 0
        for session_id in subscribed_sessions:
            try:
                delivered = await self._try_emit(session_id, notification_payload)
                if delivered is False:
                    dropped += 1
            except MCPJSONRPCError as exception:
                failures += 1
                logger.warning(
                    "Failed to send resource update notification to session %s: %s",
                    session_id,
                    exception.message,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                failures += 1
                log_exception(
                    logger,
                    exception,
                    message="Failed to send resource update notification",
                    operation=OPERATION_MCP_SERVER_NOTIFY_RESOURCE_UPDATED,
                    details={"uri": uri, "session_id": session_id},
                )
        if dropped:
            self._metrics_manager.increment_counter(
                *MCP_SERVER_COUNTER_NOTIFICATIONS_DROPPED,
                value=dropped,
            )
        if failures:
            self._metrics_manager.increment_counter(
                *MCP_SERVER_COUNTER_NOTIFICATIONS_FAILURES,
                value=failures,
            )
        sent = max(len(subscribed_sessions) - failures - dropped, 0)
        if sent:
            self._metrics_manager.increment_counter(
                *MCP_SERVER_COUNTER_NOTIFICATIONS_SENT,
                value=sent,
            )
        logger.debug(
            "Sent resource update notification for '%s' to %d sessions (%d failures)",
            uri,
            len(subscribed_sessions),
            failures,
        )

    async def emit_notification(self, client_id: str, notification: JSONDict) -> None:
        notification_payload: JSONDict = (
            dict(notification) if isinstance(notification, dict) else {}
        )
        session_id = self._resolve_session_id(client_id)
        async with self._state.session.client_sessions_lock:
            session_exists = session_id in self._state.session.client_sessions
        if session_exists:
            await self._emit_client_stream_message(session_id, notification_payload)
        await self._event_bus.publish(
            MCPNotificationEvent(client_id=client_id, notification=notification),
        )
