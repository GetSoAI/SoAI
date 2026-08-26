"""SoAI - File explorer download archive lifecycle [backend/features/file_explorer/download_archive.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from threading import Event

from core.concurrency.cancellation_cleanup import (
    uncancel_and_wait,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.files.explorer_models import FileExplorerDownloadArchive
from core.files.file_identity import FileIdentity
from core.files.operations import async_remove_if_exists
from core.hardware.protocols_storage import StorageManagerProtocol
from core.hardware.reservation_claims import claim_reserved_write
from features.file_explorer.download_archive_plan import build_download_archive_plan
from features.file_explorer.download_archive_writer import write_download_archive

__all__ = ("create_download_archive",)


async def create_download_archive(
    *,
    root_path: str,
    selected_paths: tuple[str, ...],
    temp_directory: str,
    maximum_members: int,
    maximum_archive_bytes: int,
    storage_manager: StorageManagerProtocol,
    mutation_locks: AsyncPathTreeLock,
    cancellation_event: Event,
) -> FileExplorerDownloadArchive:
    _validate_non_overlapping_selection(selected_paths, maximum_members=maximum_members)
    async with mutation_locks.lock_many(selected_paths):
        worker = create_ephemeral_task(
            asyncio.to_thread(
                _create_download_archive_sync,
                root_path=root_path,
                selected_paths=selected_paths,
                temp_directory=temp_directory,
                maximum_members=maximum_members,
                maximum_archive_bytes=maximum_archive_bytes,
                storage_manager=storage_manager,
                cancellation_event=cancellation_event,
            ),
            name="file-explorer-download-archive",
            log_exceptions=False,
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation_exception:
            cancellation_event.set()
            await wait_for_task_completion(worker)
            if worker.cancelled():
                cancellation_exception.add_note(
                    "Download archive worker was cancelled before cleanup completed.",
                )
            else:
                worker_exception = worker.exception()
                if worker_exception is not None:
                    cancellation_exception.add_note(
                        f"Download archive worker stopped with: {worker_exception}",
                    )
                else:
                    try:
                        await uncancel_and_wait(_remove_completed_archive(worker.result()))
                    except OSError as cleanup_exception:
                        cancellation_exception.add_note(
                            f"Cancelled download archive cleanup failed: {cleanup_exception}",
                        )
            raise


async def _remove_completed_archive(result: FileExplorerDownloadArchive) -> None:
    try:
        current_status = await asyncio.to_thread(os.lstat, result.archive_path)
    except FileNotFoundError:
        return
    if FileIdentity.from_stat(current_status) != result.identity:
        return
    await async_remove_if_exists(result.archive_path)


def _create_download_archive_sync(
    *,
    root_path: str,
    selected_paths: tuple[str, ...],
    temp_directory: str,
    maximum_members: int,
    maximum_archive_bytes: int,
    storage_manager: StorageManagerProtocol,
    cancellation_event: Event,
) -> FileExplorerDownloadArchive:
    plan = build_download_archive_plan(
        root_path=root_path,
        selected_paths=selected_paths,
        maximum_members=maximum_members,
        maximum_archive_bytes=maximum_archive_bytes,
        cancellation_event=cancellation_event,
    )
    with storage_manager.reserve_disk_space(
        path=temp_directory,
        required_bytes=plan.required_bytes,
        operation="file_explorer.download_archive",
        details={
            "member_count": len(plan.entries),
            "required_bytes": plan.required_bytes,
        },
    ) as reservation:
        with claim_reserved_write(reservation, size_bytes=plan.required_bytes):
            result = write_download_archive(
                plan=plan,
                root_path=root_path,
                temp_directory=temp_directory,
                cancellation_event=cancellation_event,
            )
    return result


def _validate_non_overlapping_selection(
    selected_paths: tuple[str, ...],
    *,
    maximum_members: int,
) -> None:
    if not selected_paths:
        raise ValidationError("At least one file explorer download path is required.")
    if len(selected_paths) > maximum_members:
        raise PayloadTooLargeError(
            "File explorer download selection exceeds the member limit.",
            details={
                "maximum_members": maximum_members,
                "selected_count": len(selected_paths),
            },
            operation="file_explorer.download_archive.validate_selection",
        )
    normalized_paths = [os.path.normcase(os.path.normpath(path)) for path in selected_paths]
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ValidationError("File explorer download selection contains duplicate paths.")
    selected_set = set(normalized_paths)
    for selected_path in normalized_paths:
        current_path = selected_path
        parent_path = os.path.dirname(current_path)
        while parent_path and parent_path != current_path:
            if parent_path in selected_set:
                raise ValidationError(
                    "File explorer download selection contains overlapping paths.",
                )
            current_path = parent_path
            parent_path = os.path.dirname(current_path)
