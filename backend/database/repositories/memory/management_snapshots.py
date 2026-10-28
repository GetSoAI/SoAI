"""SoAI - Transactional memory management snapshots [backend/database/repositories/memory/management_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.chat.conversation_defaults import read_chat_conversation_defaults_model_settings
from core.memory.profile_codec import USER_PROFILE_ENTITY_NAME, build_profile_form
from core.memory.revisions import calculate_memory_revision, memory_management_error
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict
from core.users.preferences import decode_stored_user_preferences
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.core.read_transaction import run_read_transaction
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.memory.entity_projection import (
    append_grouped_memory_rows,
    shape_managed_entry,
)
from database.repositories.memory.read_queries import read_entity_details_for_rows

ENTITY_COLUMNS = "id, name, entity_type, created_at_ms, updated_at_ms"
RELATION_QUERY = (
    "SELECT r.id, r.from_entity_id, r.to_entity_id, r.relation_type, r.created_at_ms, "
    "src.name AS from_entity, dst.name AS to_entity FROM mcp_memory_relations r "
    "JOIN mcp_memory_entities src ON src.id = r.from_entity_id "
    "JOIN mcp_memory_entities dst ON dst.id = r.to_entity_id "
    "WHERE (r.from_entity_id = ? OR r.to_entity_id = ?) AND src.user_id = ? AND dst.user_id = ?"
)


__all__ = (
    "ENTITY_COLUMNS",
    "RELATION_QUERY",
    "sync_read_managed_entry",
    "build_management_library",
    "read_management_library",
    "read_managed_entry",
    "sync_read_management_library",
)


def sync_read_managed_entry(conn: sqlite3.Connection, user_id: int, entry_id: str) -> JSONDict:
    entity = sync_fetch_one_as_dict(
        conn.execute(
            f"SELECT {ENTITY_COLUMNS} FROM mcp_memory_entities WHERE user_id = ? AND id = ?",
            (user_id, entry_id),
        )
    )
    if entity is None:
        raise memory_management_error(
            "memory_entry_missing", "This memory no longer exists. Refresh the library.", 404
        )
    observations = sync_fetch_all_as_dicts(
        conn.execute(
            "SELECT id, content, source, created_at_ms FROM mcp_memory_observations WHERE entity_id = ? ORDER BY created_at_ms DESC, id ASC",
            (entry_id,),
        )
    )
    relations = sync_fetch_all_as_dicts(
        conn.execute(RELATION_QUERY, (entry_id, entry_id, user_id, user_id))
    )
    return shape_managed_entry(entity, observations, relations)


def build_management_library(
    entries: list[JSONDict], preferences: JSONDict, identity: JSONDict | None
) -> JSONDict:
    preferred_name = (
        coerce_optional_trimmed_str(identity.get("user_display_name")) if identity else None
    )
    model_settings = read_chat_conversation_defaults_model_settings(preferences) or {}
    assistant_identity = coerce_json_dict(model_settings.get("identity")) or {}
    assistant_name = coerce_optional_trimmed_str(assistant_identity.get("assistant_display_name"))
    profile_form = build_profile_form(
        entries, preferred_name=preferred_name, assistant_name=assistant_name
    )
    profile_identity: JSONValue = None
    facts: list[JSONValue] = []
    for entry in entries:
        entity = entry.get("entity")
        if not isinstance(entity, dict) or entity.get("name") != USER_PROFILE_ENTITY_NAME:
            continue
        profile_identity = {
            field: entity[field] for field in ("id", "name", "entity_type", "created_at_ms")
        }
        observations = entry.get("observations")
        if isinstance(observations, list):
            facts = [
                observation
                for observation in observations
                if isinstance(observation, dict) and observation.get("profile_field") is not None
            ]
    return {
        "entries": entries,
        "profile_form": profile_form,
        "profile_revision": calculate_memory_revision(
            {
                "entity": profile_identity,
                "facts": sorted(
                    facts,
                    key=lambda observation: (
                        str(observation["id"]) if isinstance(observation, dict) else ""
                    ),
                ),
                "preferred_name": preferred_name,
                "assistant_name": assistant_name,
            }
        ),
    }


async def read_management_library(database: aiosqlite.Connection, user_id: int) -> JSONDict:
    async def snapshot(connection: aiosqlite.Connection) -> JSONDict:
        rows = await query_to_dicts(
            connection,
            f"SELECT {ENTITY_COLUMNS} FROM mcp_memory_entities WHERE user_id = ? ORDER BY updated_at_ms DESC, created_at_ms DESC, id ASC",
            (user_id,),
        )
        entries = await read_entity_details_for_rows(connection, rows, managed=True)
        user = await query_one_to_dict(
            connection,
            "SELECT preferences FROM webui_users WHERE id = ? AND account_type = 'human'",
            (user_id,),
        )
        if user is None:
            raise memory_management_error(
                "memory_user_missing", "Sign in again to manage your memories.", 401
            )
        identity = await query_one_to_dict(
            connection,
            "SELECT user_display_name FROM webui_chat_identity_defaults WHERE user_id = ?",
            (user_id,),
        )
        return build_management_library(
            entries,
            decode_stored_user_preferences(user.get("preferences")),
            sqlite_row_dict_to_json_dict(identity) if identity else None,
        )

    return await run_read_transaction(database, snapshot)


async def read_managed_entry(
    database: aiosqlite.Connection, user_id: int, entry_id: str
) -> JSONDict:
    async def snapshot(connection: aiosqlite.Connection) -> JSONDict:
        rows = await query_to_dicts(
            connection,
            f"SELECT {ENTITY_COLUMNS} FROM mcp_memory_entities WHERE user_id = ? AND id = ?",
            (user_id, entry_id),
        )
        if not rows:
            raise memory_management_error(
                "memory_entry_missing", "This memory no longer exists. Refresh the library.", 404
            )
        return (await read_entity_details_for_rows(connection, rows, managed=True))[0]

    return await run_read_transaction(database, snapshot)


def sync_read_management_library(conn: sqlite3.Connection, user_id: int) -> JSONDict:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"SELECT {ENTITY_COLUMNS} FROM mcp_memory_entities WHERE user_id = ? ORDER BY updated_at_ms DESC, created_at_ms DESC, id ASC",
            (user_id,),
        )
    )
    observations = sync_fetch_all_as_dicts(
        conn.execute(
            "SELECT o.entity_id, o.id, o.content, o.source, o.created_at_ms FROM mcp_memory_observations o JOIN mcp_memory_entities e ON e.id = o.entity_id WHERE e.user_id = ? ORDER BY o.created_at_ms DESC, o.id ASC",
            (user_id,),
        )
    )
    relations = sync_fetch_all_as_dicts(
        conn.execute(
            "SELECT r.id, r.from_entity_id, r.to_entity_id, r.relation_type, r.created_at_ms, src.name AS from_entity, dst.name AS to_entity FROM mcp_memory_relations r JOIN mcp_memory_entities src ON src.id = r.from_entity_id JOIN mcp_memory_entities dst ON dst.id = r.to_entity_id WHERE src.user_id = ? AND dst.user_id = ?",
            (user_id, user_id),
        )
    )
    observations_by_entity: dict[str, list[SQLiteRowDict]] = {}
    outbound_by_entity: dict[str, list[SQLiteRowDict]] = {}
    inbound_by_entity: dict[str, list[SQLiteRowDict]] = {}
    append_grouped_memory_rows(observations_by_entity, observations, "entity_id")
    append_grouped_memory_rows(outbound_by_entity, relations, "from_entity_id")
    append_grouped_memory_rows(inbound_by_entity, relations, "to_entity_id")
    entries = [
        shape_managed_entry(
            row,
            observations_by_entity.get(str(row["id"]), []),
            outbound_by_entity.get(str(row["id"]), []) + inbound_by_entity.get(str(row["id"]), []),
        )
        for row in rows
    ]
    user = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT preferences FROM webui_users WHERE id = ? AND account_type = 'human'",
            (user_id,),
        )
    )
    if user is None:
        raise memory_management_error(
            "memory_user_missing", "Sign in again to manage your memories.", 401
        )
    identity = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT user_display_name FROM webui_chat_identity_defaults WHERE user_id = ?",
            (user_id,),
        )
    )
    return build_management_library(
        entries,
        decode_stored_user_preferences(user.get("preferences")),
        sqlite_row_dict_to_json_dict(identity) if identity else None,
    )
