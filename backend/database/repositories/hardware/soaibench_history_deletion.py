"""SoAI - Atomic owner-scoped local benchmark history deletion [backend/database/repositories/hardware/soaibench_history_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError

__all__ = ("sync_delete_soaibench_local_run",)


def sync_delete_soaibench_local_run(
    connection: sqlite3.Connection, run_id: str, user_id: int
) -> None:
    row = connection.execute(
        """SELECT status, EXISTS(
        SELECT 1 FROM hardware_gpu_soaibench_publications
        WHERE run_id=? AND created_by_user_id=?
        ) FROM hardware_gpu_soaibench_runs WHERE run_id=? AND created_by_user_id=?""",
        (run_id, user_id, run_id, user_id),
    ).fetchone()
    if row is None:
        raise ValidationError("SoAIBench run was not found.")
    status = str(row[0])
    if status in {"running", "indeterminate"}:
        raise StateError("Stop the active SoAIBench benchmark before deleting local history.")
    if int(row[1]) == 1:
        raise StateError("Prepared or published SoAIBench history cannot be deleted.")
    cursor = connection.execute(
        """DELETE FROM hardware_gpu_soaibench_runs
        WHERE run_id=? AND created_by_user_id=?
        AND status NOT IN ('running', 'indeterminate')
        AND NOT EXISTS (SELECT 1 FROM hardware_gpu_soaibench_publications
        WHERE run_id=? AND created_by_user_id=?)""",
        (run_id, user_id, run_id, user_id),
    )
    if cursor.rowcount != 1:
        raise StateError("SoAIBench history changed before deletion could complete.")
