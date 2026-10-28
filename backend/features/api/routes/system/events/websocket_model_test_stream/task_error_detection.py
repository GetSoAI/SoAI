"""SoAI - WebSocket model test stream task error detection [backend/features/api/routes/system/events/websocket_model_test_stream/task_error_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exceptions import ApiError
from core.errors.public_projection import project_public_error
from core.tasks.enums import TaskStatus
from core.tasks.task_public_fields import resolve_public_task_terminal_fields

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext

__all__ = ("raise_terminal_model_test_task_error",)


async def raise_terminal_model_test_task_error(
    *,
    api_context: ApiContext,
    task_id: str,
    operation: str,
) -> None:
    task = await api_context.dependencies.task_registry.get(task_id, force_refresh=True)
    if task is None or task.status == TaskStatus.COMPLETED:
        return
    if not task.status.is_terminal():
        return
    terminal_fields = resolve_public_task_terminal_fields(task)
    message = (terminal_fields.error_message or terminal_fields.status_message or "").strip()
    if task.status == TaskStatus.CANCELLED:
        raise ApiError(
            message or "Model test stream was cancelled.",
            code=ErrorType.SERVICE_UNAVAILABLE.value,
            http_status=503,
            operation=operation,
        )
    failure = ApiError(
        message or "Model test stream failed.",
        code=task.error_type or ErrorType.SERVER_ERROR.value,
        http_status=(
            task.error_code
            if task.error_code is not None and 400 <= task.error_code <= 599
            else 500
        ),
        operation=operation,
    )
    failure.public_message = (
        task.public_error_message
        or project_public_error(
            ApiError(
                "Model test stream failed.", code=failure.code, http_status=failure.http_status
            )
        ).message
    )
    raise failure
