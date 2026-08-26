"""SoAI - Logical conversation message window candidate queries [backend/database/repositories/users/message_window_candidate_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.requirements import require_non_negative_int
from database.core.query_execution import query_to_dicts
from database.core.sqlite_values import SQLiteValue

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import (
        ConversationMessageWindowDirection,
    )

__all__ = (
    "LogicalMessageIdentity",
    "MESSAGE_WINDOW_IDENTITY_COLUMNS",
    "MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE",
    "identities_from_rows",
    "load_linear_message_window_candidates",
    "require_message_window_cursor",
    "trim_split_pair_boundary",
)

MESSAGE_WINDOW_IDENTITY_COLUMNS = "m.id, m.role, m.created_at_ms, m.assistant_turn_at_ms"
MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE = """
    (
        m.role != 'assistant'
        OR m.model_variant_index = 0
    )
"""


@dataclass(frozen=True, slots=True)
class LogicalMessageIdentity:
    message_id: int
    role: str
    created_at_ms: int
    assistant_turn_at_ms: int | None


def _identity_from_row(row: dict[str, SQLiteValue]) -> LogicalMessageIdentity:
    role_value = row.get("role")
    if not isinstance(role_value, str) or not role_value:
        raise ValidationError("Conversation message role must be a non-empty string.")
    assistant_turn_value = row.get("assistant_turn_at_ms")
    assistant_turn_at_ms = (
        None
        if assistant_turn_value is None
        else require_non_negative_int(
            assistant_turn_value,
            error_message="Conversation assistant_turn_at_ms must be a non-negative integer.",
        )
    )
    return LogicalMessageIdentity(
        message_id=require_non_negative_int(
            row.get("id"),
            error_message="Conversation message id must be a non-negative integer.",
        ),
        role=role_value,
        created_at_ms=require_unix_epoch_ms(
            row.get("created_at_ms"),
            error_message="Conversation message created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        ),
        assistant_turn_at_ms=assistant_turn_at_ms,
    )


def identities_from_rows(
    rows: list[dict[str, SQLiteValue]],
) -> list[LogicalMessageIdentity]:
    identities = [_identity_from_row(row) for row in rows]
    return sorted(
        identities,
        key=lambda identity: (identity.created_at_ms, identity.message_id),
    )


def trim_split_pair_boundary(
    identities: list[LogicalMessageIdentity],
    *,
    trim_older_boundary: bool,
    trim_newer_boundary: bool,
) -> list[LogicalMessageIdentity]:
    start_index = (
        1 if trim_older_boundary and identities and identities[0].role == "assistant" else 0
    )
    end_index = (
        len(identities) - 1
        if trim_newer_boundary and identities and identities[-1].role == "user"
        else len(identities)
    )
    return identities[start_index:end_index]


def require_message_window_cursor(
    created_at_ms: int | None,
    cursor_id: int | None,
    label: str,
) -> tuple[int, int]:
    if created_at_ms is None or cursor_id is None:
        raise ValidationError(f"{label} cursor requires cursor_created_at_ms and cursor_id.")
    validated_created_at_ms = require_unix_epoch_ms(
        created_at_ms,
        error_message=f"{label} cursor_created_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    validated_cursor_id = require_non_negative_int(
        cursor_id,
        error_message=f"{label} cursor_id must be a non-negative integer.",
    )
    return (validated_created_at_ms, validated_cursor_id)


async def load_linear_message_window_candidates(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    direction: ConversationMessageWindowDirection,
    candidate_limit: int,
    cursor_created_at_ms: int | None,
    cursor_id: int | None,
) -> list[LogicalMessageIdentity]:
    where_cursor = ""
    params: list[SQLiteValue] = [conv_id]
    order = "DESC"
    if direction == "before":
        cursor_at_ms, cursor_message_id = require_message_window_cursor(
            cursor_created_at_ms,
            cursor_id,
            "before",
        )
        where_cursor = "AND (m.created_at_ms < ? OR (m.created_at_ms = ? AND m.id < ?))"
        params.extend((cursor_at_ms, cursor_at_ms, cursor_message_id))
    elif direction == "after":
        cursor_at_ms, cursor_message_id = require_message_window_cursor(
            cursor_created_at_ms,
            cursor_id,
            "after",
        )
        where_cursor = "AND (m.created_at_ms > ? OR (m.created_at_ms = ? AND m.id > ?))"
        params.extend((cursor_at_ms, cursor_at_ms, cursor_message_id))
        order = "ASC"
    params.append(candidate_limit)
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {MESSAGE_WINDOW_IDENTITY_COLUMNS}
        FROM webui_messages AS m
        WHERE m.conv_id = ?
          AND {MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE}
          {where_cursor}
        ORDER BY m.created_at_ms {order}, m.id {order}
        LIMIT ?
        """,
        tuple(params),
    )
    identities = identities_from_rows(rows)
    candidate_boundary_reached = len(identities) == candidate_limit
    return trim_split_pair_boundary(
        identities,
        trim_older_boundary=(candidate_boundary_reached and direction in ("tail", "before")),
        trim_newer_boundary=candidate_boundary_reached and direction == "after",
    )
