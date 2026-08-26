"""SoAI - Conversation input read queries [backend/database/repositories/users/conversation_input_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.types.json import is_json_dict
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_input_constants import (
    CONVERSATION_INPUT_ACTIVE_ORDER_SQL,
    CONVERSATION_INPUT_DISPATCH_RANK_SQL,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "has_pending_input_type",
    "query_active_inputs",
    "query_conversation_input_execution_settings",
    "query_conversation_input_variant_outcomes",
    "query_running_chat_inputs_for_client",
    "require_conversation_input_claim",
)


async def query_running_chat_inputs_for_client(
    database: aiosqlite.Connection,
    user_id: int,
    client_id: str,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """
        SELECT *
        FROM webui_conversation_inputs
        WHERE user_id = ? AND transport_origin = 'chat' AND client_id = ?
          AND state = 'running'
        ORDER BY running_at_ms ASC, id ASC
        """,
        (user_id, client_id),
    )
    formatted: list[JSONDict] = []
    for row in rows:
        item = format_conversation_input_row(row)
        if item is not None:
            formatted.append(item)
    return formatted


async def has_pending_input_type(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    input_type: str,
) -> bool:
    row = await query_one_to_dict(
        database,
        """
        SELECT 1 FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ? AND input_type = ?
          AND state = 'pending'
        LIMIT 1
        """,
        (conv_id, user_id, input_type),
    )
    return row is not None


async def query_active_inputs(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"""
        WITH ranked_inputs AS (
            SELECT *, {CONVERSATION_INPUT_DISPATCH_RANK_SQL} AS dispatch_rank
            FROM webui_conversation_inputs
        )
        SELECT * FROM ranked_inputs
        WHERE conv_id = ? AND user_id = ?
          AND state IN ('pending', 'materializing', 'running', 'input_required')
        ORDER BY {CONVERSATION_INPUT_ACTIVE_ORDER_SQL}
        """,
        (conv_id, user_id),
    )
    formatted: list[JSONDict] = []
    for row in rows:
        item = format_conversation_input_row(row)
        if item is not None:
            formatted.append(item)
    return formatted


async def query_conversation_input_execution_settings(
    database: aiosqlite.Connection,
    input_id: str,
) -> JSONDict:
    row = await query_one_to_dict(
        database,
        """
        SELECT COALESCE(input.model_settings_json, target.model_settings_json)
                   AS model_settings_json
        FROM webui_conversation_inputs AS input
        LEFT JOIN webui_conversation_inputs AS target
          ON target.input_id = input.target_input_id
        WHERE input.input_id = ? AND input.input_type IN ('prompt', 'steer')
        LIMIT 1
        """,
        (input_id,),
    )
    if row is None:
        raise StateError("Conversation input execution settings are unavailable.")
    serialized = row.get("model_settings_json")
    if not isinstance(serialized, str) or not serialized:
        raise StateError("Conversation input execution settings are missing.")
    try:
        decoded = safe_json_deserialize(serialized)
    except ValidationError as exception:
        raise StateError("Conversation input execution settings are invalid.") from exception
    if not is_json_dict(decoded):
        raise StateError("Conversation input execution settings must be an object.")
    return decoded


async def query_conversation_input_variant_outcomes(
    database: aiosqlite.Connection,
    input_id: str,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """
        SELECT message.request_id, message.finalized_at_ms, message.finish_reason
        FROM webui_conversation_inputs AS input
        JOIN webui_messages AS message
          ON message.conv_id = input.conv_id
         AND message.role = 'assistant'
         AND (
             message.request_id = input.request_id
             OR message.request_id GLOB input.request_id || ':variant:[0-9]*'
         )
        WHERE input.input_id = ?
        ORDER BY message.model_variant_index ASC, message.id ASC
        """,
        (input_id,),
    )
    outcomes: list[JSONDict] = []
    for row in rows:
        request_id = row.get("request_id")
        finalized_at_ms = row.get("finalized_at_ms")
        finish_reason = row.get("finish_reason")
        if not isinstance(request_id, str) or not request_id:
            raise StateError("Conversation input variant request id is invalid.")
        if finalized_at_ms is not None and (
            not isinstance(finalized_at_ms, int) or isinstance(finalized_at_ms, bool)
        ):
            raise StateError("Conversation input variant finalization is invalid.")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise StateError("Conversation input variant finish reason is invalid.")
        outcomes.append(
            {
                "request_id": request_id,
                "finalized_at_ms": finalized_at_ms,
                "finish_reason": finish_reason,
            },
        )
    return outcomes


async def require_conversation_input_claim(
    database: aiosqlite.Connection,
    input_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
) -> None:
    row = await query_one_to_dict(
        database,
        """
        SELECT 1
        FROM webui_conversation_inputs AS input
        JOIN webui_conversations AS conversation
          ON conversation.id = input.conv_id
         AND conversation.user_id = input.user_id
         AND conversation.input_generation = input.conversation_generation
        WHERE input.input_id = ?
          AND input.state IN ('materializing', 'running', 'input_required')
          AND input.claim_generation = ?
          AND input.claim_owner = ?
          AND input.claim_server_boot_id = ?
        LIMIT 1
        """,
        (input_id, claim_generation, claim_owner, server_boot_id),
    )
    if row is None:
        raise ConflictError("Conversation input mutation fence changed.")
