"""SoAI - Tool-call arguments compaction [backend/features/agent/runtime/tool_call_arguments_compaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue
from features.agent.runtime.tool_argument_field_policy import (
    CONTENT_ARGUMENT_FIELD_KEYS,
    IDENTITY_ARGUMENT_FIELD_KEYS,
    string_contains_internal_truncation_marker,
)

__all__ = ("compact_tool_call_arguments",)

_MAX_TOOL_CALL_ARGUMENTS_CHARS: int = 2000
_OMIT_STRING_ABOVE_CHARS: int = 700
_PREVIEW_STRING_CHARS: int = 256
_OMITTED_SUFFIX: str = "_omitted_for_context"
_ORIGINAL_CHARS_SUFFIX: str = "_original_chars"


def _json_dumps_compact(value: JSONValue) -> str | None:
    try:
        return serialize_json_compact_stable(value, ensure_ascii=False)
    except (TypeError, ValueError, ValidationError):
        return None


def compact_tool_call_arguments(arguments_text: str) -> str:
    normalized = str(arguments_text or "")
    if not normalized.strip():
        return "{}"

    try:
        parsed = parse_json_value(normalized)
    except ValidationError:
        return "{}"

    if not isinstance(parsed, dict):
        return "{}"

    candidate = _compact_json_strings_for_prompt(parsed)
    if len(normalized) <= _MAX_TOOL_CALL_ARGUMENTS_CHARS:
        safe_text = _ensure_json_value_fits_budget(candidate)
        return safe_text if safe_text is not None else "{}"

    candidate_text = _ensure_json_value_fits_budget(candidate)
    if candidate_text is not None:
        return candidate_text

    global_candidate = _clamp_json_strings_global(candidate, max_string_chars=128)
    global_text = _ensure_json_value_fits_budget(global_candidate)
    if global_text is not None:
        return global_text

    minimal = _compact_tool_call_arguments_minimal(parsed)
    minimal_text = _ensure_json_value_fits_budget(minimal)
    return minimal_text if minimal_text is not None else "{}"


def _ensure_json_value_fits_budget(value: JSONValue) -> str | None:
    text = _json_dumps_compact(value)
    if not isinstance(text, str):
        return None
    if len(text) <= _MAX_TOOL_CALL_ARGUMENTS_CHARS:
        return text

    if not isinstance(value, dict | list | str):
        return None

    if isinstance(value, str):
        clamped_text = _json_dumps_compact(_clamp_string(value, max_chars=128))
        if isinstance(clamped_text, str) and len(clamped_text) <= _MAX_TOOL_CALL_ARGUMENTS_CHARS:
            return clamped_text
        return None

    low, high = 8, 256
    best: str | None = None
    while low <= high:
        mid = (low + high) // 2
        candidate = _clamp_json_strings_global(value, max_string_chars=mid)
        candidate_text = _json_dumps_compact(candidate)
        if (
            isinstance(candidate_text, str)
            and len(candidate_text) <= _MAX_TOOL_CALL_ARGUMENTS_CHARS
        ):
            best = candidate_text
            low = mid + 1
            continue
        high = mid - 1
    if best is not None:
        return best

    empty_json: JSONValue
    if isinstance(value, dict):
        empty_json = {}
    else:
        empty_json = []
    empty_text = _json_dumps_compact(empty_json)
    if isinstance(empty_text, str) and len(empty_text) <= _MAX_TOOL_CALL_ARGUMENTS_CHARS:
        return empty_text
    return None


def _compact_json_strings_for_prompt(value: JSONValue, *, key_name: str | None = None) -> JSONValue:
    if isinstance(value, str):
        if string_contains_internal_truncation_marker(value) or (
            key_name in CONTENT_ARGUMENT_FIELD_KEYS and len(value) > _OMIT_STRING_ABOVE_CHARS
        ):
            return {
                f"{key_name}{_OMITTED_SUFFIX}": True,
                f"{key_name}{_ORIGINAL_CHARS_SUFFIX}": len(value),
            }
        if len(value) > _PREVIEW_STRING_CHARS and key_name not in IDENTITY_ARGUMENT_FIELD_KEYS:
            return _clamp_string(value, max_chars=_PREVIEW_STRING_CHARS)
        return value
    if isinstance(value, dict):
        updated: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            compacted_item = _compact_json_strings_for_prompt(item, key_name=key)
            if (
                isinstance(compacted_item, dict)
                and len(compacted_item) == 2
                and f"{key}{_OMITTED_SUFFIX}" in compacted_item
                and f"{key}{_ORIGINAL_CHARS_SUFFIX}" in compacted_item
            ):
                for metadata_key, metadata_value in compacted_item.items():
                    updated[metadata_key] = metadata_value
                continue
            updated[key] = compacted_item
        return updated
    if isinstance(value, list):
        return [_compact_json_strings_for_prompt(item, key_name=key_name) for item in value]
    return value


def _clamp_json_strings_global(value: JSONValue, *, max_string_chars: int) -> JSONValue:
    if isinstance(value, str):
        if string_contains_internal_truncation_marker(value):
            return ""
        if len(value) <= max_string_chars:
            return value
        return _clamp_string(value, max_chars=max_string_chars)
    if isinstance(value, dict):
        updated: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            updated[key] = _clamp_json_strings_global(item, max_string_chars=max_string_chars)
        return updated
    if isinstance(value, list):
        return [
            _clamp_json_strings_global(item, max_string_chars=max_string_chars) for item in value
        ]
    return value


def _clamp_string(value: str, *, max_chars: int) -> str:
    if string_contains_internal_truncation_marker(value):
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."


def _compact_tool_call_arguments_minimal(value: JSONDict) -> JSONValue:
    keep_keys = [
        "file_path",
        "path",
        "tool",
        "name",
        "cmd",
        "command",
        "url",
        "method",
        "content",
        "text",
        "patch",
    ]
    minimal: JSONDict = {}
    for key in keep_keys:
        if key not in value:
            continue
        item = value.get(key)
        if isinstance(item, str):
            if string_contains_internal_truncation_marker(item) or (
                key in CONTENT_ARGUMENT_FIELD_KEYS and len(item) > _OMIT_STRING_ABOVE_CHARS
            ):
                minimal[f"{key}{_OMITTED_SUFFIX}"] = True
                minimal[f"{key}{_ORIGINAL_CHARS_SUFFIX}"] = len(item)
                continue
            minimal[key] = (
                item if key in IDENTITY_ARGUMENT_FIELD_KEYS else _clamp_string(item, max_chars=128)
            )
            continue
        if item is None or isinstance(item, bool | int | float):
            minimal[key] = item
            continue
        if isinstance(item, dict):
            minimal[key] = dict(item)
            continue
        if isinstance(item, list):
            minimal[key] = list(item)
            continue
        minimal[key] = str(item)[:200]
    return minimal
