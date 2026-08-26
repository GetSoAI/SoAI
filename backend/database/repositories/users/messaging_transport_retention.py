"""SoAI - Messaging transport record retention [backend/database/repositories/users/messaging_transport_retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.messaging.transport_retention import messaging_transport_retention_cutoff_ms
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform

__all__ = ("sync_cleanup_messaging_transport_records",)


def _delete_terminal_deliveries(
    conn: sqlite3.Connection,
    *,
    platform: MessagingPlatform,
    cutoff_ms: int,
) -> int:
    return len(
        conn.execute(
            """
            DELETE FROM messaging_deliveries
            WHERE state IN ('sent', 'failed', 'skipped', 'delivery_unknown')
              AND terminal_at_ms <= ?
              AND account_id IN (
                  SELECT account_id FROM messaging_accounts WHERE platform = ?
              )
            RETURNING delivery_id
            """,
            (cutoff_ms, platform),
        ).fetchall(),
    )


def _delete_terminal_interactions(
    conn: sqlite3.Connection,
    *,
    platform: MessagingPlatform,
    cutoff_ms: int,
) -> int:
    return len(
        conn.execute(
            """
            DELETE FROM messaging_interaction_routes
            WHERE state IN ('resolved', 'expired', 'cancelled')
              AND resolved_at_ms IS NOT NULL AND resolved_at_ms <= ?
              AND account_id IN (
                  SELECT account_id FROM messaging_accounts WHERE platform = ?
              )
              AND NOT EXISTS (
                  SELECT 1 FROM webui_conversation_inputs AS input
                  WHERE input.input_id = messaging_interaction_routes.input_id
                    AND input.state NOT IN ('completed', 'failed', 'cancelled', 'effect_unknown')
              )
            RETURNING route_id
            """,
            (cutoff_ms, platform),
        ).fetchall(),
    )


def _delete_terminal_ingress(
    conn: sqlite3.Connection,
    *,
    platform: MessagingPlatform,
    cutoff_ms: int,
) -> int:
    return len(
        conn.execute(
            """
            DELETE FROM messaging_ingress_events
            WHERE platform = ? AND processed_at_ms <= ?
              AND NOT EXISTS (
                  SELECT 1 FROM webui_conversation_inputs AS input
                  WHERE input.input_id = messaging_ingress_events.linked_input_id
                    AND input.state NOT IN ('completed', 'failed', 'cancelled', 'effect_unknown')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM messaging_interaction_routes AS route
                  WHERE route.route_id = messaging_ingress_events.linked_interaction_route_id
                    AND route.state NOT IN ('resolved', 'expired', 'cancelled')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM messaging_thread_bindings AS binding
                  WHERE binding.pending_reset_control_id = messaging_ingress_events.linked_control_id
                    AND binding.pending_reset_state = 'accepted'
              )
            RETURNING ingress_id
            """,
            (platform, cutoff_ms),
        ).fetchall(),
    )


def sync_cleanup_messaging_transport_records(
    conn: sqlite3.Connection,
    now_ms: int,
) -> JSONDict:
    delivery_count = 0
    interaction_count = 0
    ingress_count = 0
    for platform in ("telegram", "whatsapp", "discord"):
        cutoff_ms = messaging_transport_retention_cutoff_ms(platform, now_ms)
        delivery_count += _delete_terminal_deliveries(
            conn,
            platform=platform,
            cutoff_ms=cutoff_ms,
        )
        interaction_count += _delete_terminal_interactions(
            conn,
            platform=platform,
            cutoff_ms=cutoff_ms,
        )
        ingress_count += _delete_terminal_ingress(
            conn,
            platform=platform,
            cutoff_ms=cutoff_ms,
        )
    return {
        "delivery_count": delivery_count,
        "interaction_count": interaction_count,
        "ingress_count": ingress_count,
    }
