"""SoAI - Atomic strict user preference repository operations [backend/database/repositories/users/user_preference_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.chat.conversation_defaults import (
    read_chat_conversation_defaults_model_settings,
    write_chat_conversation_defaults_model_settings,
)
from core.errors.exceptions import StateError
from core.tool_approval.preferences import (
    clear_tool_approval_permissions,
    write_tool_approval_permission,
)
from core.types.json import JSONDict
from core.types.json_value import copy_json_dict
from core.users.preferences import (
    decode_stored_user_preferences,
    merge_user_preference_values,
    serialize_user_preferences,
)
from database.core.query_execution import query_one_to_dict

__all__ = (
    "read_user_preferences_query",
    "sync_clear_tool_approval_permissions",
    "sync_merge_user_preferences",
    "sync_replace_conversation_defaults_model_settings",
    "sync_set_default_assistant_name",
    "sync_write_tool_approval_permission",
)


def _read_user_preferences(
    conn: sqlite3.Connection,
    user_id: int,
) -> JSONDict | None:
    row = conn.execute(
        "SELECT preferences FROM webui_users WHERE id = ? AND account_type = 'human'",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return decode_stored_user_preferences(row[0])


def _write_user_preferences(
    conn: sqlite3.Connection,
    user_id: int,
    preferences: JSONDict,
) -> None:
    updated = conn.execute(
        """
        UPDATE webui_users SET preferences = ?
        WHERE id = ? AND account_type = 'human'
        """,
        (serialize_user_preferences(preferences), user_id),
    ).rowcount
    if updated != 1:
        raise StateError("User disappeared during preference mutation.")


async def read_user_preferences_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT preferences FROM webui_users WHERE id = ? AND account_type = 'human'",
        (user_id,),
    )
    if row is None:
        return None
    return decode_stored_user_preferences(row.get("preferences"))


def sync_merge_user_preferences(
    conn: sqlite3.Connection,
    user_id: int,
    patch: JSONDict,
) -> JSONDict | None:
    current = _read_user_preferences(conn, user_id)
    if current is None:
        return None
    merged = merge_user_preference_values(current, patch)
    if merged != current:
        _write_user_preferences(conn, user_id, merged)
    return merged


def sync_replace_conversation_defaults_model_settings(
    conn: sqlite3.Connection,
    user_id: int,
    model_settings: JSONDict,
) -> JSONDict | None:
    current = _read_user_preferences(conn, user_id)
    if current is None:
        return None
    updated_preferences = copy_json_dict(current)
    write_chat_conversation_defaults_model_settings(updated_preferences, model_settings)
    if updated_preferences != current:
        _write_user_preferences(conn, user_id, updated_preferences)
    return updated_preferences


def sync_set_default_assistant_name(
    conn: sqlite3.Connection,
    user_id: int,
    assistant_name: str | None,
) -> JSONDict | None:
    current = _read_user_preferences(conn, user_id)
    if current is None:
        return None
    model_settings = read_chat_conversation_defaults_model_settings(current) or {}
    next_model_settings = copy_json_dict(model_settings)
    identity_value = next_model_settings.get("identity")
    identity = copy_json_dict(identity_value) if isinstance(identity_value, dict) else {}
    if assistant_name is None:
        identity.pop("assistant_display_name", None)
    else:
        identity["assistant_display_name"] = assistant_name
    if identity:
        next_model_settings["identity"] = identity
    else:
        next_model_settings.pop("identity", None)
    updated_preferences = copy_json_dict(current)
    write_chat_conversation_defaults_model_settings(updated_preferences, next_model_settings)
    if updated_preferences != current:
        _write_user_preferences(conn, user_id, updated_preferences)
    return updated_preferences


def sync_clear_tool_approval_permissions(
    conn: sqlite3.Connection,
    user_id: int,
) -> JSONDict | None:
    current = _read_user_preferences(conn, user_id)
    if current is None:
        return None
    updated_preferences = copy_json_dict(current)
    clear_tool_approval_permissions(updated_preferences)
    if updated_preferences != current:
        _write_user_preferences(conn, user_id, updated_preferences)
    return updated_preferences


def sync_write_tool_approval_permission(
    conn: sqlite3.Connection,
    user_id: int,
    tool_permission: str,
) -> JSONDict:
    current = _read_user_preferences(conn, user_id)
    if current is None:
        raise StateError("Conversation interaction owner is unavailable.")
    updated_preferences = copy_json_dict(current)
    write_tool_approval_permission(updated_preferences, tool_permission)
    if updated_preferences != current:
        _write_user_preferences(conn, user_id, updated_preferences)
    return updated_preferences
