"""SoAI - Assistant timeline status preview publication [backend/features/assistant_timeline/status_preview_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import ChatStreamStatusPreviewEvent
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    StatusPreviewResult,
)
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.status_preview_constants import (
    STATUS_PREVIEW_START_COOLDOWN_MS,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = ("publish_status_preview_result",)

LOGGER_NAME = "SoAI.features.assistant_timeline.status_preview_publication"
OPERATION = "assistant_timeline.status_preview.publish"


async def publish_status_preview_result(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    trigger: str,
    preview_result: StatusPreviewResult | None,
    preview_generation: int,
) -> None:
    if preview_result is None:
        return
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        if (
            preview_generation != runtime.status_preview_generation
            or runtime.terminal_event_emitted
            or runtime.terminal_finalization_started
            or (runtime.detach_event is not None and runtime.detach_event.is_set())
        ):
            return
        candidate_preview_key = str(preview_result.preview_key or "").strip()
        if not candidate_preview_key:
            return
        candidate_preview_args = preview_result.preview_args
        signature = _build_status_preview_signature(
            preview_key=candidate_preview_key,
            preview_args=candidate_preview_args,
        )
        runtime.status_preview_last_completed_monotonic_ms = monotonic_ms()
        runtime.status_preview_real_emitted = True
        if runtime.status_preview_last_text == signature:
            return
        runtime.status_preview_last_text = signature
        runtime.status_preview_last_key = candidate_preview_key
        runtime.status_preview_last_args = candidate_preview_args
        preview_key = candidate_preview_key
        preview_args = candidate_preview_args
        generated_at_ms = (
            preview_result.generated_at_ms
            if preview_result.generated_at_ms > 0
            else int(epoch_ms())
        )
        runtime.status_preview_last_generated_at_ms = generated_at_ms
        runtime.status_preview_last_trigger = trigger
        try:
            await event_bus.publish(
                ChatStreamStatusPreviewEvent(
                    user_id=runtime.user_id,
                    conv_id=runtime.conv_id,
                    request_id=runtime.request_id,
                    assistant_at_ms=runtime.assistant_at_ms,
                    preview_key=preview_key,
                    preview_args=preview_args,
                    generated_at_ms=generated_at_ms,
                    preview_cooldown_ms=STATUS_PREVIEW_START_COOLDOWN_MS,
                    trigger=trigger,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_handled_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Failed to publish status preview websocket event (non-critical).",
                operation=OPERATION,
                level="debug",
                details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
            )


def _build_status_preview_signature(
    *,
    preview_key: str,
    preview_args: JSONDict | None,
) -> str:
    normalized_key = str(preview_key or "").strip()
    if not normalized_key:
        return ""
    if not preview_args:
        return normalized_key
    parts: list[str] = []
    for key in sorted(preview_args.keys()):
        raw_value = preview_args.get(key)
        if raw_value is None:
            continue
        value_text = str(raw_value).strip()
        if not value_text:
            continue
        parts.append(f"{key}={value_text}")
    if not parts:
        return normalized_key
    return f"{normalized_key}|{'|'.join(parts)}"
