"""SoAI - Subagent mode and tool policy [backend/features/agent/subagents/policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent_mode import coerce_agent_mode_or_none, is_plan_or_execute_agent_mode
from core.agent_tool_policy import build_subagent_tool_map
from core.errors.exceptions import ValidationError
from core.mcp.default_tool_names import SUBAGENT_FORBIDDEN_UNQUALIFIED_TOOL_NAMES
from core.orchestrator.types import MCPToolContext

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_subagent_tool_context",
    "resolve_subagent_mode",
)


def resolve_subagent_mode(parent_mode: str, requested_mode: str | None) -> str:
    normalized_parent_mode = coerce_agent_mode_or_none(parent_mode)
    normalized_requested_mode = coerce_agent_mode_or_none(requested_mode)
    if normalized_parent_mode is None or not is_plan_or_execute_agent_mode(normalized_parent_mode):
        raise ValidationError("Subagents can be spawned only from plan or execute mode.")
    if requested_mode is None or not requested_mode.strip():
        return normalized_parent_mode
    if normalized_requested_mode is None or not is_plan_or_execute_agent_mode(
        normalized_requested_mode,
    ):
        raise ValidationError("subagent_spawn.mode must be plan or execute when provided.")
    if normalized_parent_mode == "plan" and normalized_requested_mode != "plan":
        raise ValidationError("Plan mode can spawn only plan-mode subagents.")
    return normalized_requested_mode


def build_subagent_tool_context(
    parent_tool_context: MCPToolContext,
    *,
    subagent_mode: str,
    requested_tools: tuple[str, ...] | None,
) -> MCPToolContext:
    text_only_requested = requested_tools == ()
    normalized_requested_tools = (
        tuple(name for name in requested_tools if isinstance(name, str) and name.strip())
        if requested_tools is not None
        else None
    )
    subagent_tool_map: dict[str, JSONDict] = build_subagent_tool_map(
        parent_tool_context.tool_map,
        subagent_mode=subagent_mode,
        requested_tools=normalized_requested_tools,
        forbidden_tool_names=SUBAGENT_FORBIDDEN_UNQUALIFIED_TOOL_NAMES,
        forbidden_prefixes=("automation_",),
    )
    if (
        is_plan_or_execute_agent_mode(subagent_mode)
        and not text_only_requested
        and not subagent_tool_map
    ):
        raise ValidationError("Subagent execution requires at least one available tool.")
    if (
        normalized_requested_tools is not None
        and normalized_requested_tools
        and not subagent_tool_map
    ):
        raise ValidationError("Requested subagent tools are unavailable.")
    return MCPToolContext(
        conv_id=parent_tool_context.conv_id,
        message_index=parent_tool_context.message_index,
        user_id=parent_tool_context.user_id,
        tool_map=subagent_tool_map,
        visible_tool_names=tuple(subagent_tool_map.keys()),
        tool_approval_required=parent_tool_context.tool_approval_required,
        assistant_at_ms=parent_tool_context.assistant_at_ms,
        assistant_turn_at_ms=parent_tool_context.assistant_turn_at_ms,
        model_variant_index=parent_tool_context.model_variant_index,
        user_interaction_timeout_ms=parent_tool_context.user_interaction_timeout_ms,
    )
