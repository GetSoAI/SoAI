"""SoAI - Assistant message event query helpers [backend/database/repositories/users/message_event_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.database.protocols import DatabaseReaderProtocol
from core.errors.exceptions import DatabaseError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from database.core.query_execution import query_to_dicts

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("load_assistant_events_for_conversation",)


async def load_assistant_events_for_conversation(
    reader: DatabaseReaderProtocol,
    conv_id: str,
) -> list[SQLiteRowDict]:
    async def _query(database: aiosqlite.Connection) -> list[SQLiteRowDict]:
        return await query_to_dicts(
            database,
            "SELECT assistant_at_ms, sequence, assistant_revision, event_type, payload_json, created_at_ms FROM webui_assistant_message_events WHERE conv_id = ? ORDER BY assistant_at_ms ASC, sequence ASC, created_at_ms ASC",
            (conv_id,),
        )

    try:
        return await reader.execute_read(_query)
    except RECOVERABLE_EXCEPTIONS as exception:
        raise DatabaseError(
            "Failed to load assistant message events for conversation.",
            details={"conv_id": conv_id},
            operation="database_users.get_assistant_events_for_conversation",
            cause=exception,
        ) from exception
