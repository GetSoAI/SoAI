"""SoAI - Agent turn persistence [backend/database/repositories/users/agent_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.agent_turn_abandonment import (
    sync_abandon_running_turn_if_current,
)
from database.repositories.users.agent_turn_field_updates import (
    sync_write_turn_assistant_text,
    sync_write_turn_token_usage,
)
from database.repositories.users.agent_turn_rows import format_agent_turn_row
from database.repositories.users.agent_turn_transactions import (
    sync_claim_turn_state,
    sync_write_turn_state,
)

if TYPE_CHECKING:
    from core.database.requests import (
        ClaimAgentTurnStateRequest,
        WriteAgentTurnStateRequest,
    )
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAgentTurns",)


class DatabaseAgentTurns:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def write_turn_state(self, request: WriteAgentTurnStateRequest) -> JSONDict:
        record = await self.core.writer.queue_write_operation(
            sync_write_turn_state,
            request,
        )
        if not isinstance(record, dict):
            raise StateError("Agent turn state was persisted but could not be reloaded.")
        return record

    async def claim_turn_state(self, request: ClaimAgentTurnStateRequest) -> JSONDict:
        record = await self.core.writer.queue_write_operation(
            sync_claim_turn_state,
            request,
        )
        if not isinstance(record, dict):
            raise StateError("Agent turn state was persisted but could not be reloaded.")
        return record

    async def write_turn_token_usage(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        execution_token: str,
        token_usage: JSONDict,
        updated_at_ms: int | None = None,
    ) -> JSONDict | None:
        def _sync_write_token_usage(sqlite_conn: sqlite3.Connection) -> JSONDict | None:
            return sync_write_turn_token_usage(
                sqlite_conn,
                conv_id=conv_id,
                user_id=user_id,
                turn_id=turn_id,
                execution_token=execution_token,
                token_usage=token_usage,
                updated_at_ms=updated_at_ms,
            )

        record = await self.core.writer.queue_write_operation(
            _sync_write_token_usage,
        )
        return record if isinstance(record, dict) else None

    async def write_turn_assistant_text(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        execution_token: str,
        assistant_text: str,
        updated_at_ms: int | None = None,
    ) -> JSONDict | None:
        def _sync_write_assistant_text(
            sqlite_conn: sqlite3.Connection,
        ) -> JSONDict | None:
            return sync_write_turn_assistant_text(
                sqlite_conn,
                conv_id=conv_id,
                user_id=user_id,
                turn_id=turn_id,
                execution_token=execution_token,
                assistant_text=assistant_text,
                updated_at_ms=updated_at_ms,
            )

        record = await self.core.writer.queue_write_operation(
            _sync_write_assistant_text,
        )
        return record if isinstance(record, dict) else None

    async def abandon_running_turn_if_current(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        execution_token: str,
        finished_at_ms: int,
    ) -> JSONDict | None:
        def _sync_abandon_running_turn_if_current(
            sqlite_conn: sqlite3.Connection,
        ) -> JSONDict | None:
            return sync_abandon_running_turn_if_current(
                sqlite_conn,
                conv_id=conv_id,
                user_id=user_id,
                turn_id=turn_id,
                execution_token=execution_token,
                finished_at_ms=finished_at_ms,
            )

        record = await self.core.writer.queue_write_operation(
            _sync_abandon_running_turn_if_current,
        )
        return record if isinstance(record, dict) else None

    async def get_latest_finalized_turn(self, *, conv_id: str, user_id: int) -> JSONDict | None:
        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root' AND status != 'running'
                ORDER BY updated_at_ms DESC, turn_id DESC
                LIMIT 1
                """,
                (conv_id, int(user_id)),
            )
            return format_agent_turn_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_running_root_turn(self, *, conv_id: str, user_id: int) -> JSONDict | None:
        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root' AND status = 'running'
                ORDER BY updated_at_ms DESC, turn_id DESC
                LIMIT 1
                """,
                (conv_id, int(user_id)),
            )
            return format_agent_turn_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_turn(self, *, conv_id: str, user_id: int, turn_id: str) -> JSONDict | None:
        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE conv_id = ? AND user_id = ? AND turn_id = ?
                LIMIT 1
                """,
                (conv_id, int(user_id), turn_id),
            )
            return format_agent_turn_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_subagent_turn(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
    ) -> JSONDict | None:
        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE conv_id = ? AND user_id = ? AND turn_scope = 'subagent' AND turn_id = ?
                LIMIT 1
                """,
                (conv_id, int(user_id), turn_id),
            )
            return format_agent_turn_row(row)

        return await self.core.reader.execute_read(_query)

    async def get_running_root_turns(self, *, conv_id: str, user_id: int) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root' AND status = 'running'
                ORDER BY updated_at_ms DESC, turn_id DESC
                """,
                (conv_id, int(user_id)),
            )
            return [formatted for row in rows if (formatted := format_agent_turn_row(row))]

        return await self.core.reader.execute_read(_query)

    async def get_running_subagent_turns(
        self,
        *,
        conv_id: str,
        user_id: int,
        parent_turn_id: str,
    ) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE conv_id = ?
                  AND user_id = ?
                  AND turn_scope = 'subagent'
                  AND parent_turn_id = ?
                  AND status = 'running'
                ORDER BY updated_at_ms DESC, turn_id DESC
                """,
                (conv_id, int(user_id), parent_turn_id),
            )
            return [formatted for row in rows if (formatted := format_agent_turn_row(row))]

        return await self.core.reader.execute_read(_query)

    async def list_subagent_summaries(
        self,
        *,
        conv_id: str,
        user_id: int,
        parent_turn_id: str | None = None,
    ) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            if isinstance(parent_turn_id, str) and parent_turn_id.strip():
                rows = await query_to_dicts(
                    database,
                    """
                    SELECT *
                    FROM webui_agent_turns
                    WHERE conv_id = ?
                      AND user_id = ?
                      AND turn_scope = 'subagent'
                      AND parent_turn_id = ?
                    ORDER BY started_at_ms ASC, updated_at_ms ASC, turn_id ASC
                    """,
                    (conv_id, int(user_id), parent_turn_id.strip()),
                )
            else:
                rows = await query_to_dicts(
                    database,
                    """
                    SELECT *
                    FROM webui_agent_turns
                    WHERE conv_id = ? AND user_id = ? AND turn_scope = 'subagent'
                    ORDER BY started_at_ms ASC, updated_at_ms ASC, turn_id ASC
                    """,
                    (conv_id, int(user_id)),
                )
            return [formatted for row in rows if (formatted := format_agent_turn_row(row))]

        return await self.core.reader.execute_read(_query)
