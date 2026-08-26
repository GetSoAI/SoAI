"""SoAI - WebUI content part validation primitives [backend/core/conversations/content_part_validation_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "require_content_part_dict",
    "require_content_part_optional_string",
    "require_content_part_string",
)


def require_content_part_dict(value: JSONValue, *, message: str) -> JSONDict:
    if not isinstance(value, dict):
        raise ValidationError(message)
    return dict(value)


def require_content_part_string(
    value: JSONValue,
    *,
    message: str,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(message)
    if not allow_empty and not value.strip():
        raise ValidationError(message)
    if "\x00" in value:
        raise ValidationError(message)
    return value


def require_content_part_optional_string(value: JSONValue, *, message: str) -> str | None:
    if value is None:
        return None
    return require_content_part_string(value, message=message, allow_empty=False)
