"""SoAI - WebSocket model test stream task error detection [backend/features/api/routes/system/events/websocket_model_test_stream/task_error_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exceptions import ApiError
from core.tasks.enums import TaskStatus

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
    message = (task.error_message or task.status_message or "").strip()
    if task.status == TaskStatus.CANCELLED:
        raise ApiError(
            message or "Model test stream was cancelled.",
            code=ErrorType.SERVICE_UNAVAILABLE.value,
            http_status=503,
            operation=operation,
        )
    raise ApiError(
        message or "Model test stream failed.",
        code=ErrorType.SERVER_ERROR.value,
        http_status=500,
        operation=operation,
    )
