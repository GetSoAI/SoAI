"""SoAI - Manual compaction logical message index resolution [backend/database/repositories/users/manual_compaction_message_index.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

__all__ = ("sync_resolve_manual_compaction_message_index",)


def _sync_resolve_canonical_assistant_id(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
) -> int:
    row = conn.execute(
        """
        SELECT id
        FROM webui_messages
        WHERE conv_id = ?
          AND role = 'assistant'
          AND created_at_ms = ?
          AND assistant_turn_at_ms = created_at_ms
          AND model_variant_index = 0
        ORDER BY id ASC
        LIMIT 1
        """,
        (conv_id, assistant_at_ms),
    ).fetchone()
    if row is None:
        raise ValidationError("Compaction assistant message target could not be resolved.")
    message_id = row[0]
    if not is_strict_int(message_id) or message_id < 0:
        raise ValidationError("Compaction assistant message id is invalid.")
    return int(message_id)


def sync_resolve_manual_compaction_message_index(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
) -> int:
    assistant_id = _sync_resolve_canonical_assistant_id(
        conn,
        conv_id=conv_id,
        assistant_at_ms=assistant_at_ms,
    )
    row = conn.execute(
        """
        SELECT COUNT(*) AS message_index
        FROM webui_messages
        WHERE conv_id = ?
          AND message_type = 'chat'
          AND role != 'system'
          AND (role != 'assistant' OR model_variant_index = 0)
          AND (created_at_ms < ? OR (created_at_ms = ? AND id < ?))
        """,
        (conv_id, assistant_at_ms, assistant_at_ms, assistant_id),
    ).fetchone()
    if row is None:
        return 0
    message_index = row[0]
    if not is_strict_int(message_index) or message_index < 0:
        raise ValidationError("Compaction message index is invalid.")
    return int(message_index)
