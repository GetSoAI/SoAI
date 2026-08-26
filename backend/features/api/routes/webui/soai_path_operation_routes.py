"""SoAI - Conversation-scoped SoAI path operation routes [backend/features/api/routes/webui/soai_path_operation_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request, status
from pydantic import Field
from starlette.responses import JSONResponse, Response

from core.logging.trace import get_logger
from core.meta.soai_v1 import SoAIV1StrictModel
from core.state.access import AccessAction
from features.api.routes.file_explorer.listing_serialization import (
    serialize_list_result,
    serialize_search_result,
)
from features.api.routes.file_explorer.route_execution import (
    execute_file_explorer_route_json,
)
from features.api.routes.file_explorer.search_cancellation import (
    run_file_explorer_directory_search_with_disconnect_watch,
)
from features.api.routes.webui.soai_path_operation_opening import (
    open_soai_path_response,
    token_soai_path_response,
)
from features.api.routes.webui.soai_path_operation_runtime import (
    SoaiPathOperationRequest,
    download_soai_path_response,
    preview_soai_path_response,
    read_soai_path_response,
)
from features.api.routes.webui.soai_path_operation_scope import (
    conversation_soai_path_scope,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.soai_path_operation_routes"
OPERATION_SOAI_PATH_BROWSE = "webui.soai_paths.browse"


class SoaiPathBrowseRequest(SoAIV1StrictModel):
    query: str | None = Field(default=None, min_length=1, max_length=256)
    limit: int = Field(default=20, ge=1, le=200)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/soai-paths/browse",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def browse_soai_path(
        request: Request,
        conv_id: str,
        body: SoaiPathBrowseRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        if body.query is not None and api_context.dependencies.file_explorer_search is None:
            raise_server_error(request, "File explorer search service is not available.")

        async def run() -> JSONDict:
            scope = await conversation_soai_path_scope(
                request=request,
                conv_id=conv_id,
                current_user=current_user,
                api_context=api_context,
            )
            if body.query is None:
                list_result = await scope.file_explorer_core.list_directory(
                    scope.effective_root_scope,
                    "/",
                    limit=body.limit,
                )
                payload = serialize_list_result(list_result)
            else:
                file_explorer_search = api_context.dependencies.file_explorer_search
                if file_explorer_search is None:
                    raise_server_error(request, "File explorer search service is not available.")
                search_result = await run_file_explorer_directory_search_with_disconnect_watch(
                    request=request,
                    file_explorer_search=file_explorer_search,
                    root_scope=scope.effective_root_scope,
                    path="/",
                    query=body.query,
                    offset=0,
                    limit=body.limit,
                    case_sensitive=False,
                    include_total=False,
                )
                payload = serialize_search_result(search_result)
            payload["workspace_path_resolved"] = scope.effective_root_real
            return payload

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation=OPERATION_SOAI_PATH_BROWSE,
            operation=OPERATION_SOAI_PATH_BROWSE,
            recoverable_log_message="SoAI path browse failed",
            server_error_message="Failed to browse conversation workspace.",
            handle_validation_error=True,
        )

    @routers.webui.post(
        "/conversations/{conv_id}/soai-paths/preview",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def preview_soai_path(
        request: Request,
        conv_id: str,
        body: SoaiPathOperationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await preview_soai_path_response(
            request=request,
            conv_id=conv_id,
            body=body,
            current_user=current_user,
            api_context=api_context,
        )

    @routers.webui.post(
        "/conversations/{conv_id}/soai-paths/read",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def read_soai_path(
        request: Request,
        conv_id: str,
        body: SoaiPathOperationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await read_soai_path_response(
            request=request,
            conv_id=conv_id,
            body=body,
            current_user=current_user,
            api_context=api_context,
        )

    @routers.webui.post(
        "/conversations/{conv_id}/soai-paths/download",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def download_soai_path(
        request: Request,
        conv_id: str,
        body: SoaiPathOperationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await download_soai_path_response(
            request=request,
            conv_id=conv_id,
            body=body,
            current_user=current_user,
            api_context=api_context,
        )

    @routers.webui.post(
        "/conversations/{conv_id}/soai-paths/open",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def open_soai_path(
        request: Request,
        conv_id: str,
        body: SoaiPathOperationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await open_soai_path_response(
            request=request,
            conv_id=conv_id,
            body=body,
            current_user=current_user,
            api_context=api_context,
        )

    @routers.webui.post(
        "/conversations/{conv_id}/soai-paths/token",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def token_soai_path(
        request: Request,
        conv_id: str,
        body: SoaiPathOperationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await token_soai_path_response(
            request=request,
            conv_id=conv_id,
            body=body,
            current_user=current_user,
            api_context=api_context,
        )
