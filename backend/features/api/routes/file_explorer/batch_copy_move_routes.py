"""SoAI - File explorer batch copy/move routes [backend/features/api/routes/file_explorer/batch_copy_move_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.audit.constants import AUDIT_FILE_EXPLORER_COPY, AUDIT_FILE_EXPLORER_MOVE
from core.state.access import AccessAction
from features.api.routes.file_explorer.copy_move_operations import (
    run_copy_move_batch,
    start_copy_move_batch_task,
)
from features.api.routes.file_explorer.schemas import BatchCopyRequest, BatchMoveRequest
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user

__all__ = (
    "register_batch_copy_routes",
    "register_batch_move_routes",
)


def register_batch_copy_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.post(
        "/batch-copy",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )
    async def batch_copy_entries(
        request: Request,
        body: BatchCopyRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await run_copy_move_batch(
            request,
            api_context,
            current_user,
            audit_event=AUDIT_FILE_EXPLORER_COPY,
            sources=body.sources,
            destination_dir=body.destination_dir,
            batch_call=lambda batch, root_scope, sources, destination_dir: batch.copy_entries(
                root_scope,
                sources,
                destination_dir,
                overwrite=body.overwrite,
            ),
            coerce_operation="file_explorer.batch_copy",
            log_message="Failed to perform batch copy",
            server_error_message="Failed to perform batch copy operation.",
        )

    @routers.file_explorer.post(
        "/batch-copy-task",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )
    async def start_batch_copy_task(
        request: Request,
        body: BatchCopyRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await start_copy_move_batch_task(
            request,
            api_context,
            current_user,
            audit_event=AUDIT_FILE_EXPLORER_COPY,
            sources=body.sources,
            destination_dir=body.destination_dir,
            start_call=lambda tasks, root_scope, user_id, sources, destination_dir: tasks.start_copy_batch_task(
                root_scope,
                user_id,
                sources,
                destination_dir,
                overwrite=body.overwrite,
            ),
            coerce_operation="file_explorer.start_copy_batch_task",
            log_message="Failed to start batch copy task",
            server_error_message="Failed to initiate batch copy task.",
        )


def register_batch_move_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.post(
        "/batch-move",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )
    async def batch_move_entries(
        request: Request,
        body: BatchMoveRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await run_copy_move_batch(
            request,
            api_context,
            current_user,
            audit_event=AUDIT_FILE_EXPLORER_MOVE,
            sources=body.sources,
            destination_dir=body.destination_dir,
            batch_call=lambda batch, root_scope, sources, destination_dir: batch.move_entries(
                root_scope,
                sources,
                destination_dir,
                overwrite=body.overwrite,
            ),
            coerce_operation="file_explorer.batch_move",
            log_message="Failed to perform batch move",
            server_error_message="Failed to perform batch move operation.",
        )

    @routers.file_explorer.post(
        "/batch-move-task",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )
    async def start_batch_move_task(
        request: Request,
        body: BatchMoveRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await start_copy_move_batch_task(
            request,
            api_context,
            current_user,
            audit_event=AUDIT_FILE_EXPLORER_MOVE,
            sources=body.sources,
            destination_dir=body.destination_dir,
            start_call=lambda tasks, root_scope, user_id, sources, destination_dir: tasks.start_move_batch_task(
                root_scope,
                user_id,
                sources,
                destination_dir,
                overwrite=body.overwrite,
            ),
            coerce_operation="file_explorer.start_move_batch_task",
            log_message="Failed to start batch move task",
            server_error_message="Failed to initiate batch move task.",
        )
