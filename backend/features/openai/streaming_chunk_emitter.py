"""SoAI - Shared OpenAI streaming chunk emission state [backend/features/openai/streaming_chunk_emitter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.openai.streaming_identity import (
    extract_stream_identity_from_frame,
    rewrite_stream_identity_in_frame,
)
from core.openai.streaming_tool_calls import (
    rewrite_agentic_tool_call_chronology_in_frame,
)

__all__ = ("AgentStreamingChunkEmitter",)


@dataclass(slots=True)
class AgentStreamingChunkEmitter:
    root_stream_id: str | None = None
    root_stream_created: int | None = None
    tool_sequence_offset: int = 0
    content_index_offset: int = 0
    thinking_index_offset: int = 0

    async def emit_chunk(
        self,
        chunk: bytes,
        *,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
    ) -> None:
        candidate_stream_id, candidate_created = extract_stream_identity_from_frame(chunk)
        if self.root_stream_id is None and candidate_stream_id is not None:
            self.root_stream_id = candidate_stream_id
        if self.root_stream_created is None and candidate_created is not None:
            self.root_stream_created = candidate_created
        outbound_chunk = rewrite_agentic_tool_call_chronology_in_frame(
            chunk,
            tool_sequence_offset=self.tool_sequence_offset,
            content_index_offset=self.content_index_offset,
            thinking_index_offset=self.thinking_index_offset,
        )
        if self.root_stream_id is not None:
            outbound_chunk = rewrite_stream_identity_in_frame(
                outbound_chunk,
                stream_id=self.root_stream_id,
                created=self.root_stream_created,
            )
        awaitable = on_bytes(outbound_chunk)
        if awaitable is not None:
            await awaitable
