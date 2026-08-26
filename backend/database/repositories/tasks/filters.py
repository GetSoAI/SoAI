"""SoAI - Unified tasks filter clause builder [backend/database/repositories/tasks/filters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    active_task_status_placeholders,
)

if TYPE_CHECKING:
    type SqlParam = int | float | str | None

__all__ = (
    "build_unified_tasks_visible_to_user_where_clause",
    "build_unified_tasks_where_clause",
)


def build_unified_tasks_where_clause(
    *,
    user_id: int | None = None,
    status: str | None = None,
    task_type: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
    cancellation_id: str | None = None,
    active_only: bool = False,
    exclude_cancellation_requested: bool = False,
) -> tuple[str, list[SqlParam]]:
    conditions: list[str] = []
    params: list[SqlParam] = []
    if active_only:
        conditions.append(f"status IN ({active_task_status_placeholders()})")
        params.extend(ACTIVE_TASK_STATUS_VALUES)
    elif status is not None:
        conditions.append("status = ?")
        params.append(status)
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if task_type is not None:
        conditions.append("task_type = ?")
        params.append(task_type)
    if owner_type is not None:
        conditions.append("owner_type = ?")
        params.append(owner_type)
    if owner_id is not None:
        conditions.append("owner_id = ?")
        params.append(owner_id)
    if cancellation_id is not None:
        conditions.append("cancellation_id = ?")
        params.append(cancellation_id)
    if exclude_cancellation_requested:
        conditions.append("cancellation_requested_at_ms IS NULL")
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    return where_clause, params


def build_unified_tasks_visible_to_user_where_clause(
    *,
    user_id: int,
    include_system: bool,
    task_type: str | None = None,
    active_only: bool = False,
    exclude_cancellation_requested: bool = False,
) -> tuple[str, list[SqlParam]]:
    if user_id < 0:
        raise ValidationError("user_id must be non-negative.")
    conditions: list[str] = []
    params: list[SqlParam] = []
    if active_only:
        conditions.append(f"status IN ({active_task_status_placeholders()})")
        params.extend(ACTIVE_TASK_STATUS_VALUES)
    if task_type is not None:
        conditions.append("task_type = ?")
        params.append(task_type)
    if not include_system:
        conditions.append("user_id = ?")
        params.append(user_id)
    if exclude_cancellation_requested:
        conditions.append("cancellation_requested_at_ms IS NULL")
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    return where_clause, params
