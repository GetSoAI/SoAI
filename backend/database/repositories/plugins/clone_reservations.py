"""SoAI - Atomic plugin clone target reservations [backend/database/repositories/plugins/clone_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

__all__ = (
    "sync_get_clone_target_owner",
    "sync_list_reserved_clone_targets",
)


def sync_get_clone_target_owner(
    connection: sqlite3.Connection,
    target_plugin_name: str,
) -> str | None:
    row = connection.execute(
        "SELECT task_id FROM plugin_clone_target_reservations WHERE target_plugin_name = ?",
        (target_plugin_name,),
    ).fetchone()
    return row["task_id"] if row is not None else None


def sync_list_reserved_clone_targets(
    connection: sqlite3.Connection,
) -> tuple[str, ...]:
    rows = connection.execute("""SELECT target_plugin_name
        FROM plugin_clone_target_reservations
        UNION
        SELECT target_plugin_name FROM plugin_clone_transactions
        WHERE phase = 'recovery_required'
        ORDER BY target_plugin_name""").fetchall()
    return tuple(row["target_plugin_name"] for row in rows)
