"""SoAI - Messaging interaction lifecycle fencing [backend/database/repositories/users/messaging_interaction_fencing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

__all__ = (
    "sync_fail_messaging_interaction_route",
    "sync_fence_messaging_interactions",
)


def sync_fail_messaging_interaction_route(
    conn: sqlite3.Connection,
    route_id: str,
    diagnostic_code: str,
    resolved_at_ms: int,
) -> None:
    row = conn.execute(
        """
        SELECT task_id, resolution_ingress_id
        FROM messaging_interaction_routes
        WHERE route_id = ? AND state IN ('resolving', 'expiring')
        """,
        (route_id,),
    ).fetchone()
    if row is None:
        return
    task_id, ingress_id = row
    conn.execute(
        """
        UPDATE task_interaction_secret_handoffs
        SET state = 'expired', secret_ciphertext = NULL, updated_at_ms = ?
        WHERE task_id = ? AND state IN ('resolution_staged', 'pending', 'claimed')
        """,
        (resolved_at_ms, task_id),
    )
    conn.execute(
        """
        UPDATE messaging_interaction_routes
        SET state = 'expiring', expires_at_ms = MIN(expires_at_ms, ?)
        WHERE route_id = ? AND state IN ('resolving', 'expiring')
        """,
        (resolved_at_ms, route_id),
    )
    if isinstance(ingress_id, str):
        conn.execute(
            """
            UPDATE messaging_ingress_events
            SET outcome = 'failed', diagnostic_code = ?, processed_at_ms = ?
            WHERE ingress_id = ? AND linked_interaction_route_id = ?
            """,
            (diagnostic_code, resolved_at_ms, ingress_id, route_id),
        )


def sync_fence_messaging_interactions(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    resolved_at_ms: int,
    sender_id: str | None = None,
) -> tuple[str, ...]:
    sender_predicate = "" if sender_id is None else "AND originating_sender_id = ?"
    parameters: tuple[str | int, ...] = (
        (account_id, user_id) if sender_id is None else (account_id, user_id, sender_id)
    )
    rows = conn.execute(
        f"""
        SELECT task_id FROM messaging_interaction_routes
        WHERE account_id = ? AND user_id = ?
          AND state IN ('pending', 'resolving', 'expiring')
          {sender_predicate}
        ORDER BY created_at_ms ASC, route_id ASC
        """,
        parameters,
    ).fetchall()
    task_ids = tuple(str(row[0]) for row in rows)
    if not task_ids:
        return ()
    placeholders = ",".join("?" for _task_id in task_ids)
    conn.execute(
        f"DELETE FROM task_interaction_secret_handoffs WHERE task_id IN ({placeholders})",
        task_ids,
    )
    conn.execute(
        f"""
        UPDATE messaging_interaction_routes
        SET state = 'expiring', expires_at_ms = MIN(expires_at_ms, ?)
        WHERE task_id IN ({placeholders})
          AND state IN ('pending', 'resolving', 'expiring')
        """,
        (resolved_at_ms, *task_ids),
    )
    return task_ids
