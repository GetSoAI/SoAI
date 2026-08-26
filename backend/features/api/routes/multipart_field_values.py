"""SoAI - Multipart form field value parsing [backend/features/api/routes/multipart_field_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONValue
from core.validation.booleans import parse_true_false_token_or_none
from core.validation.integers import coerce_exact_int_or_none
from core.validation.numbers import coerce_float_from_json

__all__ = (
    "field_optional_bool",
    "field_optional_float",
    "field_optional_int",
    "field_optional_json",
    "field_optional_json_object",
    "field_optional_ranged_int",
    "field_optional_str",
    "field_optional_str_list",
    "field_optional_str_list_alias",
    "field_required_int",
    "field_required_str",
)


def _field_values(
    fields: dict[str, tuple[str, ...]],
    key: str,
) -> tuple[str, ...] | None:
    values = fields.get(key)
    if values is None:
        return None
    if not isinstance(values, tuple) or not values:
        raise ValidationError(f"Field '{key}' must not be empty.")
    normalized = tuple(value.strip() for value in values if isinstance(value, str))
    normalized = tuple(value for value in normalized if value)
    if not normalized:
        raise ValidationError(f"Field '{key}' must not be empty.")
    return normalized


def field_required_str(fields: dict[str, tuple[str, ...]], key: str) -> str:
    values = _field_values(fields, key)
    if values is None:
        raise ValidationError(f"Missing required field '{key}'.")
    if len(values) != 1:
        raise ValidationError(f"Field '{key}' must be provided exactly once.")
    return values[0]


def field_optional_str(fields: dict[str, tuple[str, ...]], key: str) -> str | None:
    values = _field_values(fields, key)
    if values is None:
        return None
    if len(values) != 1:
        raise ValidationError(f"Field '{key}' must be provided at most once.")
    return values[0]


def field_optional_str_list(
    fields: dict[str, tuple[str, ...]],
    key: str,
) -> tuple[str, ...]:
    values = _field_values(fields, key)
    if values is None:
        return ()
    return values


def field_optional_str_list_alias(
    fields: dict[str, tuple[str, ...]],
    *,
    key: str,
    alias_key: str,
) -> tuple[str, ...]:
    primary = _field_values(fields, key)
    alias = _field_values(fields, alias_key)
    if primary is not None and alias is not None:
        raise ValidationError(f"Field '{key}' must not be provided together with '{alias_key}'.")
    if primary is not None:
        return primary
    if alias is not None:
        return alias
    return ()


def field_optional_bool(fields: dict[str, tuple[str, ...]], key: str) -> bool | None:
    raw = field_optional_str(fields, key)
    if raw is None:
        return None
    parsed = parse_true_false_token_or_none(raw)
    if parsed is not None:
        return parsed
    raise ValidationError(f"Field '{key}' must be 'true' or 'false'.")


def field_optional_json(
    fields: dict[str, tuple[str, ...]],
    key: str,
    *,
    invalid_json_message: str | None = None,
) -> JSONValue:
    raw = field_optional_str(fields, key)
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return parse_json_value(stripped)
    except ValidationError as exception:
        message = invalid_json_message or f"Field '{key}' must be valid JSON."
        raise ValidationError(message) from exception


def field_optional_json_object(
    fields: dict[str, tuple[str, ...]],
    key: str,
    *,
    invalid_json_message: str | None = None,
    invalid_object_message: str | None = None,
) -> dict[str, JSONValue] | None:
    parsed = field_optional_json(fields, key, invalid_json_message=invalid_json_message)
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        message = invalid_object_message or f"Field '{key}' must be a JSON object."
        raise ValidationError(message)
    return parsed


def field_optional_int(fields: dict[str, tuple[str, ...]], key: str) -> int | None:
    raw = field_optional_str(fields, key)
    if raw is None:
        return None
    parsed = coerce_exact_int_or_none(raw)
    if parsed is None:
        raise ValidationError(f"Field '{key}' must be an integer.")
    return parsed


def field_optional_ranged_int(
    fields: dict[str, tuple[str, ...]],
    key: str,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    parsed = field_optional_int(fields, key)
    if parsed is None:
        return None
    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"Field '{key}' must be between {minimum} and {maximum}.")
    return parsed


def field_required_int(
    fields: dict[str, tuple[str, ...]],
    key: str,
    *,
    minimum: int | None = None,
) -> int:
    raw = field_required_str(fields, key)
    parsed = coerce_exact_int_or_none(raw)
    if parsed is None:
        raise ValidationError(f"Field '{key}' must be an integer.")
    if minimum is not None and parsed < minimum:
        raise ValidationError(f"Field '{key}' must be >= {minimum}.")
    return parsed


def field_optional_float(fields: dict[str, tuple[str, ...]], key: str) -> float | None:
    raw = field_optional_str(fields, key)
    if raw is None:
        return None
    parsed = coerce_float_from_json(raw, default=None, allow_bool=False, allow_nonfinite=True)
    if parsed is None:
        raise ValidationError(f"Field '{key}' must be a float.")
    finite = coerce_float_from_json(raw, default=None, allow_bool=False, allow_nonfinite=False)
    if finite is None:
        raise ValidationError(f"Field '{key}' must be a finite float.")
    return parsed
