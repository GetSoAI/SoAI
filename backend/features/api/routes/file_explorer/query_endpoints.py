"""SoAI - File explorer search, hash, and batch metadata routes [backend/features/api/routes/file_explorer/query_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.audit.constants import (
    AUDIT_FILE_EXPLORER_BATCH_METADATA,
    AUDIT_FILE_EXPLORER_READ,
    AUDIT_FILE_EXPLORER_SEARCH,
)
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.listing_serialization import (
    serialize_search_result,
)
from features.api.routes.file_explorer.route_batch_scoped_audit import (
    require_file_explorer_batch_scoped_with_audit,
)
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_core_scoped,
    require_file_explorer_tasks_scoped,
)
from features.api.routes.file_explorer.search_cancellation import (
    run_file_explorer_directory_search_with_disconnect_watch,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    resolve_api_context,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error
from features.api.runtime.responses import create_task_accepted_response
from features.file_explorer.search_service import FILE_EXPLORER_SEARCH_RESULT_LIMIT_MAX

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "BatchMetadataRequest",
    "get_metadata_batch",
    "register_endpoints",
    "register_routes",
    "search_directory",
    "start_hash_task",
)

LOGGER_NAME = "SoAI.features.api.query_endpoints"
OPERATION_FILE_EXPLORER_BATCH_METADATA = "file_explorer.batch_metadata"
OPERATION_FILE_EXPLORER_HASH_TASK = "file_explorer.hash_task"
OPERATION_FILE_EXPLORER_SEARCH = "file_explorer.search"


class BatchMetadataRequest(BaseModel):
    paths: list[str] = Field(description="Virtual file/directory paths", min_length=1)


async def get_metadata_batch(
    request: Request,
    body: BatchMetadataRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    scoped = require_file_explorer_batch_scoped_with_audit(
        request,
        api_context=api_context,
        current_user=current_user,
        audit_event=AUDIT_FILE_EXPLORER_BATCH_METADATA,
        audit_details={"batch_count": len(body.paths)},
    )
    try:
        result = await scoped.file_explorer_batch.get_metadata(scoped.root_scope, body.paths)
        results = [
            {
                "path": result_item.path,
                "success": result_item.success,
                "metadata": (
                    {
                        "name": result_item.metadata.name,
                        "path": result_item.metadata.path,
                        "is_directory": result_item.metadata.is_directory,
                        "size": result_item.metadata.size,
                        "modified_at_ms": result_item.metadata.modified_at_ms,
                        "mime_type": result_item.metadata.mime_type,
                        "type_id": result_item.metadata.type_id,
                        "type_rank": result_item.metadata.type_rank,
                        "permissions": result_item.metadata.permissions,
                        "sha256": result_item.metadata.sha256,
                    }
                    if result_item.metadata
                    else None
                ),
                "error": result_item.error_message,
            }
            for result_item in result.results
        ]
        return JSONResponse(
            content={
                "total": result.total,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "results": results,
                "status": "ok",
            },
        )
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation="file_explorer.batch_metadata",
            operation=OPERATION_FILE_EXPLORER_BATCH_METADATA,
            log_message="Failed to get batch metadata",
            server_error_message="Failed to get batch metadata.",
            log_trace_id=get_request_trace_id(request),
            log_details={"batch_count": len(body.paths)},
        )


async def start_hash_task(
    request: Request,
    path: str = Query(description="Virtual path to hash"),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    log_audit_event(
        request,
        AUDIT_FILE_EXPLORER_READ,
        "file_explorer",
        details={"path": path, "op": "hash"},
    )
    logger = get_logger(LOGGER_NAME)
    try:
        scoped = require_file_explorer_tasks_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )
        task_id = await scoped.file_explorer_tasks.start_hash_task(
            scoped.root_scope,
            current_user["id"],
            path,
        )
        return create_task_accepted_response(task_id=task_id, commit_deadline_ts_ms=None)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation="file_explorer.start_hash_task",
            operation=OPERATION_FILE_EXPLORER_HASH_TASK,
            log_message="Failed to start hash task",
            server_error_message="Failed to initiate hashing task.",
            log_trace_id=get_request_trace_id(request),
            log_details={"path": path},
        )


async def search_directory(
    request: Request,
    path: str = Query(default="/", description="Virtual directory to search in"),
    query: str = Query(description="Search pattern (glob: *, ?, [abc])"),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=FILE_EXPLORER_SEARCH_RESULT_LIMIT_MAX),
    case_sensitive: bool = Query(default=False),
    include_total: bool = Query(default=False, description="Scan full tree for exact total"),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    log_audit_event(
        request,
        AUDIT_FILE_EXPLORER_SEARCH,
        "file_explorer",
        details={"path": path, "query": query},
    )
    file_explorer_search = api_context.dependencies.file_explorer_search
    if file_explorer_search is None:
        raise_server_error(request, "File explorer search service is not available.")
    logger = get_logger(LOGGER_NAME)
    try:
        scoped = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )

        result = await run_file_explorer_directory_search_with_disconnect_watch(
            request=request,
            file_explorer_search=file_explorer_search,
            root_scope=scoped.root_scope,
            path=path,
            query=query,
            offset=offset,
            limit=limit,
            case_sensitive=case_sensitive,
            include_total=include_total,
        )
        payload: JSONDict = serialize_search_result(result)
        payload["workspace_path_resolved"] = scoped.root_scope.root_path
        return JSONResponse(content=payload)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation="file_explorer.search_directory",
            operation=OPERATION_FILE_EXPLORER_SEARCH,
            log_message="Failed to search directory",
            server_error_message="Failed to search directory.",
            log_trace_id=get_request_trace_id(request),
            log_details={"path": path, "query": query},
        )


def register_endpoints(router: APIRouter) -> None:
    router.post(
        "/batch-metadata",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )(get_metadata_batch)
    router.post(
        "/hash",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_READ,
            AccessAction.FILE_EXPLORER_HASH,
        ),
    )(start_hash_task)
    router.get(
        "/search",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )(search_directory)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.file_explorer)
