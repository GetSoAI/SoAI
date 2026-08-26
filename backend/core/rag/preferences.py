"""SoAI - RAG user preference helpers [backend/core/rag/preferences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_chat_default_embedding_model",
    "write_chat_default_embedding_model",
)


def read_chat_default_embedding_model(preferences: JSONValue) -> str:
    if not isinstance(preferences, dict):
        return ""
    chat_value = preferences.get("chat")
    if not isinstance(chat_value, dict):
        return ""
    value = chat_value.get("default_embedding_model")
    if not isinstance(value, str):
        return ""
    return value.strip()


def write_chat_default_embedding_model(preferences: JSONDict, model_id: str) -> None:
    chat_value = preferences.get("chat")
    chat_preferences = dict(chat_value) if isinstance(chat_value, dict) else {}
    chat_preferences["default_embedding_model"] = model_id
    preferences["chat"] = chat_preferences
