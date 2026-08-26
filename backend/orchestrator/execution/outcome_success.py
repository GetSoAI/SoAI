"""SoAI - Successful task outcome delivery and finalization [backend/orchestrator/execution/outcome_success.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.reply_queue_terminal_delivery import (
    try_deliver_terminal_reply_event,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_models_streaming import InferenceResultEvent, StreamEndEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_base import METRIC_KEY_COMPLETED
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_TERMINAL_DELIVERY_FAILED,
)
from core.metrics.keyspace_paths_reply_queue import (
    REPLY_QUEUE_COUNTER_TERMINAL_DELIVERY_FAILED,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from orchestrator.execution.outcome_api_key_quotas import finalize_openai_api_key_quota
from orchestrator.execution.outcome_finalization import PersistedOutcomeFinalizer
from orchestrator.execution.outcome_metrics import increment_outcome_counter_noncritical
from orchestrator.execution.outcome_quota_extraction import extract_total_tokens
from orchestrator.execution.outcome_resource_release import release_terminal_resources
from orchestrator.execution.outcome_task_state import (
    apply_terminal_persistence_to_runtime_task,
)
from orchestrator.execution.postprocessing import update_stats_and_callbacks
from orchestrator.execution.stream_delivery import try_deliver_stream_chunks
from orchestrator.execution.streaming_completion import (
    cleanup_streaming_completion_artifact,
    coerce_streaming_completion,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.events.protocols import EventBusProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
    )
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.execution.internal_protocols import DeliveryManagerProtocol
    from orchestrator.execution.outcome_finalization import OutcomeFinalizationDependencies
    from orchestrator.execution.streaming_completion import StreamingCompletion
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("handle_successful_task_outcome",)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_success"
OPERATION_ORCHESTRATOR_EXECUTION_OUTCOME_SUCCESS_HANDLE_SUCCESSFUL_TASK_OUTCOME = (
    "orchestrator.execution.outcome_success.handle_successful_task_outcome"
)
OPERATION_ORCHESTRATOR_SUCCEED_TASK = "orchestrator.succeed_task"


async def handle_successful_task_outcome(
    *,
    queue: QueueServiceView,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    task_registry: TaskRegistryProtocol,
    delivery: DeliveryManagerProtocol,
    finalization_dependencies: OutcomeFinalizationDependencies,
    metrics: MetricsManagerProtocol,
    model_information_service: ModelInformationServiceProtocol,
    database_models: DatabaseModelsProtocol,
    database_api_keys: DatabaseAPIKeysProtocol,
    event_bus: EventBusProtocol,
    task: Task,
    result: JSONDict | None = None,
    is_streaming: bool = False,
    streaming_completion: StreamingCompletion | JSONDict | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    temp_directory = finalization_dependencies.temp_directory
    normalized_streaming_completion = (
        coerce_streaming_completion(streaming_completion) if is_streaming else None
    )
    result_payload = coerce_json_dict(result) if result is not None else None
    if is_streaming:
        usage_payload = (
            normalized_streaming_completion.usage
            if normalized_streaming_completion is not None
            else None
        )
        result_payload = (
            normalized_streaming_completion.final_result
            if normalized_streaming_completion is not None
            else result_payload
        )
    else:
        usage_payload = (
            coerce_json_dict(result_payload.get("usage")) if result_payload is not None else None
        )
    total_tokens = extract_total_tokens(usage_payload)
    if total_tokens <= 0:
        reservation_value = coerce_json_dict(task.metadata.get("quota"))
        estimate_value = (
            reservation_value.get("estimate_units") if reservation_value is not None else None
        )
        total_tokens = (
            int(estimate_value) if is_strict_int(estimate_value) and estimate_value > 0 else 0
        )
    dedup_hash_to_notify: str | None = None
    context = queue.require_orchestration_context(task)
    task, delivery_version = await delivery.prepare_delivery(task)
    if delivery_version is None:
        await cleanup_streaming_completion_artifact(
            normalized_streaming_completion,
            temp_directory=temp_directory,
        )
        return
    is_deduplicated_follower = task.status == TaskStatus.DEDUPED
    context = queue.require_orchestration_context(task)
    if context.dedup_hash and task.status != TaskStatus.DEDUPED:
        dedup_hash_to_notify = context.dedup_hash
    result_payload = result_payload if result_payload is not None else {}
    outcome_finalizer = PersistedOutcomeFinalizer(
        dependencies=finalization_dependencies,
        delivery=delivery,
        claimed_task=task,
        delivery_version=delivery_version,
        dedup_hash=dedup_hash_to_notify,
        dedup_result=result_payload,
        dedup_streaming_completion=normalized_streaming_completion,
        metrics_counter=METRIC_KEY_COMPLETED,
        virtual_model_state="success",
    )
    try:
        await uncancel_then_cleanup(
            finalize_openai_api_key_quota(database_api_keys, task, actual_units=total_tokens),
        )
        finalized_task = await finalize(
            task_registry,
            task.task_id,
            TaskStatus.COMPLETED,
            result=result_payload,
            status_message="Completed",
            emit_reply_completion_event=False,
            delivery_version=delivery_version,
        )
        if finalized_task is None or finalized_task.status != TaskStatus.COMPLETED:
            await outcome_finalizer.abandon_unpersisted_claim()
            await cleanup_streaming_completion_artifact(
                normalized_streaming_completion,
                temp_directory=temp_directory,
            )
            return
        task = apply_terminal_persistence_to_runtime_task(task, finalized_task)
        outcome_finalizer.mark_persisted(task)
        task = await uncancel_then_cleanup(release_terminal_resources(queue, task))
        try:
            reply_queue = task.reply_queue
            if reply_queue is not None:
                if is_streaming:
                    terminal_chunks = (
                        normalized_streaming_completion.deferred_terminal_chunks
                        if normalized_streaming_completion is not None
                        else ()
                    )
                    chunk_timeout_seconds = (
                        normalized_streaming_completion.chunk_delivery_timeout_seconds
                        if normalized_streaming_completion is not None
                        and normalized_streaming_completion.chunk_delivery_timeout_seconds
                        is not None
                        else LOCAL_IO_TIMEOUT_SEC
                    )
                    terminal_chunks_delivered = await try_deliver_stream_chunks(
                        task=task,
                        chunks=terminal_chunks,
                        streaming_chunk_delivery_timeout=chunk_timeout_seconds,
                        operation="orchestrator.succeed_task.responses_terminal_chunk",
                        logger=logger,
                    )
                    delivered = terminal_chunks_delivered and (
                        await try_deliver_terminal_reply_event(
                            reply_queue=reply_queue,
                            event=StreamEndEvent(
                                usage=(
                                    normalized_streaming_completion.usage
                                    if normalized_streaming_completion is not None
                                    else None
                                ),
                            ),
                            timeout_seconds=LOCAL_IO_TIMEOUT_SEC,
                            logger=logger,
                            operation="orchestrator.succeed_task.stream_end",
                        )
                    )
                    if not delivered:
                        increment_outcome_counter_noncritical(
                            metrics,
                            STREAMING_COUNTER_TERMINAL_DELIVERY_FAILED,
                            task_id=task.task_id,
                        )
                else:
                    delivered = await try_deliver_terminal_reply_event(
                        reply_queue=reply_queue,
                        event=InferenceResultEvent(payload=result_payload),
                        timeout_seconds=RESPONSIVE_TIMEOUT_SEC,
                        logger=logger,
                        operation="orchestrator.succeed_task.inference_result",
                    )
                    if not delivered:
                        increment_outcome_counter_noncritical(
                            metrics,
                            REPLY_QUEUE_COUNTER_TERMINAL_DELIVERY_FAILED,
                            task_id=task.task_id,
                        )
                if not delivered:
                    logger.warning(
                        "Live success delivery backpressure for task [%s]; durable completion will continue.",
                        task.task_id,
                    )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced_exception = coerce_to_soai_error(
                exception,
                operation=OPERATION_ORCHESTRATOR_SUCCEED_TASK,
            )
            log_exception(
                logger,
                coerced_exception,
                message=f"Failed to deliver live success response for task [{task.task_id}]",
                operation=OPERATION_ORCHESTRATOR_SUCCEED_TASK,
                level="warning",
            )
        if context.execution_universal_ids and not is_deduplicated_follower:
            try:
                await update_stats_and_callbacks(
                    execution_universal_id=context.execution_universal_ids[0],
                    model_information_service=model_information_service,
                    database_models=database_models,
                    event_bus=event_bus,
                    lifecycle=lifecycle,
                    request_source=context.request_source,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                coerced_exception = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_ORCHESTRATOR_SUCCEED_TASK,
                )
                log_exception(
                    logger,
                    coerced_exception,
                    message=f"Success postprocessing failed for task [{task.task_id}]",
                    operation=OPERATION_ORCHESTRATOR_SUCCEED_TASK,
                    details={"task_id": task.task_id},
                    level="warning",
                )
    except asyncio.CancelledError as cancellation_exception:
        await outcome_finalizer.finalize_and_reraise(cancellation_exception)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(
            exception,
            operation="orchestrator.execution.outcome_success.handle_successful_task_outcome",
        )
        log_exception(
            logger,
            coerced_exception,
            message=f"Successful outcome handling failed for task [{task.task_id}]",
            operation=OPERATION_ORCHESTRATOR_EXECUTION_OUTCOME_SUCCESS_HANDLE_SUCCESSFUL_TASK_OUTCOME,
            details={"task_id": task.task_id},
            level="warning",
        )
        await outcome_finalizer.finalize_and_reraise(exception)
    await outcome_finalizer.finalize()
