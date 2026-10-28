"""SoAI - Conversation input read queries [backend/database/repositories/users/conversation_input_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ConflictError, StateError
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_input_constants import (
    CONVERSATION_INPUT_ACTIVE_ORDER_SQL,
    build_conversation_input_dispatch_rank_sql,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)

if TYPE_CHECKING:
    from core.conversations.input_claim import ConversationInputClaim
    from core.types.json import JSONDict

__all__ = (
    "CONVERSATION_INPUT_ACTIVE_CLAIM_SQL",
    "has_pending_input_type",
    "query_active_inputs",
    "query_conversation_input_variant_outcomes",
    "query_running_chat_inputs_for_client",
    "require_conversation_input_claim",
    "sync_require_conversation_input_claim",
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
            SELECT *, {build_conversation_input_dispatch_rank_sql()} AS dispatch_rank
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
        CONVERSATION_INPUT_ACTIVE_CLAIM_SQL,
        (input_id, claim_generation, claim_owner, server_boot_id),
    )
    if row is None:
        raise ConflictError("Conversation input mutation fence changed.")


CONVERSATION_INPUT_ACTIVE_CLAIM_SQL = """
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
        """


def sync_require_conversation_input_claim(
    connection: sqlite3.Connection, claim: ConversationInputClaim
) -> None:
    row = connection.execute(
        CONVERSATION_INPUT_ACTIVE_CLAIM_SQL,
        (claim.input_id, claim.generation, claim.owner, claim.server_boot_id),
    ).fetchone()
    if row is None:
        raise ConflictError("Conversation input mutation fence changed.")
