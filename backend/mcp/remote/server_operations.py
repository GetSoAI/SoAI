"""SoAI - MCP remote server records, lookups, tool calls, and resource reads [backend/mcp/remote/server_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.protocols import EventBusProtocol
from core.events.types_mcp import (
    MCPServerAddedEvent,
    MCPServerRemovedEvent,
    MCPToolInvokedEvent,
)
from core.mcp.protocols_storage import DatabaseMCPProtocol
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.types import (
    MCPJSONRPCError,
    MCPServerConfig,
    MCPServerStatus,
    MCPTransportType,
)
from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol
from mcp.remote.config_coercion import mcp_server_config_from_db_row
from mcp.remote.internal_protocols import MCPConnectionManagerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "add_server",
    "get_connected_server",
    "invoke_tool",
    "read_resource",
    "remove_server",
    "update_cached_server_config",
)


async def get_connected_server(
    connection_registry: MCPConnectionRegistryProtocol,
    server_id: str,
) -> MCPServerConnection:
    async with connection_registry.connections_lock:
        connection = connection_registry.connections.get(server_id)
        if not connection:
            raise MCPJSONRPCError(-32603, f"Server not found: {server_id}")
        if connection.status != MCPServerStatus.CONNECTED:
            raise MCPJSONRPCError(-32603, f"Server not connected: {connection.config.name}")
        return connection


async def add_server(
    db_mcp: DatabaseMCPProtocol,
    event_bus: EventBusProtocol,
    name: str,
    transport_type: MCPTransportType,
    endpoint: str,
    arguments: list[str] | None = None,
    env: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    api_key: str | None = None,
    timeout_ms: int = 30000,
    auto_reconnect: bool = True,
) -> MCPServerConfig:
    server_id = f"mcp_{hashlib.sha256(f'{name}:{endpoint}'.encode()).hexdigest()[:16]}"
    row = await db_mcp.add_mcp_server(
        server_id=server_id,
        name=name,
        transport_type=transport_type.value,
        endpoint=endpoint,
        args=arguments,
        env=env,
        headers=headers,
        api_key=api_key,
        timeout_ms=timeout_ms,
        auto_reconnect=auto_reconnect,
    )
    if not row:
        raise MCPJSONRPCError(-32603, f"Failed to add MCP server: {name}")
    await event_bus.publish(MCPServerAddedEvent(server_id=server_id, server_name=name))
    return mcp_server_config_from_db_row(row)


async def update_cached_server_config(
    connection_registry: MCPConnectionRegistryProtocol,
    config: MCPServerConfig,
) -> None:
    async with connection_registry.connections_lock:
        if config.id in connection_registry.connections:
            connection_registry.connections[config.id].config = config


async def remove_server(
    connection_registry: MCPConnectionRegistryProtocol,
    connection_manager: MCPConnectionManagerProtocol,
    db_mcp: DatabaseMCPProtocol,
    event_bus: EventBusProtocol,
    server_id: str,
) -> bool:
    async with connection_registry.connections_lock:
        connection = connection_registry.connections.pop(server_id, None)
    if connection:
        await connection_manager.disconnect_connection(
            connection,
            server_id=server_id,
            reason="Server removed",
        )
    if await db_mcp.delete_mcp_server(server_id):
        await event_bus.publish(MCPServerRemovedEvent(server_id=server_id))
        return True
    return False


async def invoke_tool(
    connection_registry: MCPConnectionRegistryProtocol,
    event_bus: EventBusProtocol,
    send_request: Callable[
        [MCPServerConnection, str, JSONDict],
        Awaitable[JSONValue | None],
    ],
    server_id: str,
    tool_name: str,
    arguments: JSONDict,
) -> JSONDict:
    start_time = time.monotonic()
    connection = await get_connected_server(connection_registry, server_id)
    response = await send_request(
        connection,
        "tools/call",
        {"name": tool_name, "arguments": arguments},
    )
    if response is None or not isinstance(response, dict):
        raise MCPJSONRPCError(-32603, "No response from server")
    await event_bus.publish(
        MCPToolInvokedEvent(
            server_id=server_id,
            tool_name=tool_name,
            success=True,
            execution_time_ms=int((time.monotonic() - start_time) * 1000),
        ),
    )
    return response


async def read_resource(
    connection_registry: MCPConnectionRegistryProtocol,
    send_request: Callable[
        [MCPServerConnection, str, JSONDict],
        Awaitable[JSONValue | None],
    ],
    server_id: str,
    uri: str,
) -> JSONDict:
    connection = await get_connected_server(connection_registry, server_id)
    response = await send_request(connection, "resources/read", {"uri": uri})
    if response is None or not isinstance(response, dict):
        raise MCPJSONRPCError(-32603, "No response from server")
    return response
