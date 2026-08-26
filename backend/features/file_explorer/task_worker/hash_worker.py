"""SoAI - File explorer hash task worker [backend/features/file_explorer/task_worker/hash_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.bootstrap.files import compute_sha256
from core.concurrency.cancellation_cleanup import shielded_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_progress
from features.file_explorer.dependencies import FileExplorerHashWorkerDependencies
from features.file_explorer.path_resolution import canonicalize_virtual_path
from features.file_explorer.workspace_scope import FileSystemRootScope

__all__ = ("FileExplorerHashWorker",)

LOGGER_NAME = "SoAI.features.file_explorer.hash_worker"
OPERATION_FILE_EXPLORER_COMPUTE_HASH = "file_explorer.compute_hash"
OPERATION_FILE_EXPLORER_COMPUTE_HASH_CANCELLED_FINALIZE = (
    "file_explorer.compute_hash.cancelled.finalize"
)


class FileExplorerHashWorker:
    __slots__ = ("_allow_symlinks", "_task_registry")

    def __init__(self, deps: FileExplorerHashWorkerDependencies) -> None:
        self._task_registry = deps.task_registry
        self._allow_symlinks = bool(deps.allow_symlinks)

    async def compute_hash_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        virtual_path: str,
        *,
        task_id: str,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        _ = user_id
        root_scope = FileSystemRootScope(
            root_path=workspace_path_resolved,
            allow_symlinks=self._allow_symlinks,
        )
        virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
        try:
            real_path = root_scope.resolve(virtual_path)
            if not os.path.isfile(real_path):
                await finalize(
                    self._task_registry,
                    task_id,
                    TaskStatus.FAILED,
                    error_message=f"File not found: {virtual_path}",
                )
                return

            await update_progress(
                self._task_registry,
                task_id,
                0,
                status_message="Computing SHA256 hash...",
            )
            sha256 = await asyncio.to_thread(compute_sha256, real_path)

            await finalize(
                self._task_registry,
                task_id,
                TaskStatus.COMPLETED,
                result={"sha256": sha256},
                status_message="Hash computed successfully",
            )
        except asyncio.CancelledError:
            try:
                await shielded_cleanup(
                    finalize(
                        self._task_registry,
                        task_id,
                        TaskStatus.CANCELLED,
                        error_message="Cancelled.",
                        status_message="Cancelled.",
                    ),
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to finalize cancelled hash task (non-critical).",
                    operation=OPERATION_FILE_EXPLORER_COMPUTE_HASH_CANCELLED_FINALIZE,
                    details={"task_id": task_id},
                    level="debug",
                )
            return
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="file_explorer.compute_hash",
            )
            log_exception(
                logger,
                coerced,
                message="Task compute_hash failed",
                operation=OPERATION_FILE_EXPLORER_COMPUTE_HASH,
            )
            await finalize(
                self._task_registry,
                task_id,
                TaskStatus.FAILED,
                error_message=coerced.message,
                status_message=f"Error: {coerced.message}",
            )
