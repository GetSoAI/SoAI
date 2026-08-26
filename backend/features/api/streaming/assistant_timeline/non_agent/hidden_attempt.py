"""SoAI - Hidden strict non-agent attempt execution [backend/features/api/streaming/assistant_timeline/non_agent/hidden_attempt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.wait_race import (
    WaitRaceOutcome,
    WaitRaceResult,
    wait_for_awaitable_or_event,
)
from core.errors.exceptions import StateError
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.usage.serialization import extract_public_usage_payload
from core.runtime.request_context import RequestContext
from core.tasks.task_cancellation import cancel
from core.validation.strings import coerce_optional_trimmed_str
from features.api.streaming.task_quota_metadata import resolve_task_stream_model
from features.api.streaming.task_stream_generator import build_task_stream_generator
from features.assistant_timeline.assistant_timeline_terminal_support import (
    wait_for_task_terminal_state,
)

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from features.agent.runtime.streaming_inference_admission import (
        AgentStreamingTaskBundle,
    )
    from features.api.runtime.container.types import ApiDependencies
    from features.api.streaming.types import StreamDependencies
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = (
    "HiddenNonAgentAttemptResult",
    "run_hidden_non_agent_attempt",
)

_STREAM_OUTPUT_CONTRACT_ERROR = "OpenAI stream generator yielded a non-bytes chunk."


@dataclass(frozen=True, slots=True)
class HiddenNonAgentAttemptResult:
    refreshed_task: Task | None
    transcript: OpenAIStreamTranscript
    canonical_usage: JSONDict | None
    cancelled: bool


def _coerce_internal_usage_payload(value: JSONDict | None) -> JSONDict | None:
    if not isinstance(value, dict):
        return None
    public_usage = extract_public_usage_payload(value)
    if public_usage is None:
        return None
    usage_source = coerce_optional_trimmed_str(value.get("usage_source"))
    if usage_source is None:
        return None
    return {
        "prompt_tokens": public_usage["prompt_tokens"],
        "completion_tokens": public_usage["completion_tokens"],
        "total_tokens": public_usage["total_tokens"],
        "usage_source": usage_source,
    }


def _require_stream_chunk_bytes(chunk: bytes | bytearray | memoryview | None) -> bytes:
    if not isinstance(chunk, bytes):
        raise StateError(_STREAM_OUTPUT_CONTRACT_ERROR)
    return chunk


async def _cancel_hidden_attempt_task(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    session: AssistantTimelineSession,
) -> None:
    active_task_id = session.runtime.active_task_id
    if not isinstance(active_task_id, str) or not active_task_id:
        return
    await cancel(
        api_dependencies.task_registry,
        active_task_id,
        reason=session.runtime.cancellation_reason or "Chat stream was cancelled.",
        context=context,
    )


async def run_hidden_non_agent_attempt(
    api_dependencies: ApiDependencies,
    *,
    stream_dependencies: StreamDependencies,
    session: AssistantTimelineSession,
    context: RequestContext,
    bundle: AgentStreamingTaskBundle,
    model: str | None,
    include_usage: bool,
    allow_image_events: bool,
    task_lookup: Callable[[str], Awaitable[Task | None]],
) -> HiddenNonAgentAttemptResult:
    async with session.runtime.quota_release_lock:
        session.runtime.active_task_id = bundle.task.task_id
        session.runtime.clear_quota_reservation()
    resolved_model = resolve_task_stream_model(bundle.task, model)
    transcript = OpenAIStreamTranscript(
        model_hint=resolved_model,
        collect_tool_calls=session.collect_tool_calls,
    )
    stream_bundle = build_task_stream_generator(
        api_dependencies,
        reply_queue=bundle.reply_queue,
        stream_dependencies=stream_dependencies,
        context=context,
        task=bundle.task,
        stream_transcript=transcript,
        model=resolved_model,
        emit_done_marker=False,
        schedule_tool_calls=session.collect_tool_calls,
        collect_tool_calls=session.collect_tool_calls,
        include_usage=include_usage,
        allow_image_events=allow_image_events,
    )
    stream_state = stream_bundle.stream_state
    stream_generator = stream_bundle.stream_generator
    stream_generator_closed = False

    async def cancel_stream_generator() -> None:
        nonlocal stream_generator_closed
        if stream_generator_closed:
            return
        close_coro = stream_generator.aclose()
        await uncancel_then_cleanup(close_coro)
        stream_generator_closed = True

    try:
        while True:
            if session.runtime.cancellation_requested:
                await _cancel_hidden_attempt_task(
                    api_dependencies=api_dependencies,
                    context=context,
                    session=session,
                )
                await cancel_stream_generator()
                return HiddenNonAgentAttemptResult(
                    refreshed_task=None,
                    transcript=transcript,
                    canonical_usage=_coerce_internal_usage_payload(stream_state.usage),
                    cancelled=True,
                )
            detach_event = session.runtime.detach_event
            if detach_event is None:
                try:
                    chunk = await anext(stream_generator)
                except StopAsyncIteration:
                    stream_generator_closed = True
                    break
                _require_stream_chunk_bytes(chunk)
                continue
            try:
                race_result: WaitRaceResult[bytes] = await wait_for_awaitable_or_event(
                    anext(stream_generator),
                    detach_event,
                )
            except StopAsyncIteration:
                stream_generator_closed = True
                break
            if race_result.outcome is WaitRaceOutcome.EVENT_TRIGGERED:
                if not session.runtime.cancellation_requested:
                    session.runtime.cancellation_requested = True
                if session.runtime.cancellation_reason is None:
                    session.runtime.cancellation_reason = "Chat stream was cancelled."
                await _cancel_hidden_attempt_task(
                    api_dependencies=api_dependencies,
                    context=context,
                    session=session,
                )
                await cancel_stream_generator()
                return HiddenNonAgentAttemptResult(
                    refreshed_task=None,
                    transcript=transcript,
                    canonical_usage=_coerce_internal_usage_payload(stream_state.usage),
                    cancelled=True,
                )
            _require_stream_chunk_bytes(race_result.value)
        refreshed_task = await wait_for_task_terminal_state(
            task_id=bundle.task.task_id,
            task_lookup=task_lookup,
        )
        return HiddenNonAgentAttemptResult(
            refreshed_task=refreshed_task,
            transcript=transcript,
            canonical_usage=_coerce_internal_usage_payload(stream_state.usage),
            cancelled=False,
        )
    except asyncio.CancelledError:
        await _cancel_hidden_attempt_task(
            api_dependencies=api_dependencies,
            context=context,
            session=session,
        )
        await cancel_stream_generator()
        raise
    finally:
        if not stream_generator_closed:
            await cancel_stream_generator()
