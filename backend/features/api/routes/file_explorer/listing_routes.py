"""SoAI - File explorer listing and metadata routes [backend/features/api/routes/file_explorer/listing_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from core.audit.constants import (
    AUDIT_FILE_EXPLORER_LIST,
    AUDIT_FILE_EXPLORER_READ,
)
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.listing_serialization import (
    serialize_list_result,
)
from features.api.routes.file_explorer.route_execution import (
    execute_file_explorer_route_json,
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

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.listing_routes"
OPERATION_FILE_EXPLORER_LIST = "file_explorer.list"
OPERATION_FILE_EXPLORER_METADATA = "file_explorer.metadata"
OPERATION_FILE_EXPLORER_READ = "file_explorer.read"


def register_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.get(
        "/list",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def list_directory(
        request: Request,
        path: str = Query(default="/", description="Virtual directory path"),
        offset: int = Query(default=0, ge=0),
        limit: int | None = Query(default=None, ge=1, le=1000),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, AUDIT_FILE_EXPLORER_LIST, "file_explorer")
        scope_context = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        async def run() -> JSONDict:
            result = await scope_context.file_explorer_core.list_directory(
                scope_context.root_scope,
                path,
                offset=offset,
                limit=limit,
            )
            payload = serialize_list_result(result)
            payload["workspace_path_resolved"] = scope_context.root_scope.root_path
            return payload

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="file_explorer.list_directory",
            operation=OPERATION_FILE_EXPLORER_LIST,
            recoverable_log_message="Failed to list directory",
            server_error_message="Failed to list directory.",
            handle_validation_error=True,
        )

    @routers.file_explorer.get(
        "/metadata",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def get_metadata(
        request: Request,
        path: str = Query(description="Virtual path to inspect"),
        include_hash: bool = Query(default=False),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, AUDIT_FILE_EXPLORER_READ, "file_explorer", details={"path": path})
        scope_context = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        async def run() -> JSONDict:
            metadata = await scope_context.file_explorer_core.get_metadata(
                scope_context.root_scope,
                path,
                include_hash=include_hash,
            )
            return {
                "name": metadata.name,
                "path": metadata.path,
                "is_directory": metadata.is_directory,
                "size": metadata.size,
                "modified_at_ms": metadata.modified_at_ms,
                "mime_type": metadata.mime_type,
                "type_id": metadata.type_id,
                "type_rank": metadata.type_rank,
                "permissions": metadata.permissions,
                "sha256": metadata.sha256,
            }

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="file_explorer.get_metadata",
            operation=OPERATION_FILE_EXPLORER_METADATA,
            recoverable_log_message="Failed to get metadata",
            server_error_message="Failed to retrieve file metadata.",
            handle_validation_error=False,
        )

    @routers.file_explorer.get(
        "/read",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def read_text_file(
        request: Request,
        path: str = Query(description="Virtual path of text file"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, AUDIT_FILE_EXPLORER_READ, "file_explorer", details={"path": path})
        scope_context = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        async def run() -> JSONDict:
            canonical_path = canonicalize_virtual_path(scope_context.root_scope, path)
            content = await scope_context.file_explorer_core.read_text_file(
                scope_context.root_scope,
                canonical_path,
            )
            return {"path": canonical_path, "content": content}

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="file_explorer.read_text",
            operation=OPERATION_FILE_EXPLORER_READ,
            recoverable_log_message="Failed to read file",
            server_error_message="Failed to read file.",
            handle_validation_error=True,
        )
