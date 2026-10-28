"""SoAI - Saved-slot intent bound to native receipt and atomic final commit [backend/hardware/gpu_tuning/slot_apply_async.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.hardware.gpu_control_operation_types import GPUControlCommitIntent
from core.logging.trace import get_logger
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
from core.types.json_value import is_json_value
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
from hardware.gpu_tuning.direct_apply import async_apply_prepared_gpu_settings
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.setting_modes import normalize_field_modes_for_settings
from hardware.gpu_tuning.slot_apply import sync_prepare_slot_apply
from hardware.gpu_tuning.slot_capabilities import async_get_tuning_capabilities
from hardware.gpu_tuning.slot_errors import apply_failed_error

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "LOGGER_NAME",
    "extract_gpu_result_entry",
    "async_execute_slot_apply",
)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.slot_apply_async"


def extract_gpu_result_entry(apply_result: JSONDict, gpu_index: int) -> JSONValue | None:
    gpus_value = apply_result.get("gpus")
    if not isinstance(gpus_value, Mapping):
        return None
    candidate = gpus_value.get(str(gpu_index))
    return candidate if is_json_value(candidate) else None


async def async_execute_slot_apply(
    *,
    settings_deps: GpuSettingsApplyDependencies,
    dirty_flag_path: str,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    device_id: str,
    slot: str | int,
    apply_at_boot: bool | None,
) -> JSONDict:
    deps = settings_deps
    delivery = deps.delivery_dependencies
    if (
        dirty_flag_path != deps.native_control_recovery.dependencies.dirty_flag_path
        or event_bus is not delivery.event_bus
        or main_loop is not delivery.main_loop
        or cancellation_binder is not delivery.cancellation_binder
        or finalizer_tracker is not delivery.finalizer_tracker
    ):
        raise ValidationError("GPU slot application must retain its concrete delivery authority.")
    prepared = await run_joined_thread_call(
        partial(
            sync_prepare_slot_apply,
            executor=deps.executor,
            storage=deps.storage,
            detailed_gpu_info=deps.detailed_gpu_info,
            device_id=device_id,
            slot=slot,
            apply_at_boot=apply_at_boot,
            gpu_services=deps.gpu_services,
        ),
        task_name=f"gpu-slot-preparation:{device_id}",
        retain_resources_until_complete=True,
    )
    if not is_success_result(
        prepared,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.slot_apply_async.is_success_result",
    ):
        return prepared
    slot_id, gpu_index, settings, device_info, signature, expected_digest = (
        prepared.get("slot_id"),
        prepared.get("gpu_index"),
        prepared.get("settings"),
        prepared.get("device_info"),
        prepared.get("signature"),
        prepared.get("expected_control_state_digest"),
    )
    if (
        not isinstance(slot_id, str)
        or not isinstance(gpu_index, int)
        or not isinstance(settings, dict)
        or not settings
    ):
        return apply_failed_error(device_id)
    if (
        not isinstance(device_info, dict)
        or not isinstance(signature, str)
        or not signature
        or not isinstance(expected_digest, str)
    ):
        return apply_failed_error(device_id)
    modes_value = prepared.get("field_modes")
    modes = normalize_field_modes_for_settings(
        settings, modes_value if isinstance(modes_value, dict) else None
    )
    apply_flag = prepared.get("apply_flag")
    if apply_flag is not None and not isinstance(apply_flag, bool):
        raise ValidationError("GPU slot preparation lost its validated boot policy.")
    capabilities = await async_get_tuning_capabilities(
        executor=deps.executor, gpu_services=deps.gpu_services, logger=deps.logger
    )
    caps = get_capabilities_for_device(capabilities, device_id, gpu_index, selected_gpu=device_info)
    grouped = group_settings_by_control_backend(
        build_apply_settings_for_modes(settings, modes), caps
    )
    user_fields = tuple(field for bucket in grouped.values() for field in bucket)
    intent = GPUControlCommitIntent(user_fields, expected_digest, slot_id, signature, apply_flag)
    result = await async_apply_prepared_gpu_settings(
        deps,
        device_id=device_id,
        gpu_index=gpu_index,
        device_info=device_info,
        capabilities=caps or {},
        settings=settings,
        field_modes=modes,
        commit_intent=intent,
    )
    if not is_success_result(
        result,
        logger=deps.logger,
        operation="hardware.gpu_tuning.slot_apply_async.finalization_result",
    ):
        if result.get("code") == "gpu_activity_conflict":
            return result
        failed = apply_failed_error(device_id, slot_id, result)
        if isinstance(result.get("changed"), bool):
            failed["changed"] = result["changed"]
        return failed
    payload: JSONDict = {
        "success": True,
        "device_id": device_id,
        "slot": slot_id,
        "result": extract_gpu_result_entry(result, gpu_index),
    }
    if isinstance(result.get("changed"), bool):
        payload["changed"] = result["changed"]
    applied_at = result.get("applied_at")
    if isinstance(applied_at, str):
        payload["applied_at"] = applied_at
    return payload
