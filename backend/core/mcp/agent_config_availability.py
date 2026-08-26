"""SoAI - Agent MCP configuration filtering by available tools [backend/core/mcp/agent_config_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig

__all__ = ("filter_normalized_mcp_to_available_tools",)


def filter_normalized_mcp_to_available_tools(
    normalized_mcp: NormalizedAgentMCPConfig,
    available_tool_names: set[str],
) -> NormalizedAgentMCPConfig:
    return NormalizedAgentMCPConfig(
        default_tools=[
            tool_name
            for tool_name in normalized_mcp.default_tools
            if tool_name in available_tool_names
        ],
        plan_tools=[
            tool_name
            for tool_name in normalized_mcp.plan_tools
            if tool_name in available_tool_names
        ],
        execute_tools=[
            tool_name
            for tool_name in normalized_mcp.execute_tools
            if tool_name in available_tool_names
        ],
        server_configs=dict(normalized_mcp.server_configs),
        tools_enabled=normalized_mcp.tools_enabled,
        tool_approval_required=normalized_mcp.tool_approval_required,
    )
