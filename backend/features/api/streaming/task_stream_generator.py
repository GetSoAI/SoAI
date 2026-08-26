"""SoAI - Shared task-backed OpenAI stream generator assembly [backend/features/api/streaming/task_stream_generator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.tasks.task import Task
from features.api.streaming.openai_stream_generator.generator import (
    create_stream_generator,
)
from features.api.streaming.stream_generator_state import StreamGeneratorState
from features.api.streaming.task_quota_metadata import (
    read_task_quota_budget_inputs,
    resolve_request_max_completion_tokens,
    resolve_task_stream_model,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.events.types_base import Event
    from features.api.runtime.container.types import ApiDependencies
    from features.api.streaming.types import StreamDependencies

__all__ = (
    "TaskStreamGeneratorBundle",
    "build_task_stream_generator",
)


@dataclass(frozen=True, slots=True)
class TaskStreamGeneratorBundle:
    stream_state: StreamGeneratorStateProtocol
    stream_generator: AsyncGenerator[bytes]


def build_task_stream_generator(
    api_dependencies: ApiDependencies,
    *,
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    task: Task,
    format_error_chunk: Callable[[str, str, str], str] | None = None,
    stream_transcript: OpenAIStreamTranscript | None = None,
    model: str | None,
    emit_done_marker: bool,
    schedule_tool_calls: bool,
    stream_state: StreamGeneratorStateProtocol | None = None,
    include_usage: bool,
    allow_image_events: bool = False,
    collect_tool_calls: bool = True,
) -> TaskStreamGeneratorBundle:
    quota_reservation, quota_prompt_tokens, _model_hint = read_task_quota_budget_inputs(task)
    resolved_model = resolve_task_stream_model(task, model)
    resolved_stream_state = stream_state if stream_state is not None else StreamGeneratorState()
    return TaskStreamGeneratorBundle(
        stream_state=resolved_stream_state,
        stream_generator=create_stream_generator(
            reply_queue,
            stream_dependencies,
            api_dependencies,
            context,
            format_error_chunk=format_error_chunk,
            task_id=task.task_id,
            stream_transcript=stream_transcript,
            model=resolved_model,
            emit_done_marker=emit_done_marker,
            schedule_tool_calls=schedule_tool_calls,
            collect_tool_calls=collect_tool_calls,
            stream_result_state=resolved_stream_state,
            include_usage=include_usage,
            quota_reservation=quota_reservation,
            quota_prompt_tokens=quota_prompt_tokens,
            max_completion_tokens=resolve_request_max_completion_tokens(
                (
                    task.orchestration_context.request_payload
                    if task.orchestration_context is not None
                    else None
                ),
            ),
            allow_image_events=allow_image_events,
        ),
    )
