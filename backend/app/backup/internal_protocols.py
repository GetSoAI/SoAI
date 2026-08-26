"""SoAI - App backup internal protocols [backend/app/backup/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, overload

from core.backup.types import BackupCreateResult, BackupManifest

if TYPE_CHECKING:
    from core.config.protocols import ConfigManagerProtocol, ConfigValue
    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.licensing.types import Edition
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "BackupRuntimeDependenciesProtocol",
    "BackupScheduleContext",
    "BackupServiceContext",
    "BackupTargetParams",
    "ConfigProviderProtocol",
    "FilesProviderProtocol",
    "RestoreCopyFuncProtocol",
    "RestoreRuntimeQuiescenceProtocol",
    "RestoreTaskRunnerContext",
)


class ConfigProviderProtocol(Protocol):
    @overload
    def get(self, key: str, default: ConfigValue) -> ConfigValue: ...

    @overload
    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None: ...

    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None: ...


class FilesProviderProtocol(Protocol):
    def resolve_path(self, path: str) -> str: ...


class RestoreRuntimeQuiescenceProtocol(Protocol):
    async def shutdown(self) -> None: ...


class BackupRuntimeDependenciesProtocol(Protocol):
    @property
    def request_restart(self) -> Callable[[str], bool]: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def task_cancellation_binder(self) -> TaskCancellationBinderProtocol: ...

    @property
    def task_finalizer_tracker(self) -> TaskFinalizerTrackerProtocol: ...

    @property
    def cancellation_coordinator(self) -> CancellationCoordinatorProtocol: ...

    @property
    def database_core(self) -> DatabaseCoreProtocol: ...

    @property
    def database_notifications(self) -> DatabaseNotificationsProtocol: ...

    @property
    def orchestrator_control(
        self,
    ) -> OrchestratorControlProtocol: ...

    @property
    def config_manager(self) -> ConfigManagerProtocol: ...

    @property
    def storage_manager(self) -> StorageManagerProtocol: ...


class BackupServiceContext(Protocol):
    @property
    def edition(self) -> Edition: ...

    @property
    def backups_path(self) -> str: ...

    @property
    def backup_lock(self) -> asyncio.Lock: ...

    @property
    def config(self) -> ConfigProviderProtocol: ...

    @property
    def files(self) -> FilesProviderProtocol: ...

    @property
    def config_manager(self) -> ConfigManagerProtocol: ...

    @property
    def runtime_dependencies(self) -> BackupRuntimeDependenciesProtocol: ...

    def is_operational(self) -> bool: ...

    def require_operational(self) -> None: ...

    def record_backup_timestamp_ms(self, timestamp_ms: int | None) -> None: ...

    async def create_backup(self, *, task_id: str | None = None) -> BackupCreateResult: ...

    async def delete_backup(self, backup_id: str) -> JSONDict: ...


class BackupScheduleContext(BackupServiceContext, Protocol):
    @property
    def backup_interval_hours(self) -> float | None: ...

    @property
    def startup_ready_event(self) -> asyncio.Event | None: ...

    @property
    def backup_shutdown_event(self) -> asyncio.Event | None: ...

    @property
    def backup_schedule_changed_event(self) -> asyncio.Event | None: ...

    @property
    def last_backup_timestamp_ms(self) -> int | None: ...


class RestoreTaskRunnerContext(BackupServiceContext, Protocol):
    @property
    def restore_lock(self) -> asyncio.Lock: ...

    @property
    def restore_runtime_quiescence(self) -> RestoreRuntimeQuiescenceProtocol: ...


class RestoreCopyFuncProtocol(Protocol):
    def __call__(
        self,
        source_path: str,
        destination_path: str,
        /,
        *,
        deadline_monotonic: float | None = None,
    ) -> tuple[int, str]: ...


@dataclass(frozen=True, slots=True)
class BackupTargetParams:
    backup_dir: str
    manifest: BackupManifest
    backed_up_targets: dict[str, list[tuple[str, int]]]
    enabled_targets_map: dict[str, bool]
    disk_reservation: DiskSpaceReservationLeaseProtocol | None
    total_enabled_targets: int
    task_id: str | None
