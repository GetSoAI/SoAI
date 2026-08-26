"""SoAI - GPU tuning startup application flow helpers [backend/hardware/gpu_tuning/startup_apply_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.files.operations import async_remove
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.timing.formatting import utc_now_iso
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_tuning.effective_control_state import (
    build_apply_settings_for_modes,
    control_state_active_for_request,
    settings_values_match_effective,
)
from hardware.gpu_tuning.event_publish import emit_gpu_startup_warning
from hardware.gpu_tuning.events import (
    SlotStateEventDependencies,
    emit_active_slot_event,
    emit_slot_and_boot_events_and_clear_active,
)
from hardware.gpu_tuning.gpu_settings import (
    GpuSettingsApplyDependencies,
    async_set_gpu_settings,
)
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.setting_modes import normalize_field_modes_for_settings
from hardware.gpu_tuning.startup import (
    sync_finalize_startup_apply,
    sync_handle_dirty_startup,
)
from hardware.gpu_tuning.startup_recovery_resets import apply_dirty_recovery_gpu_resets
from hardware.presets.slot_mutations import touch_dirty_flag

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "apply_dirty_startup_recovery",
    "apply_startup_instructions",
)

OPERATION = "hardware_presets.apply_startup_gpu_settings"


async def apply_dirty_startup_recovery(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    dirty_flag_path: str,
    slot_state_deps: SlotStateEventDependencies | None,
    settings_deps: GpuSettingsApplyDependencies,
) -> bool:
    logger = settings_deps.logger
    logger.critical(
        "Unclean shutdown detected. GPU settings are being reset to safe defaults and boot preferences will be disabled until reapplied.",
    )
    await apply_dirty_recovery_gpu_resets(
        settings_deps=settings_deps,
    )
    affected_entries: dict[str, JSONDict] = await asyncio.to_thread(
        sync_handle_dirty_startup,
        executor=settings_deps.executor,
        storage=settings_deps.storage,
        detailed_gpu_info=settings_deps.detailed_gpu_info,
        logger=logger,
        gpu_services=settings_deps.gpu_services,
    )
    try:
        await async_remove(dirty_flag_path)
    except OSError as error:
        log_exception(
            logger,
            error,
            message="Failed to clear GPU dirty flag after reset",
            operation=OPERATION,
            level="warning",
        )
    emit_slot_and_boot_events_and_clear_active(
        slot_state_deps,
        entries_by_device_id=affected_entries,
        cleared_device_ids=list(affected_entries.keys()),
    )
    emit_gpu_startup_warning(
        event_bus=event_bus,
        main_loop=main_loop,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
        device_ids=list(affected_entries.keys()),
    )
    return True


async def apply_startup_instructions(
    *,
    instructions: list[JSONDict],
    capabilities: JSONDict,
    settings_deps: GpuSettingsApplyDependencies,
    logger: TraceLogger,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    slot_state_deps: SlotStateEventDependencies | None,
    dirty_flag_path: str,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
) -> dict[str, JSONDict]:
    apply_results: list[JSONDict] = []
    dirty_required = False
    for instruction in instructions:
        device_id_value = instruction.get("device_id")
        gpu_index_value = instruction.get("gpu_index")
        slot_id_value = instruction.get("slot_id")
        settings_value = instruction.get("settings")
        field_modes_value = instruction.get("field_modes")
        current_field_modes_value = instruction.get("current_field_modes")
        applied_settings_value = instruction.get("applied_settings")
        signature_value = instruction.get("signature")
        if not (
            isinstance(device_id_value, str)
            and isinstance(gpu_index_value, int)
            and isinstance(slot_id_value, str)
            and isinstance(settings_value, dict)
            and isinstance(signature_value, str)
            and signature_value
        ):
            continue
        device_id = device_id_value
        gpu_index = gpu_index_value
        slot_id = slot_id_value
        settings = settings_value
        field_modes = field_modes_value if isinstance(field_modes_value, dict) else None
        current_field_modes = (
            current_field_modes_value if isinstance(current_field_modes_value, dict) else None
        )
        applied_settings = (
            applied_settings_value if isinstance(applied_settings_value, dict) else {}
        )
        signature = signature_value
        requested_field_modes = normalize_field_modes_for_settings(settings, field_modes)
        try:
            apply_settings = build_apply_settings_for_modes(settings, requested_field_modes)
        except ValidationError as error:
            log_exception(
                logger,
                error,
                message="Failed to normalize GPU startup slot settings.",
                operation=OPERATION,
                details={"slot_id": slot_id, "device_id": device_id},
            )
            continue
        device_entry: JSONDict = {
            "field_modes": current_field_modes or {},
            "applied_settings": applied_settings,
        }
        capabilities_entry = get_capabilities_for_device(capabilities, device_id, gpu_index)
        if control_state_active_for_request(
            device_entry=device_entry,
            settings=settings,
            requested_field_modes=requested_field_modes,
        ) and settings_values_match_effective(
            apply_settings,
            capabilities_entry,
            device_entry=device_entry,
            requested_field_modes=requested_field_modes,
        ):
            boot_state_value = instruction.get("boot_state")
            boot_state = boot_state_value if isinstance(boot_state_value, dict) else {}
            applied_at_value = boot_state.get("applied_at") or instruction.get("last_applied_at")
            existing_applied_at = applied_at_value if isinstance(applied_at_value, str) else None
            apply_results.append(
                {
                    "device_id": device_id,
                    "slot_id": slot_id,
                    "signature": signature,
                    "applied_at": None,
                    "boot_applied_at": existing_applied_at,
                },
            )
            if slot_state_deps is not None:
                emit_active_slot_event(
                    event_bus=event_bus,
                    main_loop=main_loop,
                    cancellation_binder=cancellation_binder,
                    finalizer_tracker=finalizer_tracker,
                    logger=logger,
                    device_id=device_id,
                    slot_id=slot_id,
                    signature=signature,
                    applied_at=existing_applied_at,
                )
            continue
        logger.trace("Applying GPU slot %s for %s during startup.", slot_id, device_id)
        try:
            result = await async_set_gpu_settings(
                settings_deps,
                gpu_id=gpu_index,
                settings=settings,
                field_modes=requested_field_modes,
            )
        except RECOVERABLE_EXCEPTIONS as error:
            log_exception(
                logger,
                error,
                message="Failed to apply GPU slot during startup",
                operation=OPERATION,
                details={"slot_id": slot_id, "device_id": device_id},
            )
            continue
        if not is_success_result(
            result,
            logger=logger,
            operation="hardware.gpu_tuning.startup_apply_flow.is_success_result",
        ):
            logger.warning("GPU slot %s for %s did not apply successfully.", slot_id, device_id)
            continue
        applied_at = utc_now_iso()
        apply_results.append(
            {
                "device_id": device_id,
                "slot_id": slot_id,
                "signature": signature,
                "applied_at": applied_at,
            },
        )
        dirty_required = True
        if slot_state_deps is not None:
            emit_active_slot_event(
                event_bus=event_bus,
                main_loop=main_loop,
                cancellation_binder=cancellation_binder,
                finalizer_tracker=finalizer_tracker,
                logger=logger,
                device_id=device_id,
                slot_id=slot_id,
                signature=signature,
                applied_at=applied_at,
            )
    updated_entries: dict[str, JSONDict] = {}
    if apply_results:
        updated_entries = await asyncio.to_thread(
            sync_finalize_startup_apply,
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            logger=logger,
            results=apply_results,
            gpu_services=gpu_services,
        )
    if dirty_required:
        await asyncio.to_thread(touch_dirty_flag, dirty_flag_path=dirty_flag_path, logger=logger)
    return updated_entries
