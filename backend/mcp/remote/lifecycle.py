"""SoAI - MCP remote service lifecycle operations [backend/mcp/remote/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.protocol.types import MCPServerConfig
from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol
from mcp.remote.config_coercion import mcp_server_config_from_db_row
from mcp.remote.internal_protocols import MCPConnectionManagerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "auto_connect_servers",
    "shutdown_remote_service",
)

LOGGER_NAME = "SoAI.mcp.remote.lifecycle"
OPERATION = "mcp.remote.auto_connect"
OPERATION_SHUTDOWN = "mcp.remote.shutdown"


async def auto_connect_servers(
    db_mcp_get_all_servers: Callable[[bool], Awaitable[list[JSONDict]]],
    connection_manager_connect: Callable[[MCPServerConfig], Awaitable[bool]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    for row in await db_mcp_get_all_servers(True):
        if row.get("enabled", True):
            try:
                await connection_manager_connect(mcp_server_config_from_db_row(row))
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to auto-connect",
                    operation=OPERATION,
                    details={"server_name": row["name"]},
                )


async def shutdown_remote_service(
    connection_registry: MCPConnectionRegistryProtocol,
    connection_manager: MCPConnectionManagerProtocol,
) -> None:
    async with connection_registry.connections_lock:
        connections = list(connection_registry.connections.items())
        connection_registry.connections.clear()
    if connections:
        shutdown_results = await asyncio.gather(
            *[
                connection_manager.disconnect_connection(conn, server_id=sid, reason="Shutdown")
                for sid, conn in connections
                if conn is not None
            ],
            return_exceptions=True,
        )
        logger = get_logger(LOGGER_NAME)
        for shutdown_result in shutdown_results:
            if isinstance(shutdown_result, asyncio.CancelledError):
                raise shutdown_result
            if isinstance(shutdown_result, BaseException):
                log_handled_exception(
                    logger,
                    shutdown_result,
                    message="MCP remote connection disconnect failed during shutdown (non-critical).",
                    operation=OPERATION_SHUTDOWN,
                    level="warning",
                )
