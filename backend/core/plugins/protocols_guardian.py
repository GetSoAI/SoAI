"""SoAI - Plugin guardian and director protocol contracts [backend/core/plugins/protocols_guardian.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.events.protocols import EventBusProtocol
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import (
    CancelTaskCallable,
    SpawnTrackedTaskCallable,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.plugins.protocols import PluginManagerProtocol
    from core.types.json import JSONDict

__all__ = (
    "DirectorComponentContext",
    "GuardianExecutorProtocol",
    "PluginGuardianProtocol",
    "UpdaterModuleDependenciesProtocol",
)


class UpdaterModuleDependenciesProtocol(Protocol):
    @property
    def httpx2(self) -> types.ModuleType: ...


class GuardianExecutorProtocol(Protocol):
    async def get_active_inferences_snapshot(self) -> list[JSONDict]: ...


@dataclass(frozen=True, slots=True)
class DirectorComponentContext:
    event_bus: EventBusProtocol
    plugin_manager: PluginManagerProtocol
    routing_config: RoutingConfig
    metrics_manager: MetricsManagerProtocol | None
    audit_logger: LoggerProtocol
    state_aggregator: StateAggregatorProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    spawn_tracked_task: SpawnTrackedTaskCallable
    cancel_task: CancelTaskCallable


class PluginGuardianProtocol(Protocol):
    def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def is_plugin_recovering(self, plugin_name: str) -> bool: ...

    def update_component_context(self, component_context: DirectorComponentContext) -> None: ...

    def refresh_config(
        self,
        routing_config: RoutingConfig,
        *,
        component_context: DirectorComponentContext | None = None,
    ) -> None: ...
