"""SoAI - MCP tool context builder [backend/core/mcp/tool_context_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import NoReturn

from core.agent_tool_policy import (
    agent_mode_requires_mcp_tools,
    collect_plan_mode_block_reasons,
    resolve_mode_default_tools,
)
from core.config.user_interaction_timeout import DEFAULT_USER_INTERACTION_TIMEOUT_MS
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig
from core.mcp.protocols import MCPToolCatalogSourcesProtocol
from core.mcp.tool_catalog import collect_mcp_tool_catalog
from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from core.mcp.tool_choice import extract_tool_names, normalize_tool_choice
from core.mcp.tool_name_suggestions import (
    append_tool_suggestions_to_message,
    build_tool_name_candidates_from_entry_map,
    build_tool_name_candidates_from_names,
    suggest_tool_names,
)
from core.orchestrator.types import MCPToolContext
from core.types.json import JSONDict, JSONValue
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "MCPToolCatalogSourcesProtocol",
    "build_mcp_tool_context",
)


def _raise_invalid_tools(message: str) -> NoReturn:
    raise ValidationError(message)


def _normalize_selected_tool_names_from_request(request_json: JSONDict) -> list[str]:
    tools_value = request_json.get("tools")
    return extract_tool_names(tools_value, on_error=_raise_invalid_tools)


def _resolve_enabled_default_tools(
    normalized_mcp: NormalizedAgentMCPConfig,
    *,
    agent_mode: str,
) -> list[str]:
    return resolve_mode_default_tools(
        agent_mode=agent_mode,
        default_tools=tuple(normalized_mcp.default_tools),
        plan_tools=tuple(normalized_mcp.plan_tools),
        execute_tools=tuple(normalized_mcp.execute_tools),
    )


def _normalize_forced_tool_names(forced_tool_names: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(name.strip() for name in forced_tool_names if name.strip()))


def _build_unknown_selected_tool_message(
    tool_name: str,
    selected_names: list[str],
) -> str:
    suggestions = suggest_tool_names(
        tool_name,
        build_tool_name_candidates_from_names(selected_names),
    )
    return append_tool_suggestions_to_message(f"Unknown MCP tool: {tool_name}", suggestions)


def _build_unavailable_tools_message(
    missing_tools: list[str],
    allowed_tool_map: dict[str, dict[str, JSONValue]],
) -> str:
    if len(missing_tools) != 1:
        return f"MCP tools unavailable: {', '.join(missing_tools)}"
    missing_tool_name = missing_tools[0]
    suggestions = suggest_tool_names(
        missing_tool_name,
        build_tool_name_candidates_from_entry_map(allowed_tool_map),
    )
    return append_tool_suggestions_to_message(
        f"MCP tools unavailable: {missing_tool_name}",
        suggestions,
    )


async def build_mcp_tool_context(
    *,
    request_json: JSONDict,
    agent_mode: str,
    normalized_mcp: NormalizedAgentMCPConfig,
    conv_id: str,
    user_id: int,
    message_index: int,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    model_id: str,
    tool_name_validator: Callable[[str], None] | None,
    force_tool_approval_required: bool | None,
    supports_tool_calling: Callable[[str], Awaitable[bool]],
    sources: MCPToolCatalogSourcesProtocol,
    local_tool_catalog_scope: MCPToolCatalogScope,
    forced_tool_names: tuple[str, ...] = (),
    force_tool_choice_auto: bool = False,
    user_interaction_timeout_ms: int = DEFAULT_USER_INTERACTION_TIMEOUT_MS,
) -> MCPToolContext:
    choice_mode_raw, choice_name_raw = normalize_tool_choice(request_json.get("tool_choice"))
    choice_mode = (choice_mode_raw or "auto").strip()
    choice_name = choice_name_raw if choice_mode == "function" else None
    tools_provided = "tools" in request_json
    normalized_forced_tool_names = _normalize_forced_tool_names(forced_tool_names)

    tools_enabled = bool(normalized_mcp.tools_enabled)
    tool_approval_required = (
        bool(force_tool_approval_required)
        if force_tool_approval_required is not None
        else bool(normalized_mcp.tool_approval_required)
    )

    if not tools_enabled:
        if agent_mode_requires_mcp_tools(agent_mode):
            raise ValidationError(
                (
                    "Plan mode requires tools to be enabled."
                    if agent_mode == "plan"
                    else "Execute mode requires tools to be enabled."
                ),
            )
        if choice_mode in {"function", "required"}:
            raise ValidationError("tool_choice requires MCP tools but tools are disabled.")
        request_json.pop("tools", None)
        request_json["tool_choice"] = "none"
        return MCPToolContext(
            conv_id=conv_id,
            message_index=message_index,
            user_id=user_id,
            tool_map={},
            visible_tool_names=(),
            tool_approval_required=tool_approval_required,
            assistant_at_ms=int(assistant_at_ms),
            assistant_turn_at_ms=int(assistant_turn_at_ms),
            model_variant_index=int(model_variant_index),
            user_interaction_timeout_ms=int(user_interaction_timeout_ms),
        )

    if choice_mode == "none" and not (normalized_forced_tool_names and force_tool_choice_auto):
        if agent_mode_requires_mcp_tools(agent_mode):
            raise ValidationError(
                "Plan/execute mode requires tools and cannot use tool_choice='none'.",
            )
        request_json.pop("tools", None)
        request_json["tool_choice"] = "none"
        return MCPToolContext(
            conv_id=conv_id,
            message_index=message_index,
            user_id=user_id,
            tool_map={},
            visible_tool_names=(),
            tool_approval_required=tool_approval_required,
            assistant_at_ms=int(assistant_at_ms),
            assistant_turn_at_ms=int(assistant_turn_at_ms),
            model_variant_index=int(model_variant_index),
            user_interaction_timeout_ms=int(user_interaction_timeout_ms),
        )

    if choice_mode == "none":
        choice_mode = "auto"
    selected_names = (
        _normalize_selected_tool_names_from_request(request_json)
        if tools_provided
        else _resolve_enabled_default_tools(normalized_mcp, agent_mode=agent_mode)
    )
    selected_names.extend(normalized_forced_tool_names)
    selected_names = list(
        dict.fromkeys([name for name in selected_names if isinstance(name, str) and name]),
    )

    if not selected_names:
        if choice_mode in {"function", "required"}:
            raise ValidationError("tool_choice requires at least one selected tool.")
        if agent_mode_requires_mcp_tools(agent_mode):
            raise ValidationError("Plan/execute mode requires at least one tool to be enabled.")
        raise ValidationError(
            "Tools are enabled but no tools are selected for chat mode. Select at least one default tool or disable tools.",
        )

    if tool_name_validator is not None:
        for tool_name in selected_names:
            tool_name_validator(tool_name)

    if choice_mode == "function":
        if not isinstance(choice_name, str) or not choice_name:
            raise ValidationError("tool_choice function requires a non-empty name.")
        if choice_name not in selected_names:
            raise ValidationError(_build_unknown_selected_tool_message(choice_name, selected_names))

    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        raise ValidationError("MCP tools require a resolved model.")

    if not await supports_tool_calling(normalized_model_id):
        raise ValidationError("The selected model does not support tool calling.")

    tool_entries, allowed_tool_map = await collect_mcp_tool_catalog(
        sources.mcp_server,
        sources.mcp_remote,
        sources.mcp_tool_catalog_cache,
        normalized_mcp.server_configs,
        local_tool_catalog_scope,
    )
    if not tool_entries or not allowed_tool_map:
        raise ValidationError("MCP tools are not available.")

    missing = [name for name in selected_names if name not in allowed_tool_map]
    if missing:
        raise ValidationError(_build_unavailable_tools_message(missing, allowed_tool_map))

    blocked = collect_plan_mode_block_reasons(
        agent_mode=agent_mode,
        tool_names=selected_names,
        tool_map=allowed_tool_map,
    )
    if blocked:
        reasons = "; ".join(blocked[name] for name in sorted(blocked))
        raise ValidationError(
            f"Plan mode blocked some tools: {reasons}",
            details={"blocked_tools": blocked},
        )

    selected_tool_map: dict[str, dict[str, JSONValue]] = {}
    normalized_definitions: list[JSONDict] = []
    visible_tool_names: list[str] = []
    for tool_name in selected_names:
        tool_entry = allowed_tool_map[tool_name]
        selected_tool_map[tool_name] = tool_entry
        definition = tool_entry.get("definition")
        if not isinstance(definition, dict):
            raise ValidationError(f"MCP tool '{tool_name}' definition is invalid.")
        normalized_definitions.append(dict(definition))
        visible_tool_names.append(tool_name)
    request_json["tools"] = normalized_definitions

    if choice_mode == "required":
        request_json["tool_choice"] = "required"
    elif choice_mode == "function":
        request_json["tool_choice"] = {"type": "function", "function": {"name": choice_name}}
    else:
        request_json["tool_choice"] = "auto"

    return MCPToolContext(
        conv_id=conv_id,
        message_index=message_index,
        user_id=user_id,
        tool_map=selected_tool_map,
        visible_tool_names=tuple(visible_tool_names),
        tool_approval_required=tool_approval_required,
        assistant_at_ms=int(assistant_at_ms),
        assistant_turn_at_ms=int(assistant_turn_at_ms),
        model_variant_index=int(model_variant_index),
        user_interaction_timeout_ms=int(user_interaction_timeout_ms),
    )
