"""SoAI - Conversation regeneration receipt queries [backend/database/repositories/users/conversation_input_regeneration_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_one_to_dict
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

__all__ = ("query_conversation_regeneration_attempt",)


async def query_conversation_regeneration_attempt(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    client_id: str | None,
    client_request_id: str | None,
) -> JSONDict | None:
    identity_sql = ""
    params: tuple[int | str, ...] = (conv_id, user_id)
    if client_id is not None and client_request_id is not None:
        identity_sql = " AND input.client_id = ? AND input.client_request_id = ?"
        params = (*params, client_id, client_request_id)
    row = await query_one_to_dict(
        database,
        f"""
        WITH ranked_inputs AS (
            SELECT *, {CONVERSATION_INPUT_DISPATCH_RANK_SQL} AS dispatch_rank
            FROM webui_conversation_inputs
        )
        SELECT input.*,
               CASE WHEN input.state IN ('pending', 'materializing', 'running', 'input_required')
                          AND input.conversation_generation = conversation.input_generation
                          AND {CONVERSATION_INPUT_RUNNING_ROOT_AVAILABLE_SQL}
                          AND NOT EXISTS (
                              SELECT 1 FROM ranked_inputs AS earlier
                              WHERE earlier.conv_id = input.conv_id
                                AND earlier.state IN (
                                    'pending', 'materializing', 'running', 'input_required'
                                )
                                AND ({CONVERSATION_INPUT_PRECEDES_SQL})
                          )
                    THEN 1 ELSE 0 END AS regeneration_is_dispatchable_head,
               EXISTS (
                   SELECT 1 FROM webui_messages AS replacement
                   WHERE replacement.conv_id = input.conv_id
                     AND replacement.role = 'assistant'
                     AND (
                         replacement.request_id = input.request_id
                         OR replacement.request_id GLOB input.request_id || ':variant:[0-9]*'
                     )
               ) AS regeneration_has_assistant_replacement
        FROM ranked_inputs AS input
        JOIN webui_conversations AS conversation
          ON conversation.id = input.conv_id AND conversation.user_id = input.user_id
        WHERE input.conv_id = ? AND input.user_id = ?
          AND input.regeneration_request_json IS NOT NULL
          {identity_sql}
        ORDER BY input.id DESC
        LIMIT 1
        """,
        params,
    )
    if row is None:
        return None
    formatted = format_conversation_input_row(row)
    if formatted is None:
        return None
    formatted["is_dispatchable_head"] = row.get("regeneration_is_dispatchable_head") == 1
    formatted["has_assistant_replacement"] = row.get("regeneration_has_assistant_replacement") == 1
    return formatted
