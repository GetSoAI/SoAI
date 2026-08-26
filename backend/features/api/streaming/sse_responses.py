"""SoAI - SSE response primitives [backend/features/api/streaming/sse_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator

from starlette.responses import StreamingResponse

__all__ = ("SSE_MEDIA_TYPE", "create_sse_response")

SSE_MEDIA_TYPE = "text/event-stream"


def create_sse_response(
    generator: AsyncGenerator[str | bytes],
    additional_headers: dict[str, str] | None = None,
) -> StreamingResponse:
    headers: dict[str, str] = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    if additional_headers:
        headers.update(additional_headers)
    return StreamingResponse(
        generator,
        media_type=SSE_MEDIA_TYPE,
        headers=headers,
    )
