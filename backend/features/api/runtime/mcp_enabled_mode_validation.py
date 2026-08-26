"""SoAI - MCP enabled-mode selection validation [backend/features/api/runtime/mcp_enabled_mode_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent_tool_policy import (
    agent_mode_requires_mcp_tools,
    resolve_mode_default_tools,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import AGENT_MCP_TOOL_SELECTION_FIELDS
from core.model_settings.normalization import extract_agent_mode
from core.runtime.protocols import RequestProtocol
from core.types.json import JSONDict, JSONValue
from features.api.runtime.errors import raise_invalid_request

__all__ = ("validate_enabled_tools_for_agent_mode",)


def _require_tool_name_list(
    request: RequestProtocol,
    value: JSONValue,
    *,
    field_name: str,
) -> list[str]:
    if not isinstance(value, list):
        raise_invalid_request(request, f"{field_name} must be a list.")
    normalized: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise_invalid_request(request, f"{field_name} entries must be strings.")
        candidate = entry.strip()
        if not candidate:
            raise_invalid_request(request, f"{field_name} entries cannot be empty.")
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def validate_enabled_tools_for_agent_mode(
    *,
    request: RequestProtocol,
    settings: JSONDict,
    merged_config: JSONDict,
) -> None:
    try:
        agent_mode = extract_agent_mode(settings, strict=True)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    if merged_config.get("tools_enabled") is not True:
        if agent_mode == "plan":
            raise_invalid_request(request, "Plan mode requires MCP tools to be enabled.")
        if agent_mode == "execute":
            raise_invalid_request(request, "Execute mode requires MCP tools to be enabled.")
        return
    tool_selections = {
        field_name: _require_tool_name_list(
            request,
            merged_config.get(field_name),
            field_name=field_name,
        )
        for field_name in AGENT_MCP_TOOL_SELECTION_FIELDS
    }
    if not agent_mode_requires_mcp_tools(agent_mode):
        return
    selected = resolve_mode_default_tools(
        agent_mode=agent_mode,
        default_tools=tuple(tool_selections["default_tools"]),
        plan_tools=tuple(tool_selections["plan_tools"]),
        execute_tools=tuple(tool_selections["execute_tools"]),
    )
    if selected:
        return
    field_name = "default_tools"
    if agent_mode == "plan":
        field_name = "plan_tools"
    if agent_mode == "execute":
        field_name = "execute_tools"
    raise_invalid_request(
        request,
        f"Cannot enable tools in {agent_mode} mode: mcp.{field_name} must contain at least one tool.",
    )
