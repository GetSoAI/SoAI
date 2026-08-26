"""SoAI - Quota reservation reconciliation for API key usage windows [backend/database/repositories/users/api_key_quota_usage_windows/reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from database.core.query_execution import sync_fetch_changes_count
from database.repositories.users.api_key_quota_usage_windows.window_support import (
    sync_try_mark_reservation_finalized,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_reconcile_expired_quota_reservations",)


def sync_reconcile_expired_quota_reservations(
    conn: sqlite3.Connection,
    now_ts: int,
    batch_limit: int,
) -> JSONDict:
    require_unix_epoch_ms(now_ts, error_message="now_ts must be an epoch-millisecond integer.")
    limit = int(batch_limit)
    if limit <= 0:
        raise ValidationError("batch_limit must be > 0.")
    cursor = conn.execute(
        """
        SELECT reservation_id, key_id, MAX(estimate_units) AS estimate_units
        FROM openai_api_key_quota_reservations
        WHERE status = 'reserved' AND expires_at_ms <= ?
        GROUP BY reservation_id, key_id
        ORDER BY expires_at_ms ASC
        LIMIT ?
        """,
        (int(now_ts), int(limit)),
    )
    rows = cursor.fetchall()
    released_reservations = 0
    released_rows = 0
    for reservation_id, key_id, estimate_units in rows:
        reservation_id_value = str(reservation_id or "").strip()
        key_id_value = str(key_id or "").strip()
        if not reservation_id_value or not key_id_value:
            continue
        estimate = (
            int(estimate_units) if isinstance(estimate_units, int) and estimate_units > 0 else 0
        )
        windows_cursor = conn.execute(
            """
            SELECT window_name
            FROM openai_api_key_quota_reservations
            WHERE reservation_id = ? AND key_id = ? AND status = 'reserved'
            """,
            (reservation_id_value, key_id_value),
        )
        window_rows = windows_cursor.fetchall()
        windows = [str(row[0]) for row in window_rows if row and isinstance(row[0], str)]
        if not windows:
            conn.execute(
                """
                UPDATE openai_api_key_quota_reservations
                SET status = 'expired', finalized_at_ms = ?, charged_units = 0, released_units = 0
                WHERE reservation_id = ? AND key_id = ? AND status = 'reserved'
                """,
                (int(now_ts), reservation_id_value, key_id_value),
            )
            released_rows += sync_fetch_changes_count(conn)
            continue
        finalized = sync_try_mark_reservation_finalized(
            conn,
            reservation_id=reservation_id_value,
            key_id=key_id_value,
            finalized_at_ms=int(now_ts),
            charged_units=0,
            released_units=int(estimate),
        )
        if not finalized:
            continue
        released_reservations += 1
        for window_name in windows:
            conn.execute(
                """
                UPDATE openai_api_key_quota_usage_windows
                SET reserved_units = MAX(0, reserved_units - ?),
                    updated_at_ms = ?
                WHERE key_id = ? AND window_name = ?
                """,
                (int(estimate), int(now_ts), key_id_value, window_name),
            )
        conn.execute(
            """
            UPDATE openai_api_key_quota_reservations
            SET status = 'expired',
                finalized_at_ms = ?,
                charged_units = 0,
                released_units = ?
            WHERE reservation_id = ? AND key_id = ? AND status = 'reserved'
            """,
            (int(now_ts), int(estimate), reservation_id_value, key_id_value),
        )
        released_rows += sync_fetch_changes_count(conn)
    return {
        "released_reservations": int(released_reservations),
        "released_rows": int(released_rows),
    }
