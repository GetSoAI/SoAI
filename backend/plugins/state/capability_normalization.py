"""SoAI - Pure functions for normalizing and formatting capability requirements [backend/plugins/state/capability_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.runtime.platform import (
    normalize_arch_id,
    normalize_os_id,
    normalize_platform_id,
)
from core.serialization.json_parsing import parse_json_value
from core.types.json_value import is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "as_json_list",
    "format_capability_values",
    "normalize_required_capabilities",
)


def as_json_list(values: Iterable[JSONValue]) -> list[JSONValue]:
    result: list[JSONValue] = []
    for value in values:
        if not is_json_value(value):
            raise ValidationError("Capability list contains a non-JSON value.")
        result.append(value)
    return result


def normalize_required_capabilities(
    value: JSONValue,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    if isinstance(value, str):
        try:
            parsed = parse_json_value(value)
            if not isinstance(parsed, dict):
                parsed = {}
        except (ValidationError, TypeError):
            parsed = {}
    elif isinstance(value, Mapping):
        parsed = dict(value)
    else:
        parsed = {}
    raw: dict[str, list[str]] = {}
    normalized: dict[str, list[str]] = {}
    for key, raw_val in parsed.items():
        if not isinstance(key, str):
            continue
        normalized_key = key.strip().lower()
        if not normalized_key:
            continue
        if isinstance(raw_val, list | tuple | set):
            values = [str(item).strip() for item in raw_val if str(item).strip()]
        elif raw_val in (None, "", False):
            values = []
        else:
            values = [str(raw_val).strip()]
        raw[normalized_key] = values
        normalized[normalized_key] = _normalize_values(normalized_key, values)
    return (raw, normalized)


def _normalize_values(key: str, values: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in values:
        lowered = item.lower()
        candidate: str | None
        if lowered == "any":
            candidate = "any"
        elif key == "os":
            candidate = normalize_os_id(item)
        elif key == "arch":
            candidate = normalize_arch_id(item)
        elif key in {"platform", "platforms"}:
            candidate = normalize_platform_id(item)
        else:
            candidate = lowered
        if candidate is not None and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def format_capability_values(values: Iterable[JSONValue]) -> str:
    ordered: list[str] = []
    for item in values:
        text = str(item).strip().upper()
        if text and text not in ordered:
            ordered.append(text)
    return ", ".join(ordered) if ordered else "ANY"
