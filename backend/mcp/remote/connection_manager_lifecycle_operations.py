"""SoAI - MCP remote connection manager lifecycle operations [backend/mcp/remote/connection_manager_lifecycle_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.events.types_mcp import MCPServerDisconnectedEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_remote import (
    MCP_REMOTE_COUNTER_CONNECTIONS_DISCONNECTIONS,
)
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC, STANDARD_DELAY_SEC
from mcp.protocol.connection_request_state import cancel_all_pending_requests
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.types import MCPServerStatus
from mcp.remote.internal_protocols import MCPConnectionManagerOperationsSurface

__all__ = (
    "attempt_reconnection_method",
    "cleanup_connection_resources_method",
    "disconnect_connection_method",
    "disconnect_from_server_method",
)

LOGGER_NAME = "SoAI.mcp.remote.connection_manager_lifecycle_operations"
OPERATION_MCP_REMOTE_CLEANUP_CONNECTION_RESOURCES_READER_TASK = (
    "mcp.remote.cleanup_connection_resources.reader_task"
)
OPERATION_MCP_REMOTE_DISCONNECT_CONNECTION = "mcp.remote.disconnect_connection"


async def cleanup_connection_resources_method(
    self: MCPConnectionManagerOperationsSurface,
    connection: MCPServerConnection,
) -> None:
    logger = get_logger(LOGGER_NAME)
    manager_class_name = self.__class__.__name__

    reader_task = connection.task_state.reader_task
    connection.task_state.reader_task = None
    if reader_task is not None:
        if not reader_task.done():
            reader_task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(reader_task, return_exceptions=True),
                    timeout=LOCAL_IO_TIMEOUT_SEC,
                )
            except TimeoutError:
                logger.warning(
                    "Reader task for %s did not terminate within 5s, forcing cancellation.",
                    connection.config.name,
                )
                reader_task.cancel()
                try:
                    await asyncio.wait_for(
                        asyncio.gather(reader_task, return_exceptions=True),
                        timeout=STANDARD_DELAY_SEC,
                    )
                except TimeoutError:
                    logger.warning(
                        "Reader task for %s did not terminate after forced cancellation.",
                        connection.config.name,
                    )
        if reader_task.done() and not reader_task.cancelled():
            try:
                exception = reader_task.exception()
            except asyncio.CancelledError:
                exception = None
            if exception is not None:
                log_handled_exception(
                    logger,
                    exception,
                    message="MCP reader task completed with an exception (non-critical).",
                    operation=OPERATION_MCP_REMOTE_CLEANUP_CONNECTION_RESOURCES_READER_TASK,
                    details={"server_name": connection.config.name, "manager": manager_class_name},
                    level="debug",
                )

    process = connection.process
    if process is not None and process.returncode is None:
        try:
            try:
                process.terminate()
            except ProcessLookupError:
                logger.debug(
                    "Process for %s already exited before terminate.",
                    connection.config.name,
                )
            try:
                await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    logger.debug(
                        "Process for %s already exited before kill.",
                        connection.config.name,
                    )
                try:
                    await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
                except TimeoutError:
                    logger.warning(
                        "Process for %s did not terminate within 5s after kill.",
                        connection.config.name,
                    )
        finally:
            connection.process = None


async def disconnect_connection_method(
    self: MCPConnectionManagerOperationsSurface,
    connection: MCPServerConnection,
    *,
    server_id: str,
    reason: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    if connection is None:
        return False
    async with connection.request_state.lock:
        connection.task_state.user_disconnected = True
    reconnect_task = connection.task_state.reconnect_task
    if reconnect_task is not None and not reconnect_task.done():
        reconnect_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(reconnect_task), timeout=RESPONSIVE_TIMEOUT_SEC)
        except (asyncio.CancelledError, TimeoutError) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Reconnect task shutdown wait failed (non-critical).",
                operation=OPERATION_MCP_REMOTE_DISCONNECT_CONNECTION,
                details={"server_id": server_id},
                level="debug",
            )
        connection.task_state.reconnect_task = None
    await self.cleanup_connection_resources(connection)
    await cancel_all_pending_requests(connection.request_state)
    connection.status = MCPServerStatus.DISCONNECTED
    connection.session_id = None
    connection.last_event_id = None
    connection.tools.clear()
    connection.resources.clear()
    connection.prompts.clear()
    await self.update_server_status(server_id, MCPServerStatus.DISCONNECTED)
    await self.event_bus.publish(MCPServerDisconnectedEvent(server_id=server_id, reason=reason))
    logger.info("Disconnected from MCP server: %s", connection.config.name)
    self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_DISCONNECTIONS)
    return True


async def disconnect_from_server_method(
    self: MCPConnectionManagerOperationsSurface,
    server_id: str,
) -> bool:
    registry = self.registry
    async with registry.connections_lock:
        connection = registry.connections.get(server_id)
    if not connection:
        return False
    return await self.disconnect_connection(
        connection,
        server_id=server_id,
        reason="User requested disconnect",
    )


async def attempt_reconnection_method(
    self: MCPConnectionManagerOperationsSurface,
    connection: MCPServerConnection,
) -> bool:
    if self.shutdown_event.is_set():
        return False
    if not connection.config.id:
        raise ValidationError("MCP connection config id is required for reconnection.")
    return await self.reconnection_handler.attempt_reconnection(connection)
