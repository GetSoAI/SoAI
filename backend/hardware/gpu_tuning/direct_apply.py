"""SoAI - Direct GPU settings application helpers [backend/hardware/gpu_tuning/direct_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.logging.trace import get_logger
from core.timing.formatting import utc_now_iso
from core.types.json_value import is_json_value
from core.validation.boolean_coercion import coerce_bool_flag
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.direct_prepared_apply import async_apply_prepared_gpu_settings
from hardware.gpu_tuning.dirty_tracking import touch_dirty_flag_if_apply_changed
from hardware.gpu_tuning.gpu_settings import GpuSettingsApplyDependencies
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.slot_capabilities import (
    async_get_tuning_capabilities,
    snapshot_tuning_inventory,
)
from hardware.gpu_tuning.slot_errors import (
    apply_failed_error,
    device_missing_error,
    gpu_index_error,
)
from hardware.presets.slot_mutations import touch_dirty_flag
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("apply_gpu_settings_direct",)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.direct_apply"


async def apply_gpu_settings_direct(
    *,
    settings_deps: GpuSettingsApplyDependencies,
    dirty_flag_path: str,
    device_id: str,
    settings: JSONDict,
    capabilities_snapshot: JSONDict | None = None,
) -> JSONDict:
    deps = settings_deps
    if not isinstance(settings, dict) or not settings:
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload must be a non-empty mapping.",
            device_id=device_id,
        )
    capabilities = (
        capabilities_snapshot
        if isinstance(capabilities_snapshot, dict)
        else await async_get_tuning_capabilities(
            executor=deps.executor,
            gpu_services=deps.gpu_services,
            logger=deps.logger,
        )
    )

    def prepare_device(device_info: JSONDict, cap_entry: JSONDict) -> JSONDict:
        gpu_index = normalize_gpu_index(device_info.get("index"))
        if gpu_index is None:
            gpu_index = normalize_gpu_index(device_info.get("gpu_index"))
        if gpu_index is None:
            return gpu_index_error(device_id)
        try:
            sanitized = sanitize_settings(settings, cap_entry)
        except ValidationError as exception:
            return build_gpu_operation_error(
                "invalid_request_error",
                str(exception),
                device_id=device_id,
            )
        return {
            "success": True,
            "gpu_index": gpu_index,
            "device_info": device_info,
            "capabilities": cap_entry,
            "sanitized": sanitized,
        }

    def prepare() -> JSONDict:
        cap_entry = get_capabilities_for_device(capabilities, device_id, None)
        if isinstance(cap_entry, dict):
            prepared_from_caps = prepare_device(cap_entry, cap_entry)
            if prepared_from_caps.get("code") != "device_unavailable":
                return prepared_from_caps
        with deps.storage.lock:
            inventory = snapshot_tuning_inventory(
                executor=deps.executor,
                detailed_gpu_info=deps.detailed_gpu_info,
                gpu_services=deps.gpu_services,
            )
            if not (device_info := inventory.get(device_id)):
                return device_missing_error(device_id)
            if (gpu_index := normalize_gpu_index(device_info.get("gpu_index"))) is None:
                return gpu_index_error(device_id)
            cap_entry = get_capabilities_for_device(capabilities, device_id, gpu_index)
            if not isinstance(cap_entry, dict):
                cap_entry = {}
            return prepare_device(device_info, cap_entry)

    prepared = await asyncio.to_thread(prepare)
    if not is_success_result(
        prepared,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.direct_apply.is_success_result",
        recover_message="Failed to parse GPU operation success flag (non-critical).",
    ):
        return prepared
    prepared_gpu_index = prepared.get("gpu_index")
    if not isinstance(prepared_gpu_index, int):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid gpu_index.",
            device_id=device_id,
        )
    prepared_sanitized = prepared.get("sanitized")
    if not isinstance(prepared_sanitized, dict):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid sanitized settings.",
            device_id=device_id,
        )
    prepared_device_info = prepared.get("device_info")
    if not isinstance(prepared_device_info, dict):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid device info.",
            device_id=device_id,
        )
    prepared_capabilities = prepared.get("capabilities")
    if not isinstance(prepared_capabilities, dict):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid capabilities.",
            device_id=device_id,
        )
    apply_result = await async_apply_prepared_gpu_settings(
        settings_deps,
        device_id=device_id,
        gpu_index=prepared_gpu_index,
        device_info=prepared_device_info,
        capabilities=prepared_capabilities,
        settings=prepared_sanitized,
    )
    if not is_success_result(
        apply_result,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.direct_apply.is_success_result",
        recover_message="Failed to parse GPU operation success flag (non-critical).",
    ):
        await touch_dirty_flag_if_apply_changed(apply_result, dirty_flag_path, deps.logger)
        return apply_failed_error(device_id, details=apply_result)
    result_entry: JSONValue | None = None
    gpus_value = apply_result.get("gpus")
    if isinstance(gpus_value, Mapping):
        if str(prepared_gpu_index) in gpus_value:
            result_entry = gpus_value.get(str(prepared_gpu_index))
    if not coerce_bool_flag(
        apply_result.get("changed"),
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.direct_apply.changed",
        default=False,
        recover_message="Failed to parse boolean flag (non-critical).",
    ):
        return {
            "success": True,
            "device_id": device_id,
            "changed": False,
            "result": (result_entry if is_json_value(result_entry) else None),
        }
    applied_at = utc_now_iso()
    await asyncio.to_thread(
        touch_dirty_flag,
        dirty_flag_path=dirty_flag_path,
        logger=deps.logger,
    )
    return {
        "success": True,
        "device_id": device_id,
        "applied_at": applied_at,
        "changed": True,
        "result": (result_entry if is_json_value(result_entry) else None),
    }
