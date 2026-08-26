"""SoAI - Chat preset Unicode text canonicalization [backend/core/chat_presets/text_canonicalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = ("canonicalize_trimmed_text", "require_unicode_scalar_text")


def require_unicode_scalar_text(value: str, *, field: str) -> str:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValidationError(f"{field} must contain only Unicode scalar values.")
    return value


def canonicalize_trimmed_text(
    value: JSONValue,
    *,
    field: str,
    nullable: bool,
) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        expected = "a string or null" if nullable else "a non-empty string"
        raise ValidationError(f"{field} must be {expected}.")
    normalized = require_unicode_scalar_text(value, field=field).strip()
    if normalized:
        return normalized
    if nullable:
        return None
    raise ValidationError(f"{field} must be a non-empty string.")
