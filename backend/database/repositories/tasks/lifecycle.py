"""SoAI - Database tasks lifecycle operations [backend/database/repositories/tasks/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    active_task_status_placeholders,
)
from core.timing.epoch import epoch_ms
from database.repositories.tasks.orchestrator_queue_phases import (
    sync_update_queue_phase_for_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_update_cancellation_requested_at_ms",
    "sync_update_cancellation_requested_at_ms_for_cancellation_id",
    "sync_update_orchestration_state",
)


def sync_update_orchestration_state(
    conn: sqlite3.Connection,
    task_id: str,
    orchestration_state: JSONDict | None,
) -> bool:
    state_json = (
        None
        if orchestration_state is None
        else serialize_json_compact_stable_strict(orchestration_state)
    )
    updated_at_ms = epoch_ms()
    cursor = conn.execute(
        f"""
        UPDATE unified_tasks
        SET orchestration_state = ?, updated_at_ms = ?
        WHERE task_id = ? AND status IN ({active_task_status_placeholders()})
        """,
        (state_json, updated_at_ms, task_id, *ACTIVE_TASK_STATUS_VALUES),
    )
    if cursor.rowcount > 0 and orchestration_state:
        routing_key = orchestration_state.get("routing_key")
        plugin_name = orchestration_state.get("plugin_name")
        dedup_hash = orchestration_state.get("dedup_hash")
        dedup_lead_task_id = orchestration_state.get("dedup_lead_task_id")
        normalized_routing_key = (
            routing_key if isinstance(routing_key, str) and routing_key else None
        )
        normalized_plugin_name = (
            plugin_name if isinstance(plugin_name, str) and plugin_name else None
        )
        normalized_dedup_hash = dedup_hash if isinstance(dedup_hash, str) and dedup_hash else None
        normalized_dedup_lead_task_id = (
            dedup_lead_task_id
            if isinstance(dedup_lead_task_id, str) and dedup_lead_task_id
            else None
        )
        conn.execute(
            """
            UPDATE orchestrator_queue_items
               SET routing_key = CASE
                       WHEN ? IS NULL THEN routing_key
                       ELSE ?
                   END,
                   plugin_name = ?,
                   dedup_hash = ?,
                   dedup_lead_task_id = ?,
                   updated_at_ms = ?
             WHERE task_id = ?
            """,
            (
                normalized_routing_key,
                normalized_routing_key,
                normalized_plugin_name,
                normalized_dedup_hash,
                normalized_dedup_lead_task_id,
                updated_at_ms,
                task_id,
            ),
        )
    return cursor.rowcount > 0


def sync_update_cancellation_requested_at_ms(
    conn: sqlite3.Connection,
    task_id: str,
    cancellation_requested_at_ms: int,
) -> bool:
    updated_at_ms = epoch_ms()
    cursor = conn.execute(
        f"""
        UPDATE unified_tasks
        SET cancellation_requested_at_ms = ?, updated_at_ms = ?
        WHERE task_id = ? AND status IN ({active_task_status_placeholders()})
        """,
        (cancellation_requested_at_ms, updated_at_ms, task_id, *ACTIVE_TASK_STATUS_VALUES),
    )
    if cursor.rowcount > 0:
        sync_update_queue_phase_for_status(conn, task_id, task_status="queued")
    return cursor.rowcount > 0


def sync_update_cancellation_requested_at_ms_for_cancellation_id(
    conn: sqlite3.Connection,
    cancellation_id: str,
    cancellation_requested_at_ms: int,
) -> int:
    updated_at_ms = epoch_ms()
    cursor = conn.execute(
        f"""
        UPDATE unified_tasks
        SET cancellation_requested_at_ms = ?,
            updated_at_ms = ?
        WHERE cancellation_id = ?
          AND cancellation_requested_at_ms IS NULL
          AND status IN ({active_task_status_placeholders()})
        """,
        (
            cancellation_requested_at_ms,
            updated_at_ms,
            cancellation_id,
            *ACTIVE_TASK_STATUS_VALUES,
        ),
    )
    return int(cursor.rowcount or 0)
