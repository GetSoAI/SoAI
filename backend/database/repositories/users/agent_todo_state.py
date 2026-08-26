"""SoAI - Agent todo state persistence [backend/database/repositories/users/agent_todo_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.agent.state_payloads import build_persisted_agent_todo_payload
from core.agent.state_record_validation import normalize_agent_todo_record
from core.errors.exceptions import DatabaseError, ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from database.core.query_execution import query_one_to_dict
from database.repositories.users.agent_state_persistence import (
    RevisionedAgentStateWrite,
    coerce_agent_state_row_identity,
    sync_upsert_revisioned_agent_state_write,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAgentTodoState",)


def _format_todo_state_row(
    row: SQLiteRowDict | None,
    *,
    conv_id: str,
    user_id: int,
) -> JSONDict | None:
    coerced_row, conv_id, user_id = coerce_agent_state_row_identity(
        row,
        default_conv_id=conv_id,
        default_user_id=user_id,
        invalid_utf8_message="Agent todo row contains invalid utf-8 bytes.",
        operation="database.agent_todo_state.coerce_row",
    )
    normalized_record: JSONDict | None = None
    if coerced_row is not None:
        todo_json_value = coerced_row.get("todo_json")
        if not isinstance(todo_json_value, str):
            raise DatabaseError(
                "Agent todo row field 'todo_json' is invalid.",
                operation="database.agent_todo_state.format_row",
            )
        try:
            todo_value = parse_json_value(todo_json_value, field="webui_agent_todo_state.todo_json")
        except ValidationError as exception:
            raise DatabaseError(
                "Agent todo row field 'todo_json' is invalid.",
                operation="database.agent_todo_state.format_row",
            ) from exception
        normalized_record = {
            "conv_id": coerced_row.get("conv_id"),
            "user_id": coerced_row.get("user_id"),
            "revision": coerced_row.get("revision"),
            "updated_at_ms": coerced_row.get("updated_at_ms"),
            "explanation": coerced_row.get("explanation"),
            "todo": todo_value,
        }
    return normalize_agent_todo_record(
        normalized_record,
        conv_id=conv_id,
        user_id=user_id,
        build_error=lambda message: DatabaseError(
            message,
            operation="database.agent_todo_state.format_row",
        ),
    )


class DatabaseAgentTodoState:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def get_todo_state(self, *, conv_id: str, user_id: int) -> JSONDict | None:
        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT conv_id, user_id, revision, updated_at_ms, explanation, todo_json
                FROM webui_agent_todo_state
                WHERE conv_id = ? AND user_id = ?
                """,
                (conv_id, int(user_id)),
            )
            return _format_todo_state_row(row, conv_id=conv_id, user_id=user_id)

        return await self.core.reader.execute_read(_query)

    async def upsert_todo_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        explanation: str | None,
        todo: list[JSONDict],
    ) -> bool:
        normalized = build_persisted_agent_todo_payload(
            conv_id=conv_id,
            user_id=int(user_id),
            revision=int(revision),
            updated_at_ms=int(updated_at_ms),
            explanation_value=explanation,
            todo_value=todo,
        )
        todo_json = serialize_json_compact_stable(normalized.todo)
        return await self.core.writer.queue_write_operation(
            sync_upsert_revisioned_agent_state_write,
            RevisionedAgentStateWrite(
                table_name="webui_agent_todo_state",
                value_columns=("explanation", "todo_json"),
                conv_id=conv_id,
                user_id=int(user_id),
                revision=int(revision),
                updated_at_ms=int(updated_at_ms),
                values=(normalized.explanation, todo_json),
                require_no_running_turn=False,
            ),
        )

    async def upsert_todo_state_if_no_running_turn(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        explanation: str | None,
        todo: list[JSONDict],
    ) -> bool:
        normalized = build_persisted_agent_todo_payload(
            conv_id=conv_id,
            user_id=int(user_id),
            revision=int(revision),
            updated_at_ms=int(updated_at_ms),
            explanation_value=explanation,
            todo_value=todo,
        )
        todo_json = serialize_json_compact_stable(normalized.todo)
        return await self.core.writer.queue_write_operation(
            sync_upsert_revisioned_agent_state_write,
            RevisionedAgentStateWrite(
                table_name="webui_agent_todo_state",
                value_columns=("explanation", "todo_json"),
                conv_id=conv_id,
                user_id=int(user_id),
                revision=int(revision),
                updated_at_ms=int(updated_at_ms),
                values=(normalized.explanation, todo_json),
                require_no_running_turn=True,
            ),
        )
