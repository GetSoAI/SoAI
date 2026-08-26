"""SoAI - Agent event chronology sequence repository [backend/database/repositories/users/agent_event_sequences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from database.repositories.users.agent_event_sequence_transactions import (
    sync_get_agent_event_sequence,
    sync_reserve_agent_event_sequence_range,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAgentEventSequences",)


class DatabaseAgentEventSequences:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def reserve_sequence_range(self, *, conv_id: str, user_id: int, count: int) -> JSONDict:
        def _sync_reserve(sqlite_conn: sqlite3.Connection) -> JSONDict:
            start_sequence, end_sequence = sync_reserve_agent_event_sequence_range(
                sqlite_conn,
                conv_id=conv_id,
                user_id=user_id,
                count=int(count),
                updated_at_ms=epoch_ms(),
            )
            return {
                "start_sequence": int(start_sequence),
                "end_sequence": int(end_sequence),
            }

        return await self.core.writer.queue_write_operation(_sync_reserve)

    async def get_current_sequence(self, *, conv_id: str, user_id: int) -> int:
        def _sync_get(sqlite_conn: sqlite3.Connection) -> int:
            return sync_get_agent_event_sequence(
                sqlite_conn,
                conv_id=conv_id,
                user_id=user_id,
            )

        return await self.core.writer.queue_write_operation(_sync_get)
