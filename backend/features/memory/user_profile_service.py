"""SoAI - WebUI user memory profile service [backend/features/memory/user_profile_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.chat.conversation_defaults import (
    read_chat_conversation_defaults_model_settings,
)
from core.errors.exceptions import StateError
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.memory.profile_codec import (
    USER_PROFILE_ENTITY_NAME,
    USER_PROFILE_ENTITY_TYPE,
    USER_PROFILE_SOURCE,
    build_profile_form,
    build_profile_observations,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
    )
    from core.mcp.protocols_storage import DatabaseMemoryProtocol
    from core.types.json import JSONDict, JSONValue
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "read_user_memory_snapshot",
    "save_user_profile_memory",
)


def _read_assistant_name_from_preferences(preferences_value: JSONValue) -> str | None:
    model_settings = read_chat_conversation_defaults_model_settings(preferences_value)
    if model_settings is None:
        return None
    identity = coerce_json_dict(model_settings.get("identity"))
    if identity is None:
        return None
    return coerce_optional_trimmed_str(identity.get("assistant_display_name"))


def _read_preferred_name_from_identity_defaults(identity_defaults: JSONValue) -> str | None:
    identity_defaults_dict = coerce_json_dict(identity_defaults)
    if identity_defaults_dict is None:
        return None
    return coerce_optional_trimmed_str(identity_defaults_dict.get("user_display_name"))


async def _read_user_preferences(database_users: DatabaseUsersProtocol, user_id: int) -> JSONValue:
    preferences = await database_users.get_user_preferences(user_id)
    if preferences is None:
        raise StateError("User record is unavailable while reading memory profile defaults.")
    return preferences


async def _save_assistant_name(
    database_users: DatabaseUsersProtocol,
    user_id: int,
    assistant_name: str | None,
) -> None:
    updated = await database_users.set_default_assistant_name(user_id, assistant_name)
    if updated is None:
        raise StateError("Failed to persist assistant display name defaults.")


async def read_user_memory_snapshot(
    database_memory: DatabaseMemoryProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_users: DatabaseUsersProtocol,
    user_id: int,
) -> JSONDict:
    entries = await database_memory.list_entities(user_id)
    identity_defaults = await database_chat_identity_defaults.get_identity_defaults(user_id)
    preferences_value = await _read_user_preferences(database_users, user_id)
    preferred_name = _read_preferred_name_from_identity_defaults(identity_defaults)
    assistant_name = _read_assistant_name_from_preferences(preferences_value)
    profile_form = build_profile_form(
        entries,
        preferred_name=preferred_name,
        assistant_name=assistant_name,
    )
    return {"entries": entries, "profile_form": profile_form}


async def save_user_profile_memory(
    database_memory: DatabaseMemoryProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_users: DatabaseUsersProtocol,
    user_id: int,
    payload: JSONDict,
) -> JSONDict:
    observations = build_profile_observations(payload)
    preferred_name = coerce_optional_trimmed_str(payload.get("preferred_name"))
    assistant_name = coerce_optional_trimmed_str(payload.get("assistant_name"))
    current_identity_defaults = await database_chat_identity_defaults.get_identity_defaults(user_id)
    if _read_preferred_name_from_identity_defaults(current_identity_defaults) != preferred_name:
        await database_chat_identity_defaults.upsert_user_display_name(
            user_id,
            preferred_name,
        )
    await _save_assistant_name(
        database_users,
        user_id,
        assistant_name,
    )
    existing_entries = await database_memory.list_entities(user_id)
    existing_profile_form = build_profile_form(
        existing_entries,
        preferred_name=None,
        assistant_name=None,
    )
    existing_observations = build_profile_observations(existing_profile_form)
    if existing_observations != observations:
        await database_memory.replace_entity_observations_for_source(
            user_id,
            USER_PROFILE_ENTITY_NAME,
            USER_PROFILE_SOURCE,
            observations,
            USER_PROFILE_ENTITY_TYPE if observations else None,
            not observations,
        )
    return await read_user_memory_snapshot(
        database_memory,
        database_chat_identity_defaults,
        database_users,
        user_id,
    )
