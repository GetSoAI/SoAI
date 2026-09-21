"""SoAI - Cancelled durable input recovery [backend/database/repositories/users/conversation_input_cancellation_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from database.repositories.users.conversation_input_assistant_recovery import (
    sync_finalize_abandoned_conversation_input_assistants,
)
from database.repositories.users.conversation_input_terminal_events import (
    sync_ensure_conversation_input_terminal_event,
)
from database.repositories.users.conversation_stream_cancellation_receipts import (
    sync_settle_local_chat_stream_cancellation,
)

__all__ = ("sync_recover_cancelled_conversation_input",)


def sync_recover_cancelled_conversation_input(
    sqlite_conn: sqlite3.Connection,
    *,
    input_id: str,
    conv_id: str,
    user_id: int,
    request_id: str,
    recovered_at_ms: int,
) -> None:
    uncertain_tool_effect = (
        sqlite_conn.execute(
            """
        SELECT 1
        FROM webui_chat_tool_calls AS tool_call
        JOIN webui_messages AS assistant
          ON assistant.conv_id = tool_call.conv_id
         AND assistant.created_at_ms = tool_call.assistant_at_ms
        WHERE assistant.conv_id = ? AND assistant.role = 'assistant'
          AND (assistant.request_id = ? OR assistant.request_id GLOB ?)
          AND tool_call.status IN ('pending', 'running')
        LIMIT 1
        """,
            (conv_id, request_id, f"{request_id}:variant:[0-9]*"),
        ).fetchone()
        is not None
    )
    _assistants, source_message_id = sync_finalize_abandoned_conversation_input_assistants(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        request_id=request_id,
        finish_reason="cancelled",
        terminal_reason="Chat stream was cancelled during recovery.",
    )
    terminal_state = "effect_unknown" if uncertain_tool_effect else "cancelled"
    terminal_code = "interrupted_effect_unknown" if uncertain_tool_effect else "cancelled"
    updated = sqlite_conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = ?, terminal_code = ?, terminal_args_json = ?,
            terminal_at_ms = ?, updated_at_ms = ?
        WHERE input_id = ? AND state IN ('materializing', 'running')
        """,
        (
            terminal_state,
            terminal_code,
            serialize_json_compact_stable({}),
            recovered_at_ms,
            recovered_at_ms,
            input_id,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Cancelled conversation input changed during reconciliation.")
    sync_ensure_conversation_input_terminal_event(
        sqlite_conn,
        input_id=input_id,
        user_id=user_id,
        conv_id=conv_id,
        source_message_id=source_message_id,
        terminal_state=terminal_state,
        terminal_code=terminal_code,
        created_at_ms=recovered_at_ms,
    )
    sync_settle_local_chat_stream_cancellation(
        sqlite_conn,
        user_id,
        conv_id,
        request_id,
    )
