"""SoAI - Prepared single-GPU direct tuning application [backend/hardware/gpu_tuning/direct_prepared_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_operation_results import build_gpu_result
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.control_state_write_flow import (
    CONTROL_STATE_WRITE_ERROR,
    sync_write_requested_control_state,
)
from hardware.gpu_tuning.device_mode_storage import load_known_device_slot_state
from hardware.gpu_tuning.effective_control_state import (
    build_apply_settings_for_modes,
    control_state_active_for_request,
    requested_applied_settings_for_modes,
    settings_requiring_effective_apply,
    settings_values_match_effective,
)
from hardware.gpu_tuning.setting_modes import derive_field_modes_from_settings
from hardware.gpu_tuning.vendor_backend_apply import (
    apply_vendor_backend_settings,
    supports_vendor_backend_settings,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.gpu_tuning.gpu_settings import GpuSettingsApplyDependencies

__all__ = ("async_apply_prepared_gpu_settings",)

OPERATION_HARDWARE_GPU_SETTINGS_UPDATE_CONTROL_STATE = "hardware.gpu_settings.update_control_state"


async def async_apply_prepared_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    *,
    device_id: str,
    gpu_index: int,
    device_info: JSONDict,
    capabilities: JSONDict,
    settings: JSONDict,
) -> JSONDict:
    return await asyncio.to_thread(
        sync_apply_prepared_gpu_settings,
        deps,
        device_id=device_id,
        gpu_index=gpu_index,
        device_info=device_info,
        capabilities=capabilities,
        settings=settings,
    )


def sync_apply_prepared_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    *,
    device_id: str,
    gpu_index: int,
    device_info: JSONDict,
    capabilities: JSONDict,
    settings: JSONDict,
) -> JSONDict:
    requested_field_modes = derive_field_modes_from_settings(settings)
    try:
        apply_settings = build_apply_settings_for_modes(settings, requested_field_modes)
    except ValidationError as error:
        return _single_gpu_result(gpu_index, build_gpu_result(errors=[str(error)], changed=False))
    requested_applied_settings = requested_applied_settings_for_modes(
        settings,
        requested_field_modes,
    )
    device_entry = load_known_device_slot_state(
        storage=deps.storage,
        device_id=device_id,
    )
    values_match_current = settings_values_match_effective(
        apply_settings,
        capabilities,
        device_entry=device_entry,
        requested_field_modes=requested_field_modes,
    )
    control_state_active = control_state_active_for_request(
        device_entry=device_entry,
        settings=settings,
        requested_field_modes=requested_field_modes,
    )
    if values_match_current and control_state_active:
        return _single_gpu_result(
            gpu_index,
            build_gpu_result(messages=["Requested settings already active."], changed=False),
        )
    if values_match_current:
        write_result = sync_write_requested_control_state(
            executor=deps.executor,
            storage=deps.storage,
            detailed_gpu_info=deps.detailed_gpu_info,
            gpu_services=deps.gpu_services,
            logger=deps.logger,
            operation=OPERATION_HARDWARE_GPU_SETTINGS_UPDATE_CONTROL_STATE,
            device_id=device_id,
            field_modes=requested_field_modes,
            applied_settings=requested_applied_settings,
            current_device_info=device_info,
        )
        if not write_result.success:
            return _single_gpu_result(
                gpu_index,
                build_gpu_result(errors=[CONTROL_STATE_WRITE_ERROR], changed=False),
            )
        return _single_gpu_result(gpu_index, write_result.gpu_result, changed=write_result.changed)
    settings_to_apply = settings_requiring_effective_apply(
        apply_settings,
        capabilities,
        device_entry=device_entry,
        requested_field_modes=requested_field_modes,
    )
    try:
        grouped_settings = group_settings_by_control_backend(settings_to_apply, capabilities)
    except ValidationError as error:
        return _single_gpu_result(gpu_index, build_gpu_result(errors=[str(error)], changed=False))
    vendor_type = capabilities.get("type")
    if not isinstance(vendor_type, str):
        vendor_type = capabilities.get("vendor")
    if not isinstance(vendor_type, str):
        vendor_type = device_info.get("type")
    if not isinstance(vendor_type, str):
        vendor_type = device_info.get("vendor")
    if not isinstance(vendor_type, str) or not supports_vendor_backend_settings(vendor_type):
        return _single_gpu_result(gpu_index, build_gpu_result(errors=["Unknown GPU vendor"]))
    vendor_id = normalize_gpu_index(capabilities.get("vendor_id"))
    if vendor_id is None:
        vendor_id = normalize_gpu_index(device_info.get("vendor_id"))
    if vendor_id is None:
        return _single_gpu_result(gpu_index, build_gpu_result(errors=["Invalid GPU vendor id"]))
    apply_result, backend_changed = apply_vendor_backend_settings(
        executor=deps.executor,
        logger=deps.logger,
        nvidia_settings_controller=deps.nvidia_settings_controller,
        gpu_services=deps.gpu_services,
        vendor_type=vendor_type,
        vendor_id=vendor_id,
        grouped_settings=grouped_settings,
        capabilities=capabilities,
    )
    if _has_apply_errors(apply_result):
        return _single_gpu_result(gpu_index, apply_result, changed=backend_changed)
    write_result = sync_write_requested_control_state(
        executor=deps.executor,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        gpu_services=deps.gpu_services,
        logger=deps.logger,
        operation=OPERATION_HARDWARE_GPU_SETTINGS_UPDATE_CONTROL_STATE,
        device_id=device_id,
        field_modes=requested_field_modes,
        applied_settings=requested_applied_settings,
        current_device_info=device_info,
    )
    if not write_result.success:
        return _single_gpu_result(
            gpu_index,
            build_gpu_result(errors=[CONTROL_STATE_WRITE_ERROR], changed=backend_changed),
            changed=backend_changed,
        )
    changed = backend_changed or write_result.changed
    return _single_gpu_result(gpu_index, apply_result, changed=changed)


def _has_apply_errors(result: JSONDict) -> bool:
    errors = result.get("errors")
    return not isinstance(errors, list) or bool(errors)


def _single_gpu_result(
    gpu_index: int,
    gpu_result: JSONDict,
    *,
    changed: bool | None = None,
) -> JSONDict:
    parsed_changed = changed if changed is not None else gpu_result.get("changed") is True
    return {
        "success": not _has_apply_errors(gpu_result),
        "gpus": {str(gpu_index): gpu_result},
        "changed": parsed_changed,
    }
