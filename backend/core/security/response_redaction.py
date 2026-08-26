"""SoAI - Response payload redaction helpers [backend/core/security/response_redaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.security.sensitive_detection import (
    SENSITIVE_VALUE_PATTERN_TEXTS,
    is_sensitive_key_name,
    looks_like_sensitive_string,
)
from core.serialization.json import normalize_for_json
from core.types.json import is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "REDACTED_PLACEHOLDER",
    "SENSITIVE_VALUE_PATTERN_TEXTS",
    "is_sensitive_response_key",
    "looks_like_sensitive_value",
    "redact_response_payload",
)

REDACTED_PLACEHOLDER = "***REDACTED***"


def looks_like_sensitive_value(value: str) -> bool:
    return looks_like_sensitive_string(value)


def is_sensitive_response_key(key: str) -> bool:
    return is_sensitive_key_name(key)


def redact_response_payload(
    value: JSONValue,
    *,
    max_depth: int = 20,
    preserve_empty_sensitive_strings: bool = False,
) -> JSONValue:
    max_depth = max(max_depth, 1)

    def _redact(
        node: JSONValue | bytes | bytearray | memoryview,
        *,
        key: str | None,
        depth: int,
    ) -> JSONValue:
        if depth > max_depth:
            return {"__truncated__": REDACTED_PLACEHOLDER}
        if isinstance(key, str) and is_sensitive_response_key(key):
            if preserve_empty_sensitive_strings and isinstance(node, str) and node == "":
                return ""
            return REDACTED_PLACEHOLDER
        if isinstance(node, Mapping):
            redacted: JSONDict = {}
            for raw_key, raw_value in node.items():
                key_str = str(raw_key)
                redacted[key_str] = _redact(raw_value, key=key_str, depth=depth + 1)
            return redacted
        if isinstance(node, list | tuple):
            return [_redact(item, key=key, depth=depth + 1) for item in node]
        if isinstance(node, bytes | bytearray | memoryview):
            return REDACTED_PLACEHOLDER
        if isinstance(node, str):
            if looks_like_sensitive_value(node):
                return REDACTED_PLACEHOLDER
            return node
        if is_json_value(node):
            return node
        return normalize_for_json(node)

    return _redact(value, key=None, depth=0)
