"""SoAI - File manager orchestration coordinator [backend/files/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import override

from core.errors.exceptions import StateError
from core.events.subscriptions import subscribe_many
from core.events.types_base import Event
from core.events.types_files import (
    FileContentQuery,
    FileDeleteCommand,
    FileRetrieveQuery,
    FileUploadCommand,
)
from core.events.types_tasks import CancelTaskCommand
from core.filesystem.async_queries import async_isdir
from core.lifecycle.protocols import Shutdownable
from core.logging.trace import get_logger
from core.tasks.cancellation_commands import cancel_via_registry
from files.dependencies import FileManagerDependencies
from files.handlers.content import handle_file_content
from files.handlers.delete import handle_file_delete
from files.handlers.queries import handle_file_retrieve
from files.handlers.upload import handle_file_upload
from files.reconciliation import reconcile_file_storage

__all__ = ("FileManager",)

LOGGER_NAME = "SoAI.files.manager"


class FileManager(Shutdownable):
    def __init__(self, deps: FileManagerDependencies) -> None:
        self._deps = deps
        self._storage_root = deps.storage_root
        self._perform_startup_cleanup = deps.perform_startup_cleanup
        self._reconciliation_concurrency = deps.reconciliation_concurrency
        self._directory_scan_timeout_seconds = deps.directory_scan_timeout_seconds

    async def initialize(self) -> None:
        logger = get_logger(LOGGER_NAME)
        storage_path = self._storage_root
        if not storage_path:
            raise StateError("FileManager storage path is not configured.")
        if not await async_isdir(self._storage_root):
            raise StateError(
                f"FileManager storage path is not configured or does not exist: {storage_path}",
            )
        if self._perform_startup_cleanup:
            await reconcile_file_storage(
                self._deps.database_files,
                self._storage_root,
                self._reconciliation_concurrency,
                self._directory_scan_timeout_seconds,
            )
        else:
            logger.info("Startup file storage reconciliation is disabled via configuration.")
        subscriptions: Mapping[type[Event], Callable[[Event], Awaitable[None]]] = {
            FileUploadCommand: self._on_file_upload,
            FileRetrieveQuery: self._on_file_retrieve,
            FileDeleteCommand: self._on_file_delete,
            FileContentQuery: self._on_file_content,
            CancelTaskCommand: self._on_cancel_task,
        }
        subscribe_many(self._deps.event_bus, subscriptions)
        logger.debug("FileManager initialized and subscribed to file commands.")

    @override
    async def shutdown(self, event: Event | None = None) -> None:
        logger = get_logger(LOGGER_NAME)
        _ = event
        logger.debug("FileManager shutting down.")

    async def _on_file_upload(self, command: Event) -> None:
        if not isinstance(command, FileUploadCommand):
            return
        await handle_file_upload(
            command,
            storage_root=self._storage_root,
            database_files=self._deps.database_files,
            storage_manager=self._deps.storage_manager,
            token_collection=self._deps.token_collection,
            cancellation_history=self._deps.cancellation_history,
            cancellation_event_bus=self._deps.cancellation_event_bus,
            task_registry=self._deps.task_registry,
        )

    async def _on_file_retrieve(self, command: Event) -> None:
        if not isinstance(command, FileRetrieveQuery):
            return
        await handle_file_retrieve(
            command,
            database_files=self._deps.database_files,
            task_registry=self._deps.task_registry,
        )

    async def _on_file_delete(self, command: Event) -> None:
        if not isinstance(command, FileDeleteCommand):
            return
        await handle_file_delete(
            command,
            storage_root=self._storage_root,
            database_files=self._deps.database_files,
            task_registry=self._deps.task_registry,
        )

    async def _on_file_content(self, command: Event) -> None:
        if not isinstance(command, FileContentQuery):
            return
        await handle_file_content(
            command,
            storage_root=self._storage_root,
            database_files=self._deps.database_files,
            cancellation_binder=self._deps.cancellation_binder,
            task_registry=self._deps.task_registry,
            shutdown_event=self._deps.shutdown_event,
        )

    async def _on_cancel_task(self, command: Event) -> None:
        if not isinstance(command, CancelTaskCommand):
            return
        await cancel_via_registry(
            command,
            self._deps.cancellation_coordinator,
            self._deps.cancellation_history,
        )
