"""SoAI - Database task repository active query service methods [backend/database/repositories/tasks/service_active_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.tasks import active_queries, counts, internal_protocols

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "count_running_orchestrated_inference_tasks_for_owner",
    "query_active_cancellation_ids",
    "query_active_tasks_by_type",
    "query_active_tasks_for_cancellation_id",
)


async def query_active_tasks_for_cancellation_id(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    cancellation_id: str,
    *,
    after_created_at_ms: int = 0,
    after_task_id: str = "",
    limit: int = 1000,
) -> list[JSONDict]:
    return await self.core.reader.execute_read(
        active_queries.query_active_tasks_for_cancellation_id_keyset_query,
        cancellation_id,
        after_created_at_ms=after_created_at_ms,
        after_task_id=after_task_id,
        limit=limit,
    )


async def query_active_tasks_by_type(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_type: str,
    *,
    after_created_at_ms: int = 0,
    after_task_id: str = "",
    limit: int = 1000,
) -> list[JSONDict]:
    return await self.core.reader.execute_read(
        active_queries.query_active_tasks_by_type_keyset_query,
        task_type,
        after_created_at_ms=after_created_at_ms,
        after_task_id=after_task_id,
        limit=limit,
    )


async def count_running_orchestrated_inference_tasks_for_owner(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    owner_type: str,
    owner_id: str,
) -> int:
    return await self.core.reader.execute_read(
        counts.count_running_orchestrated_inference_tasks_for_owner_query,
        owner_type,
        owner_id,
    )


async def query_active_cancellation_ids(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    *,
    include_internal: bool,
    limit: int = 200000,
) -> list[str]:
    return await self.core.reader.execute_read(
        active_queries.query_active_cancellation_ids_query,
        include_internal=include_internal,
        limit=limit,
    )
