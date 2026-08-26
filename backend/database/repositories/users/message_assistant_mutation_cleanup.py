"""SoAI - Assistant-owned cleanup for targeted message mutations [backend/database/repositories/users/message_assistant_mutation_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.integers import is_strict_int
from database.repositories.users.tool_call_deletion_transactions import (
    sync_delete_tool_calls_for_assistant_turn_rows,
)

__all__ = (
    "delete_auxiliary_for_assistant_rows",
    "select_assistant_rows_for_delete",
)


def select_assistant_rows_for_delete(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    where_sql: str,
    params: tuple[int | str, ...],
) -> list[tuple[int, int]]:
    rows = conn.execute(
        f"SELECT assistant_turn_at_ms, model_variant_index FROM webui_messages WHERE conv_id = ? AND role = 'assistant' AND {where_sql}",
        (conv_id, *params),
    ).fetchall()
    identities: list[tuple[int, int]] = []
    for assistant_turn_at_ms, model_variant_index in rows:
        if is_strict_int(assistant_turn_at_ms) and is_strict_int(model_variant_index):
            identities.append((int(assistant_turn_at_ms), int(model_variant_index)))
    return identities


def delete_auxiliary_for_assistant_rows(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_rows: list[tuple[int, int]],
) -> None:
    for assistant_turn_at_ms, model_variant_index in assistant_rows:
        conn.execute(
            """
            DELETE FROM webui_assistant_message_events
            WHERE conv_id = ?
              AND assistant_at_ms IN (
                  SELECT created_at_ms FROM webui_messages
                  WHERE conv_id = ?
                    AND assistant_turn_at_ms = ?
                    AND model_variant_index = ?
                    AND role = 'assistant'
              )
            """,
            (conv_id, conv_id, assistant_turn_at_ms, model_variant_index),
        )
        sync_delete_tool_calls_for_assistant_turn_rows(
            conn,
            conv_id=conv_id,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
        )
