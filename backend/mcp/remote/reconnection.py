"""SoAI - MCP remote reconnection handler [backend/mcp/remote/reconnection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_mcp import MCPServerConnectedEvent
from core.logging.trace import get_logger
from core.timing.epoch import epoch_seconds_float
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.types import MCPServerStatus

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.mcp.protocols_storage import DatabaseMCPProtocol

__all__ = (
    "MCPReconnectionHandler",
    "MCPReconnectionHandlerDependencies",
)

LOGGER_NAME = "SoAI.mcp.remote.reconnection"
OPERATION = "mcp.remote.reconnection.reconnect_loop"


@dataclass(frozen=True, slots=True)
class MCPReconnectionHandlerDependencies:
    db_mcp: DatabaseMCPProtocol
    event_bus: EventBusProtocol
    shutdown_event: asyncio.Event
    connect_by_transport: Callable[[MCPServerConnection], Awaitable[bool]]
    max_reconnect_attempts: int = 3
    reconnect_delay: float = 5.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPReconnectionHandlerDependencies",
            connect_by_transport=self.connect_by_transport,
            db_mcp=self.db_mcp,
            event_bus=self.event_bus,
            max_reconnect_attempts=self.max_reconnect_attempts,
            reconnect_delay=self.reconnect_delay,
            shutdown_event=self.shutdown_event,
        )


class MCPReconnectionHandler:

    def __init__(self, deps: MCPReconnectionHandlerDependencies) -> None:
        self._db_mcp = deps.db_mcp
        self._event_bus = deps.event_bus
        self._shutdown_event = deps.shutdown_event
        self._connect_by_transport = deps.connect_by_transport
        self._max_reconnect_attempts = deps.max_reconnect_attempts
        self._reconnect_delay = deps.reconnect_delay

    async def attempt_reconnection(self, connection: MCPServerConnection) -> bool:
        logger = get_logger(LOGGER_NAME)
        if not connection.config.auto_reconnect:
            return False
        if connection.status == MCPServerStatus.AUTH_REQUIRED:
            return False
        while not self._shutdown_event.is_set():
            async with connection.request_state.lock:
                if connection.task_state.user_disconnected:
                    logger.debug(
                        "Aborting reconnection for %s: user disconnected",
                        connection.config.name,
                    )
                    return False
                if connection.reconnect_attempts >= self._max_reconnect_attempts:
                    break
                connection.reconnect_attempts += 1
                attempt_number = connection.reconnect_attempts
                connection.status = MCPServerStatus.RECONNECTING
            attempt_msg = f"Attempt {attempt_number}/{self._max_reconnect_attempts}"
            await self._db_mcp.update_mcp_server_status(
                connection.config.id,
                MCPServerStatus.RECONNECTING.value,
                attempt_msg,
            )
            logger.debug(
                "Reconnecting to MCP server %s (attempt %d/%d)",
                connection.config.name,
                attempt_number,
                self._max_reconnect_attempts,
            )
            await asyncio.sleep(self._reconnect_delay)
            async with connection.request_state.lock:
                if connection.task_state.user_disconnected:
                    return False
            try:
                if await self._connect_by_transport(connection):
                    async with connection.request_state.lock:
                        connection.status = MCPServerStatus.CONNECTED
                        connection.connected_at = epoch_seconds_float()
                        connection.reconnect_attempts = 0
                        connection.task_state.user_disconnected = False
                    await self._db_mcp.update_mcp_server_status(
                        connection.config.id,
                        MCPServerStatus.CONNECTED.value,
                    )
                    await self._event_bus.publish(
                        MCPServerConnectedEvent(
                            server_id=connection.config.id,
                            server_name=connection.config.name,
                            tools_count=len(connection.tools),
                            resources_count=len(connection.resources),
                        ),
                    )
                    logger.info("Reconnected to MCP server: %s", connection.config.name)
                    return True
            except RECOVERABLE_EXCEPTIONS as exception:
                async with connection.request_state.lock:
                    connection.last_error = str(exception)
                log_exception(
                    logger,
                    exception,
                    message="Reconnection attempt failed.",
                    operation=OPERATION,
                    details={"server_name": connection.config.name},
                    level="warning",
                )
        async with connection.request_state.lock:
            connection.status = MCPServerStatus.ERROR
        error_msg = f"Max reconnection attempts ({self._max_reconnect_attempts}) exceeded"
        await self._db_mcp.update_mcp_server_status(
            connection.config.id,
            MCPServerStatus.ERROR.value,
            error_msg,
        )
        logger.warning(
            "Max reconnection attempts exceeded for MCP server: %s",
            connection.config.name,
        )
        return False
