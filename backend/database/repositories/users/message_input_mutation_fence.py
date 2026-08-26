"""SoAI - Durable conversation input fences for message mutation [backend/database/repositories/users/message_input_mutation_fence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError

__all__ = ("require_message_rows_not_linked_to_active_inputs",)


def require_message_rows_not_linked_to_active_inputs(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    where_sql: str,
    params: tuple[int | str, ...],
) -> None:
    linked_active_input = conn.execute(
        f"""
        SELECT 1
        FROM webui_conversation_inputs AS input
        INNER JOIN webui_messages AS message
            ON message.id = input.materialized_message_id
        WHERE message.conv_id = ?
          AND input.state IN ('materializing', 'running', 'input_required')
          AND {where_sql}
        LIMIT 1
        """,
        (conv_id, *params),
    ).fetchone()
    if linked_active_input is not None:
        raise ConflictError("Messages owned by an active conversation input cannot be mutated.")
