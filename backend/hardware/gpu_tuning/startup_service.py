"""SoAI - GPU tuning boot preference application at startup [backend/hardware/gpu_tuning/startup_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.protocols import EventBusProtocol
from core.filesystem.async_queries import async_path_exists
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from hardware.gpu_tuning.events import (
    build_slot_state_event_dependencies_or_none,
    emit_slot_and_boot_events_and_clear_active,
)
from hardware.gpu_tuning.gpu_settings import GpuSettingsApplyDependencies
from hardware.gpu_tuning.slot_capabilities import async_get_tuning_capabilities
from hardware.gpu_tuning.startup import (
    sync_collect_startup_apply_targets,
)
from hardware.gpu_tuning.startup_apply_flow import (
    apply_dirty_startup_recovery,
    apply_startup_instructions,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("apply_startup_gpu_settings",)


async def apply_startup_gpu_settings(
    *,
    settings_deps: GpuSettingsApplyDependencies,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    dirty_flag_path: str,
) -> None:
    deps = settings_deps
    deps.logger.trace("Preparing GPU slot boot preferences for startup.")
    slot_state_deps = build_slot_state_event_dependencies_or_none(
        deps.executor,
        event_bus,
        main_loop,
        cancellation_binder,
        finalizer_tracker,
        deps.logger,
        deps.gpu_services,
    )
    if await async_path_exists(dirty_flag_path):
        handled_dirty_startup = await apply_dirty_startup_recovery(
            event_bus=event_bus,
            main_loop=main_loop,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            dirty_flag_path=dirty_flag_path,
            slot_state_deps=slot_state_deps,
            settings_deps=settings_deps,
        )
        if handled_dirty_startup:
            return
    preparation: JSONDict = await asyncio.to_thread(
        sync_collect_startup_apply_targets,
        executor=deps.executor,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        logger=deps.logger,
        gpu_services=deps.gpu_services,
    )
    instructions_raw = preparation.get("instructions", [])
    instructions = (
        [entry for entry in instructions_raw if isinstance(entry, dict)]
        if isinstance(instructions_raw, list)
        else []
    )
    snapshots_raw = preparation.get("snapshots", {})
    snapshots: dict[str, JSONDict] = (
        {
            device_id: entry
            for device_id, entry in snapshots_raw.items()
            if isinstance(device_id, str) and isinstance(entry, dict)
        }
        if isinstance(snapshots_raw, dict)
        else {}
    )
    disabled_devices_raw = preparation.get("disabled_devices", [])
    disabled_devices = (
        [device_id for device_id in disabled_devices_raw if isinstance(device_id, str)]
        if isinstance(disabled_devices_raw, list)
        else []
    )
    emit_slot_and_boot_events_and_clear_active(
        slot_state_deps,
        entries_by_device_id=snapshots,
        cleared_device_ids=disabled_devices,
    )
    if not instructions:
        deps.logger.trace("No GPU slot boot preferences require startup application.")
        return
    capabilities = await async_get_tuning_capabilities(
        executor=deps.executor,
        gpu_services=deps.gpu_services,
        logger=deps.logger,
    )
    updated_entries = await apply_startup_instructions(
        instructions=instructions,
        capabilities=capabilities,
        settings_deps=settings_deps,
        logger=deps.logger,
        event_bus=event_bus,
        main_loop=main_loop,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        slot_state_deps=slot_state_deps,
        dirty_flag_path=dirty_flag_path,
        executor=deps.executor,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        gpu_services=deps.gpu_services,
    )
    if updated_entries:
        emit_slot_and_boot_events_and_clear_active(
            slot_state_deps,
            entries_by_device_id=updated_entries,
            cleared_device_ids=(),
        )
