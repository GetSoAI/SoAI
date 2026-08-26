"""SoAI - File explorer batch route helpers [backend/features/api/routes/file_explorer/batch_operations.py]"""
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
from core.logging.trace import get_logger
from features.api.routes.file_explorer.route_exception_handling import (
    FILE_EXPLORER_ROUTE_EXCEPTIONS,
    handle_file_explorer_route_exception,
)
from features.api.routes.file_explorer.route_paths import (
    canonicalize_non_root_route_path,
    canonicalize_non_root_route_paths,
)
from features.api.routes.file_explorer.serializers import (
    build_dual_path_response,
    serialize_batch_result,
)
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.responses import create_task_accepted_response
from features.file_explorer.path_resolution import canonicalize_virtual_path

__all__ = (
    "run_batch_dir_operation",
    "run_single_entry_operation",
    "start_batch_task_operation",
)

LOGGER_NAME = "SoAI.features.api.batch_operations"

OPERATION_RUN_BATCH_DIR_OPERATION = "file_explorer.run_batch_dir_operation"
OPERATION_START_BATCH_TASK_OPERATION = "file_explorer.start_batch_task_operation"
OPERATION_RUN_SINGLE_ENTRY_OPERATION = "file_explorer.run_single_entry_operation"


async def run_batch_dir_operation(
    request: Request,
    file_explorer_batch: FileExplorerBatchProtocol,
    root_scope: FileSystemRootScopeProtocol,
    sources: list[str],
    destination_dir: str,
    *,
    batch_call: Callable[
        [FileExplorerBatchProtocol, FileSystemRootScopeProtocol, list[str], str],
        Awaitable[BatchOperationResult],
    ],
    coerce_operation: str,
    log_message: str,
    server_error_message: str,
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    try:
        canonical_sources = canonicalize_non_root_route_paths(
            root_scope,
            sources,
            operation=coerce_operation,
            message="Cannot perform this operation on the root directory.",
        )
        canonical_destination = canonicalize_virtual_path(root_scope, destination_dir)
        result = await batch_call(
            file_explorer_batch,
            root_scope,
            canonical_sources,
            canonical_destination,
        )
        payload = serialize_batch_result(result, destination_dir=canonical_destination)
        return JSONResponse(content=payload)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation=coerce_operation,
            operation=OPERATION_RUN_BATCH_DIR_OPERATION,
            log_message=log_message,
            server_error_message=server_error_message,
            log_trace_id=get_request_trace_id(request),
            log_details={"destination_dir": destination_dir},
            handle_disk_space=True,
            disk_space_operation=coerce_operation,
            disk_space_trace_id=get_request_trace_id(request),
            disk_space_details={"destination_dir": destination_dir},
        )


async def start_batch_task_operation(
    request: Request,
    file_explorer_tasks: FileExplorerTaskLauncherProtocol,
    root_scope: FileSystemRootScopeProtocol,
    user_id: int,
    sources: list[str],
    destination_dir: str,
    *,
    start_call: Callable[
        [FileExplorerTaskLauncherProtocol, FileSystemRootScopeProtocol, int, list[str], str],
        Awaitable[str],
    ],
    coerce_operation: str,
    log_message: str,
    server_error_message: str,
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    try:
        canonical_sources = canonicalize_non_root_route_paths(
            root_scope,
            sources,
            operation=coerce_operation,
            message="Cannot perform this operation on the root directory.",
        )
        canonical_destination = canonicalize_virtual_path(root_scope, destination_dir)
        task_id = await start_call(
            file_explorer_tasks,
            root_scope,
            user_id,
            canonical_sources,
            canonical_destination,
        )
        return create_task_accepted_response(task_id=task_id, commit_deadline_ts_ms=None)
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation=coerce_operation,
            operation=OPERATION_START_BATCH_TASK_OPERATION,
            log_message=log_message,
            server_error_message=server_error_message,
            log_trace_id=get_request_trace_id(request),
            log_details={"destination_dir": destination_dir},
            handle_disk_space=True,
            disk_space_operation=coerce_operation,
            disk_space_trace_id=get_request_trace_id(request),
            disk_space_details={"destination_dir": destination_dir},
        )


async def run_single_entry_operation(
    request: Request,
    file_explorer_core: FileExplorerCoreProtocol,
    root_scope: FileSystemRootScopeProtocol,
    source: str,
    destination: str,
    *,
    entry_call: Callable[
        [FileExplorerCoreProtocol, FileSystemRootScopeProtocol, str, str],
        Awaitable[None],
    ],
    coerce_operation: str,
    log_message: str,
    server_error_message: str,
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    try:
        canonical_source = canonicalize_non_root_route_path(
            root_scope,
            source,
            operation=coerce_operation,
            message="Cannot perform this operation on the root directory.",
        )
        canonical_destination = canonicalize_non_root_route_path(
            root_scope,
            destination,
            operation=coerce_operation,
            message="Cannot perform this operation on the root directory.",
        )
        await entry_call(file_explorer_core, root_scope, canonical_source, canonical_destination)
        return JSONResponse(
            content=build_dual_path_response(
                canonical_source,
                canonical_destination,
            ),
        )
    except FILE_EXPLORER_ROUTE_EXCEPTIONS as exception:
        await handle_file_explorer_route_exception(
            request,
            exception=exception,
            logger=logger,
            coerce_operation=coerce_operation,
            operation=OPERATION_RUN_SINGLE_ENTRY_OPERATION,
            log_message=log_message,
            server_error_message=server_error_message,
            log_trace_id=get_request_trace_id(request),
            log_details={"source": source, "destination": destination},
            handle_disk_space=True,
            disk_space_operation=coerce_operation,
            disk_space_trace_id=get_request_trace_id(request),
            disk_space_details={"source": source, "destination": destination},
        )
