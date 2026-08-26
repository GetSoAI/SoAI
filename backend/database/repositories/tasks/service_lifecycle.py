"""SoAI - Database task lifecycle write boundary [backend/database/repositories/tasks/service_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.openai_responses.background_task_finalization import (
    sync_reconcile_all_terminal_background_responses,
)
from database.repositories.tasks import crud, finalization
from database.repositories.tasks.internal_protocols import (
    DatabaseTasksCoreAndSecretsOwnerProtocol,
)

if TYPE_CHECKING:
    from core.database.task_requests import (
        CreateUnifiedTaskRequest,
        UnifiedTaskFinalizationWriteResult,
    )
    from core.tasks.interaction_mutations import ConversationInteractionMutation

__all__ = (
    "cleanup_expired_unified_tasks",
    "create_unified_task",
    "delete_unified_task",
    "finalize_unified_task",
    "reconcile_terminal_background_responses",
    "update_unified_task_status",
)


async def create_unified_task(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    request: CreateUnifiedTaskRequest,
) -> bool:
    return await self.core.writer.queue_write_operation(
        crud.sync_create_unified_task,
        request,
    )


async def update_unified_task_status(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    task_id: str,
    status: str,
    status_message: str | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_details: str | None = None,
) -> bool:
    return await self.core.writer.queue_write_operation(
        crud.sync_update_unified_task_status,
        task_id,
        status,
        status_message,
        progress_current,
        progress_total,
        progress_details,
    )


async def finalize_unified_task(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    task_id: str,
    status: str,
    result: str | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    status_message: str | None = None,
    mutation_fencing_token: int | None = None,
    interaction_mutation: ConversationInteractionMutation | None = None,
) -> UnifiedTaskFinalizationWriteResult:
    return await self.core.writer.queue_write_operation(
        finalization.sync_finalize_unified_task,
        self.fernets,
        task_id,
        status,
        result,
        error_code,
        error_type,
        error_message,
        status_message,
        mutation_fencing_token,
        interaction_mutation,
    )


async def reconcile_terminal_background_responses(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
) -> int:
    return await self.core.writer.queue_write_operation(
        sync_reconcile_all_terminal_background_responses,
    )


async def delete_unified_task(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    task_id: str,
) -> bool:
    return await self.core.writer.queue_write_operation(
        crud.sync_delete_unified_task,
        task_id,
    )


async def cleanup_expired_unified_tasks(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
) -> int:
    return await self.core.writer.queue_write_operation(
        crud.sync_cleanup_expired_unified_tasks,
    )
