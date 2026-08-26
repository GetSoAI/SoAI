"""SoAI - Agent turn process-boundary reconciliation queries [backend/database/repositories/users/agent_turn_process_boundary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.repositories.users.agent_turn_rows import format_agent_turn_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAgentTurnProcessBoundary",)


class DatabaseAgentTurnProcessBoundary:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def query_running_turns_from_other_boots(
        self,
        *,
        current_boot_id: str,
        limit: int,
    ) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE status = 'running' AND server_boot_id != ?
                ORDER BY updated_at_ms ASC, turn_id ASC
                LIMIT ?
                """,
                (current_boot_id, int(limit)),
            )
            return [formatted for row in rows if (formatted := format_agent_turn_row(row))]

        return await self.core.reader.execute_read(_query)

    async def query_all_running_turns(self, *, limit: int) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_agent_turns
                WHERE status = 'running'
                ORDER BY updated_at_ms ASC, turn_id ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            return [formatted for row in rows if (formatted := format_agent_turn_row(row))]

        return await self.core.reader.execute_read(_query)

    async def query_terminal_subagent_turns_with_active_parent_tool_calls(
        self,
        *,
        limit: int,
    ) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            rows = await query_to_dicts(
                database,
                """
                SELECT at.*
                FROM webui_agent_turns AS at
                INNER JOIN webui_chat_tool_calls AS tc
                   ON tc.conv_id = at.conv_id
                  AND tc.call_id = at.parent_tool_call_id
                  AND tc.turn_id = at.parent_turn_id
                  AND tc.iteration_index = at.parent_iteration_index
                  AND tc.tool_name = 'subagent_spawn'
                WHERE at.turn_scope = 'subagent'
                  AND at.status IN ('completed', 'cancelled', 'error', 'max_iterations', 'abandoned')
                  AND at.finished_at_ms IS NOT NULL
                  AND tc.status IN ('pending', 'running')
                ORDER BY at.finished_at_ms ASC, at.turn_id ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            return [formatted for row in rows if (formatted := format_agent_turn_row(row))]

        return await self.core.reader.execute_read(_query)

    async def query_terminal_root_turn_active_tool_calls(self, *, limit: int) -> list[JSONDict]:
        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            rows = await query_to_dicts(
                database,
                """
                SELECT
                    at.conv_id,
                    at.turn_id,
                    at.status AS turn_status,
                    at.error_message AS turn_error_message,
                    at.finished_at_ms AS turn_finished_at_ms,
                    tc.id AS tool_storage_call_id,
                    tc.tool_name,
                    tc.status AS tool_status
                FROM webui_agent_turns AS at
                INNER JOIN webui_chat_tool_calls AS tc
                   ON tc.conv_id = at.conv_id
                  AND tc.turn_id = at.turn_id
                WHERE at.turn_scope = 'root'
                  AND at.status IN ('completed', 'cancelled', 'error', 'max_iterations', 'abandoned')
                  AND at.finished_at_ms IS NOT NULL
                  AND tc.status IN ('pending', 'running')
                ORDER BY at.finished_at_ms ASC, tc.sequence_index ASC, tc.id ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            return [_format_active_tool_call_row(row) for row in rows]

        return await self.core.reader.execute_read(_query)


def _format_active_tool_call_row(
    row: Mapping[str, int | float | str | bytes | None],
) -> JSONDict:
    formatted: JSONDict = {}
    for key, value in row.items():
        if isinstance(value, bytes):
            formatted[key] = value.decode("utf-8", errors="replace")
        else:
            formatted[key] = value
    return formatted
