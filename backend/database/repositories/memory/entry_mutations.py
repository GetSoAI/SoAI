"""SoAI - Atomic memory entry and observation management [backend/database/repositories/memory/entry_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.memory.profile_codec import USER_PROFILE_ENTITY_NAME
from core.memory.revisions import memory_management_error, require_memory_revision
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.record_fields import require_json_object, require_non_empty_str
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.memory.graph_records import (
    sync_insert_memory_entity,
    sync_insert_memory_observation,
)
from database.repositories.memory.management_snapshots import sync_read_managed_entry
from database.repositories.memory.write_queries_graph_delete import sync_delete_graph

__all__ = (
    "require_entry_revision",
    "require_memory_text",
    "require_available_name",
    "require_managed_observation",
    "sync_create_entry",
    "sync_update_entry",
    "sync_delete_entry",
    "sync_delete_observation",
)


def require_entry_revision(
    conn: sqlite3.Connection, user_id: int, entry_id: str, expected_revision: str
) -> JSONDict:
    entry = sync_read_managed_entry(conn, user_id, entry_id)
    require_memory_revision(expected_revision, str(entry["revision"]))
    return entry


def require_memory_text(value: str, label: str) -> str:
    return require_non_empty_str(
        value,
        label=label,
        build_error=lambda message: memory_management_error("memory_invalid_text", message, 422),
    )


def require_available_name(
    conn: sqlite3.Connection, user_id: int, name: str, entry_id: str | None = None
) -> None:
    if name == USER_PROFILE_ENTITY_NAME:
        raise memory_management_error(
            "memory_profile_restricted",
            "Use the profile form to manage structured profile facts.",
            422,
        )
    existing = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT id FROM mcp_memory_entities WHERE user_id = ? AND name = ?", (user_id, name)
        )
    )
    if existing is not None and existing["id"] != entry_id:
        raise memory_management_error(
            "memory_duplicate_name", "A memory already uses this title. Choose another title."
        )


def require_managed_observation(entry: JSONDict, observation_id: str) -> JSONDict:
    observations = entry.get("observations")
    if isinstance(observations, list):
        for observation in observations:
            if isinstance(observation, dict) and observation.get("id") == observation_id:
                if observation.get("profile_field") is not None:
                    raise memory_management_error(
                        "memory_profile_restricted",
                        "Use the profile form to manage this structured fact.",
                        422,
                    )
                return observation
    raise memory_management_error(
        "memory_observation_missing",
        "This fact no longer belongs to this memory. Refresh and review the entry.",
        404,
    )


def sync_create_entry(
    conn: sqlite3.Connection, user_id: int, entry_id: str, name: str, content: str
) -> JSONDict:
    require_memory_text(entry_id, "id")
    if entry_id in (".", "..") or any(
        character in "/\\" or ord(character) < 32 or ord(character) == 127 for character in entry_id
    ):
        raise memory_management_error(
            "memory_invalid_update", "Use a memory identity that fits one URL path segment.", 422
        )
    title = require_memory_text(name, "name")
    require_memory_text(content, "content")
    require_available_name(conn, user_id, title)
    if conn.execute("SELECT 1 FROM mcp_memory_entities WHERE id = ?", (entry_id,)).fetchone():
        raise memory_management_error(
            "memory_duplicate_id",
            "This draft identity already exists. Refresh and review the saved memory.",
        )
    now = epoch_ms()
    sync_insert_memory_entity(conn, entry_id, user_id, title, "note", now)
    sync_insert_memory_observation(conn, uuid.uuid4().hex, entry_id, content, "manual", now)
    return sync_read_managed_entry(conn, user_id, entry_id)


def sync_update_entry(
    conn: sqlite3.Connection,
    user_id: int,
    entry_id: str,
    expected_revision: str,
    name: str | None,
    observation: JSONDict | None,
) -> JSONDict:
    entry = require_entry_revision(conn, user_id, entry_id, expected_revision)
    if name is None and observation is None:
        raise memory_management_error(
            "memory_invalid_update", "Provide a title or a fact to update.", 422
        )
    entity = require_json_object(entry["entity"], label="entity", build_error=ValueError)
    title = require_memory_text(name, "name") if name is not None else None
    if title is not None and title != entity["name"]:
        if entry["is_profile"]:
            raise memory_management_error(
                "memory_profile_restricted",
                "The structured profile identity cannot be renamed.",
                422,
            )
        require_available_name(conn, user_id, title, entry_id)
    observation_id: str | None = None
    content: str | None = None
    if observation is not None:
        content_value = observation.get("content")
        if not isinstance(content_value, str):
            raise memory_management_error("memory_invalid_text", "Enter text for this fact.", 422)
        require_memory_text(content_value, "content")
        content = content_value
        observation_id_value = observation.get("id")
        if observation_id_value is not None:
            if not isinstance(observation_id_value, str):
                raise memory_management_error(
                    "memory_invalid_update", "Select a valid fact to edit.", 422
                )
            observation_id = observation_id_value
            require_managed_observation(entry, observation_id)
    now = epoch_ms()
    if title is not None:
        conn.execute("UPDATE mcp_memory_entities SET name = ? WHERE id = ?", (title, entry_id))
    if content is not None:
        if observation_id is None:
            sync_insert_memory_observation(conn, uuid.uuid4().hex, entry_id, content, "manual", now)
        else:
            conn.execute(
                "UPDATE mcp_memory_observations SET content = ? WHERE id = ? AND entity_id = ?",
                (content, observation_id, entry_id),
            )
    conn.execute("UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?", (now, entry_id))
    return sync_read_managed_entry(conn, user_id, entry_id)


def sync_delete_entry(
    conn: sqlite3.Connection, user_id: int, entry_id: str, expected_revision: str
) -> JSONDict:
    entry = require_entry_revision(conn, user_id, entry_id, expected_revision)
    entity = require_json_object(entry["entity"], label="entity", build_error=ValueError)
    return sync_delete_graph(conn, user_id, [str(entity["name"])], [], [])


def sync_delete_observation(
    conn: sqlite3.Connection,
    user_id: int,
    entry_id: str,
    observation_id: str,
    expected_revision: str,
) -> JSONDict:
    entry = require_entry_revision(conn, user_id, entry_id, expected_revision)
    require_managed_observation(entry, observation_id)
    result = sync_delete_graph(conn, user_id, [], [observation_id], [])
    conn.execute(
        "UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?", (epoch_ms(), entry_id)
    )
    return result
