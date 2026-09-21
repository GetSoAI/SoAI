"""SoAI - Shutdown service lifecycle plan construction [backend/app/lifecycle/shutdown_service_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lifecycle.entries import LifecycleEntry

if TYPE_CHECKING:
    from app.types_application import ApplicationContext
    from core.lifecycle.protocols import Shutdownable

__all__ = (
    "build_restore_service_shutdown_entries",
    "build_service_shutdown_entries",
)


def build_service_shutdown_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
    task_registry_timeout_sec: float,
    orchestrator_timeout_sec: float,
    mcp_timeout_sec: float,
) -> tuple[LifecycleEntry, ...]:
    return _build_service_shutdown_entries(
        application_context,
        component_timeout_sec=component_timeout_sec,
        task_registry_timeout_sec=task_registry_timeout_sec,
        orchestrator_timeout_sec=orchestrator_timeout_sec,
        mcp_timeout_sec=mcp_timeout_sec,
        preserve_restore_owners=False,
    )


def build_restore_service_shutdown_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
    orchestrator_timeout_sec: float,
    mcp_timeout_sec: float,
) -> tuple[LifecycleEntry, ...]:
    return _build_service_shutdown_entries(
        application_context,
        component_timeout_sec=component_timeout_sec,
        task_registry_timeout_sec=component_timeout_sec,
        orchestrator_timeout_sec=orchestrator_timeout_sec,
        mcp_timeout_sec=mcp_timeout_sec,
        preserve_restore_owners=True,
    )


def _build_service_shutdown_entries(
    application_context: ApplicationContext,
    *,
    component_timeout_sec: float,
    task_registry_timeout_sec: float,
    orchestrator_timeout_sec: float,
    mcp_timeout_sec: float,
    preserve_restore_owners: bool,
) -> tuple[LifecycleEntry, ...]:
    entries: list[LifecycleEntry] = []
    services = application_context.services
    infrastructure_services = services.infrastructure
    plugin_manager = services.plugins.plugin_manager
    if not preserve_restore_owners:
        _append_shutdown_entry(
            entries,
            "Backup Manager",
            services.storage.backup_service,
            component_timeout_sec,
            critical=False,
        )
    _append_shutdown_entry(
        entries,
        "Inactivity Monitor",
        services.orchestrator.inactivity_monitor,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Automation Service",
        infrastructure_services.automation_service,
        component_timeout_sec,
        critical=False,
    )
    messaging_gateway = infrastructure_services.messaging_gateway
    if messaging_gateway is not None:
        _append_shutdown_entry(
            entries,
            "Messaging Gateway",
            messaging_gateway,
            component_timeout_sec,
            critical=False,
        )
    _append_shutdown_entry(
        entries,
        "Conversation Input Dispatcher",
        infrastructure_services.conversation_input_dispatcher,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Mail Service",
        infrastructure_services.communications.mail,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Model Services Coordinator",
        services.models.model_coordinator,
        component_timeout_sec,
        critical=True,
    )
    entries.append(
        LifecycleEntry(
            component_name="Plugin Manager Begin Shutdown",
            phase="shutdown",
            action=plugin_manager.begin_shutdown,
            timeout_sec=component_timeout_sec,
            critical=True,
        ),
    )
    _append_shutdown_entry(
        entries,
        "Orchestrator",
        services.orchestrator.control,
        orchestrator_timeout_sec,
        critical=True,
    )
    entries.append(
        LifecycleEntry(
            component_name="Plugin Manager Finalize Shutdown",
            phase="shutdown",
            action=plugin_manager.finalize_shutdown,
            timeout_sec=component_timeout_sec,
            critical=True,
        ),
    )
    _append_shutdown_entry(
        entries,
        "MCP Services Coordinator",
        services.model_context_protocol.coordinator,
        mcp_timeout_sec,
        critical=True,
    )
    _append_shutdown_entry(
        entries,
        "Terminal",
        infrastructure_services.hardware.terminal,
        component_timeout_sec,
        critical=True,
    )
    _append_shutdown_entry(
        entries,
        "SoAIBench",
        infrastructure_services.hardware.soaibench,
        component_timeout_sec,
        critical=True,
    )
    _append_shutdown_entry(
        entries,
        "Attachment Parse Tasks",
        application_context.api_runtime_singletons.attachment_parse_tasks,
        task_registry_timeout_sec,
        critical=True,
    )
    if not preserve_restore_owners:
        _append_shutdown_entry(
            entries,
            "Task Registry",
            services.tasks.task_registry,
            task_registry_timeout_sec,
            critical=True,
        )
    _append_shutdown_entry(
        entries,
        "Authoritative Plugin State Dispatcher",
        infrastructure_services.authoritative_plugin_state_dispatcher,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Config Manager",
        services.configuration.config_manager,
        component_timeout_sec,
        critical=True,
    )
    _append_shutdown_entry(
        entries,
        "API Key Quota Reconciler",
        infrastructure_services.api_key_quota_reservation_reconciler,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "WebUI Attachment Sweeper",
        infrastructure_services.webui_attachment_sweeper,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Conversation PDF Export Sweeper",
        infrastructure_services.conversation_pdf_export_sweeper,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Database Receipt Sweeper",
        infrastructure_services.database_receipt_sweeper,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Mutation Command Supervisor",
        infrastructure_services.mutation_command_supervisor,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Domain Event Outbox Dispatcher",
        infrastructure_services.domain_event_outbox_dispatcher,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Plugin Circuit Breaker Notifications",
        infrastructure_services.plugin_circuit_breaker_notifications,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Metrics Manager",
        infrastructure_services.metrics_manager,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "File Manager",
        services.storage.file_manager,
        component_timeout_sec,
        critical=True,
    )
    _append_shutdown_entry(
        entries,
        "Media Parsing Runtimes",
        services.storage.media_parsing,
        component_timeout_sec,
        critical=True,
    )
    _append_shutdown_entry(
        entries,
        "State Aggregator",
        infrastructure_services.state_aggregator,
        component_timeout_sec,
        critical=False,
    )
    _append_shutdown_entry(
        entries,
        "Hardware Manager",
        infrastructure_services.hardware.manager,
        component_timeout_sec,
        critical=False,
    )
    return tuple(entries)


def _append_shutdown_entry(
    entries: list[LifecycleEntry],
    name: str,
    component: Shutdownable,
    timeout: float,
    *,
    critical: bool,
) -> None:
    entries.append(
        LifecycleEntry(
            component_name=name,
            phase="shutdown",
            action=component.shutdown,
            timeout_sec=timeout,
            critical=critical,
        ),
    )
