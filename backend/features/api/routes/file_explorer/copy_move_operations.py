"""SoAI - File explorer copy/move route operations [backend/features/api/routes/file_explorer/copy_move_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from core.files.explorer_models import BatchOperationResult
from core.files.protocols import (
    FileExplorerBatchProtocol,
    FileExplorerCoreProtocol,
    FileExplorerTaskLauncherProtocol,
)
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from features.api.routes.file_explorer.batch_operations import (
    run_batch_dir_operation,
    run_single_entry_operation,
    start_batch_task_operation,
)
from features.api.routes.file_explorer.route_scope_context import (
    require_file_explorer_batch_scoped,
    require_file_explorer_core_scoped,
    require_file_explorer_tasks_scoped,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser

__all__ = (
    "run_copy_move_batch",
    "run_copy_move_entry",
    "start_copy_move_batch_task",
)


async def run_copy_move_entry(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    *,
    audit_event: str,
    source: str,
    destination: str,
    entry_call: Callable[
        [FileExplorerCoreProtocol, FileSystemRootScopeProtocol, str, str],
        Awaitable[None],
    ],
    coerce_operation: str,
    log_message: str,
    server_error_message: str,
) -> JSONResponse:
    log_audit_event(
        request,
        audit_event,
        "file_explorer",
        details={"source": source, "destination": destination},
    )
    scope_context = require_file_explorer_core_scoped(
        request,
        api_context=api_context,
        current_user=current_user,
    )
    return await run_single_entry_operation(
        request,
        scope_context.file_explorer_core,
        scope_context.root_scope,
        source,
        destination,
        entry_call=entry_call,
        coerce_operation=coerce_operation,
        log_message=log_message,
        server_error_message=server_error_message,
    )


async def run_copy_move_batch(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    *,
    audit_event: str,
    sources: list[str],
    destination_dir: str,
    batch_call: Callable[
        [FileExplorerBatchProtocol, FileSystemRootScopeProtocol, list[str], str],
        Awaitable[BatchOperationResult],
    ],
    coerce_operation: str,
    log_message: str,
    server_error_message: str,
) -> JSONResponse:
    log_audit_event(
        request,
        audit_event,
        "file_explorer",
        details={"batch_count": len(sources), "destination": destination_dir},
    )
    scope_context = require_file_explorer_batch_scoped(
        request,
        api_context=api_context,
        current_user=current_user,
    )
    return await run_batch_dir_operation(
        request,
        scope_context.file_explorer_batch,
        scope_context.root_scope,
        sources,
        destination_dir,
        batch_call=batch_call,
        coerce_operation=coerce_operation,
        log_message=log_message,
        server_error_message=server_error_message,
    )


async def start_copy_move_batch_task(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    *,
    audit_event: str,
    sources: list[str],
    destination_dir: str,
    start_call: Callable[
        [FileExplorerTaskLauncherProtocol, FileSystemRootScopeProtocol, int, list[str], str],
        Awaitable[str],
    ],
    coerce_operation: str,
    log_message: str,
    server_error_message: str,
) -> JSONResponse:
    log_audit_event(
        request,
        audit_event,
        "file_explorer",
        details={"batch_count": len(sources), "destination": destination_dir, "mode": "task"},
    )
    scope_context = require_file_explorer_tasks_scoped(
        request,
        api_context=api_context,
        current_user=current_user,
    )
    return await start_batch_task_operation(
        request,
        scope_context.file_explorer_tasks,
        scope_context.root_scope,
        current_user["id"],
        sources,
        destination_dir,
        start_call=start_call,
        coerce_operation=coerce_operation,
        log_message=log_message,
        server_error_message=server_error_message,
    )
