"""SoAI - Knowledge attachment task cancellation [backend/features/api/runtime/knowledge_attachment_task_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task_cancellation import cancel
from features.api.runtime.conversation_access import require_conversation_access_context

if TYPE_CHECKING:
    from fastapi import Request

    from core.attachments.protocols_database import (
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from features.api.runtime.context import ApiContext

__all__ = (
    "KnowledgeAttachmentCancellationTarget",
    "cancel_knowledge_attachment_tasks",
    "resolve_knowledge_cancellation_target",
)


@dataclass(frozen=True, slots=True)
class KnowledgeAttachmentCancellationTarget:
    repository: DatabaseConversationKnowledgeAttachmentsProtocol
    resolved_conv_id: str
    active_task_ids: tuple[str, ...]


async def resolve_knowledge_cancellation_target(
    request: Request,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> KnowledgeAttachmentCancellationTarget:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    repository = api_context.dependencies.database_conversation_knowledge_attachments
    active_task_ids = await repository.list_active_knowledge_attachment_task_ids(
        conv_id=conversation_context.resolved_conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    return KnowledgeAttachmentCancellationTarget(
        repository=repository,
        resolved_conv_id=conversation_context.resolved_conv_id,
        active_task_ids=tuple(active_task_ids),
    )


async def cancel_knowledge_attachment_tasks(
    task_registry: TaskRegistryLifecycleView,
    *,
    task_ids: Iterable[str],
    reason: str,
) -> None:
    normalized_task_ids = sorted(
        {task_id.strip() for task_id in task_ids if isinstance(task_id, str) and task_id.strip()}
    )
    for task_id in normalized_task_ids:
        await cancel(task_registry, task_id, reason=reason)
