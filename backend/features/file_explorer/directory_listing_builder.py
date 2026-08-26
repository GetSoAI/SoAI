"""SoAI - Directory listing snapshot task execution [backend/features/file_explorer/directory_listing_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import sqlite3

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import (
    uncancel_and_wait,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.files.temp_files import create_secure_temp_file_descriptor
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_progress
from features.file_explorer.directory_listing_dependencies import (
    DirectoryListingBuilderDependencies,
)
from features.file_explorer.directory_listing_snapshot import (
    build_directory_listing_snapshot,
)
from features.file_explorer.directory_listing_state import DirectoryListingRecord
from features.file_explorer.runtime_settings import (
    resolve_file_explorer_runtime_settings,
)
from features.file_explorer.workspace_scope import FileSystemRootScope

__all__ = ("DirectoryListingBuilder",)

LOGGER_NAME = "SoAI.features.file_explorer.directory_listing_builder"
OPERATION_BUILD_DIRECTORY_LISTING = "file_explorer.directory_listing.build"
DIRECTORY_LISTING_HANDLED_EXCEPTIONS = HANDLED_RUNTIME_EXCEPTIONS + (sqlite3.Error,)


class DirectoryListingBuilder:
    __slots__ = (
        "_allow_symlinks",
        "_config",
        "_files",
        "_mutation_locks",
        "_registry",
        "_task_registry",
        "_temp_directory",
    )

    def __init__(self, deps: DirectoryListingBuilderDependencies) -> None:
        self._config = deps.config
        self._files = deps.files
        self._mutation_locks = deps.mutation_locks
        self._registry = deps.registry
        self._task_registry = deps.task_registry
        self._allow_symlinks = False
        self._temp_directory = ""

    def initialize(self) -> None:
        settings = resolve_file_explorer_runtime_settings(self._config, self._files)
        self._allow_symlinks = settings.allow_symlinks
        self._temp_directory = settings.temp_dir

    async def build_listing_task(
        self,
        *,
        listing_id: str,
        user_id: int,
        workspace_path: str,
        virtual_path: str,
        task_id: str,
    ) -> None:
        record = await self._registry.get(listing_id, user_id=user_id)
        if record is None:
            await self._finalize_cancelled(task_id, "Directory listing was released.")
            return
        snapshot_path: str | None = None
        try:
            root_scope = FileSystemRootScope(
                root_path=workspace_path,
                allow_symlinks=self._allow_symlinks,
            )
            real_path = root_scope.resolve(virtual_path)
            file_descriptor, snapshot_path = create_secure_temp_file_descriptor(
                directory=self._temp_directory,
                prefix="soai-file-listing-",
                suffix=".sqlite3",
            )
            os.close(file_descriptor)
            await update_progress(
                self._task_registry,
                task_id,
                0,
                status_message="Indexing directory...",
            )
            total = await self._run_snapshot_worker(
                record=record,
                real_path=real_path,
                snapshot_path=snapshot_path,
            )
            async with record.io_lock:
                if record.cancellation_event.is_set():
                    raise TaskCancelledError(
                        "file_explorer_listing",
                        "Directory listing was cancelled.",
                    )
                if not await self._registry.mark_ready(
                    listing_id,
                    snapshot_path=snapshot_path,
                ):
                    await self._remove_snapshot(snapshot_path)
                    await self._finalize_cancelled(
                        task_id,
                        "Directory listing was released.",
                    )
                    return
                await finalize(
                    self._task_registry,
                    task_id,
                    TaskStatus.COMPLETED,
                    result={"listing_id": listing_id, "total": total},
                    status_message="Directory indexed.",
                )
        except asyncio.CancelledError:
            record.cancellation_event.set()
            await uncancel_and_wait(
                self._cancel_listing(
                    listing_id=listing_id,
                    task_id=task_id,
                    snapshot_path=snapshot_path,
                ),
            )
        except TaskCancelledError:
            record.cancellation_event.set()
            await self._cancel_listing(
                listing_id=listing_id,
                task_id=task_id,
                snapshot_path=snapshot_path,
            )
        except DIRECTORY_LISTING_HANDLED_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_BUILD_DIRECTORY_LISTING,
            )
            log_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Directory listing snapshot failed.",
                operation=OPERATION_BUILD_DIRECTORY_LISTING,
                details={"listing_id": listing_id, "task_id": task_id},
            )
            await self._handle_failure(
                listing_id=listing_id,
                task_id=task_id,
                snapshot_path=snapshot_path,
            )

    async def _run_snapshot_worker(
        self,
        *,
        record: DirectoryListingRecord,
        real_path: str,
        snapshot_path: str,
    ) -> int:
        async with self._mutation_locks.lock(real_path):
            worker = create_ephemeral_task(
                asyncio.to_thread(
                    build_directory_listing_snapshot,
                    snapshot_path=snapshot_path,
                    real_path=real_path,
                    cancellation_event=record.cancellation_event,
                    allow_symlinks=self._allow_symlinks,
                ),
                name=f"file-explorer-listing-{record.listing_id}",
                log_exceptions=False,
            )
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError as cancellation_exception:
                record.cancellation_event.set()
                await wait_for_task_completion(worker)
                if not worker.cancelled():
                    worker_exception = worker.exception()
                    if worker_exception is not None:
                        raise worker_exception from cancellation_exception
                raise

    async def _handle_failure(
        self,
        *,
        listing_id: str,
        task_id: str,
        snapshot_path: str | None,
    ) -> None:
        await self._remove_snapshot(snapshot_path)
        await self._registry.mark_failed(listing_id)
        await finalize(
            self._task_registry,
            task_id,
            TaskStatus.FAILED,
            error_message="Directory indexing failed.",
            status_message="Directory indexing failed.",
        )

    async def _cancel_listing(
        self,
        *,
        listing_id: str,
        task_id: str,
        snapshot_path: str | None,
    ) -> None:
        await self._remove_snapshot(snapshot_path)
        await self._registry.mark_failed(listing_id)
        await self._finalize_cancelled(task_id, "Cancelled.")

    @staticmethod
    async def _remove_snapshot(snapshot_path: str | None) -> None:
        if snapshot_path is None:
            return
        await async_remove_if_exists(snapshot_path, logger=get_logger(LOGGER_NAME))

    async def _finalize_cancelled(self, task_id: str, message: str) -> None:
        await finalize(
            self._task_registry,
            task_id,
            TaskStatus.CANCELLED,
            error_message=message,
            status_message=message,
        )
