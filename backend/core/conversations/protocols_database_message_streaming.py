"""SoAI - Streaming conversation message database protocol [backend/core/conversations/protocols_database_message_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.conversations.conversation_input_finalization import (
        ConversationInputFinalization,
    )
    from core.conversations.conversation_message_write_result import (
        ConversationMessageWriteResult,
    )
    from core.types.json import JSONDict

__all__ = ("DatabaseStreamingMessagesProtocol",)


class DatabaseStreamingMessagesProtocol(Protocol):
    async def update_streaming_assistant_content(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        content_text: str,
    ) -> ConversationMessageWriteResult: ...
    async def append_streaming_assistant_events_batch(
        self,
        conv_id: str,
        user_id: int,
        *,
        assistant_at_ms: int,
        events: list[tuple[int, int, str, JSONDict, int]],
    ) -> ConversationMessageWriteResult: ...
    async def finalize_streaming_assistant_message(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        request_id: str | None,
        finish_reason: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        usage_source: str | None,
        generation_latency_ms: int | None,
        thinking_tail_duration_ms: int | None,
        terminal_reason: str | None = None,
        input_finalization: ConversationInputFinalization | None = None,
        input_terminal_code: str | None = None,
    ) -> ConversationMessageWriteResult: ...
    async def delete_streaming_assistant_events(
        self,
        conv_id: str,
        user_id: int,
        *,
        assistant_at_ms: int,
    ) -> ConversationMessageWriteResult: ...
    async def delete_streaming_assistant_message(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
    ) -> ConversationMessageWriteResult: ...
