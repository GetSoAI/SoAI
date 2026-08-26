"""SoAI - Memory repository baseline write query helpers [backend/database/repositories/memory/write_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)

__all__ = ("sync_replace_entity_observations_for_source",)


def sync_replace_entity_observations_for_source(
    conn: sqlite3.Connection,
    user_id: int,
    entity_name: str,
    source: str,
    contents: list[str],
    entity_type: str | None,
    delete_entity_if_empty: bool,
) -> None:
    now = epoch_ms()
    entity_row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
            (user_id, entity_name),
        ),
    )
    if entity_row is None:
        if not contents or not entity_type:
            return
        conn.execute(
            "INSERT INTO mcp_memory_entities (id, user_id, name, entity_type, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, user_id, entity_name, entity_type, now, now),
        )
        entity_row = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
                (user_id, entity_name),
            ),
        )
        if entity_row is None:
            return
    entity_id = coerce_required_nonempty_str_from_sqlite_row(entity_row, "id")
    conn.execute(
        "DELETE FROM mcp_memory_observations WHERE entity_id = ? AND source = ?",
        (entity_id, source),
    )
    for content in contents:
        conn.execute(
            "INSERT INTO mcp_memory_observations (id, entity_id, content, source, created_at_ms) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, entity_id, content, source, now),
        )
    conn.execute("UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?", (now, entity_id))
    if not delete_entity_if_empty:
        return
    observations_count = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM mcp_memory_observations WHERE entity_id = ?",
            (entity_id,),
        ),
    )
    relations_out_count = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM mcp_memory_relations WHERE from_entity_id = ?",
            (entity_id,),
        ),
    )
    relations_in_count = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM mcp_memory_relations WHERE to_entity_id = ?",
            (entity_id,),
        ),
    )
    if observations_count is None or relations_out_count is None or relations_in_count is None:
        return
    if (
        coerce_required_int_from_sqlite_row(observations_count, "count") > 0
        or coerce_required_int_from_sqlite_row(relations_out_count, "count") > 0
        or coerce_required_int_from_sqlite_row(relations_in_count, "count") > 0
    ):
        return
    conn.execute("DELETE FROM mcp_memory_entities WHERE id = ?", (entity_id,))
