"""SoAI - String coercion helpers for JSON and text input [backend/core/validation/strings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_optional_trimmed_str",
    "coerce_required_non_empty_str",
    "coerce_trimmed_nonempty_str_list",
    "coerce_trimmed_str_or_empty",
    "coerce_unique_trimmed_nonempty_str_list",
    "optional_trimmed_text",
    "require_bounded_trimmed_text",
    "require_canonical_trimmed_json_text",
    "require_labeled_text",
    "require_trimmed_json_text",
    "require_trimmed_text",
)


def coerce_trimmed_nonempty_str_list(value: JSONValue) -> list[str]:
    if not isinstance(value, list):
        return []
    resolved: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            resolved.append(normalized)
    return resolved


def coerce_unique_trimmed_nonempty_str_list(value: JSONValue) -> list[str]:
    resolved: list[str] = []
    for item in coerce_trimmed_nonempty_str_list(value):
        if item not in resolved:
            resolved.append(item)
    return resolved


def coerce_optional_trimmed_str(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def coerce_trimmed_str_or_empty(value: JSONValue) -> str:
    normalized = coerce_optional_trimmed_str(value)
    return normalized or ""


def coerce_required_non_empty_str(value: JSONValue, *, label: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        if isinstance(value, str):
            raise ValidationError(f"{label} must be a non-empty string.")
        raise ValidationError(f"{label} must be a string.")
    return normalized


def require_trimmed_text(value: str | None, error_message: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(error_message)
    return text


def require_trimmed_json_text(value: JSONValue, *, error_message: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError(error_message)
    return normalized


def require_canonical_trimmed_json_text(
    value: JSONValue,
    *,
    error_message: str,
) -> str:
    normalized = require_trimmed_json_text(value, error_message=error_message)
    if normalized != value:
        raise ValidationError(error_message)
    return normalized


def require_bounded_trimmed_text(
    value: JSONValue,
    *,
    type_message: str,
    empty_message: str,
    max_length: int,
    max_length_message: str,
    nul_message: str | None = None,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(type_message)
    normalized = value.strip()
    if not normalized:
        raise ValidationError(empty_message)
    if "\x00" in normalized:
        raise ValidationError(nul_message or empty_message)
    if len(normalized) > max_length:
        raise ValidationError(max_length_message)
    return normalized


def require_labeled_text(value: str | None, *, field_label: str, suffix: str) -> str:
    return require_trimmed_text(value, f"{field_label} {suffix}")


def optional_trimmed_text(value: str | None, error_message: str) -> str | None:
    if value is None:
        return None
    return require_trimmed_text(value, error_message)
