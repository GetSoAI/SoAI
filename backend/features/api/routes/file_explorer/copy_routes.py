"""SoAI - File explorer copy operation routes [backend/features/api/routes/file_explorer/copy_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.audit.constants import AUDIT_FILE_EXPLORER_COPY
from core.state.access import AccessAction
from features.api.routes.file_explorer.batch_copy_move_routes import (
    register_batch_copy_routes,
)
from features.api.routes.file_explorer.copy_move_operations import run_copy_move_entry
from features.api.routes.file_explorer.schemas import CopyRequest
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.file_explorer.post(
        "/copy",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_WRITE),
    )
    async def copy_entry(
        request: Request,
        body: CopyRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await run_copy_move_entry(
            request,
            api_context,
            current_user,
            audit_event=AUDIT_FILE_EXPLORER_COPY,
            source=body.source,
            destination=body.destination,
            entry_call=lambda core, root_scope, source, destination: core.copy_entry(
                root_scope,
                source,
                destination,
                overwrite=body.overwrite,
            ),
            coerce_operation="file_explorer.copy",
            log_message="Failed to copy entry",
            server_error_message="Failed to copy entry.",
        )

    register_batch_copy_routes(routers)
