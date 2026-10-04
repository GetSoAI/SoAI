"""SoAI - Conversation regeneration persisted target resolution [backend/database/repositories/users/conversation_regeneration_targets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from database.repositories.users.conversation_input_constants import (
    CONVERSATION_REGENERATION_HAS_REPLACEMENT_SQL,
    CONVERSATION_REGENERATION_SOURCE_EXISTS_SQL,
    CONVERSATION_REGENERATION_SOURCE_FOLLOWED_SQL,
    CONVERSATION_REGENERATION_SUPERSEDED_SQL,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "resolve_regeneration_cursor_source",
    "resolve_regeneration_retry_source",
    "sync_next_regeneration_assistant_timestamp",
)


def resolve_regeneration_cursor_source(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    command: JSONDict,
) -> tuple[int, int, int]:
    target = command.get("target")
    if not isinstance(target, dict):
        raise ValidationError("Conversation regeneration target is invalid.")
    created_at_ms = target.get("created_at_ms")
    message_id = target.get("message_id")
    if not is_strict_int(created_at_ms) or not is_strict_int(message_id):
        raise ValidationError("Conversation regeneration target cursor is invalid.")
    row = conn.execute(
        """
        SELECT assistant_turn_at_ms, message_type
        FROM webui_messages
        WHERE conv_id = ? AND id = ? AND created_at_ms = ? AND role = 'assistant'
        """,
        (conv_id, int(message_id), int(created_at_ms)),
    ).fetchone()
    if row is None or row[1] != "chat" or not is_strict_int(row[0]):
        raise ValidationError("Conversation regeneration target assistant was not found.")
    turn_at_ms = int(row[0])
    protected_sibling = conn.execute(
        """
        SELECT 1 FROM webui_messages
        WHERE conv_id = ? AND assistant_turn_at_ms = ? AND message_type != 'chat'
        LIMIT 1
        """,
        (conv_id, turn_at_ms),
    ).fetchone()
    if protected_sibling is not None:
        raise ValidationError("Conversation regeneration target includes a protected control row.")
    boundary = conn.execute(
        """
        SELECT created_at_ms, id FROM webui_messages
        WHERE conv_id = ? AND role = 'assistant' AND assistant_turn_at_ms = ?
        ORDER BY created_at_ms ASC, id ASC LIMIT 1
        """,
        (conv_id, turn_at_ms),
    ).fetchone()
    if boundary is None:
        raise StateError("Conversation regeneration turn boundary is missing.")
    source = conn.execute(
        """
        SELECT id FROM webui_messages
        WHERE conv_id = ? AND role = 'user' AND message_type = 'chat'
          AND (created_at_ms < ? OR (created_at_ms = ? AND id < ?))
        ORDER BY created_at_ms DESC, id DESC LIMIT 1
        """,
        (conv_id, int(boundary[0]), int(boundary[0]), int(boundary[1])),
    ).fetchone()
    if source is None or not is_strict_int(source[0]):
        raise ValidationError("Conversation regeneration source user message was not found.")
    return int(source[0]), int(boundary[0]), int(boundary[1])


def resolve_regeneration_retry_source(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    command: JSONDict,
) -> tuple[int, None, None]:
    retry_input_id = command.get("retry_input_id")
    if not isinstance(retry_input_id, str) or not retry_input_id.strip():
        raise ValidationError("Conversation regeneration retry identity is invalid.")
    prior = conn.execute(
        f"""
        SELECT input.state, input.request_id, input.materialized_message_id,
               {CONVERSATION_REGENERATION_HAS_REPLACEMENT_SQL} AS has_replacement,
               {CONVERSATION_REGENERATION_SUPERSEDED_SQL} AS superseded,
               {CONVERSATION_REGENERATION_SOURCE_EXISTS_SQL} AS source_exists,
               {CONVERSATION_REGENERATION_SOURCE_FOLLOWED_SQL} AS source_followed
        FROM webui_conversation_inputs AS input
        WHERE input.input_id = ? AND input.conv_id = ? AND input.user_id = ?
          AND input.regeneration_request_json IS NOT NULL
        LIMIT 1
        """,
        (retry_input_id.strip(), conv_id, user_id),
    ).fetchone()
    if (
        prior is None
        or prior[0] not in {"failed", "cancelled"}
        or not isinstance(prior[1], str)
        or not prior[1]
        or not is_strict_int(prior[2])
    ):
        raise ValidationError("Conversation regeneration retry target is not eligible.")
    if prior[3] == 1:
        raise ConflictError("Conversation regeneration retry already has an assistant replacement.")
    if prior[4] == 1:
        raise ConflictError("Conversation regeneration retry target was superseded.")
    if prior[5] != 1:
        raise ConflictError("Conversation regeneration source boundary no longer exists.")
    if prior[6] == 1:
        raise ConflictError("Conversation regeneration retry source was superseded.")
    return int(prior[2]), None, None


def sync_next_regeneration_assistant_timestamp(
    conn: sqlite3.Connection,
    conv_id: str,
) -> int:
    row = conn.execute(
        """
        SELECT MAX(value) FROM (
            SELECT MAX(created_at_ms) AS value FROM webui_messages WHERE conv_id = ?
            UNION ALL
            SELECT MAX(
                assistant_at_ms
                + MAX(1, COALESCE(json_array_length(model_settings_json, '$.comparison_models'), 0))
            )
            FROM webui_conversation_inputs
            WHERE conv_id = ? AND assistant_at_ms IS NOT NULL
        )
        """,
        (conv_id, conv_id),
    ).fetchone()
    latest = int(row[0]) if row is not None and is_strict_int(row[0]) else 0
    return max(epoch_ms(), latest + 1)
