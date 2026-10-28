"""SoAI - Memory graph entry projections [backend/database/repositories/memory/entity_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.memory.profile_codec import USER_PROFILE_ENTITY_NAME, profile_observation_field
from core.memory.revisions import calculate_memory_revision
from core.types.json import JSONDict, JSONValue
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "shape_entity_detail",
    "shape_managed_entry",
    "append_grouped_memory_rows",
)


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


def shape_entity_detail(
    entity_row: SQLiteRowDict,
    observations_by_entity: dict[str, list[SQLiteRowDict]],
    outbound_relations_by_entity: dict[str, list[SQLiteRowDict]],
    inbound_relations_by_entity: dict[str, list[SQLiteRowDict]],
) -> JSONDict:
    entity_id = str(entity_row.get("id", ""))
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


def shape_managed_entry(
    entity_row: SQLiteRowDict,
    observation_rows: list[SQLiteRowDict],
    relation_rows: list[SQLiteRowDict],
) -> JSONDict:
    entity = sqlite_row_dict_to_json_dict(entity_row)
    entity.pop("user_id", None)
    is_profile = entity["name"] == USER_PROFILE_ENTITY_NAME
    observations: list[JSONValue] = []
    for row in observation_rows:
        observation = sqlite_row_dict_to_json_dict(row)
        observation.pop("entity_id", None)
        content = observation.get("content")
        source = observation.get("source")
        observation["profile_field"] = (
            profile_observation_field(content, source if isinstance(source, str) else None)
            if is_profile and isinstance(content, str)
            else None
        )
        observations.append(observation)
    unique_relations = {str(row["id"]): row for row in relation_rows}
    relations: list[JSONValue] = [
        sqlite_row_dict_to_json_dict(unique_relations[relation_id])
        for relation_id in sorted(unique_relations)
    ]
    snapshot: JSONDict = {"entity": entity, "observations": observations, "relations": relations}
    return {
        **snapshot,
        "revision": calculate_memory_revision(
            {
                **snapshot,
                "observations": sorted(
                    observations,
                    key=lambda observation: (
                        str(observation["id"]) if isinstance(observation, dict) else ""
                    ),
                ),
            }
        ),
        "is_profile": is_profile,
    }


def append_grouped_memory_rows(
    groups: dict[str, list[SQLiteRowDict]],
    rows: list[SQLiteRowDict],
    group_key: str,
) -> None:
    for row in rows:
        key_value = str(row.get(group_key, ""))
        if key_value not in groups:
            groups[key_value] = []
        groups[key_value].append(row)
