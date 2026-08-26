"""SoAI - Canonical conversation control completion outbox intent [backend/database/repositories/users/conversation_control_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.events.domain_event_payload import build_domain_event_payload
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload

__all__ = ("sync_ensure_conversation_control_completed_event",)

EVENT_TYPE = "ConversationControlCompletedEvent"


def sync_ensure_conversation_control_completed_event(
    conn: sqlite3.Connection,
    *,
    control_id: str,
    user_id: int,
    conv_id: str,
    target_conv_id: str,
    source_message_id: int,
    created_at_ms: int,
) -> None:
    event_id = f"conversation_control_completed:{control_id}"
    payload = build_domain_event_payload(
        event_id=event_id,
        timestamp_unix=created_at_ms / 1000.0,
        fields={
            "user_id": user_id,
            "conv_id": conv_id,
            "target_conv_id": target_conv_id,
            "control_id": control_id,
            "source_message_id": source_message_id,
        },
    )
    sync_ensure_domain_event_payload(
        conn,
        event_type=EVENT_TYPE,
        payload=payload,
        created_at_ms=created_at_ms,
    )
