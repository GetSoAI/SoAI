"""SoAI - Upload cancellation cleanup helpers [backend/features/api/routes/file_explorer/upload_transfer_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.logging.protocols import LoggerProtocol

__all__ = (
    "cleanup_cancelled_upload_destination",
    "cleanup_cancelled_upload_destinations",
)

OPERATION_FEATURES_API_ROUTES_FILE_EXPLORER_UPLOAD_TRANSFER_CLEANUP_CLEANUP_CANCELLED_UPLOAD_DESTINATION = (
    "features.api.routes.file_explorer.upload_transfer_cleanup.cleanup_cancelled_upload_destination"
)


async def cleanup_cancelled_upload_destination(
    *,
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    virtual_path: str | None,
    real_path: str | None,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    if virtual_path:
        try:
            await file_explorer_core.delete_entry(root_scope, virtual_path)
            return
        except RECOVERABLE_EXCEPTIONS as delete_error:
            log_handled_exception(
                logger,
                delete_error,
                message="Failed to remove cancelled upload destination (non-critical).",
                operation=OPERATION_FEATURES_API_ROUTES_FILE_EXPLORER_UPLOAD_TRANSFER_CLEANUP_CLEANUP_CANCELLED_UPLOAD_DESTINATION,
                details={"path": virtual_path, "operation": operation},
                level="debug",
            )
    if real_path:
        await async_remove_if_exists(real_path, logger=logger)


async def cleanup_cancelled_upload_destinations(
    *,
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    virtual_paths: Sequence[str],
    real_paths: Sequence[str],
    logger: LoggerProtocol,
    operation: str,
) -> None:
    for virtual_path in virtual_paths:
        await cleanup_cancelled_upload_destination(
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            virtual_path=virtual_path,
            real_path=None,
            logger=logger,
            operation=operation,
        )
    for real_path in real_paths:
        await async_remove_if_exists(real_path, logger=logger)
