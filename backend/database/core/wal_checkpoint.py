"""SoAI - SQLite WAL checkpoint operations [backend/database/core/wal_checkpoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

__all__ = (
    "WalCheckpointResult",
    "run_passive_wal_checkpoint",
    "run_truncate_wal_checkpoint",
)

PASSIVE_CHECKPOINT_SQL = "PRAGMA wal_checkpoint(PASSIVE);"
TRUNCATE_CHECKPOINT_SQL = "PRAGMA wal_checkpoint(TRUNCATE);"


@dataclass(frozen=True, slots=True)
class WalCheckpointResult:
    busy: bool
    wal_frames: int
    checkpointed_frames: int


def _run_wal_checkpoint(
    connection: sqlite3.Connection,
    statement: str,
) -> WalCheckpointResult:
    row = connection.execute(statement).fetchone()
    if row is None or len(row) != 3:
        raise sqlite3.DatabaseError("SQLite WAL checkpoint returned an invalid result.")
    try:
        busy_value = int(row[0])
        wal_frames = int(row[1])
        checkpointed_frames = int(row[2])
    except (TypeError, ValueError, OverflowError) as exception:
        raise sqlite3.DatabaseError(
            "SQLite WAL checkpoint returned an invalid result."
        ) from exception
    if busy_value not in (0, 1) or wal_frames < -1 or checkpointed_frames < -1:
        raise sqlite3.DatabaseError("SQLite WAL checkpoint returned an invalid result.")
    return WalCheckpointResult(
        busy=bool(busy_value),
        wal_frames=wal_frames,
        checkpointed_frames=checkpointed_frames,
    )


def run_passive_wal_checkpoint(connection: sqlite3.Connection) -> WalCheckpointResult:
    return _run_wal_checkpoint(connection, PASSIVE_CHECKPOINT_SQL)


def run_truncate_wal_checkpoint(connection: sqlite3.Connection) -> WalCheckpointResult:
    return _run_wal_checkpoint(connection, TRUNCATE_CHECKPOINT_SQL)
