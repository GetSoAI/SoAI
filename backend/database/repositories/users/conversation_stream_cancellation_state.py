"""SoAI - Durable Chat stream cancellation state reads [backend/database/repositories/users/conversation_stream_cancellation_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from hashlib import sha256
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "CHAT_STREAM_CANCELLATION_EVENT_TYPE",
    "CHAT_STREAM_CANCELLATION_SETTLED_EVENT_TYPE",
    "build_chat_stream_cancellation_event_id",
    "build_chat_stream_cancellation_settled_event_id",
    "read_chat_stream_cancellation_receipt",
    "read_chat_stream_request_terminal_state",
    "sync_has_chat_stream_cancellation_for_input",
    "sync_has_chat_stream_cancellation_receipt",
    "sync_has_pending_chat_stream_cancellation",
    "validate_chat_stream_cancellation_receipt_payload",
)

CHAT_STREAM_CANCELLATION_EVENT_TYPE = "ConversationStreamCancellationRequestedEvent"
CHAT_STREAM_CANCELLATION_SETTLED_EVENT_TYPE = "ConversationStreamCancellationSettledEvent"


def validate_chat_stream_cancellation_receipt_payload(
    *,
    event_type: SQLiteValue,
    payload_json: SQLiteValue,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> JSONDict:
    if event_type != CHAT_STREAM_CANCELLATION_EVENT_TYPE or not isinstance(payload_json, str):
        raise StateError("Chat stream cancellation receipt identity collided.")
    payload = parse_json_dict(payload_json, field="Chat stream cancellation receipt")
    expected = {"user_id": user_id, "conversation_id": conv_id, "request_id": request_id}
    if any(payload.get(key) != value for key, value in expected.items()):
        raise StateError("Chat stream cancellation receipt identity collided.")
    if not isinstance(payload.get("force_pending_steers"), bool):
        raise StateError("Chat stream cancellation receipt policy is invalid.")
    return payload


def build_chat_stream_cancellation_event_id(*, user_id: int, conv_id: str, request_id: str) -> str:
    identity = f"{user_id}\0{conv_id}\0{request_id}".encode("utf-8")
    return f"chat_stream_cancellation:{sha256(identity).hexdigest()}"


def build_chat_stream_cancellation_settled_event_id(
    *, user_id: int, conv_id: str, request_id: str
) -> str:
    identity = f"{user_id}\0{conv_id}\0{request_id}".encode("utf-8")
    return f"chat_stream_cancellation_settled:{sha256(identity).hexdigest()}"


def read_chat_stream_cancellation_receipt(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> JSONDict | None:
    row = conn.execute(
        "SELECT event_type, payload_json FROM webui_domain_event_outbox WHERE event_id = ? LIMIT 1",
        (
            build_chat_stream_cancellation_event_id(
                user_id=user_id, conv_id=conv_id, request_id=request_id
            ),
        ),
    ).fetchone()
    if row is None:
        return None
    return validate_chat_stream_cancellation_receipt_payload(
        event_type=row[0],
        payload_json=row[1],
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    )


def sync_has_chat_stream_cancellation_receipt(
    conn: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> bool:
    return (
        read_chat_stream_cancellation_receipt(
            conn,
            user_id=user_id,
            conv_id=conv_id,
            request_id=request_id,
        )
        is not None
    )


def sync_has_chat_stream_cancellation_for_input(
    conn: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM webui_domain_event_outbox
        WHERE event_type = ?
          AND json_extract(payload_json, '$.user_id') = ?
          AND json_extract(payload_json, '$.conversation_id') = ?
          AND (json_extract(payload_json, '$.request_id') = ?
               OR json_extract(payload_json, '$.request_id') GLOB ?)
        LIMIT 1
        """,
        (
            CHAT_STREAM_CANCELLATION_EVENT_TYPE,
            user_id,
            conv_id,
            request_id,
            f"{request_id}:variant:[0-9]*",
        ),
    ).fetchone()
    return row is not None


def read_chat_stream_request_terminal_state(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> str | None:
    input_row = conn.execute(
        """
        SELECT state FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ?
          AND (request_id = ? OR ? GLOB request_id || ':variant:[0-9]*')
        LIMIT 1
        """,
        (conv_id, user_id, request_id, request_id),
    ).fetchone()
    if input_row is not None and isinstance(input_row[0], str):
        input_state = input_row[0]
        if input_state in {"completed", "failed", "cancelled", "effect_unknown"}:
            return input_state
        return None
    row = conn.execute(
        """
        SELECT message.finish_reason
        FROM webui_messages AS message
        JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
        WHERE message.conv_id = ? AND conversation.user_id = ?
          AND message.role = 'assistant' AND message.request_id = ?
          AND message.finalized_at_ms IS NOT NULL
        LIMIT 1
        """,
        (conv_id, user_id, request_id),
    ).fetchone()
    if row is not None:
        return row[0] if isinstance(row[0], str) and row[0] else "completed"
    settled = conn.execute(
        "SELECT 1 FROM webui_domain_event_outbox WHERE event_id = ? LIMIT 1",
        (
            build_chat_stream_cancellation_settled_event_id(
                user_id=user_id, conv_id=conv_id, request_id=request_id
            ),
        ),
    ).fetchone()
    return "cancelled" if settled is not None else None


def sync_has_pending_chat_stream_cancellation(
    conn: sqlite3.Connection,
    user_id: int,
    conv_id: str,
) -> bool:
    rows = conn.execute(
        """
        SELECT payload_json FROM webui_domain_event_outbox
        WHERE event_type = ?
          AND json_extract(payload_json, '$.user_id') = ?
          AND json_extract(payload_json, '$.conversation_id') = ?
        ORDER BY id DESC
        """,
        (CHAT_STREAM_CANCELLATION_EVENT_TYPE, user_id, conv_id),
    ).fetchall()
    for row in rows:
        if not isinstance(row[0], str):
            raise StateError("Chat stream cancellation receipt payload is invalid.")
        payload = parse_json_dict(row[0], field="Chat stream cancellation receipt")
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise StateError("Chat stream cancellation receipt request identity is invalid.")
        if (
            read_chat_stream_request_terminal_state(
                conn,
                user_id=user_id,
                conv_id=conv_id,
                request_id=request_id,
            )
            is None
        ):
            return True
    return False
