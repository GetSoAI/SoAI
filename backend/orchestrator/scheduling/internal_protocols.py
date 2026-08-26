"""SoAI - Orchestrator scheduling internal protocols [backend/orchestrator/scheduling/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable

    from core.concurrency.protocols import QueueGetNowaitProtocol
    from core.models.protocols import ModelInformationServiceProtocol
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.tasks.protocols import (
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
    )
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.internal_protocols import (
        OrchestratorCapacityProtocol,
        OrchestratorInferenceExecutorProtocol,
        OrchestratorTaskOutcomesProtocol,
    )
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )

__all__ = (
    "DispatchRuntimeInvariantDependenciesProtocol",
    "MetricsProtocol",
    "PluginQueueDispatcherDependenciesProtocol",
    "PluginStateProtocol",
    "SchedulerCapacityProtocol",
)


class SchedulerCapacityProtocol(Protocol):
    def resolve_plugin_limit_for_fairness(self, plugin_name: str) -> int: ...


class MetricsProtocol(Protocol):
    def increment_counter(self, *keys: str, value: int = 1) -> None: ...


class PluginStateProtocol(Protocol):
    loaded_model_universal_id: str | None
    loaded_parameters: JSONDict | None


class DispatchRuntimeInvariantDependenciesProtocol(Protocol):
    @property
    def lifecycle(self) -> OrchestratorLifecycleCoordinatorProtocol: ...

    @property
    def plugin_manager(self) -> PluginManagerProtocol: ...

    @property
    def state_aggregator(self) -> StateAggregatorProtocol: ...

    @property
    def dispatch_ready_states(self) -> set[str]: ...


class PluginQueueDispatcherDependenciesProtocol(Protocol):
    @property
    def queue(self) -> OrchestratorQueueProtocol: ...

    @property
    def lifecycle(self) -> OrchestratorLifecycleCoordinatorProtocol: ...

    @property
    def inference_executor(self) -> OrchestratorInferenceExecutorProtocol: ...

    @property
    def outcomes(self) -> OrchestratorTaskOutcomesProtocol: ...

    @property
    def capacity(self) -> OrchestratorCapacityProtocol: ...

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...

    @property
    def cancellation_binder(self) -> TaskCancellationBinderProtocol: ...

    @property
    def finalizer_tracker(self) -> TaskFinalizerTrackerProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def state_aggregator(self) -> StateAggregatorProtocol: ...

    @property
    def plugin_manager(self) -> PluginManagerProtocol: ...

    @property
    def model_information_service(self) -> ModelInformationServiceProtocol: ...

    @property
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    def dispatch_ready_states(self) -> set[str]: ...

    @property
    def finalize_plugin_queue_shutdown(
        self,
    ) -> Callable[[str, QueueGetNowaitProtocol[Task] | None, list[Task]], Awaitable[None]]: ...

    @property
    def claim_plugin_queue_dispatcher_idle_exit(self) -> Callable[[str], Awaitable[bool]]: ...
