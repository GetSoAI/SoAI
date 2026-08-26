"""SoAI - Linked knowledge refresh for conversation deletion [backend/database/repositories/users/conversation_linked_knowledge_delete_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.core.query_execution import sync_fetch_all_as_dicts
from database.core.sqlite_numbers import coerce_required_nonempty_str_from_sqlite_row
from database.repositories.users.conversation_linked_knowledge_activation import (
    sync_refresh_linked_knowledge_availability,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_collect_linked_knowledge_targets_for_deleted_sources",
    "sync_refresh_deleted_source_linked_knowledge",
)

DELETED_SOURCES_TABLE = "temp_conversation_linked_knowledge_deleted_sources"


def _prepare_deleted_sources_table(
    conn: sqlite3.Connection,
    source_conv_ids: tuple[str, ...],
) -> None:
    conn.execute(
        f"CREATE TEMP TABLE IF NOT EXISTS {DELETED_SOURCES_TABLE} (id TEXT PRIMARY KEY) WITHOUT ROWID",
    )
    conn.execute(f"DELETE FROM {DELETED_SOURCES_TABLE}")
    conn.executemany(
        f"INSERT OR IGNORE INTO {DELETED_SOURCES_TABLE} (id) VALUES (?)",
        ((source_conv_id,) for source_conv_id in source_conv_ids),
    )


def sync_collect_linked_knowledge_targets_for_deleted_sources(
    conn: sqlite3.Connection,
    *,
    source_conv_ids: tuple[str, ...],
    user_id: int,
) -> dict[str, tuple[str, ...]]:
    if not source_conv_ids:
        return {}
    _prepare_deleted_sources_table(conn, source_conv_ids)
    try:
        rows = sync_fetch_all_as_dicts(
            conn.execute(
                f"""
                SELECT DISTINCT source_conv_id, target_knowledge_attachment_id
                FROM rag_linked_documents AS linked
                INNER JOIN {DELETED_SOURCES_TABLE} AS deleted_sources
                  ON deleted_sources.id = linked.source_conv_id
                WHERE linked.source_user_id = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {DELETED_SOURCES_TABLE} AS deleted_targets
                      WHERE deleted_targets.id = linked.target_conv_id
                  )
                ORDER BY source_conv_id ASC, target_knowledge_attachment_id ASC
                """,
                (user_id,),
            ),
        )
    finally:
        conn.execute(f"DELETE FROM {DELETED_SOURCES_TABLE}")
    targets_by_source: dict[str, list[str]] = {}
    for row in rows:
        source_conv_id = coerce_required_nonempty_str_from_sqlite_row(row, "source_conv_id")
        target_id = coerce_required_nonempty_str_from_sqlite_row(
            row,
            "target_knowledge_attachment_id",
        )
        if source_conv_id not in targets_by_source:
            targets_by_source[source_conv_id] = []
        targets = targets_by_source[source_conv_id]
        targets.append(target_id)
    return {source_conv_id: tuple(targets) for source_conv_id, targets in targets_by_source.items()}


def sync_refresh_deleted_source_linked_knowledge(
    conn: sqlite3.Connection,
    *,
    target_ids_by_source: dict[str, tuple[str, ...]],
    updated_at_ms: int,
) -> dict[str, tuple[JSONDict, ...]]:
    summaries_by_target_id: dict[str, JSONDict] = {}
    summaries_by_source: dict[str, list[JSONDict]] = {}
    for source_conv_id, target_ids in target_ids_by_source.items():
        if source_conv_id not in summaries_by_source:
            summaries_by_source[source_conv_id] = []
        source_summaries = summaries_by_source[source_conv_id]
        for target_id in target_ids:
            summary = summaries_by_target_id.get(target_id)
            if summary is None:
                summary = sync_refresh_linked_knowledge_availability(
                    conn,
                    target_knowledge_attachment_id=target_id,
                    updated_at_ms=updated_at_ms,
                )
                if summary is None:
                    continue
                summaries_by_target_id[target_id] = summary
            source_summaries.append(summary)
    return {
        source_conv_id: tuple(summaries)
        for source_conv_id, summaries in summaries_by_source.items()
    }
