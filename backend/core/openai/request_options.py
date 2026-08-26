"""SoAI - OpenAI request option validation [backend/core/openai/request_options.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.request_field_validation import first_unknown_field

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OpenAIStreamOptions",
    "extract_openai_bool_flag",
    "extract_openai_store_flag",
    "validate_openai_stream_options",
)


@dataclass(frozen=True, slots=True)
class OpenAIStreamOptions:
    include_usage: bool | None
    include_obfuscation: bool | None


def extract_openai_bool_flag(
    payload: JSONDict,
    *,
    key: str,
    default: bool,
    trace_id: str | None = None,
) -> bool:
    if key not in payload:
        return bool(default)
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    raise ValidationError(
        f"{key} must be a boolean.",
        details={"param": key},
        trace_id=trace_id,
    )


def extract_openai_store_flag(
    payload: JSONDict,
    *,
    default: bool,
    trace_id: str | None = None,
) -> bool:
    return extract_openai_bool_flag(
        payload,
        key="store",
        default=default,
        trace_id=trace_id,
    )


def validate_openai_stream_options(
    payload: JSONDict,
    *,
    trace_id: str | None,
    allow_include_usage: bool,
) -> OpenAIStreamOptions | None:
    stream_options_value = payload.get("stream_options")
    if stream_options_value is None:
        return None
    if payload.get("stream") is not True:
        raise ValidationError(
            "stream_options is only supported when stream=true.",
            details={"param": "stream_options"},
            trace_id=trace_id,
        )
    if not isinstance(stream_options_value, dict):
        raise ValidationError(
            "stream_options must be an object.",
            details={"param": "stream_options"},
            trace_id=trace_id,
        )
    field_name = first_unknown_field(
        stream_options_value,
        allowed_fields=(
            frozenset({"include_usage", "include_obfuscation"})
            if allow_include_usage
            else frozenset({"include_obfuscation"})
        ),
    )
    if field_name is not None:
        field_path = f"stream_options.{field_name}"
        raise ValidationError(
            f"Unsupported field: '{field_path}'.",
            details={"param": field_path},
            trace_id=trace_id,
        )
    include_usage: bool | None = None
    include_usage_value = stream_options_value.get("include_usage")
    if allow_include_usage:
        if include_usage_value is not None and not isinstance(include_usage_value, bool):
            raise ValidationError(
                "stream_options.include_usage must be a boolean.",
                details={"param": "stream_options.include_usage"},
                trace_id=trace_id,
            )
        include_usage = include_usage_value if isinstance(include_usage_value, bool) else None
    include_obfuscation_value = stream_options_value.get("include_obfuscation")
    if include_obfuscation_value is not None and not isinstance(include_obfuscation_value, bool):
        raise ValidationError(
            "stream_options.include_obfuscation must be a boolean.",
            details={"param": "stream_options.include_obfuscation"},
            trace_id=trace_id,
        )
    include_obfuscation = (
        include_obfuscation_value if isinstance(include_obfuscation_value, bool) else None
    )
    return OpenAIStreamOptions(
        include_usage=include_usage,
        include_obfuscation=include_obfuscation,
    )
