"""SoAI - Authoritative plugin state outbox claim and query operations [backend/database/repositories/plugins/authoritative_state_outbox_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "sync_claim_authoritative_state_events_for_shutdown",
    "sync_claim_pending_authoritative_state_events",
    "sync_count_unpublished_authoritative_state_events",
)


def sync_claim_pending_authoritative_state_events(
    conn: sqlite3.Connection,
    now_ms: int,
    limit: int,
    processing_timeout_ms: int,
) -> list[SQLiteRowDict]:
    batch_limit = max(int(limit) or 1, 1)
    timeout_ms = max(int(processing_timeout_ms) or 1, 1)
    current_time_ms = int(now_ms)
    expired_processing_before = current_time_ms - timeout_ms
    cursor = conn.execute(
        """
        SELECT id, event_id, plugin_name, event_type, payload_json, attempts, status
        FROM plugin_authoritative_state_outbox
        WHERE
            (
                status = 'pending'
                AND next_attempt_at_ms <= ?
            )
            OR (
                status = 'processing'
                AND processing_started_at_ms IS NOT NULL
                AND processing_started_at_ms <= ?
            )
        ORDER BY id
        LIMIT ?
        """,
        (current_time_ms, expired_processing_before, batch_limit),
    )
    claimed_rows = sync_fetch_all_as_dicts(cursor)
    if not claimed_rows:
        return []
    row_ids: list[int] = []
    for row in claimed_rows:
        outbox_id = row.get("id")
        if not isinstance(outbox_id, int):
            raise StateError(
                "Authoritative plugin state outbox contained an invalid row id.",
                operation="database.plugins.authoritative_state_outbox.claim",
            )
        row_ids.append(int(outbox_id))
    placeholders = ", ".join("?" for _ in row_ids)
    conn.execute(
        f"""
        UPDATE plugin_authoritative_state_outbox
        SET status = 'processing', processing_started_at_ms = ?
        WHERE id IN ({placeholders})
        """,
        (current_time_ms, *row_ids),
    )
    return claimed_rows


def sync_claim_authoritative_state_events_for_shutdown(
    conn: sqlite3.Connection,
    now_ms: int,
    limit: int,
) -> list[SQLiteRowDict]:
    batch_limit = max(int(limit) or 1, 1)
    current_time_ms = int(now_ms)
    cursor = conn.execute(
        """
        SELECT id, event_id, plugin_name, event_type, payload_json, attempts, status
        FROM plugin_authoritative_state_outbox
        WHERE status IN ('pending', 'processing')
        ORDER BY id
        LIMIT ?
        """,
        (batch_limit,),
    )
    claimed_rows = sync_fetch_all_as_dicts(cursor)
    if not claimed_rows:
        return []
    row_ids: list[int] = []
    for row in claimed_rows:
        outbox_id = row.get("id")
        if not isinstance(outbox_id, int):
            raise StateError(
                "Authoritative plugin state outbox contained an invalid row id.",
                operation="database.plugins.authoritative_state_outbox.claim_shutdown",
            )
        row_ids.append(int(outbox_id))
    placeholders = ", ".join("?" for _ in row_ids)
    conn.execute(
        f"""
        UPDATE plugin_authoritative_state_outbox
        SET status = 'processing', processing_started_at_ms = ?
        WHERE id IN ({placeholders})
        """,
        (current_time_ms, *row_ids),
    )
    return claimed_rows


def sync_count_unpublished_authoritative_state_events(conn: sqlite3.Connection) -> int:
    row = sync_fetch_one_as_dict(conn.execute("""
            SELECT COUNT(*) AS pending_count
            FROM plugin_authoritative_state_outbox
            WHERE status IN ('pending', 'processing')
            """))
    if row is None:
        return 0
    return coerce_required_int_from_sqlite_row(row, "pending_count")
