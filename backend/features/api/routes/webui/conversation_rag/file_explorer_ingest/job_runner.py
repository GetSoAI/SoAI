"""SoAI - WebUI File Explorer to RAG ingest job runner [backend/features/api/routes/webui/conversation_rag/file_explorer_ingest/job_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Request

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_progress
from features.api.routes.webui.conversation_rag.file_explorer_ingest.job_ingest import (
    ingest_files_under_path,
)
from features.api.routes.webui.conversation_rag.file_explorer_ingest.job_steps import (
    count_files_under_path,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_failures import (
    finalize_knowledge_attachment_task_failure,
)
from features.api.routes.webui.rag_dependencies import require_rag_engine
from features.api.runtime.context import ApiContext

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = ("run_rag_file_explorer_ingest_job",)

LOGGER_NAME = "SoAI.features.api.job_runner"
OPERATION = "webui.conversation_rag.file_explorer_ingest.run_job"


async def run_rag_file_explorer_ingest_job(
    *,
    request: Request,
    api_context: ApiContext,
    task: Task,
    resolved_conv_id: str,
    user_id: int,
    workspace_path: str,
    root_virtual_path: str,
    recursive: bool,
    knowledge_attachment_id: str,
    client_batch_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    registry = api_context.dependencies.task_registry
    file_explorer_core = api_context.dependencies.file_explorer_core
    if file_explorer_core is None:
        await finalize(
            registry,
            task.task_id,
            TaskStatus.FAILED,
            error_message="File explorer is unavailable.",
        )
        await finalize_knowledge_attachment_task_failure(
            api_context=api_context,
            task_id=task.task_id,
            processing_state="error",
            terminal_item_status="error",
            error_message="File explorer is unavailable.",
        )
        return
    rag_engine = require_rag_engine(request, api_context)
    max_file_bytes = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.FILE,
    )
    try:
        root_scope = file_explorer_core.create_workspace_scope(workspace_path)
        await update_progress(
            registry,
            task.task_id,
            progress_current=0,
            percent_override=0,
            status_message="Starting import",
            details=f"Path: {root_virtual_path}",
        )
        total_files, skipped_oversize, total_bytes = await count_files_under_path(
            file_explorer_core=file_explorer_core,
            root_scope=root_scope,
            root_virtual_path=root_virtual_path,
            recursive=recursive,
            max_file_bytes=max_file_bytes,
            logger=logger,
            task_registry=registry,
            task_id=task.task_id,
        )
        await update_progress(
            registry,
            task.task_id,
            progress_current=10,
            percent_override=10,
            status_message="Scan complete",
            details=f"Files: {total_files} • Total bytes: {total_bytes} • Skipped: {skipped_oversize}",
        )
        result = await ingest_files_under_path(
            api_context=api_context,
            rag_engine=rag_engine,
            file_explorer_core=file_explorer_core,
            root_scope=root_scope,
            resolved_conv_id=resolved_conv_id,
            user_id=user_id,
            root_virtual_path=root_virtual_path,
            recursive=recursive,
            max_file_bytes=max_file_bytes,
            task_registry=registry,
            task_id=task.task_id,
            logger=logger,
            total_files=total_files,
            knowledge_attachment_id=knowledge_attachment_id,
            client_batch_id=client_batch_id,
        )
        await finalize(
            registry,
            task.task_id,
            TaskStatus.COMPLETED,
            result=result,
            status_message="Import queued",
        )
    except asyncio.CancelledError:
        await finalize(
            registry,
            task.task_id,
            TaskStatus.CANCELLED,
            error_message="Import cancelled.",
        )
        await finalize_knowledge_attachment_task_failure(
            api_context=api_context,
            task_id=task.task_id,
            processing_state="cancelled",
            terminal_item_status="cancelled",
            error_message="Import cancelled.",
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="RAG File Explorer ingest job failed.",
            operation=OPERATION,
            details={"task_id": task.task_id, "conv_id": resolved_conv_id},
        )
        await finalize(
            registry,
            task.task_id,
            TaskStatus.FAILED,
            error_message=str(coerced.message),
        )
        await finalize_knowledge_attachment_task_failure(
            api_context=api_context,
            task_id=task.task_id,
            processing_state="error",
            terminal_item_status="error",
            error_message=str(coerced.message),
        )
