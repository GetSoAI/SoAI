"""SoAI - Application runtime foundation service assembly [backend/app/composition/build_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.application_dependencies import (
    ApplicationLifecycleModuleDependencies,
    ApplicationLogging,
    ApplicationMetadata,
)
from app.composition.build_cancellation_system import (
    CancellationSystem,
    build_cancellation_system,
)
from app.lifecycle.coordinator import (
    LifecycleCoordinator,
    LifecycleCoordinatorDependencies,
)
from app.lifecycle.discovery import DiscoveryServer, DiscoveryServerDependencies
from core.logging.protocols import LoggerProtocol
from core.runtime.state_store import RuntimeStateStore

__all__ = (
    "RuntimeFoundation",
    "build_discovery_service",
    "build_lifecycle_coordinator",
    "build_logging_instance",
    "build_runtime_foundation",
    "build_runtime_state",
)


@dataclass(slots=True, frozen=True)
class RuntimeFoundation:
    runtime_state: RuntimeStateStore
    logging_instance: ApplicationLogging
    metadata: ApplicationMetadata
    cancellation_system: CancellationSystem
    lifecycle_coordinator: LifecycleCoordinator
    discovery_service: DiscoveryServer


def build_runtime_state(
    *,
    stop_event: asyncio.Event,
) -> RuntimeStateStore:
    return RuntimeStateStore(
        startup_time=time.monotonic(),
        system_stop_event=stop_event,
        restart_pending=asyncio.Event(),
        startup_ready_event=asyncio.Event(),
        shutdown_event=asyncio.Event(),
        hardware_manager_available=True,
        async_loop=asyncio.get_running_loop(),
    )


def build_logging_instance(
    *,
    application_logger: LoggerProtocol,
    bootstrap_logger: LoggerProtocol,
    lifecycle_logger: LoggerProtocol,
    gui_status: Callable[[str], None],
) -> ApplicationLogging:
    return ApplicationLogging(
        logger=application_logger,
        bootstrap_logger=bootstrap_logger,
        lifecycle_logger=lifecycle_logger,
        gui_status=gui_status,
        banner_system=None,
    )


def build_lifecycle_coordinator(
    *,
    application_logger: LoggerProtocol,
    module_dependencies: ApplicationLifecycleModuleDependencies,
) -> LifecycleCoordinator:
    return LifecycleCoordinator(
        LifecycleCoordinatorDependencies(
            logger=application_logger,
            module_dependencies=module_dependencies,
        ),
    )


def build_discovery_service(
    *,
    application_logger: LoggerProtocol,
    cancellation_system: CancellationSystem,
    module_dependencies: ApplicationLifecycleModuleDependencies,
) -> DiscoveryServer:
    return DiscoveryServer(
        DiscoveryServerDependencies(
            logger_supplier=lambda: application_logger,
            token_collection=cancellation_system.token_collection,
            cancellation_history=cancellation_system.history,
            cancellation_event_bus=cancellation_system.event_bus,
            cancellation_binder=cancellation_system.binder,
            finalizer_tracker=cancellation_system.finalizer_tracker,
            module_dependencies=module_dependencies,
        ),
    )


def build_runtime_foundation(
    *,
    stop_event: asyncio.Event,
    version: str,
    application_logger: LoggerProtocol,
    bootstrap_logger: LoggerProtocol,
    lifecycle_logger: LoggerProtocol,
    gui_status: Callable[[str], None],
    module_dependencies: ApplicationLifecycleModuleDependencies,
) -> RuntimeFoundation:
    runtime_state = build_runtime_state(
        stop_event=stop_event,
    )
    logging_instance = build_logging_instance(
        application_logger=application_logger,
        bootstrap_logger=bootstrap_logger,
        lifecycle_logger=lifecycle_logger,
        gui_status=gui_status,
    )
    metadata = ApplicationMetadata(version=version)
    cancellation_system = build_cancellation_system(logger=application_logger)
    lifecycle_coordinator = build_lifecycle_coordinator(
        application_logger=application_logger,
        module_dependencies=module_dependencies,
    )
    discovery_service = build_discovery_service(
        application_logger=application_logger,
        cancellation_system=cancellation_system,
        module_dependencies=module_dependencies,
    )
    return RuntimeFoundation(
        runtime_state=runtime_state,
        logging_instance=logging_instance,
        metadata=metadata,
        cancellation_system=cancellation_system,
        lifecycle_coordinator=lifecycle_coordinator,
        discovery_service=discovery_service,
    )
