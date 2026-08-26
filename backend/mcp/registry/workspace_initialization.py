"""SoAI - MCP registry files root runtime initialization [backend/mcp/registry/workspace_initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.users.user_id import is_strict_user_id
from mcp.registry.tool_workspace_requirements import registered_tool_uses_runtime_workspace
from mcp.workspace_resolution import (
    ensure_runtime_workspace_path_from_user,
    propagate_runtime_workspace_path_for_tool_execution,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

__all__ = ("initialize_runtime_workspace_from_manager",)


async def initialize_runtime_workspace_from_manager(
    manager: MCPRegistryManagerProtocol,
    *,
    arguments: JSONDict,
    user_id: JSONValue,
    owner_key: str,
    tool_name: str,
) -> None:
    utility_tools = manager.utility_tools
    if utility_tools is None:
        return
    if not registered_tool_uses_runtime_workspace(tool_name):
        return
    if not is_strict_user_id(user_id):
        return
    resolved_workspace_path = await ensure_runtime_workspace_path_from_user(
        runtime_sessions=utility_tools.runtime_sessions,
        database_users=utility_tools.database_users,
        config=utility_tools.config,
        user_id=user_id,
        owner_key=owner_key,
    )
    propagate_runtime_workspace_path_for_tool_execution(
        utility_tools=utility_tools,
        tool_name=tool_name,
        arguments=arguments,
        owner_key=owner_key,
        workspace_path=str(resolved_workspace_path),
    )
