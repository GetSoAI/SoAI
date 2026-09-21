"""SoAI - Conversation input claim deferral transaction [backend/database/repositories/users/conversation_input_claim_deferral.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.epoch import epoch_ms

__all__ = ("sync_defer_conversation_input_claim",)


def sync_defer_conversation_input_claim(
    conn: sqlite3.Connection,
    input_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
) -> bool:
    deferred_at_ms = epoch_ms()
    cursor = conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'pending', claim_owner = NULL, claim_server_boot_id = NULL,
            claimed_at_ms = NULL, running_at_ms = NULL, updated_at_ms = ?
        WHERE input_id = ?
          AND state IN ('materializing', 'running')
          AND claim_generation = ?
          AND claim_owner = ?
          AND claim_server_boot_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM webui_messages AS message
              WHERE message.conv_id = webui_conversation_inputs.conv_id
                AND message.role = 'assistant'
                AND (
                    message.request_id = webui_conversation_inputs.request_id
                    OR message.request_id GLOB webui_conversation_inputs.request_id || ':variant:[0-9]*'
                )
          )
        """,
        (deferred_at_ms, input_id, claim_generation, claim_owner, server_boot_id),
    )
    return cursor.rowcount == 1
