"""SoAI - SoAIBench service composition [backend/app/composition/build_soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

import httpx2

from core.concurrency.bounded_blocking import create_bounded_thread_pool
from core.events.protocols import EventBusProtocol
from core.hardware.protocols import GPURecoveryAdmissionProtocol, HardwareManagerProtocol
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
from core.hardware.soaibench_limits import MAX_CHILD_MESSAGE_BYTES
from core.ipc.multiplexed import MultiplexedIpcServer
from core.ipc.ndjson import NdjsonCodec
from core.logging.trace import get_logger
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
from hardware.soaibench.opencl_pool import (
    OPENCL_POOL_MAX_IN_FLIGHT,
    SoAIBenchOpenCLPool,
    SoAIBenchOpenCLPoolDependencies,
)
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
    recovery_admission: GPURecoveryAdmissionProtocol,
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
            recovery_admission=recovery_admission,
            database_hardware=database_hardware,
            task_registry=task_registry,
            cancellation_binder=cancellation_binder,
            event_bus=event_bus,
            activity_registry=activity_registry,
            opencl_pool=SoAIBenchOpenCLPool(
                SoAIBenchOpenCLPoolDependencies(
                    logger=logger,
                    server=MultiplexedIpcServer(
                        encoding_pool=create_bounded_thread_pool(
                            label="soaibench-ipc",
                            thread_name_prefix="soaibench-ipc",
                            max_workers=2,
                            max_in_flight=2,
                        ),
                        codec=NdjsonCodec(
                            max_line_bytes=MAX_CHILD_MESSAGE_BYTES,
                            max_depth=32,
                            reject_duplicate_keys=True,
                        ),
                    ),
                    numerical_validation_pool=create_bounded_thread_pool(
                        label="soaibench-numerical-validation",
                        thread_name_prefix="soaibench-numerical",
                        max_workers=2,
                        max_in_flight=2,
                    ),
                    cleanup_pool=create_bounded_thread_pool(
                        label="soaibench-child-cleanup",
                        thread_name_prefix="soaibench-cleanup",
                        max_workers=OPENCL_POOL_MAX_IN_FLIGHT,
                        max_in_flight=OPENCL_POOL_MAX_IN_FLIGHT,
                    ),
                )
            ),
            shutdown_event=shutdown_event,
            logger=logger,
            publication_service=publication_service,
            telemetry_pool=create_bounded_thread_pool(
                label="soaibench-telemetry",
                thread_name_prefix="soaibench-telemetry",
                max_workers=OPENCL_POOL_MAX_IN_FLIGHT,
                max_in_flight=OPENCL_POOL_MAX_IN_FLIGHT,
            ),
        ),
    )
