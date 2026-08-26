"""SoAI - Subagent parent context validation [backend/features/agent/subagents/parent_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.agent_mode import is_plan_or_execute_agent_mode
from core.errors.exceptions import ValidationError
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_calls.current_tool_call import CurrentToolCallIdentity

__all__ = ("require_parent_subagent_state",)


def require_parent_subagent_state(
    active_request_context: contextvars.ContextVar[RequestContext | None],
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None],
) -> tuple[RequestContext, CurrentToolCallIdentity, MCPToolContext]:
    parent_context = active_request_context.get()
    tool_call_identity = active_tool_call_context.get()
    if parent_context is None or tool_call_identity is None:
        raise ValidationError("Subagent tools require an active agent tool-call context.")
    if parent_context.agent_turn_scope == TURN_SCOPE_SUBAGENT:
        raise ValidationError("Subagents cannot use agent_* tools.")
    if not is_plan_or_execute_agent_mode(parent_context.agent_mode):
        raise ValidationError("Subagents are available only in plan and execute mode.")
    if parent_context.agent_turn_id is None or not parent_context.agent_turn_id.strip():
        raise ValidationError("Subagent tools require an active parent turn id.")
    if parent_context.agent_iteration_index is None:
        raise ValidationError("Subagent tools require an active parent iteration index.")
    parent_tool_context = parent_context.mcp_tool_context
    if parent_tool_context is None:
        raise ValidationError("Subagent tools require an active MCP tool context.")
    return (parent_context, tool_call_identity, parent_tool_context)
