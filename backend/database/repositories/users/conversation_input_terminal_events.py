"""SoAI - Canonical conversation input terminal outbox intent [backend/database/repositories/users/conversation_input_terminal_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.events.domain_event_payload import build_domain_event_payload
from core.serialization.json_parsing import parse_json_dict
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload

__all__ = (
    "sync_ensure_conversation_input_terminal_event",
    "sync_require_existing_conversation_input_terminal_event",
)

EVENT_TYPE = "ConversationInputTerminalEvent"


def sync_ensure_conversation_input_terminal_event(
    conn: sqlite3.Connection,
    *,
    input_id: str,
    user_id: int,
    conv_id: str,
    source_message_id: int | None,
    terminal_state: str,
    terminal_code: str,
    created_at_ms: int,
) -> None:
    event_id = f"conversation_input_terminal:{input_id}"
    payload = build_domain_event_payload(
        event_id=event_id,
        timestamp_unix=created_at_ms / 1000.0,
        fields={
            "user_id": user_id,
            "conv_id": conv_id,
            "input_id": input_id,
            "source_message_id": source_message_id,
            "terminal_state": terminal_state,
            "terminal_code": terminal_code,
        },
    )
    sync_ensure_domain_event_payload(
        conn,
        event_type=EVENT_TYPE,
        payload=payload,
        created_at_ms=created_at_ms,
    )


def sync_require_existing_conversation_input_terminal_event(
    conn: sqlite3.Connection,
    *,
    input_id: str,
    user_id: int,
    conv_id: str,
    terminal_state: str,
    terminal_code: str,
    created_at_ms: int,
) -> None:
    event_id = f"conversation_input_terminal:{input_id}"
    existing = conn.execute(
        "SELECT event_type, payload_json FROM webui_domain_event_outbox WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if existing is None or existing[0] != EVENT_TYPE or not isinstance(existing[1], str):
        raise StateError("Conversation input terminal event is unavailable.")
    payload = parse_json_dict(existing[1], field="Conversation input terminal event payload")
    expected_fields = {
        "event_id": event_id,
        "user_id": user_id,
        "conv_id": conv_id,
        "input_id": input_id,
        "terminal_state": terminal_state,
        "terminal_code": terminal_code,
        "timestamp": created_at_ms / 1000.0,
    }
    if any(payload.get(field_name) != value for field_name, value in expected_fields.items()):
        raise StateError("Conversation input terminal event identity collided.")
