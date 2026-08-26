"""SoAI - Tool approval user preference helpers [backend/core/tool_approval/preferences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "clear_tool_approval_permissions",
    "read_tool_approval_permissions",
    "write_tool_approval_permission",
)

_CHAT_KEY = "chat"
_PERMISSIONS_KEY = "tool_approval_permissions"


def read_tool_approval_permissions(preferences: JSONValue) -> set[str]:
    if not isinstance(preferences, dict):
        return set()
    chat_value = preferences.get(_CHAT_KEY)
    if not isinstance(chat_value, dict):
        return set()
    permissions_value = chat_value.get(_PERMISSIONS_KEY)
    if not isinstance(permissions_value, dict):
        return set()
    allowed: set[str] = set()
    for raw_key, raw_value in permissions_value.items():
        if not isinstance(raw_key, str):
            continue
        tool_key = raw_key.strip()
        if not tool_key:
            continue
        if raw_value is True:
            allowed.add(tool_key)
    return allowed


def write_tool_approval_permission(preferences: JSONDict, tool_key: str) -> None:
    normalized_tool_key = tool_key.strip()
    if not normalized_tool_key:
        return
    chat_value = preferences.get(_CHAT_KEY)
    chat_preferences = dict(chat_value) if isinstance(chat_value, dict) else {}
    permissions_value = chat_preferences.get(_PERMISSIONS_KEY)
    permissions = dict(permissions_value) if isinstance(permissions_value, dict) else {}
    permissions[normalized_tool_key] = True
    chat_preferences[_PERMISSIONS_KEY] = permissions
    preferences[_CHAT_KEY] = chat_preferences


def clear_tool_approval_permissions(preferences: JSONDict) -> None:
    chat_value = preferences.get(_CHAT_KEY)
    if not isinstance(chat_value, dict):
        return
    if _PERMISSIONS_KEY not in chat_value:
        return
    chat_preferences = dict(chat_value)
    chat_preferences.pop(_PERMISSIONS_KEY, None)
    preferences[_CHAT_KEY] = chat_preferences
