"""SoAI - MCP stop conversation tool implementation [backend/mcp/tools/stop_conversation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.conversation_stop_signal import (
    STOP_CONVERSATION_TOOL_NAME,
    build_stop_conversation_signal,
)
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_stop_conversation",)


async def tool_stop_conversation(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, ())
    active_turn_required_message = (
        f"{STOP_CONVERSATION_TOOL_NAME} requires an active conversation turn."
    )
    request_context = utility_tools.active_request_context.get(None)
    tool_call_identity = utility_tools.active_tool_call_context.get(None)
    if request_context is None or tool_call_identity is None:
        raise MCPToolError(-32603, active_turn_required_message)
    turn_id = request_context.agent_turn_id
    conv_id = tool_call_identity.conv_id.strip()
    if turn_id is None or not turn_id.strip() or not conv_id:
        raise MCPToolError(-32603, active_turn_required_message)
    iteration_index = request_context.agent_iteration_index
    if iteration_index is None:
        iteration_index = tool_call_identity.iteration_index
    return build_stop_conversation_signal(
        conv_id=conv_id,
        turn_id=turn_id.strip(),
        iteration_index=iteration_index,
    )
