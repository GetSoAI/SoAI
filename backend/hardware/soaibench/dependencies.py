"""SoAI - SoAIBench service dependencies [backend/hardware/soaibench/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols import (
        HardwareManagerProtocol,
    )
    from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskRegistryProtocol,
    )
    from hardware.soaibench.internal_protocols import SoAIBenchPublicationProtocol
    from hardware.soaibench.opencl_pool import SoAIBenchOpenCLPool

__all__ = ("SoAIBenchServiceDependencies",)


@dataclass(frozen=True, slots=True)
class SoAIBenchServiceDependencies:
    hardware_manager: HardwareManagerProtocol
    database_hardware: DatabaseSoAIBenchProtocol
    task_registry: TaskRegistryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    event_bus: EventBusProtocol
    activity_registry: HardwareActivityRegistryProtocol
    opencl_pool: SoAIBenchOpenCLPool
    shutdown_event: asyncio.Event
    logger: LoggerProtocol
    publication_service: SoAIBenchPublicationProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SoAIBenchServiceDependencies",
            activity_registry=self.activity_registry,
            cancellation_binder=self.cancellation_binder,
            database_hardware=self.database_hardware,
            event_bus=self.event_bus,
            hardware_manager=self.hardware_manager,
            logger=self.logger,
            opencl_pool=self.opencl_pool,
            publication_service=self.publication_service,
            shutdown_event=self.shutdown_event,
            task_registry=self.task_registry,
        )
