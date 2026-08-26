"""SoAI - MCP utility tool: plan_write [backend/mcp/tools/plan_write_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.agent_state_payloads import (
    persist_plan_payload,
    run_agent_state_write_operation,
)
from mcp.tools.error import get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_plan_write",)


async def tool_plan_write(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(owner_key, tool_name="plan_write")
    return await run_agent_state_write_operation(
        persist_plan_payload(
            utility_tools,
            conv_id=conv_id,
            user_id=user_id,
            title_value=arguments.get("title"),
            markdown_value=get_arg(arguments, "markdown"),
        ),
        conflict_message="Unable to persist agent plan due to concurrent modifications.",
    )
