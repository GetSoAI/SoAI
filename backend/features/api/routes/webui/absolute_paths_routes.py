"""SoAI - Conversation-scoped absolute-path preview URL resolution [backend/features/api/routes/webui/absolute_paths_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse

from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.route_execution import (
    execute_file_explorer_route_json,
)
from features.api.routes.webui.absolute_paths_contracts import AbsolutePathsResolveRequest
from features.api.routes.webui.absolute_paths_resolution import resolve_absolute_paths_payload
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.absolute_paths_routes"
OPERATION = "webui.absolute_paths.resolve"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/absolute-paths/resolve",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def resolve_absolute_paths(
        request: Request,
        conv_id: str,
        body: AbsolutePathsResolveRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        logger = get_logger(LOGGER_NAME)
        conversation_record = await require_conversation_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        file_explorer_core = api_context.dependencies.file_explorer_core
        if file_explorer_core is None:
            raise_server_error(request, "File explorer service is not available.")

        async def run() -> JSONDict:
            return await resolve_absolute_paths_payload(
                body=body,
                current_user=current_user,
                conversation_record=conversation_record,
                api_context=api_context,
                logger=logger,
            )

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=logger,
            recoverable_coerce_operation="webui.absolute_paths.resolve",
            operation=OPERATION,
            recoverable_log_message="Absolute path resolution failed",
            server_error_message="Resolution failed.",
            handle_validation_error=True,
        )
