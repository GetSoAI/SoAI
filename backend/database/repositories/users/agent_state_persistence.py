"""SoAI - Shared agent state persistence primitives [backend/database/repositories/users/agent_state_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from core.errors.exceptions import DatabaseError, ValidationError
from core.types.json import JSONDict
from core.users.user_id import require_strict_user_id
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.row_materialization import coerce_sqlite_row_dict_to_json_dict
from database.core.sql_builders import validate_sql_identifier
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "RevisionedAgentStateWrite",
    "coerce_agent_state_row_identity",
    "sync_upsert_revisioned_agent_state_write",
)

_AGENT_PLAN_TABLE = "webui_agent_plan"
_AGENT_TODO_STATE_TABLE = "webui_agent_todo_state"
_AGENT_PLAN_VALUE_COLUMNS = ("title", "markdown")
_AGENT_TODO_STATE_VALUE_COLUMNS = ("explanation", "todo_json")
_AGENT_PLAN_UPSERT_SQL = """
INSERT INTO webui_agent_plan (conv_id, user_id, revision, updated_at_ms, title, markdown)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(conv_id, user_id) DO UPDATE SET
    revision = excluded.revision,
    updated_at_ms = excluded.updated_at_ms,
    title = excluded.title,
    markdown = excluded.markdown
WHERE excluded.revision > webui_agent_plan.revision
"""
_AGENT_TODO_STATE_UPSERT_SQL = """
INSERT INTO webui_agent_todo_state (
    conv_id, user_id, revision, updated_at_ms, explanation, todo_json
)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(conv_id, user_id) DO UPDATE SET
    revision = excluded.revision,
    updated_at_ms = excluded.updated_at_ms,
    explanation = excluded.explanation,
    todo_json = excluded.todo_json
WHERE excluded.revision > webui_agent_todo_state.revision
"""


@dataclass(frozen=True, slots=True)
class RevisionedAgentStateWrite:
    table_name: str
    value_columns: tuple[str, ...]
    conv_id: str
    user_id: int
    revision: int
    updated_at_ms: int
    values: tuple[SQLiteValue, ...]
    require_no_running_turn: bool

    def __post_init__(self) -> None:
        try:
            normalized_table_name = validate_sql_identifier(self.table_name, label="table_name")
        except ValidationError as exception:
            raise DatabaseError(
                "Revisioned agent state write table_name is invalid.",
                operation="database.agent_state_persistence.validate_identifier",
            ) from exception
        if normalized_table_name != self.table_name:
            raise DatabaseError(
                "Revisioned agent state write table_name must not contain surrounding whitespace.",
                operation="database.agent_state_persistence.validate_identifier",
            )
        for column_name in self.value_columns:
            try:
                normalized_column_name = validate_sql_identifier(
                    column_name,
                    label="value_columns",
                )
            except ValidationError as exception:
                raise DatabaseError(
                    "Revisioned agent state write value_columns is invalid.",
                    operation="database.agent_state_persistence.validate_identifier",
                ) from exception
            if normalized_column_name != column_name:
                raise DatabaseError(
                    "Revisioned agent state write value_columns must not contain surrounding whitespace.",
                    operation="database.agent_state_persistence.validate_identifier",
                )
        if len(self.value_columns) != len(self.values):
            raise DatabaseError(
                "Revisioned agent state write column count does not match value count.",
                operation="database.agent_state_persistence.validate_write",
            )


def _resolve_revisioned_agent_state_upsert_sql(request: RevisionedAgentStateWrite) -> str:
    if request.table_name == _AGENT_PLAN_TABLE:
        if request.value_columns == _AGENT_PLAN_VALUE_COLUMNS:
            return _AGENT_PLAN_UPSERT_SQL
    if request.table_name == _AGENT_TODO_STATE_TABLE:
        if request.value_columns == _AGENT_TODO_STATE_VALUE_COLUMNS:
            return _AGENT_TODO_STATE_UPSERT_SQL
    raise DatabaseError(
        "Revisioned agent state write target is not supported.",
        operation="database.agent_state_persistence.resolve_upsert_sql",
    )


def coerce_agent_state_row_identity(
    row: SQLiteRowDict | None,
    *,
    default_conv_id: str,
    default_user_id: int,
    invalid_utf8_message: str,
    operation: str,
) -> tuple[JSONDict | None, str, int]:
    coerced_row = (
        coerce_sqlite_row_dict_to_json_dict(
            row,
            invalid_utf8_message=invalid_utf8_message,
            operation=operation,
        )
        if isinstance(row, dict)
        else None
    )
    conv_id = str(default_conv_id or "").strip()
    if not conv_id:
        raise DatabaseError(
            "Agent state default conv_id is invalid.",
            operation=operation,
        )
    try:
        user_id = require_strict_user_id(default_user_id)
    except ValidationError as exception:
        raise DatabaseError(
            "Agent state default user_id is invalid.",
            operation=operation,
        ) from exception
    if coerced_row is not None:
        row_conv_id = coerced_row.get("conv_id")
        row_user_id = coerced_row.get("user_id")
        if not isinstance(row_conv_id, str) or not row_conv_id.strip():
            raise DatabaseError(
                "Agent state row conv_id is invalid.",
                operation=operation,
            )
        conv_id = row_conv_id.strip()
        try:
            user_id = require_strict_user_id(row_user_id)
        except ValidationError as exception:
            raise DatabaseError(
                "Agent state row user_id is invalid.",
                operation=operation,
            ) from exception
    return (coerced_row, conv_id, user_id)


def _sync_root_turn_running(
    sqlite_conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
) -> bool:
    running_turn = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            SELECT turn_id
            FROM webui_agent_turns
            WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root' AND status = 'running'
            LIMIT 1
            """,
            (conv_id, int(user_id)),
        ),
    )
    return running_turn is not None


def sync_upsert_revisioned_agent_state_write(
    sqlite_conn: sqlite3.Connection,
    request: RevisionedAgentStateWrite,
) -> bool:
    if request.require_no_running_turn and _sync_root_turn_running(
        sqlite_conn,
        request.conv_id,
        request.user_id,
    ):
        return False
    before = sqlite_conn.total_changes
    sqlite_conn.execute(
        _resolve_revisioned_agent_state_upsert_sql(request),
        (
            request.conv_id,
            int(request.user_id),
            int(request.revision),
            int(request.updated_at_ms),
            *request.values,
        ),
    )
    return sqlite_conn.total_changes > before
