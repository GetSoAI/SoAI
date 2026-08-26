"""SoAI - File explorer service composition for application storage assembly [backend/app/composition/storage_file_explorer_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.internal_protocols import LifecycleCoordinatorProtocol
from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.config.protocols import ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.logging.trace import get_logger
from core.plugins.protocols_instance import FilesProtocol
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from core.timing.monotonic import monotonic_ms
from features.file_explorer.batch_service import FileExplorerBatchService
from features.file_explorer.dependencies import (
    FileExplorerBatchServiceDependencies,
    FileExplorerDeleteBatchWorkerDependencies,
    FileExplorerHashWorkerDependencies,
    FileExplorerManagerDependencies,
    FileExplorerTaskLauncherDependencies,
    FileExplorerTransferBatchWorkerDependencies,
)
from features.file_explorer.directory_listing_builder import DirectoryListingBuilder
from features.file_explorer.directory_listing_dependencies import (
    DirectoryListingBuilderDependencies,
    DirectoryListingManagerDependencies,
    DirectoryListingRegistryDependencies,
)
from features.file_explorer.directory_listing_manager import DirectoryListingManager
from features.file_explorer.directory_listing_registry import DirectoryListingRegistry
from features.file_explorer.download_service import (
    FileExplorerDownloadService,
    FileExplorerDownloadServiceDependencies,
)
from features.file_explorer.manager import FileExplorerManager
from features.file_explorer.search_dependencies import (
    FileExplorerSearchServiceDependencies,
)
from features.file_explorer.search_service import FileExplorerSearchService
from features.file_explorer.secure_ops.secure_file_ops import SecureFileOps
from features.file_explorer.task_launcher import FileExplorerTaskLauncher
from features.file_explorer.task_worker.delete_batch_worker import (
    FileExplorerDeleteBatchWorker,
)
from features.file_explorer.task_worker.hash_worker import FileExplorerHashWorker
from features.file_explorer.task_worker.transfer_batch_worker import (
    FileExplorerTransferBatchWorker,
)

__all__ = (
    "FileExplorerServices",
    "build_file_explorer_services",
)

LOGGER_NAME = "SoAI.app.composition.storage_file_explorer_composition"


class FileExplorerServices:
    def __init__(
        self,
        *,
        core: FileExplorerManager,
        batch: FileExplorerBatchService,
        tasks: FileExplorerTaskLauncher,
        search: FileExplorerSearchService,
        download: FileExplorerDownloadService,
        listings: DirectoryListingManager,
    ) -> None:
        self.core = core
        self.batch = batch
        self.tasks = tasks
        self.search = search
        self.download = download
        self.listings = listings


def build_file_explorer_services(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    event_bus: EventBusProtocol,
    task_registry: TaskRegistryProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    storage_manager: StorageManagerProtocol,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
) -> FileExplorerServices:
    logger = get_logger(LOGGER_NAME)
    allow_symlinks = config.get_bool("DATA.FILE_EXPLORER.ALLOW_SYMLINKS")
    secure_ops = SecureFileOps(allow_symlinks=allow_symlinks)
    mutation_locks = AsyncPathTreeLock()
    core = FileExplorerManager(
        FileExplorerManagerDependencies(
            config=config,
            files=files,
            event_bus=event_bus,
            storage_manager=storage_manager,
            secure_ops=secure_ops,
            mutation_locks=mutation_locks,
        ),
    )
    core.initialize()
    lifecycle_coordinator.register_actor(core)
    hash_worker = FileExplorerHashWorker(
        FileExplorerHashWorkerDependencies(
            task_registry=task_registry,
            allow_symlinks=allow_symlinks,
        ),
    )
    delete_batch_worker = FileExplorerDeleteBatchWorker(
        FileExplorerDeleteBatchWorkerDependencies(
            task_registry=task_registry,
            core=core,
            allow_symlinks=allow_symlinks,
        ),
    )
    transfer_batch_worker = FileExplorerTransferBatchWorker(
        FileExplorerTransferBatchWorkerDependencies(
            task_registry=task_registry,
            core=core,
            allow_symlinks=allow_symlinks,
        ),
    )
    batch = FileExplorerBatchService(
        FileExplorerBatchServiceDependencies(
            core=core,
        ),
    )
    tasks = FileExplorerTaskLauncher(
        FileExplorerTaskLauncherDependencies(
            cancellation_binder=cancellation_binder,
            task_registry=task_registry,
            hash_worker=hash_worker,
            delete_batch_worker=delete_batch_worker,
            transfer_batch_worker=transfer_batch_worker,
        ),
    )
    listing_registry = DirectoryListingRegistry(
        DirectoryListingRegistryDependencies(monotonic_clock=monotonic_ms),
    )
    listing_builder = DirectoryListingBuilder(
        DirectoryListingBuilderDependencies(
            config=config,
            files=files,
            mutation_locks=mutation_locks,
            registry=listing_registry,
            task_registry=task_registry,
        ),
    )
    listing_builder.initialize()
    listings = DirectoryListingManager(
        DirectoryListingManagerDependencies(
            builder=listing_builder,
            cancellation_binder=cancellation_binder,
            registry=listing_registry,
            task_registry=task_registry,
        ),
    )
    search = FileExplorerSearchService(
        FileExplorerSearchServiceDependencies(
            config=config,
        ),
    )
    search.initialize()
    download = FileExplorerDownloadService(
        FileExplorerDownloadServiceDependencies(
            config=config,
            files=files,
            storage_manager=storage_manager,
            mutation_locks=mutation_locks,
        ),
    )
    download.initialize()
    logger.debug(
        "FileExplorerManager, BatchService, TaskLauncher, SearchService, DownloadService initialized.",
    )
    return FileExplorerServices(
        core=core,
        batch=batch,
        tasks=tasks,
        search=search,
        download=download,
        listings=listings,
    )
