"""SoAI - Internal conversation skill tool authority [backend/mcp/tools/skill_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.input_claim import ConversationInputClaim
from core.skills.execution import SkillExecutionIdentity
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.skills.execution import SkillExecutionContext
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("SkillToolContext", "require_skill_tool_context")


@dataclass(frozen=True, slots=True)
class SkillToolContext:
    request: RequestContext
    call: CurrentToolCallIdentity
    execution: SkillExecutionContext
    identity: SkillExecutionIdentity


def require_skill_tool_context(
    utility_tools: MCPUtilityToolsProtocol, *, tool_name: str
) -> SkillToolContext:
    request = utility_tools.active_request_context.get(None)
    call = utility_tools.active_tool_call_context.get(None)
    if request is None or call is None:
        raise MCPToolError(-32603, "Skill tools require an internal SoAI conversation turn.")
    execution = request.skill_execution_context
    selected_tools = request.mcp_tool_context
    if execution is None or not execution.snapshot.available or selected_tools is None:
        raise MCPToolError(-32603, "No skills are available in this conversation turn.")
    if (
        not request.agent_turn_id
        or not request.agent_turn_execution_token
        or call.turn_id != request.agent_turn_id
        or call.iteration_index != request.agent_iteration_index
        or call.tool_name != tool_name
    ):
        raise MCPToolError(-32603, "Skill tool execution identity is unavailable or inconsistent.")
    snapshot = execution.snapshot
    if (
        request.user_id != snapshot.user_id
        or call.user_id != snapshot.user_id
        or selected_tools.user_id != snapshot.user_id
        or request.conversation_input_id != snapshot.input_id
    ):
        raise MCPToolError(-32603, "Skill tool ownership differs from the admitted input.")
    if call.conv_id != snapshot.conv_id or selected_tools.conv_id != snapshot.conv_id:
        raise MCPToolError(-32603, "Skill tools cannot access another conversation.")
    if tool_name not in selected_tools.tool_map:
        raise MCPToolError(-32603, "This skill tool is not selected for the current turn.")
    return SkillToolContext(
        request=request,
        call=call,
        execution=execution,
        identity=SkillExecutionIdentity(
            snapshot.user_id,
            snapshot.conv_id,
            snapshot.input_id,
            request.agent_turn_id,
            request.agent_turn_execution_token,
            ConversationInputClaim.from_fields(
                request.conversation_input_id,
                request.conversation_input_claim_generation,
                request.conversation_input_claim_owner,
                request.conversation_input_server_boot_id,
            ),
        ),
    )
