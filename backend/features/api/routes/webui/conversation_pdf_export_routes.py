"""SoAI - Conversation PDF export WebUI routes [backend/features/api/routes/webui/conversation_pdf_export_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, PayloadTooLargeError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.export import build_content_disposition_attachment
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_CONVERSATION_PDF_EXPORT
from features.api.routes.tasks.task_visibility_rules import require_task_visibility
from features.api.routes.webui.conversation_pdf_export_metadata import (
    parse_conversation_pdf_export_metadata,
    require_expected_conversation_pdf_digest,
)
from features.api.routes.webui.conversation_pdf_export_rendering import (
    run_conversation_pdf_export_render_task,
)
from features.api.routes.webui.conversation_pdf_export_snapshot import (
    validate_conversation_pdf_export_snapshot,
)
from features.api.routes.webui.conversation_pdf_export_staging import (
    stage_conversation_pdf_export_upload,
)
from features.api.routes.webui.conversation_pdf_export_tasks import (
    create_admitted_conversation_pdf_export_task,
    fail_conversation_pdf_export_upload,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.responses import create_task_accepted_response
from features.api.runtime.task_execution import finalize_task_safely
from features.conversation_export.artifacts import (
    build_conversation_pdf_artifact_paths,
    cleanup_conversation_pdf_task_directory,
    require_export_artifact_path,
    write_conversation_pdf_task_marker,
)
from features.conversation_export.settings import resolve_conversation_pdf_export_settings

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.conversation_pdf_export_routes"
OPERATION = "webui.conversation_pdf_export"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/export/pdf",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.OPENAI_API),
    )
    async def start_conversation_pdf_export(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        settings = resolve_conversation_pdf_export_settings(api_context.dependencies.config)
        registry, task, trace_id = await create_admitted_conversation_pdf_export_task(
            request=request,
            api_context=api_context,
            current_user=current_user,
            settings=settings,
        )
        paths = build_conversation_pdf_artifact_paths(settings.temp_dir, task.task_id)
        write_conversation_pdf_task_marker(paths.task_dir)
        try:
            staged = await stage_conversation_pdf_export_upload(
                request=request,
                api_context=api_context,
                task=task,
                settings=settings,
                paths=paths,
            )
            metadata = parse_conversation_pdf_export_metadata(staged.fields)
            require_expected_conversation_pdf_digest(
                metadata.expected_html_sha256,
                staged.html_sha256,
                "PDF export HTML digest does not match.",
            )
            require_expected_conversation_pdf_digest(
                metadata.expected_cover_sha256,
                staged.cover_sha256,
                "PDF export cover digest does not match.",
            )
            await validate_conversation_pdf_export_snapshot(
                api_context=api_context,
                user_id=current_user["id"],
                metadata=metadata,
            )
        except (ConflictError, PayloadTooLargeError, ValidationError) as exception:
            cleanup_conversation_pdf_task_directory(paths.task_dir)
            return await fail_conversation_pdf_export_upload(
                request=request,
                registry=registry,
                task=task,
                trace_id=trace_id,
                exception=exception,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            cleanup_conversation_pdf_task_directory(paths.task_dir)
            await finalize_task_safely(
                registry=registry,
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                operation="webui.conversation_pdf_export.stage_fail",
                trace_id=trace_id,
                error_code=500,
                error_message=str(exception),
                status_message="PDF export upload failed",
            )
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Conversation PDF export upload failed.",
                operation=OPERATION,
                trace_id=trace_id,
                details={"task_id": task.task_id},
            )
            raise_server_error(request, "Failed to stage PDF export.")
        render_coroutine = run_conversation_pdf_export_render_task(
            api_context=api_context,
            registry=registry,
            task_id=task.task_id,
            trace_id=trace_id,
            settings=settings,
            paths=paths,
            metadata=metadata,
            staged=staged,
            user_id=current_user["id"],
        )
        try:
            render_task = spawn_tracked_task(
                render_coroutine,
                name=f"conversation-pdf-export-{task.task_id}",
                logger=get_logger(LOGGER_NAME),
                cancellation_binder=api_context.dependencies.task_cancellation_binder,
                cancellation_id=task.cancellation_id,
                owner="conversation_pdf_export",
                metadata={"task_id": task.task_id},
                finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            render_coroutine.close()
            cleanup_conversation_pdf_task_directory(paths.task_dir)
            await finalize_task_safely(
                registry=registry,
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                operation="webui.conversation_pdf_export.spawn_fail",
                trace_id=trace_id,
                error_code=500,
                error_message=str(exception),
                status_message="PDF export failed",
            )
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Conversation PDF export render task spawn failed.",
                operation=OPERATION,
                trace_id=trace_id,
                details={"task_id": task.task_id},
            )
            raise_server_error(request, "Failed to start PDF export.")
        api_context.dependencies.application_control.track_background_task(render_task)
        return create_task_accepted_response(
            task_id=task.task_id,
            commit_deadline_ts_ms=None,
            extra={
                "download_url": f"/api/v1/webui/conversations/export/pdf/{task.task_id}/download",
            },
        )

    @routers.webui.get(
        "/conversations/export/pdf/{task_id}/download",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API),
    )
    async def download_conversation_pdf_export(
        request: Request,
        task_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> FileResponse:
        task = await api_context.dependencies.task_registry.get(task_id, force_refresh=True)
        if task is None:
            raise_not_found(request, "PDF export task was not found.")
        require_task_visibility(request, task, current_user)
        if task.task_type != TASK_TYPE_CONVERSATION_PDF_EXPORT:
            raise_invalid_request(request, "Task is not a conversation PDF export.")
        if task.status != TaskStatus.COMPLETED or task.result is None:
            raise_invalid_request(request, "PDF export is not ready.")
        pdf_path_value = task.result.get("pdf_path")
        pdf_path = pdf_path_value if isinstance(pdf_path_value, str) else ""
        filename_value = task.result.get("filename")
        download_filename = (
            filename_value
            if isinstance(filename_value, str) and filename_value
            else "conversation.pdf"
        )
        settings = resolve_conversation_pdf_export_settings(api_context.dependencies.config)
        artifact_path = require_export_artifact_path(settings.temp_dir, pdf_path)
        headers = {
            "Content-Disposition": build_content_disposition_attachment(download_filename),
            "Cache-Control": "no-store",
        }
        return FileResponse(
            artifact_path,
            media_type="application/pdf",
            headers=headers,
        )
