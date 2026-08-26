"""SoAI - Conversation draft database protocol definitions [backend/core/conversations/protocols_database_conversation_drafts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.conversations.conversation_draft_state import (
        ConversationDraftMutationResult,
        ConversationDraftState,
    )
    from core.types.json import JSONValue

__all__ = ("DatabaseConversationDraftsProtocol",)


class DatabaseConversationDraftsProtocol(Protocol):
    async def get_draft(self, *, conv_id: str, user_id: int) -> ConversationDraftState: ...
    async def save_draft(
        self,
        *,
        conv_id: str,
        user_id: int,
        text: str,
        source_text: str,
        attachment_content: list[JSONValue],
        client_id: str,
        client_sequence: int,
        base_revision: int,
    ) -> ConversationDraftMutationResult: ...
    async def delete_draft(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_id: str,
        client_sequence: int,
        base_revision: int,
    ) -> ConversationDraftMutationResult: ...
