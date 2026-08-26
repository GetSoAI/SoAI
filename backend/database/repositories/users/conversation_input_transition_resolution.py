"""SoAI - Conversation input transition row resolution [backend/database/repositories/users/conversation_input_transition_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "ConversationInputTransitionState",
    "read_conversation_input_by_input_id",
    "read_conversation_input_by_source_key",
    "resolve_conversation_input_transition_state",
)


@dataclass(frozen=True, slots=True)
class ConversationInputTransitionState:
    row: SQLiteRowDict
    input_record: JSONDict
    state: str
    was_updated: bool


def read_conversation_input_by_source_key(
    sqlite_conn: sqlite3.Connection,
    *,
    user_id: int,
    transport_origin: str,
    source_key: str,
) -> SQLiteRowDict | None:
    cursor = sqlite_conn.execute(
        """
        SELECT *
        FROM webui_conversation_inputs
        WHERE user_id = ? AND transport_origin = ? AND source_key = ?
        LIMIT 1
        """,
        (user_id, transport_origin, source_key),
    )
    return sync_fetch_one_as_dict(cursor)


def read_conversation_input_by_input_id(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    input_id: str,
) -> SQLiteRowDict | None:
    cursor = sqlite_conn.execute(
        """
        SELECT *
        FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ? AND input_id = ?
        LIMIT 1
        """,
        (conv_id, user_id, input_id),
    )
    return sync_fetch_one_as_dict(cursor)


def _build_transition_state(
    row: SQLiteRowDict,
    *,
    input_record: JSONDict,
    was_updated: bool,
) -> ConversationInputTransitionState:
    state_value = input_record.get("state")
    if not isinstance(state_value, str):
        raise StateError("Conversation input row state is invalid.")
    return ConversationInputTransitionState(
        row=row,
        input_record=input_record,
        state=state_value.strip(),
        was_updated=was_updated,
    )


def _try_build_updated_transition_state(
    updated_row: SQLiteRowDict,
) -> ConversationInputTransitionState | None:
    try:
        updated_prompt = format_conversation_input_row(updated_row)
    except StateError:
        return None
    if updated_prompt is None:
        return None
    return _build_transition_state(
        updated_row,
        input_record=updated_prompt,
        was_updated=True,
    )


def resolve_conversation_input_transition_state(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    input_id: str,
    updated_row: SQLiteRowDict | None,
) -> ConversationInputTransitionState:
    if updated_row is not None:
        updated_state = _try_build_updated_transition_state(updated_row)
        if updated_state is not None:
            return updated_state
    row = read_conversation_input_by_input_id(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        input_id=input_id,
    )
    if row is None:
        raise ValidationError("Conversation input not found.")
    input_record = format_conversation_input_row(row)
    if input_record is None:
        raise StateError("Conversation input row is missing after transition lookup.")
    return _build_transition_state(row, input_record=input_record, was_updated=False)
