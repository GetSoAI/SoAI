"""SoAI - Expiry of server-owned conversation interactions [backend/tasks/registry/conversation_interaction_expiry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.task_requests import UnifiedTaskQueryRequest
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION
from core.timing.epoch import epoch_ms
from tasks.registry.conversion import task_from_row

__all__ = ("cleanup_expired_conversation_interactions",)

TIMEOUT_ERROR_MESSAGE = "Timed out waiting for user input."


async def cleanup_expired_conversation_interactions(
    registry: TaskRegistryLifecycleView,
    *,
    limit: int = 1000,
) -> int:
    rows = await registry.database_tasks.query_unified_tasks(
        UnifiedTaskQueryRequest(
            status=TaskStatus.INPUT_REQUIRED.value,
            task_type=TASK_TYPE_MCP_ELICITATION,
            owner_type="conversation",
            limit=limit,
        ),
    )
    now_ms = epoch_ms()
    expired_task_ids: list[str] = []
    for row in rows:
        task = task_from_row(registry.task_catalog, row)
        if task.ttl_expires_at_ms is not None and task.ttl_expires_at_ms <= now_ms:
            expired_task_ids.append(task.task_id)
    finalized = 0
    for task_id in expired_task_ids:
        updated = await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=504,
            error_message=TIMEOUT_ERROR_MESSAGE,
            status_message="Timed out",
        )
        if updated is not None:
            finalized += 1
    return finalized
