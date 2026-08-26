"""SoAI - MCP remote connected-server catalog operations [backend/mcp/remote/listings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.protocol.types import MCPServerStatus
from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "list_all_prompts",
    "list_all_resources",
    "list_all_tools",
    "list_connected_servers",
)


async def list_connected_servers(
    connection_registry: MCPConnectionRegistryProtocol,
) -> list[JSONDict]:
    async with connection_registry.connections_lock:
        return [
            {
                "id": connection.config.id,
                "name": connection.config.name,
                "transport_type": connection.config.transport_type.value,
                "endpoint": connection.config.endpoint,
                "status": connection.status.value,
                "tools_count": len(connection.tools),
                "resources_count": len(connection.resources),
                "connected_at_ms": (
                    int(connection.connected_at * 1000)
                    if isinstance(connection.connected_at, float)
                    else None
                ),
                "last_error": connection.last_error,
            }
            for connection in connection_registry.connections.values()
        ]


async def list_all_tools(
    connection_registry: MCPConnectionRegistryProtocol,
) -> list[JSONDict]:
    async with connection_registry.connections_lock:
        return [
            {
                **tool,
                "server_id": connection.config.id,
                "server_name": connection.config.name,
            }
            for connection in connection_registry.connections.values()
            if connection.status == MCPServerStatus.CONNECTED
            for tool in connection.tools
        ]


async def list_all_resources(
    connection_registry: MCPConnectionRegistryProtocol,
) -> list[JSONDict]:
    async with connection_registry.connections_lock:
        return [
            {
                **resource,
                "server_id": connection.config.id,
                "server_name": connection.config.name,
            }
            for connection in connection_registry.connections.values()
            if connection.status == MCPServerStatus.CONNECTED
            for resource in connection.resources
        ]


async def list_all_prompts(
    connection_registry: MCPConnectionRegistryProtocol,
) -> list[JSONDict]:
    async with connection_registry.connections_lock:
        return [
            {
                **prompt,
                "server_id": connection.config.id,
                "server_name": connection.config.name,
            }
            for connection in connection_registry.connections.values()
            if connection.status == MCPServerStatus.CONNECTED
            for prompt in connection.prompts
        ]
