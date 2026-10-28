"""SoAI - GPU slot error translation helpers shared across API and hardware subsystems [backend/core/hardware/gpu_slot_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import (
    ApiError,
    ConflictError,
    GPUControlInputValidationError,
    ValidationError,
)
from core.hardware.gpu_operation_results import build_gpu_operation_error, gpu_operation_status_code
from core.validation.strict_integer import is_strict_int
from core.validation.strings import require_bounded_trimmed_text

if TYPE_CHECKING:
    from core.hardware.types import GPUSettingsOutcome
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_gpu_settings_failure_error",
    "build_gpu_slot_failure_error",
    "translate_gpu_slot_failure",
    "GPUSlotAliasConflictError",
    "GPUSettingOutOfRangeError",
    "build_gpu_range_validation_error",
    "build_gpu_validation_failure",
)


class GPUSettingOutOfRangeError(GPUControlInputValidationError):
    code: str | int = "gpu_setting_out_of_range"
    http_status = 400


def build_gpu_range_validation_error(
    field: str, requested: int, minimum: int | None, maximum: int | None, unit: str
) -> GPUSettingOutOfRangeError:
    units = {"power_limit": "W", "fan_speed": "%", "core_clock": "MHz", "mem_clock": "MHz"}
    if field not in units or units[field] != unit:
        raise ValidationError("GPU range failure has invalid public field or unit.")
    if not is_strict_int(requested) or any(
        value is not None and not is_strict_int(value) for value in (minimum, maximum)
    ):
        raise ValidationError("GPU range failure has invalid public numbers.")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationError("GPU range failure has contradictory public bounds.")
    if not (
        (minimum is not None and requested < minimum)
        or (maximum is not None and requested > maximum)
    ):
        raise ValidationError("GPU range failure has no violated bound.")
    bounds = (
        f"{minimum} to {maximum}"
        if minimum is not None and maximum is not None
        else (f"at least {minimum}" if minimum is not None else f"at most {maximum}")
    )
    message = f"Requested {field} value {requested} {unit} is outside the supported range ({bounds} {unit}). Choose a supported value."
    error = GPUSettingOutOfRangeError(message)
    error.public_message = message
    error.public_details = {
        "field": field,
        "requested": requested,
        "minimum": minimum,
        "maximum": maximum,
        "unit": unit,
    }
    return error


class GPUSlotAliasConflictError(ConflictError):
    code: str | int = "gpu_slot_alias_conflict"
    public_message: str | None = (
        "Saved GPU aliases contain conflicting or unrecognized state. Preserve the slot file and review the saved profiles before changing this GPU."
    )


def _gpu_failure_response(code: JSONValue) -> tuple[str, str]:
    if not isinstance(code, str):
        code = "slot_error"
    match code:
        case "invalid_gpu_id":
            return "invalid_gpu_id", "Select a valid GPU and retry."
        case "invalid_slot":
            return "invalid_slot", "Select a valid GPU slot and retry."
        case "invalid_payload":
            return "invalid_payload", "Check the GPU settings and retry."
        case "invalid_request_error":
            return "invalid_request_error", "Check the GPU settings and retry."
        case "no_settings":
            return "no_settings", "Choose at least one GPU setting before applying changes."
        case "device_not_found":
            return (
                "device_not_found",
                "The selected GPU was not found. Refresh the hardware list and select it again.",
            )
        case "no_gpus":
            return "no_gpus", "No GPUs are available. Check hardware detection and retry."
        case "slot_empty":
            return (
                "slot_empty",
                "The selected GPU slot is empty. Save settings in this slot before applying it.",
            )
        case "slot_unchanged":
            return "slot_unchanged", "The GPU slot already contains these settings."
        case "boot_unchanged":
            return "boot_unchanged", "The GPU slot already has this startup setting."
        case "slot_requires_apply":
            return "slot_requires_apply", "Apply the GPU slot before enabling it at startup."
        case "gpu_control_preparation_failed":
            return (
                code,
                "GPU settings preparation failed before hardware access. Retry and report the reference ID if the problem persists.",
            )
        case "apply_failed":
            return (
                "apply_failed",
                "GPU settings could not be applied safely. Review the operation details and retry.",
            )
        case "gpu_clock_combination_unsupported":
            return (
                code,
                "This GPU cannot combine the selected clock controls. Apply one clock control at a time.",
            )
        case "gpu_clock_conversion_unavailable":
            return (
                code,
                "The driver cannot provide the required clock conversion. Refresh hardware detection and check driver support.",
            )
        case "device_unavailable":
            return (
                "device_unavailable",
                "The selected GPU is unavailable. Wait for it to recover and retry.",
            )
        case "hardware_mutation_disabled":
            return (
                "hardware_mutation_disabled",
                "GPU hardware changes are disabled for this installation.",
            )
        case "gpu_activity_conflict":
            return (
                "gpu_activity_conflict",
                "The GPU is busy with another operation. Wait for it to finish and retry.",
            )
        case "hardware_unavailable":
            return (
                "hardware_unavailable",
                "GPU tuning is unavailable in this installation. Check hardware support and configuration.",
            )
        case "gpu_error":
            return "gpu_error", "The GPU settings operation failed. Check the settings and retry."
        case _:
            return (
                "slot_error",
                "The GPU slot operation failed. Refresh the hardware list and retry.",
            )


def translate_gpu_slot_failure(
    result: Mapping[str, JSONValue],
) -> tuple[int, str, str, JSONDict]:
    if result.get("code") == "gpu_setting_out_of_range":
        error = _range_failure(result)
        return 400, str(error.code), error.public_message or error.message, dict(result)
    code, message = _gpu_failure_response(result.get("code"))
    return gpu_operation_status_code(code), code, message, dict(result)


def build_gpu_slot_failure_error(
    result: Mapping[str, JSONValue],
    *,
    operation: str | None = None,
    trace_id: str | None = None,
    status_code: int | None = None,
) -> ApiError:
    translated_status, code, message, private_details = translate_gpu_slot_failure(result)
    error = ApiError(
        message,
        code=code,
        http_status=translated_status if status_code is None else status_code,
        details=private_details,
        operation=operation,
        trace_id=trace_id,
    )
    error.public_message = message
    context = _public_gpu_failure_context(result)
    if code == "gpu_setting_out_of_range":
        context.update(_range_failure(result).public_details or {})
    error.public_details = context or None
    return error


def build_gpu_settings_failure_error(
    outcome: GPUSettingsOutcome,
    *,
    trace_id: str | None = None,
) -> ApiError:
    result: JSONDict = {
        "code": outcome.error_type or "gpu_error",
        "error": outcome.error_message,
        "details": outcome.error_detail,
        "result": outcome.payload,
        "device_id": outcome.audit_details.get("device_id") or outcome.payload.get("device_id"),
    }
    return build_gpu_slot_failure_error(
        result,
        trace_id=trace_id,
        operation="hardware.gpu.settings.update",
        status_code=outcome.status_code,
    )


def _public_gpu_failure_context(result: Mapping[str, JSONValue]) -> JSONDict:
    context: JSONDict = {}
    device_value = result.get("device_id")
    try:
        device_id = require_bounded_trimmed_text(
            device_value,
            type_message="Invalid GPU diagnostic identity.",
            empty_message="Invalid GPU diagnostic identity.",
            max_length=4096,
            max_length_message="Invalid GPU diagnostic identity.",
        )
    except ValidationError:
        device_id = ""
    if device_id.startswith("gpu:") and len(device_id) > 4:
        device_bytes: bytes | None
        try:
            device_bytes = device_id.encode("utf-8")
        except UnicodeEncodeError:
            device_bytes = None
        if device_bytes is not None:
            context["device_reference"] = f"gpu-{hashlib.sha256(device_bytes).hexdigest()}"
    slot = result.get("slot")
    if isinstance(slot, str) and slot in ("1", "2", "3"):
        context["slot"] = slot
    return context


def _range_failure(result: Mapping[str, JSONValue]) -> GPUSettingOutOfRangeError:
    details = result.get("details")
    if not isinstance(details, dict):
        raise ValidationError("GPU range failure has no public operands.")
    field, unit = details.get("field"), details.get("unit")
    requested, minimum, maximum = (
        details.get("requested"),
        details.get("minimum"),
        details.get("maximum"),
    )
    if not isinstance(field, str) or not isinstance(unit, str) or not is_strict_int(requested):
        raise ValidationError("GPU range failure operands are invalid.")
    if minimum is not None and not is_strict_int(minimum):
        raise ValidationError("GPU minimum bound is invalid.")
    if maximum is not None and not is_strict_int(maximum):
        raise ValidationError("GPU maximum bound is invalid.")
    return build_gpu_range_validation_error(field, requested, minimum, maximum, unit)


def build_gpu_validation_failure(exception: ValidationError, **context: JSONValue) -> JSONDict:
    if isinstance(exception, GPUSettingOutOfRangeError):
        return build_gpu_operation_error(
            str(exception.code),
            exception.public_message or exception.message,
            details=dict(exception.public_details or {}),
            **context,
        )
    return build_gpu_operation_error(
        "invalid_request_error", exception.message, details=None, **context
    )
