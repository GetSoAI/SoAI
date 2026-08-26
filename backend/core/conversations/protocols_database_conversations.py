"""SoAI - WebUI database conversation and message protocol definitions [backend/core/conversations/protocols_database_conversations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Literal, Protocol

from core.conversations.protocols_database_message_streaming import (
    DatabaseStreamingMessagesProtocol,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_sync_cursor import (
        ConversationMessageSyncCursor,
    )
    from core.conversations.conversation_message_window import (
        ConversationMessageCursor,
        ConversationMessageWindowDirection,
        ConversationMessageWindowResult,
        ConversationRunningActivitySnapshot,
    )
    from core.conversations.conversation_message_write_result import (
        ConversationMessageWriteResult,
    )
    from core.conversations.conversation_start_snapshot import ConversationStartSnapshot
    from core.database.requests import (
        ManualCompactionStartCommitRequest,
        ManualCompactionStartCommitResult,
        ManualCompactionTerminalCommitRequest,
        ManualCompactionTerminalCommitResult,
    )
    from core.types.json import JSONDict

__all__ = ("DatabaseMessagesProtocol",)


class DatabaseMessagesProtocol(DatabaseStreamingMessagesProtocol, Protocol):
    async def has_unfinalized_assistant_stream(
        self,
        conv_id: str,
        user_id: int,
    ) -> bool: ...
    async def get_conversation_start_snapshot(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int,
        counting_mode: Literal["canonical", "including_comparison_variants"],
    ) -> ConversationStartSnapshot | None: ...
    async def get_messages_tail(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_cursor: ConversationMessageCursor | None,
        limit: int,
        roles: tuple[str, ...],
    ) -> list[JSONDict] | None: ...
    async def get_auto_title_seed_messages(
        self,
        conv_id: str,
        user_id: int,
    ) -> tuple[JSONDict | None, JSONDict | None] | None: ...
    async def get_message_window(
        self,
        conv_id: str,
        user_id: int,
        *,
        direction: ConversationMessageWindowDirection,
        limit: int,
        cursor_created_at_ms: int | None = None,
        cursor_id: int | None = None,
        anchor_created_at_ms: int | None = None,
        anchor_id: int | None = None,
    ) -> ConversationMessageWindowResult | None: ...
    def iter_conversation_export_messages(
        self,
        conv_id: str,
        user_id: int,
        *,
        page_size: int = 1000,
    ) -> AsyncIterator[JSONDict]: ...
    async def get_running_activity_snapshot(
        self,
        conv_id: str,
        user_id: int,
    ) -> ConversationRunningActivitySnapshot | None: ...
    async def get_context_compaction_tool_call_id(
        self,
        conv_id: str,
        user_id: int,
        *,
        assistant_turn_at_ms: int,
    ) -> str | None: ...
    async def resolve_manual_compaction_message_index(
        self,
        conv_id: str,
        user_id: int,
        *,
        replace_assistant_at_ms: int | None,
    ) -> int | None: ...
    async def search_messages_by_content(
        self,
        user_id: int,
        *,
        query: str,
        limit: int,
        include_automation: bool,
        roles: tuple[str, ...],
    ) -> list[JSONDict]: ...
    async def get_assistant_turn_variant_stream_state(
        self,
        conv_id: str,
        user_id: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None: ...
    async def get_canonical_agent_history(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int | None = None,
    ) -> list[JSONDict] | None: ...
    async def overwrite_messages(
        self,
        conv_id: str,
        user_id: int,
        messages: list[JSONDict],
        expected_last_modified_at_ms: int | None = None,
    ) -> ConversationMessageWriteResult: ...
    async def append_messages(
        self,
        conv_id: str,
        user_id: int,
        messages: list[JSONDict],
        expected_last_modified_at_ms: int | None = None,
    ) -> ConversationMessageWriteResult: ...
    async def resubmit_user_message_by_cursor(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        message_id: int,
        message: JSONDict,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult: ...
    async def truncate_messages_from_cursor(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        message_id: int,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult: ...
    async def delete_message_by_cursor(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        message_id: int,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult: ...
    async def remove_context_compaction_boundary(
        self,
        conv_id: str,
        user_id: int,
        *,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        tool_call_id: str,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult: ...
    async def commit_manual_compaction_terminal(
        self,
        request: ManualCompactionTerminalCommitRequest,
    ) -> ManualCompactionTerminalCommitResult: ...
    async def commit_manual_compaction_start(
        self,
        request: ManualCompactionStartCommitRequest,
    ) -> ManualCompactionStartCommitResult: ...
    async def get_message_sync_cursor(
        self,
        conv_id: str,
        user_id: int,
    ) -> ConversationMessageSyncCursor | None: ...
    async def get_latest_message_timestamp(self, conv_id: str, user_id: int) -> int | None: ...
    async def count_messages(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int | None = None,
    ) -> int | None: ...
    async def count_messages_including_comparison_variants(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int | None = None,
    ) -> int | None: ...
    async def append_streaming_assistant_placeholder(
        self,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        assistant_turn_at_ms: int,
        request_id: str | None,
        model_id: str | None,
        model_variant_index: int,
    ) -> ConversationMessageWriteResult: ...
