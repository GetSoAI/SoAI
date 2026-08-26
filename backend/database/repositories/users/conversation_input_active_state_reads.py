"""SoAI - Active conversation input state summary reads [backend/database/repositories/users/conversation_input_active_state_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.conversations.conversation_input_active_state import ActiveConversationInputSummary
from core.errors.exceptions import StateError
from database.core.query_execution import query_to_dicts, sync_fetch_all_as_dicts
from database.repositories.users.conversation_input_constants import (
    ACTIVE_INPUT_STATES,
    CONVERSATION_INPUT_ACTIVE_ORDER_SQL,
    CONVERSATION_INPUT_DISPATCH_RANK_SQL,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "build_active_conversation_input_summary",
    "query_active_conversation_input_summaries_by_conversation",
    "query_active_conversation_input_summary",
    "sync_read_active_conversation_input_summary",
)

CONVERSATION_ACTIVE_INPUTS_SQL_TEMPLATE = """
WITH ranked_inputs AS (
    SELECT *, {dispatch_rank} AS dispatch_rank
    FROM webui_conversation_inputs
)
SELECT input_id, state
FROM ranked_inputs
WHERE conv_id = ? AND user_id = ?
  AND state IN ('pending', 'materializing', 'running', 'input_required')
ORDER BY {active_order}
"""

USER_ACTIVE_INPUTS_SQL_TEMPLATE = """
WITH ranked_inputs AS (
    SELECT *, {dispatch_rank} AS dispatch_rank
    FROM webui_conversation_inputs
)
SELECT conv_id, input_id, state
FROM ranked_inputs
WHERE user_id = ?
  AND state IN ('pending', 'materializing', 'running', 'input_required')
ORDER BY conv_id ASC, {active_order}
"""


def _render_active_inputs_sql(template: str) -> str:
    return template.format(
        dispatch_rank=CONVERSATION_INPUT_DISPATCH_RANK_SQL,
        active_order=CONVERSATION_INPUT_ACTIVE_ORDER_SQL,
    )


def _require_row_text(row: SQLiteRowDict, column: str) -> str:
    value = row.get(column)
    if not isinstance(value, str) or not value.strip():
        raise StateError("Active conversation input row is invalid.")
    return value.strip()


def _require_active_state(row: SQLiteRowDict) -> str:
    state = _require_row_text(row, "state")
    if state not in ACTIVE_INPUT_STATES:
        raise StateError("Active conversation input state is invalid.")
    return state


def build_active_conversation_input_summary(
    rows: Sequence[SQLiteRowDict],
) -> ActiveConversationInputSummary:
    head_input_id: str | None = None
    head_state: str | None = None
    active_states: list[str] = []
    for row in rows:
        input_id = _require_row_text(row, "input_id")
        state = _require_active_state(row)
        if head_input_id is None:
            head_input_id = input_id
            head_state = state
        if state not in active_states:
            active_states.append(state)
    return ActiveConversationInputSummary(
        active_count=len(rows),
        head_input_id=head_input_id,
        head_state=head_state,
        active_states=tuple(active_states),
    )


async def query_active_conversation_input_summary(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
) -> ActiveConversationInputSummary:
    rows = await query_to_dicts(
        database,
        _render_active_inputs_sql(CONVERSATION_ACTIVE_INPUTS_SQL_TEMPLATE),
        (conv_id, user_id),
    )
    return build_active_conversation_input_summary(rows)


async def query_active_conversation_input_summaries_by_conversation(
    database: aiosqlite.Connection,
    user_id: int,
) -> dict[str, ActiveConversationInputSummary]:
    rows = await query_to_dicts(
        database,
        _render_active_inputs_sql(USER_ACTIVE_INPUTS_SQL_TEMPLATE),
        (user_id,),
    )
    rows_by_conversation: dict[str, list[SQLiteRowDict]] = {}
    for row in rows:
        conv_id = _require_row_text(row, "conv_id")
        if conv_id not in rows_by_conversation:
            rows_by_conversation[conv_id] = []
        rows_by_conversation[conv_id].append(row)
    return {
        conv_id: build_active_conversation_input_summary(conversation_rows)
        for conv_id, conversation_rows in rows_by_conversation.items()
    }


def sync_read_active_conversation_input_summary(
    sqlite_conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
) -> ActiveConversationInputSummary:
    rows = sync_fetch_all_as_dicts(
        sqlite_conn.execute(
            _render_active_inputs_sql(CONVERSATION_ACTIVE_INPUTS_SQL_TEMPLATE),
            (conv_id, user_id),
        ),
    )
    return build_active_conversation_input_summary(rows)
