"""SoAI - Messaging interaction timeout claims [backend/database/repositories/users/messaging_interaction_timeouts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.messaging.interaction_resolution import MessagingInteractionTimeout

__all__ = ("sync_claim_expired_messaging_interactions",)


def _decode_timeout(row: sqlite3.Row) -> MessagingInteractionTimeout:
    if not all(isinstance(row[index], str) and row[index] for index in (0, 1, 2, 4)):
        raise StateError("Messaging interaction timeout identity is invalid.")
    if not isinstance(row[3], int) or row[3] <= 0:
        raise StateError("Messaging interaction timeout owner is invalid.")
    if not isinstance(row[5], int) or row[5] <= 0:
        raise StateError("Messaging interaction timeout generation is invalid.")
    return MessagingInteractionTimeout(
        route_id=row[0],
        task_id=row[1],
        conv_id=row[2],
        user_id=row[3],
        interaction_type=row[4],
        checkpoint_generation=row[5],
    )


def sync_claim_expired_messaging_interactions(
    conn: sqlite3.Connection,
    now_ms: int,
    limit: int,
) -> list[MessagingInteractionTimeout]:
    conn.execute(
        """
        UPDATE task_interaction_secret_handoffs
        SET state = 'expired', secret_ciphertext = NULL, updated_at_ms = ?
        WHERE state = 'resolution_staged' AND expires_at_ms <= ?
        """,
        (now_ms, now_ms),
    )
    conn.execute(
        """
        UPDATE messaging_interaction_routes
        SET state = 'expiring'
        WHERE state = 'resolving' AND interaction_type = 'vault_secret_request'
          AND EXISTS (
              SELECT 1 FROM task_interaction_secret_handoffs AS secret
              WHERE secret.task_id = messaging_interaction_routes.task_id
                AND secret.checkpoint_generation = messaging_interaction_routes.checkpoint_generation
                AND secret.state = 'expired'
          )
        """,
    )
    pending_rows = conn.execute(
        """
        SELECT route.route_id
        FROM messaging_interaction_routes AS route
        JOIN unified_tasks AS task ON task.task_id = route.task_id
        WHERE route.state = 'pending' AND route.expires_at_ms <= ?
          AND task.status = 'input_required'
        ORDER BY route.expires_at_ms ASC, route.route_id ASC
        LIMIT ?
        """,
        (now_ms, limit),
    ).fetchall()
    for pending_row in pending_rows:
        route_id = pending_row[0]
        if not isinstance(route_id, str):
            raise StateError("Messaging interaction timeout route is invalid.")
        conn.execute(
            """
            UPDATE messaging_interaction_routes
            SET state = 'expiring'
            WHERE route_id = ? AND state = 'pending' AND expires_at_ms <= ?
            """,
            (route_id, now_ms),
        )
    rows = conn.execute(
        """
        SELECT route.route_id, route.task_id, route.conv_id, route.user_id,
               route.interaction_type, route.checkpoint_generation
        FROM messaging_interaction_routes AS route
        JOIN unified_tasks AS task ON task.task_id = route.task_id
        WHERE route.state = 'expiring' AND task.status = 'input_required'
        ORDER BY route.expires_at_ms ASC, route.route_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_decode_timeout(row) for row in rows]
