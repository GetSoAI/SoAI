"""SoAI - Directory listing session orchestration [backend/features/file_explorer/directory_listing_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine

from core.concurrency.cancellation_cleanup import (
    uncancel_then_cleanup,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import ConflictError, NotFoundError, StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.directory_listing_models import (
    DirectoryListingAdmission,
    DirectoryListingEntryType,
    DirectoryListingLocateResult,
    DirectoryListingPage,
    DirectoryListingSortColumn,
    DirectoryListingSortDirection,
)
from core.files.operations import async_remove_if_exists
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from core.logging.trace import get_logger
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB
from features.file_explorer.background_task_launching import (
    start_file_explorer_background_task,
)
from features.file_explorer.directory_listing_dependencies import (
    DirectoryListingManagerDependencies,
)
from features.file_explorer.directory_listing_queries import (
    DirectoryListingQuery,
    locate_directory_listing_entry,
    read_directory_listing_page,
)
from features.file_explorer.directory_listing_state import DirectoryListingRecord
from features.file_explorer.path_resolution import canonicalize_virtual_path

__all__ = ("DirectoryListingManager",)

LOGGER_NAME = "SoAI.features.file_explorer.directory_listing_manager"


class DirectoryListingManager:
    __slots__ = (
        "_background_tasks",
        "_builder",
        "_cancellation_binder",
        "_registry",
        "_task_registry",
    )

    def __init__(self, deps: DirectoryListingManagerDependencies) -> None:
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._builder = deps.builder
        self._cancellation_binder = deps.cancellation_binder
        self._registry = deps.registry
        self._task_registry = deps.task_registry

    async def start_listing(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> DirectoryListingAdmission:
        await self._reap_expired_records()
        virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
        record = await self._registry.admit(
            listing_id=listing_id,
            user_id=user_id,
            workspace_path=root_scope.root_path,
            virtual_path=virtual_path,
        )
        if not record.should_start:
            task_id = await self._registry.wait_for_task_id(listing_id, user_id=user_id)
            return DirectoryListingAdmission(
                listing_id=listing_id,
                task_id=task_id,
                path=virtual_path,
            )
        try:
            task_id = await start_file_explorer_background_task(
                cancellation_binder=self._cancellation_binder,
                task_registry=self._task_registry,
                track_task=self._track_task,
                task_type=TASK_TYPE_BACKGROUND_JOB,
                user_id=user_id,
                owner_id=f"file_explorer_listing:{listing_id}",
                status_message=f"Indexing {virtual_path}...",
                task_name_prefix="file-explorer-listing-",
                metadata_operation="directory_listing",
                launch_message="Failed to launch directory listing task worker.",
                error_operation="file_explorer.directory_listing.start",
                error_message="Failed to start directory listing.",
                details={"listing_id": listing_id, "path": virtual_path},
                build_worker=lambda worker_task_id: self._builder.build_listing_task(
                    listing_id=listing_id,
                    user_id=user_id,
                    workspace_path=root_scope.root_path,
                    virtual_path=virtual_path,
                    task_id=worker_task_id,
                ),
                on_task_created=lambda created_task_id: self._registry.attach_task(
                    listing_id,
                    task_id=created_task_id,
                ),
            )
        except asyncio.CancelledError:
            await uncancel_then_cleanup(self._registry.mark_failed(listing_id))
            raise
        except HANDLED_RUNTIME_EXCEPTIONS:
            await uncancel_then_cleanup(self._registry.mark_failed(listing_id))
            raise
        return DirectoryListingAdmission(
            listing_id=listing_id,
            task_id=task_id,
            path=virtual_path,
        )

    async def get_page(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
        offset: int,
        limit: int,
        sort_column: DirectoryListingSortColumn,
        sort_direction: DirectoryListingSortDirection,
        entry_type: DirectoryListingEntryType,
    ) -> DirectoryListingPage:
        await self._reap_expired_records()
        record = await self._require_ready_record(
            listing_id=listing_id,
            user_id=user_id,
            root_scope=root_scope,
        )
        async with record.io_lock:
            if await self._registry.get(listing_id, user_id=user_id) is None:
                raise NotFoundError("Directory listing was released.")
            snapshot_path = self._require_snapshot_path(record)
            page = await self._await_snapshot_io(
                asyncio.to_thread(
                    read_directory_listing_page,
                    DirectoryListingQuery(
                        snapshot_path=snapshot_path,
                        offset=offset,
                        limit=limit,
                        sort_column=sort_column,
                        sort_direction=sort_direction,
                        entry_type=entry_type,
                    ),
                ),
            )
        return DirectoryListingPage(
            listing_id=listing_id,
            path=record.virtual_path,
            entries=page.entries,
            total=page.total,
            offset=offset,
            limit=limit,
            has_more=page.has_more,
            next_offset=page.next_offset,
        )

    async def locate(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
        name: str,
        sort_column: DirectoryListingSortColumn,
        sort_direction: DirectoryListingSortDirection,
        entry_type: DirectoryListingEntryType,
    ) -> DirectoryListingLocateResult:
        await self._reap_expired_records()
        record = await self._require_ready_record(
            listing_id=listing_id,
            user_id=user_id,
            root_scope=root_scope,
        )
        try:
            async with record.io_lock:
                if await self._registry.get(listing_id, user_id=user_id) is None:
                    raise NotFoundError("Directory listing was released.")
                offset = await self._await_snapshot_io(
                    asyncio.to_thread(
                        locate_directory_listing_entry,
                        DirectoryListingQuery(
                            snapshot_path=self._require_snapshot_path(record),
                            offset=0,
                            limit=1,
                            sort_column=sort_column,
                            sort_direction=sort_direction,
                            entry_type=entry_type,
                        ),
                        name=name,
                    ),
                )
        except FileNotFoundError as exception:
            raise NotFoundError("Directory entry was not found in the listing.") from exception
        return DirectoryListingLocateResult(offset=offset)

    async def release(self, *, listing_id: str, user_id: int) -> None:
        await self._reap_expired_records()
        record = await self._registry.get(listing_id, user_id=user_id)
        if record is None:
            await uncancel_then_cleanup(
                self._registry.release(listing_id, user_id=user_id),
            )
            return
        await uncancel_then_cleanup(
            self._release_record(
                record,
                listing_id=listing_id,
                user_id=user_id,
            ),
        )

    async def _release_record(
        self,
        record: DirectoryListingRecord,
        *,
        listing_id: str,
        user_id: int,
    ) -> None:
        async with record.io_lock:
            if record.snapshot_path is not None:
                removed = await async_remove_if_exists(
                    record.snapshot_path,
                    logger=get_logger(LOGGER_NAME),
                )
                if not removed and await asyncio.to_thread(os.path.exists, record.snapshot_path):
                    raise StateError("Directory listing snapshot could not be removed.")
            await self._registry.release(listing_id, user_id=user_id)

    async def _reap_expired_records(self) -> None:
        records = await self._registry.reap_expired()
        for record in records:
            await self._release_record(
                record,
                listing_id=record.listing_id,
                user_id=record.user_id,
            )

    async def _require_ready_record(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
    ) -> DirectoryListingRecord:
        record = await self._registry.get(listing_id, user_id=user_id)
        if record is None:
            raise NotFoundError("Directory listing was not found.")
        if record.workspace_path != root_scope.root_path:
            raise NotFoundError("Directory listing was not found.")
        if record.status != "ready":
            raise ConflictError("Directory listing is not ready.")
        return record

    @staticmethod
    def _require_snapshot_path(record: DirectoryListingRecord) -> str:
        if record.snapshot_path is None:
            raise StateError("Ready directory listing is missing its snapshot.")
        return record.snapshot_path

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    @staticmethod
    async def _await_snapshot_io[Result](
        operation: Coroutine[None, None, Result],
    ) -> Result:
        worker = create_ephemeral_task(
            operation,
            name="file-explorer-listing-snapshot-io",
            log_exceptions=False,
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation_exception:
            await wait_for_task_completion(worker)
            if not worker.cancelled():
                worker_exception = worker.exception()
                if worker_exception is not None:
                    cancellation_exception.add_note(
                        f"Directory listing snapshot I/O stopped with: {worker_exception}",
                    )
            raise
