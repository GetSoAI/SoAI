"""SoAI - Message counting and timestamp reads [backend/database/repositories/users/messages_counting_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.conversations.conversation_message_sync_cursor import (
    ConversationMessageSyncCursor,
)
from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.message_counting_queries import (
    load_conversation_message_count,
)

if TYPE_CHECKING:
    from database.repositories.users.internal_protocols import (
        DatabaseMessagesCoreOwnerProtocol,
    )

__all__ = (
    "count_messages",
    "count_messages_including_comparison_variants",
    "get_latest_message_timestamp",
    "get_message_sync_cursor",
)


async def get_latest_message_timestamp(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
) -> int | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> int | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        row = await query_one_to_dict(
            database,
            "SELECT created_at_ms FROM webui_messages WHERE conv_id = ? ORDER BY created_at_ms DESC, id DESC LIMIT 1",
            (conv_id,),
        )
        if row is None:
            return None
        timestamp_value = row.get("created_at_ms")
        if not is_strict_int(timestamp_value):
            raise ValidationError("Stored conversation message created_at_ms must be an integer.")
        return timestamp_value

    return await self.core.reader.execute_read(_query)


async def get_message_sync_cursor(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
) -> ConversationMessageSyncCursor | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> ConversationMessageSyncCursor | None:
        row = await query_one_to_dict(
            database,
            "SELECT c.last_modified_at_ms, c.message_count, (SELECT created_at_ms FROM webui_messages WHERE conv_id = c.id ORDER BY created_at_ms DESC, id DESC LIMIT 1) AS latest_timestamp FROM webui_conversations AS c WHERE c.id = ? AND c.user_id = ?",
            (conv_id, user_id),
        )
        if row is None:
            return None
        timestamp_value = row.get("latest_timestamp")
        latest_timestamp: int | None = None
        if timestamp_value is not None:
            if not is_strict_int(timestamp_value):
                raise ValidationError(
                    "Stored conversation message created_at_ms must be an integer.",
                )
            latest_timestamp = timestamp_value
        message_count = row.get("message_count")
        if (
            isinstance(message_count, bool)
            or not isinstance(message_count, int)
            or message_count < 0
        ):
            raise ValidationError(
                "Stored conversation message count must be a non-negative integer.",
            )
        return ConversationMessageSyncCursor(
            latest_timestamp=latest_timestamp,
            last_modified_at_ms=require_unix_epoch_ms(
                row.get("last_modified_at_ms"),
                error_message="Conversation last_modified_at_ms must be an epoch-millisecond integer.",
                enforce_maximum=False,
            ),
            message_count=int(message_count),
        )

    return await self.core.reader.execute_read(_query)


async def count_messages(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    *,
    before_timestamp_exclusive: int | None = None,
) -> int | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> int | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        return await load_conversation_message_count(
            database,
            conv_id=conv_id,
            before_timestamp_exclusive=before_timestamp_exclusive,
            counting_mode="canonical",
        )

    return await self.core.reader.execute_read(_query)


async def count_messages_including_comparison_variants(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    *,
    before_timestamp_exclusive: int | None = None,
) -> int | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> int | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        return await load_conversation_message_count(
            database,
            conv_id=conv_id,
            before_timestamp_exclusive=before_timestamp_exclusive,
            counting_mode="including_comparison_variants",
        )

    return await self.core.reader.execute_read(_query)
