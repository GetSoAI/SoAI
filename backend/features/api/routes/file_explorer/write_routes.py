"""SoAI - File explorer write and mkdir routes [backend/features/api/routes/file_explorer/write_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.audit.constants import AUDIT_FILE_EXPLORER_MKDIR, AUDIT_FILE_EXPLORER_WRITE
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.route_mutation_execution import (
    run_single_path_mutation_route,
)
from features.api.routes.file_explorer.schemas import MkdirRequest, WriteTextRequest
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user

if TYPE_CHECKING:
    from core.files.protocols import FileExplorerCoreProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.write_routes"
OPERATION_FILE_EXPLORER_MKDIR = "file_explorer.mkdir"
OPERATION_FILE_EXPLORER_WRITE = "file_explorer.write"


def register_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.put(
        "/write",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_WRITE),
    )
    async def write_text_file(
        request: Request,
        body: WriteTextRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        async def _write(
            file_explorer_core: FileExplorerCoreProtocol,
            root_scope: FileSystemRootScopeProtocol,
            canonical_path: str,
        ) -> None:
            await file_explorer_core.write_text_file(
                root_scope,
                canonical_path,
                body.content,
            )

        return await run_single_path_mutation_route(
            request,
            api_context=api_context,
            current_user=current_user,
            path=body.path,
            canonical_operation="file_explorer.write_text_file",
            audit_event=AUDIT_FILE_EXPLORER_WRITE,
            audit_details={"path": body.path},
            logger=get_logger(LOGGER_NAME),
            coerce_operation="file_explorer.write_text",
            operation=OPERATION_FILE_EXPLORER_WRITE,
            log_message="Failed to write file",
            server_error_message="Failed to write file.",
            mutation=_write,
            handle_disk_space=True,
            disk_space_operation="api_file_explorer.write_text",
            disk_space_details={"path": body.path},
        )

    @routers.file_explorer.post(
        "/mkdir",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_WRITE),
    )
    async def create_directory(
        request: Request,
        body: MkdirRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        async def _mkdir(
            file_explorer_core: FileExplorerCoreProtocol,
            root_scope: FileSystemRootScopeProtocol,
            canonical_path: str,
        ) -> None:
            await file_explorer_core.create_directory(root_scope, canonical_path)

        return await run_single_path_mutation_route(
            request,
            api_context=api_context,
            current_user=current_user,
            path=body.path,
            canonical_operation="file_explorer.create_directory",
            audit_event=AUDIT_FILE_EXPLORER_MKDIR,
            audit_details={"path": body.path},
            logger=get_logger(LOGGER_NAME),
            coerce_operation="file_explorer.mkdir",
            operation=OPERATION_FILE_EXPLORER_MKDIR,
            log_message="Failed to create directory",
            server_error_message="Failed to create directory.",
            mutation=_mkdir,
            handle_disk_space=True,
            disk_space_operation="api_file_explorer.mkdir",
            disk_space_details={"path": body.path},
        )
