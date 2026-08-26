"""SoAI - Durable database operation receipt maintenance [backend/database/operation_receipts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.durations import MILLISECONDS_PER_DAY

__all__ = (
    "DATABASE_OPERATION_RETENTION_MS",
    "DATABASE_RECEIPT_CLEANUP_BATCH_SIZE",
    "sync_apply_acknowledged_database_write_receipts",
    "sync_delete_expired_database_write_receipts",
    "sync_insert_database_write_receipt",
)

DATABASE_OPERATION_RETENTION_MS = 30 * MILLISECONDS_PER_DAY
DATABASE_RECEIPT_CLEANUP_BATCH_SIZE = 1000


def sync_insert_database_write_receipt(
    conn: sqlite3.Connection,
    *,
    operation_id: str,
    committed_at_ms: int,
) -> None:
    conn.execute(
        """
        INSERT INTO database_write_receipts (operation_id, committed_at_ms)
        VALUES (?, ?)
        """,
        (operation_id, committed_at_ms),
    )


def sync_apply_acknowledged_database_write_receipts(
    conn: sqlite3.Connection,
    *,
    operation_ids: tuple[str, ...],
    acknowledged_at_ms: int,
) -> int:
    updated = 0
    for operation_id in operation_ids:
        cursor = conn.execute(
            """
            UPDATE database_write_receipts
            SET acknowledged_at_ms = ?
            WHERE operation_id = ?
              AND acknowledged_at_ms IS NULL
            """,
            (acknowledged_at_ms, operation_id),
        )
        updated += cursor.rowcount
    return updated


def sync_delete_expired_database_write_receipts(
    conn: sqlite3.Connection,
    now_ms: int,
) -> int:
    cursor = conn.execute(
        """
        DELETE FROM database_write_receipts
        WHERE operation_id IN (
            SELECT operation_id
            FROM database_write_receipts
            WHERE committed_at_ms < ?
            ORDER BY committed_at_ms
            LIMIT ?
        )
        """,
        (
            now_ms - DATABASE_OPERATION_RETENTION_MS,
            DATABASE_RECEIPT_CLEANUP_BATCH_SIZE,
        ),
    )
    return cursor.rowcount
