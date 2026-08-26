"""SoAI - Compaction hidden streaming helpers [backend/features/api/routes/openai/compaction/streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_prefixed_hex_id, extend_soai_id
from features.api.routes.openai.hidden_streaming_text import await_hidden_streaming_text
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONDict

__all__ = (
    "COMPACTION_VISIBLE_OUTPUT_ERROR",
    "await_streaming_summary_text",
    "resolve_summary_cancellation_id",
)

COMPACTION_VISIBLE_OUTPUT_ERROR = "Context compaction summarizer returned no visible output."


def resolve_summary_cancellation_id(context: RequestContext) -> str:
    base_value = context.cancellation_id
    base_cancellation_id = str(base_value or "").strip()
    if not base_cancellation_id:
        raise ValidationError("Compaction summary requires a non-empty base cancellation_id.")
    return extend_soai_id(
        base_cancellation_id,
        ("agent", "compaction_summary", create_prefixed_hex_id("summary", length=12)),
    )


async def await_streaming_summary_text(
    *,
    request: RequestProtocol,
    context: RequestContext,
    stream_dependencies: StreamDependencies,
    request_json: JSONDict,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    timeout: float,
    on_text_delta: Callable[[str], Awaitable[None]] | None,
) -> str:
    return await await_hidden_streaming_text(
        request=request,
        context=context,
        stream_dependencies=stream_dependencies,
        request_json=request_json,
        reply_queue=reply_queue,
        task_id=task_id,
        timeout=timeout,
        on_text_delta=on_text_delta,
        allow_reasoning_fallback=False,
        empty_response_message=COMPACTION_VISIBLE_OUTPUT_ERROR,
    )
