"""SoAI - Sensitive data redaction utilities for logging [backend/core/logging/redaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.security.sensitive_detection import is_sensitive_key_name

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "is_sensitive_key",
    "redact_value",
)

MAX_DISPLAY_LENGTH = 100
REVEAL_CHARS = 4


def is_sensitive_key(key: str) -> bool:
    return is_sensitive_key_name(key)


def redact_value(key: str, value: JSONValue, *, max_length: int = MAX_DISPLAY_LENGTH) -> str:
    if value is None:
        return "None"
    string_value = str(value)
    if is_sensitive_key(key):
        value_length = len(string_value)
        if value_length <= REVEAL_CHARS * 2:
            return "*" * value_length
        prefix = string_value[:REVEAL_CHARS]
        suffix = string_value[-REVEAL_CHARS:]
        return f"{prefix}****...****{suffix}"
    if len(string_value) > max_length:
        return f"{string_value[:max_length]}... [truncated]"
    return string_value
