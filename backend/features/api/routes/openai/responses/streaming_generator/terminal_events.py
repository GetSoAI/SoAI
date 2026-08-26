"""SoAI - Responses streaming terminal event emission [backend/features/api/routes/openai/responses/streaming_generator/terminal_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from core.openai.responses_events import build_response_status_event

if TYPE_CHECKING:
    from core.openai.responses_provider_state import (
        ResponsesProviderState,
    )
    from features.api.routes.openai.responses.streaming_generator.passthrough_persistence import (
        ResponsesPassthroughPersistence,
    )

__all__ = (
    "emit_failure_done",
    "emit_synthesized_completion_or_failure",
    "persist_cancelled_response",
)


async def emit_synthesized_completion_or_failure(
    *,
    provider_state: ResponsesProviderState,
    persistence: ResponsesPassthroughPersistence,
    done_chunk: bytes,
    message: str,
) -> AsyncGenerator[bytes]:
    synthesized_event = provider_state.build_response_event(status="completed")
    if synthesized_event is None:
        async for chunk in emit_failure_done(
            persistence=persistence,
            done_chunk=done_chunk,
            code="server_error",
            message=message,
        ):
            yield chunk
        return
    event_bytes, terminal = persistence.emit_response_event(payload=synthesized_event)
    await persistence.flush_if_needed(force=bool(terminal))
    yield event_bytes
    yield done_chunk


async def emit_failure_done(
    *,
    persistence: ResponsesPassthroughPersistence,
    done_chunk: bytes,
    code: str,
    message: str,
) -> AsyncGenerator[bytes]:
    yield await persistence.emit_failure(code=code, message=message)
    yield done_chunk


async def persist_cancelled_response(
    *,
    persistence: ResponsesPassthroughPersistence,
) -> None:
    cancelled_event = build_response_status_event(
        response_id=persistence.recorded_response_id,
        status="cancelled",
        model=persistence.storage_target.model,
        created_at=int(persistence.storage_target.created_at),
    )
    persistence.emit_response_event(
        payload=cancelled_event,
        default_status="cancelled",
    )
    await persistence.flush_if_needed(force=True)
