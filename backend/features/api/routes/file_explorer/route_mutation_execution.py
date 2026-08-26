"""SoAI - File explorer route mutation execution helpers [backend/features/api/routes/file_explorer/route_mutation_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import StateError
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_paths import (
    canonicalize_non_root_route_path,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_core_scoped,
)
from features.api.routes.file_explorer.serializers import build_single_path_response
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import get_request_trace_id

if TYPE_CHECKING:
    from core.files.protocols import FileExplorerCoreProtocol
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser

__all__ = ("run_single_path_mutation_route",)


async def run_single_path_mutation_route(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
    path: str,
    canonical_operation: str,
    audit_event: str,
    audit_details: dict[str, JSONValue],
    logger: TraceLogger,
    coerce_operation: str,
    operation: str,
    log_message: str,
    server_error_message: str,
    mutation: Callable[
        [FileExplorerCoreProtocol, FileSystemRootScopeProtocol, str],
        Awaitable[None],
    ],
    handle_disk_space: bool = False,
    disk_space_operation: str | None = None,
    disk_space_details: dict[str, JSONValue] | None = None,
) -> JSONResponse:
    log_audit_event(request, audit_event, "file_explorer", details=dict(audit_details))
    try:
        scoped = require_file_explorer_core_scoped(
            request,
            api_context=api_context,
            current_user=current_user,
        )
        canonical_path = canonicalize_non_root_route_path(
            scoped.root_scope,
            path,
            operation=canonical_operation,
            message="Cannot perform this operation on the root directory.",
        )
        await mutation(scoped.file_explorer_core, scoped.root_scope, canonical_path)
        return JSONResponse(content=build_single_path_response(canonical_path))
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation=coerce_operation,
            operation=operation,
            log_message=log_message,
            server_error_message=server_error_message,
            log_trace_id=get_request_trace_id(request),
            log_details={"path": path},
            handle_disk_space=handle_disk_space,
            disk_space_operation=disk_space_operation,
            disk_space_trace_id=get_request_trace_id(request),
            disk_space_details=disk_space_details,
        )
    raise StateError(
        "File explorer single-path mutation route did not return.",
        operation=operation,
        details={"path": path},
    )
