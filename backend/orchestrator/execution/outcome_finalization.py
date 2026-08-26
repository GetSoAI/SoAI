"""SoAI - Task outcome finalization flow [backend/orchestrator/execution/outcome_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from orchestrator.execution.outcome_metrics import increment_outcome_metrics
from orchestrator.execution.postprocessing import propagate_dedup_result
from orchestrator.execution.streaming_completion import (
    cleanup_streaming_completion_artifact,
)
from orchestrator.execution.temp_cleanup import cleanup_task_temp_files

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.execution.internal_protocols import (
        DeliveryManagerProtocol,
        OutcomeManagerProtocol,
    )
    from orchestrator.execution.streaming_completion import StreamingCompletion
    from orchestrator.internal_protocols import VirtualModelHealthProtocol
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = (
    "OutcomeFinalizationDependencies",
    "PersistedOutcomeFinalizer",
    "finalize_task_outcome",
)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_finalization"
OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP = (
    "orchestrator_executor.finalize_task_outcome.cleanup"
)
OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_DEDUP_PROPAGATION = (
    "orchestrator_executor.finalize_task_outcome.dedup_propagation"
)
DEDUP_PROPAGATION_RECOVERY_REASON = (
    "Deduplicated result propagation did not reach a terminal state."
)


@dataclass(frozen=True, slots=True)
class OutcomeFinalizationDependencies:
    queue: QueueServiceView
    virtual_model_health: VirtualModelHealthProtocol
    task_registry: TaskRegistryProtocol
    outcomes: OutcomeManagerProtocol
    metrics: MetricsManagerProtocol
    temp_directory: str | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OutcomeFinalizationDependencies",
            metrics=self.metrics,
            outcomes=self.outcomes,
            queue=self.queue,
            task_registry=self.task_registry,
            virtual_model_health=self.virtual_model_health,
        )


@dataclass(slots=True)
class PersistedOutcomeFinalizer:
    dependencies: OutcomeFinalizationDependencies
    delivery: DeliveryManagerProtocol
    claimed_task: Task
    delivery_version: int
    dedup_hash: str | None = None
    dedup_result: JSONDict | None = None
    dedup_streaming_completion: StreamingCompletion | JSONDict | None = None
    dedup_exception: BaseException | None = None
    metrics_counter: str | None = None
    virtual_model_state: str | None = None
    _task: Task | None = field(default=None, init=False)
    _finalized: bool = field(default=False, init=False)

    @property
    def persisted(self) -> bool:
        return self._task is not None

    def mark_persisted(self, task: Task) -> None:
        if not task.status.is_terminal():
            raise StateError("Persisted outcome finalization requires a terminal task.")
        if self._task is not None:
            raise StateError("Persisted outcome finalization was already recorded.")
        self._task = task

    async def finalize(self) -> None:
        task = self._task
        if task is None or self._finalized:
            return
        dependencies = self.dependencies
        await uncancel_then_cleanup(
            finalize_task_outcome(
                queue=dependencies.queue,
                virtual_model_health=dependencies.virtual_model_health,
                task_registry=dependencies.task_registry,
                outcomes=dependencies.outcomes,
                metrics=dependencies.metrics,
                temp_directory=dependencies.temp_directory,
                task=task,
                dedup_hash=self.dedup_hash,
                dedup_result=self.dedup_result,
                dedup_streaming_completion=self.dedup_streaming_completion,
                dedup_exception=self.dedup_exception,
                metrics_counter=self.metrics_counter,
                virtual_model_state=self.virtual_model_state,
            )
        )
        self._finalized = True

    async def abandon_unpersisted_claim(self) -> None:
        if self.persisted:
            return
        await uncancel_then_cleanup(
            self.delivery.clear_delivery_in_progress(
                self.claimed_task,
                self.delivery_version,
            )
        )

    async def finalize_and_reraise(self, exception: BaseException) -> NoReturn:
        await self.abandon_unpersisted_claim()
        await self.finalize()
        raise exception


async def finalize_task_outcome(
    *,
    queue: QueueServiceView,
    virtual_model_health: VirtualModelHealthProtocol,
    task_registry: TaskRegistryProtocol,
    outcomes: OutcomeManagerProtocol,
    metrics: MetricsManagerProtocol,
    temp_directory: str | None,
    task: Task,
    dedup_hash: str | None = None,
    dedup_result: JSONDict | None = None,
    dedup_streaming_completion: StreamingCompletion | JSONDict | None = None,
    dedup_exception: BaseException | None = None,
    metrics_counter: str | None = None,
    virtual_model_state: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    waiters: list[str] = []
    unresolved_waiter_ids: list[str] = []
    try:
        if dedup_hash and (
            dedup_result is not None
            or dedup_streaming_completion is not None
            or dedup_exception is not None
        ):
            waiters = await queue.deduplication.resolve_future(
                dedup_hash,
                result=dedup_result,
                exception=dedup_exception,
            )
            unresolved_waiter_ids = list(waiters)
            try:
                propagation_result = await propagate_dedup_result(
                    waiters=waiters,
                    queue=queue,
                    task_registry=task_registry,
                    succeed_task=outcomes.succeed_task,
                    cancel_task=outcomes.cancel_task,
                    fail_task=outcomes.fail_task,
                    result=dedup_result,
                    streaming_completion=dedup_streaming_completion,
                    exception=dedup_exception,
                )
                unresolved_waiter_ids = list(propagation_result.unresolved_waiter_ids)
            finally:
                await queue.deduplication.complete_resolution(
                    waiters,
                    unresolved_waiter_ids,
                )
            if unresolved_waiter_ids:
                recovery_unresolved_waiter_ids = list(unresolved_waiter_ids)
                try:
                    recovery_unresolved_waiter_ids = (
                        await queue.dedup_requeue.requeue_stale_dedup_waiters(
                            unresolved_waiter_ids,
                            reason=DEDUP_PROPAGATION_RECOVERY_REASON,
                        )
                    )
                finally:
                    await queue.deduplication.complete_resolution(
                        unresolved_waiter_ids,
                        recovery_unresolved_waiter_ids,
                    )
    except HANDLED_RUNTIME_EXCEPTIONS as dedup_propagation_exception:
        coerced = coerce_to_soai_error(
            dedup_propagation_exception,
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_DEDUP_PROPAGATION,
        )
        log_exception(
            logger,
            coerced,
            message=f"Dedup propagation failed for task [{task.task_id}]; continuing finalization",
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_DEDUP_PROPAGATION,
            details={"task_id": task.task_id, "dedup_hash": dedup_hash},
            level="warning",
        )
    try:
        increment_outcome_metrics(metrics, metrics_counter, task)
    except HANDLED_RUNTIME_EXCEPTIONS as metrics_exception:
        coerced = coerce_to_soai_error(
            metrics_exception,
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
        )
        log_exception(
            logger,
            coerced,
            message=f"Outcome metrics failed for task [{task.task_id}].",
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
            details={"task_id": task.task_id},
            level="warning",
        )
    try:
        context = queue.require_orchestration_context(task)
        if virtual_model_state == "success" and context.virtual_model_name:
            await virtual_model_health.record_success(context.virtual_model_name)
        elif virtual_model_state == "failure" and context.virtual_model_name:
            await virtual_model_health.record_failure(context.virtual_model_name)
    except HANDLED_RUNTIME_EXCEPTIONS as health_exception:
        coerced = coerce_to_soai_error(
            health_exception,
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
        )
        log_exception(
            logger,
            coerced,
            message=f"Virtual-model health update failed for task [{task.task_id}].",
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
            details={"task_id": task.task_id},
            level="warning",
        )
    try:
        await cleanup_task_temp_files(task, temp_directory)
    except HANDLED_RUNTIME_EXCEPTIONS as temp_cleanup_exception:
        coerced = coerce_to_soai_error(
            temp_cleanup_exception,
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
        )
        log_exception(
            logger,
            coerced,
            message=f"Temporary-file cleanup failed for task [{task.task_id}].",
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
            details={"task_id": task.task_id},
            level="warning",
        )
    try:
        await cleanup_streaming_completion_artifact(
            dedup_streaming_completion,
            temp_directory=temp_directory,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as artifact_cleanup_exception:
        coerced = coerce_to_soai_error(
            artifact_cleanup_exception,
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
        )
        log_exception(
            logger,
            coerced,
            message=f"Streaming artifact cleanup failed for task [{task.task_id}].",
            operation=OPERATION_ORCHESTRATOR_EXECUTOR_FINALIZE_TASK_OUTCOME_CLEANUP,
            details={"task_id": task.task_id},
            level="warning",
        )
