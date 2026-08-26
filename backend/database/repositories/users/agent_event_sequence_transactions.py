"""SoAI - Agent event chronology sequence transactions [backend/database/repositories/users/agent_event_sequence_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.users.user_id import require_strict_user_id
from core.validation.epoch import require_unix_epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row

__all__ = (
    "sync_get_agent_event_sequence",
    "sync_reserve_agent_event_sequence_range",
)


def _require_conv_id(value: str) -> str:
    conv_id = str(value or "").strip()
    if not conv_id:
        raise ValidationError("conv_id must be a non-empty string.")
    return conv_id


def _require_count(value: int) -> int:
    if isinstance(value, bool):
        raise ValidationError("count must be a positive integer.")
    count = int(value or 0)
    if count <= 0:
        raise ValidationError("count must be a positive integer.")
    return count


def _extract_sequence(row: dict[str, int | float | str | bytes | None] | None) -> int:
    if row is None:
        return 0
    try:
        sequence = coerce_required_int_from_sqlite_row(row, "sequence")
    except ValidationError as exception:
        raise StateError("Agent event sequence value is invalid.") from exception
    if sequence < 0:
        raise StateError("Agent event sequence value is invalid.")
    return sequence


def sync_get_agent_event_sequence(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> int:
    normalized_conv_id = _require_conv_id(conv_id)
    normalized_user_id = require_strict_user_id(user_id)
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT sequence FROM webui_agent_event_sequences WHERE conv_id = ? AND user_id = ?",
            (normalized_conv_id, int(normalized_user_id)),
        ),
    )
    return _extract_sequence(row)


def sync_reserve_agent_event_sequence_range(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    count: int,
    updated_at_ms: int,
) -> tuple[int, int]:
    normalized_conv_id = _require_conv_id(conv_id)
    normalized_user_id = require_strict_user_id(user_id)
    normalized_count = _require_count(count)
    normalized_updated_at_ms = require_unix_epoch_ms(
        updated_at_ms,
        error_message="updated_at_ms must be a valid unix epoch milliseconds timestamp.",
    )
    sqlite_conn.execute(
        """
        INSERT INTO webui_agent_event_sequences (conv_id, user_id, sequence, updated_at_ms)
        VALUES (?, ?, 0, ?)
        ON CONFLICT(conv_id, user_id) DO NOTHING
        """,
        (
            normalized_conv_id,
            int(normalized_user_id),
            int(normalized_updated_at_ms),
        ),
    )
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            UPDATE webui_agent_event_sequences
               SET sequence = sequence + ?,
                   updated_at_ms = ?
             WHERE conv_id = ?
               AND user_id = ?
             RETURNING sequence
            """,
            (
                int(normalized_count),
                int(normalized_updated_at_ms),
                normalized_conv_id,
                int(normalized_user_id),
            ),
        ),
    )
    end_sequence = _extract_sequence(row)
    if end_sequence <= 0:
        raise StateError("Agent event sequence allocator returned an invalid end sequence.")
    start_sequence = int(end_sequence) - int(normalized_count) + 1
    if start_sequence <= 0:
        raise StateError("Agent event sequence allocator returned an invalid start sequence.")
    return (int(start_sequence), int(end_sequence))
