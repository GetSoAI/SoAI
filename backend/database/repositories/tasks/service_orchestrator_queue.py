"""SoAI - Database task repository durable queue service methods [backend/database/repositories/tasks/service_orchestrator_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.tasks import (
    active_queries,
    internal_protocols,
    orchestrator_queue_leases,
    orchestrator_queue_phases,
    orchestrator_queue_requeue,
    queries,
)

if TYPE_CHECKING:
    from core.database.task_requests import DurableQueueClaim
    from core.orchestrator.request_priority import RequestPriority
    from core.types.json import JSONDict

__all__ = (
    "claim_orchestrator_queue_items",
    "finalize_orchestrator_queue_item",
    "get_unified_tasks_by_ids",
    "mark_orchestrator_queue_item_prefetched_if_leased",
    "mark_orchestrator_queue_item_running_if_leased",
    "query_prefetched_orchestrated_task_ids",
    "recover_expired_orchestrator_queue_items",
    "release_orchestrator_queue_item_lease",
    "requeue_orchestrated_inference_task",
)


async def get_unified_tasks_by_ids(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_ids: tuple[str, ...],
) -> list[JSONDict]:
    return await self.core.reader.execute_read(queries.get_unified_tasks_by_ids_query, task_ids)


async def claim_orchestrator_queue_items(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    *,
    now_ms: int,
    lease_owner: str,
    lease_ttl_ms: int,
    limit: int,
    request_priority: RequestPriority,
) -> list[DurableQueueClaim]:
    return await self.core.writer.queue_write_operation(
        orchestrator_queue_leases.sync_claim_orchestrator_queue_items,
        now_ms,
        lease_owner,
        lease_ttl_ms,
        limit,
        request_priority,
    )


async def recover_expired_orchestrator_queue_items(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    *,
    now_ms: int,
) -> int:
    return await self.core.writer.queue_write_operation(
        orchestrator_queue_leases.sync_recover_expired_orchestrator_queue_items,
        now_ms,
    )


async def release_orchestrator_queue_item_lease(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    *,
    available_at_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        orchestrator_queue_leases.sync_release_orchestrator_queue_item_lease,
        task_id,
        available_at_ms,
    )


async def mark_orchestrator_queue_item_running_if_leased(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    *,
    lease_owner: str,
) -> bool:
    return await self.core.writer.queue_write_operation(
        orchestrator_queue_phases.sync_mark_orchestrator_queue_item_running_if_leased,
        task_id,
        lease_owner,
    )


async def mark_orchestrator_queue_item_prefetched_if_leased(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    *,
    lease_owner: str,
) -> bool:
    return await self.core.writer.queue_write_operation(
        orchestrator_queue_phases.sync_mark_orchestrator_queue_item_prefetched_if_leased,
        task_id,
        lease_owner,
    )


async def finalize_orchestrator_queue_item(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    status: str,
) -> None:
    await self.core.writer.queue_write_operation(
        orchestrator_queue_phases.sync_finalize_orchestrator_queue_item,
        task_id,
        status,
    )


async def requeue_orchestrated_inference_task(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    *,
    available_at_ms: int,
    status_message: str | None = None,
) -> bool:
    return await self.core.writer.queue_write_operation(
        orchestrator_queue_requeue.sync_requeue_orchestrated_inference_task,
        task_id,
        available_at_ms,
        status_message,
    )


async def query_prefetched_orchestrated_task_ids(
    self: internal_protocols.DatabaseTasksQueueCoreOwnerProtocol,
    *,
    limit: int = 10000,
) -> list[str]:
    return await self.core.reader.execute_read(
        active_queries.query_prefetched_orchestrated_task_ids_query,
        limit=limit,
    )
