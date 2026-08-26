"""SoAI - MCP remote server tool routing [backend/mcp/registry/tools_remote_routing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_mcp import MCPToolInvokedEvent
from core.mcp.qualified_name import decode_qualified_tool_name
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
    MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED,
)
from core.types.json_value import coerce_json_dict, is_json_value
from mcp.protocol.types import MCPJSONRPCError, MCPServerStatus
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.registry.tool_name_candidates import build_registry_unknown_tool_error

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("try_route_to_remote_server_tool",)


async def try_route_to_remote_server_tool(
    manager: MCPRegistryManagerProtocol,
    name: str,
    arguments: JSONDict,
    start_time: float,
) -> JSONDict | None:
    if name in manager.state.registration.registered_tools:
        return None
    potential_server_id, tool_name = decode_qualified_tool_name(name)
    if potential_server_id is None:
        return None
    async with manager.connection_registry.connections_lock:
        connection = manager.connection_registry.connections.get(potential_server_id)
        if connection is None:
            return None
        connection_status = connection.status
        connection_config_id = connection.config.id
        available_remote_tool_names = frozenset(
            remote_tool_name
            for remote_tool in connection.tools
            for remote_tool_name in [remote_tool.get("name")]
            if isinstance(remote_tool_name, str)
        )
    if connection_status != MCPServerStatus.CONNECTED:
        return None
    if tool_name not in available_remote_tool_names:
        raise await build_registry_unknown_tool_error(manager, tool_name=name)
    result = await manager.host_mode.send_host_mode_request(
        connection_config_id,
        "tools/call",
        {"name": tool_name, "arguments": arguments},
    )
    if result is None:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
        raise MCPJSONRPCError(-32603, f"No response from server {potential_server_id}")
    if not is_json_value(result):
        raise StateError("Remote tool response must be JSON-compatible.")
    result_dict = coerce_json_dict(result)
    if result_dict is None:
        raise MCPJSONRPCError(-32603, "Remote tool response must be an object.")
    manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED)
    await manager.event_bus.publish(
        MCPToolInvokedEvent(
            server_id=potential_server_id,
            tool_name=tool_name,
            success=True,
            execution_time_ms=int((time.monotonic() - start_time) * 1000),
        ),
    )
    return result_dict
