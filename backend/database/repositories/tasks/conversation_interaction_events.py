"""SoAI - Conversation interaction-required outbox intent [backend/database/repositories/tasks/conversation_interaction_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.events.domain_event_payload import build_domain_event_payload
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload

__all__ = ("sync_ensure_conversation_interaction_required_event",)

EVENT_TYPE = "ConversationInteractionRequiredEvent"


def sync_ensure_conversation_interaction_required_event(
    conn: sqlite3.Connection,
    *,
    route_id: str,
    task_id: str,
    input_id: str,
    user_id: int,
    conv_id: str,
    interaction_type: str,
    reply_token: str,
    focus_nonce: str,
    created_at_ms: int,
) -> None:
    event_id = f"conversation_interaction_required:{task_id}"
    payload = build_domain_event_payload(
        event_id=event_id,
        timestamp_unix=created_at_ms / 1000.0,
        fields={
            "task_id": task_id,
            "route_id": route_id,
            "interaction_type": interaction_type,
            "reply_token": reply_token,
            "focus_nonce": focus_nonce,
            "input_id": input_id,
            "conv_id": conv_id,
            "user_id": user_id,
        },
    )
    sync_ensure_domain_event_payload(
        conn,
        event_type=EVENT_TYPE,
        payload=payload,
        created_at_ms=created_at_ms,
    )
