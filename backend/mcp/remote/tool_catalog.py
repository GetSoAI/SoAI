"""SoAI - MCP remote tool catalog key and cache helpers [backend/mcp/remote/tool_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from mcp.protocol.types import MCPServerStatus
from mcp.remote.internal_protocols import MCPRemoteToolCatalogSurface

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.protocol.connection_state import MCPServerConnection

__all__ = (
    "build_tool_catalog_key",
    "build_tool_catalog_snapshot",
    "list_all_tools_method",
    "tool_catalog_version_method",
)


def _tools_payload_id(tools: list[JSONDict]) -> int:
    payload = serialize_json_compact_stable(tools)
    return hash(payload)


def build_tool_catalog_key(
    connections: dict[str, MCPServerConnection],
) -> tuple[tuple[str, int, int], ...]:
    key_items: list[tuple[str, int, int]] = []
    for connection in connections.values():
        if connection.status != MCPServerStatus.CONNECTED:
            continue
        tools_count = len(connection.tools)
        tools_id = _tools_payload_id(connection.tools)
        key_items.append((connection.config.id, tools_id, tools_count))
    key_items.sort(key=lambda item: item[0])
    return tuple(key_items)


def build_tool_catalog_snapshot(
    connections: dict[str, MCPServerConnection],
) -> list[JSONDict]:
    snapshot: list[JSONDict] = []
    for connection in connections.values():
        if connection.status != MCPServerStatus.CONNECTED:
            continue
        for tool in connection.tools:
            snapshot.append(
                {
                    **tool,
                    "server_id": connection.config.id,
                    "server_name": connection.config.name,
                },
            )
    return snapshot


async def tool_catalog_version_method(self: MCPRemoteToolCatalogSurface) -> str:
    async with self.connection_registry.connections_lock:
        key = build_tool_catalog_key(self.connection_registry.connections)
    if not key:
        return "none"
    return "|".join(
        f"{server_id}:{tools_id}:{tools_count}" for server_id, tools_id, tools_count in key
    )


async def list_all_tools_method(self: MCPRemoteToolCatalogSurface) -> list[JSONDict]:
    async with self.connection_registry.connections_lock:
        key = build_tool_catalog_key(self.connection_registry.connections)
        if self.tool_catalog_cache_key == key:
            return list(self.tool_catalog_cache_snapshot)
        snapshot = build_tool_catalog_snapshot(self.connection_registry.connections)
        self.tool_catalog_cache_key = key
        self.tool_catalog_cache_snapshot = tuple(snapshot)
        return list(self.tool_catalog_cache_snapshot)
