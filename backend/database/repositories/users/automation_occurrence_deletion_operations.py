"""SoAI - Automation occurrence deletion operations [backend/database/repositories/users/automation_occurrence_deletion_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import NotFoundError, StateError, ValidationError
from core.types.json import JSONDict
from core.users.user_id import is_strict_user_id
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict, sync_fetch_one_scalar
from database.repositories.users.automation_abandoned_run_operations import (
    sync_list_abandoned_occurrence_owner_task_ids,
)
from database.repositories.users.automation_event_outbox import (
    sync_enqueue_automation_domain_event,
)

__all__ = (
    "should_notify_for_occurrence_deletion_result",
    "sync_delete_automation_occurrences",
)


def _extend_owner_task_ids(owner_task_ids: list[str], candidates: list[str]) -> None:
    for candidate in candidates:
        if candidate not in owner_task_ids:
            owner_task_ids.append(candidate)


def should_notify_for_occurrence_deletion_result(result: JSONDict) -> bool:
    tombstone_inserted_count = result.get("tombstone_inserted_count")
    deleted_run_count = result.get("deleted_run_count")
    return (
        isinstance(tombstone_inserted_count, int)
        and tombstone_inserted_count > 0
        or isinstance(deleted_run_count, int)
        and deleted_run_count > 0
    )


def sync_delete_automation_occurrences(
    conn: sqlite3.Connection,
    user_id: int,
    occurrences: list[tuple[str, int]],
    deleted_at_ms: int,
) -> JSONDict:
    if not is_strict_user_id(user_id):
        raise ValidationError("Automation deletion requires a valid user_id.")
    if not is_strict_int(deleted_at_ms) or deleted_at_ms <= 0:
        raise ValidationError("Automation deletion requires a valid deleted_at timestamp.")
    if not occurrences:
        raise ValidationError("Automation deletion requires at least one occurrence.")

    normalized: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for automation_id, scheduled_at_ms in occurrences:
        normalized_id = automation_id.strip() if isinstance(automation_id, str) else ""
        if not normalized_id:
            raise ValidationError("Automation occurrence automation_id is invalid.")
        if (
            isinstance(scheduled_at_ms, bool)
            or not isinstance(scheduled_at_ms, int)
            or scheduled_at_ms <= 0
        ):
            raise ValidationError("Automation occurrence scheduled_at_ms is invalid.")
        key = (normalized_id, scheduled_at_ms)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)

    tombstone_inserted_count = 0
    deleted_run_count = 0
    cancelled_run_ids: list[str] = []
    abandoned_owner_task_ids: list[str] = []
    updated_automation_ids: set[str] = set()
    for automation_id, scheduled_at_ms in normalized:
        automation_exists = sync_fetch_one_scalar(
            conn.execute(
                "SELECT 1 FROM automations WHERE id = ? AND user_id = ?",
                (automation_id, user_id),
            ),
        )
        if automation_exists is None:
            raise NotFoundError("Automation not found.")

        tombstone_cursor = conn.execute(
            """
            INSERT OR IGNORE INTO automation_occurrence_deletions (
                user_id,
                automation_id,
                scheduled_at_ms,
                deleted_at_ms
            ) VALUES (?, ?, ?, ?)
            """,
            (user_id, automation_id, scheduled_at_ms, deleted_at_ms),
        )
        inserted_tombstone = tombstone_cursor.rowcount == 1
        if inserted_tombstone:
            tombstone_inserted_count += 1
            updated_automation_ids.add(automation_id)

        run_row = sync_fetch_one_as_dict(
            conn.execute(
                """
                SELECT id, status, status_message
                FROM automation_runs
                WHERE automation_id = ? AND scheduled_at_ms = ? AND user_id = ?
                """,
                (automation_id, scheduled_at_ms, user_id),
            ),
        )
        if run_row is None:
            continue
        run_id = run_row.get("id")
        run_status = run_row.get("status")
        run_status_message = run_row.get("status_message")
        if not isinstance(run_id, str) or not run_id.strip():
            raise StateError("Automation run id is invalid.")
        if not isinstance(run_status, str) or not run_status.strip():
            raise StateError("Automation run status is invalid.")
        run_id = run_id.strip()
        run_status = run_status.strip()

        if run_status == "queued":
            updated = conn.execute(
                """
                UPDATE automation_runs
                SET status = 'abandoned', status_message = ?, finished_at_ms = ?
                WHERE id = ? AND user_id = ? AND status = 'queued'
                """,
                ("deleted", deleted_at_ms, run_id, user_id),
            ).rowcount
            if updated == 1:
                deleted_run_count += 1
                _extend_owner_task_ids(
                    abandoned_owner_task_ids,
                    sync_list_abandoned_occurrence_owner_task_ids(
                        conn,
                        automation_id=automation_id,
                        user_id=user_id,
                        scheduled_at_ms=scheduled_at_ms,
                        status_message="deleted",
                    ),
                )
                sync_enqueue_automation_domain_event(
                    conn,
                    event_type="AutomationRunUpdatedEvent",
                    created_at_ms=deleted_at_ms,
                    user_id=user_id,
                    automation_id=automation_id,
                    run_id=run_id,
                )
            continue
        if run_status == "abandoned" and run_status_message == "deleted":
            _extend_owner_task_ids(
                abandoned_owner_task_ids,
                sync_list_abandoned_occurrence_owner_task_ids(
                    conn,
                    automation_id=automation_id,
                    user_id=user_id,
                    scheduled_at_ms=scheduled_at_ms,
                    status_message="deleted",
                ),
            )
            continue
        if run_status == "running" and run_id not in cancelled_run_ids:
            cancelled_run_ids.append(run_id)

    for automation_id in sorted(updated_automation_ids):
        sync_enqueue_automation_domain_event(
            conn,
            event_type="AutomationUpdatedEvent",
            created_at_ms=deleted_at_ms,
            user_id=user_id,
            automation_id=automation_id,
        )

    return {
        "deleted_occurrence_count": len(normalized),
        "tombstone_inserted_count": tombstone_inserted_count,
        "deleted_run_count": deleted_run_count,
        "cancelled_run_ids": cancelled_run_ids,
        "abandoned_owner_task_ids": abandoned_owner_task_ids,
    }
