"""SoAI - Message mutation repository persistence [backend/database/repositories/users/messages_mutation_repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.database.protocols import DatabaseCoreProtocol
from core.database.requests import (
    ManualCompactionStartCommitRequest,
    ManualCompactionStartCommitResult,
    ManualCompactionTerminalCommitRequest,
    ManualCompactionTerminalCommitResult,
)
from core.plugins.protocols_instance import FilesProtocol
from core.types.json import JSONDict
from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.context_compaction_boundary_removal import (
    sync_remove_context_compaction_boundary,
)
from database.repositories.users.internal_protocols import (
    DatabaseMessagesStorageOwnerProtocol,
)
from database.repositories.users.manual_compaction_start_commit import (
    sync_commit_manual_compaction_start,
)
from database.repositories.users.manual_compaction_terminal_commit import (
    sync_commit_manual_compaction_terminal,
)
from database.repositories.users.message_targeted_mutations import (
    sync_delete_message_by_cursor,
    sync_resubmit_user_message_by_cursor,
    sync_truncate_messages_from_cursor,
)
from database.repositories.users.message_write_transactions import (
    sync_append_messages,
    sync_overwrite_messages,
)
from database.repositories.users.messages_streaming_repository import (
    DatabaseMessageStreamingRepository,
)

__all__ = ("DatabaseMessageMutationRepository",)


class DatabaseMessageMutationRepository(DatabaseMessageStreamingRepository):
    if not TYPE_CHECKING:
        core: DatabaseCoreProtocol
        storage_root: str | None
        files: FilesProtocol | None

    async def overwrite_messages(
        self: DatabaseMessagesStorageOwnerProtocol,
        conv_id: str,
        user_id: int,
        messages: list[JSONDict],
        expected_last_modified_at_ms: int | None = None,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_overwrite_messages,
            conv_id,
            user_id,
            messages,
            expected_last_modified_at_ms,
            self.storage_root,
            self.files,
        )

    async def append_messages(
        self: DatabaseMessagesStorageOwnerProtocol,
        conv_id: str,
        user_id: int,
        messages: list[JSONDict],
        expected_last_modified_at_ms: int | None = None,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_append_messages,
            conv_id,
            user_id,
            messages,
            expected_last_modified_at_ms,
            self.storage_root,
            self.files,
        )

    async def resubmit_user_message_by_cursor(
        self: DatabaseMessagesStorageOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        message_id: int,
        message: JSONDict,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_resubmit_user_message_by_cursor,
            conv_id,
            user_id,
            created_at_ms,
            message_id,
            message,
            expected_last_modified_at_ms,
        )

    async def truncate_messages_from_cursor(
        self: DatabaseMessagesStorageOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        message_id: int,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_truncate_messages_from_cursor,
            conv_id,
            user_id,
            created_at_ms,
            message_id,
            expected_last_modified_at_ms,
        )

    async def delete_message_by_cursor(
        self: DatabaseMessagesStorageOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        message_id: int,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_delete_message_by_cursor,
            conv_id,
            user_id,
            created_at_ms,
            message_id,
            expected_last_modified_at_ms,
        )

    async def remove_context_compaction_boundary(
        self: DatabaseMessagesStorageOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        tool_call_id: str,
        expected_last_modified_at_ms: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_remove_context_compaction_boundary,
            conv_id,
            user_id,
            assistant_turn_at_ms,
            model_variant_index,
            tool_call_id,
            expected_last_modified_at_ms,
        )

    async def commit_manual_compaction_terminal(
        self: DatabaseMessagesStorageOwnerProtocol,
        request: ManualCompactionTerminalCommitRequest,
    ) -> ManualCompactionTerminalCommitResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_commit_manual_compaction_terminal,
            request,
        )

    async def commit_manual_compaction_start(
        self: DatabaseMessagesStorageOwnerProtocol,
        request: ManualCompactionStartCommitRequest,
    ) -> ManualCompactionStartCommitResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_commit_manual_compaction_start,
            request,
        )
