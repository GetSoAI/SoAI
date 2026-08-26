"""SoAI - Orchestrator startup logic for config and model updates [backend/orchestrator/lifecycle/startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import override

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_models_model_events import ModelParametersRequireReloadEvent
from core.events.types_system import ConfigReloadedEvent
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN,
    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
    SchedulerWorkItem,
)
from core.state.state_names import (
    ORCH_STATE_PROCESSING,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_READY_PENDING_DISPATCH,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.internal_protocols import (
    VirtualModelHealthProtocol,
    VirtualModelRotationProtocol,
)
from orchestrator.lifecycle.config_reload_result import PluginConfigReloadResult
from orchestrator.lifecycle.plugin_config_reload_handler import (
    PluginConfigReloadHandler,
    PluginConfigReloadHandlerDependencies,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleRuntimeMutationsProtocol,
    OrchestratorLifecycleShutdownCoordinatorProtocol,
)
from orchestrator.lifecycle.shared_dependencies import LifecycleSharedDependencies
from orchestrator.lifecycle.state_access.internal_protocols import (
    RoutingConfigProviderProtocol,
)

__all__ = (
    "OrchestratorLifecycleStartup",
    "OrchestratorLifecycleStartupDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.startup"
OPERATION = "orchestrator.load_virtual_models"


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleStartupDependencies(LifecycleSharedDependencies):
    routing_config_provider: RoutingConfigProviderProtocol
    virtual_model_health: VirtualModelHealthProtocol
    virtual_model_rotation: VirtualModelRotationProtocol
    task_registry: TaskRegistryProtocol
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol

    @override
    def __post_init__(self) -> None:
        LifecycleSharedDependencies.__post_init__(self)
        require_dependencies(
            owner="OrchestratorLifecycleStartupDependencies",
            routing_config_provider=self.routing_config_provider,
            shutdown=self.shutdown,
            task_registry=self.task_registry,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
        )


class OrchestratorLifecycleStartup:
    def __init__(self, deps: OrchestratorLifecycleStartupDependencies) -> None:
        self._deps = deps
        self._runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol | None = None
        self._plugin_config_reload_handler = PluginConfigReloadHandler(
            PluginConfigReloadHandlerDependencies(
                orchestrator=deps.orchestrator,
                shutdown_event=deps.shutdown_event,
                state=deps.state,
                lifecycle_publisher=deps.lifecycle_publisher,
                shutdown=deps.shutdown,
            ),
        )
        self.get_virtual_model_map = deps.state.get_virtual_model_map

    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None:
        self._runtime_mutations = runtime_mutations

    async def handle_plugin_config_reloaded(
        self,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.startup.handle_plugin_config_reloaded",
            )
        return await runtime_mutations.submit_config_reload(event)

    async def execute_plugin_config_reload(
        self,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult:
        return await self._plugin_config_reload_handler.handle_plugin_config_reloaded(event)

    async def publish_config_reload_failure(
        self,
        event: ConfigReloadedEvent,
        error: str,
    ) -> None:
        await self._plugin_config_reload_handler.publish_config_apply_failure(event, error)

    async def handle_parameters_changed(
        self,
        event: ModelParametersRequireReloadEvent,
    ) -> list[SchedulerWorkItem]:
        logger = get_logger(LOGGER_NAME)
        universal_id = event.universal_id
        if not isinstance(universal_id, str) or not universal_id:
            return []
        target_plugin: str | None = None
        current_version: int | None = None
        async with self._deps.state.plugins_context() as plugin_context:
            for plugin_name, plugin_state in plugin_context.plugin_states.items():
                if plugin_state.loaded_model_universal_id == universal_id:
                    target_plugin = plugin_name
                    current_version = plugin_state.parameter_version
                    break
        if not target_plugin:
            return []
        _, latest_version = (
            await self._deps.orchestrator.model_parameter_service.model_get_parameters_and_version(
                universal_id,
            )
        )
        if current_version == latest_version:
            return []
        plugin_status = await self._deps.orchestrator.state_aggregator.get_plugin_status(
            target_plugin,
        )
        async with self._deps.state.plugins_context() as plugin_context:
            current_plugin_state = plugin_context.plugin_states.get(target_plugin)
            if (
                not current_plugin_state
                or current_plugin_state.loaded_model_universal_id != universal_id
                or current_plugin_state.parameter_version == latest_version
            ):
                return []
        logger.debug(
            "Model [%s] parameters changed, marking plugin %s as dirty",
            universal_id,
            target_plugin,
        )
        if plugin_status in {
            ORCH_STATE_READY,
            ORCH_STATE_READY_PENDING_DISPATCH,
            ORCH_STATE_PROCESSING,
            ORCH_STATE_READY_DIRTY,
            PLUGIN_STATE_PERSISTENT_READY,
        }:
            await self._deps.lifecycle_publisher.publish_runtime_state_change(
                target_plugin,
                ORCH_STATE_READY_DIRTY,
                "Model parameters changed",
                details={"universal_id": universal_id},
            )
        virtual_model_names = list(
            await self._deps.state.get_virtual_model_dependencies(universal_id),
        )
        work_items = [SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, target_plugin)]
        work_items.extend(
            SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY, name)
            for name in virtual_model_names
        )
        return work_items

    async def load_virtual_models(self) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            base_routing_config = self._deps.orchestrator.routing_config_holder.base_routing_config
            database_virtual_models = (
                await self._deps.orchestrator.database_models.list_all_virtual_models()
            )
            effective_config = (
                self._deps.orchestrator.routing_config_holder.replace_effective_sources(
                    routing_config=base_routing_config,
                    database_virtual_models=database_virtual_models,
                )
            )
            self._deps.routing_config_provider.routing_config = effective_config
            virtual_model_map = {
                virtual_model.name: virtual_model
                for virtual_model in effective_config.virtual_models
                if virtual_model.is_enabled
            }
            dependency_map: defaultdict[str, set[str]] = defaultdict(set)
            for virtual_model in virtual_model_map.values():
                for constituent_model in virtual_model.models:
                    dependency_map[constituent_model.universal_id].add(virtual_model.name)
            await self._deps.state.set_virtual_model_maps(virtual_model_map, dependency_map)
            active_virtual_model_names = set(virtual_model_map.keys())
            await self._deps.virtual_model_health.prune(active_virtual_model_names)
            await self._deps.virtual_model_rotation.prune(active_virtual_model_names)
            logger.debug("Loaded/reloaded %s virtual models", len(virtual_model_map))
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Error loading virtual models",
                operation=OPERATION,
            )
