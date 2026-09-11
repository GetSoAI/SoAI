"""SoAI - Automated backup creation and management service [backend/app/backup/backup_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override

from app.backup.internal_protocols import (
    BackupRuntimeDependenciesProtocol,
    ConfigProviderProtocol,
    FilesProviderProtocol,
)
from app.backup.lifecycle import (
    execute_initialization,
    execute_shutdown,
    execute_startup,
)
from app.backup.operations import (
    execute_create_backup,
    execute_delete_backup,
    execute_export_archive,
    execute_list_backups,
)
from app.backup.service_dependencies import ApplicationBackupServiceDependencies
from app.backup.task_launching import (
    launch_create_backup_task,
    launch_delete_backup_task,
    launch_restore_backup_task,
    launch_verify_backup_task,
)
from core.backup.types import BackupCreateResult
from core.config.protocols import ConfigManagerProtocol
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.lifecycle.protocols import Shutdownable
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.validation.booleans import parse_bool
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from app.backup.internal_protocols import RestoreRuntimeQuiescenceProtocol
    from core.licensing.types import Edition
    from core.types.json import JSONDict

__all__ = ("ApplicationBackupService",)

LOGGER_NAME = "SoAI.app.backup.backup_service"
OPERATION_APPLICATION_BACKUP_INITIALIZE_RESOLVE_PATH = "application_backup.initialize.resolve_path"
OPERATION_APPLICATION_BACKUP_PERIODIC_LOOP = "application_backup.periodic_loop"


class ApplicationBackupService(Shutdownable):

    def __init__(self, deps: ApplicationBackupServiceDependencies) -> None:
        self.edition: Edition = deps.edition
        self.config: ConfigProviderProtocol = deps.config
        self.files: FilesProviderProtocol = deps.files
        self.runtime_dependencies: BackupRuntimeDependenciesProtocol = deps
        self.config_manager: ConfigManagerProtocol = deps.config_manager
        self.startup_ready_event: asyncio.Event | None = deps.startup_ready_event
        self.backup_lock = asyncio.Lock()
        self.restore_lock = asyncio.Lock()
        self.backup_shutdown_event: asyncio.Event | None = None
        self.backup_schedule_changed_event: asyncio.Event | None = None
        self._backup_task: asyncio.Task[None] | None = None
        self.backups_path: str = ""
        self.backup_interval_hours: float | None = None
        self._run_on_startup: bool = False
        self._initialized: bool = False
        self.last_backup_timestamp_ms: int | None = None
        self._operation_tasks: set[asyncio.Task[None]] = set()
        self._invalid_manifest_log_limiter = RateLimitedLogger(interval_seconds=300.0)
        self._restore_runtime_quiescence: RestoreRuntimeQuiescenceProtocol | None = None

    @property
    def operation_tasks(self) -> set[asyncio.Task[None]]:
        return self._operation_tasks

    @property
    def restore_runtime_quiescence(self) -> RestoreRuntimeQuiescenceProtocol:
        if self._restore_runtime_quiescence is None:
            raise StateError("Restore runtime quiescence is not attached.")
        return self._restore_runtime_quiescence

    def attach_restore_runtime_quiescence(
        self,
        quiescence: RestoreRuntimeQuiescenceProtocol,
    ) -> None:
        if self._restore_runtime_quiescence is not None:
            raise StateError("Restore runtime quiescence is already attached.")
        self._restore_runtime_quiescence = quiescence

    def _handle_backup_task_completion(self, background_task: asyncio.Task[None]) -> None:
        logger = get_logger(LOGGER_NAME)
        if background_task.cancelled():
            return
        try:
            exception = background_task.exception()
        except asyncio.CancelledError:
            return
        if exception is None:
            return
        if isinstance(exception, RECOVERABLE_EXCEPTIONS):
            log_exception(
                logger,
                exception,
                message="Periodic backup task failed",
                operation=OPERATION_APPLICATION_BACKUP_PERIODIC_LOOP,
            )
            return
        coerced = coerce_to_soai_error(
            exception,
            operation="application_backup.periodic_loop",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Periodic backup task raised an unexpected exception (non-critical).",
            operation=OPERATION_APPLICATION_BACKUP_PERIODIC_LOOP,
            level="debug",
        )

    def _is_enabled(self) -> bool:
        return parse_bool(self.config.get("DATA.BACKUP.ENABLED", False), default=False)

    def is_operational(self) -> bool:
        return self._is_enabled() and self._initialized and bool(self.backups_path)

    def require_operational(self) -> None:
        if not self.is_operational():
            raise StateError("Backup service is not operational.")

    def _get_backups_path(self) -> str:
        raw_path = self.config.get("DATA.BACKUP.BACKUPS_PATH")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise StateError("DATA.BACKUP.BACKUPS_PATH is missing or invalid.")
        return self.files.resolve_path(raw_path)

    def record_backup_timestamp_ms(self, timestamp_ms: int | None) -> None:
        if timestamp_ms is None:
            return
        if not is_strict_int(timestamp_ms):
            raise StateError("Backup timestamp must be an integer.")
        self.last_backup_timestamp_ms = int(timestamp_ms)
        if self.backup_schedule_changed_event:
            self.backup_schedule_changed_event.set()

    async def initialize(self) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            backups_path = self._get_backups_path()
        except RECOVERABLE_EXCEPTIONS as path_exception:
            log_handled_exception(
                logger,
                path_exception,
                message="Could not resolve backup path during initialization (non-critical).",
                operation=OPERATION_APPLICATION_BACKUP_INITIALIZE_RESOLVE_PATH,
                level="debug",
            )
            backups_path = ""
        result = await execute_initialization(
            enabled=self._is_enabled(),
            get_backups_path=backups_path,
            config=self.config,
            files=self.files,
            context=self,
            log=logger,
        )
        self.backups_path = result.backups_path
        self.backup_interval_hours = result.backup_interval_hours
        self._run_on_startup = result.run_on_startup
        self._initialized = result.initialized

    async def start(self, *, wait_for_startup_ready: bool = True) -> None:
        logger = get_logger(LOGGER_NAME)
        if not self._is_enabled():
            return
        if not self._initialized or not self.backups_path:
            logger.warning("ApplicationBackupService not properly initialized. Skipping start.")
            return
        self.backup_shutdown_event = asyncio.Event()
        self.backup_schedule_changed_event = asyncio.Event()
        self._backup_task = await execute_startup(
            context=self,
            backups_path=self.backups_path,
            run_on_startup=self._run_on_startup,
            backup_interval_hours=self.backup_interval_hours,
            config=self.config,
            log=logger,
            wait_for_startup_ready=wait_for_startup_ready,
        )
        if self._backup_task is not None:
            self._backup_task.add_done_callback(self._handle_backup_task_completion)

    @override
    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        await execute_shutdown(
            backup_shutdown_event=self.backup_shutdown_event,
            backup_task=self._backup_task,
            operation_tasks=self._operation_tasks,
            log=logger,
        )
        self._backup_task = None

    async def create_backup(
        self,
        *,
        task_id: str | None = None,
    ) -> BackupCreateResult:
        return await execute_create_backup(
            context=self,
            backups_path=self.backups_path,
            backup_lock=self.backup_lock,
            config=self.config,
            task_id=task_id,
        )

    async def list_backups(self) -> list[JSONDict]:
        self.require_operational()
        return await execute_list_backups(
            backups_path=self.backups_path,
            invalid_manifest_log_limiter=self._invalid_manifest_log_limiter,
        )

    async def delete_backup(self, backup_id: str) -> JSONDict:
        self.require_operational()
        return await execute_delete_backup(
            backups_path=self.backups_path,
            backup_lock=self.backup_lock,
            config=self.config,
            backup_id=backup_id,
        )

    async def start_create_backup_task(self, *, user_id: int) -> str:
        return await launch_create_backup_task(
            context=self,
            runtime_deps=self.runtime_dependencies,
            operation_tasks=self._operation_tasks,
            user_id=user_id,
        )

    async def start_verify_backup_task(self, backup_id: str, *, user_id: int) -> str:
        return await launch_verify_backup_task(
            context=self,
            runtime_deps=self.runtime_dependencies,
            operation_tasks=self._operation_tasks,
            backup_id=backup_id,
            user_id=user_id,
        )

    async def start_delete_backup_task(self, backup_id: str, *, user_id: int) -> str:
        return await launch_delete_backup_task(
            context=self,
            runtime_deps=self.runtime_dependencies,
            operation_tasks=self._operation_tasks,
            backups_path=self.backups_path,
            backup_id=backup_id,
            user_id=user_id,
        )

    async def start_restore_backup_task(self, backup_id: str, *, user_id: int) -> str:
        self.require_operational()
        return await launch_restore_backup_task(
            context=self,
            runtime_deps=self.runtime_dependencies,
            operation_tasks=self._operation_tasks,
            backup_id=backup_id,
            user_id=user_id,
        )

    async def create_backup_export_archive(self, backup_id: str) -> str:
        self.require_operational()
        return await execute_export_archive(
            backups_path=self.backups_path,
            backup_lock=self.backup_lock,
            config=self.config,
            storage_manager=self.runtime_dependencies.storage_manager,
            backup_id=backup_id,
        )
