"""SoAI - Async GPU slot application orchestration [backend/hardware/gpu_tuning/slot_apply_async.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.events.protocols import EventBusProtocol
from core.logging.trace import get_logger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.timing.formatting import utc_now_iso
from core.types.json_value import is_json_value
from core.validation.boolean_coercion import coerce_bool_flag
from hardware.gpu_tuning.dirty_tracking import touch_dirty_flag_if_apply_changed
from hardware.gpu_tuning.events import (
    emit_active_slot_event,
    emit_mutation_events,
)
from hardware.gpu_tuning.gpu_settings import (
    GpuSettingsApplyDependencies,
    async_set_gpu_settings,
)
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.slot_apply import (
    sync_finalize_slot_apply,
    sync_prepare_slot_apply,
)
from hardware.gpu_tuning.slot_errors import apply_failed_error, slot_unchanged_error
from hardware.operations import can_emit_events
from hardware.presets.slot_mutations import touch_dirty_flag

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "async_execute_slot_apply",
    "extract_gpu_result_entry",
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
    prepared = await asyncio.to_thread(
        sync_prepare_slot_apply,
        executor=deps.executor,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        device_id=device_id,
        slot=slot,
        apply_at_boot=apply_at_boot,
        gpu_services=deps.gpu_services,
    )
    if not is_success_result(
        prepared,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.slot_apply_async.is_success_result",
    ):
        return prepared
    if coerce_bool_flag(
        prepared.get("unchanged"),
        logger=deps.logger,
        operation="hardware.gpu_tuning.slot_apply_async.coerce_bool_flag",
        default=False,
        recover_message="Failed to parse boolean flag (non-critical).",
    ):
        slot_id_value = prepared.get("slot_id")
        slot_id = slot_id_value if isinstance(slot_id_value, str) else ""
        return slot_unchanged_error(
            device_id,
            slot_id,
            "Selected slot settings are already active.",
        )
    slot_id_value = prepared.get("slot_id")
    if not isinstance(slot_id_value, str) or not slot_id_value:
        return apply_failed_error(device_id)
    gpu_index_value = prepared.get("gpu_index")
    if not isinstance(gpu_index_value, int):
        return apply_failed_error(device_id, slot_id_value)
    settings_value = prepared.get("settings")
    if not isinstance(settings_value, dict):
        return apply_failed_error(device_id, slot_id_value)
    settings_payload: dict[str, JSONValue] = {
        key: value for key, value in settings_value.items() if isinstance(key, str)
    }
    if not settings_payload:
        return apply_failed_error(device_id, slot_id_value)
    field_modes_value = prepared.get("field_modes")
    field_modes_payload = field_modes_value if isinstance(field_modes_value, dict) else None
    apply_result = await async_set_gpu_settings(
        settings_deps,
        gpu_id=gpu_index_value,
        settings=settings_payload,
        field_modes=field_modes_payload,
    )
    if not is_success_result(
        apply_result,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.slot_apply_async.is_success_result",
    ):
        await touch_dirty_flag_if_apply_changed(apply_result, dirty_flag_path, deps.logger)
        return apply_failed_error(device_id, slot_id_value, apply_result)
    applied_at = utc_now_iso()
    signature_value = prepared.get("signature")
    if not isinstance(signature_value, str) or not signature_value:
        return apply_failed_error(device_id, slot_id_value)
    signature = signature_value
    apply_flag_value = prepared.get("apply_flag")
    apply_flag = apply_flag_value if isinstance(apply_flag_value, bool) else None
    finalize = await asyncio.to_thread(
        sync_finalize_slot_apply,
        executor=deps.executor,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        logger=deps.logger,
        device_id=device_id,
        slot_id=slot_id_value,
        signature=signature,
        apply_flag=apply_flag,
        applied_at=applied_at,
        gpu_services=deps.gpu_services,
    )
    entry_value = finalize.get("entry")
    entry_snapshot = entry_value if isinstance(entry_value, dict) else None
    if entry_snapshot and can_emit_events(event_bus, main_loop):
        emit_mutation_events(
            executor=deps.executor,
            event_bus=event_bus,
            main_loop=main_loop,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            logger=deps.logger,
            result=dict(finalize),
            emit_boot_on_success=False,
            gpu_services=deps.gpu_services,
        )
        emit_active_slot_event(
            event_bus=event_bus,
            main_loop=main_loop,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            logger=deps.logger,
            device_id=device_id,
            slot_id=slot_id_value,
            signature=signature,
            applied_at=applied_at,
        )
    payload: JSONDict = {
        "success": True,
        "device_id": device_id,
        "slot": slot_id_value,
        "applied_at": applied_at,
        "changed": True,
        "result": extract_gpu_result_entry(apply_result, gpu_index_value),
        "boot": entry_snapshot.get("boot") if entry_snapshot else None,
    }
    warning_value = finalize.get("warning")
    if isinstance(warning_value, str) and warning_value:
        payload["warning"] = warning_value
    await asyncio.to_thread(
        touch_dirty_flag,
        dirty_flag_path=dirty_flag_path,
        logger=deps.logger,
    )
    return payload
