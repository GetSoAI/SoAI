"""SoAI - Central JSON parsing helpers [backend/core/serialization/json_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.serialization.strict_json import (
    StrictJSONDuplicateKeyError,
    StrictJSONNonFiniteError,
    decode_strict_json,
)
from core.types.json_value import coerce_str_list, is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MAX_JSON_NESTING_DEPTH",
    "StrictJSONDuplicateKeyError",
    "StrictJSONNonFiniteError",
    "parse_json_dict",
    "parse_json_dict_with_messages",
    "parse_json_str_list",
    "parse_json_value",
    "parse_json_value_or_none",
    "parse_strict_json",
    "parse_optional_json_dict",
    "parse_optional_json_value",
)

MAX_JSON_NESTING_DEPTH = 64


def parse_strict_json(
    raw: str | bytes,
    *,
    field: str = "json",
    max_depth: int | None = None,
    strict_utf8: bool = False,
    reject_duplicate_keys: bool = False,
) -> JSONValue:
    return decode_strict_json(
        raw,
        decoder=json.loads,
        field=field,
        max_depth=max_depth,
        strict_utf8=strict_utf8,
        reject_duplicate_keys=reject_duplicate_keys,
    )


def parse_json_value(
    raw: str | bytes,
    *,
    field: str = "json",
    max_depth: int | None = None,
    strict_utf8: bool = False,
    reject_duplicate_keys: bool = False,
) -> JSONValue:
    normalized_field = str(field or "").strip() or "json"
    try:
        parsed = parse_strict_json(
            raw,
            field=normalized_field,
            max_depth=max_depth,
            strict_utf8=strict_utf8,
            reject_duplicate_keys=reject_duplicate_keys,
        )
    except ValueError as exception:
        raise ValidationError(
            f"Failed to parse {normalized_field} as JSON: {type(exception).__name__}: {exception}",
        ) from exception
    normalized = normalize_for_json(parsed)
    if normalized is None or is_json_value(normalized):
        return normalized
    raise ValidationError(f"{normalized_field} must be JSON-compatible.")


def parse_json_value_or_none(raw: str | bytes | None, *, field: str = "json") -> JSONValue | None:
    if raw is None:
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    try:
        return parse_json_value(normalized, field=field)
    except ValidationError:
        return None


def parse_optional_json_value(raw: str | bytes | None, *, field: str = "json") -> JSONValue | None:
    if raw is None:
        return None
    return parse_json_value(raw, field=field)


def parse_json_dict(
    raw: str | bytes,
    *,
    field: str = "json",
    reject_duplicate_keys: bool = False,
) -> JSONDict:
    parsed = parse_json_value(
        raw,
        field=field,
        reject_duplicate_keys=reject_duplicate_keys,
    )
    if isinstance(parsed, dict):
        return parsed
    raise ValidationError(f"{field} must be a JSON object.")


def parse_json_dict_with_messages(
    raw: str | bytes,
    *,
    field: str,
    invalid_object_message: str,
    invalid_json_message: str | None = None,
) -> JSONDict:
    try:
        parsed = parse_json_value(raw, field=field)
    except ValidationError as exception:
        if invalid_json_message is None:
            raise
        raise ValidationError(invalid_json_message) from exception
    if not isinstance(parsed, dict):
        raise ValidationError(invalid_object_message)
    return parsed


def parse_json_str_list(
    raw: str | bytes,
    *,
    field: str = "json",
    strip_items: bool = False,
    drop_empty: bool = False,
) -> list[str]:
    parsed = parse_json_value(raw, field=field)
    normalized = coerce_str_list(parsed, strip_items=strip_items, drop_empty=drop_empty)
    if normalized is None:
        raise ValidationError(f"{field} must be a JSON array of strings.")
    return normalized


def parse_optional_json_dict(raw: str | bytes | None, *, field: str = "json") -> JSONDict | None:
    if raw is None:
        return None
    return parse_json_dict(raw, field=field)
