"""SoAI - Conversation interaction task validation [backend/features/chat/interaction_task_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_interactions import (
    normalize_interaction_type,
    resolve_interaction_error_messages,
)
from core.errors.exceptions import NotFoundError, ValidationError
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION

if TYPE_CHECKING:
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task

__all__ = ("require_conversation_interaction_task",)


async def require_conversation_interaction_task(
    task_registry: TaskRegistryProtocol,
    *,
    conv_id: str,
    user_id: int,
    task_id: str,
    interaction_type: str,
    allow_terminal: bool,
) -> Task:
    not_found_message, invalid_message = resolve_interaction_error_messages(interaction_type)
    task = await task_registry.get(task_id)
    if task is None:
        raise NotFoundError(not_found_message)
    if task.task_type != TASK_TYPE_MCP_ELICITATION:
        raise ValidationError("Task is not an elicitation interaction.")
    if task.owner_type != "conversation" or task.owner_id != conv_id:
        raise ValidationError("Task does not belong to this conversation.")
    if task.user_id != user_id:
        raise ValidationError("Task does not belong to the current user.")
    interaction_key = normalize_interaction_type(task.metadata.get("interaction_type")) or ""
    if interaction_key != interaction_type:
        raise ValidationError(invalid_message)
    if task.status == TaskStatus.INPUT_REQUIRED:
        return task
    if allow_terminal and task.status.is_terminal():
        return task
    raise ValidationError("Task is not awaiting user input.")
