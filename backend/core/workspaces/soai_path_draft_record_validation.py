"""SoAI - WebUI SoAI path draft record validation [backend/core/workspaces/soai_path_draft_record_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.content_part_validation_primitives import (
    require_content_part_dict,
    require_content_part_optional_string,
    require_content_part_string,
)
from core.errors.exceptions import ValidationError
from core.validation.strict_numbers import require_non_negative_int_strict
from core.workspaces.soai_path_content_validation import validate_soai_path_content_part

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("validate_soai_path_draft_record",)

_ALLOWED_FIELDS = frozenset(("type", "token", "occurrence_index", "display_label", "content_part"))
_MAX_TOKEN_CHARS = 4096
_MAX_DISPLAY_LABEL_CHARS = 512


def _require_token(value: JSONValue) -> str:
    token = require_content_part_string(
        value,
        message="SoAI path draft token must be a non-empty string.",
    )
    if "\x00" in token or len(token) > _MAX_TOKEN_CHARS:
        raise ValidationError("SoAI path draft token is invalid.")
    return token


def _require_display_label(value: JSONValue) -> str | None:
    display_label = require_content_part_optional_string(
        value,
        message="SoAI path draft display_label must be a non-empty string.",
    )
    if display_label is not None and (
        "\x00" in display_label or len(display_label) > _MAX_DISPLAY_LABEL_CHARS
    ):
        raise ValidationError("SoAI path draft display_label is invalid.")
    return display_label


def validate_soai_path_draft_record(record: JSONDict) -> JSONDict:
    for field_name in record:
        if field_name not in _ALLOWED_FIELDS:
            raise ValidationError(
                f"SoAI path draft record contains unsupported field '{field_name}'.",
            )
    if record.get("type") != "soai_path_record":
        raise ValidationError("SoAI path draft record type must be 'soai_path_record'.")
    content_part = require_content_part_dict(
        record.get("content_part"),
        message="SoAI path draft content_part must be an object.",
    )
    return {
        "type": "soai_path_record",
        "token": _require_token(record.get("token")),
        "occurrence_index": require_non_negative_int_strict(
            record.get("occurrence_index"),
            error_message="SoAI path draft occurrence_index must be a non-negative integer.",
        ),
        "display_label": _require_display_label(record.get("display_label")),
        "content_part": validate_soai_path_content_part(content_part),
    }
