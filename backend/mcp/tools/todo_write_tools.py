"""SoAI - MCP utility tool: todo_write [backend/mcp/tools/todo_write_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.agent_state_payloads import (
    persist_todo_payload,
    run_agent_state_write_operation,
)
from mcp.tools.error import get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_todo_write",)


async def tool_todo_write(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(owner_key, tool_name="todo_write")
    return await run_agent_state_write_operation(
        persist_todo_payload(
            utility_tools,
            conv_id=conv_id,
            user_id=user_id,
            todo_value=get_arg(arguments, "todo"),
            explanation_value=arguments.get("explanation"),
        ),
        conflict_message="Unable to persist agent todo state due to concurrent modifications.",
    )
