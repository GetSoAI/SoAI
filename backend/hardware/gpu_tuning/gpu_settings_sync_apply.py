"""SoAI - GPU settings synchronous application flow [backend/hardware/gpu_tuning/gpu_settings_sync_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_operation_results import (
    build_gpu_operation_error,
    build_gpu_result,
)
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.control_backend_selection import (
    group_settings_by_control_backend,
)
from hardware.gpu_tuning.control_state_write_flow import (
    CONTROL_STATE_WRITE_ERROR,
    sync_write_requested_control_state,
)
from hardware.gpu_tuning.device_mode_storage import load_known_device_slot_state
from hardware.gpu_tuning.direct_control_state import control_state_matches
from hardware.gpu_tuning.effective_control_state import (
    build_apply_settings_for_modes,
    requested_applied_settings_for_modes,
    settings_requiring_effective_apply,
    settings_values_match_effective,
)
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.setting_modes import (
    derive_field_modes_from_settings,
    normalize_field_modes_for_settings,
)
from hardware.gpu_tuning.slot_capabilities import get_tuning_capabilities_for_services
from hardware.gpu_tuning.vendor_backend_apply import (
    apply_vendor_backend_settings,
    supports_vendor_backend_settings,
)
from hardware.info_gpu import get_gpu_info
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
    from hardware.vendors.nvidia.smi import NvidiaSettingsController

__all__ = ("sync_set_gpu_settings",)

OPERATION_HARDWARE_GPU_SETTINGS_PERSIST_CONTROL_STATE = (
    "hardware.gpu_settings.persist_control_state"
)
OPERATION_HARDWARE_GPU_SETTINGS_UPDATE_CONTROL_STATE = "hardware.gpu_settings.update_control_state"


def sync_set_gpu_settings(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    gpu_id: int | None = None,
    settings: JSONDict,
    field_modes: JSONDict | None = None,
) -> JSONDict:
    gpus_value = get_gpu_info(
        executor,
        detailed=False,
        cache_service=gpu_services.gpu_info_cache_service,
        vendor_detection_service=gpu_services.gpu_vendor_detection_service,
        nvidia_nvml_gate=gpu_services.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=gpu_services.nvidia_capabilities_cache_service,
    ).get("gpus")
    gpus_raw = gpus_value if isinstance(gpus_value, list) else []
    gpus = [gpu for gpu in gpus_raw if isinstance(gpu, dict)]
    if not gpus:
        return build_gpu_operation_error("no_gpus", "No GPUs found.")
    target_gpus = (
        gpus
        if gpu_id is None
        else [gpu for gpu in gpus if normalize_gpu_index(gpu.get("index")) == gpu_id]
    )
    if gpu_id is not None and (not target_gpus):
        return build_gpu_operation_error(
            "invalid_gpu_id",
            f"Invalid GPU ID {gpu_id}.",
            details={
                "valid_gpu_ids": [
                    gpu_index
                    for gpu in gpus
                    if (gpu_index := normalize_gpu_index(gpu.get("index"))) is not None
                ],
            },
            gpu_id=gpu_id,
        )
    if not settings:
        return build_gpu_operation_error("no_settings", "No GPU settings were provided.")
    capabilities = get_tuning_capabilities_for_services(
        executor=executor,
        gpu_services=gpu_services,
        logger=logger,
    )
    gpus_results: dict[str, JSONDict] = {}
    results: JSONDict = {"success": True, "gpus": gpus_results, "changed": False}
    overall_changed = False
    for gpu in target_gpus:
        index_key: str
        gpu_index = normalize_gpu_index(gpu.get("index"))
        device_id_value = gpu.get("device_id")
        device_id = device_id_value if isinstance(device_id_value, str) else None
        if gpu_index is not None:
            index_key = str(gpu_index)
        else:
            index_key = device_id or f"gpu:{len(gpus_results)}"
        cap_entry = get_capabilities_for_device(
            capabilities,
            device_id,
            gpu_index,
        )
        try:
            sanitized = sanitize_settings(settings, cap_entry)
        except ValidationError as error:
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(errors=[str(error)], changed=False)
            continue
        requested_field_modes = (
            normalize_field_modes_for_settings(sanitized, field_modes)
            if isinstance(field_modes, dict)
            else derive_field_modes_from_settings(sanitized)
        )
        try:
            apply_settings = build_apply_settings_for_modes(sanitized, requested_field_modes)
        except ValidationError as error:
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(errors=[str(error)], changed=False)
            continue
        requested_applied_settings = requested_applied_settings_for_modes(
            sanitized,
            requested_field_modes,
        )
        if not device_id:
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(
                errors=["GPU device_id is required to persist control modes."],
                changed=False,
            )
            continue
        device_entry = load_known_device_slot_state(
            storage=storage,
            device_id=device_id,
        )
        requested_control_state_active = control_state_matches(
            device_entry=device_entry,
            requested_settings=sanitized,
            requested_field_modes=requested_field_modes,
            requested_applied_settings=requested_applied_settings,
        )
        values_match_current = settings_values_match_effective(
            apply_settings,
            cap_entry,
            device_entry=device_entry,
            requested_field_modes=requested_field_modes,
        )
        if values_match_current and requested_control_state_active:
            logger.info(
                "%s settings already match requested values.",
                device_id or f"gpu:{index_key}",
            )
            gpus_results[index_key] = build_gpu_result(
                messages=["Requested settings already active."],
                changed=False,
            )
            continue
        if values_match_current:
            write_result = sync_write_requested_control_state(
                executor=executor,
                storage=storage,
                detailed_gpu_info=detailed_gpu_info,
                gpu_services=gpu_services,
                logger=logger,
                operation=OPERATION_HARDWARE_GPU_SETTINGS_PERSIST_CONTROL_STATE,
                device_id=device_id,
                field_modes=requested_field_modes,
                applied_settings=requested_applied_settings,
                current_device_info=gpu,
            )
            if write_result.changed:
                overall_changed = True
            if write_result.success:
                gpus_results[index_key] = write_result.gpu_result
                continue
            results["success"] = False
            gpus_results[index_key] = write_result.gpu_result
            continue
        settings_to_apply = settings_requiring_effective_apply(
            apply_settings,
            cap_entry,
            device_entry=device_entry,
            requested_field_modes=requested_field_modes,
        )
        try:
            grouped_settings = group_settings_by_control_backend(settings_to_apply, cap_entry)
        except ValidationError as error:
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(errors=[str(error)], changed=False)
            continue
        vendor_type = gpu.get("type")
        if not isinstance(vendor_type, str) or not supports_vendor_backend_settings(vendor_type):
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(errors=["Unknown GPU vendor"], changed=False)
            continue
        vendor_id = normalize_gpu_index(gpu.get("vendor_id"))
        if vendor_id is None:
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(
                errors=["Invalid GPU vendor id"],
                changed=False,
            )
            continue
        apply_result, backend_changed = apply_vendor_backend_settings(
            executor=executor,
            logger=logger,
            nvidia_settings_controller=nvidia_settings_controller,
            gpu_services=gpu_services,
            vendor_type=vendor_type,
            vendor_id=vendor_id,
            grouped_settings=grouped_settings,
            capabilities=cap_entry,
        )
        apply_errors = apply_result.get("errors")
        if not isinstance(apply_errors, list):
            results["success"] = False
            gpus_results[index_key] = build_gpu_result(
                errors=["GPU apply result payload is invalid."],
                changed=False,
            )
            continue
        successful_apply = not apply_errors
        if backend_changed:
            overall_changed = True
        if successful_apply:
            write_result = sync_write_requested_control_state(
                executor=executor,
                storage=storage,
                detailed_gpu_info=detailed_gpu_info,
                gpu_services=gpu_services,
                logger=logger,
                operation=OPERATION_HARDWARE_GPU_SETTINGS_UPDATE_CONTROL_STATE,
                device_id=device_id,
                field_modes=requested_field_modes,
                applied_settings=requested_applied_settings,
                current_device_info=gpu,
            )
            if write_result.changed:
                overall_changed = True
            if not write_result.success:
                results["success"] = False
                apply_result = build_gpu_result(
                    errors=[CONTROL_STATE_WRITE_ERROR],
                    changed=backend_changed,
                )
        else:
            results["success"] = False
        gpus_results[index_key] = apply_result
    results["changed"] = overall_changed
    if not overall_changed and is_success_result(
        results,
        logger=logger,
        operation="hardware.gpu_tuning.gpu_settings_sync_apply.is_success_result",
    ):
        results["message"] = "Settings already match current configuration."
    return results
