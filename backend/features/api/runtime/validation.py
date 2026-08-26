"""SoAI - API runtime validation helpers [backend/features/api/runtime/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import normalize_to_json_dict
from core.types.json_value import coerce_json_dict
from core.validation.epoch import require_unix_epoch_ms
from features.api.runtime.errors import raise_server_error

if TYPE_CHECKING:
    from core.runtime.protocols import ConnectionProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "require_bool_value",
    "require_conversation_model_settings_payload",
    "require_field",
    "require_json_dict",
    "require_optional_json_dict",
    "require_optional_str_value",
    "require_str_value",
    "require_unix_timestamp_ms",
)


def require_str_value(
    request: ConnectionProtocol,
    value: JSONValue,
    *,
    message: str,
    allow_empty: bool = True,
) -> str:
    if isinstance(value, str) and (allow_empty or value.strip()):
        return value
    raise_server_error(request, message)


def require_optional_str_value(
    request: ConnectionProtocol,
    value: JSONValue,
    *,
    field: str,
) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise_server_error(request, f"Conversation field '{field}' must be a string or null.")


def require_bool_value(request: ConnectionProtocol, value: JSONValue, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise_server_error(request, f"Conversation field '{field}' must be a boolean.")


def require_unix_timestamp_ms(request: ConnectionProtocol, value: JSONValue, *, field: str) -> int:
    message = f"Conversation field '{field}' must be an epoch-millisecond timestamp."
    try:
        return require_unix_epoch_ms(value, error_message=message)
    except ValidationError:
        raise_server_error(request, message)


def require_field(
    request: ConnectionProtocol,
    record: Mapping[str, JSONValue],
    field: str,
) -> JSONValue:
    if field not in record:
        raise_server_error(request, f"Conversation field '{field}' is required.")
    return record[field]


def require_json_dict(
    request: ConnectionProtocol,
    value: JSONDict | JSONValue,
    *,
    message: str,
) -> JSONDict:
    try:
        return normalize_to_json_dict(value, message=message)
    except (StateError, ValidationError):
        raise_server_error(request, message)
    raise StateError("JSON payload coercion unexpectedly returned.")


def require_optional_json_dict(
    request: ConnectionProtocol,
    value: JSONValue,
    *,
    field: str,
) -> JSONDict:
    if value is None:
        return {}
    result = coerce_json_dict(value)
    if result is None:
        raise_server_error(request, f"Conversation field '{field}' is invalid.")
    return result


def require_conversation_model_settings_payload(
    request: ConnectionProtocol,
    value: JSONValue,
    *,
    field: str = "model_settings",
) -> JSONDict:
    message = f"Conversation field '{field}' is invalid."
    result = coerce_json_dict(value)
    if result is None:
        raise_server_error(request, message)
    return result
