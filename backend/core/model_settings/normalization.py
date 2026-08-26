"""SoAI - Canonical model_settings normalization helpers [backend/core/model_settings/normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.iteration_limits import require_agent_max_iterations
from core.agent_mode import normalize_agent_mode
from core.errors.exceptions import StateError, ValidationError
from core.model_settings.request_projection import read_execution_context_window_override
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "extract_agent_mode",
    "merge_model_settings",
    "normalize_agent_settings",
    "normalize_chat_execution_settings",
    "normalize_comparison_models",
    "normalize_identity_settings",
    "normalize_model_selection_settings",
    "normalize_optional_bool_setting",
    "normalize_prompt_settings",
    "read_optional_agent_settings",
    "resolve_execution_model_sequence",
)


def normalize_identity_settings(value: JSONValue) -> JSONDict:
    raw = coerce_json_dict(value) or {}
    return {
        "user_display_name": coerce_optional_trimmed_str(raw.get("user_display_name")),
        "assistant_display_name": coerce_optional_trimmed_str(raw.get("assistant_display_name")),
    }


def normalize_optional_bool_setting(value: JSONValue, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return value == 1
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on", "enabled"):
            return True
        if lowered in ("false", "0", "no", "off", "disabled"):
            return False
    return default


def normalize_prompt_settings(value: JSONValue) -> JSONDict:
    raw = coerce_json_dict(value) or {}
    user_system_prompt_value = raw.get("user_system_prompt")
    user_system_prompt = (
        user_system_prompt_value if isinstance(user_system_prompt_value, str) else None
    )
    user_system_prompt = (
        user_system_prompt if user_system_prompt and user_system_prompt.strip() else None
    )
    return {
        "user_system_prompt": user_system_prompt,
        "soai_system_prompt_enabled": normalize_optional_bool_setting(
            raw.get("soai_system_prompt_enabled"),
            default=True,
        ),
    }


def normalize_agent_settings(value: JSONValue) -> JSONDict:
    raw = coerce_json_dict(value) or {}
    normalized: JSONDict = dict(raw)
    if "mode" in normalized:
        normalized["mode"] = normalize_agent_mode(normalized.get("mode"), strict=True)
    if "max_iterations" in normalized:
        normalized["max_iterations"] = require_agent_max_iterations(
            normalized["max_iterations"],
        )
    return normalized


def normalize_chat_execution_settings(model_settings: JSONDict) -> JSONDict:
    normalized = normalize_model_selection_settings(dict(model_settings))
    normalized["agent"] = normalize_agent_settings(normalized.get("agent"))
    normalized["identity"] = normalize_identity_settings(normalized.get("identity"))
    normalized["prompts"] = normalize_prompt_settings(normalized.get("prompts"))
    read_execution_context_window_override(normalized)
    return normalized


def normalize_comparison_models(
    *,
    primary_model: str | None,
    raw_value: JSONValue,
) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValidationError("model_settings.comparison_models must be an array.")
    normalized_primary = coerce_optional_trimmed_str(primary_model)
    if normalized_primary is None:
        raise ValidationError("model_settings.model is required when comparison_models is set.")
    normalized_models: list[str] = []
    for entry in raw_value:
        if not isinstance(entry, str):
            raise ValidationError("model_settings.comparison_models entries must be strings.")
        normalized_entry = coerce_optional_trimmed_str(entry)
        if normalized_entry is None:
            raise ValidationError(
                "model_settings.comparison_models entries must be non-empty strings.",
            )
        normalized_models.append(normalized_entry)
        if len(normalized_models) > 4:
            raise ValidationError("model_settings.comparison_models supports at most 4 entries.")
    return normalized_models


def normalize_model_selection_settings(model_settings: JSONDict) -> JSONDict:
    normalized_model_settings: JSONDict = dict(model_settings)
    normalized_model = coerce_optional_trimmed_str(normalized_model_settings.get("model"))
    if normalized_model is not None:
        normalized_model_settings["model"] = normalized_model
    elif "model" in normalized_model_settings:
        normalized_model_settings["model"] = None
    comparison_models = normalize_comparison_models(
        primary_model=normalized_model,
        raw_value=normalized_model_settings.get("comparison_models"),
    )
    if comparison_models:
        normalized_model_settings["comparison_models"] = comparison_models
    else:
        normalized_model_settings.pop("comparison_models", None)
    return normalized_model_settings


def resolve_execution_model_sequence(model_settings: JSONDict) -> tuple[str, ...]:
    primary_model = coerce_optional_trimmed_str(model_settings.get("model"))
    if primary_model is None:
        raise ValidationError("model_settings.model is required for execution.")
    comparison_models = normalize_comparison_models(
        primary_model=primary_model,
        raw_value=model_settings.get("comparison_models"),
    )
    return (primary_model, *comparison_models)


def read_optional_agent_settings(
    model_settings: JSONDict,
    *,
    error_message: str = "model_settings.agent payload is invalid.",
    exception_type: type[StateError | ValidationError] = ValidationError,
) -> JSONDict:
    agent_value = model_settings.get("agent")
    if agent_value is None:
        return {}
    agent_settings = coerce_json_dict(agent_value)
    if agent_settings is None:
        raise exception_type(error_message)
    return agent_settings


def extract_agent_mode(model_settings: JSONDict, *, strict: bool) -> str:
    agent_settings = read_optional_agent_settings(model_settings)
    return normalize_agent_mode(agent_settings.get("mode"), strict=strict)


def merge_model_settings(existing: JSONDict, patch: JSONDict) -> JSONDict:
    merged: JSONDict = dict(existing)
    for key, value in patch.items():
        if key == "context_window_tokens" and value is None:
            merged.pop(key, None)
            continue
        existing_value = merged.get(key)
        existing_nested = coerce_json_dict(existing_value)
        patch_nested = coerce_json_dict(value)
        if key == "parameters" and patch_nested is not None:
            merged[key] = (
                merge_model_settings(existing_nested, patch_nested)
                if existing_nested is not None
                else value
            )
            for parameter_name in patch_nested:
                merged.pop(parameter_name, None)
            continue
        if existing_nested is not None and patch_nested is not None:
            merged[key] = merge_model_settings(existing_nested, patch_nested)
            continue
        merged[key] = value
    return merged
