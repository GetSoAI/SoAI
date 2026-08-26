"""SoAI - Plugin command context ID helpers [backend/plugins/context_ids.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from plugins.internal_protocols import PluginCommandContextProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "resolve_task_id_from_context",
    "resolve_user_id_from_context",
)


def resolve_task_id_from_context(
    context: PluginCommandContextProtocol | dict[str, JSONValue] | None,
) -> str | None:
    if context is None:
        return None
    task_id_value: JSONValue | None
    if isinstance(context, dict):
        task_id_value = context.get("task_id")
    else:
        task_id_value = context.task_id
    task_id = task_id_value if isinstance(task_id_value, str) else None
    return task_id.strip() if task_id else None


def resolve_user_id_from_context(
    context: PluginCommandContextProtocol | dict[str, JSONValue] | None,
) -> int:
    if context is None:
        return 0
    user_id_value: JSONValue | None
    if isinstance(context, dict):
        user_id_value = context.get("user_id", 0)
    else:
        user_id_value = context.user_id
    return user_id_value if isinstance(user_id_value, int) else 0
