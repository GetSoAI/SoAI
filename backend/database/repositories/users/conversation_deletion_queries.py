"""SoAI - Conversation deletion lifecycle selection queries [backend/database/repositories/users/conversation_deletion_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import coerce_required_nonempty_str_from_sqlite_row
from database.repositories.users.conversation_input_active_state_reads import (
    query_active_conversation_input_summaries_by_conversation,
)

if TYPE_CHECKING:
    import aiosqlite

    from core.conversations.conversation_input_active_state import ActiveConversationInputSummary
    from core.database.protocols import DatabaseCoreProtocol

__all__ = (
    "list_conversation_ids_for_deletion",
    "summarize_active_conversation_inputs_for_deletion",
)


async def list_conversation_ids_for_deletion(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
) -> tuple[str, ...]:
    async def _query(database: aiosqlite.Connection) -> tuple[str, ...]:
        rows = await query_to_dicts(
            database,
            """
            SELECT id
            FROM webui_conversations
            WHERE user_id = ?
            ORDER BY last_modified_at_ms DESC, id DESC
            """,
            (user_id,),
        )
        return tuple(coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows)

    return await core.reader.execute_read(_query)


async def summarize_active_conversation_inputs_for_deletion(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
) -> dict[str, ActiveConversationInputSummary]:
    return await core.reader.execute_read(
        query_active_conversation_input_summaries_by_conversation,
        user_id,
    )
