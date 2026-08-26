"""SoAI - Durable orchestrator queue sequence allocation [backend/database/repositories/tasks/orchestrator_queue_sequence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row

__all__ = (
    "reserve_enqueue_sequences",
    "reserve_next_enqueue_sequence",
)


def reserve_enqueue_sequences(conn: sqlite3.Connection, count: int) -> list[int]:
    normalized_count = max(int(count), 0)
    if normalized_count <= 0:
        return []
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            UPDATE orchestrator_queue_sequence
               SET next_enqueue_seq = next_enqueue_seq + ?
             WHERE singleton = 1
         RETURNING next_enqueue_seq - ? AS first_enqueue_seq
            """,
            (normalized_count, normalized_count),
        ),
    )
    if row is None:
        raise sqlite3.IntegrityError("orchestrator_queue_sequence row is missing")
    first_value = coerce_required_int_from_sqlite_row(row, "first_enqueue_seq")
    return [first_value + index for index in range(normalized_count)]


def reserve_next_enqueue_sequence(conn: sqlite3.Connection) -> int:
    values = reserve_enqueue_sequences(conn, 1)
    if not values:
        raise sqlite3.IntegrityError("Failed to allocate orchestrator queue sequence")
    return values[0]
