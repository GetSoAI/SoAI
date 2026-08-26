"""SoAI - Conversation input terminal transitions [backend/database/repositories/users/conversation_input_terminalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_input_constants import TERMINAL_INPUT_STATES
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)
from database.repositories.users.conversation_input_terminal_events import (
    sync_ensure_conversation_input_terminal_event,
    sync_require_existing_conversation_input_terminal_event,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_terminalize_conversation_input",)


def sync_terminalize_conversation_input(
    sqlite_conn: sqlite3.Connection,
    input_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    terminal_state: str,
    terminal_code: str,
    terminal_args: JSONDict,
    source_message_id: int | None = None,
) -> JSONDict:
    if terminal_state not in TERMINAL_INPUT_STATES:
        raise ValidationError("Conversation input terminal state is invalid.")
    terminal_at_ms = epoch_ms()
    cursor = sqlite_conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = ?, terminal_code = ?, terminal_args_json = ?,
            terminal_at_ms = ?, updated_at_ms = ?
        WHERE input_id = ?
          AND state IN ('materializing', 'running', 'input_required')
          AND claim_generation = ? AND claim_owner = ? AND claim_server_boot_id = ?
          AND conversation_generation = (
              SELECT input_generation
              FROM webui_conversations
              WHERE id = webui_conversation_inputs.conv_id
                AND user_id = webui_conversation_inputs.user_id
          )
        RETURNING *
        """,
        (
            terminal_state,
            terminal_code,
            serialize_json_compact_stable(terminal_args),
            terminal_at_ms,
            terminal_at_ms,
            input_id,
            claim_generation,
            claim_owner,
            server_boot_id,
        ),
    )
    updated = sync_fetch_one_as_dict(cursor)
    if updated is not None:
        formatted = format_conversation_input_row(updated)
        if formatted is None:
            raise StateError("Terminal conversation input is missing.")
        user_id = formatted.get("user_id")
        conv_id = formatted.get("conv_id")
        if not isinstance(user_id, int) or not isinstance(conv_id, str):
            raise StateError("Terminal conversation input ownership is invalid.")
        sync_ensure_conversation_input_terminal_event(
            sqlite_conn,
            input_id=input_id,
            user_id=user_id,
            conv_id=conv_id,
            source_message_id=source_message_id,
            terminal_state=terminal_state,
            terminal_code=terminal_code,
            created_at_ms=terminal_at_ms,
        )
        return formatted
    existing = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT * FROM webui_conversation_inputs WHERE input_id = ? LIMIT 1",
            (input_id,),
        ),
    )
    formatted = format_conversation_input_row(existing)
    if formatted is not None and formatted.get("state") == terminal_state:
        if formatted.get("terminal_code") == terminal_code:
            user_id = formatted.get("user_id")
            conv_id = formatted.get("conv_id")
            existing_terminal_at_ms = formatted.get("terminal_at_ms")
            if (
                not isinstance(user_id, int)
                or not isinstance(conv_id, str)
                or not isinstance(existing_terminal_at_ms, int)
            ):
                raise StateError("Terminal conversation input identity is invalid.")
            sync_require_existing_conversation_input_terminal_event(
                sqlite_conn,
                input_id=input_id,
                user_id=user_id,
                conv_id=conv_id,
                terminal_state=terminal_state,
                terminal_code=terminal_code,
                created_at_ms=existing_terminal_at_ms,
            )
            return formatted
    raise ConflictError("Conversation input terminalization fence changed.")
