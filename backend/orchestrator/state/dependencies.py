"""SoAI - Dependency bundles for the orchestrator state subsystem [backend/orchestrator/state/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from orchestrator.state.internal_protocols import (
    MainStateControllerProtocol,
    PluginStateStoreProtocol,
)

__all__ = (
    "MainStateControllerDependencies",
    "PluginStateStoreDependencies",
    "StateAggregatorDependencies",
)


@dataclass(frozen=True, slots=True)
class PluginStateStoreDependencies:
    database_plugins: DatabasePluginsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginStateStoreDependencies",
            database_plugins=self.database_plugins,
        )


@dataclass(frozen=True, slots=True)
class MainStateControllerDependencies:
    event_bus: EventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MainStateControllerDependencies",
            cancellation_binder=self.cancellation_binder,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
        )


@dataclass(frozen=True, slots=True)
class StateAggregatorDependencies:
    event_bus: EventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    plugin_store: PluginStateStoreProtocol
    main_state_controller: MainStateControllerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="StateAggregatorDependencies",
            cancellation_binder=self.cancellation_binder,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            main_state_controller=self.main_state_controller,
            plugin_store=self.plugin_store,
        )
