"""SoAI - Automation payload validation [backend/core/automation/automation_payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.agent_mode import normalize_agent_mode
from core.agent_tool_policy import agent_mode_requires_mcp_tools
from core.automation.automation_constants import (
    AUTOMATION_PAYLOAD_FIELDS,
    AUTOMATION_RECURRENCE_VALUES,
    build_automation_recurrence_error_message,
)
from core.automation.automation_local_time import parse_start_local, require_timezone
from core.automation.automation_mcp_config import (
    normalize_automation_mcp_payload_settings,
)
from core.automation.automation_recurrence import resolve_next_run_at
from core.automation.automation_turn_limits import (
    normalize_automation_max_run_minutes,
    normalize_automation_max_turn_chars,
    normalize_automation_max_turns,
    normalize_automation_turns,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import (
    build_normalized_agent_mcp_config_payload,
)
from core.openai.model_settings_validation import validate_model_settings
from core.prompts.colors import validate_prompt_color
from core.types.json import JSONDict, JSONValue
from core.validation.strings import require_trimmed_json_text

__all__ = ("validate_automation_payload",)

_ALLOWED_AUTOMATION_PAYLOAD_KEYS: tuple[str, ...] = AUTOMATION_PAYLOAD_FIELDS


def validate_automation_payload(
    payload: Mapping[str, JSONValue],
    *,
    now_ms: int,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict:
    if not isinstance(payload, Mapping):
        raise ValidationError("Automation payload must be an object.")
    unexpected_keys: list[str] = []
    for key in payload:
        if not isinstance(key, str):
            raise ValidationError("Automation payload keys must be strings.")
        if key not in _ALLOWED_AUTOMATION_PAYLOAD_KEYS:
            unexpected_keys.append(key)
    if unexpected_keys:
        unexpected_joined = ", ".join(sorted(unexpected_keys))
        allowed_joined = ", ".join(sorted(_ALLOWED_AUTOMATION_PAYLOAD_KEYS))
        raise ValidationError(
            f"Unexpected automation payload fields: {unexpected_joined}. Allowed: {allowed_joined}.",
        )
    title = _require_title(payload.get("title"))
    enabled = _require_bool(payload.get("enabled"), field_name="enabled")
    timezone_value = _require_timezone_name(payload.get("timezone"))
    start_local_value = _require_start_local(payload.get("start_local"))
    recurrence_value = _require_recurrence(payload.get("recurrence"))
    interactive_tool_approval = _require_bool(
        payload.get("interactive_tool_approval"),
        field_name="interactive_tool_approval",
    )
    max_turns = normalize_automation_max_turns(
        payload.get("max_turns"),
        field_label="Automation max_turns",
    )
    max_turn_chars = normalize_automation_max_turn_chars(
        payload.get("max_turn_chars"),
        field_label="Automation max_turn_chars",
    )
    max_run_minutes = normalize_automation_max_run_minutes(
        payload.get("max_run_minutes"),
        field_label="Automation max_run_minutes",
    )
    turns = normalize_automation_turns(
        payload.get("turns"),
        max_turns=max_turns,
        max_turn_chars=max_turn_chars,
        label="Automation turns",
    )
    return {
        "title": title,
        "enabled": enabled,
        "color": _normalize_color(payload.get("color")),
        "timezone": timezone_value,
        "start_local": start_local_value,
        "recurrence": recurrence_value,
        "turns": turns,
        "max_turns": max_turns,
        "max_turn_chars": max_turn_chars,
        "max_run_minutes": max_run_minutes,
        "interactive_tool_approval": interactive_tool_approval,
        "model_settings": _normalize_model_settings(
            payload.get("model_settings"),
            interactive_tool_approval=interactive_tool_approval,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        ),
        "next_run_at_ms": resolve_next_run_at(
            timezone_name=timezone_value,
            start_local=start_local_value,
            recurrence=recurrence_value,
            enabled=enabled,
            now_ms=now_ms,
        ),
    }


def _require_title(value: JSONValue) -> str:
    return require_trimmed_json_text(value, error_message="Automation title is required.")


def _require_bool(value: JSONValue, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"Automation {field_name} must be a boolean.")
    return value


def _normalize_color(value: JSONValue) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Automation color must be a string when provided.")
    stripped = value.strip()
    return validate_prompt_color(stripped or None)


def _require_timezone_name(value: JSONValue) -> str:
    normalized = require_trimmed_json_text(
        value,
        error_message="Automation timezone is required.",
    )
    require_timezone(normalized)
    return normalized


def _require_start_local(value: JSONValue) -> str:
    normalized = require_trimmed_json_text(
        value,
        error_message="Automation start_local is required.",
    )
    parse_start_local(normalized)
    return normalized


def _require_recurrence(value: JSONValue) -> str:
    if not isinstance(value, str):
        raise ValidationError("Automation recurrence is required.")
    normalized = value.strip()
    if normalized not in AUTOMATION_RECURRENCE_VALUES:
        raise ValidationError(build_automation_recurrence_error_message())
    return normalized


def _normalize_model_settings(
    value: JSONValue,
    *,
    interactive_tool_approval: bool,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict:
    validated = validate_model_settings(value)
    if "tools" in validated:
        raise ValidationError(
            "Automation model_settings.tools is not allowed. Configure tools via model_settings.mcp.",
        )
    if "tool_choice" in validated:
        raise ValidationError(
            "Automation model_settings.tool_choice is not allowed. Configure tools via model_settings.mcp.",
        )
    validated["model"] = require_trimmed_json_text(
        validated.get("model"),
        error_message="Automation model_settings.model is required.",
    )
    agent_value = validated.get("agent")
    if isinstance(agent_value, Mapping) and "interactive_tool_approval" in agent_value:
        raise ValidationError(
            "Automation model_settings.agent.interactive_tool_approval is not allowed. Use interactive_tool_approval in the automation payload.",
        )
    validated["agent"] = _normalize_agent_settings(
        validated.get("agent"),
        interactive_tool_approval=interactive_tool_approval,
    )
    agent_record = validated.get("agent")
    if not isinstance(agent_record, dict):
        raise ValidationError("Automation model_settings.agent must be an object.")
    agent_mode = agent_record.get("mode")
    if not isinstance(agent_mode, str):
        raise ValidationError("Automation agent mode must be 'execute'.")
    if agent_mode != "execute":
        raise ValidationError("Automation agent mode must be 'execute'.")
    mcp_value = validated.get("mcp")
    if mcp_value is not None and not isinstance(mcp_value, Mapping):
        raise ValidationError("Automation model_settings.mcp must be an object.")
    normalized_mcp = normalize_automation_mcp_payload_settings(
        mcp_value if isinstance(mcp_value, Mapping) else None,
        interactive_tool_approval=interactive_tool_approval,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    if agent_mode == "execute" and "todo_write" not in normalized_mcp.execute_tools:
        raise ValidationError("Automation execute mode requires the todo_write tool to be enabled.")
    validated["mcp"] = build_normalized_agent_mcp_config_payload(normalized_mcp)
    mcp_record = validated.get("mcp")
    if not isinstance(mcp_record, dict):
        raise ValidationError("Automation model_settings.mcp must be an object.")
    if agent_mode_requires_mcp_tools(agent_mode) and mcp_record.get("tools_enabled") is not True:
        raise ValidationError("Automation agent mode requires MCP tools to be enabled.")
    return validated


def _normalize_agent_settings(value: JSONValue, *, interactive_tool_approval: bool) -> JSONDict:
    if value is None:
        return {"mode": "execute", "interactive_tool_approval": interactive_tool_approval}
    if not isinstance(value, Mapping):
        raise ValidationError("Automation model_settings.agent must be an object.")
    normalized: JSONDict = {}
    for key, entry in value.items():
        if not isinstance(key, str):
            raise ValidationError("Automation model_settings.agent keys must be strings.")
        normalized[key] = entry
    mode_value = normalized.get("mode")
    if mode_value is None:
        normalized["mode"] = "execute"
    else:
        normalized["mode"] = normalize_agent_mode(mode_value, strict=True)
    if normalized.get("mode") != "execute":
        raise ValidationError("Automation model_settings.agent.mode must be 'execute'.")
    normalized["interactive_tool_approval"] = interactive_tool_approval
    return normalized
