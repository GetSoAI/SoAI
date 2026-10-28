"""SoAI - WebUI user memory profile service [backend/features/memory/user_profile_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.chat.conversation_defaults import (
    read_chat_conversation_defaults_model_settings,
)
from core.errors.exceptions import StateError
from core.memory.profile_codec import (
    build_profile_form,
)
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str

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
    user_id: int,
    payload: JSONDict,
    expected_revision: str | None = None,
) -> JSONDict:
    return await database_memory.save_profile(user_id, payload, expected_revision)
