"""SoAI - Shared agent MCP normalization primitives [backend/core/mcp/agent_config_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue

__all__ = (
    "AGENT_MCP_TOOL_SELECTION_FIELDS",
    "NormalizedAgentMCPConfig",
    "build_normalized_agent_mcp_config_payload",
    "normalize_agent_mcp_config",
)

AGENT_MCP_TOOL_SELECTION_FIELDS: tuple[str, str, str] = (
    "default_tools",
    "plan_tools",
    "execute_tools",
)


@dataclass(frozen=True, slots=True)
class NormalizedAgentMCPConfig:
    default_tools: list[str]
    plan_tools: list[str]
    execute_tools: list[str]
    server_configs: dict[str, bool]
    tools_enabled: bool
    tool_approval_required: bool


_AGENT_MCP_CONFIG_FIELDS: frozenset[str] = frozenset(
    (
        *AGENT_MCP_TOOL_SELECTION_FIELDS,
        "server_configs",
        "tools_enabled",
        "tool_approval_required",
    ),
)


def normalize_agent_mcp_config(
    raw: Mapping[str, JSONValue] | None,
    *,
    field_prefix: str,
    default_tools: tuple[str, ...],
    default_plan_tools: tuple[str, ...],
    default_execute_tools: tuple[str, ...],
    default_tools_enabled: bool,
    default_tool_approval_required: bool,
    tool_name_validator: Callable[[str], None] | None,
) -> NormalizedAgentMCPConfig:
    config = raw or {}
    if not isinstance(config, Mapping):
        raise ValidationError(f"{field_prefix} config must be an object.")
    for field_name in config:
        if field_name not in _AGENT_MCP_CONFIG_FIELDS:
            raise ValidationError(
                f"{field_prefix} config contains unsupported field '{field_name}'.",
            )
    tools_enabled = _normalize_bool(
        config.get("tools_enabled"),
        field_name=f"{field_prefix} tools_enabled",
        default=default_tools_enabled,
    )
    tool_approval_required = _normalize_bool(
        config.get("tool_approval_required"),
        field_name=f"{field_prefix} tool_approval_required",
        default=default_tool_approval_required,
    )
    return NormalizedAgentMCPConfig(
        default_tools=_normalize_tool_list(
            config.get("default_tools"),
            field_name=f"{field_prefix} default_tools",
            default=default_tools,
            tool_name_validator=tool_name_validator,
        ),
        plan_tools=_normalize_tool_list(
            config.get("plan_tools"),
            field_name=f"{field_prefix} plan_tools",
            default=default_plan_tools,
            tool_name_validator=tool_name_validator,
        ),
        execute_tools=_normalize_tool_list(
            config.get("execute_tools"),
            field_name=f"{field_prefix} execute_tools",
            default=default_execute_tools,
            tool_name_validator=tool_name_validator,
        ),
        server_configs=_normalize_server_configs(
            config.get("server_configs"),
            field_name=f"{field_prefix} server_configs",
        ),
        tools_enabled=tools_enabled,
        tool_approval_required=tool_approval_required,
    )


def _normalize_bool(value: JSONValue, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValidationError(f"{field_name} must be a boolean.")


def _normalize_server_configs(value: JSONValue, *, field_name: str) -> dict[str, bool]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field_name} must be an object.")
    normalized: dict[str, bool] = {}
    for server_id, enabled in value.items():
        if not isinstance(server_id, str):
            raise ValidationError(f"{field_name} keys must be strings.")
        normalized_server_id = server_id.strip()
        if not normalized_server_id:
            raise ValidationError(f"{field_name} keys cannot be empty.")
        if not isinstance(enabled, bool):
            raise ValidationError(f"{field_name} values must be booleans.")
        normalized[normalized_server_id] = enabled
    return normalized


def _normalize_tool_list(
    value: JSONValue,
    *,
    field_name: str,
    default: tuple[str, ...],
    tool_name_validator: Callable[[str], None] | None,
) -> list[str]:
    if value is None:
        return _normalize_default_tool_list(
            default,
            tool_name_validator=tool_name_validator,
        )
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be an array.")
    normalized: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ValidationError(f"{field_name} entries must be strings.")
        candidate = entry.strip()
        if not candidate:
            raise ValidationError(f"{field_name} entries cannot be empty.")
        if tool_name_validator is not None:
            tool_name_validator(candidate)
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _normalize_default_tool_list(
    default: tuple[str, ...],
    *,
    tool_name_validator: Callable[[str], None] | None,
) -> list[str]:
    normalized: list[str] = []
    for candidate in default:
        if tool_name_validator is not None:
            tool_name_validator(candidate)
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def build_normalized_agent_mcp_config_payload(
    normalized: NormalizedAgentMCPConfig,
) -> JSONDict:
    return {
        "default_tools": list(normalized.default_tools),
        "plan_tools": list(normalized.plan_tools),
        "execute_tools": list(normalized.execute_tools),
        "server_configs": dict(normalized.server_configs),
        "tools_enabled": normalized.tools_enabled,
        "tool_approval_required": normalized.tool_approval_required,
    }
