"""SoAI - Conversation deletion write operations [backend/database/repositories/users/conversation_deletion_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.conversations.conversation_deletion import DeletedConversationRecord
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_all_as_dicts
from database.core.sqlite_numbers import coerce_required_nonempty_str_from_sqlite_row
from database.repositories.users.conversation_linked_knowledge_delete_refresh import (
    sync_collect_linked_knowledge_targets_for_deleted_sources,
    sync_refresh_deleted_source_linked_knowledge,
)
from database.repositories.users.conversation_quiescence import (
    CONVERSATION_SELECTION_TABLE,
    clear_conversation_selection,
    prepare_conversation_selection,
    require_selected_conversations_quiescent,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "sync_delete_all_conversations",
    "sync_delete_conversation",
    "sync_delete_conversations",
)

_CONVERSATION_ROWS_SQL = "SELECT c.id AS conv_id FROM webui_conversations AS c "

_CONVERSATION_ORDER_SQL = "ORDER BY c.last_modified_at_ms DESC, c.id DESC"


def _records_from_conversation_rows(rows: list[SQLiteRowDict]) -> list[DeletedConversationRecord]:
    return [
        DeletedConversationRecord(
            conv_id=coerce_required_nonempty_str_from_sqlite_row(row, "conv_id"),
        )
        for row in rows
    ]


def _records_with_linked_knowledge_summaries(
    records: list[DeletedConversationRecord],
    summaries_by_source: dict[str, tuple[JSONDict, ...]],
) -> list[DeletedConversationRecord]:
    return [
        DeletedConversationRecord(
            conv_id=record.conv_id,
            linked_knowledge_summaries=summaries_by_source.get(record.conv_id, ()),
        )
        for record in records
    ]


def _collect_selected_conversation_records(
    conn: sqlite3.Connection,
    user_id: int,
) -> list[DeletedConversationRecord]:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            (
                f"{_CONVERSATION_ROWS_SQL} "
                f"INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected_conversations "
                "ON selected_conversations.id = c.id "
                "WHERE c.user_id = ? "
                "ORDER BY selected_conversations.position ASC"
            ),
            (user_id,),
        ),
    )
    return _records_from_conversation_rows(rows)


def _delete_selected_conversation_inputs(
    conn: sqlite3.Connection,
    *,
    user_id: int,
) -> None:
    input_rows = conn.execute(
        (
            "SELECT inputs.id FROM webui_conversation_inputs AS inputs "
            f"INNER JOIN {CONVERSATION_SELECTION_TABLE} AS selected "
            "ON selected.id = inputs.conv_id "
            "WHERE inputs.user_id = ? ORDER BY inputs.id DESC"
        ),
        (user_id,),
    ).fetchall()
    conn.executemany(
        "DELETE FROM webui_conversation_inputs WHERE id = ?",
        input_rows,
    )


def sync_delete_conversation(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
) -> DeletedConversationRecord | None:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            (
                f"{_CONVERSATION_ROWS_SQL} "
                "WHERE c.user_id = ? AND c.id = ? "
                f"{_CONVERSATION_ORDER_SQL}"
            ),
            (user_id, conv_id),
        ),
    )
    records = _records_from_conversation_rows(rows)
    if not records:
        return None
    if len(records) != 1:
        raise StateError("Single conversation delete selected multiple conversations.")
    prepare_conversation_selection(conn, (conv_id,))
    try:
        require_selected_conversations_quiescent(conn, user_id=user_id)
        linked_target_ids_by_source = sync_collect_linked_knowledge_targets_for_deleted_sources(
            conn,
            source_conv_ids=(conv_id,),
            user_id=user_id,
        )
        _delete_selected_conversation_inputs(conn, user_id=user_id)
        deleted_count = conn.execute(
            "DELETE FROM webui_conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ).rowcount
        if deleted_count != 1:
            raise StateError(
                "Single conversation delete count did not match selected conversation."
            )
        summaries_by_source = sync_refresh_deleted_source_linked_knowledge(
            conn,
            target_ids_by_source=linked_target_ids_by_source,
            updated_at_ms=epoch_ms(),
        )
        return _records_with_linked_knowledge_summaries(records, summaries_by_source)[0]
    finally:
        clear_conversation_selection(conn)


def sync_delete_conversations(
    conn: sqlite3.Connection,
    conv_ids: tuple[str, ...],
    user_id: int,
) -> list[DeletedConversationRecord]:
    if not conv_ids:
        return []
    prepare_conversation_selection(conn, conv_ids)
    try:
        records = _collect_selected_conversation_records(conn, user_id)
        if not records:
            return []
        require_selected_conversations_quiescent(conn, user_id=user_id)
        selected_conv_ids = tuple(record.conv_id for record in records)
        linked_target_ids_by_source = sync_collect_linked_knowledge_targets_for_deleted_sources(
            conn,
            source_conv_ids=selected_conv_ids,
            user_id=user_id,
        )
        _delete_selected_conversation_inputs(conn, user_id=user_id)
        deleted_count = conn.execute(
            (
                "DELETE FROM webui_conversations "
                "WHERE user_id = ? "
                f"AND id IN (SELECT id FROM {CONVERSATION_SELECTION_TABLE})"
            ),
            (user_id,),
        ).rowcount
        if deleted_count != len(records):
            raise StateError(
                "Selected conversation delete count did not match selected conversations."
            )
        summaries_by_source = sync_refresh_deleted_source_linked_knowledge(
            conn,
            target_ids_by_source=linked_target_ids_by_source,
            updated_at_ms=epoch_ms(),
        )
        return _records_with_linked_knowledge_summaries(records, summaries_by_source)
    finally:
        clear_conversation_selection(conn)


def sync_delete_all_conversations(
    conn: sqlite3.Connection,
    user_id: int,
) -> list[DeletedConversationRecord]:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            (f"{_CONVERSATION_ROWS_SQL} " "WHERE c.user_id = ? " f"{_CONVERSATION_ORDER_SQL}"),
            (user_id,),
        ),
    )
    records = _records_from_conversation_rows(rows)
    if not records:
        return []
    conv_ids = tuple(record.conv_id for record in records)
    prepare_conversation_selection(conn, conv_ids)
    try:
        require_selected_conversations_quiescent(conn, user_id=user_id)
        linked_target_ids_by_source = sync_collect_linked_knowledge_targets_for_deleted_sources(
            conn,
            source_conv_ids=conv_ids,
            user_id=user_id,
        )
        _delete_selected_conversation_inputs(conn, user_id=user_id)
        deleted_count = conn.execute(
            "DELETE FROM webui_conversations WHERE user_id = ?",
            (user_id,),
        ).rowcount
        if deleted_count != len(records):
            raise StateError("Bulk conversation delete count did not match selected conversations.")
        summaries_by_source = sync_refresh_deleted_source_linked_knowledge(
            conn,
            target_ids_by_source=linked_target_ids_by_source,
            updated_at_ms=epoch_ms(),
        )
        return _records_with_linked_knowledge_summaries(records, summaries_by_source)
    finally:
        clear_conversation_selection(conn)
