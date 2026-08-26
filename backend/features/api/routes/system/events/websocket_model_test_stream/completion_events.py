"""SoAI - WebSocket model test stream completion events [backend/features/api/routes/system/events/websocket_model_test_stream/completion_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.monotonic import monotonic_ms
from features.api.routes.system.events.websocket_model_test_stream.state import (
    ModelTestStreamRuntime,
    publish_model_test_stream_event,
    publish_model_test_stream_loading_activity,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.types.json import JSONDict

__all__ = ("publish_model_test_stream_completion",)


async def publish_model_test_stream_completion(
    *,
    event_bus: EventBusProtocol,
    runtime: ModelTestStreamRuntime,
    stream_transcript: OpenAIStreamTranscript,
) -> None:
    stream_transcript.finalize()
    remaining_visible_deltas = stream_transcript.drain_visible_text_deltas()
    if remaining_visible_deltas:
        remaining_delta_text = "".join(remaining_visible_deltas)
        if remaining_delta_text:
            await publish_model_test_stream_event(
                event_bus,
                runtime,
                event_type="assistant_text_delta",
                payload={"delta": remaining_delta_text},
            )
    final_payload = stream_transcript.build_result_payload()
    finish_reason: str | None = None
    usage: JSONDict | None = None
    if isinstance(final_payload, dict):
        usage_candidate = final_payload.get("usage")
        if isinstance(usage_candidate, dict):
            usage = usage_candidate
        choices_value = final_payload.get("choices")
        first_choice = (
            choices_value[0] if isinstance(choices_value, list) and choices_value else None
        )
        if isinstance(first_choice, dict):
            finish_reason_candidate = first_choice.get("finish_reason")
            if isinstance(finish_reason_candidate, str):
                finish_reason = finish_reason_candidate
    duration_ms = max(0, monotonic_ms() - runtime.started_at_ms)
    await publish_model_test_stream_loading_activity(
        event_bus,
        runtime,
        status="success",
        duration_ms=duration_ms,
        reason=None,
        error_type=None,
    )
    await publish_model_test_stream_event(
        event_bus,
        runtime,
        event_type="completed",
        payload={"finish_reason": finish_reason, "usage": usage or {}},
    )
