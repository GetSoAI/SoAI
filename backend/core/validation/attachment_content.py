"""SoAI - Attachment content validation helpers [backend/core/validation/attachment_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.types.json import JSONDict, JSONValue

    type ErrorBuilder = Callable[[str], Exception]

__all__ = ("require_attachment_content_fragment", "require_attachment_content_list")


def require_attachment_content_fragment(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder = ValidationError,
    object_message: str | None = None,
    type_message: str | None = None,
) -> JSONDict:
    entry = coerce_json_dict(value)
    if entry is None:
        raise build_error(object_message or f"{label} must be an object.")
    type_value = entry.get("type")
    entry_type = type_value.strip() if isinstance(type_value, str) else ""
    if not entry_type:
        raise build_error(type_message or f"{label} must include a non-empty type.")
    return entry


def require_attachment_content_list(
    value: JSONValue,
    *,
    label: str = "attachment_content",
    build_error: ErrorBuilder = ValidationError,
    invalid_message: str | None = None,
    entry_object_message: str | None = None,
    entry_type_message: str | None = None,
) -> list[JSONDict]:
    if not isinstance(value, list):
        raise build_error(invalid_message or f"{label} must be a list.")
    validated: list[JSONDict] = []
    for index, entry in enumerate(value):
        validated.append(
            require_attachment_content_fragment(
                entry,
                label=f"{label} entry {index + 1}",
                build_error=build_error,
                object_message=entry_object_message,
                type_message=entry_type_message,
            ),
        )
    return validated
