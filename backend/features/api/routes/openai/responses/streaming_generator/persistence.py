"""SoAI - Responses streaming persistence helpers [backend/features/api/routes/openai/responses/streaming_generator/persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.responses_events import build_failed_response_event
from core.openai.sse_events import format_openai_sse_data
from core.openai.sse_frames import sse_done_chunk

if TYPE_CHECKING:
    from core.errors.payload import ErrorPublicPayload

__all__ = (
    "build_failed_event_bytes",
    "build_failed_event_done_chunks",
)


def build_failed_event_bytes(
    *,
    response_id: str,
    message: str,
    code: str,
    model: str,
    created_at: int,
    public_error: ErrorPublicPayload | None = None,
) -> bytes:
    payload = build_failed_response_event(
        response_id=response_id,
        message=message,
        code=code,
        model=model,
        created_at=created_at,
        public_error=public_error,
    )
    return format_openai_sse_data(payload).encode("utf-8")


def build_failed_event_done_chunks(
    *,
    response_id: str,
    message: str,
    code: str,
    model: str,
    created_at: int,
) -> tuple[bytes, bytes]:
    return (
        build_failed_event_bytes(
            response_id=response_id,
            message=message,
            code=code,
            model=model,
            created_at=created_at,
        ),
        sse_done_chunk(),
    )
