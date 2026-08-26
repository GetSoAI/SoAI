"""SoAI - MCP registry tool name suggestion helpers [backend/mcp/registry/tool_name_candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.tool_name_suggestions import (
    append_tool_suggestions_to_message,
    build_tool_name_candidates_from_named_descriptions,
    build_tool_name_candidates_from_remote_tools,
    suggest_tool_names,
)
from mcp.protocol.types import MCPJSONRPCError, MCPServerStatus

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

__all__ = (
    "build_registry_unknown_tool_error",
    "build_registry_unknown_tool_message",
)


async def build_registry_unknown_tool_message(
    manager: MCPRegistryManagerProtocol,
    *,
    tool_name: str,
) -> str:
    return (await _build_registry_unknown_tool_message_details(manager, tool_name=tool_name))[0]


async def build_registry_unknown_tool_error(
    manager: MCPRegistryManagerProtocol,
    *,
    tool_name: str,
) -> MCPJSONRPCError:
    message, suggestions = await _build_registry_unknown_tool_message_details(
        manager,
        tool_name=tool_name,
    )
    return MCPJSONRPCError(
        -32602,
        message,
        data={
            "requested_tool_name": tool_name,
            "suggested_tool_names": list(suggestions),
        },
    )


async def _build_registry_unknown_tool_message_details(
    manager: MCPRegistryManagerProtocol,
    *,
    tool_name: str,
) -> tuple[str, tuple[str, ...]]:
    suggestions = await _build_registry_unknown_tool_suggestions(manager, tool_name=tool_name)
    message = append_tool_suggestions_to_message(f"Unknown tool: {tool_name}", suggestions)
    return message, suggestions


async def _build_registry_unknown_tool_suggestions(
    manager: MCPRegistryManagerProtocol,
    *,
    tool_name: str,
) -> tuple[str, ...]:
    local_definitions = manager.registration.tool_definitions()
    local_descriptions: dict[str, str | None] = {}
    for registered_name in manager.state.registration.registered_tools:
        definition = local_definitions.get(registered_name)
        description_value = definition.get("description") if isinstance(definition, dict) else None
        description = (
            description_value.strip()
            if isinstance(description_value, str) and description_value.strip()
            else None
        )
        local_descriptions[registered_name] = description
    remote_tools = await _collect_connected_remote_tools(manager)
    return suggest_tool_names(
        tool_name,
        (
            *build_tool_name_candidates_from_named_descriptions(local_descriptions),
            *build_tool_name_candidates_from_remote_tools(remote_tools),
        ),
    )


async def _collect_connected_remote_tools(
    manager: MCPRegistryManagerProtocol,
) -> list[JSONDict]:
    remote_tools: list[JSONDict] = []
    async with manager.connection_registry.connections_lock:
        for connection in manager.connection_registry.connections.values():
            if connection.status != MCPServerStatus.CONNECTED:
                continue
            for remote_tool in connection.tools:
                remote_tools.append({**remote_tool, "server_id": connection.config.id})
    return remote_tools
