"""SoAI - Core bootstrap stage for application assembly [backend/app/composition/build_application_bootstrap_core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from app.application_dependencies import (
    ApplicationEnvironment,
    ApplicationLogging,
    ApplicationModuleDependencies,
)
from app.bootstrap import apply_cancellation_system_settings
from app.composition.build_config import (
    ConfigurationFoundation,
    build_configuration_foundation,
)
from app.composition.build_core_configuration import (
    ensure_base_path_correct,
    validate_environment,
)
from app.composition.build_core_services import build_event_bus, ensure_banner_system
from app.composition.build_runtime import RuntimeFoundation, build_runtime_foundation
from app.edition_composition import EditionComposition
from app.lifecycle.budgets import resolve_lifecycle_shutdown_budgets
from app.lifecycle.entries import LifecycleEntry
from app.lifecycle.runner import LifecycleRunner
from app.system_restart_requester import (
    SystemRestartRequester,
    SystemRestartRequesterDependencies,
)
from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.bus import EventBus
from core.hardware.speed_test.disk_service import (
    DiskSpeedTestService,
    DiskSpeedTestServiceDependencies,
)
from core.hardware.speed_test.network_service import (
    NetworkSpeedTestService,
    NetworkSpeedTestServiceDependencies,
)
from core.logging.manager import LoggingManager, LoggingManagerDependencies
from core.logging.protocols import LoggerProtocol
from core.state.restart_manager import (
    RestartStateManager,
    RestartStateManagerDependencies,
)
from core.tasks.routing_service import (
    TaskTypeRoutingService,
    TaskTypeRoutingServiceDependencies,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "CoreBootstrapStage",
    "build_core_bootstrap_stage",
)


@dataclass(slots=True, frozen=True)
class CoreBootstrapStage:
    runtime_foundation: RuntimeFoundation
    configuration_foundation: ConfigurationFoundation
    task_type_routing_service: TaskTypeRoutingService
    event_bus: EventBus
    log_manager: LoggingManager
    logging_instance: ApplicationLogging
    restart_state_manager: RestartStateManager
    disk_speed_test_service: DiskSpeedTestService
    network_speed_test_service: NetworkSpeedTestService


async def build_core_bootstrap_stage(
    *,
    environment: ApplicationEnvironment,
    module_dependencies: ApplicationModuleDependencies,
    stop_event: asyncio.Event,
    application_logger: LoggerProtocol,
    bootstrap_logger: LoggerProtocol,
    lifecycle_logger: LoggerProtocol,
    gui_status: Callable[[str], None],
    edition_composition: EditionComposition,
) -> CoreBootstrapStage:
    validate_environment(environment)
    runtime_foundation = build_runtime_foundation(
        stop_event=stop_event,
        version=environment.version,
        application_logger=application_logger,
        bootstrap_logger=bootstrap_logger,
        lifecycle_logger=lifecycle_logger,
        gui_status=gui_status,
        module_dependencies=module_dependencies.lifecycle,
    )
    runtime_state = runtime_foundation.runtime_state
    cancellation_system = runtime_foundation.cancellation_system
    configuration_foundation = await build_configuration_foundation(
        environment=environment,
        module_dependencies=module_dependencies,
        logging_instance=runtime_foundation.logging_instance,
        edition_capabilities=edition_composition.capabilities,
    )
    runtime_state.set_degraded_mode(configuration_foundation.degraded_mode)
    config = configuration_foundation.config
    configuration_data = configuration_foundation.configuration_data
    resolve_lifecycle_shutdown_budgets(config)
    await ensure_base_path_correct(
        config_data=configuration_data,
        environment=environment,
        lifecycle_logger=lifecycle_logger,
    )
    await apply_cancellation_system_settings(
        config,
        cancellation_system,
        lifecycle_logger,
        module_dependencies.bootstrap,
    )
    task_type_routing_service = TaskTypeRoutingService(
        TaskTypeRoutingServiceDependencies(
            command_routes=edition_composition.tasks.command_routes,
        ),
    )
    event_bus = build_event_bus(
        config=config,
        cancellation_binder=cancellation_system.binder,
        finalizer_tracker=cancellation_system.finalizer_tracker,
        lifecycle_logger=lifecycle_logger,
    )
    log_manager = LoggingManager(LoggingManagerDependencies())
    log_manager.setup_logging(
        config,
        main_loop=runtime_state.async_loop,
    )
    event_bus.start()
    try:
        disk_speed_test_service = DiskSpeedTestService(
            DiskSpeedTestServiceDependencies(
                reservation_provider=create_bootstrap_disk_reservation_provider(
                    environment.base_dir,
                ),
            ),
        )
        network_speed_test_service = NetworkSpeedTestService(NetworkSpeedTestServiceDependencies())
        logging_instance = ensure_banner_system(
            logging_instance=runtime_foundation.logging_instance,
            log_manager=log_manager,
            banner_width=module_dependencies.lifecycle.banner_width,
        )
        restart_state_manager = RestartStateManager(
            RestartStateManagerDependencies(
                restart_pending_event=runtime_state.restart_pending,
                logger=application_logger,
            ),
        )
        await restart_state_manager.check_and_clear_stale_state()
        runtime_state.set_restart_state_manager(restart_state_manager)
        system_restart_requester = SystemRestartRequester(
            SystemRestartRequesterDependencies(
                restart_state_manager=restart_state_manager,
                event_bus=event_bus,
                system_restart_required_event=(
                    module_dependencies.runtime.event_types.system_restart_required_event
                ),
                logger=application_logger,
            ),
        )
        runtime_state.set_system_restart_requester(system_restart_requester)
        return CoreBootstrapStage(
            runtime_foundation=runtime_foundation,
            configuration_foundation=configuration_foundation,
            task_type_routing_service=task_type_routing_service,
            event_bus=event_bus,
            log_manager=log_manager,
            logging_instance=logging_instance,
            restart_state_manager=restart_state_manager,
            disk_speed_test_service=disk_speed_test_service,
            network_speed_test_service=network_speed_test_service,
        )
    except asyncio.CancelledError:
        await LifecycleRunner(logger=lifecycle_logger).run_entries_continue(
            (
                LifecycleEntry(
                    component_name="Core Bootstrap Event Bus",
                    phase="core_bootstrap_failure_cleanup",
                    action=event_bus.shutdown,
                    timeout_sec=CONTROL_TIMEOUT_SEC,
                    critical=False,
                ),
            ),
        )
        raise
    except RECOVERABLE_EXCEPTIONS:
        await LifecycleRunner(logger=lifecycle_logger).run_entries_continue(
            (
                LifecycleEntry(
                    component_name="Core Bootstrap Event Bus",
                    phase="core_bootstrap_failure_cleanup",
                    action=event_bus.shutdown,
                    timeout_sec=CONTROL_TIMEOUT_SEC,
                    critical=False,
                ),
            ),
        )
        raise
