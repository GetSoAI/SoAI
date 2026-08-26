"""SoAI - Durable Messaging cancellation control recovery [backend/database/repositories/users/messaging_control_cancellation_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_reconcile_pending_messaging_cancellations",)


def sync_reconcile_pending_messaging_cancellations(
    conn: sqlite3.Connection,
) -> list[JSONDict]:
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET diagnostic_code = NULL
        WHERE diagnostic_code = 'cancel_pending'
          AND NOT EXISTS (
              SELECT 1 FROM webui_conversation_inputs AS input
              WHERE input.input_id = messaging_ingress_events.linked_input_id
                AND input.state IN ('pending', 'materializing', 'running', 'input_required')
          )
        """,
    )
    rows = conn.execute(
        """
        SELECT ingress.ingress_id, input.input_id, input.conv_id, input.user_id
        FROM messaging_ingress_events AS ingress
        JOIN webui_conversation_inputs AS input
          ON input.input_id = ingress.linked_input_id
        WHERE ingress.diagnostic_code = 'cancel_pending'
          AND input.state IN ('pending', 'materializing', 'running', 'input_required')
        ORDER BY ingress.received_at_ms ASC, ingress.ingress_id ASC
        LIMIT 100
        """,
    ).fetchall()
    return [
        {
            "status": "cancel_pending",
            "ingress_id": str(row[0]),
            "cancellation_input_id": str(row[1]),
            "conv_id": str(row[2]),
            "user_id": int(row[3]),
        }
        for row in rows
    ]
