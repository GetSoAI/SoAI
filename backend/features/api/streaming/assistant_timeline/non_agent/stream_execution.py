"""SoAI - Non-agent streaming execution into assistant timeline [backend/features/api/streaming/assistant_timeline/non_agent/stream_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exceptions import ApiError
from core.runtime.request_context import RequestContext
from core.tasks.task import Task
from features.agent.runtime.streaming_inference_admission import (
    AgentStreamingTaskBundle,
)
from features.api.streaming.task_stream_generator import build_task_stream_generator
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_assistant_timeline_non_agentic,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.api.streaming.types import StreamDependencies
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = ("execute_timeline_non_agent_stream",)


async def execute_timeline_non_agent_stream(
    api_dependencies: ApiDependencies,
    *,
    stream_dependencies: StreamDependencies,
    session: AssistantTimelineSession,
    context: RequestContext,
    bundle: AgentStreamingTaskBundle,
    model: str | None,
    include_usage: bool,
    emit_done_marker: bool,
    allow_image_events: bool,
    task_lookup: Callable[[str], Awaitable[Task | None]],
) -> str:
    async with session.runtime.quota_release_lock:
        session.runtime.active_task_id = bundle.task.task_id
        session.runtime.clear_quota_reservation()
    stream_bundle = build_task_stream_generator(
        api_dependencies,
        reply_queue=bundle.reply_queue,
        stream_dependencies=stream_dependencies,
        context=context,
        task=bundle.task,
        stream_transcript=None,
        model=model,
        include_usage=include_usage,
        emit_done_marker=emit_done_marker,
        schedule_tool_calls=session.collect_tool_calls,
        collect_tool_calls=session.collect_tool_calls,
        allow_image_events=allow_image_events,
    )
    try:
        await session.consume_stream(stream_bundle.stream_generator)
    except ApiError as exception:
        if exception.code != "cancelled":
            raise
        raise TaskCancelledError(
            bundle.task.cancellation_id,
            exception.message,
        ) from exception
    await finalize_assistant_timeline_non_agentic(
        session,
        task=bundle.task,
        task_lookup=task_lookup,
    )
    return bundle.task.task_id
