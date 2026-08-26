"""SoAI - OpenAI request field validation primitives [backend/core/openai/request_field_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Never

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "first_unknown_field",
    "raise_required_string_field",
    "raise_unsupported_field",
    "reject_unsupported_openai_request_fields",
    "select_first_field_name",
)


def select_first_field_name(fields: list[str]) -> str:
    candidates = [field for field in fields if field]
    if candidates:
        return sorted(candidates)[0]
    return "unknown"


def first_unknown_field(
    payload: Mapping[str, JSONValue],
    *,
    allowed_fields: frozenset[str],
) -> str | None:
    unknown_fields = [key for key in payload if key not in allowed_fields]
    if not unknown_fields:
        return None
    return select_first_field_name(unknown_fields)


def raise_unsupported_field(field_name: str, *, trace_id: str | None) -> Never:
    raise ValidationError(
        f"Unsupported field: '{field_name}'.",
        details={"param": field_name},
        trace_id=trace_id,
    )


def reject_unsupported_openai_request_fields(
    payload: Mapping[str, JSONValue],
    *,
    forbidden_fields: tuple[str, ...],
    trace_id: str | None,
) -> None:
    for field in forbidden_fields:
        if field in payload:
            raise_unsupported_field(field, trace_id=trace_id)


def raise_required_string_field(
    payload: Mapping[str, JSONValue],
    *,
    field_name: str,
    trace_id: str | None,
) -> str:
    value = coerce_optional_trimmed_str(payload.get(field_name))
    if value is None:
        raise ValidationError(
            f"{field_name} is required and must be a non-empty string.",
            details={"param": field_name},
            trace_id=trace_id,
        )
    return value
