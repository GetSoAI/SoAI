"""SoAI - Plugin slot inference execution [backend/orchestrator/execution/plugin_slot_inference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import AsyncIterable
from functools import partial
from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ApiError, IpcRemoteRequestError, StateError
from core.errors.external_service_exception import ExternalServiceError
from core.events.types_models_requests import InferenceRequestReceived
from core.logging.protocols import TraceLogger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.model_context import ModelContext
from core.openai.chat_template_role_policy_resolver import (
    ChatTemplateRolePolicyResolver,
    is_chat_template_role_policy_rejection,
)
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.tasks.execution_budget import ExecutionLimit
from core.tasks.protocols import TaskFinalizerTrackerProtocol, TaskRegistryProtocol
from core.tasks.task import Task
from core.types.json import JSONDict
from orchestrator.execution.execution_phase_timeouts import (
    ExecutionPhase,
    admit_inference_execution_budget,
    await_within_execution_budget,
    execution_phase_timeout_error,
)
from orchestrator.execution.internal_protocols import (
    ActiveInferenceRegistryProtocol,
    OutcomeManagerProtocol,
    ResultProcessorProtocol,
)
from orchestrator.execution.plugin_slot_streaming import (
    prefetch_first_stream_item,
    yield_prefetched_then_iterate,
)
from orchestrator.execution.result_handlers import (
    buffer_stream_to_result,
    handle_streaming_result,
    handle_unary_result,
)
from orchestrator.execution.retry_policy import resolve_execution_retry_decision
from orchestrator.execution.retry_progress import log_retry_then_backoff
from orchestrator.execution.streaming import StreamingSourceTimeoutError

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = ("execute_plugin_inference_request",)

_RETRY_LOG_MESSAGE_BEFORE_STREAMING = (
    "Task %s inference attempt %s/%s failed before streaming began (%s). Retrying."
)
_RETRY_LOG_MESSAGE_BUFFERED_STREAMING = (
    "Task %s inference attempt %s/%s failed during buffered streaming (%s). Retrying."
)
_INFERENCE_ATTEMPT_EXCEPTIONS: tuple[type[Exception], ...] = (
    ExternalServiceError,
    ApiError,
    IpcRemoteRequestError,
    httpx2.HTTPStatusError,
    httpx2.RequestError,
)


async def execute_plugin_inference_request(
    results: ResultProcessorProtocol,
    outcomes: OutcomeManagerProtocol,
    *,
    metrics: MetricsManagerProtocol,
    task_registry: TaskRegistryProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    task: Task,
    plugin_instance: PluginInstanceProtocol,
    prepared_payload: JSONDict,
    model_info: JSONDict,
    plugin_name: str,
    model_context: ModelContext,
    request_limit: ExecutionLimit,
    first_chunk_limit: ExecutionLimit,
    event: InferenceRequestReceived,
    logger: TraceLogger,
    delivery_to_user: bool,
    requested_stream: bool,
    max_execution_retries: int,
    usage_reporting_requested: bool,
    role_policy_resolver: ChatTemplateRolePolicyResolver,
    active_inferences: ActiveInferenceRegistryProtocol,
    health_check_config: JSONDict | None = None,
) -> tuple[Task, bool]:
    task, execution_budget = await admit_inference_execution_budget(
        task_registry=task_registry,
        active_inferences=active_inferences,
        task=task,
        limit=first_chunk_limit if requested_stream else request_limit,
        health_check_config=health_check_config,
    )
    if execution_budget is None:
        return (task, False)
    execution_deadline = execution_budget.deadline
    request_phase = ExecutionPhase.INITIAL_RESPONSE if requested_stream else ExecutionPhase.RESPONSE
    replayable_stream: AsyncIterable[StreamChunk] | None = None
    last_attempt_exception: Exception | None = None
    replayable_stream_success_policy: str | None = None
    candidate_payloads = await role_policy_resolver.build_candidate_payloads(
        prepared_payload,
        model_context,
    )
    for candidate_index, candidate in enumerate(candidate_payloads):
        role_policy = candidate.policy
        candidate_payload = candidate.payload
        has_next_candidate = candidate_index + 1 < len(candidate_payloads)
        for attempt in range(1, max_execution_retries + 1):
            current_task = await task_registry.get(task.task_id)
            if current_task is None or current_task.status.is_terminal():
                return (current_task or task, False)
            if execution_deadline.remaining_seconds() <= 0:
                raise execution_phase_timeout_error(
                    execution_budget,
                    request_phase,
                    wait_started_monotonic=time.monotonic(),
                    limit_seconds=0.0,
                ) from last_attempt_exception
            try:
                result = await await_within_execution_budget(
                    plugin_instance.handle_request(candidate_payload, event.context, model_context),
                    budget=execution_budget,
                    phase=request_phase,
                    task_registry=task_registry,
                    task=task,
                )
                if isinstance(result, dict):
                    result = handle_unary_result(
                        results,
                        task,
                        model_info,
                        result,
                        plugin_name=plugin_name,
                    )
            except _INFERENCE_ATTEMPT_EXCEPTIONS as exception:
                if is_chat_template_role_policy_rejection(exception):
                    if not has_next_candidate:
                        raise
                    last_attempt_exception = exception
                    logger.warning(
                        "Task %s backend rejected chat-template role policy '%s'. Retrying with next policy.",
                        task.task_id,
                        role_policy,
                    )
                    break
                retry_decision = resolve_execution_retry_decision(
                    exception,
                    attempt=attempt,
                    remaining_seconds=execution_deadline.remaining_seconds(),
                )
                if not retry_decision.should_retry:
                    raise
                last_attempt_exception = exception
                await log_retry_then_backoff(
                    exception,
                    attempt=attempt,
                    decision=retry_decision,
                    metrics=metrics,
                    task_registry=task_registry,
                    task=task,
                    plugin_name=plugin_name,
                    logger=logger,
                    retry_message=_RETRY_LOG_MESSAGE_BEFORE_STREAMING,
                )
                continue

            if isinstance(result, dict):
                if candidate.cacheable:
                    await role_policy_resolver.record_success(model_context, role_policy)
                await outcomes.succeed_task(task, result=result)
                return (task, True)
            if not isinstance(result, AsyncIterable):
                raise StateError(
                    "Plugin returned an unsupported streaming result type for inference request.",
                )

            if not delivery_to_user:
                try:
                    buffered = await await_within_execution_budget(
                        buffer_stream_to_result(
                            results,
                            task,
                            model_info,
                            result,
                            plugin_name=plugin_name,
                        ),
                        budget=execution_budget,
                        phase=ExecutionPhase.BUFFERED_RESPONSE,
                        task_registry=task_registry,
                        task=task,
                    )
                except _INFERENCE_ATTEMPT_EXCEPTIONS as exception:
                    if is_chat_template_role_policy_rejection(exception):
                        if not has_next_candidate:
                            raise
                        last_attempt_exception = exception
                        logger.warning(
                            "Task %s buffered stream rejected chat-template role policy '%s'. Retrying with next policy.",
                            task.task_id,
                            role_policy,
                        )
                        break
                    retry_decision = resolve_execution_retry_decision(
                        exception,
                        attempt=attempt,
                        remaining_seconds=execution_deadline.remaining_seconds(),
                    )
                    if not retry_decision.should_retry:
                        raise
                    last_attempt_exception = exception
                    await log_retry_then_backoff(
                        exception,
                        attempt=attempt,
                        decision=retry_decision,
                        metrics=metrics,
                        task_registry=task_registry,
                        task=task,
                        plugin_name=plugin_name,
                        logger=logger,
                        retry_message=_RETRY_LOG_MESSAGE_BUFFERED_STREAMING,
                    )
                    continue
                if candidate.cacheable:
                    await role_policy_resolver.record_success(model_context, role_policy)
                await outcomes.succeed_task(task, result=buffered)
                return (task, True)

            prefetch_started = time.monotonic()
            prefetch_limit = min(first_chunk_limit.seconds, execution_deadline.remaining_seconds())
            try:
                first_item, iterator = await prefetch_first_stream_item(
                    result,
                    timeout=prefetch_limit,
                    task_registry=task_registry,
                    task=task,
                    timeout_error=partial(
                        execution_phase_timeout_error,
                        execution_budget,
                        ExecutionPhase.FIRST_TOKEN,
                        wait_started_monotonic=prefetch_started,
                        limit_seconds=prefetch_limit,
                        phase_cap=first_chunk_limit,
                    ),
                )
            except TimeoutError as exception:
                raise StreamingSourceTimeoutError(first_chunk_limit.seconds) from exception
            except _INFERENCE_ATTEMPT_EXCEPTIONS as exception:
                if is_chat_template_role_policy_rejection(exception):
                    if not has_next_candidate:
                        raise
                    last_attempt_exception = exception
                    logger.warning(
                        "Task %s stream prefetch rejected chat-template role policy '%s'. Retrying with next policy.",
                        task.task_id,
                        role_policy,
                    )
                    break
                retry_decision = resolve_execution_retry_decision(
                    exception,
                    attempt=attempt,
                    remaining_seconds=execution_deadline.remaining_seconds(),
                )
                if not retry_decision.should_retry:
                    raise
                last_attempt_exception = exception
                await log_retry_then_backoff(
                    exception,
                    attempt=attempt,
                    decision=retry_decision,
                    metrics=metrics,
                    task_registry=task_registry,
                    task=task,
                    plugin_name=plugin_name,
                    logger=logger,
                    retry_message=_RETRY_LOG_MESSAGE_BEFORE_STREAMING,
                )
                continue
            if candidate.cacheable:
                replayable_stream_success_policy = role_policy
            replayable_stream = yield_prefetched_then_iterate(
                first_item, iterator, finalizer_tracker=finalizer_tracker
            )
            break
        if replayable_stream is not None:
            break

    if replayable_stream is None:
        if last_attempt_exception is not None:
            raise last_attempt_exception
        raise StateError("Execution retry loop exited unexpectedly.")
    streaming_completion = await handle_streaming_result(
        results,
        task,
        model_info,
        replayable_stream,
        usage_reporting_requested=usage_reporting_requested,
        plugin_name=plugin_name,
    )
    current_task = await task_registry.get(task.task_id)
    if current_task is not None and current_task.status.is_terminal():
        return (current_task, False)
    if replayable_stream_success_policy is not None:
        await role_policy_resolver.record_success(model_context, replayable_stream_success_policy)
    await outcomes.succeed_task(
        task,
        is_streaming=True,
        streaming_completion=streaming_completion,
    )
    return (task, True)
