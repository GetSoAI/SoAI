"""SoAI - Memory repository atomic graph store queries [backend/database/repositories/memory/write_queries_graph_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.validation.record_fields import (
    require_non_empty_str,
    require_optional_non_empty_str,
)
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_store_graph",)


def _resolve_entity_id(
    conn: sqlite3.Connection,
    user_id: int,
    entity_name: str,
    cached_entity_ids: dict[str, str],
) -> str | None:
    cached = cached_entity_ids.get(entity_name)
    if cached is not None:
        return cached
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
            (user_id, entity_name),
        ),
    )
    if row is None:
        return None
    entity_id = coerce_required_nonempty_str_from_sqlite_row(row, "id")
    cached_entity_ids[entity_name] = entity_id
    return entity_id


def sync_store_graph(
    conn: sqlite3.Connection,
    user_id: int,
    entities: list[JSONDict],
    observations: list[JSONDict],
    relations: list[JSONDict],
) -> JSONDict:
    now = epoch_ms()
    entity_ids_by_name: dict[str, str] = {}
    entity_names_in_order: list[str] = []
    seen_entity_names: set[str] = set()
    entities_inserted = 0
    entities_updated = 0

    for index, entity in enumerate(entities):
        name = require_non_empty_str(
            entity.get("name"),
            label=f"entities[{index}].name",
            build_error=ValidationError,
            invalid_message=f"entities[{index}].name must be a non-empty string.",
        )
        entity_type = require_non_empty_str(
            entity.get("entity_type"),
            label=f"entities[{index}].entity_type",
            build_error=ValidationError,
            invalid_message=f"entities[{index}].entity_type must be a non-empty string.",
        )
        if name in seen_entity_names:
            raise ValidationError(f"entities[{index}].name duplicates '{name}'.")
        seen_entity_names.add(name)
        existing_row = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
                (user_id, name),
            ),
        )
        if existing_row is None:
            entity_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO mcp_memory_entities (id, user_id, name, entity_type, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
                (entity_id, user_id, name, entity_type, now, now),
            )
            entities_inserted += 1
            entity_ids_by_name[name] = entity_id
            entity_names_in_order.append(name)
            continue
        entity_id = coerce_required_nonempty_str_from_sqlite_row(existing_row, "id")
        conn.execute(
            "UPDATE mcp_memory_entities SET entity_type = ?, updated_at_ms = ? WHERE id = ?",
            (entity_type, now, entity_id),
        )
        entities_updated += 1
        entity_ids_by_name[name] = entity_id
        entity_names_in_order.append(name)

    observations_inserted = 0
    observation_results: list[JSONDict] = []
    touched_entity_ids: set[str] = set()
    for index, observation in enumerate(observations):
        entity_name = require_non_empty_str(
            observation.get("entity_name"),
            label=f"observations[{index}].entity_name",
            build_error=ValidationError,
            invalid_message=f"observations[{index}].entity_name must be a non-empty string.",
        )
        content = require_non_empty_str(
            observation.get("content"),
            label=f"observations[{index}].content",
            build_error=ValidationError,
            invalid_message=f"observations[{index}].content must be a non-empty string.",
        )
        source = require_optional_non_empty_str(
            observation.get("source"),
            label=f"observations[{index}].source",
            build_error=ValidationError,
            invalid_message=(
                f"observations[{index}].source must be a non-empty string when provided."
            ),
        )
        resolved_entity_id = _resolve_entity_id(
            conn,
            user_id,
            entity_name,
            entity_ids_by_name,
        )
        if resolved_entity_id is None:
            raise ValidationError(
                f"Observation at index {index} references unknown entity '{entity_name}'.",
            )
        observation_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO mcp_memory_observations (id, entity_id, content, source, created_at_ms) VALUES (?, ?, ?, ?, ?)",
            (observation_id, resolved_entity_id, content, source, now),
        )
        touched_entity_ids.add(resolved_entity_id)
        observations_inserted += 1
        observation_results.append(
            {
                "id": observation_id,
                "entity_name": entity_name,
                "entity_id": resolved_entity_id,
                "content": content,
                "source": source,
                "created_at_ms": now,
            },
        )

    relations_inserted = 0
    relations_existing = 0
    relation_results: list[JSONDict] = []
    seen_relation_keys: set[tuple[str, str, str]] = set()
    for index, relation in enumerate(relations):
        from_entity = require_non_empty_str(
            relation.get("from_entity"),
            label=f"relations[{index}].from_entity",
            build_error=ValidationError,
            invalid_message=f"relations[{index}].from_entity must be a non-empty string.",
        )
        to_entity = require_non_empty_str(
            relation.get("to_entity"),
            label=f"relations[{index}].to_entity",
            build_error=ValidationError,
            invalid_message=f"relations[{index}].to_entity must be a non-empty string.",
        )
        relation_type = require_non_empty_str(
            relation.get("relation_type"),
            label=f"relations[{index}].relation_type",
            build_error=ValidationError,
            invalid_message=f"relations[{index}].relation_type must be a non-empty string.",
        )
        relation_key = (from_entity, to_entity, relation_type)
        if relation_key in seen_relation_keys:
            raise ValidationError(
                f"relations[{index}] duplicates relation ({from_entity}, {to_entity}, {relation_type}).",
            )
        seen_relation_keys.add(relation_key)
        from_entity_id = _resolve_entity_id(conn, user_id, from_entity, entity_ids_by_name)
        if from_entity_id is None:
            raise ValidationError(
                f"Relation at index {index} references unknown source entity '{from_entity}'.",
            )
        to_entity_id = _resolve_entity_id(conn, user_id, to_entity, entity_ids_by_name)
        if to_entity_id is None:
            raise ValidationError(
                f"Relation at index {index} references unknown target entity '{to_entity}'.",
            )
        existing_relation = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT id, created_at_ms FROM mcp_memory_relations WHERE from_entity_id = ? AND to_entity_id = ? AND relation_type = ?",
                (from_entity_id, to_entity_id, relation_type),
            ),
        )
        relation_id: str
        created_at_ms: int
        if existing_relation is None:
            relation_id = uuid.uuid4().hex
            created_at_ms = now
            conn.execute(
                "INSERT INTO mcp_memory_relations (id, from_entity_id, to_entity_id, relation_type, created_at_ms) VALUES (?, ?, ?, ?, ?)",
                (relation_id, from_entity_id, to_entity_id, relation_type, created_at_ms),
            )
            relations_inserted += 1
        else:
            relation_id = coerce_required_nonempty_str_from_sqlite_row(existing_relation, "id")
            created_at_ms = coerce_required_int_from_sqlite_row(existing_relation, "created_at_ms")
            relations_existing += 1
        relation_results.append(
            {
                "id": relation_id,
                "from_entity": from_entity,
                "to_entity": to_entity,
                "relation_type": relation_type,
                "created_at_ms": created_at_ms,
            },
        )
        touched_entity_ids.add(from_entity_id)
        touched_entity_ids.add(to_entity_id)

    for touched_entity_id in touched_entity_ids:
        conn.execute(
            "UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?",
            (now, touched_entity_id),
        )

    entity_results: list[JSONDict] = []
    for name in entity_names_in_order:
        row = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT id, name, entity_type, created_at_ms, updated_at_ms FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
                (user_id, name),
            ),
        )
        if row is None:
            continue
        entity_results.append(
            {
                "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
                "name": coerce_required_nonempty_str_from_sqlite_row(row, "name"),
                "entity_type": coerce_required_nonempty_str_from_sqlite_row(row, "entity_type"),
                "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
                "updated_at_ms": coerce_required_int_from_sqlite_row(row, "updated_at_ms"),
            },
        )

    return {
        "entities_inserted": entities_inserted,
        "entities_updated": entities_updated,
        "entities_written_total": entities_inserted + entities_updated,
        "observations_inserted": observations_inserted,
        "relations_inserted": relations_inserted,
        "relations_existing": relations_existing,
        "relations_written_total": relations_inserted + relations_existing,
        "entities": entity_results,
        "observations": observation_results,
        "relations": relation_results,
    }
