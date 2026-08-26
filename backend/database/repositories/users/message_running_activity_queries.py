"""SoAI - Running activity snapshots for conversations [backend/database/repositories/users/message_running_activity_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.conversations.conversation_message_window import (
    ConversationRunningActivitySnapshot,
)
from core.types.json import JSONDict
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_values import SQLiteValue
from database.repositories.users.message_row_mapping import (
    build_message_payload_from_row,
)
from database.repositories.users.message_window_assistant_details import (
    attach_window_assistant_details,
)
from database.repositories.users.message_window_row_selection import (
    MESSAGE_WINDOW_SELECT_COLUMNS,
)
from database.repositories.users.read_transactions import run_user_read_transaction

__all__ = ("load_conversation_running_activity_snapshot",)


def _running_turn_identity(row: dict[str, SQLiteValue]) -> tuple[int, int] | None:
    assistant_turn_at_ms = row.get("assistant_turn_at_ms")
    model_variant_index = row.get("model_variant_index")
    if not is_strict_int(assistant_turn_at_ms) or assistant_turn_at_ms < 0:
        return None
    if not is_strict_int(model_variant_index) or model_variant_index < 0:
        return None
    return (int(assistant_turn_at_ms), int(model_variant_index))


async def _load_running_turn_identities(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
) -> set[tuple[int, int]]:
    query = " ".join(
        (
            "SELECT DISTINCT assistant_turn_at_ms, model_variant_index",
            "FROM webui_chat_tool_calls",
            "WHERE conv_id = ? AND status IN ('pending', 'running')",
        )
    )
    rows = await query_to_dicts(
        database,
        query,
        (conv_id,),
    )
    identities: set[tuple[int, int]] = set()
    for row in rows:
        identity = _running_turn_identity(row)
        if identity is not None:
            identities.add(identity)
    return identities


async def _load_running_messages(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    identities: set[tuple[int, int]],
) -> list[JSONDict]:
    if not identities:
        return []
    assistant_turns = sorted({turn for turn, _ in identities})
    selected_rows: list[dict[str, SQLiteValue]] = []
    for start_index in range(0, len(assistant_turns), SQLITE_BATCH_SIZE):
        batch = assistant_turns[start_index : start_index + SQLITE_BATCH_SIZE]
        placeholders = ",".join("?" for _ in batch)
        query = " ".join(
            (
                f"SELECT {MESSAGE_WINDOW_SELECT_COLUMNS} FROM webui_messages",
                f"WHERE conv_id = ? AND role = 'assistant' AND assistant_turn_at_ms IN ({placeholders})",
                "ORDER BY created_at_ms ASC, id ASC",
            )
        )
        rows = await query_to_dicts(
            database,
            query,
            (conv_id, *batch),
        )
        for row in rows:
            identity = _running_turn_identity(row)
            if identity is not None and identity in identities:
                selected_rows.append(row)
    messages = [build_message_payload_from_row(row) for row in selected_rows]
    await attach_window_assistant_details(database, conv_id=conv_id, messages=messages)
    return messages


async def _load_running_activity_snapshot_transaction(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> ConversationRunningActivitySnapshot | None:
    conversation_row = await query_one_to_dict(
        database,
        "SELECT last_modified_at_ms FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    if conversation_row is None:
        return None
    last_modified_at_ms = require_unix_epoch_ms(
        conversation_row.get("last_modified_at_ms"),
        error_message="Conversation last_modified_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    identities = await _load_running_turn_identities(database, conv_id=conv_id)
    running_messages = await _load_running_messages(
        database,
        conv_id=conv_id,
        identities=identities,
    )
    return ConversationRunningActivitySnapshot(
        conv_id=conv_id,
        running_messages=running_messages,
        last_modified_at_ms=last_modified_at_ms,
    )


async def load_conversation_running_activity_snapshot(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> ConversationRunningActivitySnapshot | None:
    async def _transaction(
        transaction_database: aiosqlite.Connection,
    ) -> ConversationRunningActivitySnapshot | None:
        return await _load_running_activity_snapshot_transaction(
            transaction_database,
            conv_id=conv_id,
            user_id=user_id,
        )

    return await run_user_read_transaction(database, _transaction)
