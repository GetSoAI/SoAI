"""SoAI - Admin file browser routes for user workspace path assignment [backend/features/api/routes/webui/users_admin_file_browser_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Query, Request
from fastapi.responses import Response

from core.files.host_filesystem_roots import (
    default_host_filesystem_root,
    enumerate_host_filesystem_roots,
    locate_existing_host_directory,
    resolve_host_filesystem_root,
)
from core.logging.trace import get_logger
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
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_server_error
from features.api.schemas.users import AdminWorkspaceBrowserLocate
from features.file_explorer.workspace_scope import FileSystemRootScope

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.users_admin_file_browser_routes"
OPERATION_WEBUI_USERS_FILE_BROWSER_LIST = "webui.users.file_browser.list"
OPERATION_WEBUI_USERS_FILE_BROWSER_LOCATE = "webui.users.file_browser.locate"
OPERATION_WEBUI_USERS_FILE_BROWSER_ROOTS = "webui.users.file_browser.roots"
OPERATION_WEBUI_USERS_FILE_BROWSER_SEARCH = "webui.users.file_browser.search"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/users/workspace-browser/roots",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def list_host_filesystem_roots(request: Request) -> Response:
        log_audit_event(request, "LIST_WORKSPACE_BROWSER_ROOTS", "file_explorer")

        async def run() -> JSONDict:
            roots = enumerate_host_filesystem_roots()
            return {
                "roots": list(roots),
                "default_root": roots[0],
            }

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation=OPERATION_WEBUI_USERS_FILE_BROWSER_ROOTS,
            operation=OPERATION_WEBUI_USERS_FILE_BROWSER_ROOTS,
            recoverable_log_message="Failed to list host filesystem roots",
            server_error_message="Failed to list filesystem roots.",
            handle_validation_error=True,
        )

    @routers.webui.post(
        "/users/workspace-browser/locate",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def locate_host_directory(
        request: Request,
        payload: AdminWorkspaceBrowserLocate,
    ) -> Response:
        log_audit_event(
            request,
            "LOCATE_WORKSPACE_BROWSER_DIRECTORY",
            "file_explorer",
            {"path": payload.path},
        )

        async def run() -> JSONDict:
            location = locate_existing_host_directory(payload.path)
            root_scope = FileSystemRootScope(
                root_path=location.root_path,
                allow_symlinks=True,
            )
            return {
                "root_path": root_scope.root_path,
                "path": root_scope.to_virtual_path(location.absolute_path),
                "absolute_path": location.absolute_path,
            }

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation=OPERATION_WEBUI_USERS_FILE_BROWSER_LOCATE,
            operation=OPERATION_WEBUI_USERS_FILE_BROWSER_LOCATE,
            recoverable_log_message="Failed to locate host directory",
            server_error_message="Failed to locate directory.",
            handle_validation_error=True,
        )

    @routers.webui.get(
        "/users/workspace-browser/list",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def list_global_file_explorer_root(
        request: Request,
        path: str = Query(default="/", description="Virtual directory path"),
        root_path: str | None = Query(default=None, description="Native filesystem root"),
        offset: int = Query(default=0, ge=0),
        limit: int | None = Query(default=None, ge=1, le=1000),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_audit_event(
            request,
            "LIST_WORKSPACE_BROWSER",
            "file_explorer",
            {"path": path, "root_path": root_path},
        )
        file_explorer_core = api_context.dependencies.file_explorer_core
        if file_explorer_core is None:
            raise_server_error(request, "File explorer service is not available.")

        async def run() -> JSONDict:
            resolved_root = (
                default_host_filesystem_root()
                if root_path is None
                else resolve_host_filesystem_root(root_path)
            )
            root_scope = FileSystemRootScope(root_path=resolved_root, allow_symlinks=True)
            result = await file_explorer_core.list_directory(
                root_scope,
                path,
                offset=offset,
                limit=limit,
            )
            payload = serialize_list_result(result)
            payload["workspace_path_resolved"] = root_scope.root_path
            return payload

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="webui.users.file_browser.list",
            operation=OPERATION_WEBUI_USERS_FILE_BROWSER_LIST,
            recoverable_log_message="Failed to list admin file browser directory",
            server_error_message="Failed to list directory.",
            handle_validation_error=True,
        )

    @routers.webui.get(
        "/users/workspace-browser/search",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def search_global_file_explorer_root(
        request: Request,
        path: str = Query(default="/", description="Virtual directory path"),
        root_path: str | None = Query(default=None, description="Native filesystem root"),
        query: str = Query(description="Search pattern"),
        offset: int = Query(default=0, ge=0),
        limit: int | None = Query(default=None, ge=1, le=1000),
        case_sensitive: bool = Query(default=False),
        include_total: bool = Query(default=False),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_audit_event(
            request,
            "SEARCH_WORKSPACE_BROWSER",
            "file_explorer",
            {"path": path, "query": query, "root_path": root_path},
        )
        file_explorer_search = api_context.dependencies.file_explorer_search
        if file_explorer_search is None:
            raise_server_error(request, "File explorer search service is not available.")

        async def run() -> JSONDict:
            resolved_root = (
                default_host_filesystem_root()
                if root_path is None
                else resolve_host_filesystem_root(root_path)
            )
            root_scope = FileSystemRootScope(root_path=resolved_root, allow_symlinks=True)
            result = await run_file_explorer_directory_search_with_disconnect_watch(
                request=request,
                file_explorer_search=file_explorer_search,
                root_scope=root_scope,
                path=path,
                query=query,
                offset=offset,
                limit=limit,
                case_sensitive=case_sensitive,
                include_total=include_total,
            )
            payload = serialize_search_result(result)
            payload["workspace_path_resolved"] = root_scope.root_path
            return payload

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="webui.users.file_browser.search",
            operation=OPERATION_WEBUI_USERS_FILE_BROWSER_SEARCH,
            recoverable_log_message="Failed to search admin file browser directory",
            server_error_message="Failed to search directory.",
            handle_validation_error=True,
        )
