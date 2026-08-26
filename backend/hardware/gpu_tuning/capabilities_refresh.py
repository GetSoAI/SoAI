"""SoAI - Post-tuning GPU capability refresh [backend/hardware/gpu_tuning/capabilities_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.threading_async import run_sync_in_daemon_thread
from core.errors.exceptions import SoAIError
from hardware.gpu_tuning.slot_capabilities import get_tuning_capabilities_for_services
from hardware.manager.events import schedule_gpu_capabilities_changed_event

if TYPE_CHECKING:
    import asyncio

    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies

__all__ = ("refresh_capabilities_after_settings_change",)


async def refresh_capabilities_after_settings_change(
    *,
    executor: CommandExecutorProtocol,
    gpu_services: GpuServiceDependencies,
    enrich_gpu_capabilities: Callable[[JSONDict], JSONDict],
    event_bus: EventBusProtocol,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    probe_timeout_seconds: float,
) -> bool:
    def sync_compute() -> JSONDict:
        raw = get_tuning_capabilities_for_services(
            executor=executor,
            gpu_services=gpu_services,
            logger=logger,
        )
        return enrich_gpu_capabilities(raw)

    try:
        new_caps = await run_sync_in_daemon_thread(
            sync_compute,
            timeout=probe_timeout_seconds,
            thread_name="soai-gpu-tuning-capabilities-refresh",
            logger=logger,
            operation="hardware_gpu_tuning.refresh_capabilities_after_settings_change",
            log_message="Failed to refresh GPU capabilities after settings update (non-critical).",
            log_level="warning",
        )
    except TimeoutError:
        logger.warning("Timed out while probing GPU capabilities after settings update.")
        return False
    except SoAIError:
        return False
    schedule_gpu_capabilities_changed_event(
        event_bus,
        main_loop,
        new_caps,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )
    return True
