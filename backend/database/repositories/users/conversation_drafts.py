"""SoAI - Conversation draft persistence [backend/database/repositories/users/conversation_drafts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.strict_numbers import require_non_negative_int_strict
from database.repositories.users.conversation_draft_queries import (
    async_query_conversation_draft_state,
)
from database.repositories.users.conversation_draft_row_mapping import (
    serialize_conversation_draft_entries,
)
from database.repositories.users.conversation_draft_sync_writes import (
    sync_delete_conversation_draft,
    sync_save_conversation_draft,
)
from database.repositories.users.conversation_input_validation import (
    now_ms,
    require_client_id,
)
from database.repositories.users.storage_backed_repository_runtime import (
    queue_storage_backed_write,
    resolve_storage_backed_repository_root,
)

if TYPE_CHECKING:
    from core.conversations.conversation_draft_state import (
        ConversationDraftMutationResult,
        ConversationDraftState,
    )
    from core.types.json import JSONValue
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationDrafts",)


class DatabaseConversationDrafts:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.files = deps.files
        self.storage_root = resolve_storage_backed_repository_root(deps)

    async def get_draft(self, *, conv_id: str, user_id: int) -> ConversationDraftState:
        return await self.core.reader.execute_read(
            async_query_conversation_draft_state,
            conv_id,
            user_id,
        )

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
    ) -> ConversationDraftMutationResult:
        return await queue_storage_backed_write(
            self.core,
            sync_save_conversation_draft,
            conv_id,
            user_id,
            text,
            source_text,
            serialize_conversation_draft_entries(attachment_content),
            require_client_id(client_id),
            require_non_negative_int_strict(
                client_sequence,
                error_message="client_sequence must be a non-negative integer.",
            ),
            require_non_negative_int_strict(
                base_revision,
                error_message="base_revision must be a non-negative integer.",
            ),
            now_ms(),
            self.storage_root,
        )

    async def delete_draft(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_id: str,
        client_sequence: int,
        base_revision: int,
    ) -> ConversationDraftMutationResult:
        return await queue_storage_backed_write(
            self.core,
            sync_delete_conversation_draft,
            conv_id,
            user_id,
            require_client_id(client_id),
            require_non_negative_int_strict(
                client_sequence,
                error_message="client_sequence must be a non-negative integer.",
            ),
            require_non_negative_int_strict(
                base_revision,
                error_message="base_revision must be a non-negative integer.",
            ),
            now_ms(),
        )
