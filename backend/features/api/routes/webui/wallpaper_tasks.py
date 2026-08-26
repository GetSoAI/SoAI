"""SoAI - Wallpaper task helpers [backend/features/api/routes/webui/wallpaper_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import TASK_TYPE_WALLPAPER_UPDATE
from features.api.runtime.context import ApiContext
from features.api.runtime.task_creation_context import (
    create_working_task_from_request_context,
)
from features.api.runtime.task_execution import cancel_task_safely, finalize_task_safely

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "cancel_wallpaper_task_after_request_cancellation",
    "create_wallpaper_update_task",
    "finalize_wallpaper_task_cancelled",
    "finalize_wallpaper_task_completed",
    "finalize_wallpaper_task_failed",
)


async def create_wallpaper_update_task(
    *,
    request: Request,
    api_context: ApiContext,
    status_message: str,
    metadata: dict[str, JSONValue],
) -> tuple[TaskRegistryProtocol, Task]:
    created = await create_working_task_from_request_context(
        request=request,
        api_context=api_context,
        task_type=TASK_TYPE_WALLPAPER_UPDATE,
        status_message=status_message,
        metadata=metadata,
    )
    request.state.context.task_id = created.task.task_id
    return created.registry, created.task


async def finalize_wallpaper_task_completed(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    operation: str,
    result: dict[str, JSONValue],
    status_message: str,
) -> None:
    await finalize_task_safely(
        registry=registry,
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        operation=operation,
        trace_id=trace_id,
        result=result,
        status_message=status_message,
        details={"purpose": "wallpaper_update"},
    )


async def finalize_wallpaper_task_failed(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    operation: str,
    error_code: int,
    error_message: str,
) -> None:
    await finalize_task_safely(
        registry=registry,
        task_id=task_id,
        status=TaskStatus.FAILED,
        operation=operation,
        trace_id=trace_id,
        error_code=error_code,
        error_message=error_message,
        details={"purpose": "wallpaper_update"},
    )


async def finalize_wallpaper_task_cancelled(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    operation: str,
    cancel_reason: str,
) -> None:
    await finalize_task_safely(
        registry=registry,
        task_id=task_id,
        status=TaskStatus.CANCELLED,
        operation=operation,
        trace_id=trace_id,
        error_message=cancel_reason,
        status_message=cancel_reason,
        details={"purpose": "wallpaper_update"},
    )


async def cancel_wallpaper_task_after_request_cancellation(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    operation: str,
) -> None:
    await cancel_task_safely(
        registry=registry,
        task_id=task_id,
        reason="Cancelled",
        operation=operation,
        trace_id=trace_id,
        details={"purpose": "wallpaper_update"},
    )
