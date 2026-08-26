"""SoAI - Messaging delivery lifecycle fencing [backend/database/repositories/users/messaging_delivery_fencing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from database.repositories.users.messaging_delivery_state_transitions import (
    sync_terminalize_messaging_delivery,
)

__all__ = ("sync_fence_messaging_deliveries",)


def sync_fence_messaging_deliveries(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    failure_code: str,
    now_ms: int,
    sender_id: str | None = None,
) -> int:
    if sender_id is None:
        rows = conn.execute(
            """
            SELECT delivery_id, state,
                   (
                       SELECT ordinal FROM messaging_delivery_chunks AS chunk
                       WHERE chunk.delivery_id = messaging_deliveries.delivery_id
                         AND chunk.state = 'sending'
                         AND chunk.request_started_at_ms IS NOT NULL
                       ORDER BY ordinal LIMIT 1
                   )
            FROM messaging_deliveries
            WHERE account_id = ? AND user_id = ? AND state IN ('pending', 'sending')
            """,
            (account_id, user_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT delivery_id, state,
                   (
                       SELECT ordinal FROM messaging_delivery_chunks AS chunk
                       WHERE chunk.delivery_id = messaging_deliveries.delivery_id
                         AND chunk.state = 'sending'
                         AND chunk.request_started_at_ms IS NOT NULL
                       ORDER BY ordinal LIMIT 1
                   )
            FROM messaging_deliveries
            WHERE account_id = ? AND user_id = ? AND originating_sender_id = ?
              AND state IN ('pending', 'sending')
            """,
            (account_id, user_id, sender_id),
        ).fetchall()
    for delivery_id, state, unknown_ordinal in rows:
        ambiguous = state == "sending" and unknown_ordinal is not None
        normalized_unknown_ordinal: int | None = None
        if ambiguous:
            if isinstance(unknown_ordinal, bool) or not isinstance(unknown_ordinal, int):
                raise StateError("Messaging delivery unknown chunk ordinal is invalid.")
            normalized_unknown_ordinal = unknown_ordinal
        terminal_state = "delivery_unknown" if ambiguous else "skipped"
        terminal_code = f"{failure_code}_during_send" if ambiguous else failure_code
        sync_terminalize_messaging_delivery(
            conn,
            delivery_id=str(delivery_id),
            expected_state=str(state),
            terminal_state=terminal_state,
            failure_code=terminal_code,
            now_ms=now_ms,
            unknown_ordinal=normalized_unknown_ordinal,
        )
    return len(rows)
