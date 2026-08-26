"""SoAI - MCP server write field coercion [backend/core/mcp/server_write_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.argument_validation import require_non_empty_string_value
from core.security.secret_crypto import coerce_optional_secret_plaintext
from core.types.json_value import coerce_str_dict, coerce_str_list
from core.validation.booleans import parse_bool_token_or_none
from core.validation.integers import coerce_exact_int_or_none
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "MCP_SERVER_TIMEOUT_DEFAULT_MS",
    "MCP_SERVER_TIMEOUT_MAX_MS",
    "MCP_SERVER_TIMEOUT_MIN_MS",
    "coerce_mcp_auth_type",
    "coerce_mcp_optional_epoch_ms",
    "coerce_mcp_optional_secret_text",
    "coerce_mcp_optional_str_dict",
    "coerce_mcp_optional_str_list",
    "coerce_mcp_optional_text",
    "coerce_mcp_required_bool_flag",
    "coerce_mcp_required_text",
    "coerce_mcp_timeout_ms",
    "coerce_mcp_transport_type",
)

MCP_SERVER_TIMEOUT_DEFAULT_MS: int = 30_000
MCP_SERVER_TIMEOUT_MIN_MS: int = 5_000
MCP_SERVER_TIMEOUT_MAX_MS: int = 300_000


def coerce_mcp_timeout_ms(value: JSONValue | None) -> int:
    if value is None:
        raise ValidationError("timeout_ms must not be null.")
    timeout_value = coerce_exact_int_or_none(value)
    if timeout_value is None:
        raise ValidationError("timeout_ms must be an integer.")
    if timeout_value < MCP_SERVER_TIMEOUT_MIN_MS:
        raise ValidationError(
            f"timeout_ms must be greater than or equal to {MCP_SERVER_TIMEOUT_MIN_MS}.",
        )
    if timeout_value > MCP_SERVER_TIMEOUT_MAX_MS:
        raise ValidationError(
            f"timeout_ms must be less than or equal to {MCP_SERVER_TIMEOUT_MAX_MS}.",
        )
    return timeout_value


def coerce_mcp_required_text(value: JSONValue | None, field_name: str) -> str:
    return require_non_empty_string_value(
        value,
        build_error=ValidationError,
        type_message=f"{field_name} must be a string.",
        empty_message=f"{field_name} must not be empty.",
    )


def coerce_mcp_optional_text(value: JSONValue | None, field_name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")
    return coerce_optional_trimmed_str(value)


def coerce_mcp_optional_secret_text(value: JSONValue | None, field_name: str) -> str | None:
    return coerce_optional_secret_plaintext(value, label=field_name)


def coerce_mcp_optional_str_list(value: JSONValue | None, field_name: str) -> list[str] | None:
    if value is None:
        return None
    normalized = coerce_str_list(value, drop_empty=True, strip_items=True)
    if normalized is None:
        raise ValidationError(f"{field_name} must be an array of strings.")
    return normalized


def coerce_mcp_optional_str_dict(
    value: JSONValue | None,
    field_name: str,
) -> dict[str, str] | None:
    if value is None:
        return None
    normalized = coerce_str_dict(value, stringify_values=False)
    if normalized is None:
        raise ValidationError(f"{field_name} must be an object of string values.")
    for key in normalized:
        if not key:
            raise ValidationError(f"{field_name} contains an empty key.")
    return normalized


def coerce_mcp_transport_type(
    value: JSONValue | None,
    *,
    allowed_transport_types: frozenset[str],
) -> str:
    normalized = coerce_mcp_required_text(value, "transport_type")
    if normalized not in allowed_transport_types:
        raise ValidationError("transport_type must be one of: stdio, streamable_http.")
    return normalized


def coerce_mcp_auth_type(value: JSONValue | None) -> str:
    normalized = coerce_mcp_required_text(value, "auth_type")
    if normalized not in {"none", "api_key", "oauth"}:
        raise ValidationError("auth_type must be one of: none, api_key, oauth.")
    return normalized


def coerce_mcp_optional_epoch_ms(value: JSONValue | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    parsed = coerce_exact_int_or_none(value)
    if parsed is None:
        raise ValidationError(f"{field_name} must be an integer.")
    if parsed < 0:
        raise ValidationError(f"{field_name} must be greater than or equal to 0.")
    return parsed


def coerce_mcp_required_bool_flag(value: JSONValue | None, field_name: str) -> int:
    parsed = parse_bool_token_or_none(value)
    if parsed is not None:
        return int(parsed)
    if value is None:
        raise ValidationError(f"{field_name} must not be null.")
    raise ValidationError(f"{field_name} must be a boolean.")
