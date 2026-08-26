"""SoAI - Task registry query request builders [backend/tasks/registry/query_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.task_requests import UnifiedTaskQueryRequest
from core.tasks.enums import TaskStatus
from core.tasks.requests import TaskRegistryFilteredQueryRequest
from core.tasks.type_catalog import TaskTypeId

__all__ = (
    "build_active_query_request",
    "build_filtered_query_request",
    "build_owner_query_request",
    "build_user_query_request",
    "enum_value",
)


def enum_value(enum_obj: TaskStatus | TaskTypeId | None) -> str | None:
    if enum_obj is None:
        return None
    if isinstance(enum_obj, TaskStatus):
        return enum_obj.value
    return enum_obj


def build_user_query_request(
    *,
    user_id: int,
    status: TaskStatus | None,
    task_type: TaskTypeId | None,
    limit: int,
    offset: int,
) -> UnifiedTaskQueryRequest:
    return UnifiedTaskQueryRequest(
        user_id=user_id,
        status=enum_value(status),
        task_type=enum_value(task_type),
        limit=limit,
        offset=offset,
    )


def build_owner_query_request(
    *,
    owner_type: str,
    owner_id: str,
    status: TaskStatus | None,
    limit: int,
    offset: int,
) -> UnifiedTaskQueryRequest:
    return UnifiedTaskQueryRequest(
        owner_type=owner_type,
        owner_id=owner_id,
        status=enum_value(status),
        limit=limit,
        offset=offset,
    )


def build_filtered_query_request(
    request: TaskRegistryFilteredQueryRequest,
) -> UnifiedTaskQueryRequest:
    return UnifiedTaskQueryRequest(
        user_id=request.user_id,
        status=enum_value(request.status),
        task_type=enum_value(request.task_type),
        owner_type=request.owner_type,
        owner_id=request.owner_id,
        cancellation_id=request.cancellation_id,
        limit=request.limit,
        offset=request.offset,
    )


def build_active_query_request(
    *,
    task_type: TaskTypeId | None,
    owner_type: str | None,
    owner_id: str | None,
    cancellation_id: str | None,
    user_id: int | None = None,
    exclude_cancellation_requested: bool = False,
    limit: int = 1000,
    offset: int = 0,
) -> UnifiedTaskQueryRequest:
    return UnifiedTaskQueryRequest(
        user_id=user_id,
        task_type=enum_value(task_type),
        owner_type=owner_type,
        owner_id=owner_id,
        cancellation_id=cancellation_id,
        active_only=True,
        exclude_cancellation_requested=exclude_cancellation_requested,
        limit=limit,
        offset=offset,
    )
