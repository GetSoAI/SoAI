"""SoAI - WebSocket chat stream hidden status preview inference [backend/features/api/routes/system/events/websocket_chat_stream/status_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.timing.epoch import epoch_ms
from features.assistant_timeline.models import (
    StatusPreviewRequest,
    StatusPreviewResult,
)
from features.assistant_timeline.status_preview_payload_generation import (
    generate_status_preview_payload,
)

__all__ = ("build_ws_chat_stream_status_preview_executor",)


def build_ws_chat_stream_status_preview_executor() -> (
    Callable[[StatusPreviewRequest], Awaitable[StatusPreviewResult | None]]
):
    async def execute_status_preview(
        preview_request: StatusPreviewRequest,
    ) -> StatusPreviewResult | None:
        payload = generate_status_preview_payload(preview_request)
        if payload is None:
            return None
        preview_key, preview_args = payload
        return StatusPreviewResult(
            preview_key=preview_key,
            preview_args=preview_args,
            generated_at_ms=int(epoch_ms()),
        )

    return execute_status_preview
