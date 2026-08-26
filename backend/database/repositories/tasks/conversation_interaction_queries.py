"""SoAI - Conversation interaction checkpoint queries [backend/database/repositories/tasks/conversation_interaction_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

__all__ = ("has_conversation_interaction_checkpoint",)


async def has_conversation_interaction_checkpoint(
    conn: aiosqlite.Connection,
    input_id: str,
    task_id: str,
) -> bool:
    cursor = await conn.execute(
        """
        SELECT 1 FROM webui_conversation_inputs
        WHERE input_id = ? AND task_id = ? AND state = 'input_required'
        LIMIT 1
        """,
        (input_id, task_id),
    )
    row = await cursor.fetchone()
    return row is not None
