"""SoAI - System log snapshot route [backend/features/api/routes/system/system_logs_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from threading import Event

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.archives.zip_creation_models import ZipArchiveResult
from core.archives.zip_writing import remove_completed_zip_archive
from core.concurrency.cancellation_cleanup import current_task_has_pending_cancellation
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.hardware.reservation_exceptions import preserve_primary_exception_cleanup_failure
from core.logging.trace import get_logger
from core.runtime.request_trace_id import get_request_trace_id
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found, raise_service_unavailable
from features.api.runtime.request_disconnect import run_with_request_disconnect_watch
from features.api.runtime.temporary_file_response import TemporaryFileResponse

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.system_logs_routes"
OPERATION_LOGS_EXPORT_CLEANUP = "logs.export.cleanup"
OPERATION_LOGS_SNAPSHOT = "api_system.logs.snapshot"


async def get_log_sources(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    log_manager = api_context.dependencies.log_manager
    if log_manager is None:
        raise_service_unavailable(request, "Logging service is unavailable.")
    return JSONResponse(content={"sources": log_manager.list_log_sources()})


async def get_logs_snapshot(
    request: Request,
    source_name: str,
    limit: int = Query(200, ge=1, le=10000),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    log_manager = api_context.dependencies.log_manager
    if log_manager is None:
        raise_service_unavailable(request, "Logging service is unavailable.")
    try:
        entries = await asyncio.to_thread(log_manager.get_recent_logs, source_name, limit)
    except (ValidationError, ValueError) as error:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Log source lookup failed.",
            operation=OPERATION_LOGS_SNAPSHOT,
            trace_id=get_request_trace_id(request),
            level="debug",
        )
        raise_not_found(request, "Log source unavailable. Choose an available log source.")
    return JSONResponse(content={"entries": entries, "source": source_name, "limit": limit})


async def export_logs_archive(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    service = api_context.dependencies.backup_service
    if service is None:
        raise_service_unavailable(request, "Logs export service is unavailable.")
    result: ZipArchiveResult | None = None
    handed_off = False

    async def prepare(cancellation_event: Event) -> ZipArchiveResult:
        nonlocal result
        result = await service.create_logs_export_archive(cancellation_event)
        return result

    try:
        await run_with_request_disconnect_watch(
            request, prepare, cancel_operation_on_disconnect=True
        )
        disconnected = await request.is_disconnected()
        if disconnected or current_task_has_pending_cancellation():
            raise asyncio.CancelledError()
        if result is None:
            raise_service_unavailable(request, "Logs export service returned no archive.")
        response = TemporaryFileResponse(
            result.archive_path,
            expected_identity=result.identity,
            filename=result.download_filename,
            media_type="application/zip",
        )
        response.headers["Cache-Control"] = "no-store"
        handed_off = True
        return response
    finally:
        primary_exception = sys.exception()
        if result is not None and not handed_off:
            try:
                await run_joined_thread_call(
                    remove_completed_zip_archive,
                    result,
                    task_name="logs-export-route-cleanup",
                    retain_resources_until_complete=True,
                )
            except OSError as cleanup_exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_exception,
                    message="Logs export route cleanup failed.",
                    operation=OPERATION_LOGS_EXPORT_CLEANUP,
                    trace_id=get_request_trace_id(request),
                )
                preserve_primary_exception_cleanup_failure(
                    primary_exception, cleanup_exception, cleanup_action="Logs export route cleanup"
                )


def register_routes(routers: ApiRouters) -> None:
    routers.system.add_api_route(
        "/logs/export/archive",
        export_logs_archive,
        methods=["GET"],
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
    routers.system.add_api_route(
        "/logs/sources",
        get_log_sources,
        methods=["GET"],
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
    routers.system.add_api_route(
        "/logs/{source_name}",
        get_logs_snapshot,
        methods=["GET"],
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
