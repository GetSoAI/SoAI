"""SoAI - Plugin slot inference execution [backend/orchestrator/execution/plugin_slot_inference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ApiError, IpcRemoteRequestError, StateError
from core.errors.external_service_exception import ExternalServiceError
from core.events.types_models_requests import InferenceRequestReceived
from core.logging.protocols import TraceLogger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.model_context import ModelContext
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.types.json import JSONDict
from orchestrator.execution.chat_template_role_policy import (
    ChatTemplateRolePolicyResolver,
    is_chat_template_role_policy_rejection,
)
from orchestrator.execution.internal_protocols import (
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
    task: Task,
    plugin_instance: PluginInstanceProtocol,
    prepared_payload: JSONDict,
    model_info: JSONDict,
    plugin_name: str,
    model_context: ModelContext,
    request_timeout: float,
    first_chunk_timeout: float,
    event: InferenceRequestReceived,
    logger: TraceLogger,
    delivery_to_user: bool,
    max_execution_retries: int,
    usage_reporting_requested: bool,
    role_policy_resolver: ChatTemplateRolePolicyResolver,
) -> tuple[Task, bool]:
    execution_deadline = asyncio.get_running_loop().time() + request_timeout
    replayable_stream: AsyncIterable[StreamChunk] | None = None
    role_policy_exception: Exception | None = None
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
            remaining = execution_deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError
            try:
                result = await asyncio.wait_for(
                    plugin_instance.handle_request(candidate_payload, event.context, model_context),
                    timeout=remaining,
                )
            except _INFERENCE_ATTEMPT_EXCEPTIONS as exception:
                if is_chat_template_role_policy_rejection(exception):
                    if not has_next_candidate:
                        raise
                    role_policy_exception = exception
                    logger.warning(
                        "Task %s backend rejected chat-template role policy '%s'. Retrying with next policy.",
                        task.task_id,
                        role_policy,
                    )
                    break
                retry_decision = resolve_execution_retry_decision(exception, attempt=attempt)
                if not retry_decision.should_retry:
                    raise
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
                unary = handle_unary_result(
                    results,
                    task,
                    model_info,
                    result,
                    plugin_name=plugin_name,
                )
                if candidate.cacheable:
                    await role_policy_resolver.record_success(model_context, role_policy)
                await outcomes.succeed_task(task, result=unary)
                return (task, True)
            if not isinstance(result, AsyncIterable):
                raise StateError(
                    "Plugin returned an unsupported streaming result type for inference request.",
                )

            if not delivery_to_user:
                try:
                    buffered = await buffer_stream_to_result(
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
                        role_policy_exception = exception
                        logger.warning(
                            "Task %s buffered stream rejected chat-template role policy '%s'. Retrying with next policy.",
                            task.task_id,
                            role_policy,
                        )
                        break
                    retry_decision = resolve_execution_retry_decision(exception, attempt=attempt)
                    if not retry_decision.should_retry:
                        raise
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

            try:
                first_item, iterator = await prefetch_first_stream_item(
                    result,
                    timeout=first_chunk_timeout,
                )
            except TimeoutError as exception:
                raise StreamingSourceTimeoutError(first_chunk_timeout) from exception
            except _INFERENCE_ATTEMPT_EXCEPTIONS as exception:
                if is_chat_template_role_policy_rejection(exception):
                    if not has_next_candidate:
                        raise
                    role_policy_exception = exception
                    logger.warning(
                        "Task %s stream prefetch rejected chat-template role policy '%s'. Retrying with next policy.",
                        task.task_id,
                        role_policy,
                    )
                    break
                retry_decision = resolve_execution_retry_decision(exception, attempt=attempt)
                if not retry_decision.should_retry:
                    raise
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
            replayable_stream = yield_prefetched_then_iterate(first_item, iterator)
            break
        if replayable_stream is not None:
            break

    if replayable_stream is None:
        if role_policy_exception is not None:
            raise role_policy_exception
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
