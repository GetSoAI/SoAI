"""SoAI - Automation interactive tool approval helpers [backend/core/automation/automation_interactive_tool_approval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict

__all__ = (
    "extract_interactive_tool_approval",
    "strip_interactive_tool_approval",
)


def extract_interactive_tool_approval(model_settings: JSONDict) -> bool:
    agent_value = model_settings.get("agent")
    agent = agent_value if isinstance(agent_value, dict) else None
    approval_value = agent.get("interactive_tool_approval") if agent is not None else None
    return approval_value is True


def strip_interactive_tool_approval(model_settings: JSONDict) -> JSONDict:
    updated_settings: JSONDict = dict(model_settings)
    agent_value = model_settings.get("agent")
    agent = agent_value if isinstance(agent_value, dict) else None
    if agent is not None and "interactive_tool_approval" in agent:
        updated_agent: JSONDict = dict(agent)
        updated_agent.pop("interactive_tool_approval", None)
        updated_settings["agent"] = updated_agent
    mcp_value = model_settings.get("mcp")
    mcp = mcp_value if isinstance(mcp_value, dict) else None
    if mcp is not None and "tool_approval_required" in mcp:
        updated_mcp: JSONDict = dict(mcp)
        updated_mcp.pop("tool_approval_required", None)
        updated_settings["mcp"] = updated_mcp
    return updated_settings
