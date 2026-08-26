"""SoAI - Task registry storage helpers (DB interface validation) [backend/tasks/registry/storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect

from core.database.protocols_tasks import DatabaseTasksProtocol
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol

__all__ = (
    "validate_db_tasks_module",
    "validate_event_bus",
    "validate_task_registry_dependencies",
)

_TASK_DB_REQUIRED_METHODS: tuple[str, ...] = (
    "accept_durable_inference_task",
    "claim_orchestrator_queue_items",
    "cleanup_expired_unified_tasks",
    "count_running_orchestrated_inference_tasks_for_owner",
    "create_unified_task",
    "delete_unified_task",
    "finalize_orchestrator_queue_item",
    "finalize_unified_task",
    "get_unified_task",
    "get_unified_tasks_by_ids",
    "mark_orchestrator_queue_item_prefetched_if_leased",
    "mark_orchestrator_queue_item_running_if_leased",
    "query_prefetched_orchestrated_task_ids",
    "query_active_cancellation_ids",
    "query_active_tasks_by_type",
    "query_active_tasks_for_cancellation_id",
    "query_stuck_active_tasks",
    "query_unified_tasks",
    "reconcile_terminal_background_responses",
    "recover_expired_orchestrator_queue_items",
    "release_orchestrator_queue_item_lease",
    "requeue_orchestrated_inference_task",
    "update_cancellation_requested_at_ms",
    "update_cancellation_requested_at_ms_for_cancellation_id",
    "update_orchestration_state",
    "update_unified_task_status",
)


def validate_db_tasks_module(database_tasks: DatabaseTasksProtocol) -> None:
    missing: list[str] = []
    non_async: list[str] = []
    resolved_members = dict(inspect.getmembers(database_tasks))
    for method_name in _TASK_DB_REQUIRED_METHODS:
        method = resolved_members.get(method_name)
        if method is None or not callable(method):
            missing.append(method_name)
            continue
        if not inspect.iscoroutinefunction(method):
            non_async.append(method_name)
    if missing:
        missing_list = ", ".join(missing)
        raise ValidationError(
            f"database_tasks does not implement the Task DB interface (missing: {missing_list}).",
        )
    if non_async:
        non_async_list = ", ".join(non_async)
        raise ValidationError(
            f"database_tasks Task DB methods must be async (non-async: {non_async_list}).",
        )


def validate_event_bus(event_bus: EventBusProtocol) -> None:
    try:
        publish = event_bus.publish
    except AttributeError:
        publish = None
    if not callable(publish) or not inspect.iscoroutinefunction(publish):
        raise ValidationError("event_bus must provide an awaitable publish(event) method.")


def validate_task_registry_dependencies(
    database_tasks: DatabaseTasksProtocol,
    event_bus: EventBusProtocol,
) -> None:
    validate_db_tasks_module(database_tasks)
    validate_event_bus(event_bus)
