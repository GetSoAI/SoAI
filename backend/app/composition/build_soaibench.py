"""SoAI - SoAIBench service composition [backend/app/composition/build_soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

import httpx2

from core.events.protocols import EventBusProtocol
from core.hardware.protocols import HardwareManagerProtocol
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
from core.logging.trace import get_logger
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
from hardware.soaibench.opencl_pool import SoAIBenchOpenCLPool
from hardware.soaibench.publication_service import (
    SoAIBenchPublicationService,
    SoAIBenchPublicationServiceDependencies,
)
from hardware.soaibench.service import SoAIBenchService

__all__ = ("build_soaibench_service",)

SOAIBENCH_LOGGER_NAME = "SoAI.hardware.soaibench"


def build_soaibench_service(
    *,
    hardware_manager: HardwareManagerProtocol,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    event_bus: EventBusProtocol,
    activity_registry: HardwareActivityRegistryProtocol,
    shutdown_event: asyncio.Event,
    http_client: httpx2.AsyncClient,
) -> SoAIBenchService:
    logger = get_logger(SOAIBENCH_LOGGER_NAME)
    publication_service = SoAIBenchPublicationService(
        SoAIBenchPublicationServiceDependencies(
            database_hardware=database_hardware,
            http_client=http_client,
            logger=logger,
        )
    )
    return SoAIBenchService(
        SoAIBenchServiceDependencies(
            hardware_manager=hardware_manager,
            database_hardware=database_hardware,
            task_registry=task_registry,
            cancellation_binder=cancellation_binder,
            event_bus=event_bus,
            activity_registry=activity_registry,
            opencl_pool=SoAIBenchOpenCLPool(logger),
            shutdown_event=shutdown_event,
            logger=logger,
            publication_service=publication_service,
        ),
    )
