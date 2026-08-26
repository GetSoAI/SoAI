"""SoAI - Shared interaction task access and cleanup helpers [backend/features/chat/interaction_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_interactions import normalize_interaction_type
from core.elicitation_task_scanning import iter_pending_conversation_elicitation_tasks
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION
from features.api.runtime.conversation_access import require_conversation_access
from features.chat.interaction_payloads import extract_interaction_payload
from features.chat.interaction_task_validation import (
    require_conversation_interaction_task,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "list_pending_conversation_interaction_payloads",
    "require_conversation_access_and_list_pending_conversation_interactions",
    "require_conversation_access_and_pending_conversation_interaction_task",
)


async def list_pending_conversation_interaction_payloads(
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
) -> list[JSONDict]:
    tasks = await api_context.dependencies.task_registry_queries.query_active_by_user(
        user_id,
        task_type=TASK_TYPE_MCP_ELICITATION,
        limit=500,
    )
    interactions: list[JSONDict] = []
    for task in iter_pending_conversation_elicitation_tasks(tasks, conv_id=conv_id):
        interaction_key = normalize_interaction_type(task.metadata.get("interaction_type"))
        if interaction_key is None:
            continue
        payload = extract_interaction_payload(task, interaction_key)
        if payload is None:
            continue
        interactions.append(payload)

    def sort_key(item: JSONDict) -> int:
        created_at_value = item.get("created_at_ms")
        if isinstance(created_at_value, int):
            return created_at_value
        if isinstance(created_at_value, float):
            return int(created_at_value)
        if isinstance(created_at_value, str):
            normalized = created_at_value.strip()
            if normalized.isdigit():
                return int(normalized)
        return 0

    interactions.sort(key=sort_key, reverse=True)
    return interactions


async def require_conversation_access_and_list_pending_conversation_interactions(
    request: Request,
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
) -> list[JSONDict]:
    await require_conversation_access(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    return await list_pending_conversation_interaction_payloads(
        api_context,
        conv_id=conv_id,
        user_id=user_id,
    )


async def require_conversation_access_and_pending_conversation_interaction_task(
    request: Request,
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
    task_id: str,
    interaction_type: str,
) -> tuple[TaskRegistryProtocol, Task]:
    await require_conversation_access(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    task_registry = api_context.dependencies.task_registry
    task = await require_conversation_interaction_task(
        task_registry,
        conv_id=conv_id,
        user_id=user_id,
        task_id=task_id,
        interaction_type=interaction_type,
        allow_terminal=False,
    )
    return (task_registry, task)
