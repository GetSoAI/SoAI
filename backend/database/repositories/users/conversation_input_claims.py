"""SoAI - Conversation input head claiming [backend/database/repositories/users/conversation_input_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_input_constants import (
    CONVERSATION_INPUT_DISPATCH_RANK_SQL,
    CONVERSATION_INPUT_PRECEDES_SQL,
    CONVERSATION_INPUT_RUNNING_ROOT_AVAILABLE_SQL,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "attach_conversation_input_dispatch_state",
    "read_dispatchable_conversation_input_head",
    "sync_claim_next_conversation_input",
)


def attach_conversation_input_dispatch_state(
    sqlite_conn: sqlite3.Connection,
    input_record: JSONDict,
) -> JSONDict:
    input_id = input_record.get("input_id")
    if not isinstance(input_id, str) or not input_id.strip():
        raise StateError("Conversation input is missing its identity.")
    input_record["is_dispatchable_head"] = (
        read_dispatchable_conversation_input_head(sqlite_conn, input_id) is not None
    )
    return input_record


def read_dispatchable_conversation_input_head(
    sqlite_conn: sqlite3.Connection,
    input_id: str | None = None,
    excluded_conversation_ids: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    exclusion_sql = ""
    exclusion_params: tuple[str, ...] = ()
    if excluded_conversation_ids:
        placeholders = ", ".join("?" for _ in excluded_conversation_ids)
        exclusion_sql = f" AND input.conv_id NOT IN ({placeholders})"
        exclusion_params = excluded_conversation_ids
    row = sqlite_conn.execute(
        f"""
        WITH ranked_inputs AS (
            SELECT *, {CONVERSATION_INPUT_DISPATCH_RANK_SQL} AS dispatch_rank
            FROM webui_conversation_inputs
        )
        SELECT input.input_id, input.state
        FROM ranked_inputs AS input
        JOIN webui_conversations AS conversation
          ON conversation.id = input.conv_id
         AND conversation.user_id = input.user_id
         AND conversation.input_generation = input.conversation_generation
        WHERE input.state = 'pending'
          AND (? IS NULL OR input.input_id = ?)
          {exclusion_sql}
          AND input.input_type IN ('prompt', 'steer')
          AND {CONVERSATION_INPUT_RUNNING_ROOT_AVAILABLE_SQL}
          AND NOT EXISTS (
              SELECT 1
              FROM ranked_inputs AS earlier
              WHERE earlier.conv_id = input.conv_id
                AND (
                    earlier.state IN ('materializing', 'running', 'input_required')
                    OR (
                        earlier.state = 'pending'
                        AND ({CONVERSATION_INPUT_PRECEDES_SQL})
                    )
                )
          )
        ORDER BY input.dispatch_rank ASC, input.accepted_at_ms ASC, input.id ASC
        LIMIT 1
        """,
        (input_id, input_id, *exclusion_params),
    ).fetchone()
    if row is None:
        return None
    input_id, state = row
    if not isinstance(input_id, str) or state != "pending":
        raise StateError("Dispatchable conversation input row is invalid.")
    return (input_id, state)


def sync_claim_next_conversation_input(
    sqlite_conn: sqlite3.Connection,
    claim_owner: str,
    server_boot_id: str,
    claimed_at_ms: int,
    excluded_conversation_ids: tuple[str, ...] = (),
) -> JSONDict | None:
    input_head = read_dispatchable_conversation_input_head(
        sqlite_conn,
        excluded_conversation_ids=excluded_conversation_ids,
    )
    if input_head is None:
        return None
    input_id, _state = input_head
    cursor = sqlite_conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = CASE
                WHEN materialized_message_id IS NULL THEN 'materializing'
                ELSE 'running'
            END,
            claim_owner = ?, claim_server_boot_id = ?,
            claim_generation = claim_generation + 1,
            claimed_at_ms = ?,
            running_at_ms = CASE
                WHEN materialized_message_id IS NULL THEN running_at_ms
                ELSE ?
            END,
            updated_at_ms = ?
        WHERE input_id = ? AND state = 'pending'
          AND conversation_generation = (
              SELECT input_generation
              FROM webui_conversations
              WHERE id = webui_conversation_inputs.conv_id
                AND user_id = webui_conversation_inputs.user_id
          )
        RETURNING *
        """,
        (
            claim_owner,
            server_boot_id,
            claimed_at_ms,
            claimed_at_ms,
            claimed_at_ms,
            input_id,
        ),
    )
    updated = sync_fetch_one_as_dict(cursor)
    if updated is None:
        return None
    formatted = format_conversation_input_row(updated)
    if formatted is None:
        raise StateError("Claimed conversation input is missing.")
    return formatted
