"""SoAI - Shared MCP tool catalog response shaping [backend/features/api/runtime/mcp_tool_catalog_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_tool_validation import (
    is_disallowed_automation_tool_name,
)
from core.errors.exceptions import StateError
from core.mcp.default_tool_names import (
    DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
    DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
    DEFAULT_CONVERSATION_MCP_TOOLS,
)
from core.mcp.server_config_normalization import require_valid_server_id
from core.rag.knowledge_prompt_contract import resolve_knowledge_tool_role
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig
    from core.types.json import JSONDict

__all__ = (
    "build_automation_mcp_tool_catalog_response",
    "build_conversation_mcp_tool_catalog_response",
    "build_messaging_mcp_tool_catalog_response",
    "build_mcp_tool_catalog_payload",
)


def build_mcp_tool_catalog_payload(
    *,
    tools_by_name: dict[str, JSONDict],
    default_tools: tuple[str, ...],
    plan_tools: tuple[str, ...],
    execute_tools: tuple[str, ...],
    apply_automation_policy: bool = False,
    disallowed_unqualified_tools: tuple[str, ...] = (),
) -> list[JSONDict]:
    default_tool_names = set(default_tools)
    plan_tool_names = set(plan_tools)
    execute_tool_names = set(execute_tools)
    tools: list[JSONDict] = []
    for tool_name in sorted(tools_by_name):
        entry = tools_by_name[tool_name]
        server_id_value = _read_server_id(entry)
        allowed, blocked_reason = _resolve_tool_allowed_state(
            tool_name=tool_name,
            apply_automation_policy=apply_automation_policy,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
        tool_payload: JSONDict = {
            "name": tool_name,
            "definition": _read_tool_definition(entry),
            "source": "builtin" if server_id_value is None else "remote",
            "server_id": server_id_value,
            "server_name": _read_server_name(entry),
            "allowed": allowed,
            "blocked_reason": blocked_reason,
            "enabled_by_default": tool_name in default_tool_names,
            "enabled_by_plan": tool_name in plan_tool_names,
            "enabled_by_execute": tool_name in execute_tool_names,
            "knowledge_role": resolve_knowledge_tool_role(tool_name),
        }
        icons = _read_tool_icons(entry)
        if icons is not None:
            tool_payload["icons"] = icons
        tools.append(tool_payload)
    return tools


def _read_tool_definition(entry: JSONDict) -> JSONDict | None:
    definition = entry.get("definition")
    if definition is None:
        return None
    normalized_definition = coerce_json_dict(definition)
    if normalized_definition is None:
        raise StateError("MCP tool definition payload is invalid.")
    return normalized_definition


def _read_server_id(entry: JSONDict) -> str | None:
    server_id_value = entry.get("server_id")
    if server_id_value is None:
        return None
    if not isinstance(server_id_value, str):
        raise StateError("MCP tool server_id payload is invalid.")
    try:
        return require_valid_server_id(server_id_value)
    except StateError as exception:
        raise StateError("MCP tool server_id payload is invalid.") from exception


def _read_server_name(entry: JSONDict) -> str:
    server_name_value = entry.get("server_name")
    if not isinstance(server_name_value, str):
        raise StateError("MCP tool server_name payload is invalid.")
    normalized_server_name = server_name_value.strip()
    if not normalized_server_name:
        raise StateError("MCP tool server_name payload is invalid.")
    return normalized_server_name


def _read_tool_icons(entry: JSONDict) -> list[JSONDict] | None:
    raw_value = entry.get("raw")
    if not isinstance(raw_value, dict):
        return None
    icons_value = raw_value.get("icons")
    if icons_value is None:
        return None
    if not isinstance(icons_value, list):
        raise StateError("MCP tool icons payload is invalid.")
    icons: list[JSONDict] = []
    for icon_value in icons_value:
        normalized_icon = coerce_json_dict(icon_value)
        if normalized_icon is None:
            raise StateError("MCP tool icons payload is invalid.")
        icons.append(normalized_icon)
    return icons


def _resolve_tool_allowed_state(
    *,
    tool_name: str,
    apply_automation_policy: bool,
    disallowed_unqualified_tools: tuple[str, ...],
) -> tuple[bool, str | None]:
    if apply_automation_policy and is_disallowed_automation_tool_name(
        tool_name,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    ):
        return (False, "Blocked by automation tool policy.")
    return (True, None)


def build_conversation_mcp_tool_catalog_response(
    *,
    conv_id: str,
    tools_by_name: dict[str, JSONDict],
    normalized_mcp: NormalizedAgentMCPConfig,
    is_automation: bool,
    disallowed_unqualified_tools: tuple[str, ...] = (),
) -> JSONDict:
    return {
        "conv_id": conv_id,
        "tools": build_mcp_tool_catalog_payload(
            tools_by_name=tools_by_name,
            default_tools=tuple(normalized_mcp.default_tools),
            plan_tools=tuple(normalized_mcp.plan_tools),
            execute_tools=tuple(normalized_mcp.execute_tools),
            apply_automation_policy=is_automation,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        ),
        "default_tools": list(normalized_mcp.default_tools),
        "plan_tools": list(normalized_mcp.plan_tools),
        "execute_tools": list(normalized_mcp.execute_tools),
        "canonical_default_tools": list(DEFAULT_CONVERSATION_MCP_TOOLS),
        "canonical_plan_tools": list(DEFAULT_CONVERSATION_MCP_PLAN_TOOLS),
        "canonical_execute_tools": list(DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS),
    }


def build_automation_mcp_tool_catalog_response(
    *,
    tools_by_name: dict[str, JSONDict],
    execute_tools: list[str],
    disallowed_unqualified_tools: tuple[str, ...] = (),
) -> JSONDict:
    return {
        "tools": build_mcp_tool_catalog_payload(
            tools_by_name=tools_by_name,
            default_tools=(),
            plan_tools=(),
            execute_tools=tuple(execute_tools),
            apply_automation_policy=True,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        ),
        "execute_tools": list(execute_tools),
    }


def build_messaging_mcp_tool_catalog_response(
    *,
    tools_by_name: dict[str, JSONDict],
) -> JSONDict:
    return {
        "tools": build_mcp_tool_catalog_payload(
            tools_by_name=tools_by_name,
            default_tools=DEFAULT_CONVERSATION_MCP_TOOLS,
            plan_tools=DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
            execute_tools=DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
        ),
        "default_tools": list(DEFAULT_CONVERSATION_MCP_TOOLS),
        "plan_tools": list(DEFAULT_CONVERSATION_MCP_PLAN_TOOLS),
        "execute_tools": list(DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS),
    }
