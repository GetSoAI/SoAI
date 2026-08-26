"""SoAI - File explorer delete operation routes [backend/features/api/routes/file_explorer/delete_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core.audit.constants import AUDIT_FILE_EXPLORER_DELETE
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.file_explorer.route_batch_scoped_audit import (
    require_file_explorer_batch_scoped_with_audit,
)
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_mutation_execution import (
    run_single_path_mutation_route,
)
from features.api.routes.file_explorer.route_paths import (
    canonicalize_non_root_route_paths,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_tasks_scoped,
)
from features.api.routes.file_explorer.schemas import BatchDeleteRequest, DeleteRequest
from features.api.routes.file_explorer.serializers import (
    serialize_batch_result,
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
from features.api.runtime.responses import create_task_accepted_response

if TYPE_CHECKING:
    from core.files.protocols import FileExplorerCoreProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol

__all__ = (
    "batch_delete_entries",
    "delete_entry",
    "register_endpoints",
    "register_routes",
    "start_batch_delete_task",
)

LOGGER_NAME = "SoAI.features.api.delete_endpoints"
OPERATION_FILE_EXPLORER_BATCH_DELETE = "file_explorer.batch_delete"
OPERATION_FILE_EXPLORER_BATCH_DELETE_TASK = "file_explorer.batch_delete_task"
OPERATION_FILE_EXPLORER_DELETE = "file_explorer.delete"


async def delete_entry(
    request: Request,
    body: DeleteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    async def _delete(
        file_explorer_core: FileExplorerCoreProtocol,
        root_scope: FileSystemRootScopeProtocol,
        canonical_path: str,
    ) -> None:
        await file_explorer_core.delete_entry(root_scope, canonical_path)

    return await run_single_path_mutation_route(
        request,
        api_context=api_context,
        current_user=current_user,
        path=body.path,
        canonical_operation="file_explorer.delete_entry",
        audit_event=AUDIT_FILE_EXPLORER_DELETE,
        audit_details={"path": body.path},
        logger=get_logger(LOGGER_NAME),
        coerce_operation="file_explorer.delete",
        operation=OPERATION_FILE_EXPLORER_DELETE,
        log_message="Failed to delete entry",
        server_error_message="Failed to delete entry.",
        mutation=_delete,
    )


async def batch_delete_entries(
    request: Request,
    body: BatchDeleteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    scoped = require_file_explorer_batch_scoped_with_audit(
        request,
        api_context=api_context,
        current_user=current_user,
        audit_event=AUDIT_FILE_EXPLORER_DELETE,
        audit_details={"batch_count": len(body.paths)},
    )
    try:
        canonical_paths = canonicalize_non_root_route_paths(
            scoped.root_scope,
            body.paths,
            operation="file_explorer.batch_delete",
            message="Cannot delete the root directory.",
        )
        result = await scoped.file_explorer_batch.delete_entries(scoped.root_scope, canonical_paths)
        payload = serialize_batch_result(result)
        return JSONResponse(content=payload)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation="file_explorer.batch_delete",
            operation=OPERATION_FILE_EXPLORER_BATCH_DELETE,
            log_message="Failed to perform batch delete",
            server_error_message="Failed to perform batch delete operation.",
            log_trace_id=get_request_trace_id(request),
            log_details={"batch_count": len(body.paths)},
        )


async def start_batch_delete_task(
    request: Request,
    body: BatchDeleteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    log_audit_event(
        request,
        AUDIT_FILE_EXPLORER_DELETE,
        "file_explorer",
        details={"batch_count": len(body.paths), "mode": "task"},
    )
    scoped = require_file_explorer_tasks_scoped(
        request,
        api_context=api_context,
        current_user=current_user,
    )
    logger = get_logger(LOGGER_NAME)
    try:
        canonical_paths = canonicalize_non_root_route_paths(
            scoped.root_scope,
            body.paths,
            operation="file_explorer.batch_delete_task",
            message="Cannot delete the root directory.",
        )
        task_id = await scoped.file_explorer_tasks.start_delete_batch_task(
            scoped.root_scope,
            current_user["id"],
            canonical_paths,
        )
        return create_task_accepted_response(task_id=task_id, commit_deadline_ts_ms=None)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation="file_explorer.start_delete_batch_task",
            operation=OPERATION_FILE_EXPLORER_BATCH_DELETE_TASK,
            log_message="Failed to start batch delete task",
            server_error_message="Failed to initiate batch delete task.",
            log_trace_id=get_request_trace_id(request),
            log_details={"batch_count": len(body.paths), "mode": "task"},
        )


def register_endpoints(router: APIRouter) -> None:
    router.delete(
        "/delete",
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_WRITE),
    )(delete_entry)
    router.post(
        "/batch-delete",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )(batch_delete_entries)
    router.post(
        "/batch-delete-task",
        dependencies=require_action_dependencies(
            AccessAction.FILE_EXPLORER_WRITE,
            AccessAction.FILE_EXPLORER_ADMIN,
        ),
    )(start_batch_delete_task)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.file_explorer)
