"""SoAI - RequestContext agent runtime field helpers [backend/core/runtime/request_context_agent_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.settings_types import AgentSettings
from core.runtime.request_context import RequestContext

__all__ = (
    "apply_agent_runtime_context_fields",
    "read_agent_requested_model",
    "reset_agent_runtime_context_fields",
)


def apply_agent_runtime_context_fields(
    context: RequestContext,
    settings: AgentSettings,
    requested_model: str | None,
    turn_scope: str | None,
) -> None:
    context.agent_mode = settings.mode
    context.agent_workspace_path = settings.workspace_path
    context.agent_requested_model = requested_model
    if turn_scope is not None:
        context.agent_turn_scope = turn_scope


def reset_agent_runtime_context_fields(context: RequestContext) -> None:
    context.agent_turn_id = None
    context.agent_turn_scope = None
    context.agent_turn_execution_token = None
    context.agent_iteration_index = None
    context.agent_parent_turn_id = None
    context.agent_parent_tool_call_id = None
    context.agent_parent_iteration_index = None
    context.agent_display_name = None
    context.agent_requested_model = None
    context.agent_owner_task_id = None
    context.mcp_tool_context = None
    context.agent_mode = None
    context.agent_workspace_path = None


def read_agent_requested_model(context: RequestContext) -> str | None:
    requested_model_value = context.agent_requested_model
    if requested_model_value is None:
        return None
    normalized_requested_model = requested_model_value.strip()
    return normalized_requested_model or None
