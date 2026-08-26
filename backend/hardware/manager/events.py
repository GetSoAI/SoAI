"""SoAI - Hardware manager event publication helpers [backend/hardware/manager/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.protocols import EventBusProtocol
from core.events.types_system import GPUCapabilitiesChangedEvent
from core.logging.protocols import TraceLogger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from hardware.operations import schedule_event_bus_publish

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("schedule_gpu_capabilities_changed_event",)


def schedule_gpu_capabilities_changed_event(
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    capabilities: JSONDict,
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
) -> None:
    if main_loop is None:
        return
    event = GPUCapabilitiesChangedEvent(capabilities=capabilities)
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label="gpu-capabilities",
        owner_prefix="hardware-manager",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )
