"""SoAI - Agent streaming inference stream generator [backend/features/agent/runtime/streaming_inference_stream_generator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamGeneratorStateProtocol
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.api.streaming.task_stream_generator import build_task_stream_generator

if TYPE_CHECKING:
    from core.tasks.task import Task
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("build_agent_stream_generator",)


def build_agent_stream_generator(
    api_dependencies: ApiDependencies,
    *,
    context: RequestContext,
    task: Task,
    reply_queue: asyncio.Queue[Event],
    model: str | None,
    include_usage: bool,
    emit_done_marker: bool,
    stream_transcript: OpenAIStreamTranscript | None,
    stream_result_state: StreamGeneratorStateProtocol | None,
) -> AsyncGenerator[bytes]:
    return build_task_stream_generator(
        api_dependencies,
        reply_queue=reply_queue,
        stream_dependencies=build_stream_dependencies(api_dependencies),
        context=context,
        task=task,
        stream_transcript=stream_transcript,
        model=model,
        emit_done_marker=emit_done_marker,
        schedule_tool_calls=False,
        stream_state=stream_result_state,
        include_usage=include_usage,
    ).stream_generator
