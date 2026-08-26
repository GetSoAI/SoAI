"""SoAI - WebUI wallpaper download route handler [backend/features/api/routes/webui/wallpaper_download_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

import httpx2
from fastapi import Depends, Request, status

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.events.types_webui import WallpaperChangedEvent
from core.logging.trace import get_logger
from core.runtime.network_policy import OfflineModeError
from core.state.access import AccessAction
from features.api.routes.webui.wallpaper_error_handling import (
    handle_wallpaper_disk_space_error,
    handle_wallpaper_exception,
)
from features.api.routes.webui.wallpaper_tasks import (
    cancel_wallpaper_task_after_request_cancellation,
    create_wallpaper_update_task,
    finalize_wallpaper_task_cancelled,
    finalize_wallpaper_task_completed,
    finalize_wallpaper_task_failed,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.task_api_errors import raise_api_error_with_task
from features.api.schemas.wallpaper import WallpaperDownloadRequest

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.wallpaper_download_routes"
OPERATION = "api_theme.download_wallpaper"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/wallpaper/download",
        status_code=200,
        dependencies=require_action_dependencies(AccessAction.WEBUI_APPEARANCE_ADMIN),
    )
    async def download_wallpaper(
        request: Request,
        payload: WallpaperDownloadRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, str]:
        url = str(payload.url)
        log_audit_event(request, "DOWNLOAD_WALLPAPER", url)
        context = request.state.context
        try:
            trace_id = context.trace_id
        except AttributeError:
            trace_id = None
        registry, task = await create_wallpaper_update_task(
            request=request,
            api_context=api_context,
            status_message="Downloading wallpaper",
            metadata={"operation": "wallpaper_download", "url": url},
        )
        try:
            await api_context.dependencies.webui_manager.wallpaper.set_wallpaper_from_url(
                url,
                api_context.dependencies.http_client,
                task.cancellation_id,
            )
            await finalize_wallpaper_task_completed(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.complete_task",
                result={"url": url},
                status_message="Wallpaper updated",
            )
            await api_context.dependencies.event_bus.publish(WallpaperChangedEvent())
            return {"message": "Wallpaper updated successfully from URL."}
        except TaskCancelledError as exception:
            cancel_reason = str(exception).strip() or "Cancelled by user"
            await finalize_wallpaper_task_cancelled(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.finalize_cancelled",
                cancel_reason=cancel_reason,
            )
            raise_api_error_with_task(
                request,
                499,
                "cancelled",
                "Wallpaper download was cancelled.",
                task_id=task.task_id,
            )
        except asyncio.CancelledError:
            await cancel_wallpaper_task_after_request_cancellation(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.cancel_task",
            )
            raise
        except OfflineModeError as exception:
            await finalize_wallpaper_task_failed(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.fail_task",
                error_code=423,
                error_message=str(exception),
            )
            raise_api_error_with_task(
                request,
                status.HTTP_423_LOCKED,
                "offline_mode",
                str(exception),
                task_id=task.task_id,
            )
        except httpx2.HTTPStatusError as exception:
            await finalize_wallpaper_task_failed(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.fail_task",
                error_code=int(exception.response.status_code),
                error_message=(
                    "Download failed. Server responded with status "
                    f"{exception.response.status_code}."
                ),
            )
            raise_api_error_with_task(
                request,
                exception.response.status_code,
                "download_failed",
                f"Download failed. Server responded with status {exception.response.status_code}.",
                task_id=task.task_id,
            )
        except httpx2.RequestError as exception:
            await finalize_wallpaper_task_failed(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.fail_task",
                error_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_message=f"A network error occurred during download: {exception}",
            )
            raise_api_error_with_task(
                request,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "download_failed",
                f"A network error occurred during download: {exception}",
                task_id=task.task_id,
            )
        except InsufficientDiskSpaceError as exception:
            return await handle_wallpaper_disk_space_error(
                registry,
                task.task_id,
                request,
                exception,
            )
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            await finalize_wallpaper_task_failed(
                registry=registry,
                task_id=task.task_id,
                trace_id=trace_id,
                operation="api_theme.download_wallpaper.fail_task",
                error_code=500,
                error_message=str(exception),
            )
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Wallpaper download failed with exception",
                operation=OPERATION,
                trace_id=trace_id,
                details={"task_id": task.task_id},
                level="warning",
            )
            handle_wallpaper_exception(
                request,
                exception,
                f"wallpaper download from {url}",
                task_id=task.task_id,
            )
