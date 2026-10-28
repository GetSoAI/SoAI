"""SoAI - Plugin API task finalization and response wiring [backend/features/api/routes/plugins/plugin_task_api_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import Request

from core.tasks.enums import TaskStatus
from features.api.runtime.task_api_errors import raise_api_error_with_task
from features.api.runtime.task_execution import finalize_task_safely

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.routes.plugins.plugin_task_preparation import PreparedPluginTask

__all__ = ("raise_prepared_plugin_task_error",)


async def raise_prepared_plugin_task_error(
    request: Request,
    *,
    prepared_task: PreparedPluginTask,
    status_code: int,
    error_type: str,
    error_message: str,
    operation: str,
    details: dict[str, JSONValue],
    extra: JSONDict | None = None,
) -> NoReturn:
    task_id = prepared_task.task_id
    await finalize_task_safely(
        registry=prepared_task.registry,
        task_id=task_id,
        status=TaskStatus.FAILED,
        operation=operation,
        trace_id=prepared_task.trace_id,
        error_code=status_code,
        error_message=error_message,
        details=details,
    )
    raise_api_error_with_task(
        request,
        status_code,
        error_type,
        error_message,
        task_id=task_id,
        extra=extra,
    )
