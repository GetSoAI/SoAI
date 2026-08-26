"""SoAI - File explorer preview route (typed Content-Type and Range) [backend/features/api/routes/file_explorer/preview_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from fastapi import Depends, Query, Request
from fastapi.responses import FileResponse

from core.audit.constants import AUDIT_FILE_EXPLORER_READ
from core.errors.exceptions import ValidationError
from core.files.export import (
    build_content_disposition_attachment,
    build_content_disposition_inline,
)
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_core_scoped,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.file_explorer.path_resolution import canonicalize_virtual_path

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.preview_routes"
OPERATION = "file_explorer.preview"


def register_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.get(
        "/preview",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def preview_file(
        request: Request,
        path: str = Query(description="Virtual path of the file to preview"),
        download: int = Query(default=0, ge=0, le=1, description="Return as attachment when 1"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> FileResponse:
        log_audit_event(request, AUDIT_FILE_EXPLORER_READ, "file_explorer", details={"path": path})
        scoped = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )
        logger = get_logger(LOGGER_NAME)
        try:
            canonical_path = canonicalize_virtual_path(scoped.root_scope, path)
            metadata = await scoped.file_explorer_core.get_metadata(
                scoped.root_scope,
                canonical_path,
                include_hash=False,
            )
            if metadata.is_directory:
                raise ValidationError("Cannot preview a folder.", operation=OPERATION)
            filename = metadata.name or os.path.basename(metadata.path) or "download"
            content_disposition = (
                build_content_disposition_attachment(filename)
                if int(download) == 1
                else build_content_disposition_inline(filename)
            )
            headers = {
                "Cache-Control": "no-store",
                "Content-Disposition": content_disposition,
                "X-Content-Type-Options": "nosniff",
            }
            return FileResponse(
                scoped.root_scope.resolve(metadata.path),
                media_type=metadata.mime_type or "application/octet-stream",
                headers=headers,
            )
        except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
            await handle_file_explorer_route_exception(
                request,
                exception=exception,
                logger=logger,
                coerce_operation=OPERATION,
                operation=OPERATION,
                log_message="Failed to preview file",
                server_error_message="Failed to preview file.",
            )
