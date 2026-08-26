"""SoAI - Model actions service dependencies [backend/models/actions/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.models.protocols_database import (
    DatabaseModelsProtocol,
    ModelDatabasePurgeServiceProtocol,
)
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    SpawnTrackedTaskCallable,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from models.internal_protocols import ModelMutationEffectsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("ModelActionsServiceDependencies",)


@dataclass(frozen=True, slots=True)
class ModelActionsServiceDependencies:
    config: ConfigProtocol
    database_models: DatabaseModelsProtocol
    database_plugins: DatabasePluginsProtocol
    plugin_manager: PluginManagerProtocol
    state_aggregator: StateAggregatorProtocol
    event_bus: EventBusProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    task_registry: TaskRegistryProtocol
    mutation_effects: ModelMutationEffectsProtocol
    model_database_purge_service: ModelDatabasePurgeServiceProtocol
    model_record_locks: AsyncLockRegistryProtocol[str]
    installed_plugin_names_ref: Callable[[], set[str]]
    model_get_info: Callable[[str], Awaitable[JSONDict | None]]
    spawn_tracked_task: SpawnTrackedTaskCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelActionsServiceDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            config=self.config,
            database_models=self.database_models,
            database_plugins=self.database_plugins,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            installed_plugin_names_ref=self.installed_plugin_names_ref,
            model_get_info=self.model_get_info,
            model_record_locks=self.model_record_locks,
            mutation_effects=self.mutation_effects,
            model_database_purge_service=self.model_database_purge_service,
            plugin_manager=self.plugin_manager,
            spawn_tracked_task=self.spawn_tracked_task,
            state_aggregator=self.state_aggregator,
            task_registry=self.task_registry,
            token_collection=self.token_collection,
        )
