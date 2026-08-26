"""SoAI - Repository service for conversation messages [backend/database/repositories/users/messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import aiosqlite

from core.conversations.conversation_message_sync_cursor import (
    ConversationMessageSyncCursor,
)
from core.conversations.conversation_message_window import (
    ConversationMessageWindowResult,
    ConversationRunningActivitySnapshot,
)
from core.conversations.conversation_start_snapshot import ConversationStartSnapshot
from core.database.protocols import DatabaseCoreProtocol
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from database.core.flags import FEATURE_PROMPTS
from database.repositories.dependencies import DatabaseRepositoryDependencies
from database.repositories.users.agent_history_queries import (
    load_canonical_agent_history_for_conversation,
)
from database.repositories.users.message_auto_title_reads import (
    get_auto_title_seed_messages_method,
)
from database.repositories.users.message_compaction_context_reads import (
    get_context_compaction_tool_call_id_method,
    resolve_manual_compaction_message_index_method,
)
from database.repositories.users.message_export_queries import (
    iter_conversation_export_messages_method,
)
from database.repositories.users.message_history_queries import (
    load_tail_messages_for_conversation,
    search_messages_by_content,
)
from database.repositories.users.message_running_activity_queries import (
    load_conversation_running_activity_snapshot,
)
from database.repositories.users.message_stream_lifecycle_reads import (
    has_unfinalized_assistant_stream,
)
from database.repositories.users.message_window_queries import (
    load_conversation_message_window,
)
from database.repositories.users.messages_counting_reads import (
    count_messages,
    count_messages_including_comparison_variants,
    get_latest_message_timestamp,
    get_message_sync_cursor,
)
from database.repositories.users.messages_mutation_repository import (
    DatabaseMessageMutationRepository,
)
from database.repositories.users.messages_start_snapshot_reads import (
    get_conversation_start_snapshot,
)
from database.repositories.users.messages_stream_state_reads import (
    get_assistant_turn_variant_stream_state,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import (
        ConversationMessageCursor,
        ConversationMessageWindowDirection,
    )
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONDict

__all__ = ("DatabaseMessages",)


class DatabaseMessages(DatabaseMessageMutationRepository):
    get_auto_title_seed_messages = get_auto_title_seed_messages_method
    get_context_compaction_tool_call_id = get_context_compaction_tool_call_id_method
    iter_conversation_export_messages = iter_conversation_export_messages_method
    resolve_manual_compaction_message_index = resolve_manual_compaction_message_index_method
    has_unfinalized_assistant_stream = has_unfinalized_assistant_stream

    core: DatabaseCoreProtocol
    storage_root: str | None
    files: FilesProtocol | None

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.files = deps.files
        self.event_bus = deps.event_bus
        self.storage_root = (
            resolve_managed_files_storage_root(deps.config, deps.files)
            if deps.files is not None
            else None
        )

    async def get_messages_tail(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_cursor: ConversationMessageCursor | None,
        limit: int,
        roles: tuple[str, ...],
    ) -> list[JSONDict] | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await load_tail_messages_for_conversation(
            self.core.reader,
            conv_id=conv_id,
            user_id=user_id,
            before_cursor=before_cursor,
            limit=limit,
            roles=roles,
        )

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
    ) -> ConversationMessageWindowResult | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

        async def _query(
            database: aiosqlite.Connection,
        ) -> ConversationMessageWindowResult | None:
            return await load_conversation_message_window(
                database,
                conv_id=conv_id,
                user_id=user_id,
                direction=direction,
                limit=limit,
                cursor_created_at_ms=cursor_created_at_ms,
                cursor_id=cursor_id,
                anchor_created_at_ms=anchor_created_at_ms,
                anchor_id=anchor_id,
            )

        return await self.core.reader.execute_read(_query)

    async def get_running_activity_snapshot(
        self,
        conv_id: str,
        user_id: int,
    ) -> ConversationRunningActivitySnapshot | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

        async def _query(
            database: aiosqlite.Connection,
        ) -> ConversationRunningActivitySnapshot | None:
            return await load_conversation_running_activity_snapshot(
                database,
                conv_id=conv_id,
                user_id=user_id,
            )

        return await self.core.reader.execute_read(_query)

    async def search_messages_by_content(
        self,
        user_id: int,
        *,
        query: str,
        limit: int,
        include_automation: bool,
        roles: tuple[str, ...],
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await search_messages_by_content(
            self.core.reader,
            user_id=user_id,
            query=query,
            limit=limit,
            include_automation=include_automation,
            roles=roles,
        )

    async def get_canonical_agent_history(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int | None = None,
    ) -> list[JSONDict] | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await load_canonical_agent_history_for_conversation(
            self.core.reader,
            conv_id=conv_id,
            user_id=user_id,
            before_timestamp_exclusive=before_timestamp_exclusive,
        )

    async def get_assistant_turn_variant_stream_state(
        self,
        conv_id: str,
        user_id: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None:
        return await get_assistant_turn_variant_stream_state(
            self,
            conv_id,
            user_id,
            assistant_turn_at_ms,
            model_variant_index,
        )

    async def get_latest_message_timestamp(self, conv_id: str, user_id: int) -> int | None:
        return await get_latest_message_timestamp(self, conv_id, user_id)

    async def get_message_sync_cursor(
        self,
        conv_id: str,
        user_id: int,
    ) -> ConversationMessageSyncCursor | None:
        return await get_message_sync_cursor(self, conv_id, user_id)

    async def count_messages(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int | None = None,
    ) -> int | None:
        return await count_messages(
            self,
            conv_id,
            user_id,
            before_timestamp_exclusive=before_timestamp_exclusive,
        )

    async def count_messages_including_comparison_variants(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int | None = None,
    ) -> int | None:
        return await count_messages_including_comparison_variants(
            self,
            conv_id,
            user_id,
            before_timestamp_exclusive=before_timestamp_exclusive,
        )

    async def get_conversation_start_snapshot(
        self,
        conv_id: str,
        user_id: int,
        *,
        before_timestamp_exclusive: int,
        counting_mode: Literal["canonical", "including_comparison_variants"],
    ) -> ConversationStartSnapshot | None:
        return await get_conversation_start_snapshot(
            self,
            conv_id,
            user_id,
            before_timestamp_exclusive=before_timestamp_exclusive,
            counting_mode=counting_mode,
        )
