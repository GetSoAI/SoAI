"""SoAI - GPU settings request orchestration [backend/hardware/gpu_tuning/request_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_operation_results import (
    extract_gpu_operation_error_detail,
    extract_gpu_operation_error_message,
)
from core.hardware.gpu_settings_contract import (
    GPU_RESET_CLOCKS_FIELD,
    GPU_SETTING_FIELDS,
    extract_direct_gpu_settings,
)
from core.hardware.gpu_slot_failures import translate_gpu_slot_failure
from core.hardware.types import GPUSettingsOutcome
from core.logging.trace import get_logger
from core.validation.boolean_coercion import coerce_bool_flag
from hardware.gpu_tuning.backend_apply_results import gpu_apply_result_changed
from hardware.gpu_tuning.result_flags import is_success_result

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("handle_gpu_settings_request",)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.request_handler"


async def handle_gpu_settings_request(
    *,
    payload: Mapping[str, JSONValue],
    apply_gpu_settings_direct: Callable[[str, JSONDict], Awaitable[JSONDict]],
    apply_gpu_settings_update: Callable[[JSONDict], Awaitable[JSONDict]],
) -> tuple[GPUSettingsOutcome, bool]:
    device_id_value = payload.get("device_id")
    if isinstance(device_id_value, str):
        device_id = device_id_value.strip()
        if not device_id:
            return (
                GPUSettingsOutcome(
                    success=False,
                    status_code=422,
                    payload={},
                    audit_action="APPLY_GPU_SETTINGS_DIRECT",
                    audit_target="gpu_device:invalid",
                    audit_details={"device_id": device_id_value, "fields": []},
                    error_type="invalid_request_error",
                    error_message="device_id must be a non-empty string.",
                ),
                False,
            )
        requested_fields = [key for key in GPU_SETTING_FIELDS if payload.get(key) is not None]
        try:
            settings_payload = extract_direct_gpu_settings(payload)
        except ValidationError as exception:
            return (
                GPUSettingsOutcome(
                    success=False,
                    status_code=422,
                    payload={},
                    audit_action="APPLY_GPU_SETTINGS_DIRECT",
                    audit_target=f"gpu_device:{device_id}",
                    audit_details={
                        "device_id": device_id,
                        "fields": requested_fields or [GPU_RESET_CLOCKS_FIELD],
                    },
                    error_type="invalid_request_error",
                    error_message=str(exception),
                ),
                False,
            )
        if not settings_payload:
            return (
                GPUSettingsOutcome(
                    success=False,
                    status_code=422,
                    payload={},
                    audit_action="APPLY_GPU_SETTINGS_DIRECT",
                    audit_target=f"gpu_device:{device_id}",
                    audit_details={"device_id": device_id, "fields": []},
                    error_type="invalid_request_error",
                    error_message="No GPU settings provided for direct apply.",
                ),
                False,
            )
        result = await apply_gpu_settings_direct(device_id, settings_payload)
        audit_details: JSONDict = {
            "device_id": device_id,
            "fields": list(settings_payload.keys()),
        }
        audit_target = f"gpu_device:{device_id}"
        if not is_success_result(
            result,
            logger=get_logger(LOGGER_NAME),
            operation="hardware.gpu_tuning.request_handler.is_success_result",
        ):
            status_code, error_type, message, detail = translate_gpu_slot_failure(result)
            return (
                GPUSettingsOutcome(
                    success=False,
                    status_code=status_code,
                    payload=result,
                    audit_action="APPLY_GPU_SETTINGS_DIRECT",
                    audit_target=audit_target,
                    audit_details=audit_details,
                    error_type=error_type,
                    error_message=message,
                    error_detail=detail,
                ),
                gpu_apply_result_changed(result),
            )
        return (
            GPUSettingsOutcome(
                success=True,
                status_code=200,
                payload=result,
                audit_action="APPLY_GPU_SETTINGS_DIRECT",
                audit_target=audit_target,
                audit_details=audit_details,
            ),
            gpu_apply_result_changed(result),
        )
    target = f"gpu:{payload.get('gpu_id')}" if payload.get("gpu_id") is not None else "gpu:all"
    request_payload: JSONDict = {
        key: value for key, value in payload.items() if value is not None and key != "device_id"
    }
    result = await apply_gpu_settings_update(request_payload)
    audit_details_update: JSONDict = dict(request_payload)
    if not is_success_result(
        result,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.request_handler.is_success_result",
    ):
        if isinstance(result.get("code"), str):
            status_code, error_type, message, detail = translate_gpu_slot_failure(result)
            return (
                GPUSettingsOutcome(
                    success=False,
                    status_code=status_code,
                    payload=result,
                    audit_action="SET_GPU_SETTINGS",
                    audit_target=target,
                    audit_details=audit_details_update,
                    error_type=error_type,
                    error_message=message,
                    error_detail=detail,
                ),
                gpu_apply_result_changed(result),
            )
        return (
            GPUSettingsOutcome(
                success=False,
                status_code=400,
                payload=result,
                audit_action="SET_GPU_SETTINGS",
                audit_target=target,
                audit_details=audit_details_update,
                error_type="gpu_error",
                error_message=extract_gpu_operation_error_message(
                    result,
                    default_message="GPU settings operation failed.",
                ),
                error_detail=extract_gpu_operation_error_detail(result),
            ),
            gpu_apply_result_changed(result),
        )
    return (
        GPUSettingsOutcome(
            success=True,
            status_code=200,
            payload=result,
            audit_action="SET_GPU_SETTINGS",
            audit_target=target,
            audit_details=audit_details_update,
        ),
        coerce_bool_flag(
            result.get("changed"),
            logger=get_logger(LOGGER_NAME),
            operation="hardware.gpu_tuning.request_handler.coerce_bool_flag",
            default=False,
            recover_message="Failed to parse boolean flag (non-critical).",
        ),
    )
