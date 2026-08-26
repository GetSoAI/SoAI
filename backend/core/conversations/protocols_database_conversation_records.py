"""SoAI - WebUI database conversation record protocol definitions [backend/core/conversations/protocols_database_conversation_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.conversations.archived_conversation_models import (
        ArchivedConversationsPage,
        ArchivedConversationSummary,
    )
    from core.conversations.conversation_deletion import DeletedConversationRecord
    from core.conversations.conversation_input_active_state import ActiveConversationInputSummary
    from core.conversations.settings_commit import (
        ConversationSettingsCommitResult,
        ConversationToolDefaultsCommitResult,
    )
    from core.types.json import JSONDict

__all__ = ("DatabaseConversationsProtocol",)


class DatabaseConversationsProtocol(Protocol):
    async def get_conversation_attention_snapshot(
        self,
        user_id: int,
    ) -> list[JSONDict]: ...
    async def mark_conversation_attention_seen(
        self,
        user_id: int,
        conv_id: str,
        assistant_at_ms: int,
    ) -> bool: ...
    async def mark_conversation_attention_seen_through(
        self,
        user_id: int,
        seen_through_attention_id: int,
    ) -> bool: ...
    async def create_conversation(
        self,
        user_id: int,
        title: str,
        model_settings: JSONDict,
        is_automation: bool,
        conv_id: str | None = None,
    ) -> JSONDict: ...
    async def clone_conversation(
        self,
        source_conv_id: str,
        user_id: int,
        *,
        target_conv_id: str | None = None,
    ) -> JSONDict | None: ...
    async def get_conversation(self, conv_id: str, user_id: int) -> JSONDict | None: ...
    async def list_conversations(self, user_id: int) -> list[JSONDict]: ...
    async def list_conversation_ids_for_deletion(self, user_id: int) -> tuple[str, ...]: ...
    async def summarize_active_conversation_inputs_for_deletion(
        self,
        user_id: int,
    ) -> dict[str, ActiveConversationInputSummary]: ...
    async def search_conversation_titles(
        self,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[JSONDict]: ...
    async def search_conversation_by_identifier(
        self,
        user_id: int,
        conversation_id: str,
    ) -> list[JSONDict]: ...
    async def list_archived_conversations(
        self,
        user_id: int,
        *,
        limit: int,
        before_last_modified_at_ms: int | None,
        before_id: str | None,
    ) -> ArchivedConversationsPage: ...
    async def search_archived_conversation_titles(
        self,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[ArchivedConversationSummary]: ...
    async def update_conversation_title(
        self,
        conv_id: str,
        user_id: int,
        new_title: str,
    ) -> JSONDict | None: ...
    async def update_conversation_title_if_matches(
        self,
        conv_id: str,
        user_id: int,
        expected_title: str,
        new_title: str,
    ) -> JSONDict | None: ...
    async def update_conversation_settings(
        self,
        conv_id: str,
        user_id: int,
        new_settings: JSONDict,
    ) -> ConversationSettingsCommitResult | None: ...
    async def reconcile_conversation_tool_defaults(
        self,
        *,
        conv_id: str,
        user_id: int,
        tool_field: str,
        expected_tools_enabled: bool,
        expected_tools: list[str],
        tools_enabled: bool,
        updated_tools: list[str],
    ) -> ConversationToolDefaultsCommitResult: ...
    async def update_conversation_color(
        self,
        conv_id: str,
        user_id: int,
        color: str | None,
    ) -> JSONDict | None: ...
    async def update_conversation_favorite(
        self,
        conv_id: str,
        user_id: int,
        is_favorite: bool,
    ) -> JSONDict | None: ...
    async def update_conversation_archived(
        self,
        conv_id: str,
        user_id: int,
        is_archived: bool,
    ) -> JSONDict | None: ...
    async def delete_conversation(
        self,
        conv_id: str,
        user_id: int,
    ) -> DeletedConversationRecord | None: ...
    async def delete_conversations(
        self,
        conv_ids: tuple[str, ...],
        user_id: int,
    ) -> list[DeletedConversationRecord]: ...
    async def delete_all_conversations(self, user_id: int) -> list[DeletedConversationRecord]: ...
