"""SoAI - Orchestrator scheduler loop and dispatch coordination [backend/orchestrator/scheduling/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.orchestrator.routing_config import RoutingConfig, require_routing_config
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_SHUTDOWN,
    SchedulerWorkItem,
)
from core.state.state_transition_sets import DISPATCH_READY_STATES
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task import Task
from core.tasks.task_cancellation_ops import generate_system_cancellation_id
from orchestrator.scheduling.action_generation_dependencies import (
    SchedulerActionGenerationDependencies,
)
from orchestrator.scheduling.action_generator import SchedulerActionGeneration
from orchestrator.scheduling.capacity import (
    SchedulerCapacity,
    SchedulerCapacityDependencies,
)
from orchestrator.scheduling.decisions import (
    SchedulerDecisionDependencies,
    SchedulerDecisions,
)
from orchestrator.scheduling.dependencies import (
    OrchestratorSchedulerDependencies,
    SchedulerDispatchCandidateDependencies,
    SchedulerPlanningDependencies,
)
from orchestrator.scheduling.dispatch_candidate_handler import (
    handle_scheduler_dispatch_candidate,
)
from orchestrator.scheduling.dispatching import SchedulerDispatching
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.failover import SchedulerPlanning
from orchestrator.scheduling.loop_runtime import (
    SchedulerLoopRuntimeDependencies,
    run_scheduler_loop,
)
from orchestrator.scheduling.work_queue import SchedulerWorkQueueState

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OrchestratorScheduler",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.service"


class OrchestratorScheduler:
    def __init__(self, deps: OrchestratorSchedulerDependencies) -> None:
        self._orchestrator_deps = deps.orchestrator
        self._routing_config: RoutingConfig | None = deps.routing_config
        self._queue = deps.queue
        self._lifecycle = deps.lifecycle
        self._inference_executor = deps.inference_executor
        self._outcomes = deps.outcomes
        self._capacity = deps.capacity
        self._task_registry = deps.task_registry
        self._shutdown_event = deps.shutdown_event
        self._scheduler_safety_net_delay = deps.config.scheduler_safety_net_delay
        self._work_queue_state = SchedulerWorkQueueState()
        self._planner = SchedulerPlanning(
            SchedulerPlanningDependencies(
                queue=self._queue,
                lifecycle=self._lifecycle,
                transient_failures=deps.transient_failures,
                virtual_model_health=deps.virtual_model_health,
                virtual_model_rotation=deps.virtual_model_rotation,
                capacity=self._capacity,
                model_information_service=self._orchestrator_deps.model_information_service,
                model_resolution_service=self._orchestrator_deps.model_resolution_service,
                state_aggregator=self._orchestrator_deps.state_aggregator,
            ),
        )
        self._capacity_service = self._build_capacity_service(deps.config)
        self._action_generation = self._build_action_generation(deps.config)
        self._dispatching = self._build_dispatching()
        self._decisions = self._build_decisions(deps.config)

    @property
    def routing_config(self) -> RoutingConfig:
        return require_routing_config(self._routing_config)

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None:
        self._routing_config = value
        self._decisions.update_routing_config(value)

    @property
    def planner(self) -> SchedulerPlanning:
        return self._planner

    @property
    def capacity_service(self) -> SchedulerCapacity:
        return self._capacity_service

    @property
    def dispatching(self) -> SchedulerDispatching:
        return self._dispatching

    def _build_capacity_service(self, config: OrchestratorRuntimeConfig) -> SchedulerCapacity:
        return SchedulerCapacity(
            SchedulerCapacityDependencies(
                capacity=self._capacity,
                lifecycle=self._lifecycle,
                plugin_manager=self._orchestrator_deps.plugin_manager,
                concurrency_config=config.concurrency_config,
            ),
        )

    def _get_lifecycle_locks_snapshot(self, plugin_names: set[str]) -> dict[str, bool]:
        lifecycle = self._orchestrator_deps.plugin_manager.lifecycle
        return {name: lifecycle.is_plugin_locked(name) for name in plugin_names}

    def _build_action_generation(
        self,
        config: OrchestratorRuntimeConfig,
    ) -> SchedulerActionGeneration:
        return SchedulerActionGeneration(
            SchedulerActionGenerationDependencies(
                queue=self._queue,
                lifecycle=self._lifecycle,
                capacity=self._capacity,
                state_aggregator=self._orchestrator_deps.state_aggregator,
                plugin_manager=self._orchestrator_deps.plugin_manager,
                model_information_service=self._orchestrator_deps.model_information_service,
                param_manager=self._orchestrator_deps.param_manager,
                task_registry=self._task_registry,
                max_concurrent_plugins=config.max_concurrent_plugins,
                resolve_execution_plan=self._planner.resolve_execution_plan,
                snapshot_outstanding_counts=self._capacity_service.snapshot_outstanding_counts,
                get_lifecycle_locks_snapshot=self._get_lifecycle_locks_snapshot,
            ),
        )

    def _build_dispatching(self) -> SchedulerDispatching:
        return SchedulerDispatching(
            SchedulerDispatchingDependencies(
                queue=self._queue,
                lifecycle=self._lifecycle,
                inference_executor=self._inference_executor,
                outcomes=self._outcomes,
                capacity=self._capacity,
                cancellation_history=self._orchestrator_deps.cancellation_history,
                cancellation_binder=self._orchestrator_deps.task_cancellation_binder,
                finalizer_tracker=self._orchestrator_deps.task_finalizer_tracker,
                task_registry=self._task_registry,
                state_aggregator=self._orchestrator_deps.state_aggregator,
                plugin_manager=self._orchestrator_deps.plugin_manager,
                model_information_service=self._orchestrator_deps.model_information_service,
                shutdown_event=self._shutdown_event,
                dispatch_ready_states=set(DISPATCH_READY_STATES),
                ensure_plugin_capacity=self._capacity_service.ensure_plugin_capacity,
                schedule_plugin_dispatch=self.schedule_plugin_dispatch,
            ),
        )

    def _build_decisions(self, config: OrchestratorRuntimeConfig) -> SchedulerDecisions:
        return SchedulerDecisions(
            SchedulerDecisionDependencies(
                queue=self._queue,
                lifecycle=self._lifecycle,
                outcomes=self._outcomes,
                cancellation_binder=self._orchestrator_deps.task_cancellation_binder,
                finalizer_tracker=self._orchestrator_deps.task_finalizer_tracker,
                queue_scheduler_work=self.queue_scheduler_work,
                dispatch_waiters=self._dispatching.dispatch_waiters,
                action_generation=self._action_generation,
                capacity_service=self._capacity_service,
                scheduler_start_task_tracker=(self._orchestrator_deps.scheduler_start_task_tracker),
                max_concurrent_plugins=config.max_concurrent_plugins,
                fair_dispatch_enabled=config.fair_dispatch_enabled,
                fair_dispatch_cap=config.fair_dispatch_cap,
            ),
        )

    def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self._scheduler_safety_net_delay = config.scheduler_safety_net_delay
        self._capacity_service.update_config(config.concurrency_config)
        self._action_generation.update_config(config.max_concurrent_plugins)
        self._decisions.update_config(
            config.max_concurrent_plugins,
            config.fair_dispatch_enabled,
            config.fair_dispatch_cap,
        )

    def _get_scheduler_safety_net_delay(self) -> float | None:
        return self._scheduler_safety_net_delay

    async def queue_scheduler_work(self, work_item: SchedulerWorkItem) -> None:
        await self._work_queue_state.enqueue_work(work_item)

    async def schedule_plugin_dispatch(self, task: Task, plugin_name: str) -> None:
        logger = get_logger(LOGGER_NAME)
        _ = spawn_tracked_task(
            self._dispatching.dispatch_task_to_plugin_queue(task, plugin_name),
            cancellation_binder=self._orchestrator_deps.task_cancellation_binder,
            cancellation_id=generate_system_cancellation_id(
                f"dispatch_to_plugin_queue_{plugin_name}",
            ),
            owner="dispatch_to_plugin_queue",
            name=f"orchestrator-dispatch-{plugin_name}-{task.task_id}",
            logger=logger,
            metadata={"plugin": plugin_name},
            finalizer_tracker=self._orchestrator_deps.task_finalizer_tracker,
        )

    async def scheduler_loop(self) -> None:
        await run_scheduler_loop(
            SchedulerLoopRuntimeDependencies(
                orchestrator_deps=self._orchestrator_deps,
                queue=self._queue,
                decisions=self._decisions,
                work_queue_state=self._work_queue_state,
                shutdown_event=self._shutdown_event,
            ),
            get_scheduler_safety_net_delay=self._get_scheduler_safety_net_delay,
        )

    async def shutdown(self) -> None:
        await self.queue_scheduler_work(SchedulerWorkItem(SCHEDULER_WORK_TYPE_SHUTDOWN, "now"))
        await self._dispatching.shutdown()

    async def handle_dispatch_candidate(
        self,
        task: Task,
        model_info: JSONDict,
        plugin_name: str,
        routing_key: str,
        *,
        from_queue: bool = False,
    ) -> None:
        await handle_scheduler_dispatch_candidate(
            deps=SchedulerDispatchCandidateDependencies(
                orchestrator=self._orchestrator_deps,
                queue=self._queue,
                lifecycle=self._lifecycle,
                outcomes=self._outcomes,
                queue_scheduler_work=self.queue_scheduler_work,
                schedule_plugin_dispatch=self.schedule_plugin_dispatch,
            ),
            task=task,
            model_info=model_info,
            plugin_name=plugin_name,
            routing_key=routing_key,
            from_queue=from_queue,
        )

    async def get_status_snapshot(self) -> JSONDict:
        dispatcher = await self._dispatching.get_status_snapshot()
        pending_count = await self._queue.tracking.get_total_pending_count()
        return {
            "scheduler_work_queue_size": self._work_queue_state.pending_count,
            "scheduler_pending_count": pending_count,
            **dispatcher,
        }
