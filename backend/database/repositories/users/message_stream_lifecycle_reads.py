"""SoAI - Streaming assistant message lifecycle reads [backend/database/repositories/users/message_stream_lifecycle_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.flags import FEATURE_PROMPTS

if TYPE_CHECKING:
    from database.repositories.users.internal_protocols import (
        DatabaseMessagesCoreOwnerProtocol,
    )

__all__ = ("has_unfinalized_assistant_stream",)


async def has_unfinalized_assistant_stream(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> bool:
        cursor = await database.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM webui_messages AS messages
                INNER JOIN webui_conversations AS conversations
                    ON conversations.id = messages.conv_id
                WHERE messages.conv_id = ?
                  AND conversations.user_id = ?
                  AND messages.role = 'assistant'
                  AND messages.finalized_at_ms IS NULL
            )
            """,
            (conv_id, user_id),
        )
        row = await cursor.fetchone()
        return row is not None and bool(row[0])

    return await self.core.reader.execute_read(_query)
