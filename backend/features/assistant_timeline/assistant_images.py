"""SoAI - Assistant timeline image validation, persistence, and publication [backend/features/assistant_timeline/assistant_images.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.processing_activity import (
    complete_processing_activity_if_running_locked,
    note_visible_activity_locked,
)
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    publish_chat_stream_event_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol

__all__ = ("persist_and_publish_assistant_image",)

MAX_ASSISTANT_IMAGES_PER_MESSAGE: int = 4
MAX_ASSISTANT_IMAGE_URL_CHARS: int = 2_000_000


def validate_image_url(url: str) -> str:
    if not isinstance(url, str):
        raise ValidationError("assistant image url must be a string.")
    normalized = url.strip()
    if not normalized:
        raise ValidationError("assistant image url must be a non-empty string.")
    if len(normalized) > MAX_ASSISTANT_IMAGE_URL_CHARS:
        raise ValidationError("assistant image url exceeds the maximum allowed size.")
    if not normalized.startswith("data:image/"):
        raise ValidationError("assistant image url must be a data:image/* URL.")
    return normalized


async def persist_and_publish_assistant_image(
    *,
    runtime: AssistantTimelineRuntime,
    image_url: str,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
) -> bool:
    normalized_url = validate_image_url(image_url)
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        if runtime.assistant_images_emitted >= MAX_ASSISTANT_IMAGES_PER_MESSAGE:
            raise ValidationError("assistant image limit exceeded for this message.")
        if normalized_url in runtime.emitted_image_urls:
            return False
        runtime.emitted_image_urls.add(normalized_url)
        await complete_processing_activity_if_running_locked(
            runtime=runtime,
            event_bus=event_bus,
            database_messages=database_messages,
            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
        )
        runtime.assistant_visible_output_started = True
        note_visible_activity_locked(runtime)
        await publish_chat_stream_event_locked(
            event_bus,
            runtime,
            database_messages,
            event_type="assistant_image",
            payload={
                "assistant_at_ms": runtime.assistant_at_ms,
                "image": {"url": normalized_url},
            },
        )
        runtime.assistant_images_emitted += 1
        return True
