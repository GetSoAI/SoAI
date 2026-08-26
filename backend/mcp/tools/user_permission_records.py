"""SoAI - MCP tool user permission record access [backend/mcp/tools/user_permission_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("resolve_tool_user_is_admin",)


async def resolve_tool_user_is_admin(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
) -> bool:
    user = await utility_tools.database_users.get_account_by_id(user_id)
    if user is None:
        raise MCPToolError(-32603, "User record not found for permission check.")
    try:
        is_admin = user.get("is_admin")
    except AttributeError as exception:
        raise MCPToolError(-32603, "User record not available for permission check.") from exception
    return is_admin is True
