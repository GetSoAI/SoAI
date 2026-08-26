"""SoAI - Canonical agent-history database queries [backend/database/repositories/users/agent_history_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.protocols import DatabaseReaderProtocol
from core.errors.exceptions import DatabaseError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from database.repositories.users.canonical_agent_history_reads import (
    query_canonical_agent_history,
)
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.read_transactions import run_user_read_transaction

if TYPE_CHECKING:
    import aiosqlite

    from core.types.json import JSONDict

__all__ = ("load_canonical_agent_history_for_conversation",)


async def load_canonical_agent_history_for_conversation(
    reader: DatabaseReaderProtocol,
    *,
    conv_id: str,
    user_id: int,
    before_timestamp_exclusive: int | None = None,
) -> list[JSONDict] | None:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict] | None:
        async def _transaction(
            transaction_database: aiosqlite.Connection,
        ) -> list[JSONDict] | None:
            if not await conversation_exists_for_user(
                transaction_database,
                conv_id=conv_id,
                user_id=user_id,
            ):
                return None
            history = await query_canonical_agent_history(
                transaction_database,
                conv_id=conv_id,
                before_timestamp_exclusive=before_timestamp_exclusive,
            )
            return history

        return await run_user_read_transaction(database, _transaction)

    try:
        return await reader.execute_read(_query)
    except RECOVERABLE_EXCEPTIONS as exception:
        raise DatabaseError(
            "Failed to load canonical agent history for conversation.",
            details={"conv_id": conv_id, "user_id": user_id},
            operation="database_users.get_canonical_agent_history",
            cause=exception,
        ) from exception
