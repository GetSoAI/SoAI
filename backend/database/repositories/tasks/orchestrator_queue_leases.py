"""SoAI - Durable orchestrator queue leasing [backend/database/repositories/tasks/orchestrator_queue_leases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.task_requests import (
    DurableQueueClaim,
    durable_queue_claim_scheduling_key,
)
from core.orchestrator.request_priority import RequestPriority
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    active_task_status_placeholders,
)
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_all_as_dicts
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)
from database.repositories.tasks.orchestrator_queue_phases import (
    QUEUE_PHASE_LEASED,
    QUEUE_PHASE_PREFETCHED,
    QUEUE_PHASE_READY,
    QUEUE_PHASE_RUNNING,
)
from database.repositories.tasks.orchestrator_queue_ready_transitions import (
    sync_move_orchestrator_queue_item_to_ready,
)
from database.repositories.tasks.orchestrator_queue_sequence import (
    reserve_enqueue_sequences,
)
from database.repositories.tasks.orchestrator_queue_task_predicates import (
    active_task_exists_clause,
)

__all__ = (
    "sync_claim_orchestrator_queue_items",
    "sync_recover_expired_orchestrator_queue_items",
    "sync_release_orchestrator_queue_item_lease",
)


def sync_claim_orchestrator_queue_items(
    conn: sqlite3.Connection,
    now_ms: int,
    lease_owner: str,
    lease_ttl_ms: int,
    limit: int,
    request_priority: RequestPriority,
) -> list[DurableQueueClaim]:
    if limit <= 0:
        return []
    lease_expires_at_ms = int(now_ms) + max(0, int(lease_ttl_ms))
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"""
            WITH claimable AS (
                SELECT oq.task_id, oq.enqueue_seq, oq.priority_order_at_ms
                  FROM orchestrator_queue_items AS oq
                 JOIN unified_tasks AS ut ON ut.task_id = oq.task_id
                 WHERE oq.phase = ?
                   AND oq.available_at_ms <= ?
                   AND oq.request_priority = ?
                   AND ut.status IN ({active_task_status_placeholders()})
                 ORDER BY oq.priority_order_at_ms ASC, oq.enqueue_seq ASC
                 LIMIT ?
            )
            UPDATE orchestrator_queue_items
               SET phase = ?,
                   lease_owner = ?,
                   lease_expires_at_ms = ?,
                   attempt_count = attempt_count + 1,
                   updated_at_ms = ?
             WHERE task_id IN (SELECT task_id FROM claimable)
               AND phase = ?
               AND available_at_ms <= ?
               {active_task_exists_clause()}
         RETURNING task_id, enqueue_seq, priority_order_at_ms
            """,
            (
                QUEUE_PHASE_READY,
                now_ms,
                request_priority.value,
                *ACTIVE_TASK_STATUS_VALUES,
                limit,
                QUEUE_PHASE_LEASED,
                lease_owner,
                lease_expires_at_ms,
                now_ms,
                QUEUE_PHASE_READY,
                now_ms,
                *ACTIVE_TASK_STATUS_VALUES,
            ),
        ),
    )
    claimed_items = [
        DurableQueueClaim(
            priority_order_at_ms=coerce_required_int_from_sqlite_row(row, "priority_order_at_ms"),
            enqueue_seq=coerce_required_int_from_sqlite_row(row, "enqueue_seq"),
            task_id=coerce_required_nonempty_str_from_sqlite_row(row, "task_id"),
        )
        for row in rows
    ]
    claimed_items.sort(key=durable_queue_claim_scheduling_key)
    return claimed_items


def sync_recover_expired_orchestrator_queue_items(
    conn: sqlite3.Connection,
    now_ms: int,
) -> int:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"""
            SELECT oq.task_id
              FROM orchestrator_queue_items AS oq
              JOIN unified_tasks AS ut ON ut.task_id = oq.task_id
             WHERE oq.phase = ?
               AND oq.lease_expires_at_ms IS NOT NULL
               AND oq.lease_expires_at_ms <= ?
               AND ut.status IN ({active_task_status_placeholders()})
             ORDER BY oq.enqueue_seq ASC
            """,
            (QUEUE_PHASE_LEASED, now_ms, *ACTIVE_TASK_STATUS_VALUES),
        ),
    )
    task_ids = [coerce_required_nonempty_str_from_sqlite_row(row, "task_id") for row in rows]
    if not task_ids:
        return 0
    enqueue_values = reserve_enqueue_sequences(conn, len(task_ids))
    recovered = 0
    for task_id, enqueue_seq in zip(task_ids, enqueue_values, strict=True):
        updated = conn.execute(
            f"""
            UPDATE orchestrator_queue_items
               SET phase = ?,
                   enqueue_seq = ?,
                   lease_owner = NULL,
                   lease_expires_at_ms = NULL,
                   updated_at_ms = ?
             WHERE task_id = ?
               AND phase = ?
               AND lease_expires_at_ms IS NOT NULL
               AND lease_expires_at_ms <= ?
               {active_task_exists_clause()}
            """,
            (
                QUEUE_PHASE_READY,
                enqueue_seq,
                now_ms,
                task_id,
                QUEUE_PHASE_LEASED,
                now_ms,
                *ACTIVE_TASK_STATUS_VALUES,
            ),
        ).rowcount
        if updated > 0:
            recovered += 1
    return recovered


def sync_release_orchestrator_queue_item_lease(
    conn: sqlite3.Connection,
    task_id: str,
    available_at_ms: int,
) -> bool:
    now = epoch_ms()
    enqueue_seq = reserve_enqueue_sequences(conn, 1)[0]
    return sync_move_orchestrator_queue_item_to_ready(
        conn,
        task_id=task_id,
        enqueue_seq=enqueue_seq,
        available_at_ms=available_at_ms,
        now_ms=now,
        allowed_source_phases=(
            QUEUE_PHASE_LEASED,
            QUEUE_PHASE_RUNNING,
            QUEUE_PHASE_PREFETCHED,
        ),
    )
