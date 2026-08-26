"""SoAI - SoAIBench service composition [backend/app/composition/build_soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.bounded_process import create_bounded_process_pool
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import HardwareManagerProtocol
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
from core.logging.trace import get_logger
from core.runtime.opencl_environment import configure_opencl_runtime_environment
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
from hardware.soaibench.opencl_pool import (
    OPENCL_POOL_MAX_IN_FLIGHT,
    OPENCL_POOL_MAX_WORKERS,
    SoAIBenchOpenCLPool,
)
from hardware.soaibench.service import SoAIBenchService

__all__ = ("build_soaibench_service",)

SOAIBENCH_LOGGER_NAME = "SoAI.hardware.soaibench"


def create_soaibench_opencl_pool() -> BoundedBlockingPool:
    process_executor = ProcessPoolExecutor(
        max_workers=OPENCL_POOL_MAX_WORKERS,
        initializer=configure_opencl_runtime_environment,
        max_tasks_per_child=1,
    )
    return create_bounded_process_pool(
        executor=process_executor,
        label="soaibench_opencl",
        max_workers=OPENCL_POOL_MAX_WORKERS,
        max_in_flight=OPENCL_POOL_MAX_IN_FLIGHT,
    )


def build_soaibench_service(
    *,
    hardware_manager: HardwareManagerProtocol,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    event_bus: EventBusProtocol,
    activity_registry: HardwareActivityRegistryProtocol,
    shutdown_event: asyncio.Event,
) -> SoAIBenchService:
    logger = get_logger(SOAIBENCH_LOGGER_NAME)
    return SoAIBenchService(
        SoAIBenchServiceDependencies(
            hardware_manager=hardware_manager,
            database_hardware=database_hardware,
            task_registry=task_registry,
            cancellation_binder=cancellation_binder,
            event_bus=event_bus,
            activity_registry=activity_registry,
            opencl_pool=SoAIBenchOpenCLPool(logger, create_soaibench_opencl_pool),
            shutdown_event=shutdown_event,
            logger=logger,
        ),
    )
