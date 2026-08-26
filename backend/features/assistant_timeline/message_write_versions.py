"""SoAI - Assistant timeline committed message version tracking [backend/features/assistant_timeline/message_write_versions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.errors.exceptions import StateError
from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "record_assistant_timeline_message_write",
    "require_assistant_timeline_message_write",
)


def record_assistant_timeline_message_write(
    runtime: AssistantTimelineRuntime,
    write_result: ConversationMessageWriteResult,
) -> None:
    runtime.latest_message_write_last_modified_at_ms = write_result.last_modified_at_ms
    runtime.latest_message_write_count = write_result.message_count


def require_assistant_timeline_message_write(
    runtime: AssistantTimelineRuntime,
) -> ConversationMessageWriteResult:
    last_modified_at_ms = runtime.latest_message_write_last_modified_at_ms
    message_count = runtime.latest_message_write_count
    if last_modified_at_ms is None or message_count is None:
        raise StateError("Assistant timeline has no committed message write version.")
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=message_count,
    )
