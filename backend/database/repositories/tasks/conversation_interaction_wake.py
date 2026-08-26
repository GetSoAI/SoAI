"""SoAI - Atomic terminal interaction input wake [backend/database/repositories/tasks/conversation_interaction_wake.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError

__all__ = (
    "sync_reconcile_terminal_interaction_input_wakes",
    "sync_wake_conversation_input_for_terminal_interaction",
)


def sync_wake_conversation_input_for_terminal_interaction(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    task_status: str,
    resolved_at_ms: int,
) -> bool:
    row = conn.execute(
        """
        SELECT input_id, suspension_generation
        FROM webui_conversation_inputs
        WHERE task_id = ? AND state = 'input_required'
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return False
    if not isinstance(row[0], str) or not isinstance(row[1], int) or row[1] <= 0:
        raise StateError("Terminal conversation interaction checkpoint is invalid.")
    updated = conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'pending', claim_owner = NULL, claim_server_boot_id = NULL,
            claimed_at_ms = NULL, running_at_ms = NULL, updated_at_ms = ?
        WHERE input_id = ? AND task_id = ? AND state = 'input_required'
          AND suspension_generation = ?
        """,
        (resolved_at_ms, row[0], task_id, row[1]),
    ).rowcount
    if updated != 1:
        raise StateError("Terminal conversation interaction wake lost its checkpoint.")
    route_state = "resolved" if task_status == "completed" else "cancelled"
    if task_status != "completed":
        conn.execute(
            """
            UPDATE task_interaction_secret_handoffs
            SET state = 'expired', secret_ciphertext = NULL, updated_at_ms = ?
            WHERE task_id = ? AND state IN ('resolution_staged', 'pending', 'claimed')
            """,
            (resolved_at_ms, task_id),
        )
    conn.execute(
        """
        UPDATE messaging_interaction_routes
        SET state = ?, resolved_at_ms = ?
        WHERE task_id = ? AND checkpoint_generation = ?
          AND state IN ('pending', 'resolving', 'expiring')
        """,
        (route_state, resolved_at_ms, task_id, row[1]),
    )
    return True


def sync_reconcile_terminal_interaction_input_wakes(
    conn: sqlite3.Connection,
    *,
    resolved_at_ms: int,
) -> int:
    rows = conn.execute(
        """
        SELECT input.task_id, task.status
        FROM webui_conversation_inputs AS input
        JOIN unified_tasks AS task ON task.task_id = input.task_id
        WHERE input.state = 'input_required'
          AND task.status IN ('completed', 'failed', 'cancelled')
        ORDER BY input.accepted_at_ms ASC, input.id ASC
        """,
    ).fetchall()
    reconciled = 0
    for task_id, task_status in rows:
        if not isinstance(task_id, str) or not isinstance(task_status, str):
            raise StateError("Terminal conversation interaction task identity is invalid.")
        if sync_wake_conversation_input_for_terminal_interaction(
            conn,
            task_id=task_id,
            task_status=task_status,
            resolved_at_ms=resolved_at_ms,
        ):
            reconciled += 1
    return reconciled
