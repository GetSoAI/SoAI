"""SoAI - File explorer copy/move batch task worker [backend/features/file_explorer/task_worker/transfer_batch_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import NotFoundError, ValidationError
from core.events.types_file_explorer import FileExplorerOperation
from core.logging.trace import get_logger
from features.file_explorer.dependencies import (
    FileExplorerTransferBatchWorkerDependencies,
)
from features.file_explorer.path_resolution import canonicalize_virtual_path
from features.file_explorer.task_worker.batch_task import run_batch_task
from features.file_explorer.workspace_scope import FileSystemRootScope

__all__ = ("FileExplorerTransferBatchWorker",)

LOGGER_NAME = "SoAI.features.file_explorer.transfer_batch_worker"


class FileExplorerTransferBatchWorker:
    __slots__ = ("_allow_symlinks", "_core", "_task_registry")

    def __init__(self, deps: FileExplorerTransferBatchWorkerDependencies) -> None:
        self._task_registry = deps.task_registry
        self._core = deps.core
        self._allow_symlinks = bool(deps.allow_symlinks)

    async def copy_batch_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        source_paths: list[str],
        destination_dir: str,
        *,
        task_id: str,
        overwrite: bool = False,
    ) -> None:
        _ = user_id
        await self._batch_transfer_async(
            task_id,
            workspace_path_resolved,
            source_paths,
            destination_dir,
            operation=FileExplorerOperation.COPY,
            overwrite=overwrite,
        )

    async def move_batch_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        source_paths: list[str],
        destination_dir: str,
        *,
        task_id: str,
        overwrite: bool = False,
    ) -> None:
        _ = user_id
        await self._batch_transfer_async(
            task_id,
            workspace_path_resolved,
            source_paths,
            destination_dir,
            operation=FileExplorerOperation.MOVE,
            overwrite=overwrite,
        )

    async def _batch_transfer_async(
        self,
        task_id: str,
        workspace_path_resolved: str,
        source_paths: list[str],
        destination_dir: str,
        operation: FileExplorerOperation,
        overwrite: bool,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        root_scope = FileSystemRootScope(
            root_path=workspace_path_resolved,
            allow_symlinks=self._allow_symlinks,
        )
        source_paths = [canonicalize_virtual_path(root_scope, sp) for sp in source_paths]
        destination_dir = canonicalize_virtual_path(root_scope, destination_dir)
        dest_parent_real = root_scope.resolve(destination_dir)
        if not os.path.isdir(dest_parent_real):
            raise NotFoundError(
                f"Destination directory not found: {destination_dir}",
                operation="file_explorer.batch_transfer",
            )
        reserved_destinations: set[str] = set()

        async def _process_item(src_vpath: str) -> None:
            normalized_src = src_vpath.rstrip("/") or "/"
            src_name = os.path.basename(normalized_src)
            if not src_name:
                raise ValidationError(
                    "Cannot perform batch operation on root directory.",
                )
            dest_vpath = canonicalize_virtual_path(
                root_scope,
                f"{destination_dir.rstrip('/')}/{src_name}",
            )
            if dest_vpath in reserved_destinations:
                raise ValidationError("Duplicate destination path in batch operation.")
            reserved_destinations.add(dest_vpath)
            if operation == FileExplorerOperation.COPY:
                await self._core.copy_entry(root_scope, src_vpath, dest_vpath, overwrite=overwrite)
            else:
                await self._core.move_entry(root_scope, src_vpath, dest_vpath, overwrite=overwrite)

        await run_batch_task(
            task_registry=self._task_registry,
            logger=logger,
            task_id=task_id,
            operation=operation,
            item_paths=source_paths,
            progress_verb=f"{operation.value.capitalize()}ing",
            action_verb=operation.value,
            item_error_operation="file_explorer.batch_transfer_item",
            cancel_finalization_operation="file_explorer.batch_transfer.cancelled.finalize",
            cancel_details={"task_id": task_id, "operation": operation.value},
            process_item=_process_item,
        )
