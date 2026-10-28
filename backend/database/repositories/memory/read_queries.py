"""SoAI - Memory repository read query helpers [backend/database/repositories/memory/read_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.types.json import JSONDict
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_to_dicts
from database.core.sql_builders import build_placeholder_list
from database.repositories.memory.entity_projection import (
    append_grouped_memory_rows,
    shape_entity_detail,
    shape_managed_entry,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "read_get_entity",
    "read_list_entities",
    "read_search_entities",
)


def _entity_id(entity_row: SQLiteRowDict) -> str:
    return str(entity_row.get("id", ""))


def _entity_id_batches(entity_rows: list[SQLiteRowDict]) -> Iterable[list[str]]:
    entity_ids: list[str] = []
    seen_ids: set[str] = set()
    for entity_row in entity_rows:
        entity_id = _entity_id(entity_row)
        if entity_id in seen_ids:
            continue
        seen_ids.add(entity_id)
        entity_ids.append(entity_id)
    for start_index in range(0, len(entity_ids), SQLITE_BATCH_SIZE):
        yield entity_ids[start_index : start_index + SQLITE_BATCH_SIZE]


async def _read_observations_by_entity(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> dict[str, list[SQLiteRowDict]]:
    groups: dict[str, list[SQLiteRowDict]] = {}
    for entity_ids in _entity_id_batches(entity_rows):
        sql = " ".join(
            (
                "SELECT entity_id, id, content, source, created_at_ms FROM mcp_memory_observations",
                f"WHERE entity_id IN ({build_placeholder_list(len(entity_ids))})",
                "ORDER BY entity_id ASC, created_at_ms DESC, id ASC",
            ),
        )
        rows = await query_to_dicts(
            database,
            sql,
            tuple(entity_ids),
        )
        append_grouped_memory_rows(groups, rows, "entity_id")
    return groups


async def _read_outbound_relations_by_entity(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> dict[str, list[SQLiteRowDict]]:
    groups: dict[str, list[SQLiteRowDict]] = {}
    for entity_ids in _entity_id_batches(entity_rows):
        sql = " ".join(
            (
                "SELECT r.from_entity_id, r.to_entity_id, r.id, r.relation_type, r.created_at_ms, e.name as to_entity, src.name as from_entity",
                "FROM mcp_memory_relations r JOIN mcp_memory_entities e ON e.id = r.to_entity_id JOIN mcp_memory_entities src ON src.id = r.from_entity_id",
                f"WHERE r.from_entity_id IN ({build_placeholder_list(len(entity_ids))})",
            ),
        )
        rows = await query_to_dicts(
            database,
            sql,
            tuple(entity_ids),
        )
        append_grouped_memory_rows(groups, rows, "from_entity_id")
    return groups


async def _read_inbound_relations_by_entity(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> dict[str, list[SQLiteRowDict]]:
    groups: dict[str, list[SQLiteRowDict]] = {}
    for entity_ids in _entity_id_batches(entity_rows):
        sql = " ".join(
            (
                "SELECT r.to_entity_id, r.from_entity_id, r.id, r.relation_type, r.created_at_ms, e.name as from_entity, dst.name as to_entity",
                "FROM mcp_memory_relations r JOIN mcp_memory_entities e ON e.id = r.from_entity_id JOIN mcp_memory_entities dst ON dst.id = r.to_entity_id",
                f"WHERE r.to_entity_id IN ({build_placeholder_list(len(entity_ids))})",
            ),
        )
        rows = await query_to_dicts(
            database,
            sql,
            tuple(entity_ids),
        )
        append_grouped_memory_rows(groups, rows, "to_entity_id")
    return groups


async def read_entity_details_for_rows(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
    *,
    managed: bool = False,
) -> list[JSONDict]:
    if not entity_rows:
        return []
    observations_by_entity = await _read_observations_by_entity(database, entity_rows)
    outbound_relations_by_entity = await _read_outbound_relations_by_entity(database, entity_rows)
    inbound_relations_by_entity = await _read_inbound_relations_by_entity(database, entity_rows)
    if managed:
        return [
            shape_managed_entry(
                entity_row,
                observations_by_entity.get(_entity_id(entity_row), []),
                outbound_relations_by_entity.get(_entity_id(entity_row), [])
                + inbound_relations_by_entity.get(_entity_id(entity_row), []),
            )
            for entity_row in entity_rows
        ]
    return [
        shape_entity_detail(
            entity_row,
            observations_by_entity,
            outbound_relations_by_entity,
            inbound_relations_by_entity,
        )
        for entity_row in entity_rows
    ]


async def read_search_entities(
    database: aiosqlite.Connection,
    user_id: int,
    query: str,
    entity_type: str | None,
    limit: int,
) -> list[JSONDict]:
    normalized_query = str(query or "").strip()
    is_match_all = normalized_query == "*" or not normalized_query
    if is_match_all:
        if entity_type:
            entity_rows = await query_to_dicts(
                database,
                "SELECT DISTINCT e.id, e.name, e.entity_type, e.created_at_ms, e.updated_at_ms FROM mcp_memory_entities e WHERE e.user_id = ? AND e.entity_type = ? ORDER BY e.updated_at_ms DESC LIMIT ?",
                (user_id, entity_type, limit),
            )
        else:
            entity_rows = await query_to_dicts(
                database,
                "SELECT DISTINCT e.id, e.name, e.entity_type, e.created_at_ms, e.updated_at_ms FROM mcp_memory_entities e WHERE e.user_id = ? ORDER BY e.updated_at_ms DESC LIMIT ?",
                (user_id, limit),
            )
    elif entity_type:
        entity_rows = await query_to_dicts(
            database,
            "SELECT DISTINCT e.id, e.name, e.entity_type, e.created_at_ms, e.updated_at_ms FROM mcp_memory_entities e LEFT JOIN mcp_memory_observations o ON o.entity_id = e.id WHERE e.user_id = ? AND e.entity_type = ? AND (instr(lower(e.name), lower(?)) > 0 OR instr(lower(COALESCE(o.content, '')), lower(?)) > 0) ORDER BY CASE WHEN lower(e.name) = lower(?) THEN 0 ELSE 1 END, e.updated_at_ms DESC LIMIT ?",
            (
                user_id,
                entity_type,
                normalized_query,
                normalized_query,
                normalized_query,
                limit,
            ),
        )
    else:
        entity_rows = await query_to_dicts(
            database,
            "SELECT DISTINCT e.id, e.name, e.entity_type, e.created_at_ms, e.updated_at_ms FROM mcp_memory_entities e LEFT JOIN mcp_memory_observations o ON o.entity_id = e.id WHERE e.user_id = ? AND (instr(lower(e.name), lower(?)) > 0 OR instr(lower(COALESCE(o.content, '')), lower(?)) > 0) ORDER BY CASE WHEN lower(e.name) = lower(?) THEN 0 ELSE 1 END, e.updated_at_ms DESC LIMIT ?",
            (user_id, normalized_query, normalized_query, normalized_query, limit),
        )
    return await read_entity_details_for_rows(database, entity_rows)


async def read_get_entity(
    database: aiosqlite.Connection,
    user_id: int,
    name: str,
) -> JSONDict | None:
    entity_rows = await query_to_dicts(
        database,
        "SELECT id, name, entity_type, created_at_ms, updated_at_ms FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
        (user_id, name),
    )
    if not entity_rows:
        return None
    entity_details = await read_entity_details_for_rows(database, [entity_rows[0]])
    return entity_details[0]


async def read_list_entities(
    database: aiosqlite.Connection,
    user_id: int,
) -> list[JSONDict]:
    entity_rows = await query_to_dicts(
        database,
        "SELECT id, name, entity_type, created_at_ms, updated_at_ms FROM mcp_memory_entities WHERE user_id = ? ORDER BY updated_at_ms DESC, created_at_ms DESC",
        (user_id,),
    )
    return await read_entity_details_for_rows(database, entity_rows)
