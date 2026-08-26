"""SoAI - Committed clone evidence and integrity operations [backend/database/repositories/plugins/clone_committed_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.clone_requests import CloneTransactionRecord
from database.core.savepoints import SQLiteSavepoint

__all__ = (
    "sync_get_committed_clone_for_target",
    "sync_list_committed_clone_transactions",
    "sync_mark_committed_clone_integrity_failure",
)


def _record(row: sqlite3.Row) -> CloneTransactionRecord:
    return CloneTransactionRecord(
        task_id=row["task_id"],
        source_plugin_name=row["source_plugin_name"],
        target_plugin_name=row["target_plugin_name"],
        clone_models=bool(row["clone_models"]),
        phase=row["phase"],
        committed=bool(row["committed"]),
    )


def sync_list_committed_clone_transactions(
    connection: sqlite3.Connection,
) -> tuple[CloneTransactionRecord, ...]:
    rows = connection.execute("""SELECT task_id, source_plugin_name, target_plugin_name,
        clone_models, phase, committed
        FROM plugin_clone_transactions
        WHERE phase = 'committed' AND committed = 1
        ORDER BY created_at_ms, task_id""").fetchall()
    return tuple(_record(row) for row in rows)


def sync_get_committed_clone_for_target(
    connection: sqlite3.Connection,
    target_plugin_name: str,
) -> CloneTransactionRecord | None:
    row = connection.execute(
        """SELECT task_id, source_plugin_name, target_plugin_name, clone_models, phase, committed
        FROM plugin_clone_transactions
        WHERE target_plugin_name = ? AND committed = 1
        ORDER BY created_at_ms DESC, task_id DESC LIMIT 1""",
        (target_plugin_name,),
    ).fetchone()
    return _record(row) if row is not None else None


def sync_mark_committed_clone_integrity_failure(
    connection: sqlite3.Connection,
    task_id: str,
    target_plugin_name: str,
    recovery_error: str,
) -> bool:
    with SQLiteSavepoint(connection, "clone_integrity_failure") as savepoint:
        updated = connection.execute(
            """UPDATE plugin_clone_transactions
            SET phase = 'recovery_required', recovery_error = ?
            WHERE task_id = ? AND target_plugin_name = ?
                AND phase = 'committed' AND committed = 1""",
            (recovery_error, task_id, target_plugin_name),
        ).rowcount
        if updated != 1:
            savepoint.rollback()
            return False
        connection.execute(
            """UPDATE plugins_catalog SET state = 'QUARANTINED'
            WHERE plugin_name = ? AND state != 'DELETING'""",
            (target_plugin_name,),
        )
    return True
