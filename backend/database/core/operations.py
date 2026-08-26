"""SoAI - Database sync maintenance operations [backend/database/core/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.durations import hours_to_ms
from core.timing.epoch import epoch_ms
from database.core.data_conversions import (
    SQLITE_BATCH_SIZE,
    resolve_delete_statement,
    resolve_prune_statement,
)

__all__ = (
    "sync_delete_by_ids",
    "sync_prune_by_timestamp",
)


def sync_prune_by_timestamp(
    conn: sqlite3.Connection,
    tables: tuple[str, ...],
    retention_hours: int,
) -> None:
    cutoff = epoch_ms() - hours_to_ms(retention_hours)
    for table in tables:
        prune_statement = resolve_prune_statement(table)
        conn.execute(prune_statement, (cutoff,))


def sync_delete_by_ids(
    conn: sqlite3.Connection,
    table: str,
    id_column: str,
    ids: list[str],
) -> int:
    if not ids:
        return 0
    delete_statement = resolve_delete_statement(table, id_column)
    total_deleted = 0
    for start_index in range(0, len(ids), SQLITE_BATCH_SIZE):
        batch = ids[start_index : start_index + SQLITE_BATCH_SIZE]
        batch_parameters = [(identifier_value,) for identifier_value in batch]
        before_total_changes = conn.total_changes
        conn.executemany(delete_statement, batch_parameters)
        total_deleted += conn.total_changes - before_total_changes
    return total_deleted
