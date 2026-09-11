"""SoAI - Shared assistant timeline visible success finalization [backend/features/assistant_timeline/stream_finalize_success_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.conversations.assistant_terminal_finalization import (
    TerminalAssistantMessageFinalization,
)
from core.openai.usage.serialization import is_aggregate_usage_source
from core.types.json import JSONDict
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
    TIMELINE_ACTIVITY_STATUS_RUNNING,
)
from features.assistant_timeline.loading_activity_payloads import (
    build_loading_activity_payload,
)
from features.assistant_timeline.processing_activity import (
    complete_processing_activity_if_running,
)
from features.assistant_timeline.publish import publish_chat_stream_event
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.stream_finalize_success_state import (
    ChatStreamSuccessSnapshot,
)
from features.assistant_timeline.stream_finalize_support import (
    flush_pending_visible_text_deltas,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    complete_chat_stream_terminal_finalization,
)
from features.assistant_timeline.terminal_event_publication import (
    persist_and_publish_terminal_chat_stream_event,
)
from features.assistant_timeline.tool_call_terminal_event_synthesis import (
    synthesize_terminal_tool_call_events,
)
from features.assistant_timeline.tool_events_flushing import flush_pending_tool_events
from features.assistant_timeline.usage_preview_tracking import (
    finalize_runtime_usage_preview,
    freeze_runtime_usage_preview,
)
from features.assistant_timeline.wait_for_user_activity import (
    complete_wait_for_user_activity_if_running,
)

__all__ = ("finalize_visible_chat_stream_success",)


def _finalize_terminal_usage_preview(
    *,
    context: ChatStreamFinalizeContext,
    snapshot: ChatStreamSuccessSnapshot,
) -> JSONDict | None:
    usage = snapshot.usage
    if usage is None:
        return freeze_runtime_usage_preview(runtime=context.runtime)
    context_usage = snapshot.context_usage
    if context_usage is not None:
        context_completion_tokens = context_usage.completion_tokens
    elif not is_aggregate_usage_source(usage.usage_source):
        context_completion_tokens = usage.completion_tokens
    else:
        return freeze_runtime_usage_preview(runtime=context.runtime)
    return finalize_runtime_usage_preview(
        runtime=context.runtime,
        usage_prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        context_completion_tokens=context_completion_tokens,
        usage_source=usage.usage_source,
    )


async def finalize_visible_chat_stream_success(
    *,
    context: ChatStreamFinalizeContext,
    snapshot: ChatStreamSuccessSnapshot,
    flush_pending_tool_events_before_terminal_synthesis: bool,
) -> None:
    await complete_wait_for_user_activity_if_running(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
    )
    await complete_processing_activity_if_running(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
    )
    loading_was_running = (
        context.runtime.loading_activity.status == TIMELINE_ACTIVITY_STATUS_RUNNING
    )
    loading_duration_ms = (
        context.runtime.loading_activity.duration_ms
        if context.runtime.loading_activity.status == TIMELINE_ACTIVITY_STATUS_COMPLETED
        else snapshot.duration_ms
    )
    if loading_was_running:
        context.runtime.loading_activity.status = TIMELINE_ACTIVITY_STATUS_COMPLETED
        context.runtime.loading_activity.duration_ms = snapshot.duration_ms
        loading_completed = build_loading_activity_payload(
            runtime=context.runtime,
            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
            duration_ms=loading_duration_ms,
        )
        await publish_chat_stream_event(
            context.event_bus,
            context.runtime,
            context.database_messages,
            event_type="loading_activity",
            payload={
                "assistant_at_ms": context.runtime.assistant_at_ms,
                "loading_activity": loading_completed,
            },
        )
    await flush_pending_visible_text_deltas(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
        database_messages=context.database_messages,
        event_bus=context.event_bus,
        pending_visible_text=snapshot.pending_visible_text,
    )
    if flush_pending_tool_events_before_terminal_synthesis:
        await flush_pending_tool_events(
            event_bus=context.event_bus,
            runtime=context.runtime,
            database_messages=context.database_messages,
            database_tool_calls=context.database_tool_calls,
        )
    await synthesize_terminal_tool_call_events(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        database_tool_calls=context.database_tool_calls,
        task_registry=context.task_registry,
        status="error",
        message=snapshot.tool_call_terminal_message,
        preserve_active_owned_tool_calls=True,
    )
    usage_preview = _finalize_terminal_usage_preview(
        context=context,
        snapshot=snapshot,
    )
    await persist_and_publish_terminal_chat_stream_event(
        event_bus=context.event_bus,
        runtime=context.runtime,
        database_messages=context.database_messages,
        event_type="completed",
        payload={
            "assistant_at_ms": context.runtime.assistant_at_ms,
            "finish_reason": snapshot.finish_reason,
            "usage": (
                snapshot.usage.as_public_usage_payload() if snapshot.usage is not None else {}
            ),
            "usage_preview": dict(usage_preview) if usage_preview is not None else None,
        },
        finalization=TerminalAssistantMessageFinalization(
            finish_reason=snapshot.finish_reason,
            prompt_tokens=(snapshot.usage.prompt_tokens if snapshot.usage is not None else None),
            completion_tokens=(
                snapshot.usage.completion_tokens if snapshot.usage is not None else None
            ),
            total_tokens=(snapshot.usage.total_tokens if snapshot.usage is not None else None),
            usage_source=(snapshot.usage.usage_source if snapshot.usage is not None else None),
            generation_latency_ms=snapshot.duration_ms,
            thinking_tail_duration_ms=snapshot.thinking_tail_duration_ms,
            terminal_reason=None,
            terminal_code="completed",
        ),
    )
    await complete_chat_stream_terminal_finalization(context)
