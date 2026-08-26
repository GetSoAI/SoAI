"""SoAI - Durable orchestrator queue row insertion [backend/database/repositories/tasks/orchestrator_queue_insertion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.orchestrator.request_priority import RequestPriority

__all__ = ("insert_orchestrator_queue_item",)


def insert_orchestrator_queue_item(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    enqueue_seq: int,
    phase: str,
    routing_key: str,
    plugin_name: str | None,
    available_at_ms: int,
    lease_owner: str | None,
    lease_expires_at_ms: int | None,
    attempt_count: int,
    dedup_hash: str | None,
    dedup_lead_task_id: str | None,
    request_source: str,
    delivery_mode: str,
    request_priority: RequestPriority,
    priority_order_at_ms: int,
    now: int,
) -> None:
    conn.execute(
        """
        INSERT INTO orchestrator_queue_items (
            task_id,
            enqueue_seq,
            phase,
            routing_key,
            plugin_name,
            available_at_ms,
            lease_owner,
            lease_expires_at_ms,
            attempt_count,
            dedup_hash,
            dedup_lead_task_id,
            request_source,
            delivery_mode,
            request_priority,
            priority_order_at_ms,
            created_at_ms,
            updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            enqueue_seq,
            phase,
            routing_key,
            plugin_name,
            available_at_ms,
            lease_owner,
            lease_expires_at_ms,
            attempt_count,
            dedup_hash,
            dedup_lead_task_id,
            request_source,
            delivery_mode,
            request_priority.value,
            priority_order_at_ms,
            now,
            now,
        ),
    )
