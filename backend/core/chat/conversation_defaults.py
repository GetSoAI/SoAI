"""SoAI - Chat last-used conversation defaults preferences [backend/core/chat/conversation_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_chat_auto_title_generation_enabled",
    "read_chat_conversation_defaults_model_settings",
    "read_chat_conversation_defaults_rag_config",
    "read_chat_conversation_defaults_snapshot",
    "read_chat_new_conversation_inherit_last_settings_enabled",
    "write_chat_conversation_defaults_model_settings",
    "write_chat_conversation_defaults_rag_config",
)

_CHAT_KEY = "chat"
_CHAT_PREFERENCES_KEY = "preferences"
_CHAT_PARAMETERS_KEY = "parameters"
_INHERIT_ON_NEW_CONVERSATION_KEY = "new_conversation_inherit_last_settings"
_AUTO_TITLE_GENERATION_KEY = "auto_title_generation"

_DEFAULTS_SNAPSHOT_KEY = "conversation_defaults_v1"
_DEFAULTS_SNAPSHOT_VERSION_KEY = "version"
_DEFAULTS_SNAPSHOT_MODEL_SETTINGS_KEY = "model_settings"
_DEFAULTS_SNAPSHOT_RAG_CONFIG_KEY = "rag_config"

_DEFAULTS_SNAPSHOT_VERSION = 1


def _read_chat_parameters(preferences: JSONValue) -> JSONDict:
    preferences_dict = coerce_json_dict(preferences) or {}
    chat = coerce_json_dict(preferences_dict.get(_CHAT_KEY)) or {}
    chat_preferences = coerce_json_dict(chat.get(_CHAT_PREFERENCES_KEY)) or {}
    parameters = coerce_json_dict(chat_preferences.get(_CHAT_PARAMETERS_KEY)) or {}
    return dict(parameters)


def read_chat_new_conversation_inherit_last_settings_enabled(preferences: JSONValue) -> bool:
    raw_value = _read_chat_parameters(preferences).get(_INHERIT_ON_NEW_CONVERSATION_KEY)
    if isinstance(raw_value, bool):
        return raw_value
    return True


def read_chat_auto_title_generation_enabled(preferences: JSONValue) -> bool:
    raw_value = _read_chat_parameters(preferences).get(_AUTO_TITLE_GENERATION_KEY)
    if isinstance(raw_value, bool):
        return raw_value
    return True


def read_chat_conversation_defaults_snapshot(preferences: JSONValue) -> JSONDict | None:
    preferences_dict = coerce_json_dict(preferences) or {}
    chat = coerce_json_dict(preferences_dict.get(_CHAT_KEY)) or {}
    snapshot = coerce_json_dict(chat.get(_DEFAULTS_SNAPSHOT_KEY))
    if snapshot is None:
        return None
    version = snapshot.get(_DEFAULTS_SNAPSHOT_VERSION_KEY)
    if version != _DEFAULTS_SNAPSHOT_VERSION:
        return None
    return dict(snapshot)


def read_chat_conversation_defaults_model_settings(preferences: JSONValue) -> JSONDict | None:
    snapshot = read_chat_conversation_defaults_snapshot(preferences)
    if snapshot is None:
        return None
    model_settings = coerce_json_dict(snapshot.get(_DEFAULTS_SNAPSHOT_MODEL_SETTINGS_KEY))
    if model_settings is None:
        return None
    return dict(model_settings)


def read_chat_conversation_defaults_rag_config(preferences: JSONValue) -> JSONDict | None:
    snapshot = read_chat_conversation_defaults_snapshot(preferences)
    if snapshot is None:
        return None
    rag_config = coerce_json_dict(snapshot.get(_DEFAULTS_SNAPSHOT_RAG_CONFIG_KEY))
    if rag_config is None:
        return None
    return dict(rag_config)


def write_chat_conversation_defaults_model_settings(
    preferences: JSONDict,
    model_settings: JSONDict,
) -> None:
    chat_value = preferences.get(_CHAT_KEY)
    chat = dict(chat_value) if isinstance(chat_value, dict) else {}
    snapshot_value = chat.get(_DEFAULTS_SNAPSHOT_KEY)
    snapshot = dict(snapshot_value) if isinstance(snapshot_value, dict) else {}
    snapshot[_DEFAULTS_SNAPSHOT_VERSION_KEY] = _DEFAULTS_SNAPSHOT_VERSION
    snapshot[_DEFAULTS_SNAPSHOT_MODEL_SETTINGS_KEY] = dict(model_settings)
    chat[_DEFAULTS_SNAPSHOT_KEY] = snapshot
    preferences[_CHAT_KEY] = chat


def write_chat_conversation_defaults_rag_config(
    preferences: JSONDict,
    rag_config: JSONDict,
) -> None:
    chat_value = preferences.get(_CHAT_KEY)
    chat = dict(chat_value) if isinstance(chat_value, dict) else {}
    snapshot_value = chat.get(_DEFAULTS_SNAPSHOT_KEY)
    snapshot = dict(snapshot_value) if isinstance(snapshot_value, dict) else {}
    snapshot[_DEFAULTS_SNAPSHOT_VERSION_KEY] = _DEFAULTS_SNAPSHOT_VERSION
    snapshot[_DEFAULTS_SNAPSHOT_RAG_CONFIG_KEY] = dict(rag_config)
    chat[_DEFAULTS_SNAPSHOT_KEY] = snapshot
    preferences[_CHAT_KEY] = chat
