"""SoAI - OpenAI route streaming runner overrides [backend/features/api/streaming/openai_streaming_runner_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException

from core.errors.exceptions import ApiError
from core.openai.chat_messages_contracts import (
    is_internal_chat_messages_tool_sequence_contract_violation_message,
)
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId
from features.agent.runtime.streaming_inference_runner import (
    StreamingTaskCreationAbortedError,
    StreamingTaskCreationRetryableError,
)
from features.agent.runtime.types import StreamingRunnerCallbackBases
from features.api.routes.openai.agent_inference_task_creation import (
    create_agent_inference_task,
)
from features.api.routes.openai.agent_streaming_http_error_emission import (
    emit_api_error_and_build_outcome,
    emit_http_exception_and_build_outcome,
)
from features.api.streaming.task_stream_generator import build_task_stream_generator
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("build_openai_streaming_runner_overrides",)


def build_openai_streaming_runner_overrides(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    trace_id: str,
    task_type: TaskTypeId,
    owner_type: str,
    owner_id: str,
    format_error_chunk: Callable[[str, str, str], str] | None,
    model: str | None,
    event_type_label: str,
) -> StreamingRunnerCallbackBases:
    normalized_trace_id = str(trace_id or "").strip()

    async def create_additional_task(
        payload: JSONDict,
        iteration_context: RequestContext,
        effective_cancellation_id: str,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
    ) -> tuple[Task, asyncio.Queue[Event]]:
        try:
            task_bundle = await create_agent_inference_task(
                request,
                api_context,
                context=iteration_context,
                payload=payload,
                task_type=task_type,
                owner_type=owner_type,
                owner_id=owner_id,
                cancellation_id=effective_cancellation_id,
                event_type_label=event_type_label,
            )
            return (task_bundle.task, task_bundle.reply_queue)
        except ApiError as exception:
            if is_internal_chat_messages_tool_sequence_contract_violation_message(
                exception.message,
            ):
                raise StreamingTaskCreationRetryableError(
                    error_message=exception.message,
                    error_type=str(exception.code),
                ) from exception
            outcome = await emit_api_error_and_build_outcome(
                exception,
                format_error_chunk=format_error_chunk,
                trace_id=normalized_trace_id,
                on_bytes=on_bytes,
            )
            raise StreamingTaskCreationAbortedError(outcome) from exception
        except HTTPException as exception:
            outcome = await emit_http_exception_and_build_outcome(
                exception,
                format_error_chunk=format_error_chunk,
                trace_id=normalized_trace_id,
                on_bytes=on_bytes,
            )
            raise StreamingTaskCreationAbortedError(outcome) from exception

    def create_generator(
        reply_queue: asyncio.Queue[Event],
        stream_context: RequestContext,
        task: Task,
        stream_state: StreamGeneratorStateProtocol,
        stream_transcript: OpenAIStreamTranscript,
    ) -> AsyncIterator[bytes]:
        return build_task_stream_generator(
            api_context.dependencies,
            reply_queue=reply_queue,
            stream_dependencies=stream_dependencies,
            context=stream_context,
            task=task,
            format_error_chunk=format_error_chunk,
            stream_transcript=stream_transcript,
            model=model,
            emit_done_marker=False,
            schedule_tool_calls=False,
            include_usage=False,
            stream_state=stream_state,
        ).stream_generator

    return StreamingRunnerCallbackBases(
        create_additional_task=create_additional_task,
        create_stream_generator=create_generator,
    )
