"""SoAI - Failed and cancelled terminal outcome execution [backend/orchestrator/execution/outcome_terminal_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.status_mapping import error_type_to_status_code
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_base import METRIC_KEY_CANCELLED, METRIC_KEY_FAILED
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_TERMINAL_DELIVERY_FAILED,
)
from core.metrics.keyspace_paths_reply_queue import (
    REPLY_QUEUE_COUNTER_TERMINAL_DELIVERY_FAILED,
)
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from orchestrator.execution.event_context import is_streaming_request
from orchestrator.execution.outcome_api_key_quotas import finalize_openai_api_key_quota
from orchestrator.execution.outcome_delivery import (
    prepare_failure_delivery,
    try_publish_error_event,
)
from orchestrator.execution.outcome_finalization import PersistedOutcomeFinalizer
from orchestrator.execution.outcome_metrics import increment_outcome_counter_noncritical
from orchestrator.execution.outcome_quota_extraction import (
    extract_quota_units_for_terminal_failure,
)
from orchestrator.execution.outcome_resource_release import release_terminal_resources
from orchestrator.execution.outcome_task_state import (
    apply_terminal_persistence_to_runtime_task,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from orchestrator.execution.internal_protocols import DeliveryManagerProtocol
    from orchestrator.execution.outcome_finalization import (
        OutcomeFinalizationDependencies,
    )
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("execute_terminal_failure_outcome",)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_terminal_failure"
OPERATION_CANCEL_TASK = "orchestrator.execution.outcomes.cancel_task"
OPERATION_FAIL_TASK = "orchestrator.execution.outcomes.fail_task"


async def execute_terminal_failure_outcome(
    *,
    queue: QueueServiceView,
    delivery: DeliveryManagerProtocol,
    task_registry: TaskRegistryProtocol,
    finalization_dependencies: OutcomeFinalizationDependencies,
    metrics: MetricsManagerProtocol,
    database_api_keys: DatabaseAPIKeysProtocol,
    task: Task,
    reason: str,
    status: TaskStatus,
    error_type: ErrorType,
    reason_is_public: bool = False,
) -> None:
    context, task, delivery_version, dedup_hash, dedup_exception = await prepare_failure_delivery(
        queue, delivery, task, reason=reason
    )
    if delivery_version is None:
        return
    normalized_reason = str(reason or "").strip() or (
        "Cancelled by user" if status == TaskStatus.CANCELLED else "Inference failed"
    )
    outcome_finalizer = PersistedOutcomeFinalizer(
        dependencies=finalization_dependencies,
        delivery=delivery,
        claimed_task=task,
        delivery_version=delivery_version,
        dedup_hash=dedup_hash,
        dedup_exception=dedup_exception,
        metrics_counter=(
            METRIC_KEY_CANCELLED if status == TaskStatus.CANCELLED else METRIC_KEY_FAILED
        ),
        virtual_model_state="failure",
    )
    try:
        failure_units = extract_quota_units_for_terminal_failure(task, normalized_reason)
        await uncancel_then_cleanup(
            finalize_openai_api_key_quota(
                database_api_keys,
                task,
                actual_units=failure_units,
            ),
        )
        finalized_task = await finalize(
            task_registry,
            task.task_id,
            status,
            error_code=(
                None if status == TaskStatus.CANCELLED else error_type_to_status_code(error_type)
            ),
            error_type=(None if status == TaskStatus.CANCELLED else error_type.value),
            error_message=normalized_reason,
            status_message=(normalized_reason if status == TaskStatus.CANCELLED else None),
            emit_reply_completion_event=False,
            delivery_version=delivery_version,
        )
        if finalized_task is None or finalized_task.status != status:
            await outcome_finalizer.abandon_unpersisted_claim()
            return
        task = apply_terminal_persistence_to_runtime_task(task, finalized_task)
        outcome_finalizer.mark_persisted(task)
        task = await uncancel_then_cleanup(release_terminal_resources(queue, task))
        delivered = await try_publish_error_event(
            delivery,
            task,
            context=context,
            reason=normalized_reason,
            error_type=error_type,
            log_message="Failed to deliver terminal inference error event",
            operation=(
                "orchestrator.cancel_task"
                if status == TaskStatus.CANCELLED
                else "orchestrator.fail_task"
            ),
            reason_is_public=reason_is_public,
            details={"task_id": task.task_id},
            level="debug" if status == TaskStatus.CANCELLED else "warning",
        )
        if not delivered:
            increment_outcome_counter_noncritical(
                metrics,
                (
                    STREAMING_COUNTER_TERMINAL_DELIVERY_FAILED
                    if is_streaming_request(context)
                    else REPLY_QUEUE_COUNTER_TERMINAL_DELIVERY_FAILED
                ),
                task_id=task.task_id,
            )
    except asyncio.CancelledError as cancellation_exception:
        await outcome_finalizer.finalize_and_reraise(cancellation_exception)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        if status == TaskStatus.CANCELLED:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_CANCEL_TASK,
            )
            log_exception(
                logger,
                coerced,
                message=f"Cancellation outcome handling failed for task [{task.task_id}]",
                operation=OPERATION_CANCEL_TASK,
                details={"task_id": task.task_id},
                level="warning",
            )
        else:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_FAIL_TASK,
            )
            log_exception(
                logger,
                coerced,
                message=f"Failure outcome handling failed for task [{task.task_id}]",
                operation=OPERATION_FAIL_TASK,
                details={"task_id": task.task_id},
                level="warning",
            )
        await outcome_finalizer.finalize_and_reraise(exception)
    await outcome_finalizer.finalize()
