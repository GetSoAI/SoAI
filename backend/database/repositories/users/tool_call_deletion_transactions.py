"""SoAI - Tool call deletion transactions [backend/database/repositories/users/tool_call_deletion_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.repositories.users.context_compaction_metric_events import (
    sync_delete_context_compaction_metric_events_for_assistant_turn,
)

__all__ = ("sync_delete_tool_calls_for_assistant_turn_rows",)


def sync_delete_tool_calls_for_assistant_turn_rows(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> int:
    sync_delete_context_compaction_metric_events_for_assistant_turn(
        conn,
        conv_id=conv_id,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
    )
    conn.execute(
        """
        DELETE FROM webui_tool_call_live_events
        WHERE conv_id = ? AND assistant_turn_at_ms = ? AND model_variant_index = ?
        """,
        (conv_id, assistant_turn_at_ms, model_variant_index),
    )
    cursor = conn.execute(
        """
        DELETE FROM webui_chat_tool_calls
        WHERE conv_id = ? AND assistant_turn_at_ms = ? AND model_variant_index = ?
        """,
        (conv_id, assistant_turn_at_ms, model_variant_index),
    )
    return cursor.rowcount
