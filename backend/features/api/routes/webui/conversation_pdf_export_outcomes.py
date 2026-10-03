"""SoAI - Conversation PDF export terminal outcomes [backend/features/api/routes/webui/conversation_pdf_export_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.browser.html_pdf_renderer import PdfBrowserUnavailableError
from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError
from core.errors.external_service_exception import ExternalServiceError
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.errors import TaskFinalizationPersistenceError
from core.tasks.finalization import finalize
from features.api.routes.webui.conversation_pdf_export_rendering import (
    render_conversation_pdf_artifact,
)
from features.conversation_export.artifacts import cleanup_conversation_pdf_task_directory

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from features.api.routes.webui.conversation_pdf_export_metadata import (
        ConversationPdfExportMetadata,
    )
    from features.api.routes.webui.conversation_pdf_export_staging import (
        ConversationPdfStagedUpload,
    )
    from features.api.runtime.context import ApiContext
    from features.conversation_export.artifacts import ConversationPdfArtifactPaths
    from features.conversation_export.settings import ConversationPdfExportSettings

__all__ = ("run_conversation_pdf_export_render_task",)

LOGGER_NAME = "SoAI.features.api.conversation_pdf_export_outcomes"
OPERATION_RENDER = "webui.conversation_pdf_export.render"


async def run_conversation_pdf_export_render_task(
    *,
    api_context: ApiContext,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    settings: ConversationPdfExportSettings,
    paths: ConversationPdfArtifactPaths,
    metadata: ConversationPdfExportMetadata,
    staged: ConversationPdfStagedUpload,
    user_id: int,
) -> None:
    try:
        result = await render_conversation_pdf_artifact(
            api_context=api_context,
            registry=registry,
            task_id=task_id,
            settings=settings,
            paths=paths,
            metadata=metadata,
            staged=staged,
            user_id=user_id,
        )
    except (asyncio.CancelledError, TaskCancelledError) as exception:
        terminal = await finalize(
            registry,
            task_id,
            TaskStatus.CANCELLED,
            error_message="PDF export was cancelled.",
            status_message="PDF export cancelled",
        )
        if terminal is None:
            raise TaskFinalizationPersistenceError(
                "PDF export task is missing after cancellation finalization.",
                details={"task_id": task_id},
            ) from exception
        if terminal.status is not TaskStatus.COMPLETED:
            cleanup_conversation_pdf_task_directory(paths.task_dir)
        raise
    except Exception as exception:
        if isinstance(exception, ConflictError):
            error_code = 409
            error_type = None
            error_message = str(exception)
            status_message = "PDF export blocked"
        elif isinstance(exception, PdfBrowserUnavailableError):
            error_code = exception.http_status
            error_type = str(exception.code)
            error_message = str(exception)
            status_message = "PDF export browser unavailable"
        else:
            error_code = 500
            error_type = None
            error_message = "PDF export failed."
            status_message = "PDF export failed"
        terminal = await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            status_message=status_message,
        )
        if terminal is not None:
            if terminal.status is not TaskStatus.COMPLETED:
                cleanup_conversation_pdf_task_directory(paths.task_dir)
            if error_code == 500 and not isinstance(exception, ExternalServiceError):
                coerced = coerce_to_soai_error(exception, operation=OPERATION_RENDER)
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerced,
                    message="Conversation PDF export failed.",
                    operation=OPERATION_RENDER,
                    trace_id=trace_id,
                    details={"task_id": task_id},
                )
            return
        raise TaskFinalizationPersistenceError(
            "PDF export task is missing after failure finalization.",
            details={"task_id": task_id},
        ) from exception

    terminal = await finalize(
        registry,
        task_id,
        TaskStatus.COMPLETED,
        result=result,
        status_message="PDF export ready",
    )
    if terminal is None:
        raise TaskFinalizationPersistenceError(
            "PDF export task is missing after completion finalization.",
            details={"task_id": task_id},
        )
    if terminal.status is not TaskStatus.COMPLETED:
        cleanup_conversation_pdf_task_directory(paths.task_dir)
