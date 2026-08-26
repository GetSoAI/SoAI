"""SoAI - Orchestrator component assembly and lifecycle registration [backend/app/composition/manager_orchestrator_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.composition.build_orchestrator import build_orchestrator_services
from app.composition.manager_precondition_resolution import (
    resolve_infrastructure_preconditions,
)
from app.composition.manager_preconditions import ManagerPreconditions
from app.composition.orchestrator_service_components import (
    OrchestratorServiceComponents,
)
from app.composition.temp_directory_resolution import resolve_temp_directory
from app.internal_protocols import LifecycleCoordinatorProtocol
from core.config.protocols import ConfigProtocol
from core.mcp.tool_choice import extract_tool_names
from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task_cancellation_ops import cancel_task
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.plugins.protocols import PluginManagerProtocol

__all__ = ("build_orchestrator_components_and_register",)


def build_orchestrator_components_and_register(
    *,
    config: ConfigProtocol,
    preconditions: ManagerPreconditions,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    plugin_manager: PluginManagerProtocol,
    orchestrator_dependencies: OrchestratorDependencies,
) -> tuple[
    OrchestratorControlProtocol,
    OrchestratorServiceComponents,
]:
    (
        _event_bus,
        _log_manager,
        task_registry,
        task_registry_queries,
        _http_client,
        _hardware_manager,
        _command_executor,
        _metrics_manager,
        _state_aggregator,
        _authoritative_plugin_state_transitions,
    ) = resolve_infrastructure_preconditions(preconditions)
    temp_directory = resolve_temp_directory(config)
    orchestrator_components = build_orchestrator_services(
        orchestrator_dependencies,
        task_registry,
        task_registry_queries,
        tool_name_extractor=extract_tool_names,
        spawn_tracked_task=spawn_tracked_task,
        cancel_task=cancel_task,
        temp_directory=temp_directory,
    )
    plugin_manager.bind_orchestrator_lifecycle(orchestrator_components.lifecycle)
    lifecycle_coordinator.register_actor(orchestrator_components.control)
    return (
        orchestrator_components.control,
        orchestrator_components,
    )
