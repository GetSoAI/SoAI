"""SoAI - Orchestrator scheduler protocol contracts [backend/core/orchestrator/protocols_scheduler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.orchestrator.execution_plan import ExecutionPlan
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.orchestrator.scheduler_work import SchedulerWorkItem
    from core.types.json import JSONDict

__all__ = (
    "OrchestratorSchedulerDispatchingProtocol",
    "OrchestratorSchedulerProtocol",
    "SchedulerCapacityServiceProtocol",
    "SchedulerPlanningProtocol",
)


class SchedulerPlanningProtocol(Protocol):
    async def resolve_execution_plan(
        self,
        task: Task,
        context: OrchestrationContext,
        excluded_universal_ids: set[str] | None = None,
    ) -> ExecutionPlan: ...


class SchedulerCapacityServiceProtocol(Protocol):
    async def get_concurrency_limit_for_plugin(self, plugin_name: str) -> int: ...


class OrchestratorSchedulerDispatchingProtocol(Protocol):
    async def begin_global_purge(self, *, reason: str) -> None: ...
    async def finish_global_purge(self) -> None: ...
    async def begin_plugin_purge(self, plugin_name: str, *, reason: str) -> None: ...
    async def finish_plugin_purge(self, plugin_name: str) -> None: ...
    async def cancel_all_plugin_queue_dispatchers(self) -> None: ...
    async def cancel_and_drain_plugin_queue(self, plugin_name: str, *, reason: str) -> None: ...
    async def get_status_snapshot(self) -> JSONDict: ...


class OrchestratorSchedulerProtocol(Protocol):
    @property
    def routing_config(self) -> RoutingConfig: ...
    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None: ...
    @property
    def planner(self) -> SchedulerPlanningProtocol: ...
    @property
    def dispatching(self) -> OrchestratorSchedulerDispatchingProtocol: ...
    @property
    def capacity_service(self) -> SchedulerCapacityServiceProtocol: ...
    async def queue_scheduler_work(self, work_item: SchedulerWorkItem) -> None: ...
    async def schedule_plugin_dispatch(self, task: Task, plugin_name: str) -> None: ...
    async def handle_dispatch_candidate(
        self,
        task: Task,
        model_info: JSONDict,
        plugin_name: str,
        routing_key: str,
        *,
        from_queue: bool = False,
    ) -> None: ...
    def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...
    async def scheduler_loop(self) -> None: ...
    async def shutdown(self) -> None: ...
