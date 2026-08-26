"""SoAI - Cursor-window conversation message row selection [backend/database/repositories/users/message_window_row_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.validation.requirements import require_non_negative_int
from core.validation.strict_numbers import require_int_in_range_strict
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_to_dicts
from database.core.sqlite_values import SQLiteValue
from database.repositories.users.message_window_budget_selection import (
    MessageWindowIdentitySelection,
    select_message_window_identities,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import (
        ConversationMessageWindowDirection,
    )

__all__ = (
    "MESSAGE_WINDOW_SELECT_COLUMNS",
    "load_window_message_rows",
)

MESSAGE_WINDOW_SELECT_COLUMNS = (
    "id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, "
    "request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, "
    "generation_latency_ms, finish_reason, thinking_tail_duration_ms, "
    "(SELECT input_id FROM webui_conversation_inputs "
    "WHERE materialized_message_id = webui_messages.id) AS conversation_input_id, "
    "(SELECT CASE WHEN transport_origin = 'messaging' "
    "THEN json_extract(source_metadata_json, '$.sender_display_name') END "
    "FROM webui_conversation_inputs "
    "WHERE materialized_message_id = webui_messages.id) AS messaging_sender_display_name, "
    "(SELECT CASE WHEN transport_origin = 'messaging' "
    "THEN json_extract(source_metadata_json, '$.sender_id') END "
    "FROM webui_conversation_inputs "
    "WHERE materialized_message_id = webui_messages.id) AS messaging_sender_id"
)


def _require_limit(limit: int) -> int:
    return require_int_in_range_strict(
        limit,
        minimum=1,
        maximum=1000,
        error_message="limit must be between 1 and 1000.",
    )


async def _load_selected_rows(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    selection: MessageWindowIdentitySelection,
) -> list[dict[str, SQLiteValue]]:
    rows: list[dict[str, SQLiteValue]] = []
    message_index = 0
    turn_index = 0
    while message_index < len(selection.non_assistant_message_ids) or turn_index < len(
        selection.assistant_turn_at_ms_values
    ):
        message_batch = selection.non_assistant_message_ids[
            message_index : message_index + SQLITE_BATCH_SIZE
        ]
        remaining_batch_size = SQLITE_BATCH_SIZE - len(message_batch)
        turn_batch = selection.assistant_turn_at_ms_values[
            turn_index : turn_index + remaining_batch_size
        ]
        predicates: list[str] = []
        if message_batch:
            message_placeholders = ",".join("?" for _ in message_batch)
            predicates.append(f"id IN ({message_placeholders})")
        if turn_batch:
            turn_placeholders = ",".join("?" for _ in turn_batch)
            predicates.append(
                f"(role = 'assistant' AND assistant_turn_at_ms IN ({turn_placeholders}))"
            )
        rows.extend(
            await query_to_dicts(
                database,
                f"""
                SELECT {MESSAGE_WINDOW_SELECT_COLUMNS}
                FROM webui_messages
                WHERE conv_id = ? AND ({" OR ".join(predicates)})
                ORDER BY created_at_ms ASC, id ASC
                """,
                (conv_id, *message_batch, *turn_batch),
            ),
        )
        message_index += len(message_batch)
        turn_index += len(turn_batch)
    rows.sort(
        key=lambda row: (
            require_non_negative_int(
                row.get("created_at_ms"),
                error_message="Conversation message timestamp must be a non-negative integer.",
            ),
            require_non_negative_int(
                row.get("id"),
                error_message="Conversation message id must be a non-negative integer.",
            ),
        ),
    )
    return rows


async def load_window_message_rows(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    direction: ConversationMessageWindowDirection,
    limit: int,
    cursor_created_at_ms: int | None,
    cursor_id: int | None,
    anchor_created_at_ms: int | None,
    anchor_id: int | None,
) -> list[dict[str, SQLiteValue]]:
    validated_limit = _require_limit(limit)
    selection = await select_message_window_identities(
        database,
        conv_id=conv_id,
        direction=direction,
        limit=validated_limit,
        cursor_created_at_ms=cursor_created_at_ms,
        cursor_id=cursor_id,
        anchor_created_at_ms=anchor_created_at_ms,
        anchor_id=anchor_id,
    )
    return await _load_selected_rows(
        database,
        conv_id=conv_id,
        selection=selection,
    )
