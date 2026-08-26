"""SoAI - FileManager dependencies dataclass [backend/files/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.files.protocols import DatabaseFilesProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)

__all__ = ("FileManagerDependencies",)


@dataclass(frozen=True, slots=True)
class FileManagerDependencies:
    config: ConfigProtocol
    database_files: DatabaseFilesProtocol
    storage_manager: StorageManagerProtocol
    event_bus: EventBusProtocol
    shutdown_event: asyncio.Event
    storage_root: str
    perform_startup_cleanup: bool
    reconciliation_concurrency: int
    directory_scan_timeout_seconds: float
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileManagerDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            config=self.config,
            database_files=self.database_files,
            storage_manager=self.storage_manager,
            directory_scan_timeout_seconds=self.directory_scan_timeout_seconds,
            event_bus=self.event_bus,
            perform_startup_cleanup=self.perform_startup_cleanup,
            reconciliation_concurrency=self.reconciliation_concurrency,
            shutdown_event=self.shutdown_event,
            storage_root=self.storage_root,
            task_registry=self.task_registry,
            token_collection=self.token_collection,
        )
