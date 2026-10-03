"""SoAI - Async durable Chat cancellation queries [backend/database/repositories/users/conversation_stream_cancellation_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_stream_cancellation_state import (
    CHAT_STREAM_CANCELLATION_EVENT_TYPE,
    CHAT_STREAM_CANCELLATION_FOR_INPUT_SQL,
    CHAT_STREAM_CANCELLATION_SETTLED_SQL,
    CHAT_STREAM_REQUEST_FINISH_REASON_SQL,
    CHAT_STREAM_REQUEST_INPUT_STATE_SQL,
    CHAT_STREAM_TERMINAL_INPUT_STATES,
    PENDING_CHAT_STREAM_CANCELLATIONS_SQL,
    build_chat_stream_cancellation_event_id,
    build_chat_stream_cancellation_for_input_params,
    build_chat_stream_cancellation_settled_event_id,
    parse_pending_chat_stream_cancellation_request_id,
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
        CHAT_STREAM_CANCELLATION_FOR_INPUT_SQL,
        build_chat_stream_cancellation_for_input_params(
            user_id=user_id,
            conv_id=conv_id,
            request_id=request_id,
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
        CHAT_STREAM_REQUEST_INPUT_STATE_SQL,
        (conv_id, user_id, request_id, request_id),
    )
    if input_row is not None and isinstance(input_row.get("state"), str):
        input_state = input_row["state"]
        return input_state if input_state in CHAT_STREAM_TERMINAL_INPUT_STATES else None
    message = await query_one_to_dict(
        conn,
        CHAT_STREAM_REQUEST_FINISH_REASON_SQL,
        (conv_id, user_id, request_id),
    )
    if message is not None:
        finish_reason = message.get("finish_reason")
        return finish_reason if isinstance(finish_reason, str) and finish_reason else "completed"
    settled = await query_one_to_dict(
        conn,
        CHAT_STREAM_CANCELLATION_SETTLED_SQL,
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
        PENDING_CHAT_STREAM_CANCELLATIONS_SQL,
        (CHAT_STREAM_CANCELLATION_EVENT_TYPE, user_id, conv_id),
    )
    for row in rows:
        request_id = parse_pending_chat_stream_cancellation_request_id(row.get("payload_json"))
        terminal_state = await _query_chat_stream_request_terminal_state(
            conn,
            user_id=user_id,
            conv_id=conv_id,
            request_id=request_id,
        )
        if terminal_state is None:
            return True
    return False
