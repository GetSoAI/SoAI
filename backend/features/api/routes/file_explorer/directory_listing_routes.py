"""SoAI - File explorer directory listing session routes [backend/features/api/routes/file_explorer/directory_listing_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from fastapi import Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.audit.constants import AUDIT_FILE_EXPLORER_LIST
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.routes.file_explorer.listing_serialization import (
    serialize_file_entry,
)
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_execution import (
    execute_file_explorer_route_json,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_listing_scoped,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.responses import create_task_accepted_response

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.directory_listing_routes"
LISTING_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class StartDirectoryListingRequest(BaseModel):
    listing_id: str = Field(min_length=1, max_length=128, pattern=LISTING_ID_PATTERN)
    path: str = Field(min_length=1)


def register_routes(routers: ApiRouters) -> None:
    dependencies = require_action_dependencies(AccessAction.FILE_EXPLORER_READ)

    @routers.file_explorer.post("/listings", dependencies=dependencies)
    async def start_listing(
        request: Request,
        body: StartDirectoryListingRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        log_audit_event(request, AUDIT_FILE_EXPLORER_LIST, "file_explorer")
        scoped = require_file_explorer_listing_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )
        try:
            admission = await scoped.file_explorer_listings.start_listing(
                listing_id=body.listing_id,
                user_id=current_user["id"],
                root_scope=scoped.root_scope,
                virtual_path=body.path,
            )
        except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
            await handle_file_explorer_route_exception(
                request,
                exception=exception,
                logger=get_logger(LOGGER_NAME),
                coerce_operation="file_explorer.directory_listing.start",
                operation="file_explorer.directory_listing.start",
                log_message="Failed to start directory listing.",
                server_error_message="Failed to start directory listing.",
            )
        return create_task_accepted_response(
            task_id=admission.task_id,
            commit_deadline_ts_ms=None,
            extra={"listing_id": admission.listing_id, "path": admission.path},
        )

    @routers.file_explorer.get("/listings/{listing_id}", dependencies=dependencies)
    async def get_listing_page(
        request: Request,
        listing_id: str = Path(pattern=LISTING_ID_PATTERN),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=400, ge=1, le=1000),
        sort_column: Literal["modified", "name", "size", "type"] = Query(default="name"),
        sort_direction: Literal["asc", "desc"] = Query(default="asc"),
        entry_type: Literal["all", "directory", "file"] = Query(default="all"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        scoped = require_file_explorer_listing_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        async def run() -> JSONDict:
            page = await scoped.file_explorer_listings.get_page(
                listing_id=listing_id,
                user_id=current_user["id"],
                root_scope=scoped.root_scope,
                offset=offset,
                limit=limit,
                sort_column=sort_column,
                sort_direction=sort_direction,
                entry_type=entry_type,
            )
            return {
                "listing_id": page.listing_id,
                "path": page.path,
                "entries": [serialize_file_entry(entry) for entry in page.entries],
                "total": page.total,
                "offset": page.offset,
                "limit": page.limit,
                "has_more": page.has_more,
                "next_offset": page.next_offset,
                "workspace_path_resolved": scoped.root_scope.root_path,
            }

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="file_explorer.directory_listing.page",
            operation="file_explorer.directory_listing.page",
            recoverable_log_message="Failed to read directory listing page.",
            server_error_message="Failed to read directory listing.",
        )

    @routers.file_explorer.get(
        "/listings/{listing_id}/locate",
        dependencies=dependencies,
    )
    async def locate_listing_entry(
        request: Request,
        listing_id: str = Path(pattern=LISTING_ID_PATTERN),
        name: str = Query(min_length=1),
        sort_column: Literal["modified", "name", "size", "type"] = Query(default="name"),
        sort_direction: Literal["asc", "desc"] = Query(default="asc"),
        entry_type: Literal["all", "directory", "file"] = Query(default="all"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        scoped = require_file_explorer_listing_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        async def run() -> JSONDict:
            result = await scoped.file_explorer_listings.locate(
                listing_id=listing_id,
                user_id=current_user["id"],
                root_scope=scoped.root_scope,
                name=name,
                sort_column=sort_column,
                sort_direction=sort_direction,
                entry_type=entry_type,
            )
            return {"offset": result.offset}

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="file_explorer.directory_listing.locate",
            operation="file_explorer.directory_listing.locate",
            recoverable_log_message="Failed to locate directory listing entry.",
            server_error_message="Failed to locate directory entry.",
        )

    @routers.file_explorer.delete("/listings/{listing_id}", dependencies=dependencies)
    async def release_listing(
        request: Request,
        listing_id: str = Path(pattern=LISTING_ID_PATTERN),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        scoped = require_file_explorer_listing_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        async def run() -> JSONDict:
            await scoped.file_explorer_listings.release(
                listing_id=listing_id,
                user_id=current_user["id"],
            )
            return {"status": "released", "listing_id": listing_id}

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=get_logger(LOGGER_NAME),
            recoverable_coerce_operation="file_explorer.directory_listing.release",
            operation="file_explorer.directory_listing.release",
            recoverable_log_message="Failed to release directory listing.",
            server_error_message="Failed to release directory listing.",
        )
