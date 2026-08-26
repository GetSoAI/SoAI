"""SoAI - GPU tuning event publish helpers [backend/hardware/gpu_tuning/event_publish.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Sequence

from core.events.protocols import EventBusProtocol
from core.events.types_system import (
    GPUActiveSlotChangedEvent,
    GPUBootPreferenceChangedEvent,
    GPUStartupWarningEvent,
)
from core.logging.protocols import TraceLogger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.types.json import JSONDict
from hardware.operations import can_emit_events, schedule_event_bus_publish

__all__ = (
    "emit_active_slot_event",
    "emit_boot_preference_event",
    "emit_gpu_startup_warning",
)


def emit_active_slot_event(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    device_id: str,
    slot_id: str | None,
    signature: str | None,
    applied_at: str | None,
) -> None:
    if not can_emit_events(event_bus, main_loop):
        return
    if event_bus is None or main_loop is None:
        return
    event = GPUActiveSlotChangedEvent(
        device_id=device_id,
        slot=slot_id,
        signature=signature,
        applied_at=applied_at,
    )
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label=f"gpu-active-slot-{device_id}",
        owner_prefix="hardware-presets",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )


def emit_boot_preference_event(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    device_id: str,
    boot_payload: JSONDict,
) -> None:
    if not can_emit_events(event_bus, main_loop):
        return
    if event_bus is None or main_loop is None:
        return
    event = GPUBootPreferenceChangedEvent(device_id=device_id, boot=copy.deepcopy(boot_payload))
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label=f"gpu-boot-pref-{device_id}",
        owner_prefix="hardware-presets",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )


def emit_gpu_startup_warning(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    device_ids: Sequence[str],
) -> None:
    if not can_emit_events(event_bus, main_loop):
        return
    if event_bus is None or main_loop is None:
        return
    message = "GPU boot preferences were disabled after an unsafe shutdown. Reapply slot settings to restore automatic startup."
    event = GPUStartupWarningEvent(device_ids=list(device_ids), message=message)
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label="gpu-startup-warning",
        owner_prefix="hardware-presets",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )
