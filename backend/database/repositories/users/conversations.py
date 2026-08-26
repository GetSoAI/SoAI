"""SoAI - Conversation CRUD with settings and favorites [backend/database/repositories/users/conversations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.conversation_active_queries import (
    read_active_conversations,
    read_conversation,
)
from database.repositories.users.conversation_archive_sync_operations import (
    sync_update_conversation_archived,
)
from database.repositories.users.conversation_archived_queries import (
    list_archived_conversations_query,
    search_archived_conversation_titles_query,
)
from database.repositories.users.conversation_attention import (
    get_conversation_attention_snapshot_method,
    mark_conversation_attention_seen_method,
    mark_conversation_attention_seen_through_method,
)
from database.repositories.users.conversation_clone_operations import clone_conversation_method
from database.repositories.users.conversation_creation import sync_create_conversation
from database.repositories.users.conversation_deletion_operations import (
    sync_delete_all_conversations,
    sync_delete_conversation,
    sync_delete_conversations,
)
from database.repositories.users.conversation_deletion_queries import (
    list_conversation_ids_for_deletion,
    summarize_active_conversation_inputs_for_deletion,
)
from database.repositories.users.conversation_row_formatter import (
    attach_conversation_settings_authority,
)
from database.repositories.users.conversation_settings_commit import (
    sync_commit_conversation_settings,
)
from database.repositories.users.conversation_sync_operations import (
    sync_update_conversation_color,
    sync_update_conversation_favorite,
    sync_update_conversation_title,
    sync_update_conversation_title_if_matches,
)
from database.repositories.users.conversation_title_search import (
    search_conversation_titles,
)
from database.repositories.users.conversation_tool_defaults_commit import (
    reconcile_conversation_tool_defaults_method,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.conversations.archived_conversation_models import (
        ArchivedConversationsPage,
        ArchivedConversationSummary,
    )
    from core.conversations.conversation_deletion import DeletedConversationRecord
    from core.conversations.conversation_input_active_state import ActiveConversationInputSummary
    from core.conversations.settings_commit import (
        ConversationSettingsCommitResult,
    )
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversations",)


class DatabaseConversations:
    clone_conversation = clone_conversation_method
    get_conversation_attention_snapshot = get_conversation_attention_snapshot_method
    mark_conversation_attention_seen = mark_conversation_attention_seen_method
    mark_conversation_attention_seen_through = mark_conversation_attention_seen_through_method
    reconcile_conversation_tool_defaults = reconcile_conversation_tool_defaults_method

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.event_bus = deps.event_bus

    async def create_conversation(
        self,
        user_id: int,
        title: str,
        model_settings: JSONDict,
        is_automation: bool,
        conv_id: str | None = None,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_create_conversation,
            user_id,
            title,
            model_settings,
            is_automation,
            conv_id,
        )

    async def get_conversation(self, conv_id: str, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.reader.execute_read(
            read_conversation,
            conv_id=conv_id,
            user_id=user_id,
        )

    async def list_conversations(self, user_id: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

        return await self.core.reader.execute_read(
            read_active_conversations,
            user_id=user_id,
        )

    async def search_conversation_titles(
        self,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await search_conversation_titles(
            self.core,
            user_id=user_id,
            query=query,
            limit=limit,
        )

    async def search_conversation_by_identifier(
        self,
        user_id: int,
        conversation_id: str,
    ) -> list[JSONDict]:
        record = await self.get_conversation(conversation_id, user_id)
        if record is None or record["is_archived"] is True:
            return []
        return [attach_conversation_settings_authority(record)]

    async def list_archived_conversations(
        self,
        user_id: int,
        *,
        limit: int,
        before_last_modified_at_ms: int | None,
        before_id: str | None,
    ) -> ArchivedConversationsPage:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_archived_conversations_query(
            self.core.reader,
            user_id,
            limit=limit,
            before_last_modified_at_ms=before_last_modified_at_ms,
            before_id=before_id,
        )

    async def search_archived_conversation_titles(
        self,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[ArchivedConversationSummary]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await search_archived_conversation_titles_query(
            self.core,
            user_id=user_id,
            query=query,
            limit=limit,
        )

    async def update_conversation_title(
        self,
        conv_id: str,
        user_id: int,
        new_title: str,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_conversation_title,
            conv_id,
            user_id,
            new_title,
        )

    async def update_conversation_title_if_matches(
        self,
        conv_id: str,
        user_id: int,
        expected_title: str,
        new_title: str,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_conversation_title_if_matches,
            conv_id,
            user_id,
            expected_title,
            new_title,
        )

    async def update_conversation_settings(
        self,
        conv_id: str,
        user_id: int,
        new_settings: JSONDict,
    ) -> ConversationSettingsCommitResult | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_commit_conversation_settings,
            conv_id,
            user_id,
            new_settings,
        )
        if result is not None and result.conversation_changed:
            notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def update_conversation_color(
        self,
        conv_id: str,
        user_id: int,
        color: str | None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_conversation_color,
            conv_id,
            user_id,
            color,
        )

    async def update_conversation_favorite(
        self,
        conv_id: str,
        user_id: int,
        is_favorite: bool,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_conversation_favorite,
            conv_id,
            user_id,
            is_favorite,
        )

    async def update_conversation_archived(
        self,
        conv_id: str,
        user_id: int,
        is_archived: bool,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_conversation_archived,
            conv_id,
            user_id,
            is_archived,
        )

    async def delete_conversation(
        self,
        conv_id: str,
        user_id: int,
    ) -> DeletedConversationRecord | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_delete_conversation,
            conv_id,
            user_id,
        )

    async def delete_conversations(
        self,
        conv_ids: tuple[str, ...],
        user_id: int,
    ) -> list[DeletedConversationRecord]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_delete_conversations,
            conv_ids,
            user_id,
        )

    async def delete_all_conversations(self, user_id: int) -> list[DeletedConversationRecord]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_delete_all_conversations,
            user_id,
        )

    async def list_conversation_ids_for_deletion(self, user_id: int) -> tuple[str, ...]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_conversation_ids_for_deletion(self.core, user_id=user_id)

    async def summarize_active_conversation_inputs_for_deletion(
        self,
        user_id: int,
    ) -> dict[str, ActiveConversationInputSummary]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await summarize_active_conversation_inputs_for_deletion(self.core, user_id=user_id)
