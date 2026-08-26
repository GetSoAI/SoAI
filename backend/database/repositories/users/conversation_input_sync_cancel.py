"""SoAI - Conversation input cancel transactions [backend/database/repositories/users/conversation_input_sync_cancel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, ConversationInputNotCancellableError
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_pending_sync import (
    sync_cancel_pending_attachment_references,
)
from database.repositories.users.conversation_input_terminal_events import (
    sync_ensure_conversation_input_terminal_event,
)
from database.repositories.users.conversation_input_transition_resolution import (
    resolve_conversation_input_transition_state,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_cancel_conversation_input",)


def sync_cancel_conversation_input(
    sqlite_conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    input_id: str,
) -> JSONDict:
    cancelled_at_ms = epoch_ms()
    cursor = sqlite_conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'cancelled', terminal_code = 'cancelled',
            terminal_args_json = '{}', terminal_at_ms = ?, updated_at_ms = ?
        WHERE conv_id = ? AND user_id = ? AND input_id = ?
          AND (state = 'pending' OR (state = 'materializing' AND materialized_message_id IS NULL))
        RETURNING *
        """,
        (cancelled_at_ms, cancelled_at_ms, conv_id, user_id, input_id),
    )
    updated = sync_fetch_one_as_dict(cursor)
    transition = resolve_conversation_input_transition_state(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        input_id=input_id,
        updated_row=updated,
    )
    if transition.was_updated:
        sync_cancel_pending_attachment_references(
            sqlite_conn,
            conv_id=conv_id,
            user_id=user_id,
            conversation_input_id=input_id,
            updated_at_ms=cancelled_at_ms,
        )
    if transition.state == "cancelled":
        terminal_at_value = transition.input_record.get("terminal_at_ms")
        if not isinstance(terminal_at_value, int):
            raise ConflictError("Cancelled conversation input terminal time is invalid.")
        sync_ensure_conversation_input_terminal_event(
            sqlite_conn,
            input_id=input_id,
            user_id=user_id,
            conv_id=conv_id,
            source_message_id=None,
            terminal_state="cancelled",
            terminal_code="cancelled",
            created_at_ms=terminal_at_value,
        )
        return transition.input_record
    raise ConversationInputNotCancellableError(
        "Conversation input is not cancellable.",
        details={"input_id": input_id, "state": transition.state},
    )
