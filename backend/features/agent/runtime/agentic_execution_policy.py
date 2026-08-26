"""SoAI - Shared agentic execution selection policy [backend/features/agent/runtime/agentic_execution_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent_mode import is_plan_or_execute_agent_mode
from core.orchestrator.types import MCPToolContext

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings

__all__ = (
    "normalize_tool_context_for_agent_settings",
    "should_run_agent_turn_engine",
)


def normalize_tool_context_for_agent_settings(
    *,
    agent_settings: AgentSettings,
    tool_context: MCPToolContext | None,
) -> MCPToolContext | None:
    if tool_context is None:
        return None
    if is_plan_or_execute_agent_mode(agent_settings.mode):
        return tool_context
    if tool_context.tool_map:
        return tool_context
    return None


def should_run_agent_turn_engine(
    *,
    agent_settings: AgentSettings,
    tool_context: MCPToolContext | None,
) -> bool:
    normalized_tool_context = normalize_tool_context_for_agent_settings(
        agent_settings=agent_settings,
        tool_context=tool_context,
    )
    return normalized_tool_context is not None
