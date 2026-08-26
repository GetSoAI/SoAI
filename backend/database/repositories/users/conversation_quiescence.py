"""SoAI - Conversation durable work quiescence [backend/database/repositories/users/conversation_quiescence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError

__all__ = (
    "clear_conversation_selection",
    "prepare_conversation_selection",
    "require_selected_conversations_quiescent",
)

CONVERSATION_SELECTION_TABLE = "temp_webui_conversation_delete_selection"


def prepare_conversation_selection(
    conn: sqlite3.Connection,
    conv_ids: tuple[str, ...],
) -> None:
    conn.execute(
        f"CREATE TEMP TABLE IF NOT EXISTS {CONVERSATION_SELECTION_TABLE} (id TEXT PRIMARY KEY, position INTEGER NOT NULL) WITHOUT ROWID",
    )
    conn.execute(f"DELETE FROM {CONVERSATION_SELECTION_TABLE}")
    conn.executemany(
        f"INSERT OR IGNORE INTO {CONVERSATION_SELECTION_TABLE} (id, position) VALUES (?, ?)",
        ((conv_id, index) for index, conv_id in enumerate(conv_ids)),
    )


def clear_conversation_selection(conn: sqlite3.Connection) -> None:
    conn.execute(f"DELETE FROM {CONVERSATION_SELECTION_TABLE}")


def require_selected_conversations_quiescent(
    conn: sqlite3.Connection,
    *,
    user_id: int,
) -> None:
    active_row = conn.execute(
        f"""
        SELECT
            EXISTS(
                SELECT 1 FROM webui_conversation_inputs AS inputs
                INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected ON selected.id = inputs.conv_id
                WHERE inputs.user_id = ?
                  AND inputs.state NOT IN ('completed', 'failed', 'cancelled', 'effect_unknown')
            )
            OR EXISTS(
                SELECT 1 FROM webui_agent_turns AS turns
                INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected ON selected.id = turns.conv_id
                WHERE turns.user_id = ? AND turns.status = 'running'
            )
            OR EXISTS(
                SELECT 1 FROM webui_chat_tool_calls AS calls
                INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected ON selected.id = calls.conv_id
                INNER JOIN webui_conversations AS conversations ON conversations.id = calls.conv_id
                WHERE conversations.user_id = ? AND calls.status IN ('pending', 'running')
            )
            OR EXISTS(
                SELECT 1 FROM automation_runs AS runs
                INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected ON selected.id = runs.conv_id
                WHERE runs.user_id = ? AND runs.status IN ('queued', 'running')
            )
            OR EXISTS(
                SELECT 1 FROM unified_tasks AS tasks
                INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected ON selected.id = tasks.owner_id
                WHERE tasks.user_id = ? AND tasks.owner_type = 'conversation'
                  AND tasks.status NOT IN ('completed', 'failed', 'cancelled')
            )
            OR EXISTS(
                SELECT 1 FROM webui_messages AS messages
                INNER JOIN webui_conversations AS conversations ON conversations.id = messages.conv_id
                INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected ON selected.id = messages.conv_id
                WHERE conversations.user_id = ? AND messages.role = 'assistant'
                  AND messages.finalized_at_ms IS NULL
            )
        """,
        (user_id, user_id, user_id, user_id, user_id, user_id),
    ).fetchone()
    if active_row is not None and bool(active_row[0]):
        raise ConflictError("Conversation operation requires durable work to quiesce.")
