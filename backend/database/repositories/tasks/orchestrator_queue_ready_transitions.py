"""SoAI - Durable queue ready transitions [backend/database/repositories/tasks/orchestrator_queue_ready_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
)
from database.repositories.tasks.orchestrator_queue_phases import QUEUE_PHASE_READY
from database.repositories.tasks.orchestrator_queue_task_predicates import (
    active_task_exists_clause,
)

__all__ = ("sync_move_orchestrator_queue_item_to_ready",)


def sync_move_orchestrator_queue_item_to_ready(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    enqueue_seq: int,
    available_at_ms: int,
    now_ms: int,
    allowed_source_phases: tuple[str, ...] | None = None,
) -> bool:
    if allowed_source_phases is not None and not allowed_source_phases:
        return False
    if allowed_source_phases is not None:
        placeholders = ", ".join("?" for _ in allowed_source_phases)
        return (
            conn.execute(
                f"""
                UPDATE orchestrator_queue_items
                   SET phase = ?,
                       enqueue_seq = ?,
                       available_at_ms = ?,
                       lease_owner = NULL,
                       lease_expires_at_ms = NULL,
                       updated_at_ms = ?
                 WHERE task_id = ?
                   AND phase IN ({placeholders})
                   {active_task_exists_clause()}
                """,
                (
                    QUEUE_PHASE_READY,
                    enqueue_seq,
                    available_at_ms,
                    now_ms,
                    task_id,
                    *allowed_source_phases,
                    *ACTIVE_TASK_STATUS_VALUES,
                ),
            ).rowcount
            > 0
        )
    return (
        conn.execute(
            f"""
            UPDATE orchestrator_queue_items
               SET phase = ?,
                   enqueue_seq = ?,
                   available_at_ms = ?,
                   lease_owner = NULL,
                   lease_expires_at_ms = NULL,
                   updated_at_ms = ?
             WHERE task_id = ?
               {active_task_exists_clause()}
            """,
            (
                QUEUE_PHASE_READY,
                enqueue_seq,
                available_at_ms,
                now_ms,
                task_id,
                *ACTIVE_TASK_STATUS_VALUES,
            ),
        ).rowcount
        > 0
    )
