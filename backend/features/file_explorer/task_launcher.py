"""SoAI - File explorer background task launcher [backend/features/file_explorer/task_launcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError, StateError
from core.tasks.type_catalog import TASK_TYPE_FILE_EXPLORER_OP
from features.file_explorer.background_task_launching import (
    start_file_explorer_background_task,
)
from features.file_explorer.dependencies import FileExplorerTaskLauncherDependencies
from features.file_explorer.path_resolution import canonicalize_virtual_path

if TYPE_CHECKING:
    from core.files.protocols_explorer import FileSystemRootScopeProtocol

__all__ = ("FileExplorerTaskLauncher",)


class FileExplorerTaskLauncher:
    __slots__ = (
        "_background_tasks",
        "_cancellation_binder",
        "_delete_batch_worker",
        "_hash_worker",
        "_task_registry",
        "_transfer_batch_worker",
    )

    def __init__(self, deps: FileExplorerTaskLauncherDependencies) -> None:
        self._cancellation_binder = deps.cancellation_binder
        self._task_registry = deps.task_registry
        self._hash_worker = deps.hash_worker
        self._delete_batch_worker = deps.delete_batch_worker
        self._transfer_batch_worker = deps.transfer_batch_worker
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def start_hash_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        virtual_path: str,
    ) -> str:
        virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
        return await start_file_explorer_background_task(
            cancellation_binder=self._cancellation_binder,
            task_registry=self._task_registry,
            track_task=self._track_task,
            task_type=TASK_TYPE_FILE_EXPLORER_OP,
            user_id=user_id,
            owner_id=f"file_explorer_hash:{virtual_path}",
            status_message=f"Hashing {virtual_path}...",
            task_name_prefix="file-explorer-hash-",
            metadata_operation="hash",
            launch_message="Failed to launch file explorer hash task worker.",
            error_operation="file_explorer.task_launcher.start_hash_task",
            error_message="Failed to start hash task.",
            details={"path": virtual_path},
            build_worker=lambda task_id: self._hash_worker.compute_hash_async(
                user_id,
                root_scope.root_path,
                virtual_path,
                task_id=task_id,
            ),
        )

    async def start_delete_batch_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        virtual_paths: list[str],
    ) -> str:
        virtual_paths = [
            canonicalize_virtual_path(root_scope, virtual_path) for virtual_path in virtual_paths
        ]
        if any(vp == "/" for vp in virtual_paths):
            raise SecurityError(
                "Cannot delete the root directory.",
                operation="file_explorer.start_delete_batch_task",
            )
        return await start_file_explorer_background_task(
            cancellation_binder=self._cancellation_binder,
            task_registry=self._task_registry,
            track_task=self._track_task,
            task_type=TASK_TYPE_FILE_EXPLORER_OP,
            user_id=user_id,
            owner_id="file_explorer_delete:batch",
            status_message=f"Deleting {len(virtual_paths)} entries...",
            task_name_prefix="file-explorer-delete-batch-",
            metadata_operation="delete_batch",
            launch_message="Failed to launch file explorer delete batch task worker.",
            error_operation="file_explorer.task_launcher.start_delete_batch_task",
            error_message="Failed to start delete batch task.",
            details={"count": len(virtual_paths)},
            build_worker=lambda task_id: self._delete_batch_worker.delete_batch_async(
                user_id,
                root_scope.root_path,
                virtual_paths,
                task_id=task_id,
            ),
        )

    async def start_copy_batch_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> str:
        return await self._start_transfer_batch_task(
            root_scope=root_scope,
            user_id=user_id,
            source_paths=source_paths,
            destination_dir=destination_dir,
            operation="copy",
            overwrite=overwrite,
        )

    async def start_move_batch_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> str:
        return await self._start_transfer_batch_task(
            root_scope=root_scope,
            user_id=user_id,
            source_paths=source_paths,
            destination_dir=destination_dir,
            operation="move",
            overwrite=overwrite,
        )

    async def _start_transfer_batch_task(
        self,
        *,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        source_paths: list[str],
        destination_dir: str,
        operation: str,
        overwrite: bool,
    ) -> str:
        source_paths = [
            canonicalize_virtual_path(root_scope, source_path) for source_path in source_paths
        ]
        destination_dir = canonicalize_virtual_path(root_scope, destination_dir)
        config = (
            (
                "copy",
                "file_explorer_copy:batch",
                "Copying",
                "file-explorer-copy-batch-",
            ),
            (
                "move",
                "file_explorer_move:batch",
                "Moving",
                "file-explorer-move-batch-",
            ),
        )
        transfer_operation = next(
            (op_config for op_config in config if op_config[0] == operation),
            None,
        )
        if transfer_operation is None:
            raise StateError(f"Unsupported transfer batch operation: {operation}")
        _, owner_id, status_verb, task_name_prefix = transfer_operation
        return await start_file_explorer_background_task(
            cancellation_binder=self._cancellation_binder,
            task_registry=self._task_registry,
            track_task=self._track_task,
            task_type=TASK_TYPE_FILE_EXPLORER_OP,
            user_id=user_id,
            owner_id=owner_id,
            status_message=f"{status_verb} {len(source_paths)} entries...",
            task_name_prefix=task_name_prefix,
            metadata_operation=f"{operation}_batch",
            launch_message=("Failed to launch file explorer " f"{operation} batch task worker."),
            error_operation=f"file_explorer.task_launcher.start_{operation}_batch_task",
            error_message=f"Failed to start {operation} batch task.",
            details={"count": len(source_paths)},
            build_worker=lambda task_id: (
                self._transfer_batch_worker.copy_batch_async(
                    user_id,
                    root_scope.root_path,
                    source_paths,
                    destination_dir,
                    task_id=task_id,
                    overwrite=overwrite,
                )
                if operation == "copy"
                else self._transfer_batch_worker.move_batch_async(
                    user_id,
                    root_scope.root_path,
                    source_paths,
                    destination_dir,
                    task_id=task_id,
                    overwrite=overwrite,
                )
            ),
        )

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
