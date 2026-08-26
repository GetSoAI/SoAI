"""SoAI - Assistant timeline text buffering rules [backend/features/assistant_timeline/assistant_text_buffers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "append_assistant_visible_delta",
    "append_pending_delta",
    "drain_pending_delta",
    "should_flush_assistant_content",
    "should_flush_delta_event",
)

ASSISTANT_CONTENT_FLUSH_INTERVAL_MS: int = 300
ASSISTANT_CONTENT_FLUSH_CHAR_THRESHOLD: int = 1024
ASSISTANT_DELTA_FLUSH_MIN_CHARS: int = 256
ASSISTANT_DELTA_FLUSH_MAX_DELAY_MS: int = 33


def append_assistant_visible_delta(runtime: AssistantTimelineRuntime, delta_text: str) -> None:
    runtime.assistant_visible_chunks.append(delta_text)
    runtime.assistant_visible_chars += len(delta_text)


def append_pending_delta(runtime: AssistantTimelineRuntime, delta_text: str) -> None:
    runtime.assistant_delta_buffer.append(delta_text)
    runtime.assistant_delta_buffer_chars += len(delta_text)


def drain_pending_delta(runtime: AssistantTimelineRuntime) -> str:
    if not runtime.assistant_delta_buffer:
        return ""
    if len(runtime.assistant_delta_buffer) == 1:
        drained = runtime.assistant_delta_buffer[0]
    else:
        drained = "".join(runtime.assistant_delta_buffer)
    runtime.assistant_delta_buffer.clear()
    runtime.assistant_delta_buffer_chars = 0
    return drained


def should_flush_delta_event(
    runtime: AssistantTimelineRuntime,
    *,
    now_ms: int,
    force_publish: bool,
) -> bool:
    if runtime.assistant_delta_buffer_chars <= 0:
        return False
    if force_publish:
        return True
    if not runtime.assistant_delta_emitted:
        return True
    if runtime.assistant_delta_buffer_chars >= ASSISTANT_DELTA_FLUSH_MIN_CHARS:
        return True
    elapsed_ms = now_ms - runtime.assistant_delta_last_emit_ms
    return elapsed_ms >= ASSISTANT_DELTA_FLUSH_MAX_DELAY_MS


def resolve_unpersisted_assistant_chars(runtime: AssistantTimelineRuntime) -> int:
    unpersisted_char_count = runtime.assistant_visible_chars - runtime.assistant_persisted_chars
    if unpersisted_char_count <= 0:
        return 0
    return unpersisted_char_count


def should_flush_assistant_content(
    runtime: AssistantTimelineRuntime,
    *,
    now_ms: int,
    force: bool,
) -> bool:
    if force:
        return True
    unpersisted_char_count = resolve_unpersisted_assistant_chars(runtime)
    if unpersisted_char_count <= 0:
        return False
    if unpersisted_char_count >= ASSISTANT_CONTENT_FLUSH_CHAR_THRESHOLD:
        return True
    elapsed_ms = now_ms - runtime.assistant_last_persist_monotonic_ms
    return elapsed_ms >= ASSISTANT_CONTENT_FLUSH_INTERVAL_MS
