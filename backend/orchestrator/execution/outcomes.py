"""SoAI - Task outcome finalization for success, failure, and cancellation [backend/orchestrator/execution/outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.events.protocols import EventBusProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.tasks.enums import TaskStatus
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from orchestrator.execution.dependencies import OutcomeManagerDependencies
from orchestrator.execution.internal_protocols import DeliveryManagerProtocol
from orchestrator.execution.outcome_failover import (
    requeue_failover_task,
    try_failover_task,
)
from orchestrator.execution.outcome_finalization import OutcomeFinalizationDependencies
from orchestrator.execution.outcome_success import handle_successful_task_outcome
from orchestrator.execution.outcome_terminal_failure import (
    execute_terminal_failure_outcome,
)
from orchestrator.execution.streaming_completion import StreamingCompletion
from orchestrator.execution.waiter_failures import (
    cancel_waiters_for_routing_key,
    fail_waiters_for_routing_key,
)
from orchestrator.internal_protocols import (
    TransientFailureCooldownsProtocol,
    VirtualModelHealthProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OutcomeManager",)


class OutcomeManager:
    def __init__(self, deps: OutcomeManagerDependencies) -> None:
        self._queue: QueueServiceView = deps.queue
        self._lifecycle: OrchestratorLifecycleCoordinatorProtocol = deps.lifecycle
        self._transient_failures: TransientFailureCooldownsProtocol = deps.transient_failures
        self._virtual_model_health: VirtualModelHealthProtocol = deps.virtual_model_health
        self._task_registry: TaskRegistryProtocol = deps.task_registry
        self._delivery: DeliveryManagerProtocol = deps.delivery
        self._metrics: MetricsManagerProtocol = deps.metrics
        self._model_information_service = deps.model_information_service
        self._database_models: DatabaseModelsProtocol = deps.database_models
        self._database_api_keys = deps.database_api_keys
        self._event_bus: EventBusProtocol = deps.event_bus
        self._temp_directory: str | None = deps.temp_directory
        self._finalization_dependencies = OutcomeFinalizationDependencies(
            queue=self._queue,
            virtual_model_health=self._virtual_model_health,
            task_registry=self._task_registry,
            outcomes=self,
            metrics=self._metrics,
            temp_directory=self._temp_directory,
        )

    async def succeed_task(
        self,
        task: Task,
        *,
        result: JSONDict | None = None,
        is_streaming: bool = False,
        streaming_completion: StreamingCompletion | JSONDict | None = None,
    ) -> None:
        await handle_successful_task_outcome(
            queue=self._queue,
            lifecycle=self._lifecycle,
            delivery=self._delivery,
            task_registry=self._task_registry,
            finalization_dependencies=self._finalization_dependencies,
            metrics=self._metrics,
            model_information_service=self._model_information_service,
            database_models=self._database_models,
            database_api_keys=self._database_api_keys,
            event_bus=self._event_bus,
            task=task,
            result=result,
            is_streaming=is_streaming,
            streaming_completion=streaming_completion,
        )

    async def cancel_task(
        self,
        task: Task,
        reason: str,
        *,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None:
        await execute_terminal_failure_outcome(
            queue=self._queue,
            delivery=self._delivery,
            task_registry=self._task_registry,
            finalization_dependencies=self._finalization_dependencies,
            metrics=self._metrics,
            database_api_keys=self._database_api_keys,
            task=task,
            reason=reason,
            status=TaskStatus.CANCELLED,
            error_type=error_type,
        )

    async def fail_task(
        self,
        task: Task,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
        reason_is_public: bool = False,
    ) -> None:
        cached_task = await self._task_registry.get(task.task_id)
        task = cached_task if cached_task is not None else task
        task, did_failover = (
            await try_failover_task(self._queue, self._lifecycle, self._transient_failures, task)
            if allow_failover
            else (task, False)
        )
        if did_failover:
            requeue_result = await requeue_failover_task(self._queue, self._task_registry, task)
            task = requeue_result.task
            if requeue_result.requeued:
                return
            if not requeue_result.blocked_by_delivery:
                reason = TASK_STATE_PERSISTENCE_FAILED_MESSAGE
        await execute_terminal_failure_outcome(
            queue=self._queue,
            delivery=self._delivery,
            task_registry=self._task_registry,
            finalization_dependencies=self._finalization_dependencies,
            metrics=self._metrics,
            database_api_keys=self._database_api_keys,
            task=task,
            reason=reason,
            status=TaskStatus.FAILED,
            error_type=error_type,
            reason_is_public=reason_is_public,
        )

    async def fail_waiters(
        self,
        routing_key: str,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None:
        await fail_waiters_for_routing_key(
            routing_key=routing_key,
            reason=reason,
            allow_failover=allow_failover,
            error_type=error_type,
            unregister_pending_queue=self._queue.tracking.unregister_pending_queue,
            fail_task=self.fail_task,
        )

    async def cancel_waiters(
        self,
        routing_key: str,
        reason: str,
        *,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None:
        await cancel_waiters_for_routing_key(
            routing_key=routing_key,
            reason=reason,
            error_type=error_type,
            unregister_pending_queue=self._queue.tracking.unregister_pending_queue,
            cancel_task=self.cancel_task,
        )
