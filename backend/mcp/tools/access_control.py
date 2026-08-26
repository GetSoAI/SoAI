"""SoAI - MCP utility tool ACL checks [backend/mcp/tools/access_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.access import AccessAction, AccessState
from core.state.access_policy_overrides import (
    load_access_policy_overrides,
    merge_access_policy,
)
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.user_permission_records import resolve_tool_user_is_admin

__all__ = ("require_tool_action",)


async def _resolve_current_user_actions(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
) -> frozenset[AccessAction]:
    if user_id <= 0:
        return frozenset()
    is_admin = await resolve_tool_user_is_admin(utility_tools, user_id=user_id)
    access_state = AccessState.ADMIN if is_admin else AccessState.STANDARD
    overrides = await load_access_policy_overrides(utility_tools.database_plugins)
    policy = merge_access_policy(overrides)
    return policy.get(access_state, frozenset())


async def require_tool_action(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    action: AccessAction,
    tool_name: str,
) -> int:
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name=tool_name,
        message=f"User authentication required for {tool_name}.",
    )
    request_context = utility_tools.active_request_context.get(None)
    if request_context is not None and request_context.access_actions:
        allowed_actions = request_context.access_actions
    else:
        allowed_actions = await _resolve_current_user_actions(utility_tools, user_id=user_id)
    required_actions = frozenset({AccessAction.MCP_USE, action})
    missing_actions = required_actions.difference(allowed_actions)
    if missing_actions:
        missing_text = ", ".join(sorted(missing_action.value for missing_action in missing_actions))
        raise MCPToolError(-32603, f"{missing_text} permission required for {tool_name}.")
    return user_id
