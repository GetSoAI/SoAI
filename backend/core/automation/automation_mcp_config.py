"""SoAI - Automation MCP config normalization [backend/core/automation/automation_mcp_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.automation.automation_tool_validation import (
    build_automation_tool_name_validator,
    filter_disallowed_automation_tool_names,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import (
    NormalizedAgentMCPConfig,
    build_normalized_agent_mcp_config_payload,
    normalize_agent_mcp_config,
)
from core.mcp.default_tool_names import (
    DEFAULT_AUTOMATION_MCP_EXECUTE_TOOLS,
)
from core.types.json import JSONDict, JSONValue

__all__ = (
    "normalize_automation_mcp_config",
    "normalize_automation_mcp_payload_settings",
    "normalize_automation_mcp_settings",
)


def normalize_automation_mcp_settings(
    raw: Mapping[str, JSONValue] | None,
    *,
    disallowed_unqualified_tools: tuple[str, ...],
) -> NormalizedAgentMCPConfig:
    default_execute_tools = filter_disallowed_automation_tool_names(
        DEFAULT_AUTOMATION_MCP_EXECUTE_TOOLS,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    return normalize_agent_mcp_config(
        raw,
        field_prefix="Automation MCP",
        default_tools=(),
        default_plan_tools=(),
        default_execute_tools=tuple(default_execute_tools),
        default_tools_enabled=True,
        default_tool_approval_required=False,
        tool_name_validator=build_automation_tool_name_validator(disallowed_unqualified_tools),
    )


def normalize_automation_mcp_payload_settings(
    raw: Mapping[str, JSONValue] | None,
    *,
    interactive_tool_approval: bool,
    disallowed_unqualified_tools: tuple[str, ...],
) -> NormalizedAgentMCPConfig:
    if raw is not None:
        approval_value = raw.get("tool_approval_required")
        if approval_value is not None and not isinstance(approval_value, bool):
            raise ValidationError("Automation MCP tool_approval_required must be a boolean.")
        if isinstance(approval_value, bool) and approval_value != interactive_tool_approval:
            raise ValidationError(
                "Automation MCP tool_approval_required must match interactive_tool_approval.",
            )
    normalized = normalize_automation_mcp_settings(
        raw,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    return NormalizedAgentMCPConfig(
        default_tools=list(normalized.default_tools),
        plan_tools=list(normalized.plan_tools),
        execute_tools=list(normalized.execute_tools),
        server_configs=dict(normalized.server_configs),
        tools_enabled=normalized.tools_enabled,
        tool_approval_required=interactive_tool_approval,
    )


def normalize_automation_mcp_config(
    raw: Mapping[str, JSONValue] | None,
    *,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict:
    return build_normalized_agent_mcp_config_payload(
        normalize_automation_mcp_settings(
            raw,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        ),
    )
