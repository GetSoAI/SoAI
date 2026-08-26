"""SoAI - Shared assistant timeline stream chunk processing [backend/features/assistant_timeline/stream_chunk_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.stream_frame_processing import process_openai_stream_frame
from core.openai.streaming_image_segments import extract_openai_streaming_image_urls
from core.tool_calls.chronology import resolve_required_non_negative_integer
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
)
from features.assistant_timeline.assistant_images import (
    persist_and_publish_assistant_image,
)
from features.assistant_timeline.assistant_text import (
    flush_assistant_visible_chronology,
    persist_and_publish_assistant_text_delta,
)
from features.assistant_timeline.loading_activity import (
    mark_loading_completed_if_running,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.stream_finalize_context import (
    build_chat_stream_finalize_context,
)
from features.assistant_timeline.stream_tool_call_events import (
    queue_synthetic_tool_call_created_if_missing,
)
from features.assistant_timeline.thinking_phase import (
    normalize_thinking_phase_text_for_rendering,
)
from features.assistant_timeline.thinking_phase_tail_finalization import (
    finalize_thinking_tail_phase_for_context,
)
from features.assistant_timeline.thinking_phase_updates import (
    ThinkingPhaseState,
    coerce_thinking_call_id,
    finalize_thinking_phase_before_tool_call,
    upsert_intermediate_thinking_phase,
)
from features.assistant_timeline.usage_preview_tracking import (
    update_runtime_completion_usage_preview_if_due,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.openai.token_counter import PromptTokenCounter
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = ("process_stream_chunk",)


def has_unfinalized_thinking_text(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
) -> bool:
    thinking_text = stream_transcript.get_thinking_text()
    start_cursor = max(0, runtime.thinking_phase_cursor)
    if len(thinking_text) <= start_cursor:
        return False
    return bool(normalize_thinking_phase_text_for_rendering(thinking_text[start_cursor:]).strip())


async def process_stream_chunk(
    *,
    decoded_chunk: str,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    prompt_token_counter: PromptTokenCounter,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryLifecycleView,
    event_bus: EventBusProtocol,
) -> bool:
    stream_frame = process_openai_stream_frame(decoded_chunk)
    if not stream_frame.filtered_text.strip():
        return not stream_frame.done_marker_observed
    finalize_context = build_chat_stream_finalize_context(
        runtime,
        stream_transcript,
        thinking_phases,
        thinking_state,
        database_messages,
        database_tool_calls,
        task_registry,
        event_bus,
    )
    stream_transcript.feed(stream_frame.filtered_text)
    update_runtime_completion_usage_preview_if_due(
        runtime=runtime,
        stream_transcript=stream_transcript,
        prompt_token_counter=prompt_token_counter,
    )
    visible_deltas = stream_transcript.drain_visible_text_deltas()
    delta_text = "".join(visible_deltas) if visible_deltas else ""
    image_urls = extract_openai_streaming_image_urls(decoded_chunk)
    new_calls = stream_transcript.drain_new_tool_calls()
    has_output_token = (
        bool(delta_text)
        or bool(image_urls)
        or bool(new_calls)
        or stream_transcript.get_thinking_char_count() > 0
    )
    if has_output_token:
        await mark_loading_completed_if_running(
            runtime=runtime,
            event_bus=event_bus,
            database_messages=database_messages,
        )
    if not new_calls:
        thinking_closed = stream_transcript.drain_thinking_close_events() > 0
        should_finalize_before_visible_text = bool(delta_text) and has_unfinalized_thinking_text(
            runtime=runtime,
            stream_transcript=stream_transcript,
        )
        if thinking_closed or should_finalize_before_visible_text:
            await finalize_thinking_tail_phase_for_context(
                context=finalize_context,
                status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
            )
        else:
            await upsert_intermediate_thinking_phase(
                runtime=runtime,
                stream_transcript=stream_transcript,
                thinking_phases=thinking_phases,
                thinking_state=thinking_state,
                database_messages=database_messages,
                event_bus=event_bus,
            )
        if image_urls:
            for image_url in image_urls:
                await persist_and_publish_assistant_image(
                    runtime=runtime,
                    image_url=image_url,
                    database_messages=database_messages,
                    event_bus=event_bus,
                )
        if delta_text:
            await persist_and_publish_assistant_text_delta(
                runtime=runtime,
                delta_text=delta_text,
                database_messages=database_messages,
                event_bus=event_bus,
            )
        return not stream_frame.done_marker_observed
    if image_urls:
        for image_url in image_urls:
            await persist_and_publish_assistant_image(
                runtime=runtime,
                image_url=image_url,
                database_messages=database_messages,
                event_bus=event_bus,
            )
    if delta_text:
        await persist_and_publish_assistant_text_delta(
            runtime=runtime,
            delta_text=delta_text,
            database_messages=database_messages,
            event_bus=event_bus,
        )
    await flush_assistant_visible_chronology(
        runtime=runtime,
        database_messages=database_messages,
        event_bus=event_bus,
    )
    thinking_text = stream_transcript.get_thinking_text()
    for call in new_calls:
        call_id = coerce_thinking_call_id(call.get("id"))
        if not call_id:
            raise ValidationError("Streamed tool call field 'id' must be a non-empty string.")
        canonical_sequence_index = resolve_required_non_negative_integer(
            call.get("sequence_index"),
            "sequence_index",
            field_label="Streamed tool call",
            exception_type=ValidationError,
        )
        boundary = resolve_required_non_negative_integer(
            call.get("thinking_index_before"),
            "thinking_index_before",
            field_label="Streamed tool call",
            exception_type=ValidationError,
        )
        duration_before_value = call.get("thinking_duration_before_ms")
        duration_before = coerce_optional_non_negative_int_strict(duration_before_value)
        content_index_before = resolve_required_non_negative_integer(
            call.get("content_index_before"),
            "content_index_before",
            field_label="Streamed tool call",
            exception_type=ValidationError,
        )
        boundary = max(runtime.thinking_phase_cursor, min(len(thinking_text), max(0, boundary)))
        if not runtime.agent_tool_events_authoritative:
            await queue_synthetic_tool_call_created_if_missing(
                runtime=runtime,
                call=call,
                call_id=call_id,
                content_index_before=content_index_before,
                thinking_index_before=boundary,
                explicit_sequence_index=canonical_sequence_index,
            )
        await finalize_thinking_phase_before_tool_call(
            context=finalize_context,
            call_id=call_id,
            thinking_index_before=boundary,
            content_index_before=content_index_before,
            duration_ms=duration_before,
            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
        )
    await upsert_intermediate_thinking_phase(
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        database_messages=database_messages,
        event_bus=event_bus,
    )
    if stream_transcript.drain_thinking_close_events() > 0:
        await finalize_thinking_tail_phase_for_context(
            context=finalize_context,
            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
        )
    return not stream_frame.done_marker_observed
