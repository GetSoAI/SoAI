"""SoAI - Durable orchestrator queue phase constants and transitions [backend/database/repositories/tasks/orchestrator_queue_phases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.tasks.enums import TaskStatus
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    RUNNING_TASK_STATUS_VALUES,
)
from core.timing.epoch import epoch_ms
from database.repositories.tasks.orchestrator_queue_task_predicates import (
    active_task_exists_clause,
)

__all__ = (
    "NON_TERMINAL_QUEUE_PHASES",
    "QUEUE_PHASE_LEASED",
    "QUEUE_PHASE_PREFETCHED",
    "QUEUE_PHASE_READY",
    "sync_finalize_orchestrator_queue_item",
    "sync_mark_orchestrator_queue_item_prefetched_if_leased",
    "sync_mark_orchestrator_queue_item_running_if_leased",
    "sync_update_queue_phase_for_status",
)

QUEUE_PHASE_READY = "ready"
QUEUE_PHASE_LEASED = "leased"
QUEUE_PHASE_PREFETCHED = "prefetched"
QUEUE_PHASE_RUNNING = "running"
QUEUE_PHASE_DEDUP_WAITING = "dedup_waiting"
QUEUE_PHASE_COMPLETED = "completed"
QUEUE_PHASE_FAILED = "failed"
QUEUE_PHASE_CANCELLED = "cancelled"
NON_TERMINAL_QUEUE_PHASES = (
    QUEUE_PHASE_READY,
    QUEUE_PHASE_LEASED,
    QUEUE_PHASE_PREFETCHED,
    QUEUE_PHASE_RUNNING,
    QUEUE_PHASE_DEDUP_WAITING,
)


def resolve_terminal_queue_phase(status: str) -> str | None:
    if status == TaskStatus.COMPLETED.value:
        return QUEUE_PHASE_COMPLETED
    if status == TaskStatus.FAILED.value:
        return QUEUE_PHASE_FAILED
    if status == TaskStatus.CANCELLED.value:
        return QUEUE_PHASE_CANCELLED
    return None


def resolve_queue_phase_transition(task_status: str) -> tuple[str, tuple[str, ...]] | None:
    if task_status == TaskStatus.AWAITING_SCHEDULER.value:
        return (
            QUEUE_PHASE_RUNNING,
            (
                QUEUE_PHASE_READY,
                QUEUE_PHASE_LEASED,
                QUEUE_PHASE_PREFETCHED,
                QUEUE_PHASE_RUNNING,
            ),
        )
    if task_status == TaskStatus.QUEUED.value:
        return (
            QUEUE_PHASE_READY,
            (
                QUEUE_PHASE_READY,
                QUEUE_PHASE_LEASED,
                QUEUE_PHASE_PREFETCHED,
                QUEUE_PHASE_RUNNING,
                QUEUE_PHASE_DEDUP_WAITING,
            ),
        )
    if task_status == TaskStatus.DEDUPED.value:
        return (
            QUEUE_PHASE_DEDUP_WAITING,
            (
                QUEUE_PHASE_READY,
                QUEUE_PHASE_LEASED,
                QUEUE_PHASE_PREFETCHED,
                QUEUE_PHASE_RUNNING,
            ),
        )
    if task_status in RUNNING_TASK_STATUS_VALUES:
        return (
            QUEUE_PHASE_RUNNING,
            (
                QUEUE_PHASE_READY,
                QUEUE_PHASE_LEASED,
                QUEUE_PHASE_PREFETCHED,
            ),
        )
    return None


def sync_update_queue_phase_for_status(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    task_status: str,
) -> None:
    transition = resolve_queue_phase_transition(task_status)
    if transition is None:
        return
    target_phase, source_phases = transition
    source_phase_placeholders = ", ".join(("?",) * len(source_phases))
    now = epoch_ms()
    conn.execute(
        f"""
        UPDATE orchestrator_queue_items
           SET phase = ?,
               lease_owner = NULL,
               lease_expires_at_ms = NULL,
               updated_at_ms = ?
         WHERE task_id = ?
           AND phase IN ({source_phase_placeholders})
        """,
        (
            target_phase,
            now,
            task_id,
            *source_phases,
        ),
    )


def sync_finalize_orchestrator_queue_item(
    conn: sqlite3.Connection,
    task_id: str,
    status: str,
) -> None:
    phase = resolve_terminal_queue_phase(status)
    if phase is None:
        return
    now = epoch_ms()
    conn.execute(
        """
        UPDATE orchestrator_queue_items
           SET phase = ?,
               lease_owner = NULL,
               lease_expires_at_ms = NULL,
               updated_at_ms = ?
         WHERE task_id = ?
        """,
        (phase, now, task_id),
    )


def sync_mark_orchestrator_queue_item_running_if_leased(
    conn: sqlite3.Connection,
    task_id: str,
    lease_owner: str,
) -> bool:
    now = epoch_ms()
    return (
        conn.execute(
            f"""
            UPDATE orchestrator_queue_items
               SET phase = ?,
                   lease_owner = NULL,
                   lease_expires_at_ms = NULL,
                   updated_at_ms = ?
             WHERE task_id = ?
               AND phase = ?
               AND lease_owner = ?
               {active_task_exists_clause()}
            """,
            (
                QUEUE_PHASE_RUNNING,
                now,
                task_id,
                QUEUE_PHASE_LEASED,
                lease_owner,
                *ACTIVE_TASK_STATUS_VALUES,
            ),
        ).rowcount
        > 0
    )


def sync_mark_orchestrator_queue_item_prefetched_if_leased(
    conn: sqlite3.Connection,
    task_id: str,
    lease_owner: str,
) -> bool:
    now = epoch_ms()
    return (
        conn.execute(
            f"""
            UPDATE orchestrator_queue_items
               SET phase = ?,
                   lease_owner = NULL,
                   lease_expires_at_ms = NULL,
                   updated_at_ms = ?
             WHERE task_id = ?
               AND phase = ?
               AND lease_owner = ?
               {active_task_exists_clause()}
            """,
            (
                QUEUE_PHASE_PREFETCHED,
                now,
                task_id,
                QUEUE_PHASE_LEASED,
                lease_owner,
                *ACTIVE_TASK_STATUS_VALUES,
            ),
        ).rowcount
        > 0
    )
