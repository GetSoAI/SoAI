"""SoAI - Conversation domain event outbox payloads [backend/database/repositories/users/conversation_event_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.events.domain_event_payload import build_domain_event_payload
from core.types.json import JSONDict
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload

__all__ = ("sync_enqueue_conversation_updated_event",)


def sync_enqueue_conversation_updated_event(
    conn: sqlite3.Connection,
    *,
    created_at_ms: int,
    user_id: int,
    conv_id: str,
    last_modified_at_ms: int,
    model_settings: JSONDict,
) -> None:
    payload = build_domain_event_payload(
        fields={
            "user_id": user_id,
            "conv_id": conv_id,
            "last_modified_at_ms": last_modified_at_ms,
            "model_settings": model_settings,
        }
    )
    sync_enqueue_domain_event_payload(
        conn,
        event_type="ConversationUpdatedEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )
