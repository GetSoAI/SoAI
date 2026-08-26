"""SoAI - Durable orchestrator queue requeue [backend/database/repositories/tasks/orchestrator_queue_requeue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    active_task_status_placeholders,
)
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.tasks.orchestrator_queue_insertion import (
    insert_orchestrator_queue_item,
)
from database.repositories.tasks.orchestrator_queue_phases import (
    NON_TERMINAL_QUEUE_PHASES,
    QUEUE_PHASE_READY,
)
from database.repositories.tasks.orchestrator_queue_ready_transitions import (
    sync_move_orchestrator_queue_item_to_ready,
)
from database.repositories.tasks.orchestrator_queue_requeue_state import (
    OrchestratorQueueRequeueState,
    resolve_orchestrator_queue_requeue_state,
)
from database.repositories.tasks.orchestrator_queue_sequence import (
    reserve_next_enqueue_sequence,
)

__all__ = ("sync_requeue_orchestrated_inference_task",)

OPERATION = "database.tasks.requeue_orchestrated_inference_task"


def _has_requeueable_queue_item(conn: sqlite3.Connection, task_id: str) -> bool:
    placeholders = ", ".join(("?",) * len(NON_TERMINAL_QUEUE_PHASES))
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT 1 AS has_queue_item
              FROM orchestrator_queue_items
             WHERE task_id = ?
               AND phase IN ({placeholders})
             LIMIT 1
            """,
            (task_id, *NON_TERMINAL_QUEUE_PHASES),
        ),
    )
    return row is not None


def sync_requeue_orchestrated_inference_task(
    conn: sqlite3.Connection,
    task_id: str,
    available_at_ms: int,
    status_message: str | None,
) -> bool:
    now = epoch_ms()
    has_queue_item = _has_requeueable_queue_item(conn, task_id)
    insert_state: OrchestratorQueueRequeueState | None = (
        None if has_queue_item else resolve_orchestrator_queue_requeue_state(conn, task_id)
    )
    task_updated = (
        conn.execute(
            f"""
            UPDATE unified_tasks
               SET status = 'queued',
                   status_message = COALESCE(?, status_message),
                   updated_at_ms = ?
             WHERE task_id = ?
               AND orchestration_state IS NOT NULL
               AND status IN ({active_task_status_placeholders()})
               AND cancellation_requested_at_ms IS NULL
            """,
            (status_message, now, task_id, *ACTIVE_TASK_STATUS_VALUES),
        ).rowcount
        > 0
    )
    if not task_updated:
        return False
    enqueue_seq = reserve_next_enqueue_sequence(conn)
    if has_queue_item:
        return sync_move_orchestrator_queue_item_to_ready(
            conn,
            task_id=task_id,
            enqueue_seq=enqueue_seq,
            available_at_ms=available_at_ms,
            now_ms=now,
            allowed_source_phases=NON_TERMINAL_QUEUE_PHASES,
        )
    if insert_state is None:
        raise StateError(
            "Cannot requeue orchestrated task without queue insert state.",
            operation=OPERATION,
            details={"task_id": task_id},
        )
    try:
        insert_orchestrator_queue_item(
            conn,
            task_id=task_id,
            enqueue_seq=enqueue_seq,
            phase=QUEUE_PHASE_READY,
            routing_key=insert_state.routing_key,
            plugin_name=insert_state.plugin_name,
            available_at_ms=available_at_ms,
            lease_owner=None,
            lease_expires_at_ms=None,
            attempt_count=0,
            dedup_hash=insert_state.dedup_hash,
            dedup_lead_task_id=insert_state.dedup_lead_task_id,
            request_source=insert_state.request_source,
            delivery_mode=insert_state.delivery_mode,
            request_priority=insert_state.request_priority,
            priority_order_at_ms=insert_state.priority_order_at_ms,
            now=now,
        )
        return True
    except sqlite3.IntegrityError:
        return sync_move_orchestrator_queue_item_to_ready(
            conn,
            task_id=task_id,
            enqueue_seq=enqueue_seq,
            available_at_ms=available_at_ms,
            now_ms=now,
        )
