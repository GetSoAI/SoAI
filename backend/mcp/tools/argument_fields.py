"""SoAI - MCP utility tool field argument validation [backend/mcp/tools/argument_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

from core.mcp.argument_shapes import (
    optional_trimmed_bounded_string,
    require_json_dict_value,
    require_string_map_value,
    require_string_value,
    require_trimmed_bounded_string_value,
)
from core.mcp.argument_validation import (
    optional_trimmed_string,
    require_no_unknown_keys,
    require_non_empty_string_value,
)
from mcp.tools.error import build_invalid_params_error

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "normalize_string_argument",
    "optional_bounded_string",
    "optional_non_empty_string",
    "optional_string",
    "reject_unexpected_parameters",
    "require_allowed_keys",
    "require_bounded_string",
    "require_json_object",
    "require_non_empty_string",
    "require_string",
    "require_string_choice",
    "require_string_map",
)


def reject_unexpected_parameters(arguments: JSONDict, allowed_keys: Collection[str]) -> None:
    require_no_unknown_keys(
        arguments,
        allowed_keys,
        build_error=build_invalid_params_error,
        message=lambda invalid_keys: f"Unexpected parameter(s): {', '.join(invalid_keys)}",
    )


def require_allowed_keys(
    arguments: JSONDict,
    *,
    allowed_keys: frozenset[str],
    tool_name: str,
) -> None:
    require_no_unknown_keys(
        arguments,
        allowed_keys,
        build_error=build_invalid_params_error,
        message=lambda invalid_keys: (
            f"{tool_name} received unknown parameter(s): {', '.join(invalid_keys)}"
        ),
    )


def require_non_empty_string(
    value: JSONValue,
    *,
    key: str,
    type_message: str | None = None,
    empty_message: str | None = None,
) -> str:
    return require_non_empty_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message=type_message or f"{key} must be a string",
        empty_message=empty_message or f"{key} must be a non-empty string",
    )


def optional_string(
    value: JSONValue,
    *,
    key: str,
    type_message: str | None = None,
) -> str | None:
    return optional_trimmed_string(
        value,
        build_error=build_invalid_params_error,
        type_message=type_message or f"{key} must be a string when provided",
    )


def optional_non_empty_string(value: JSONValue, *, key: str) -> str | None:
    if value is None:
        return None
    return require_non_empty_string(value, key=key)


def normalize_string_argument(value: JSONValue, *, field: str, required: bool) -> str | None:
    if value is None:
        if required:
            raise build_invalid_params_error(f"{field} is required")
        return None
    if required:
        return require_non_empty_string_value(
            value,
            build_error=build_invalid_params_error,
            type_message=f"{field} must be a string",
            empty_message=f"{field} must be a non-empty string",
        )
    return optional_trimmed_string(
        value,
        build_error=build_invalid_params_error,
        type_message=f"{field} must be a string",
    )


def require_string(
    value: JSONValue,
    *,
    key: str,
    type_message: str | None = None,
) -> str:
    return require_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message=type_message
        or f"Parameter '{key}' must be a string, got {type(value).__name__}",
    )


def require_bounded_string(value: JSONValue, *, field: str, max_length: int) -> str:
    return require_trimmed_bounded_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message=f"{field} must be a string",
        empty_message=f"{field} must be a non-empty string",
        max_length_message=f"{field} must be <= {max_length} characters",
        max_length=max_length,
    )


def optional_bounded_string(value: JSONValue, *, field: str, max_length: int) -> str | None:
    return optional_trimmed_bounded_string(
        value,
        build_error=build_invalid_params_error,
        type_message=f"{field} must be a string or null",
        max_length_message=f"{field} must be <= {max_length} characters",
        max_length=max_length,
    )


def require_string_choice(value: JSONValue, *, key: str, choices: tuple[str, ...]) -> str:
    normalized = require_string(value, key=key).lower()
    if normalized not in choices:
        raise build_invalid_params_error(
            f"Unknown {key}: {normalized}. Valid: {', '.join(choices)}",
        )
    return normalized


def require_json_object(value: JSONValue, *, field_name: str) -> JSONDict:
    return require_json_dict_value(
        value,
        build_error=build_invalid_params_error,
        message=f"{field_name} must be an object",
    )


def require_string_map(value: JSONValue, *, field_name: str) -> dict[str, str]:
    return require_string_map_value(
        value,
        build_error=build_invalid_params_error,
        object_message=f"{field_name} must be an object",
        key_message=f"{field_name} keys must be non-empty strings",
        value_message=lambda key: f"{field_name}[{key}] must be a string",
    )
