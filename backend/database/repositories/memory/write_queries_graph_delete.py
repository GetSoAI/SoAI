"""SoAI - Memory repository atomic graph delete queries [backend/database/repositories/memory/write_queries_graph_delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.query_execution import sync_fetch_all_as_dicts
from database.core.sql_builders import build_placeholder_list, validate_sql_identifier
from database.core.sqlite_numbers import coerce_required_nonempty_str_from_sqlite_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_delete_graph",)


def _normalize_non_empty_unique_identifiers(values: list[str], label: str) -> list[str]:
    normalized_values: list[str] = []
    seen_values: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValidationError(f"{label}[{index}] must be a non-empty string.")
        normalized_value = value.strip()
        if not normalized_value:
            raise ValidationError(f"{label}[{index}] must be a non-empty string.")
        if normalized_value in seen_values:
            raise ValidationError(f"{label}[{index}] duplicates '{normalized_value}'.")
        seen_values.add(normalized_value)
        normalized_values.append(normalized_value)
    return normalized_values


def _fetch_entity_ids_for_names(
    conn: sqlite3.Connection,
    user_id: int,
    entity_names: list[str],
) -> set[str]:
    if not entity_names:
        return set()
    placeholders = build_placeholder_list(len(entity_names))
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name IN ({placeholders})",
            (user_id, *entity_names),
        ),
    )
    return {coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows}


def _fetch_user_scoped_observation_ids(
    conn: sqlite3.Connection,
    user_id: int,
    observation_ids: list[str],
) -> set[str]:
    if not observation_ids:
        return set()
    placeholders = build_placeholder_list(len(observation_ids))
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"SELECT o.id AS id FROM mcp_memory_observations o JOIN mcp_memory_entities e ON e.id = o.entity_id WHERE e.user_id = ? AND o.id IN ({placeholders})",
            (user_id, *observation_ids),
        ),
    )
    return {coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows}


def _fetch_user_scoped_relation_ids(
    conn: sqlite3.Connection,
    user_id: int,
    relation_ids: list[str],
) -> set[str]:
    if not relation_ids:
        return set()
    placeholders = build_placeholder_list(len(relation_ids))
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"SELECT r.id AS id FROM mcp_memory_relations r JOIN mcp_memory_entities src ON src.id = r.from_entity_id JOIN mcp_memory_entities dst ON dst.id = r.to_entity_id WHERE src.user_id = ? AND dst.user_id = ? AND r.id IN ({placeholders})",
            (user_id, user_id, *relation_ids),
        ),
    )
    return {coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows}


def _fetch_cascade_observation_ids(
    conn: sqlite3.Connection,
    entity_ids: set[str],
) -> set[str]:
    if not entity_ids:
        return set()
    placeholders = build_placeholder_list(len(entity_ids))
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"SELECT id FROM mcp_memory_observations WHERE entity_id IN ({placeholders})",
            tuple(entity_ids),
        ),
    )
    return {coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows}


def _fetch_cascade_relation_ids(
    conn: sqlite3.Connection,
    entity_ids: set[str],
) -> set[str]:
    if not entity_ids:
        return set()
    placeholders = build_placeholder_list(len(entity_ids))
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"SELECT id FROM mcp_memory_relations WHERE from_entity_id IN ({placeholders}) OR to_entity_id IN ({placeholders})",
            tuple(entity_ids) + tuple(entity_ids),
        ),
    )
    return {coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows}


def _delete_by_ids(conn: sqlite3.Connection, table_name: str, ids: set[str]) -> int:
    if not ids:
        return 0
    table_identifier = validate_sql_identifier(table_name, label="table")
    placeholders = build_placeholder_list(len(ids))
    cursor = conn.execute(
        f"DELETE FROM {table_identifier} WHERE id IN ({placeholders})",
        tuple(ids),
    )
    return int(cursor.rowcount)


def sync_delete_graph(
    conn: sqlite3.Connection,
    user_id: int,
    entity_names: list[str],
    observation_ids: list[str],
    relation_ids: list[str],
) -> JSONDict:
    normalized_entity_names = _normalize_non_empty_unique_identifiers(entity_names, "entity_names")
    normalized_observation_ids = _normalize_non_empty_unique_identifiers(
        observation_ids,
        "observation_ids",
    )
    normalized_relation_ids = _normalize_non_empty_unique_identifiers(relation_ids, "relation_ids")
    entity_ids = _fetch_entity_ids_for_names(conn, user_id, normalized_entity_names)
    direct_observation_ids = _fetch_user_scoped_observation_ids(
        conn,
        user_id,
        normalized_observation_ids,
    )
    direct_relation_ids = _fetch_user_scoped_relation_ids(conn, user_id, normalized_relation_ids)
    cascade_observation_ids = (
        _fetch_cascade_observation_ids(conn, entity_ids) - direct_observation_ids
    )
    cascade_relation_ids = _fetch_cascade_relation_ids(conn, entity_ids) - direct_relation_ids

    observations_deleted_direct = _delete_by_ids(
        conn,
        "mcp_memory_observations",
        direct_observation_ids,
    )
    relations_deleted_direct = _delete_by_ids(conn, "mcp_memory_relations", direct_relation_ids)
    entities_deleted = _delete_by_ids(conn, "mcp_memory_entities", entity_ids)

    observations_deleted_cascade = len(cascade_observation_ids)
    relations_deleted_cascade = len(cascade_relation_ids)
    observations_deleted_total = observations_deleted_direct + observations_deleted_cascade
    relations_deleted_total = relations_deleted_direct + relations_deleted_cascade
    records_deleted_total = entities_deleted + observations_deleted_total + relations_deleted_total

    return {
        "entities_deleted": entities_deleted,
        "observations_deleted_direct": observations_deleted_direct,
        "observations_deleted_cascade": observations_deleted_cascade,
        "observations_deleted_total": observations_deleted_total,
        "relations_deleted_direct": relations_deleted_direct,
        "relations_deleted_cascade": relations_deleted_cascade,
        "relations_deleted_total": relations_deleted_total,
        "records_deleted_total": records_deleted_total,
    }
