"""SoAI - File explorer delete batch task worker [backend/features/file_explorer/task_worker/delete_batch_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SecurityError
from core.events.types_file_explorer import FileExplorerOperation
from core.logging.trace import get_logger
from features.file_explorer.dependencies import (
    FileExplorerDeleteBatchWorkerDependencies,
)
from features.file_explorer.path_resolution import canonicalize_virtual_path
from features.file_explorer.task_worker.batch_task import run_batch_task
from features.file_explorer.workspace_scope import FileSystemRootScope

__all__ = ("FileExplorerDeleteBatchWorker",)

LOGGER_NAME = "SoAI.features.file_explorer.delete_batch_worker"


class FileExplorerDeleteBatchWorker:
    __slots__ = ("_allow_symlinks", "_core", "_task_registry")

    def __init__(self, deps: FileExplorerDeleteBatchWorkerDependencies) -> None:
        self._task_registry = deps.task_registry
        self._core = deps.core
        self._allow_symlinks = bool(deps.allow_symlinks)

    async def delete_batch_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        virtual_paths: list[str],
        *,
        task_id: str,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        _ = user_id
        root_scope = FileSystemRootScope(
            root_path=workspace_path_resolved,
            allow_symlinks=self._allow_symlinks,
        )
        virtual_paths = [canonicalize_virtual_path(root_scope, vp) for vp in virtual_paths]

        async def _process_item(path: str) -> None:
            if path == "/":
                raise SecurityError(
                    "Cannot delete the root directory.",
                    operation="file_explorer.delete_batch_item",
                )
            await self._core.delete_entry(root_scope, path)

        await run_batch_task(
            task_registry=self._task_registry,
            logger=logger,
            task_id=task_id,
            operation=FileExplorerOperation.DELETE,
            item_paths=virtual_paths,
            progress_verb="Deleting",
            action_verb="delete",
            item_error_operation="file_explorer.delete_batch_item",
            cancel_finalization_operation="file_explorer.delete_batch.cancelled.finalize",
            cancel_details={"task_id": task_id},
            process_item=_process_item,
        )
