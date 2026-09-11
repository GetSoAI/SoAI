"""SoAI - Central startup lifecycle plan construction [backend/app/lifecycle/startup_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lifecycle.entries import LifecycleEntry
from app.lifecycle.startup_entries import startup_entry, timed_startup_entry

if TYPE_CHECKING:
    from app.startup_steps.dependencies import StartupStepDependencies
    from app.types_application import ApplicationContext
    from core.mcp.protocols_main import MCPServicesCoordinatorProtocol
    from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import StateAggregatorProtocol
    from orchestrator.director import InactivityMonitor

__all__ = (
    "build_background_startup_entries",
    "build_core_actor_startup_entries",
)


def build_background_startup_entries(
    *,
    application_context: ApplicationContext,
    deps: StartupStepDependencies,
    state_aggregator: StateAggregatorProtocol,
    plugin_manager_instance: PluginManagerProtocol,
) -> tuple[LifecycleEntry, ...]:
    infrastructure_services = application_context.services.infrastructure
    entries: list[LifecycleEntry] = [
        timed_startup_entry(
            component_name="API Key Quota Reconciler",
            metric_key="startup.background.api_key_quota_reconciler_start_ms",
            deps=deps,
            action=infrastructure_services.api_key_quota_reservation_reconciler.start,
        ),
        timed_startup_entry(
            component_name="WebUI Attachment Sweeper",
            metric_key="startup.background.webui_attachment_sweeper_start_ms",
            deps=deps,
            action=infrastructure_services.webui_attachment_sweeper.start,
        ),
        timed_startup_entry(
            component_name="Conversation PDF Export Sweeper",
            metric_key="startup.background.conversation_pdf_export_sweeper_start_ms",
            deps=deps,
            action=infrastructure_services.conversation_pdf_export_sweeper.start,
        ),
        timed_startup_entry(
            component_name="Database Receipt Sweeper",
            metric_key="startup.background.database_receipt_sweeper_start_ms",
            deps=deps,
            action=infrastructure_services.database_receipt_sweeper.start,
        ),
        timed_startup_entry(
            component_name="Automation Service",
            metric_key="startup.background.automation_service_start_ms",
            deps=deps,
            action=infrastructure_services.automation_service.start,
        ),
        timed_startup_entry(
            component_name="Conversation Input Dispatcher",
            metric_key="startup.background.conversation_input_dispatcher_start_ms",
            deps=deps,
            action=infrastructure_services.conversation_input_dispatcher.start,
        ),
    ]
    entries.append(
        timed_startup_entry(
            component_name="Domain Event Outbox Dispatcher",
            metric_key="startup.background.domain_event_outbox_start_ms",
            deps=deps,
            action=infrastructure_services.domain_event_outbox_dispatcher.start,
        ),
    )
    messaging_gateway = infrastructure_services.messaging_gateway
    if messaging_gateway is not None:
        entries.append(
            timed_startup_entry(
                component_name="Messaging Gateway",
                metric_key="startup.background.messaging_gateway_start_ms",
                deps=deps,
                action=messaging_gateway.start,
            ),
        )
    entries.extend(
        (
            timed_startup_entry(
                component_name="Plugin Circuit Breaker Notifications",
                metric_key="startup.background.plugin_circuit_breaker_notifications_start_ms",
                deps=deps,
                action=infrastructure_services.plugin_circuit_breaker_notifications.start,
            ),
            timed_startup_entry(
                component_name="Communications Sync Actor",
                metric_key="startup.background.communications_sync_start_ms",
                deps=deps,
                action=infrastructure_services.communications_sync_actor.start,
            ),
        )
    )
    entries.extend(
        (
            timed_startup_entry(
                component_name="State Aggregator",
                metric_key="startup.background.state_aggregator_start_ms",
                deps=deps,
                action=state_aggregator.start,
            ),
            timed_startup_entry(
                component_name="Authoritative Plugin State Dispatcher",
                metric_key="startup.background.authoritative_plugin_dispatcher_start_ms",
                deps=deps,
                action=infrastructure_services.authoritative_plugin_state_dispatcher.start,
            ),
            timed_startup_entry(
                component_name="Plugin Manager",
                metric_key="startup.background.plugin_manager_initialize_ms",
                deps=deps,
                action=plugin_manager_instance.initialize,
            ),
        ),
    )
    entries.append(
        timed_startup_entry(
            component_name="Mutation Command Supervisor",
            metric_key="startup.background.mutation_command_supervisor_start_ms",
            deps=deps,
            action=infrastructure_services.mutation_command_supervisor.start,
        ),
    )
    return tuple(entries)


def build_core_actor_startup_entries(
    *,
    application_context: ApplicationContext,
    inactivity_monitor_instance: InactivityMonitor,
    orchestrator_control_instance: OrchestratorControlProtocol,
    model_context_protocol_coordinator: MCPServicesCoordinatorProtocol,
    hardware_activation_enabled: bool,
    setup_required: bool,
) -> tuple[LifecycleEntry, ...]:
    infrastructure_services = application_context.services.infrastructure
    entries: list[LifecycleEntry] = [
        startup_entry(
            component_name="Orchestrator",
            action=orchestrator_control_instance.start,
        ),
        startup_entry(
            component_name="Inactivity Monitor",
            action=inactivity_monitor_instance.start,
        ),
    ]
    if hardware_activation_enabled and not setup_required:

        async def _start_hardware_monitoring() -> None:
            await infrastructure_services.hw_manager.start_monitoring()

        entries.extend(
            (
                startup_entry(
                    component_name="Hardware Manager",
                    action=_start_hardware_monitoring,
                ),
                startup_entry(
                    component_name="SoAIBench",
                    action=infrastructure_services.hardware_soaibench.reconcile_startup,
                ),
                startup_entry(
                    component_name="Hardware GPU Tuning",
                    action=infrastructure_services.hw_gpu_tuning.apply_startup_gpu_settings,
                ),
            ),
        )
    entries.append(
        startup_entry(
            component_name="MCP Services Coordinator",
            action=model_context_protocol_coordinator.start,
        ),
    )
    return tuple(entries)
