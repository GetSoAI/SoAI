"""SoAI - Boolean coercion helpers [backend/core/validation/boolean_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.types.json import JSONValue
from core.validation.booleans import parse_bool, parse_bool_token_or_none

__all__ = (
    "coerce_bool",
    "coerce_bool_flag",
    "coerce_bool_with_default",
    "coerce_bool_with_recovery",
    "coerce_payload_bool",
    "coerce_success_flag",
)

OPERATION_CORE_VALIDATION_BOOLEAN_COERCION_COERCE_BOOL_WITH_RECOVERY = (
    "core.validation.boolean_coercion.coerce_bool_with_recovery"
)


def coerce_bool_with_recovery(
    value: bool | str | JSONValue,
    key: str | None = None,
    *,
    logger: LoggerProtocol,
    operation: str,
    default: bool = False,
    recover_message: str | None = None,
) -> bool:
    if key is not None and isinstance(value, Mapping):
        normalized_value = value.get(key)
    else:
        normalized_value = value
    try:
        return bool(parse_bool(normalized_value, default=default))
    except ValidationError as exception:
        if recover_message is None:
            details: dict[str, JSONValue] = {"coerce_operation": operation}
            if key:
                details["key"] = key
            log_handled_exception(
                logger,
                exception,
                message="Failed to parse boolean flag from payload (non-critical).",
                operation=OPERATION_CORE_VALIDATION_BOOLEAN_COERCION_COERCE_BOOL_WITH_RECOVERY,
                details=details,
                level="debug",
            )
            return default
        logger.debug(recover_message)
        return default


def coerce_payload_bool(
    value: bool | str | JSONValue,
    *,
    logger: LoggerProtocol,
    operation: str,
    default: bool = False,
    recover_message: str = "Failed to parse boolean from payload (non-critical).",
) -> bool:
    return coerce_bool_with_recovery(
        value,
        logger=logger,
        operation=operation,
        default=default,
        recover_message=recover_message,
    )


def coerce_bool_flag(
    value: bool | str | JSONValue,
    *,
    logger: LoggerProtocol,
    operation: str,
    default: bool = False,
    recover_message: str = "Failed to parse boolean flag (non-critical).",
) -> bool:
    return coerce_payload_bool(
        value,
        logger=logger,
        operation=operation,
        default=default,
        recover_message=recover_message,
    )


def coerce_success_flag(
    payload: JSONValue | Mapping[str, JSONValue],
    key: str,
    *,
    logger: LoggerProtocol,
    operation: str,
    default: bool = False,
    recover_message: str | None = None,
) -> bool:
    return coerce_bool_with_recovery(
        payload,
        key,
        logger=logger,
        operation=operation,
        default=default,
        recover_message=(
            recover_message or "Failed to parse success flag from payload (non-critical)."
        ),
    )


def coerce_bool_with_default(
    value: JSONValue | bytes | bytearray,
    default: bool = False,
    *,
    strict: bool = True,
) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        parsed_token = parse_bool_token_or_none(stripped)
        if parsed_token is not None:
            return parsed_token
        if not strict:
            return bool(value)
    if strict:
        raise ValidationError(f"Invalid boolean value '{value}'.")
    return bool(value)


def coerce_bool(value: JSONValue | bytes | bytearray, default: bool = False) -> bool:
    return coerce_bool_with_default(value, default=default, strict=True)
