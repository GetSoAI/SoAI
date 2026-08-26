"""SoAI - Dependency bundle for the application backup service [backend/app/backup/service_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from app.backup.internal_protocols import (
        ConfigProviderProtocol,
        FilesProviderProtocol,
    )
    from core.config.protocols import ConfigManagerProtocol
    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.licensing.types import Edition
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
    )

__all__ = ("ApplicationBackupServiceDependencies",)


@dataclasses.dataclass(slots=True, frozen=True)
class ApplicationBackupServiceDependencies:
    edition: Edition
    config: ConfigProviderProtocol
    files: FilesProviderProtocol
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    task_finalizer_tracker: TaskFinalizerTrackerProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    database_core: DatabaseCoreProtocol
    database_notifications: DatabaseNotificationsProtocol
    orchestrator_control: OrchestratorControlProtocol
    config_manager: ConfigManagerProtocol
    storage_manager: StorageManagerProtocol
    request_restart: Callable[[str], bool]
    startup_ready_event: asyncio.Event | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationBackupServiceDependencies",
            cancellation_coordinator=self.cancellation_coordinator,
            config=self.config,
            config_manager=self.config_manager,
            database_core=self.database_core,
            database_notifications=self.database_notifications,
            event_bus=self.event_bus,
            edition=self.edition,
            files=self.files,
            orchestrator_control=self.orchestrator_control,
            request_restart=self.request_restart,
            storage_manager=self.storage_manager,
            task_cancellation_binder=self.task_cancellation_binder,
            task_finalizer_tracker=self.task_finalizer_tracker,
            task_registry=self.task_registry,
        )
