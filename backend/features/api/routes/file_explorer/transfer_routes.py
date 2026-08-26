"""SoAI - File explorer upload and download routes [backend/features/api/routes/file_explorer/transfer_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

from fastapi import Depends, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse

from core.audit.constants import (
    AUDIT_FILE_EXPLORER_DOWNLOAD,
    AUDIT_FILE_EXPLORER_UPLOAD,
)
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_core_scoped,
    require_file_explorer_download_scoped,
)
from features.api.routes.file_explorer.schemas import DownloadSelectionRequest
from features.api.routes.file_explorer.upload_transfer.streaming.batch import (
    handle_streaming_upload_batch,
)
from features.api.routes.file_explorer.upload_transfer.streaming.single import (
    handle_streaming_file_upload,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.request_disconnect import run_with_request_disconnect_watch
from features.api.runtime.temporary_file_response import TemporaryFileResponse
from features.file_explorer.path_resolution import resolve_download_real_path

if TYPE_CHECKING:
    from core.files.explorer_models import FileExplorerDownloadArchive
    from features.api.routes.file_explorer.route_scope_context import (
        FileExplorerDownloadScopeContext,
    )

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.transfer_routes"
OPERATION = "file_explorer.download"


async def _create_archive_response(
    request: Request,
    scoped: FileExplorerDownloadScopeContext,
    virtual_paths: tuple[str, ...],
) -> TemporaryFileResponse:
    async def create_archive(
        cancellation_event: threading.Event,
    ) -> FileExplorerDownloadArchive:
        return await scoped.file_explorer_download.create_archive(
            scoped.root_scope,
            virtual_paths,
            cancellation_event,
        )

    result = await run_with_request_disconnect_watch(request, create_archive)
    return TemporaryFileResponse(
        result.archive_path,
        expected_identity=result.identity,
        filename=result.download_filename,
        media_type="application/zip",
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.get(
        "/download",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def download_file(
        request: Request,
        path: str = Query(description="Virtual path of the file to download"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> FileResponse:
        log_audit_event(
            request,
            AUDIT_FILE_EXPLORER_DOWNLOAD,
            "file_explorer",
            details={"path": path},
        )
        try:
            scoped = require_file_explorer_download_scoped(
                request,
                api_context=api_context,
                current_user=current_user,
            )
            real_path = resolve_download_real_path(scoped.root_scope, path)
            if os.path.isdir(real_path):
                return await _create_archive_response(request, scoped, (path,))
            filename = os.path.basename(real_path)
            return FileResponse(
                real_path,
                filename=filename,
                media_type="application/octet-stream",
            )
        except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
            await handle_file_explorer_route_exception(
                request,
                exception=exception,
                logger=get_logger(LOGGER_NAME),
                coerce_operation="file_explorer.download",
                operation=OPERATION,
                log_message="Failed to download file",
                server_error_message="Failed to download file.",
                handle_disk_space=True,
                disk_space_operation="file_explorer.download",
            )

    @routers.file_explorer.post(
        "/download-selection",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def download_selection(
        request: Request,
        payload: DownloadSelectionRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> FileResponse:
        log_audit_event(
            request,
            AUDIT_FILE_EXPLORER_DOWNLOAD,
            "file_explorer",
            details={"paths": payload.paths, "path_count": len(payload.paths)},
        )
        try:
            scoped = require_file_explorer_download_scoped(
                request,
                api_context=api_context,
                current_user=current_user,
            )
            return await _create_archive_response(request, scoped, tuple(payload.paths))
        except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
            await handle_file_explorer_route_exception(
                request,
                exception=exception,
                logger=get_logger(LOGGER_NAME),
                coerce_operation="file_explorer.download_selection",
                operation=OPERATION,
                log_message="Failed to download file explorer selection",
                server_error_message="Failed to download file explorer selection.",
                handle_disk_space=True,
                disk_space_operation="file_explorer.download_selection",
                disk_space_details={"path_count": len(payload.paths)},
            )

    @routers.file_explorer.post(
        "/upload",
        status_code=status.HTTP_201_CREATED,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_WRITE),
    )
    async def upload_file(
        request: Request,
        path: str = Query(description="Virtual directory path for upload destination"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(
            request,
            AUDIT_FILE_EXPLORER_UPLOAD,
            "file_explorer",
            details={"path": path},
        )
        scoped = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )
        return await handle_streaming_file_upload(
            request,
            file_explorer_core=scoped.file_explorer_core,
            root_scope=scoped.root_scope,
            path=path,
            api_context=api_context,
        )

    @routers.file_explorer.post(
        "/upload-batch",
        status_code=status.HTTP_201_CREATED,
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )
    async def upload_batch(
        request: Request,
        path: str = Query(description="Virtual directory path for upload destination"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(
            request,
            AUDIT_FILE_EXPLORER_UPLOAD,
            "file_explorer",
            details={"path": path},
        )
        scoped = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )
        return await handle_streaming_upload_batch(
            request,
            file_explorer_core=scoped.file_explorer_core,
            root_scope=scoped.root_scope,
            path=path,
            api_context=api_context,
        )
