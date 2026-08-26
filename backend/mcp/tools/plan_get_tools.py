"""SoAI - MCP utility tool: plan_get [backend/mcp/tools/plan_get_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.agent_state_payloads import read_plan_payload
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_plan_get",)


async def tool_plan_get(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    _ = arguments
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(owner_key, tool_name="plan_get")
    payload = await read_plan_payload(utility_tools, conv_id=conv_id, user_id=user_id)
    revision_value = payload.get("revision")
    return {
        "revision": int(revision_value) if isinstance(revision_value, int) else 0,
        "updated_at_ms": payload.get("updated_at_ms"),
        "title": payload.get("title"),
        "markdown": payload.get("markdown"),
    }
