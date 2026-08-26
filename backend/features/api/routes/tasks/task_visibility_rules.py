"""SoAI - Task visibility rules [backend/features/api/routes/tasks/task_visibility_rules.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.tasks.api_queries import (
    build_task_visibility_user_payload,
    get_task_visibility_error,
    parse_task_type_filter_value,
)
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId
from features.api.runtime.errors import raise_bad_request, raise_forbidden

if TYPE_CHECKING:
    from features.api.runtime.current_user import CurrentUser

__all__ = ()


def parse_task_type_filter(
    request: Request,
    task_type: str | None,
    task_catalog: TaskTypeCatalog,
) -> TaskTypeId | None:
    try:
        return parse_task_type_filter_value(task_type, task_catalog)
    except ValidationError:
        raise_bad_request(
            request,
            f"Unknown task type: {task_type}",
            error_type="invalid_task_type",
        )


def require_task_visibility(request: Request, task: Task, current_user: CurrentUser) -> None:
    message = get_task_visibility_error(task, build_task_visibility_user_payload(current_user))
    if message:
        raise_forbidden(request, message, error_type="forbidden")
