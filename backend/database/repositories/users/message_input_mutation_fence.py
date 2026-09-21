"""SoAI - Durable conversation input fences for message mutation [backend/database/repositories/users/message_input_mutation_fence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError

__all__ = ("require_message_mutation_allowed",)


def require_message_mutation_allowed(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    where_sql: str,
    params: tuple[int | str, ...],
) -> None:
    running_root_turn = conn.execute(
        """
        SELECT 1
        FROM webui_agent_turns
        WHERE conv_id = ? AND user_id = ? AND turn_scope = 'root' AND status = 'running'
        LIMIT 1
        """,
        (conv_id, user_id),
    ).fetchone()
    if running_root_turn is not None:
        raise ConflictError("Conversation messages cannot change while an agent is running.")
    linked_active_input = conn.execute(
        f"""
        SELECT 1
        FROM webui_conversation_inputs AS input
        INNER JOIN webui_messages AS message ON message.conv_id = input.conv_id
        WHERE message.conv_id = ?
          AND input.state IN ('pending', 'materializing', 'running', 'input_required')
          AND (
              message.id = input.materialized_message_id
              OR (
                  message.role = 'assistant'
                  AND input.request_id IS NOT NULL
                  AND (
                      message.request_id = input.request_id
                      OR message.request_id GLOB input.request_id || ':variant:[0-9]*'
                  )
              )
              OR (
                  input.regeneration_request_json IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM webui_messages AS source
                      WHERE source.conv_id = input.conv_id
                        AND source.id = input.materialized_message_id
                        AND (
                            message.created_at_ms < source.created_at_ms
                            OR (
                                message.created_at_ms = source.created_at_ms
                                AND message.id <= source.id
                            )
                        )
                  )
              )
          )
          AND ({where_sql})
        LIMIT 1
        """,
        (conv_id, *params),
    ).fetchone()
    if linked_active_input is not None:
        raise ConflictError("Messages owned by an active conversation input cannot be mutated.")
