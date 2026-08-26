"""SoAI - GPU operation result payload construction [backend/core/hardware/gpu_operation_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exceptions import ConfigurationError
from core.errors.payload import ErrorPublicPayload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_gpu_operation_error",
    "build_gpu_result",
    "extract_gpu_operation_error_detail",
    "extract_gpu_operation_error_message",
    "gpu_operation_status_code",
)

RESERVED_ERROR_PAYLOAD_KEYS: tuple[str, ...] = ("success", "code", "error")


def build_gpu_result(
    messages: list[str] | None = None,
    errors: list[str] | None = None,
    changed: bool | None = None,
) -> JSONDict:
    result: JSONDict = {
        "messages": list(messages) if messages is not None else [],
        "errors": list(errors) if errors is not None else [],
    }
    if changed is not None:
        result["changed"] = changed
    return result


def gpu_operation_status_code(code: str) -> int:
    match code:
        case "device_not_found" | "no_gpus" | "slot_empty":
            return 404
        case (
            "invalid_gpu_id"
            | "invalid_slot"
            | "invalid_payload"
            | "invalid_request_error"
            | "no_settings"
        ):
            return 400
        case "slot_unchanged" | "boot_unchanged":
            return 409
        case "slot_requires_apply":
            return 412
        case "apply_failed":
            return 500
        case "device_unavailable" | "hardware_mutation_disabled":
            return 503
        case _:
            return 400


def extract_gpu_operation_error_message(
    payload: Mapping[str, JSONValue],
    *,
    default_message: str,
) -> str:
    error_value = payload.get("error")
    if isinstance(error_value, dict):
        message_value = error_value.get("message") or error_value.get("type")
        return str(message_value) if message_value is not None else default_message
    return str(error_value) if error_value is not None else default_message


def extract_gpu_operation_error_detail(payload: Mapping[str, JSONValue]) -> JSONDict | None:
    error_value = payload.get("error")
    if not isinstance(error_value, dict):
        return None
    return {"error": dict(error_value)}


def build_gpu_operation_error(
    code: str,
    message: str,
    *,
    details: JSONDict | None = None,
    **extra: JSONValue,
) -> JSONDict:
    conflicting_keys = [key for key in RESERVED_ERROR_PAYLOAD_KEYS if key in extra]
    if conflicting_keys:
        raise ConfigurationError(
            f"Reserved hardware error payload keys cannot be supplied as extras: {conflicting_keys}.",
        )
    match code:
        case "apply_failed":
            error_type = ErrorType.SERVER_ERROR.value
        case "boot_unchanged":
            error_type = ErrorType.CONFLICT.value
        case "device_not_found" | "no_gpus" | "slot_empty":
            error_type = ErrorType.NOT_FOUND.value
        case "device_unavailable":
            error_type = ErrorType.SERVICE_UNAVAILABLE.value
        case (
            "invalid_gpu_id"
            | "invalid_payload"
            | "invalid_request_error"
            | "invalid_slot"
            | "no_settings"
        ):
            error_type = ErrorType.INVALID_REQUEST.value
        case "slot_unchanged":
            error_type = ErrorType.CONFLICT.value
        case "slot_requires_apply":
            error_type = "precondition_failed"
        case _:
            raise ConfigurationError(f"Unhandled hardware error code '{code}'.")
    error_details = dict(details or {})
    for key, value in extra.items():
        if key not in error_details:
            error_details[key] = value
    error_payload = ErrorPublicPayload(
        code=error_type,
        message=message,
        details=error_details or None,
    ).to_dict()
    payload: JSONDict = {"success": False, "code": code, "error": error_payload}
    if details is not None and "details" not in extra:
        payload["details"] = details
    payload.update(extra)
    return payload
