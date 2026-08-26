"""SoAI - Hardware operation utilities [backend/hardware/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "can_emit_events",
    "create_device_id",
    "schedule_event_bus_publish",
    "sum_vram_gb",
)

OPERATION_HARDWARE_OPERATIONS_DISPATCH_EVENT = "hardware.operations.dispatch_event"
OPERATION_HARDWARE_OPERATIONS_SCHEDULE_EVENT_BUS_PUBLISH = (
    "hardware.operations.schedule_event_bus_publish"
)


def create_device_id(prefix: str, primary: str | float | None) -> str:
    if primary is None:
        raise ValidationError(f"{prefix} device identifier is missing.")
    token = str(primary).strip()
    if not token:
        raise ValidationError(f"{prefix} device identifier is empty.")
    return f"{prefix}:{token.lower()}"


def sum_vram_gb(gpu_info: JSONDict | None) -> float:
    if not isinstance(gpu_info, dict):
        return 0.0
    gpus = gpu_info.get("gpus")
    if not isinstance(gpus, list):
        return 0.0
    total_mb = 0.0
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        memory_total = gpu.get("memory_total_mb", 0)
        if isinstance(memory_total, int | float) and math.isfinite(memory_total):
            total_mb += float(memory_total)
    return round(total_mb / 1024, 2)


def can_emit_events(
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
) -> bool:
    return bool(event_bus and main_loop and (not main_loop.is_closed()))


def schedule_event_bus_publish(
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop,
    event: Event,
    label: str,
    owner_prefix: str,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: LoggerProtocol | None = None,
) -> None:
    if event_bus is None or main_loop is None or main_loop.is_closed():
        return
    if cancellation_binder is None or finalizer_tracker is None:
        raise ValidationError(
            "schedule_event_bus_publish requires cancellation binder dependencies.",
        )

    def _dispatch_event() -> None:
        try:
            _ = spawn_tracked_task(
                event_bus.publish(event),
                name=f"{owner_prefix}-event-{label}",
                logger=logger,
                cancellation_id=create_system_id(
                    subsystem=f"{owner_prefix}_event",
                    owner=label,
                    include_random_suffix=True,
                ),
                owner=f"{owner_prefix}_event",
                metadata={"event": type(event).__name__},
                cancellation_binder=cancellation_binder,
                finalizer_tracker=finalizer_tracker,
            )
        except (
            RuntimeError,
            TypeError,
            ValidationError,
        ) as exception:
            if logger:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to dispatch hardware event {type(event).__name__}",
                    operation=OPERATION_HARDWARE_OPERATIONS_DISPATCH_EVENT,
                    details={"event_type": type(event).__name__},
                )

    try:
        main_loop.call_soon_threadsafe(_dispatch_event)
    except RuntimeError as exception:
        if logger:
            log_exception(
                logger,
                exception,
                message=f"Failed to dispatch hardware event {type(event).__name__}",
                operation=OPERATION_HARDWARE_OPERATIONS_SCHEDULE_EVENT_BUS_PUBLISH,
                details={"event_type": type(event).__name__},
            )
