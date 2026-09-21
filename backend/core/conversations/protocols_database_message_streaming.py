"""SoAI - Streaming conversation message database protocol [backend/core/conversations/protocols_database_message_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.conversations.conversation_message_write_result import (
        ConversationMessageWriteResult,
    )
    from core.conversations.streaming_assistant_terminal_commit import (
        StreamingAssistantTerminalCommitRequest,
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
    async def commit_streaming_assistant_terminal(
        self,
        request: StreamingAssistantTerminalCommitRequest,
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
