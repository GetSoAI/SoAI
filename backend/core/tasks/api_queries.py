"""SoAI - Task API query helpers for task listings and snapshots [backend/core/tasks/api_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, TypedDict

from core.errors.exceptions import ValidationError
from core.tasks.api_models import TaskQueryResponse
from core.tasks.identity import build_task_identity_payload
from core.tasks.protocols_query import TaskRegistryQueryView
from core.tasks.task import Task
from core.tasks.task_public_fields import resolve_public_task_terminal_fields
from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId
from core.types.json_value import copy_json_value
from core.types.pydantic_json_value import coerce_to_pydantic_json_dict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ()


class TaskVisibilityUserPayload(TypedDict):
    id: int
    is_admin: bool


def task_to_response(task: Task) -> TaskQueryResponse:
    public_terminal_fields = resolve_public_task_terminal_fields(
        status=task.status,
        error_code=task.error_code,
        error_type=task.error_type,
        status_message=task.status_message,
        error_message=task.error_message,
    )
    identity_payload = build_task_identity_payload(task)
    task_id_value = identity_payload.get("task_id")
    task_id = task_id_value if isinstance(task_id_value, str) else task.task_id
    task_type_value = identity_payload.get("task_type")
    task_type = task_type_value if isinstance(task_type_value, str) else task.task_type
    status_value = identity_payload.get("status")
    status = status_value if isinstance(status_value, str) else task.status.value
    user_id_value = identity_payload.get("user_id")
    user_id = user_id_value if is_strict_int(user_id_value) else task.user_id
    owner_id_value = identity_payload.get("owner_id")
    owner_id = owner_id_value if isinstance(owner_id_value, str) else task.owner_id
    owner_type_value = identity_payload.get("owner_type")
    owner_type = owner_type_value if isinstance(owner_type_value, str) else task.owner_type
    metadata = (
        coerce_to_pydantic_json_dict(
            {key: copy_json_value(value) for key, value in task.metadata.items()},
        )
        if task.metadata
        else {}
    )
    result = (
        coerce_to_pydantic_json_dict(
            {key: copy_json_value(value) for key, value in task.result.items()},
        )
        if task.result is not None
        else None
    )
    return TaskQueryResponse(
        task_id=task_id,
        task_type=task_type,
        status=status,
        user_id=user_id,
        owner_id=owner_id,
        owner_type=owner_type,
        created_at_ms=int(task.created_at_ms),
        updated_at_ms=int(task.updated_at_ms),
        completed_at_ms=int(task.completed_at_ms) if task.completed_at_ms is not None else None,
        progress_current=task.progress_current,
        progress_total=task.progress_total,
        progress_percent=task.progress_percent(),
        status_message=public_terminal_fields.status_message,
        metadata=metadata,
        result=result,
        error_code=task.error_code,
        error_type=task.error_type,
        error_message=public_terminal_fields.error_message,
    )


def get_task_visibility_error(
    task: Task,
    current_user: TaskVisibilityUserPayload,
) -> str | None:
    is_admin = current_user.get("is_admin") is True
    user_id_value = current_user.get("id")
    user_id = user_id_value if is_strict_int(user_id_value) else None
    if task.owner_type == "system":
        if is_admin:
            return None
        if user_id is None or task.user_id != user_id:
            return "Only administrators may access system tasks."
        return None
    if is_admin:
        return None
    if user_id is None or task.user_id != user_id:
        return "Access denied to this task."
    return None


def parse_task_type_filter_value(
    task_type: str | None,
    task_catalog: TaskTypeCatalog,
) -> TaskTypeId | None:
    if not task_type:
        return None
    try:
        return task_catalog.require(task_type)
    except ValidationError as exception:
        raise ValidationError(
            f"Unknown task type: {task_type}",
            details={"task_type": task_type},
        ) from exception


def build_task_visibility_user_payload(
    current_user: Mapping[str, JSONValue] | TaskVisibilityUserPayload,
) -> TaskVisibilityUserPayload:
    user_id_value = current_user.get("id")
    is_admin_value = current_user.get("is_admin")
    return {
        "id": user_id_value if is_strict_int(user_id_value) else 0,
        "is_admin": is_admin_value if isinstance(is_admin_value, bool) else False,
    }


async def query_active_tasks_for_user(
    user_id: int,
    is_admin: bool,
    task_type_filter: TaskTypeId | None,
    effective_limit: int,
    registry: TaskRegistryQueryView,
) -> tuple[Sequence[Task], int]:
    tasks, count = await registry.query_visible_to_user_with_count(
        user_id=user_id,
        include_system=is_admin,
        task_type=task_type_filter,
        active_only=True,
        limit=effective_limit,
    )
    return (tasks, count)
