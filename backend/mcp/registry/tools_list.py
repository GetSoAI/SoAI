"""SoAI - MCP tools/list handler [backend/mcp/registry/tools_list.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.qualified_name import encode_qualified_tool_name
from core.mcp.tool_entries import build_remote_tool_entry, build_tool_entry
from mcp.protocol.types import MCPServerStatus
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.registry.tools_definitions import build_tool_definitions
from mcp.tools.openai_owner_context import has_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_tools_list",)


def _should_expose_local_tool(
    manager: MCPRegistryManagerProtocol,
    *,
    tool_name: str,
) -> bool:
    if tool_name != "browser_autofill_secret":
        return True
    session = manager.context.get_active_session()
    if session is None:
        return False
    return has_openai_conversation_owner(
        str(session.client_id or ""),
    ) or has_openai_conversation_owner(str(session.session_id or ""))


async def handle_tools_list(manager: MCPRegistryManagerProtocol, parameters: JSONDict) -> JSONDict:
    tools: list[JSONDict] = []
    tool_definitions = build_tool_definitions()
    local_tool_names = sorted(manager.state.registration.registered_tools.keys())
    for name in local_tool_names:
        if not _should_expose_local_tool(manager, tool_name=name):
            continue
        definition = tool_definitions.get(name, {})
        tools.append(build_tool_entry(name=name, definition=definition))
    async with manager.connection_registry.connections_lock:
        for connection in manager.connection_registry.connections.values():
            if connection.status != MCPServerStatus.CONNECTED:
                continue
            server_id = connection.config.id
            for tool in connection.tools:
                tool_name = tool.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                tools.append(
                    build_remote_tool_entry(
                        name=encode_qualified_tool_name(server_id, tool_name),
                        tool_definition=tool,
                    ),
                )
    tools.sort(key=lambda tool: str(tool.get("name", "")))
    cursor_value = parameters.get("cursor")
    cursor = cursor_value if isinstance(cursor_value, str) else None
    page, next_cursor = manager.pagination.paginate_list(tools, cursor)
    return {"tools": page, **({"nextCursor": next_cursor} if next_cursor else {})}
