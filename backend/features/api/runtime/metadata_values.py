"""SoAI - Metadata sanitization and redaction helpers for runtime logging/task metadata [backend/features/api/runtime/metadata_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.security.sensitive_detection import (
    SENSITIVE_VALUE_PATTERN_TEXTS,
    is_sensitive_key_name,
)
from core.serialization.json import normalize_for_json
from core.types.json import is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "safe_metadata_value",
    "sanitize_dict_for_logging",
)


def is_sensitive_key(key: str) -> bool:
    return is_sensitive_key_name(key, include_credential_containers=True)


def safe_metadata_value(key: str, value: JSONValue | bytes | bytearray | memoryview) -> JSONValue:
    if is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        nested: JSONDict = {
            str(sub_key): safe_metadata_value(str(sub_key), sub_val)
            for sub_key, sub_val in value.items()
        }
        return nested
    if isinstance(value, list | tuple):
        return [safe_metadata_value(key, item) for item in value]
    if isinstance(value, bytes | bytearray | memoryview):
        return "[BINARY_REDACTED]"
    if isinstance(value, str):
        for pattern_text in SENSITIVE_VALUE_PATTERN_TEXTS:
            if re.search(pattern_text, value):
                return "[REDACTED]"
        if len(value) > 500:
            return f"{value[:500]}...[truncated]"
        return value
    if is_json_value(value):
        return value
    return normalize_for_json(value)


def sanitize_dict_for_logging(data: Mapping[str, JSONValue], _depth: int = 0) -> JSONDict:
    if _depth > 10:
        return {"__truncated__": "max depth exceeded"}
    result: JSONDict = {}
    for raw_key, raw_value in data.items():
        key_str = str(raw_key)
        if is_sensitive_key(key_str):
            result[key_str] = "***REDACTED***"
            continue
        if isinstance(raw_value, Mapping):
            nested: dict[str, JSONValue] = {}
            for nested_key, nested_value in raw_value.items():
                if isinstance(nested_key, str) and is_json_value(nested_value):
                    nested[nested_key] = nested_value
            result[key_str] = sanitize_dict_for_logging(nested, _depth + 1)
            continue
        if isinstance(raw_value, list | tuple):
            items: list[JSONValue] = []
            for item in raw_value:
                if is_json_value(item):
                    items.append(item)
                else:
                    items.append(normalize_for_json(item))
            result[key_str] = items
            continue
        result[key_str] = raw_value if is_json_value(raw_value) else normalize_for_json(raw_value)
    return result
