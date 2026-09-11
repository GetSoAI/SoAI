"""SoAI - Application startup actors and services initialization [backend/app/startup_steps/actors_and_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.lifecycle.runner import LifecycleRunner
from app.lifecycle.startup_plan import build_core_actor_startup_entries
from app.startup_steps.actors_and_services_flows import (
    require_mcp_coordinator_components,
    resolve_setup_and_hardware_activation,
    start_background_services_and_initialize_managers,
    start_metrics_or_enable_initial_user_activation,
)
from app.startup_steps.actors_and_services_model_discovery_wait import (
    wait_for_model_discovery_or_shutdown,
)
from app.startup_steps.dependencies import StartupStepDependencies
from app.startup_steps.disk_speed_warmup import DiskSpeedWarmupStep
from app.startup_steps.plugin_summary import log_plugin_startup_summary
from app.startup_steps.webui_attachment_recovery import (
    recover_webui_conversation_attachments,
)
from app.types_application import ApplicationContext
from core.errors.exceptions import StateError
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from orchestrator.director import InactivityMonitor

__all__ = ("ActorsAndServicesStartupStep",)


def _require_startup_dependency[StartupDependency](
    value: StartupDependency | None,
    *,
    error_message: str,
) -> StartupDependency:
    if value is None:
        raise StateError(error_message)
    return value


def _require_startup_configuration(application_context: ApplicationContext) -> ConfigProtocol:
    configuration = application_context.services.configuration.config
    if configuration is None:
        raise StateError("Configuration not loaded before startup.")
    return configuration


@dataclass(frozen=True, slots=True)
class ActorsAndServicesStartupStep:
    deps: StartupStepDependencies

    async def start_actors_and_services(
        self,
        application_context: ApplicationContext,
    ) -> InactivityMonitor | None:
        overall_started_ms = monotonic_ms()
        logging_context = application_context.logging
        logging_context.logger.debug("Starting all system actors and background services...")
        logging_context.gui_status("Starting system actors and services...")
        configuration = _require_startup_configuration(application_context)
        event_bus = _require_startup_dependency(
            application_context.services.infrastructure.event_bus,
            error_message="Event bus was not initialized before startup.",
        )
        metrics_manager = _require_startup_dependency(
            application_context.services.infrastructure.metrics_manager,
            error_message="Metrics manager was not initialized before startup.",
        )
        state_aggregator = _require_startup_dependency(
            application_context.services.infrastructure.state_aggregator,
            error_message="State aggregator was not initialized before startup.",
        )
        model_manager_instance = _require_startup_dependency(
            application_context.services.models.model_coordinator,
            error_message="Model manager was not initialized before startup.",
        )
        plugin_manager_instance = _require_startup_dependency(
            application_context.services.plugins.plugin_manager,
            error_message="Plugin manager was not initialized before startup.",
        )
        configuration_manager_instance = _require_startup_dependency(
            application_context.services.configuration.config_manager,
            error_message="Configuration manager was not initialized before startup.",
        )
        file_manager_instance = _require_startup_dependency(
            application_context.services.storage.file_manager,
            error_message="File manager was not initialized before startup.",
        )
        backup_service_instance = _require_startup_dependency(
            application_context.services.storage.backup_service,
            error_message="Backup service was not initialized before startup.",
        )
        orchestrator_control_instance = _require_startup_dependency(
            application_context.services.orchestrator.control,
            error_message="Orchestrator control was not initialized before startup.",
        )
        model_context_protocol_coordinator = _require_startup_dependency(
            application_context.services.model_context_protocol.coordinator,
            error_message="MCP coordinator was not initialized before startup.",
        )
        require_mcp_coordinator_components(model_context_protocol_coordinator)
        setup_started_ms = monotonic_ms()
        await application_context.services.licensing.recovery_actor.start()
        activation_plan = await resolve_setup_and_hardware_activation(
            application_context=application_context,
            deps=self.deps,
        )
        self.deps.startup_timings.record_since_ms(
            "startup.actors.resolve_setup_and_hardware_activation_ms",
            setup_started_ms,
        )
        metrics_started_ms = monotonic_ms()
        await start_metrics_or_enable_initial_user_activation(
            application_context=application_context,
            deps=self.deps,
            event_bus=event_bus,
            metrics_manager=metrics_manager,
            logging_context=logging_context,
            setup_required=activation_plan.setup_required,
            hardware_activation_enabled=activation_plan.hardware_activation_enabled,
            repair_plane=activation_plan.repair_plane,
        )
        self.deps.startup_timings.record_since_ms(
            "startup.actors.metrics_or_activation_ms",
            metrics_started_ms,
        )
        background_started_ms = monotonic_ms()
        await start_background_services_and_initialize_managers(
            application_context=application_context,
            deps=self.deps,
            setup_required=activation_plan.setup_required,
            logging_context=logging_context,
            state_aggregator=state_aggregator,
            plugin_manager_instance=plugin_manager_instance,
            configuration_manager_instance=configuration_manager_instance,
            file_manager_instance=file_manager_instance,
            backup_service_instance=backup_service_instance,
            repair_plane=activation_plan.repair_plane,
        )
        self.deps.startup_timings.record_since_ms(
            "startup.actors.background_services_ms",
            background_started_ms,
        )
        if activation_plan.repair_plane:
            logging_context.logger.warning(
                "Ordinary actors and model services remain stopped while the repair plane is active.",
            )
            self.deps.startup_timings.record_since_ms("startup.actors.total_ms", overall_started_ms)
            return None
        recovery_sweep_started_ms = monotonic_ms()
        await plugin_manager_instance.perform_startup_recovery_stop_sweep()
        self.deps.startup_timings.record_since_ms(
            "startup.actors.plugin_recovery_stop_sweep_ms",
            recovery_sweep_started_ms,
        )
        attachment_recovery_started_ms = monotonic_ms()
        await recover_webui_conversation_attachments(application_context)
        self.deps.startup_timings.record_since_ms(
            "startup.actors.webui_attachment_recovery_ms",
            attachment_recovery_started_ms,
        )
        plugin_reconciliation_started_ms = monotonic_ms()
        await plugin_manager_instance.run_initial_reconciliation()
        await plugin_manager_instance.require_ready()
        self.deps.startup_timings.record_since_ms(
            "startup.actors.plugin_initial_reconciliation_ms",
            plugin_reconciliation_started_ms,
        )
        model_init_started_ms = monotonic_ms()
        await model_manager_instance.initialize()
        self.deps.startup_timings.record_since_ms(
            "startup.actors.model_manager_initialize_ms",
            model_init_started_ms,
        )
        disk_warmup_started_ms = monotonic_ms()
        await DiskSpeedWarmupStep(self.deps).prime_disk_speed_tests(application_context)
        self.deps.startup_timings.record_since_ms(
            "startup.actors.disk_speed_warmup_ms",
            disk_warmup_started_ms,
        )
        logging_context.logger.info(
            "Performing initial scan to discover all available models. Please wait...",
        )
        logging_context.gui_status("Discovering available models...")
        model_discovery_started_ms = monotonic_ms()
        if await wait_for_model_discovery_or_shutdown(
            application_context=application_context,
            configuration=configuration,
            model_manager_instance=model_manager_instance,
            logging_context=logging_context,
        ):
            return None
        self.deps.startup_timings.record_since_ms(
            "startup.actors.model_discovery_ms",
            model_discovery_started_ms,
        )
        await log_plugin_startup_summary(plugin_manager_instance, state_aggregator)
        inactivity_monitor_instance = application_context.services.orchestrator.inactivity_monitor
        if inactivity_monitor_instance is None:
            raise StateError("Inactivity monitor is not configured.")
        core_actors_started_ms = monotonic_ms()
        entries = build_core_actor_startup_entries(
            application_context=application_context,
            inactivity_monitor_instance=inactivity_monitor_instance,
            orchestrator_control_instance=orchestrator_control_instance,
            model_context_protocol_coordinator=model_context_protocol_coordinator,
            hardware_activation_enabled=activation_plan.hardware_activation_enabled,
            setup_required=activation_plan.setup_required,
        )
        await LifecycleRunner(logger=logging_context.logger).run_entries(entries)
        self.deps.startup_timings.record_since_ms(
            "startup.actors.start_core_actors_and_services_ms",
            core_actors_started_ms,
        )
        logging_context.logger.debug(
            "%s core actors and services have been started.",
            application_context.services.lifecycle.coordinator.actor_count(),
        )
        self.deps.startup_timings.record_since_ms("startup.actors.total_ms", overall_started_ms)
        return inactivity_monitor_instance
