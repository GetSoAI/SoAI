"""SoAI - Receipt-bound upload cancellation cleanup [backend/features/api/routes/file_explorer/upload_transfer_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import shielded_cleanup, wait_for_task_completion
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import SoAIError
from core.errors.public_projection import project_public_error_code, project_public_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import (
    FileCleanupIncompleteError,
    FileCommitReceipt,
    FilePublicationUncertainError,
)
from core.files.protocols_explorer import FileExplorerCoreProtocol, FileSystemRootScopeProtocol
from core.files.upload_staging import cleanup_temp_files
from core.filesystem.operation_errors import build_filesystem_operation_error
from core.types.json import JSONDict

if TYPE_CHECKING:
    from features.api.routes.file_explorer.upload_transfer_progress_pump import UploadProgressPump

__all__ = ("cleanup_cancelled_upload_destinations",)

_RESOURCE_CLEANUP_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    asyncio.CancelledError,
)


async def cleanup_cancelled_upload_destinations(
    *,
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    receipts: Sequence[FileCommitReceipt],
) -> list[str]:
    failures: list[JSONDict] = []
    retained: list[str] = []
    removed: list[str] = []
    for receipt in receipts:
        try:
            await file_explorer_core.cleanup_upload_commit(root_scope, receipt)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            retained.append(receipt.virtual_path)
            public_error = project_public_exception(
                build_filesystem_operation_error(exception)
                if isinstance(exception, OSError)
                else exception
            )
            failures.append({"path": receipt.virtual_path, "error": public_error.to_dict()})
        else:
            removed.append(receipt.virtual_path)
    if retained:
        error = FileCleanupIncompleteError(
            "Some uploaded files could not be safely removed.",
            details={"retained_paths": retained, "removed_paths": removed, "failures": failures},
        )
        error.public_details = {
            "retained_paths": retained,
            "removed_paths": removed,
            "failures": failures,
        }
        raise error
    return removed


@asynccontextmanager
async def settle_upload_resources(
    progress: UploadProgressPump,
    staged_paths: list[str],
) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        primary = sys.exception()
        failures: list[JSONDict] = []
        cancellation: asyncio.CancelledError | None = None
        cleanup_cause: BaseException | None = None
        for operation in (
            progress.close(final_bytes_done=progress.latest_bytes_done or None),
            cleanup_temp_files(staged_paths),
        ):
            try:
                cleanup_task = create_ephemeral_task(
                    operation, name="file-upload-resource-settlement"
                )
                try:
                    await shielded_cleanup(cleanup_task)
                except asyncio.CancelledError as cancel_error:
                    cancellation = cancellation or cancel_error
                    await wait_for_task_completion(
                        cleanup_task, retain_resources_until_complete=True
                    )
                cleanup_task.result()
            except _RESOURCE_CLEANUP_EXCEPTIONS as exception:
                cleanup_cause = cleanup_cause or exception
                if primary is not None:
                    primary.add_note(f"Upload resource cleanup failed: {exception}")
                failure = (
                    project_public_error_code(
                        code="cancelled", message="File cleanup was cancelled."
                    )
                    if isinstance(exception, asyncio.CancelledError)
                    else project_public_exception(
                        build_filesystem_operation_error(exception)
                        if isinstance(exception, OSError)
                        else exception
                    )
                )
                failures.append({"code": failure.code, "message": failure.message})
        if failures:
            if isinstance(primary, FilePublicationUncertainError | FileCleanupIncompleteError):
                primary.public_details = {
                    **(primary.public_details or {}),
                    "cleanup_incomplete": True,
                    "cleanup_failures": failures,
                }
            else:
                cleanup_error = FileCleanupIncompleteError(
                    "Upload resource cleanup is incomplete.", cause=primary or cleanup_cause
                )
                primary_error = (
                    primary.__cause__ if isinstance(primary, asyncio.CancelledError) else primary
                )
                primary_details = (
                    primary_error.public_details if isinstance(primary_error, SoAIError) else None
                )
                cleanup_error.public_details = {
                    **(primary_details or {}),
                    "cleanup_incomplete": True,
                    "cleanup_failures": failures,
                }
                raise cleanup_error from (primary or cleanup_cause)
        if cancellation is not None and primary is None:
            raise cancellation
