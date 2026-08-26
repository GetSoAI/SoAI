"""SoAI - Post-delivery processing utilities for orchestrator executor [backend/orchestrator/execution/postprocessing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_models_model_events import ModelLastUsedChangedEvent
from core.events.types_plugins import PluginLastUsedChangedEvent
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.models.model_info_fields import coerce_plugin_name
from core.models.protocols import (
    ModelInformationServiceProtocol,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.models.provider_backing import is_provider_backed_model
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.runtime.request_sources import REQUEST_SOURCE_MODEL_TEST, RequestSource
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.execution.binary_dedup_replay import replay_binary_replay_file
from orchestrator.execution.internal_protocols import (
    CancelTaskCallable,
    FailTaskCallable,
    SucceedTaskCallable,
)
from orchestrator.execution.result_processing_error import ResultProcessingError
from orchestrator.execution.streaming import STREAMING_CHUNK_DELIVERY_TIMEOUT_DEFAULT
from orchestrator.execution.streaming_completion import coerce_streaming_completion
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from orchestrator.execution.streaming_completion import StreamingCompletion

__all__ = (
    "DedupPropagationResult",
    "propagate_dedup_result",
    "update_stats_and_callbacks",
)

LOGGER_NAME = "SoAI.orchestrator.execution.postprocessing"
OPERATION_ORCHESTRATOR_EXECUTOR_PROPAGATE_DEDUP_RESULT = (
    "orchestrator_executor.propagate_dedup_result"
)
OPERATION_ORCHESTRATOR_UPDATE_STATS_AND_CALLBACKS = "orchestrator.update_stats_and_callbacks"


@dataclass(frozen=True, slots=True)
class DedupPropagationResult:
    unresolved_waiter_ids: tuple[str, ...]


async def _gather_and_log_waiter_errors(
    awaitables: list[Awaitable[None]],
    waiter_ids: list[str],
    logger: LoggerProtocol,
    error_message_prefix: str,
) -> DedupPropagationResult:
    gather_results = await asyncio.gather(*awaitables, return_exceptions=True)
    unresolved_waiter_ids: list[str] = []
    for waiter_index, gather_result in enumerate(gather_results):
        if isinstance(gather_result, BaseException):
            unresolved_waiter_ids.append(waiter_ids[waiter_index])
            log_exception(
                logger,
                gather_result,
                message=f"{error_message_prefix} [{waiter_ids[waiter_index]}]",
                operation=OPERATION_ORCHESTRATOR_EXECUTOR_PROPAGATE_DEDUP_RESULT,
                details={"task_id": waiter_ids[waiter_index]},
                level="warning",
            )
    return DedupPropagationResult(unresolved_waiter_ids=tuple(unresolved_waiter_ids))


async def propagate_dedup_result(
    *,
    waiters: list[str],
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    succeed_task: SucceedTaskCallable,
    cancel_task: CancelTaskCallable,
    fail_task: FailTaskCallable,
    result: JSONDict | None = None,
    streaming_completion: StreamingCompletion | JSONDict | None = None,
    exception: BaseException | None = None,
) -> DedupPropagationResult:
    logger = get_logger(LOGGER_NAME)
    if not waiters:
        return DedupPropagationResult(unresolved_waiter_ids=())
    registry = task_registry
    if exception is None:
        logger.debug(
            "Lead task for dedup hash succeeded. Propagating result to %s followers.",
            len(waiters),
        )

        async def deliver(task_id: str) -> None:
            logger = get_logger(LOGGER_NAME)
            waiter_task = await registry.get(task_id)
            if waiter_task is None or waiter_task.status.is_terminal():
                return
            if await queue.is_task_cancelled(waiter_task):
                await cancel_task(
                    waiter_task,
                    "Task cancelled by user while waiting for deduplicated result.",
                )
                return
            try:
                normalized_streaming_completion = coerce_streaming_completion(streaming_completion)
                if normalized_streaming_completion.binary_replay_temp_path is not None:
                    replay_timeout_seconds = (
                        normalized_streaming_completion.chunk_delivery_timeout_seconds
                        if normalized_streaming_completion.chunk_delivery_timeout_seconds
                        is not None
                        else STREAMING_CHUNK_DELIVERY_TIMEOUT_DEFAULT
                    )
                    await replay_binary_replay_file(
                        task=waiter_task,
                        temp_path=normalized_streaming_completion.binary_replay_temp_path,
                        streaming_chunk_delivery_timeout=replay_timeout_seconds,
                        logger=logger,
                    )
                    await succeed_task(
                        waiter_task,
                        is_streaming=True,
                        streaming_completion=normalized_streaming_completion,
                    )
                    return
                if normalized_streaming_completion.deferred_terminal_chunks:
                    await succeed_task(
                        waiter_task,
                        is_streaming=True,
                        streaming_completion=normalized_streaming_completion,
                    )
                    return
                await succeed_task(waiter_task, result=result)
            except OSError as exception:
                replay_exception = ResultProcessingError(
                    "Failed to deliver deduplicated binary replay.",
                    operation=OPERATION_ORCHESTRATOR_EXECUTOR_PROPAGATE_DEDUP_RESULT,
                    details={"task_id": task_id, "error": str(exception)},
                    cause=exception,
                )
                log_exception(
                    logger,
                    replay_exception,
                    message=f"Failed to propagate dedup binary replay to follower [{task_id}]",
                    operation=OPERATION_ORCHESTRATOR_EXECUTOR_PROPAGATE_DEDUP_RESULT,
                    details={"task_id": task_id},
                    level="warning",
                )
                await fail_task(
                    waiter_task,
                    f"Failed to deliver deduplicated binary replay: {exception}",
                    allow_failover=False,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to propagate dedup success to follower [{task_id}]",
                    operation=OPERATION_ORCHESTRATOR_EXECUTOR_PROPAGATE_DEDUP_RESULT,
                    details={"task_id": task_id},
                    level="warning",
                )
                await fail_task(
                    waiter_task,
                    f"Failed to deliver deduplicated result due to channel error: {exception}",
                    allow_failover=False,
                )

        return await _gather_and_log_waiter_errors(
            [deliver(task_id) for task_id in waiters],
            waiters,
            logger,
            "Dedup success propagation failed for follower",
        )
    reason = f"Lead request failed: {exception}"
    logger.warning(
        "Lead task for dedup hash failed. Failing %s followers. Reason: %s",
        len(waiters),
        reason,
    )

    async def fail_waiter(task_id: str) -> None:
        waiter_task = await registry.get(task_id)
        if waiter_task is None or waiter_task.status.is_terminal():
            return
        await fail_task(waiter_task, reason, allow_failover=False)

    return await _gather_and_log_waiter_errors(
        [fail_waiter(task_id) for task_id in waiters],
        waiters,
        logger,
        "Dedup failure propagation failed for follower",
    )


async def update_stats_and_callbacks(
    *,
    execution_universal_id: str,
    model_information_service: ModelInformationServiceProtocol | None,
    database_models: DatabaseModelsProtocol,
    event_bus: EventBusProtocol,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    request_source: RequestSource | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        model_info = (
            await model_information_service.model_get_info(execution_universal_id)
            if model_information_service
            else None
        )
        if model_info:
            universal_id_value = model_info.get("universal_id")
            if (
                not isinstance(universal_id_value, str)
                or not universal_id_value
                or universal_id_value != execution_universal_id
            ):
                raise StateError(
                    "Model information payload does not match the executed universal_id.",
                    operation="orchestrator.update_stats_and_callbacks",
                    details={
                        "execution_universal_id": execution_universal_id,
                        "universal_id": universal_id_value,
                    },
                )
            plugin_value = model_info.get("plugin")
            plugin_name = coerce_plugin_name(model_info)
            if plugin_name is None:
                raise StateError(
                    "Model information payload is missing a valid plugin name.",
                    operation="orchestrator.update_stats_and_callbacks",
                    details={
                        "execution_universal_id": execution_universal_id,
                        "plugin": plugin_value,
                    },
                )
            usage_record = await database_models.record_model_usage(
                universal_id_value,
                plugin_name,
            )
            if usage_record is None:
                raise StateError(
                    "Failed to persist model usage statistics.",
                    operation="orchestrator.update_stats_and_callbacks",
                    details={
                        "execution_universal_id": execution_universal_id,
                        "universal_id": universal_id_value,
                    },
                )
            last_used_at_ms, revision = usage_record
            event_bus.try_publish_nowait(
                ModelLastUsedChangedEvent(
                    universal_id=universal_id_value,
                    last_used_at_ms=last_used_at_ms,
                    revision=revision,
                ),
            )
            event_bus.try_publish_nowait(
                PluginLastUsedChangedEvent(
                    plugin_name=plugin_name,
                    last_used_at_ms=last_used_at_ms,
                    revision=revision,
                ),
            )
            if request_source != REQUEST_SOURCE_MODEL_TEST and not is_provider_backed_model(
                model_info,
            ):
                await lifecycle.circuit_breakers.record_cb_success(plugin_name)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to update stats/callbacks for [{execution_universal_id}]",
            operation=OPERATION_ORCHESTRATOR_UPDATE_STATS_AND_CALLBACKS,
        )
