"""SoAI - Startup flows for actors and services [backend/app/startup_steps/actors_and_services_flows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.lifecycle.runner import LifecycleRunner
from app.lifecycle.startup_plan import build_background_startup_entries
from app.startup_steps.dependencies import StartupStepDependencies
from app.startup_steps.initial_user_persistence_activation import (
    InitialUserPersistenceActivation,
    InitialUserPersistenceActivationDependencies,
    schedule_prune_webui_session_state,
)
from core.errors.exceptions import StateError
from core.mcp.protocols_main import MCPServicesCoordinatorProtocol
from core.timing.monotonic import monotonic_ms
from core.users.bootstrap_state import BootstrapState

if TYPE_CHECKING:
    from app.application_dependencies import ApplicationLogging
    from app.backup.backup_service import ApplicationBackupService
    from app.types_application import ApplicationContext
    from core.config.protocols import ConfigManagerProtocol
    from core.events.protocols import EventBusProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import StateAggregatorProtocol
    from files.manager import FileManager

__all__ = (
    "require_mcp_coordinator_components",
    "StartupActivationPlan",
    "resolve_setup_and_hardware_activation",
    "start_background_services_and_initialize_managers",
    "start_metrics_or_enable_initial_user_activation",
)


@dataclass(frozen=True, slots=True)
class StartupActivationPlan:
    setup_required: bool
    hardware_activation_enabled: bool
    repair_plane: bool


def require_mcp_coordinator_components(mcp_coordinator: MCPServicesCoordinatorProtocol) -> None:
    if mcp_coordinator.server is None:
        raise StateError("MCP server coordinator was not initialized before startup.")
    if mcp_coordinator.remote is None:
        raise StateError("MCP remote coordinator was not initialized before startup.")


async def resolve_setup_and_hardware_activation(
    *,
    application_context: ApplicationContext,
    deps: StartupStepDependencies,
) -> StartupActivationPlan:
    bootstrap_state = await application_context.services.databases.users.get_bootstrap_state()
    if bootstrap_state is BootstrapState.INTEGRITY_ERROR:
        application_context.runtime.set_degraded_mode(True)
        application_context.runtime.set_repair_plane(True)
        application_context.logging.logger.critical(
            "Initial setup database state is inconsistent; starting the restricted repair plane.",
        )
        return StartupActivationPlan(
            setup_required=False,
            hardware_activation_enabled=False,
            repair_plane=True,
        )
    if bootstrap_state is BootstrapState.COMPLETE:
        licensing_status = await application_context.services.licensing.runtime.resolved_status()
        if licensing_status.requires_repair_plane:
            await application_context.services.licensing.repair_plane_coordinator.activate_startup_repair_plane()
            application_context.runtime.set_degraded_mode(True)
            application_context.runtime.set_repair_plane(True)
            application_context.logging.logger.critical(
                "Licensing state %s requires recovery; starting the restricted repair plane.",
                licensing_status.state,
            )
            return StartupActivationPlan(
                setup_required=False,
                hardware_activation_enabled=False,
                repair_plane=True,
            )
    setup_required = bootstrap_state is BootstrapState.UNINITIALIZED
    hardware_activation_enabled = (
        application_context.runtime.hardware_manager_available
        and deps.runtime_coordinator.get_configuration_flag("SYSTEM.HARDWARE.ENABLED", False)
    )
    return StartupActivationPlan(
        setup_required=setup_required,
        hardware_activation_enabled=hardware_activation_enabled,
        repair_plane=False,
    )


async def start_metrics_or_enable_initial_user_activation(
    *,
    application_context: ApplicationContext,
    deps: StartupStepDependencies,
    event_bus: EventBusProtocol,
    metrics_manager: MetricsManagerProtocol,
    logging_context: ApplicationLogging,
    setup_required: bool,
    hardware_activation_enabled: bool,
    repair_plane: bool,
) -> None:
    if repair_plane:
        await metrics_manager.start()
        application_context.runtime.set_prune_tokens_task(None)
        return
    if setup_required:
        InitialUserPersistenceActivation(
            InitialUserPersistenceActivationDependencies(
                event_bus=event_bus,
                runtime_coordinator=deps.runtime_coordinator,
                metrics_manager=metrics_manager,
                hardware_manager=application_context.services.infrastructure.hw_manager,
                hardware_gpu_tuning=application_context.services.infrastructure.hw_gpu_tuning,
                database_tokens=application_context.services.plugins.webui_manager.database_tokens,
                runtime_state=application_context.runtime,
                logger=logging_context.logger,
                hardware_activation_enabled=hardware_activation_enabled,
            ),
        ).enable()
        logging_context.logger.info(
            "Initial setup detected; deferring metrics and hardware persistence until the first user is created.",
        )
        return
    await metrics_manager.start()


async def start_background_services_and_initialize_managers(
    *,
    application_context: ApplicationContext,
    deps: StartupStepDependencies,
    setup_required: bool,
    logging_context: ApplicationLogging,
    state_aggregator: StateAggregatorProtocol,
    plugin_manager_instance: PluginManagerProtocol,
    configuration_manager_instance: ConfigManagerProtocol,
    file_manager_instance: FileManager,
    backup_service_instance: ApplicationBackupService,
    repair_plane: bool,
) -> None:
    if not repair_plane:
        entries = build_background_startup_entries(
            application_context=application_context,
            deps=deps,
            state_aggregator=state_aggregator,
            plugin_manager_instance=plugin_manager_instance,
        )
        await LifecycleRunner(logger=logging_context.logger).run_entries(entries)
    step_started_ms = monotonic_ms()
    await configuration_manager_instance.establish_baseline()
    deps.startup_timings.record_since_ms("startup.background.config_baseline_ms", step_started_ms)
    step_started_ms = monotonic_ms()
    configuration_manager_instance.start()
    deps.startup_timings.record_since_ms(
        "startup.background.config_manager_start_ms",
        step_started_ms,
    )
    step_started_ms = monotonic_ms()
    await file_manager_instance.initialize()
    deps.startup_timings.record_since_ms(
        "startup.background.file_manager_initialize_ms",
        step_started_ms,
    )
    step_started_ms = monotonic_ms()
    await backup_service_instance.initialize()
    deps.startup_timings.record_since_ms(
        "startup.background.backup_service_initialize_ms",
        step_started_ms,
    )
    if setup_required or repair_plane:
        application_context.runtime.set_prune_tokens_task(None)
    else:
        schedule_prune_webui_session_state(
            runtime_coordinator=deps.runtime_coordinator,
            runtime_state=application_context.runtime,
            database_tokens=application_context.services.plugins.webui_manager.database_tokens,
            logger=logging_context.logger,
        )
    logging_context.logger.debug(
        "Model, Plugin, Config, File, and Backup managers, State Aggregator, and authoritative state dispatcher initialized.",
    )
    logging_context.gui_status("Managers initialized successfully")
