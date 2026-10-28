"""SoAI - Atomic structured memory profile persistence [backend/database/repositories/memory/profile_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.memory.profile_codec import (
    PROFILE_FIELD_NAMES,
    USER_PROFILE_ENTITY_NAME,
    USER_PROFILE_ENTITY_TYPE,
    USER_PROFILE_SOURCE,
    build_profile_observations,
    profile_observation_field,
)
from core.memory.revisions import memory_management_error, require_memory_revision
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_json_object
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import sync_fetch_all_as_dicts, sync_fetch_one_as_dict
from database.repositories.memory.graph_records import (
    sync_insert_memory_entity,
    sync_insert_memory_observation,
)
from database.repositories.memory.management_snapshots import sync_read_management_library
from database.repositories.users.chat_identity_defaults import sync_upsert_user_display_name
from database.repositories.users.user_preference_mutations import sync_set_default_assistant_name

__all__ = (
    "legacy_memory_snapshot",
    "sync_save_profile",
)


def legacy_memory_snapshot(library: JSONDict) -> JSONDict:
    managed_entries = library.get("entries")
    entries: list[JSONValue] = []
    if isinstance(managed_entries, list):
        for entry in managed_entries:
            if not isinstance(entry, dict):
                continue
            entity = require_json_object(entry["entity"], label="entity", build_error=ValueError)
            observations = entry.get("observations")
            relations = entry.get("relations")
            entry_id = entity["id"]
            legacy_relations: list[JSONValue] = []
            if isinstance(relations, list):
                for direction, endpoint in (
                    ("from_entity_id", "to_entity"),
                    ("to_entity_id", "from_entity"),
                ):
                    for relation in relations:
                        if isinstance(relation, dict) and relation[direction] == entry_id:
                            legacy_relations.append(
                                {
                                    "id": relation["id"],
                                    "relation_type": relation["relation_type"],
                                    "created_at_ms": relation["created_at_ms"],
                                    endpoint: relation[endpoint],
                                }
                            )
            entries.append(
                {
                    "entity": {key: value for key, value in entity.items() if key != "id"},
                    "observations": (
                        [
                            {
                                key: value
                                for key, value in observation.items()
                                if key != "profile_field"
                            }
                            for observation in observations
                            if isinstance(observation, dict)
                        ]
                        if isinstance(observations, list)
                        else []
                    ),
                    "relations": legacy_relations,
                }
            )
    return {"entries": entries, "profile_form": library["profile_form"]}


def sync_save_profile(
    conn: sqlite3.Connection, user_id: int, payload: JSONDict, expected_revision: str | None
) -> JSONDict:
    current = sync_read_management_library(conn, user_id)
    if expected_revision is not None:
        require_memory_revision(expected_revision, str(current["profile_revision"]))
    form = require_json_object(
        current["profile_form"], label="profile_form", build_error=ValueError
    )
    for field_name, value in payload.items():
        if field_name not in PROFILE_FIELD_NAMES or (
            value is not None and not isinstance(value, str)
        ):
            raise memory_management_error(
                "memory_invalid_profile", "Use the profile form's supported text fields.", 422
            )
    if "preferred_name" in payload:
        preferred_name = coerce_optional_trimmed_str(payload["preferred_name"])
        if form.get("preferred_name") != preferred_name:
            sync_upsert_user_display_name(conn, user_id, preferred_name)
    if "assistant_name" in payload:
        assistant_name = coerce_optional_trimmed_str(payload["assistant_name"])
        if sync_set_default_assistant_name(conn, user_id, assistant_name) is None:
            raise memory_management_error(
                "memory_user_missing", "Sign in again to manage your profile.", 401
            )
    entity = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name = ?",
            (user_id, USER_PROFILE_ENTITY_NAME),
        )
    )
    now = epoch_ms()
    changed = False
    for field_name in PROFILE_FIELD_NAMES:
        if field_name not in payload or field_name in ("preferred_name", "assistant_name"):
            continue
        value = coerce_optional_trimmed_str(payload[field_name])
        if value is not None and value == form.get(field_name):
            continue
        matching_content = build_profile_observations({field_name: value})
        if entity is None:
            if not matching_content:
                continue
            entity_id = uuid.uuid4().hex
            sync_insert_memory_entity(
                conn, entity_id, user_id, USER_PROFILE_ENTITY_NAME, USER_PROFILE_ENTITY_TYPE, now
            )
            entity = {"id": entity_id}
        entity_id = str(entity["id"])
        rows = sync_fetch_all_as_dicts(
            conn.execute(
                "SELECT id, content FROM mcp_memory_observations WHERE entity_id = ? AND source = ? ORDER BY created_at_ms DESC, id ASC",
                (entity_id, USER_PROFILE_SOURCE),
            )
        )
        matching_ids = [
            str(row["id"])
            for row in rows
            if isinstance(row["content"], str)
            and profile_observation_field(row["content"], USER_PROFILE_SOURCE) == field_name
        ]
        if not matching_ids and not matching_content:
            continue
        changed = True
        if matching_content:
            if matching_ids:
                conn.execute(
                    "UPDATE mcp_memory_observations SET content = ? WHERE id = ?",
                    (matching_content[0], matching_ids[0]),
                )
                matching_ids = matching_ids[1:]
            else:
                sync_insert_memory_observation(
                    conn, uuid.uuid4().hex, entity_id, matching_content[0], USER_PROFILE_SOURCE, now
                )
        for observation_id in matching_ids:
            conn.execute("DELETE FROM mcp_memory_observations WHERE id = ?", (observation_id,))
    if changed and entity is not None:
        conn.execute(
            "UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?", (now, entity["id"])
        )
    return legacy_memory_snapshot(sync_read_management_library(conn, user_id))
