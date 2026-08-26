"""SoAI - Wallpaper upload execution flow [backend/features/api/routes/webui/wallpaper_upload_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError, PayloadTooLargeError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_webui import WallpaperChangedEvent
from core.files.upload_size_validation import UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.wallpaper.settings import WallpaperSettings
from features.api.routes.upload_streaming_progress import StreamingProgressBridge
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)
from features.api.routes.webui.wallpaper_error_handling import (
    handle_wallpaper_disk_space_error,
    handle_wallpaper_exception,
)
from features.api.routes.webui.wallpaper_tasks import (
    cancel_wallpaper_task_after_request_cancellation,
    finalize_wallpaper_task_cancelled,
    finalize_wallpaper_task_completed,
    finalize_wallpaper_task_failed,
)
from features.api.routes.webui.wallpaper_upload_progress import (
    WallpaperUploadProgressState,
    report_wallpaper_upload_progress,
)
from features.api.routes.webui.wallpaper_upload_staging import stage_and_apply_wallpaper
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import create_json_response_with_task_id
from features.api.runtime.task_api_errors import raise_api_error_with_task

__all__ = ("execute_wallpaper_upload_flow",)

LOGGER_NAME_API = "SoAI.features.api.api"
LOGGER_NAME_API_ROUTES_WEBUI = "SoAI.features.api.routes_webui"
LOGGER_NAME_WALLPAPER_UPLOAD_PROGRESS = "SoAI.features.api.wallpaper_upload_progress"

OPERATION_WALLPAPER_UPLOAD = "api_theme.upload_wallpaper"


async def execute_wallpaper_upload_flow(
    *,
    request: Request,
    api_context: ApiContext,
    registry: TaskRegistryProtocol,
    task: Task,
    settings: WallpaperSettings,
) -> JSONResponse:
    context = request.state.context
    try:
        trace_id = context.trace_id
    except AttributeError:
        trace_id = None
    task_id = task.task_id

    if settings.temp_path is None:
        raise_api_error_with_task(
            request,
            422,
            "invalid_request_error",
            "SYSTEM.PATHS.TEMP is not configured.",
            task_id=task_id,
        )
    temp_dir = api_context.dependencies.files.resolve_path(settings.temp_path)
    progress_state = WallpaperUploadProgressState.create()
    reservation_purpose = StreamingUploadReservationPurpose(
        declared_operation="api_theme.upload_wallpaper.stage",
        chunk_operation="api_theme.upload_wallpaper.stage_chunk",
        declared_details={"purpose": "wallpaper_upload_temp_file"},
        chunk_details={"purpose": "wallpaper_upload_temp_file"},
    )
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=temp_dir,
        initial_purpose=reservation_purpose,
    )
    logger_api = get_logger(LOGGER_NAME_API)
    logger_webui = get_logger(LOGGER_NAME_API_ROUTES_WEBUI)
    logger_progress = get_logger(LOGGER_NAME_WALLPAPER_UPLOAD_PROGRESS)

    async def report_upload_progress(bytes_done: int) -> None:
        await report_wallpaper_upload_progress(
            context=context,
            registry=registry,
            task_id=task_id,
            bytes_done=bytes_done,
            declared_total=reservation_tracker.declared_size,
            state=progress_state,
        )

    staged_path: str | None = None
    staged_size: int | None = None
    original_filename: str | None = None

    bridge = StreamingProgressBridge(
        callback=report_upload_progress,
        logger=logger_progress,
        operation="api_theme.upload_wallpaper.progress",
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        cancellation_id=task.cancellation_id,
        owner="wallpaper_upload_progress",
    )
    try:
        bridge.start()
        staged_path, staged_size, original_filename = await stage_and_apply_wallpaper(
            request=request,
            api_context=api_context,
            task=task,
            settings=settings,
            temp_dir=temp_dir,
            reservation_tracker=reservation_tracker,
            bridge=bridge,
            logger_api=logger_api,
            logger_webui=logger_webui,
            cancellation_scope=cancellation_token_scope,
        )
        await finalize_wallpaper_task_completed(
            registry=registry,
            task_id=task_id,
            trace_id=trace_id,
            operation="api_theme.upload_wallpaper.complete_task",
            result={"filename": original_filename or ""},
            status_message="Wallpaper updated",
        )
        await api_context.dependencies.event_bus.publish(WallpaperChangedEvent())
        return create_json_response_with_task_id(
            {"message": "Wallpaper updated successfully.", "task_id": task_id},
            task_id,
        )
    except TaskCancelledError as exception:
        cancel_reason = str(exception).strip() or "Cancelled by user"
        await finalize_wallpaper_task_cancelled(
            registry=registry,
            task_id=task_id,
            trace_id=trace_id,
            operation="api_theme.upload_wallpaper.finalize_cancelled",
            cancel_reason=cancel_reason,
        )
        raise_api_error_with_task(
            request,
            499,
            "cancelled",
            "Wallpaper upload was cancelled.",
            task_id=task_id,
        )
    except asyncio.CancelledError:
        await cancel_wallpaper_task_after_request_cancellation(
            registry=registry,
            task_id=task_id,
            trace_id=trace_id,
            operation="api_theme.upload_wallpaper.cancel_task",
        )
        raise
    except PayloadTooLargeError as exception:
        await finalize_wallpaper_task_failed(
            registry=registry,
            task_id=task.task_id,
            trace_id=trace_id,
            operation="api_theme.upload_wallpaper.fail_task",
            error_code=413,
            error_message=str(exception),
        )
        raise_api_error_with_task(
            request,
            413,
            "payload_too_large",
            UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE,
            task_id=task.task_id,
        )
    except InsufficientDiskSpaceError as exception:
        return await handle_wallpaper_disk_space_error(registry, task.task_id, request, exception)
    except ValidationError as exception:
        await finalize_wallpaper_task_failed(
            registry=registry,
            task_id=task.task_id,
            trace_id=trace_id,
            operation="api_theme.upload_wallpaper.fail_task",
            error_code=422,
            error_message=str(exception),
        )
        raise_api_error_with_task(
            request,
            422,
            "invalid_request_error",
            str(exception.message),
            task_id=task.task_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        await finalize_wallpaper_task_failed(
            registry=registry,
            task_id=task.task_id,
            trace_id=trace_id,
            operation="api_theme.upload_wallpaper.fail_task",
            error_code=500,
            error_message=str(exception),
        )
        log_exception(
            logger_api,
            exception,
            message="Wallpaper upload failed with exception",
            operation=OPERATION_WALLPAPER_UPLOAD,
            trace_id=trace_id,
            details={"task_id": task.task_id},
            level="warning",
        )
        handle_wallpaper_exception(request, exception, "wallpaper upload", task_id=task.task_id)
    finally:
        await bridge.close(final_bytes_done=staged_size)
        if staged_path:
            await cleanup_temp_file(staged_path)
