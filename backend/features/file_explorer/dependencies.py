"""SoAI - File explorer dependency bundles [backend/features/file_explorer/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.files.protocols import FilesPathResolverProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from features.file_explorer.internal_protocols import (
    FileExplorerCoreProtocol,
    FileExplorerDeleteBatchWorkerProtocol,
    FileExplorerHashWorkerProtocol,
    FileExplorerTransferBatchWorkerProtocol,
    SecureFileOpsProtocol,
)

__all__ = (
    "FileExplorerBatchServiceDependencies",
    "FileExplorerDeleteBatchWorkerDependencies",
    "FileExplorerHashWorkerDependencies",
    "FileExplorerManagerDependencies",
    "FileExplorerTaskLauncherDependencies",
    "FileExplorerTransferBatchWorkerDependencies",
)


@dataclass(frozen=True, slots=True)
class FileExplorerManagerDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    event_bus: EventBusProtocol
    storage_manager: StorageManagerProtocol
    secure_ops: SecureFileOpsProtocol
    mutation_locks: AsyncPathTreeLock

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerManagerDependencies",
            config=self.config,
            event_bus=self.event_bus,
            files=self.files,
            mutation_locks=self.mutation_locks,
            secure_ops=self.secure_ops,
            storage_manager=self.storage_manager,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerBatchServiceDependencies:
    core: FileExplorerCoreProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerBatchServiceDependencies",
            core=self.core,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerTaskLauncherDependencies:
    cancellation_binder: TaskCancellationBinderProtocol
    task_registry: TaskRegistryProtocol
    hash_worker: FileExplorerHashWorkerProtocol
    delete_batch_worker: FileExplorerDeleteBatchWorkerProtocol
    transfer_batch_worker: FileExplorerTransferBatchWorkerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerTaskLauncherDependencies",
            cancellation_binder=self.cancellation_binder,
            delete_batch_worker=self.delete_batch_worker,
            hash_worker=self.hash_worker,
            task_registry=self.task_registry,
            transfer_batch_worker=self.transfer_batch_worker,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerHashWorkerDependencies:
    task_registry: TaskRegistryProtocol
    allow_symlinks: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerHashWorkerDependencies",
            allow_symlinks=self.allow_symlinks,
            task_registry=self.task_registry,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerDeleteBatchWorkerDependencies:
    task_registry: TaskRegistryProtocol
    core: FileExplorerCoreProtocol
    allow_symlinks: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerDeleteBatchWorkerDependencies",
            allow_symlinks=self.allow_symlinks,
            core=self.core,
            task_registry=self.task_registry,
        )


@dataclass(frozen=True, slots=True)
class FileExplorerTransferBatchWorkerDependencies:
    task_registry: TaskRegistryProtocol
    core: FileExplorerCoreProtocol
    allow_symlinks: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerTransferBatchWorkerDependencies",
            allow_symlinks=self.allow_symlinks,
            core=self.core,
            task_registry=self.task_registry,
        )
