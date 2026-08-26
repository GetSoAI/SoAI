"""SoAI - Strict chat preset V1 canonicalization [backend/core/chat_presets/canonicalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.chat_presets.constants import (
    CHAT_PRESET_MAX_AGENT_ITERATIONS,
    CHAT_PRESET_MAX_SECTIONS_JSON_BYTES,
    CHAT_PRESET_MAX_STOP_ENTRIES,
    CHAT_PRESET_MOBILE_AUXILIARY_ACTIONS,
    CHAT_PRESET_REASONING_EFFORTS,
    CHAT_PRESET_SECTION_IDS,
    CHAT_PRESET_SERVICE_TIERS,
    CHAT_PRESET_TOOL_MODES,
    chat_preset_section_fields,
)
from core.chat_presets.text_canonicalization import (
    canonicalize_trimmed_text,
    require_unicode_scalar_text,
)
from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.rag.parameter_validation import validate_chunking_window
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue, is_json_value
from core.validation.integers import is_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from core.workspaces.user_workspace_path import normalize_workspace_path_update

if TYPE_CHECKING:
    from core.chat_presets.contracts import ChatPresetSections

__all__ = (
    "canonicalize_chat_preset_field",
    "canonicalize_chat_preset_sections",
    "serialize_chat_preset_sections",
)


def _bounded_nullable_identity(value: JSONValue, *, field: str) -> str | None:
    normalized = canonicalize_trimmed_text(value, field=field, nullable=True)
    if normalized is not None and len(normalized) > 50:
        raise ValidationError(f"{field} must contain at most 50 Unicode code points.")
    return normalized


def _strict_bool(value: JSONValue, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be a boolean.")
    return value


def _strict_int(
    value: JSONValue,
    *,
    field: str,
    minimum: int,
    maximum: int,
    nullable: bool = False,
) -> int | None:
    if value is None and nullable:
        return None
    if not is_strict_int(value):
        expected = "an integer or null" if nullable else "an integer"
        raise ValidationError(f"{field} must be {expected}.")
    if value < minimum or value > maximum:
        raise ValidationError(f"{field} must be between {minimum} and {maximum}.")
    return value


def _finite_number(value: JSONValue, *, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{field} must be a finite number.")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < minimum or normalized > maximum:
        raise ValidationError(f"{field} must be between {minimum} and {maximum}.")
    return 0.0 if normalized == 0.0 else normalized


def _enum_or_null(
    value: JSONValue,
    *,
    field: str,
    allowed: frozenset[str],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise ValidationError(f"{field} has an invalid value.")
    require_unicode_scalar_text(value, field=field)
    return value


def _strict_stop(value: JSONValue, *, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) > CHAT_PRESET_MAX_STOP_ENTRIES:
        raise ValidationError(f"{field} must be an array of at most 50 strings.")
    normalized: list[str] = []
    for entry in value:
        item = canonicalize_trimmed_text(entry, field=field, nullable=False)
        if item is None:
            raise ValidationError(f"{field} must contain non-empty strings.")
        normalized.append(item)
    return normalized


def _boolean_map(value: JSONValue, *, field: str) -> dict[str, bool]:
    if not isinstance(value, Mapping) or not value:
        raise ValidationError(f"{field} must be a non-empty object.")
    normalized: dict[str, bool] = {}
    raw_by_key: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = canonicalize_trimmed_text(raw_key, field=f"{field} key", nullable=False)
        if key is None:
            raise ValidationError(f"{field} contains an invalid key.")
        prior_raw = raw_by_key.get(key)
        if prior_raw is not None and prior_raw != raw_key:
            raise ValidationError(f"{field} contains keys that collide after trimming.")
        raw_by_key[key] = raw_key
        normalized[key] = _strict_bool(raw_value, field=f"{field}.{key}")
    return normalized


def _tool_modes(value: JSONValue, *, field: str) -> dict[str, dict[str, bool]]:
    if not isinstance(value, Mapping) or not value:
        raise ValidationError(f"{field} must be a non-empty object.")
    if any(key not in CHAT_PRESET_TOOL_MODES for key in value):
        raise ValidationError(f"{field} contains an unsupported mode.")
    return {
        mode: _boolean_map(tool_map, field=f"{field}.{mode}") for mode, tool_map in value.items()
    }


def _completion_field(field: str, value: JSONValue) -> JSONValue:
    path = f"completion.{field}"
    if field == "user_system_prompt":
        return canonicalize_trimmed_text(value, field=path, nullable=True)
    if field in {"user_system_prompt_lock_enabled", "soai_system_prompt_enabled"} or field.endswith(
        "_send_enabled"
    ):
        return _strict_bool(value, field=path)
    if field == "context_window_tokens":
        return _strict_int(
            value, field=path, minimum=1, maximum=JAVASCRIPT_SAFE_INTEGER_MAX, nullable=True
        )
    if field == "max_completion_tokens":
        return _strict_int(value, field=path, minimum=0, maximum=4_194_304, nullable=True)
    if field == "agent_max_iterations":
        return _strict_int(value, field=path, minimum=1, maximum=CHAT_PRESET_MAX_AGENT_ITERATIONS)
    if field == "top_logprobs":
        return _strict_int(value, field=path, minimum=0, maximum=5, nullable=True)
    if field == "reasoning_effort":
        return _enum_or_null(value, field=path, allowed=CHAT_PRESET_REASONING_EFFORTS)
    if field == "service_tier":
        return _enum_or_null(value, field=path, allowed=CHAT_PRESET_SERVICE_TIERS)
    if field == "stop":
        return _strict_stop(value, field=path)
    ranges = {
        "temperature": (0.0, 2.0),
        "top_p": (0.0, 1.0),
        "frequency_penalty": (-2.0, 2.0),
        "presence_penalty": (-2.0, 2.0),
    }
    minimum, maximum = ranges[field]
    return _finite_number(value, field=path, minimum=minimum, maximum=maximum)


def _knowledge_field(field: str, value: JSONValue) -> JSONValue:
    path = f"knowledge.{field}"
    if field == "enabled":
        return _strict_bool(value, field=path)
    if field == "retrieval_strategy":
        result = _enum_or_null(
            value, field=path, allowed=frozenset({"similarity", "mmr", "hybrid"})
        )
        if result is None:
            raise ValidationError(f"{path} must not be null.")
        return result
    if field == "chunking_strategy":
        result = _enum_or_null(
            value,
            field=path,
            allowed=frozenset({"token_based", "fixed_size", "paragraph", "semantic"}),
        )
        if result is None:
            raise ValidationError(f"{path} must not be null.")
        return result
    if field == "top_k":
        return _strict_int(value, field=path, minimum=1, maximum=50)
    if field == "chunk_size":
        return _strict_int(value, field=path, minimum=100, maximum=4_000)
    if field == "chunk_overlap":
        return _strict_int(value, field=path, minimum=0, maximum=500)
    if field == "similarity_threshold":
        return _finite_number(value, field=path, minimum=0.0, maximum=1.0)
    return canonicalize_trimmed_text(value, field=path, nullable=True)


def canonicalize_chat_preset_field(section: str, field: str, value: JSONValue) -> JSONValue:
    fields = chat_preset_section_fields(section)
    if fields is None or field not in fields:
        raise ValidationError(f"Unsupported chat preset field: {section}.{field}.")
    path = f"{section}.{field}"
    if section == "completion":
        return _completion_field(field, value)
    if section == "knowledge":
        return _knowledge_field(field, value)
    if section == "general":
        if field == "model":
            return canonicalize_trimmed_text(value, field=path, nullable=False)
        if field in {"user_display_name", "assistant_display_name"}:
            return _bounded_nullable_identity(value, field=path)
        return _strict_bool(value, field=path)
    if section == "appearance":
        if field == "text_zoom":
            return _finite_number(value, field=path, minimum=0.5, maximum=1.5)
        if field == "input_action_mobile_auxiliary_action":
            result = _enum_or_null(value, field=path, allowed=CHAT_PRESET_MOBILE_AUXILIARY_ACTIONS)
            if result is None:
                raise ValidationError(f"{path} must not be null.")
            return result
        return _strict_bool(value, field=path)
    if section == "voice":
        return canonicalize_trimmed_text(value, field=path, nullable=False)
    if section == "files":
        if value is not None and not isinstance(value, str):
            raise ValidationError(f"{path} must be a string or null.")
        normalized = normalize_workspace_path_update(value)
        if normalized is not None:
            require_unicode_scalar_text(normalized, field=path)
        return normalized
    if field in {"tools_enabled", "tool_approval_required"}:
        return _strict_bool(value, field=path)
    if field == "servers":
        return _boolean_map(value, field=path)
    return _tool_modes(value, field=path)


def _canonical_section(section: str, value: JSONValue) -> JSONDict:
    if not isinstance(value, Mapping) or not value:
        raise ValidationError(f"Chat preset section {section} must be a non-empty object.")
    fields = chat_preset_section_fields(section)
    if fields is None:
        raise ValidationError(f"Unsupported chat preset section: {section}.")
    unknown = set(value).difference(fields)
    if unknown:
        raise ValidationError(f"Chat preset section {section} contains unsupported fields.")
    canonical = {
        field: canonicalize_chat_preset_field(section, field, field_value)
        for field, field_value in value.items()
    }
    if section == "knowledge" and {"chunking_strategy", "chunk_size", "chunk_overlap"}.issubset(
        canonical
    ):
        strategy = canonical["chunking_strategy"]
        chunk_size = canonical["chunk_size"]
        chunk_overlap = canonical["chunk_overlap"]
        if isinstance(strategy, str) and is_strict_int(chunk_size) and is_strict_int(chunk_overlap):
            validate_chunking_window(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, chunking_strategy=strategy
            )
    return canonical


def canonicalize_chat_preset_sections(value: JSONValue) -> ChatPresetSections:
    if not isinstance(value, Mapping) or not value:
        raise ValidationError("Chat preset sections must be a non-empty object.")
    unknown = set(value).difference(CHAT_PRESET_SECTION_IDS)
    if unknown:
        raise ValidationError("Chat preset sections contain unsupported sections.")
    canonical: ChatPresetSections = {}
    for section, section_value in value.items():
        projected = _canonical_section(section, section_value)
        if not is_json_value(projected):
            raise ValidationError("Chat preset sections must be JSON-compatible.")
        canonical[section] = projected
    serialize_chat_preset_sections(canonical)
    return canonical


def serialize_chat_preset_sections(sections: ChatPresetSections) -> str:
    serialized = serialize_json_compact_stable_strict(sections)
    if len(serialized.encode("utf-8")) > CHAT_PRESET_MAX_SECTIONS_JSON_BYTES:
        raise PayloadTooLargeError("Chat preset sections exceed the 64 KiB limit.")
    return serialized
