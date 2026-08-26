"""SoAI - Conversation PDF export task helpers [backend/features/api/routes/webui/conversation_pdf_export_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NoReturn

from core.errors.exceptions import ConflictError, PayloadTooLargeError
from core.files.locking import async_guarded_file_lock
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_CONVERSATION_PDF_EXPORT
from features.api.runtime.errors import raise_rate_limit
from features.api.runtime.task_api_errors import raise_api_error_with_task
from features.api.runtime.task_creation_context import (
    create_working_task_from_request_context,
)
from features.api.runtime.task_execution import finalize_task_safely

if TYPE_CHECKING:
    from fastapi import Request

    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser
    from features.conversation_export.settings import ConversationPdfExportSettings

__all__ = (
    "create_admitted_conversation_pdf_export_task",
    "fail_conversation_pdf_export_upload",
)


def _resolve_upload_failure_status(exception: BaseException) -> tuple[int, str, str]:
    if isinstance(exception, PayloadTooLargeError):
        return 413, "payload_too_large", "PDF export upload failed"
    if isinstance(exception, ConflictError):
        return 409, "conflict_error", "PDF export blocked"
    return 422, "invalid_request_error", "PDF export upload failed"


async def _enforce_conversation_pdf_export_admission(
    *,
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    settings: ConversationPdfExportSettings,
) -> None:
    queries = api_context.dependencies.task_registry_queries
    user_count = await queries.count_active_by_user(
        current_user["id"],
        task_type=TASK_TYPE_CONVERSATION_PDF_EXPORT,
    )
    if user_count >= settings.max_active_per_user:
        raise_rate_limit(request, "A conversation PDF export is already running.")
    global_count = await queries.count_active_filtered(
        task_type=TASK_TYPE_CONVERSATION_PDF_EXPORT,
    )
    if global_count >= settings.max_active_global:
        raise_rate_limit(request, "Too many conversation PDF exports are running.")


async def _create_conversation_pdf_export_task(
    *,
    request: Request,
    api_context: ApiContext,
) -> tuple[TaskRegistryProtocol, Task, str | None]:
    created = await create_working_task_from_request_context(
        request=request,
        api_context=api_context,
        task_type=TASK_TYPE_CONVERSATION_PDF_EXPORT,
        status_message="Uploading PDF export",
        metadata={"operation": "conversation_pdf_export"},
        progress_total=100,
    )
    request.state.context.task_id = created.task.task_id
    return created.registry, created.task, created.trace_id


async def create_admitted_conversation_pdf_export_task(
    *,
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    settings: ConversationPdfExportSettings,
) -> tuple[TaskRegistryProtocol, Task, str | None]:
    os.makedirs(settings.temp_dir, exist_ok=True)
    admission_lock_path = os.path.join(settings.temp_dir, "conversation-pdf-admission.lock")
    async with async_guarded_file_lock(admission_lock_path, timeout=30.0):
        await _enforce_conversation_pdf_export_admission(
            request=request,
            api_context=api_context,
            current_user=current_user,
            settings=settings,
        )
        return await _create_conversation_pdf_export_task(
            request=request,
            api_context=api_context,
        )


async def fail_conversation_pdf_export_upload(
    *,
    request: Request,
    registry: TaskRegistryProtocol,
    task: Task,
    trace_id: str | None,
    exception: BaseException,
) -> NoReturn:
    http_status, error_type, status_message = _resolve_upload_failure_status(exception)
    await finalize_task_safely(
        registry=registry,
        task_id=task.task_id,
        status=TaskStatus.FAILED,
        operation="webui.conversation_pdf_export.upload_fail",
        trace_id=trace_id,
        error_code=http_status,
        error_message=str(exception),
        status_message=status_message,
    )
    raise_api_error_with_task(
        request,
        http_status,
        error_type,
        str(exception),
        task_id=task.task_id,
    )
