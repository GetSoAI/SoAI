"""SoAI - Durable orchestrator queue task acceptance operations [backend/database/repositories/tasks/orchestrator_queue_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.task_requests import CreateDurableInferenceTaskRequest
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    ServiceUnavailableError,
    TaskConcurrencyLimitError,
)
from core.hardware.disk_usage import read_disk_usage_with_parent_fallback
from core.tasks.errors import TaskIDCollisionError
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    active_task_status_placeholders,
)
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import (
    coerce_optional_str_from_sqlite_row,
    coerce_required_int_from_sqlite_row,
)
from database.repositories.tasks.durable_acceptance_policy import (
    DurableAcceptancePolicy,
)
from database.repositories.tasks.orchestrator_queue_insertion import (
    insert_orchestrator_queue_item,
)
from database.repositories.tasks.orchestrator_queue_phases import (
    NON_TERMINAL_QUEUE_PHASES,
)
from database.repositories.tasks.orchestrator_queue_sequence import (
    reserve_next_enqueue_sequence,
)

__all__ = ("sync_accept_durable_inference_task",)


def _insert_unified_task_for_durable_accept(
    conn: sqlite3.Connection,
    request: CreateDurableInferenceTaskRequest,
) -> None:
    task_request = request.task
    if task_request.max_concurrent is not None:
        row = sync_fetch_one_as_dict(
            conn.execute(
                f"""SELECT COUNT(*) AS count FROM unified_tasks
                   WHERE owner_type = ? AND owner_id = ?
                   AND status IN ({active_task_status_placeholders()})
                   AND cancellation_requested_at_ms IS NULL""",
                (
                    task_request.owner_type,
                    task_request.owner_id,
                    *ACTIVE_TASK_STATUS_VALUES,
                ),
            ),
        )
        active_count = coerce_required_int_from_sqlite_row(row, "count") if row else 0
        if active_count >= task_request.max_concurrent:
            raise TaskConcurrencyLimitError(
                task_request.owner_type,
                task_request.owner_id,
                task_request.max_concurrent,
            )
    now = epoch_ms()
    progress_current = 0 if task_request.progress_total is not None else None
    conn.execute(
        """INSERT INTO unified_tasks (
            task_id, task_type, status, user_id, owner_id, owner_type,
            cancellation_id, created_at_ms, updated_at_ms, ttl_ms, poll_interval_ms,
            progress_current, progress_total, status_message, metadata, orchestration_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task_request.task_id,
            task_request.task_type,
            task_request.status,
            task_request.user_id,
            task_request.owner_id,
            task_request.owner_type,
            task_request.cancellation_id,
            now,
            now,
            task_request.ttl_ms,
            task_request.poll_interval_ms,
            progress_current,
            task_request.progress_total,
            task_request.status_message,
            task_request.metadata,
            task_request.orchestration_state,
        ),
    )


def sync_accept_durable_inference_task(
    conn: sqlite3.Connection,
    request: CreateDurableInferenceTaskRequest,
    policy: DurableAcceptancePolicy,
) -> int:
    queue_item = request.queue_item
    _enforce_durable_acceptance_policy(conn, policy)
    try:
        _insert_unified_task_for_durable_accept(conn, request)
    except sqlite3.IntegrityError as exception:
        exc_str = str(exception)
        if "UNIQUE constraint failed" in exc_str or "PRIMARY KEY constraint" in exc_str:
            existing_row = sync_fetch_one_as_dict(
                conn.execute(
                    "SELECT status FROM unified_tasks WHERE task_id = ?",
                    (request.task.task_id,),
                ),
            )
            existing_status = (
                coerce_optional_str_from_sqlite_row(existing_row, "status")
                if existing_row is not None
                else None
            ) or "unknown"
            raise TaskIDCollisionError(request.task.task_id, existing_status) from exception
        raise
    enqueue_seq = reserve_next_enqueue_sequence(conn)
    now = epoch_ms()
    insert_orchestrator_queue_item(
        conn,
        task_id=queue_item.task_id,
        enqueue_seq=enqueue_seq,
        phase=queue_item.phase,
        routing_key=queue_item.routing_key,
        plugin_name=queue_item.plugin_name,
        available_at_ms=queue_item.available_at_ms,
        lease_owner=queue_item.lease_owner,
        lease_expires_at_ms=queue_item.lease_expires_at_ms,
        attempt_count=queue_item.attempt_count,
        dedup_hash=queue_item.dedup_hash,
        dedup_lead_task_id=queue_item.dedup_lead_task_id,
        request_source=queue_item.request_source,
        delivery_mode=queue_item.delivery_mode,
        request_priority=queue_item.request_priority,
        priority_order_at_ms=queue_item.priority_order_at_ms,
        now=now,
    )
    return enqueue_seq


def _enforce_durable_acceptance_policy(
    conn: sqlite3.Connection,
    policy: DurableAcceptancePolicy,
) -> None:
    _enforce_durable_queue_hard_limit(conn, policy.durable_queue_hard_limit_tasks)
    _enforce_min_free_disk_bytes(
        filesystem_path=policy.filesystem_path,
        min_free_disk_bytes=policy.min_free_disk_bytes_for_accept,
    )


def _enforce_durable_queue_hard_limit(conn: sqlite3.Connection, hard_limit_tasks: int) -> None:
    if hard_limit_tasks <= 0:
        return
    queue_phase_placeholders = ", ".join("?" for _ in NON_TERMINAL_QUEUE_PHASES)
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT COUNT(*) AS count
              FROM orchestrator_queue_items AS oq
              JOIN unified_tasks AS ut ON ut.task_id = oq.task_id
             WHERE oq.phase IN ({queue_phase_placeholders})
               AND ut.status IN ({active_task_status_placeholders()})
               AND ut.cancellation_requested_at_ms IS NULL
            """,
            (*NON_TERMINAL_QUEUE_PHASES, *ACTIVE_TASK_STATUS_VALUES),
        ),
    )
    queue_depth = coerce_required_int_from_sqlite_row(row, "count") if row else 0
    if queue_depth >= hard_limit_tasks:
        raise ServiceUnavailableError(
            f"Durable inference queue hard limit reached ({hard_limit_tasks} tasks).",
            details={"queue_depth": queue_depth, "hard_limit_tasks": hard_limit_tasks},
        )


def _enforce_min_free_disk_bytes(
    *,
    filesystem_path: str,
    min_free_disk_bytes: int,
) -> None:
    if min_free_disk_bytes <= 0:
        return
    disk_usage = read_disk_usage_with_parent_fallback(filesystem_path)
    free_bytes = disk_usage.free_bytes
    if free_bytes < min_free_disk_bytes:
        raise InsufficientDiskSpaceError(
            "Durable inference acceptance requires more free disk space.",
            details={
                "disk_usage_path": disk_usage.disk_usage_path,
                "filesystem_path": filesystem_path,
                "free_bytes": free_bytes,
                "required_min_free_bytes": min_free_disk_bytes,
            },
        )
