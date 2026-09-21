"""SoAI - Async durable Chat cancellation queries [backend/database/repositories/users/conversation_stream_cancellation_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_stream_cancellation_state import (
    CHAT_STREAM_CANCELLATION_EVENT_TYPE,
    build_chat_stream_cancellation_event_id,
    build_chat_stream_cancellation_settled_event_id,
    validate_chat_stream_cancellation_receipt_payload,
)

__all__ = (
    "query_has_chat_stream_cancellation_for_input",
    "query_has_chat_stream_cancellation_receipt",
    "query_has_pending_chat_stream_cancellation",
)


async def query_has_chat_stream_cancellation_receipt(
    conn: aiosqlite.Connection,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> bool:
    row = await query_one_to_dict(
        conn,
        "SELECT event_type, payload_json FROM webui_domain_event_outbox WHERE event_id = ? LIMIT 1",
        (
            build_chat_stream_cancellation_event_id(
                user_id=user_id, conv_id=conv_id, request_id=request_id
            ),
        ),
    )
    if row is None:
        return False
    validate_chat_stream_cancellation_receipt_payload(
        event_type=row.get("event_type"),
        payload_json=row.get("payload_json"),
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    )
    return True


async def query_has_chat_stream_cancellation_for_input(
    conn: aiosqlite.Connection,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> bool:
    row = await query_one_to_dict(
        conn,
        """
        SELECT 1 AS found FROM webui_domain_event_outbox
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
    )
    return row is not None


async def _query_chat_stream_request_terminal_state(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> str | None:
    input_row = await query_one_to_dict(
        conn,
        """
        SELECT state FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ?
          AND (request_id = ? OR ? GLOB request_id || ':variant:[0-9]*')
        LIMIT 1
        """,
        (conv_id, user_id, request_id, request_id),
    )
    if input_row is not None and isinstance(input_row.get("state"), str):
        input_state = input_row["state"]
        if input_state in {"completed", "failed", "cancelled", "effect_unknown"}:
            return input_state
        return None
    message = await query_one_to_dict(
        conn,
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
    )
    if message is not None:
        finish_reason = message.get("finish_reason")
        return finish_reason if isinstance(finish_reason, str) and finish_reason else "completed"
    settled = await query_one_to_dict(
        conn,
        "SELECT 1 AS found FROM webui_domain_event_outbox WHERE event_id = ? LIMIT 1",
        (
            build_chat_stream_cancellation_settled_event_id(
                user_id=user_id, conv_id=conv_id, request_id=request_id
            ),
        ),
    )
    return "cancelled" if settled is not None else None


async def query_has_pending_chat_stream_cancellation(
    conn: aiosqlite.Connection,
    user_id: int,
    conv_id: str,
) -> bool:
    rows = await query_to_dicts(
        conn,
        """
        SELECT payload_json FROM webui_domain_event_outbox
        WHERE event_type = ?
          AND json_extract(payload_json, '$.user_id') = ?
          AND json_extract(payload_json, '$.conversation_id') = ?
        ORDER BY id DESC
        """,
        (CHAT_STREAM_CANCELLATION_EVENT_TYPE, user_id, conv_id),
    )
    for row in rows:
        payload_json = row.get("payload_json")
        if not isinstance(payload_json, str):
            raise StateError("Chat stream cancellation receipt payload is invalid.")
        payload = parse_json_dict(payload_json, field="Chat stream cancellation receipt")
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise StateError("Chat stream cancellation receipt request identity is invalid.")
        terminal_state = await _query_chat_stream_request_terminal_state(
            conn,
            user_id=user_id,
            conv_id=conv_id,
            request_id=request_id,
        )
        if terminal_state is None:
            return True
    return False
