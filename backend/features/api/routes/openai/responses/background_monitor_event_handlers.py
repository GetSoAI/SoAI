"""SoAI - OpenAI Responses background monitor event handling [backend/features/api/routes/openai/responses/background_monitor_event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_models_streaming import StreamChunkEvent
from features.api.routes.openai.responses.background_monitor_state import (
    BackgroundResponsesState,
)
from features.api.routes.openai.responses.background_monitor_storage import (
    append_response_event,
)
from features.api.routes.openai.responses.provider_chunk_validation import (
    validate_responses_provider_chunk,
)

if TYPE_CHECKING:
    from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
    from features.api.runtime.context import ApiContext

__all__ = ("handle_stream_chunk_event",)


async def handle_stream_chunk_event(
    api_context: ApiContext,
    state: BackgroundResponsesState,
    *,
    event: StreamChunkEvent,
    accumulator: OpenAISSEFrameAccumulator,
    response_finalized: bool,
) -> bool:
    validated_chunk = validate_responses_provider_chunk(
        accumulator,
        event.chunk,
        terminal_observed=response_finalized,
    )
    for payload in validated_chunk.payloads:
        terminal = await append_response_event(api_context, state, payload=payload)
        if terminal:
            response_finalized = True
    return response_finalized
