"""SoAI - Memory repository read query helpers [backend/database/repositories/memory/read_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.types.json import JSONDict
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_to_dicts

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


def _placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)


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


def _append_grouped_rows(
    groups: dict[str, list[SQLiteRowDict]],
    rows: list[SQLiteRowDict],
    group_key: str,
) -> None:
    for row in rows:
        key_value = str(row.get(group_key, ""))
        if key_value not in groups:
            groups[key_value] = []
        groups[key_value].append(row)


async def _read_observations_by_entity(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> dict[str, list[SQLiteRowDict]]:
    groups: dict[str, list[SQLiteRowDict]] = {}
    for entity_ids in _entity_id_batches(entity_rows):
        sql = " ".join(
            (
                "SELECT entity_id, id, content, source, created_at_ms FROM mcp_memory_observations",
                f"WHERE entity_id IN ({_placeholders(entity_ids)})",
                "ORDER BY entity_id ASC, created_at_ms DESC",
            ),
        )
        rows = await query_to_dicts(
            database,
            sql,
            tuple(entity_ids),
        )
        _append_grouped_rows(groups, rows, "entity_id")
    return groups


async def _read_outbound_relations_by_entity(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> dict[str, list[SQLiteRowDict]]:
    groups: dict[str, list[SQLiteRowDict]] = {}
    for entity_ids in _entity_id_batches(entity_rows):
        sql = " ".join(
            (
                "SELECT r.from_entity_id, r.id, r.relation_type, r.created_at_ms, e.name as to_entity",
                "FROM mcp_memory_relations r JOIN mcp_memory_entities e ON e.id = r.to_entity_id",
                f"WHERE r.from_entity_id IN ({_placeholders(entity_ids)})",
            ),
        )
        rows = await query_to_dicts(
            database,
            sql,
            tuple(entity_ids),
        )
        _append_grouped_rows(groups, rows, "from_entity_id")
    return groups


async def _read_inbound_relations_by_entity(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> dict[str, list[SQLiteRowDict]]:
    groups: dict[str, list[SQLiteRowDict]] = {}
    for entity_ids in _entity_id_batches(entity_rows):
        sql = " ".join(
            (
                "SELECT r.to_entity_id, r.id, r.relation_type, r.created_at_ms, e.name as from_entity",
                "FROM mcp_memory_relations r JOIN mcp_memory_entities e ON e.id = r.from_entity_id",
                f"WHERE r.to_entity_id IN ({_placeholders(entity_ids)})",
            ),
        )
        rows = await query_to_dicts(
            database,
            sql,
            tuple(entity_ids),
        )
        _append_grouped_rows(groups, rows, "to_entity_id")
    return groups


def _shape_observations(rows: list[SQLiteRowDict]) -> list[JSONDict]:
    return [
        {
            "id": observation.get("id", ""),
            "content": observation.get("content", ""),
            "source": observation.get("source"),
            "created_at_ms": observation.get("created_at_ms", 0),
        }
        for observation in rows
    ]


def _shape_outbound_relations(rows: list[SQLiteRowDict]) -> list[JSONDict]:
    return [
        {
            "id": relation.get("id", ""),
            "relation_type": relation.get("relation_type", ""),
            "to_entity": relation.get("to_entity", ""),
            "created_at_ms": relation.get("created_at_ms", 0),
        }
        for relation in rows
    ]


def _shape_inbound_relations(rows: list[SQLiteRowDict]) -> list[JSONDict]:
    return [
        {
            "id": relation.get("id", ""),
            "relation_type": relation.get("relation_type", ""),
            "from_entity": relation.get("from_entity", ""),
            "created_at_ms": relation.get("created_at_ms", 0),
        }
        for relation in rows
    ]


def _shape_entity_detail(
    entity_row: SQLiteRowDict,
    observations_by_entity: dict[str, list[SQLiteRowDict]],
    outbound_relations_by_entity: dict[str, list[SQLiteRowDict]],
    inbound_relations_by_entity: dict[str, list[SQLiteRowDict]],
) -> JSONDict:
    entity_id = _entity_id(entity_row)
    return {
        "entity": {
            "name": entity_row.get("name", ""),
            "entity_type": entity_row.get("entity_type", ""),
            "created_at_ms": entity_row.get("created_at_ms", 0),
            "updated_at_ms": entity_row.get("updated_at_ms", 0),
        },
        "observations": _shape_observations(observations_by_entity.get(entity_id, [])),
        "relations": _shape_outbound_relations(outbound_relations_by_entity.get(entity_id, []))
        + _shape_inbound_relations(inbound_relations_by_entity.get(entity_id, [])),
    }


async def read_entity_details_for_rows(
    database: aiosqlite.Connection,
    entity_rows: list[SQLiteRowDict],
) -> list[JSONDict]:
    if not entity_rows:
        return []
    observations_by_entity = await _read_observations_by_entity(database, entity_rows)
    outbound_relations_by_entity = await _read_outbound_relations_by_entity(database, entity_rows)
    inbound_relations_by_entity = await _read_inbound_relations_by_entity(database, entity_rows)
    return [
        _shape_entity_detail(
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
