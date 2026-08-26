"""SoAI - Orchestrator streaming result resolution [backend/orchestrator/execution/streaming_result_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.streaming_usage import StreamingUsageCollection
from core.openai.token_counter import PromptTokenCounter
from core.openai.usage.resolution import resolve_canonical_usage
from core.openai.usage.serialization import build_internal_usage_payload
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from orchestrator.execution.billing import perform_billing_record, resolve_prompt_tokens

if TYPE_CHECKING:
    from core.openai.protocols_usage import CompletionTokenTranscriptProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_stream_transcript",
    "resolve_streaming_usage",
)

LOGGER_NAME = "SoAI.orchestrator.execution.streaming_result_resolution"


def build_stream_transcript(
    *,
    queue: OrchestratorQueueProtocol,
    task: Task,
) -> OpenAIStreamTranscript:
    context = queue.require_orchestration_context(task)
    event = context.event
    payload = event.payload if event is not None else None
    requested_model = payload.get("model") if isinstance(payload, dict) else None
    model_hint = requested_model if isinstance(requested_model, str) else None
    return OpenAIStreamTranscript(model_hint=model_hint)


def resolve_streaming_usage(
    *,
    queue: OrchestratorQueueProtocol,
    prompt_token_counter: PromptTokenCounter,
    metrics: MetricsManagerProtocol,
    task: Task,
    model_info: JSONDict,
    plugin_name: str,
    transcript: CompletionTokenTranscriptProtocol,
    usage_collection: StreamingUsageCollection,
) -> JSONDict | None:
    model_value = model_info.get("model_id")
    model_name = model_value if isinstance(model_value, str) and model_value else None
    resolution = resolve_canonical_usage(
        transcript=transcript,
        explicit_usage_payload=(
            usage_collection.usage_value
            if usage_collection.usage_value is not None
            else transcript.get_reported_usage()
        ),
        prompt_tokens_hint=resolve_prompt_tokens(task),
        prompt_token_counter=prompt_token_counter,
        model_name=model_name,
    )
    if resolution.status not in {"accepted", "absent"}:
        get_logger(LOGGER_NAME).warning(
            "Rejected provider usage for task %s; reconstructed usage from transcript (%s).",
            task.task_id,
            resolution.status,
        )
    canonical_usage = resolution.usage
    perform_billing_record(
        queue=queue,
        metrics=metrics,
        task=task,
        model_info=model_info,
        tokens=canonical_usage.total_tokens,
        plugin_name=plugin_name,
    )
    return build_internal_usage_payload(canonical_usage)
