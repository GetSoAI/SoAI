"""SoAI - MCP server config field normalization rules [backend/core/mcp/server_config_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.external_accounts.state import coerce_oauth_status, optional_oauth_status
from core.serialization.json_parsing import parse_json_value
from core.timing.durations import ms_to_seconds_ceil
from core.types.json_value import coerce_str_dict, coerce_str_list
from core.validation.booleans import parse_bool_flag_or_none
from core.validation.integers import coerce_exact_int_or_none
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_config_bool",
    "coerce_optional_config_int",
    "coerce_optional_config_str",
    "coerce_optional_config_str_dict",
    "coerce_optional_config_str_list",
    "coerce_optional_row_int",
    "coerce_optional_row_str",
    "coerce_optional_row_str_dict",
    "coerce_optional_row_str_list",
    "coerce_row_bool",
    "coerce_timeout_sec_from_row",
    "normalize_config_auth_type",
    "normalize_config_oauth_status",
    "normalize_row_auth_type",
    "normalize_row_oauth_status",
    "require_non_empty_config_str",
    "require_non_empty_row_str",
)

_ALLOWED_AUTH_TYPES: frozenset[str] = frozenset({"none", "api_key", "oauth"})


def _require_allowed_string(
    value: str,
    *,
    field_name: str,
    allowed_values: frozenset[str],
    row_error: bool,
) -> str:
    normalized = value.strip().lower()
    if normalized in allowed_values:
        return normalized
    if row_error:
        raise ValidationError(f"MCP server row has invalid {field_name}.")
    raise StateError(f"MCP server config field '{field_name}' is invalid.")


def require_non_empty_row_str(value: JSONValue, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"MCP server row is missing a valid {field_name}.")
    return value.strip()


def coerce_optional_row_str(value: JSONValue) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("MCP server row has invalid text value.")
    return coerce_optional_trimmed_str(value)


def _coerce_optional_row_json(value: JSONValue, *, field_name: str) -> JSONValue | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return parse_json_value(normalized)
        except ValidationError as exception:
            raise ValidationError(f"MCP server row has invalid {field_name}.") from exception
    return value


def coerce_optional_row_str_list(value: JSONValue, *, field_name: str) -> list[str] | None:
    parsed = _coerce_optional_row_json(value, field_name=field_name)
    if parsed is None:
        return None
    normalized = coerce_str_list(parsed, drop_empty=True, strip_items=True)
    if normalized is None:
        raise ValidationError(f"MCP server row has invalid {field_name}.")
    return normalized


def coerce_optional_row_str_dict(
    value: JSONValue,
    *,
    field_name: str,
) -> dict[str, str] | None:
    parsed = _coerce_optional_row_json(value, field_name=field_name)
    if parsed is None:
        return None
    normalized = coerce_str_dict(parsed, stringify_values=False)
    if normalized is None:
        raise ValidationError(f"MCP server row has invalid {field_name}.")
    return normalized


def coerce_optional_row_int(value: JSONValue, *, field_name: str) -> int | None:
    if value is None:
        return None
    normalized = coerce_exact_int_or_none(value)
    if normalized is None:
        raise ValidationError(f"MCP server row has invalid {field_name}.")
    return int(normalized)


def coerce_timeout_sec_from_row(value: JSONValue, *, field_name: str) -> int:
    timeout_ms = coerce_optional_row_int(value, field_name=field_name)
    if timeout_ms is None:
        return 30
    if timeout_ms < 1:
        raise ValidationError(f"MCP server row has invalid {field_name}.")
    return max(1, ms_to_seconds_ceil(timeout_ms))


def coerce_row_bool(value: JSONValue, *, default: bool) -> bool:
    if value is None:
        return default
    parsed = parse_bool_flag_or_none(value)
    if parsed is None:
        raise ValidationError("MCP server row has invalid boolean value.")
    return parsed


def normalize_row_auth_type(value: JSONValue) -> str:
    if value is None:
        return "none"
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("MCP server row has invalid auth_type.")
    return _require_allowed_string(
        value,
        field_name="auth_type",
        allowed_values=_ALLOWED_AUTH_TYPES,
        row_error=True,
    )


def normalize_row_oauth_status(value: JSONValue) -> str:
    try:
        return optional_oauth_status(value)
    except ValidationError as exception:
        raise ValidationError("MCP server row has invalid oauth_status.") from exception


def require_non_empty_config_str(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    return normalized


def coerce_optional_config_str(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    normalized = value.strip()
    return normalized or None


def coerce_optional_config_str_list(
    value: JSONValue,
    *,
    field_name: str,
) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    normalized = coerce_str_list(list(value), drop_empty=True, strip_items=True)
    if normalized is None:
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    return normalized


def coerce_optional_config_str_dict(
    value: JSONValue,
    *,
    field_name: str,
) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    normalized = coerce_str_dict(dict(value), stringify_values=False)
    if normalized is None:
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    return dict(normalized)


def coerce_optional_config_int(
    value: int | None,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int | None:
    if value is None:
        return None
    normalized = coerce_exact_int_or_none(value)
    if normalized is None:
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    normalized_int = int(normalized)
    if minimum is not None and normalized_int < minimum:
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    return normalized_int


def coerce_config_bool(value: bool | None, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    parsed = parse_bool_flag_or_none(value)
    if parsed is None:
        raise StateError(f"MCP server config field '{field_name}' is invalid.")
    return parsed


def normalize_config_auth_type(value: str) -> str:
    return _require_allowed_string(
        value,
        field_name="auth_type",
        allowed_values=_ALLOWED_AUTH_TYPES,
        row_error=False,
    )


def normalize_config_oauth_status(value: str) -> str:
    try:
        return coerce_oauth_status(value)
    except ValidationError as exception:
        raise StateError("MCP server config field 'oauth_status' is invalid.") from exception
