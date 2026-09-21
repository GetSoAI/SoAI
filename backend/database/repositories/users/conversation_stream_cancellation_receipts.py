"""SoAI - Durable Chat stream cancellation receipts [backend/database/repositories/users/conversation_stream_cancellation_receipts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.events.domain_event_payload import build_domain_event_payload
from core.timing.epoch import epoch_ms
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload
from database.repositories.users.conversation_input_force_steering import (
    sync_force_pending_conversation_steers,
)
from database.repositories.users.conversation_stream_cancellation_state import (
    CHAT_STREAM_CANCELLATION_EVENT_TYPE,
    CHAT_STREAM_CANCELLATION_SETTLED_EVENT_TYPE,
    build_chat_stream_cancellation_event_id,
    build_chat_stream_cancellation_settled_event_id,
    read_chat_stream_cancellation_receipt,
    read_chat_stream_request_terminal_state,
)
from database.repositories.users.message_streaming_assistant.message_finalization_transactions import (
    sync_finalize_streaming_assistant_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_accept_chat_stream_cancellation",
    "sync_settle_local_chat_stream_cancellation",
)


def _persisted_target_exists(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM webui_messages AS message
        JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
        WHERE message.conv_id = ? AND conversation.user_id = ?
          AND message.role = 'assistant' AND message.request_id = ?
        UNION ALL
        SELECT 1
        FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ?
          AND (request_id = ? OR ? GLOB request_id || ':variant:[0-9]*')
        LIMIT 1
        """,
        (conv_id, user_id, request_id, conv_id, user_id, request_id, request_id),
    ).fetchone()
    return row is not None


def _recover_accepted_without_execution(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> bool:
    pending_input = conn.execute(
        """
        SELECT 1 FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ?
          AND state NOT IN ('completed', 'failed', 'cancelled', 'effect_unknown')
          AND (request_id = ? OR ? GLOB request_id || ':variant:[0-9]*')
        LIMIT 1
        """,
        (conv_id, user_id, request_id, request_id),
    ).fetchone()
    if pending_input is not None:
        return False
    assistant = conn.execute(
        """
        SELECT message.created_at_ms, message.finalized_at_ms,
               message.prompt_tokens, message.completion_tokens, message.total_tokens,
               message.usage_source, message.generation_latency_ms,
               message.thinking_tail_duration_ms
        FROM webui_messages AS message
        JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
        WHERE message.conv_id = ? AND conversation.user_id = ?
          AND message.role = 'assistant' AND message.request_id = ?
        LIMIT 1
        """,
        (conv_id, user_id, request_id),
    ).fetchone()
    if assistant is not None:
        if assistant[1] is None:
            sync_finalize_streaming_assistant_message(
                conn,
                conv_id,
                user_id,
                assistant[0],
                request_id,
                "cancelled",
                assistant[2],
                assistant[3],
                assistant[4],
                assistant[5],
                assistant[6],
                assistant[7],
                "Chat stream was cancelled during recovery.",
            )
        sync_settle_local_chat_stream_cancellation(conn, user_id, conv_id, request_id)
        return True
    sync_settle_local_chat_stream_cancellation(conn, user_id, conv_id, request_id)
    return True


def sync_accept_chat_stream_cancellation(
    conn: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    request_id: str,
    force_pending_steers: bool,
    allow_unpersisted_target: bool,
) -> JSONDict:
    existing = read_chat_stream_cancellation_receipt(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    )
    terminal_state = read_chat_stream_request_terminal_state(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    )
    if terminal_state is not None:
        if existing is not None:
            sync_settle_local_chat_stream_cancellation(conn, user_id, conv_id, request_id)
        return {
            "status": "already_terminal",
            "terminal_status": terminal_state,
            "created": False,
            "forced_input_created": False,
        }
    if existing is not None:
        if not allow_unpersisted_target and _recover_accepted_without_execution(
            conn,
            user_id=user_id,
            conv_id=conv_id,
            request_id=request_id,
        ):
            return {
                "status": "already_terminal",
                "terminal_status": "cancelled",
                "created": False,
                "recovered": True,
                "forced_input_created": False,
            }
        return {
            "status": "cancellation_requested",
            "created": False,
            "force_pending_steers": existing["force_pending_steers"],
            "forced_input_created": False,
        }
    if not allow_unpersisted_target and not _persisted_target_exists(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    ):
        raise ConflictError("The requested chat stream is no longer current.")
    forced_input_created = False
    if force_pending_steers:
        forced = sync_force_pending_conversation_steers(
            conn,
            conv_id,
            user_id,
            request_id,
            None,
        )
        forced_input_created = forced.get("created") is True
    accepted_at_ms = epoch_ms()
    payload = build_domain_event_payload(
        event_id=build_chat_stream_cancellation_event_id(
            user_id=user_id, conv_id=conv_id, request_id=request_id
        ),
        timestamp_unix=accepted_at_ms / 1000.0,
        fields={
            "user_id": user_id,
            "conversation_id": conv_id,
            "request_id": request_id,
            "force_pending_steers": force_pending_steers,
        },
    )
    sync_enqueue_domain_event_payload(
        conn,
        event_type=CHAT_STREAM_CANCELLATION_EVENT_TYPE,
        payload=payload,
        created_at_ms=accepted_at_ms,
    )
    terminal_completed = not allow_unpersisted_target and _recover_accepted_without_execution(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    )
    return {
        "status": "cancellation_requested",
        "created": True,
        "force_pending_steers": force_pending_steers,
        "forced_input_created": forced_input_created,
        "terminal_completed": terminal_completed,
    }


def sync_settle_local_chat_stream_cancellation(
    conn: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> None:
    if (
        read_chat_stream_cancellation_receipt(
            conn,
            user_id=user_id,
            conv_id=conv_id,
            request_id=request_id,
        )
        is None
    ):
        raise StateError("Chat stream cancellation cannot settle before acceptance.")
    existing = conn.execute(
        "SELECT event_type FROM webui_domain_event_outbox WHERE event_id = ? LIMIT 1",
        (
            build_chat_stream_cancellation_settled_event_id(
                user_id=user_id, conv_id=conv_id, request_id=request_id
            ),
        ),
    ).fetchone()
    if existing is not None:
        if existing[0] != CHAT_STREAM_CANCELLATION_SETTLED_EVENT_TYPE:
            raise StateError("Chat stream cancellation settlement identity collided.")
        return
    settled_at_ms = epoch_ms()
    payload = build_domain_event_payload(
        event_id=build_chat_stream_cancellation_settled_event_id(
            user_id=user_id, conv_id=conv_id, request_id=request_id
        ),
        timestamp_unix=settled_at_ms / 1000.0,
        fields={
            "user_id": user_id,
            "conversation_id": conv_id,
            "request_id": request_id,
        },
    )
    sync_enqueue_domain_event_payload(
        conn,
        event_type=CHAT_STREAM_CANCELLATION_SETTLED_EVENT_TYPE,
        payload=payload,
        created_at_ms=settled_at_ms,
    )
