"""SoAI - Agent steer interrupt helpers [backend/features/agent/runtime/tool_execution_steer_interrupt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.orchestrator.types import MCPToolContext

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversation_inputs import (
        DatabaseConversationInputsProtocol,
    )
    from core.runtime.request_context import RequestContext

__all__ = (
    "AgentTurnInterruptedBySteer",
    "STEER_INTERRUPTED_ERROR_MESSAGE",
    "STEER_INTERRUPTED_ERROR_TYPE",
    "should_interrupt_turn_for_steer",
)

STEER_INTERRUPTED_ERROR_TYPE = "steer_interrupted"
STEER_INTERRUPTED_ERROR_MESSAGE = "Agent turn interrupted by steer."


class AgentTurnInterruptedBySteer(Exception):
    def __init__(self, executed_tool_calls: int) -> None:
        super().__init__(STEER_INTERRUPTED_ERROR_MESSAGE)
        self.executed_tool_calls = int(executed_tool_calls)


async def should_interrupt_turn_for_steer(
    *,
    request_context: RequestContext,
    database_input_queue: DatabaseConversationInputsProtocol,
    tool_context: MCPToolContext,
) -> bool:
    if (
        request_context.conversation_input_id is None
        or request_context.agent_turn_scope == TURN_SCOPE_SUBAGENT
    ):
        return False
    conv_id = str(tool_context.conv_id or "").strip()
    user_id_value = tool_context.user_id
    user_id = int(user_id_value)
    if not conv_id or user_id <= 0:
        return False
    return await database_input_queue.has_pending_input_type(
        conv_id=conv_id,
        user_id=user_id,
        input_type="steer",
    )
