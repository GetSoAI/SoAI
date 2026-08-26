"""SoAI - Orchestrator streaming result handling [backend/orchestrator/execution/streaming_result_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol, TokenStreamMetricsProtocol
from core.openai.streaming_usage import StreamingUsageCollector
from core.openai.token_counter import PromptTokenCounter
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import (
    TASK_TYPE_IMAGE_EDIT,
    TASK_TYPE_IMAGE_GENERATION,
    TASK_TYPE_IMAGE_VARIATION,
    TaskTypeId,
)
from orchestrator.execution.billing import requires_api_key_token_accounting
from orchestrator.execution.image_sse_transcript import ImageSSETranscript
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.streaming_completion import StreamingCompletion
from orchestrator.execution.streaming_result_resolution import resolve_streaming_usage
from orchestrator.execution.streaming_sse_flow import (
    build_streaming_final_result,
    process_streaming_sse_flow,
)

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict

__all__ = (
    "handle_streaming_lightweight",
    "handle_streaming_with_usage_parsing",
    "should_parse_streaming_usage",
)

LOGGER_NAME = "SoAI.orchestrator.execution.streaming_result_handling"
_IMAGE_STREAMING_TASK_TYPES: frozenset[TaskTypeId] = frozenset(
    {
        TASK_TYPE_IMAGE_GENERATION,
        TASK_TYPE_IMAGE_EDIT,
        TASK_TYPE_IMAGE_VARIATION,
    },
)


async def handle_streaming_lightweight(
    *,
    queue: OrchestratorQueueProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    task: Task,
    result: AsyncIterable[StreamChunk],
    tracking_id: str,
    streaming_chunk_delivery_timeout: float,
    first_chunk_timeout: float,
    streaming_idle_timeout: float,
    prompt_token_counter: PromptTokenCounter,
    metrics: TokenStreamMetricsProtocol,
    plugin_name: str,
    model_name: str | None = None,
) -> StreamingCompletion:
    logger = get_logger(LOGGER_NAME)
    image_transcript = (
        ImageSSETranscript() if task.task_type in _IMAGE_STREAMING_TASK_TYPES else None
    )
    flow_result = await process_streaming_sse_flow(
        queue=queue,
        active_inferences=active_inferences,
        task=task,
        result=result,
        tracking_id=tracking_id,
        streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
        first_chunk_timeout=first_chunk_timeout,
        streaming_idle_timeout=streaming_idle_timeout,
        operation="orchestrator.handle_streaming_result.lightweight",
        logger=logger,
        include_transcript=image_transcript is None,
        image_transcript=image_transcript,
        usage_collector=None,
        metrics=metrics,
        prompt_token_counter=prompt_token_counter,
        plugin_name=plugin_name,
        model_name=model_name,
    )
    final_result = build_streaming_final_result(flow_result)
    return StreamingCompletion(
        usage=None,
        final_result=final_result,
        deferred_terminal_chunks=flow_result.deferred_terminal_chunks,
        chunk_delivery_timeout_seconds=(
            streaming_chunk_delivery_timeout if flow_result.deferred_terminal_chunks else None
        ),
    )


async def handle_streaming_with_usage_parsing(
    *,
    queue: OrchestratorQueueProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    prompt_token_counter: PromptTokenCounter,
    metrics: MetricsManagerProtocol,
    model_info: JSONDict,
    task: Task,
    plugin_name: str,
    model_name: str | None = None,
    result: AsyncIterable[StreamChunk],
    tracking_id: str,
    streaming_chunk_delivery_timeout: float,
    first_chunk_timeout: float,
    streaming_idle_timeout: float,
) -> StreamingCompletion:
    logger = get_logger(LOGGER_NAME)
    image_transcript = (
        ImageSSETranscript() if task.task_type in _IMAGE_STREAMING_TASK_TYPES else None
    )
    usage_collector = StreamingUsageCollector()
    flow_result = await process_streaming_sse_flow(
        queue=queue,
        active_inferences=active_inferences,
        task=task,
        result=result,
        tracking_id=tracking_id,
        streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
        first_chunk_timeout=first_chunk_timeout,
        streaming_idle_timeout=streaming_idle_timeout,
        operation="orchestrator.handle_streaming_result.with_usage",
        logger=logger,
        include_transcript=True,
        image_transcript=image_transcript,
        usage_collector=usage_collector,
        metrics=metrics,
        prompt_token_counter=prompt_token_counter,
        plugin_name=plugin_name,
        model_name=model_name,
    )
    usage_transcript = (
        flow_result.responses_transcript
        or flow_result.transcription_transcript
        or flow_result.transcript
    )
    if usage_transcript is None:
        raise StateError("Streaming usage parsing completed without a transcript.")
    internal_usage = resolve_streaming_usage(
        queue=queue,
        prompt_token_counter=prompt_token_counter,
        metrics=metrics,
        task=task,
        model_info=model_info,
        plugin_name=plugin_name,
        transcript=usage_transcript,
        usage_collection=usage_collector.finalize(),
    )
    final_result = build_streaming_final_result(flow_result, usage=internal_usage)
    return StreamingCompletion(
        usage=internal_usage,
        final_result=final_result,
        deferred_terminal_chunks=flow_result.deferred_terminal_chunks,
        chunk_delivery_timeout_seconds=(
            streaming_chunk_delivery_timeout if flow_result.deferred_terminal_chunks else None
        ),
    )


def should_parse_streaming_usage(*, task: Task, usage_reporting_requested: bool) -> bool:
    return usage_reporting_requested or requires_api_key_token_accounting(task)
