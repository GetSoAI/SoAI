"""SoAI - Conversation input dispatch holds after user interrupts [backend/database/repositories/users/conversation_input_dispatch_holds.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.epoch import epoch_ms
from database.repositories.users.conversation_input_constants import CONVERSATION_INPUT_HELD_SQL

__all__ = (
    "sync_hold_pending_conversation_prompts",
    "sync_release_conversation_input_holds",
)


def sync_hold_pending_conversation_prompts(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
) -> int:
    updated_at_ms = epoch_ms()
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_inputs
        SET source_metadata_json = json_set(source_metadata_json, '$.dispatch_held', json('true')),
            updated_at_ms = ?
        WHERE conv_id = ? AND user_id = ?
          AND state = 'pending'
          AND input_type = 'prompt'
          AND transport_origin = 'chat'
          AND regeneration_request_json IS NULL
          AND NOT ({CONVERSATION_INPUT_HELD_SQL})
          AND conversation_generation = (
              SELECT input_generation
              FROM webui_conversations
              WHERE id = webui_conversation_inputs.conv_id
                AND user_id = webui_conversation_inputs.user_id
          )
        """,
        (updated_at_ms, conv_id, user_id),
    )
    return cursor.rowcount


def sync_release_conversation_input_holds(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
) -> int:
    updated_at_ms = epoch_ms()
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_inputs
        SET source_metadata_json = json_remove(source_metadata_json, '$.dispatch_held'),
            updated_at_ms = ?
        WHERE conv_id = ? AND user_id = ?
          AND state = 'pending'
          AND {CONVERSATION_INPUT_HELD_SQL}
        """,
        (updated_at_ms, conv_id, user_id),
    )
    return cursor.rowcount
