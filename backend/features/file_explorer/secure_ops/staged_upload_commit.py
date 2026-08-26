"""SoAI - Staged upload commit orchestration [backend/features/file_explorer/secure_ops/staged_upload_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exceptions import SecurityError, ValidationError
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from features.file_explorer.secure_ops import (
    staged_upload_commit_posix,
    staged_upload_commit_windows,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("commit_staged_upload",)


async def commit_staged_upload(
    *,
    source_path: str,
    destination_path: str,
    destination_root: str,
    expected_size: int,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
    allow_symlinks: bool,
) -> None:
    token.raise_if_cancelled()
    if expected_size < 0:
        raise ValidationError("Expected staged upload size must be non-negative.")
    destination_parent = os.path.dirname(destination_path)
    destination_name = os.path.basename(destination_path)
    if not destination_parent or not destination_name:
        raise ValidationError("Upload destination path is invalid.")
    _ensure_destination_within_root(destination_root, destination_parent)
    commit_function = (
        staged_upload_commit_windows.commit_windows_staged_upload
        if os.name == "nt"
        else staged_upload_commit_posix.commit_posix_staged_upload
    )
    commit_task = asyncio.create_task(
        asyncio.to_thread(
            commit_function,
            source_path=source_path,
            destination_path=destination_path,
            destination_root=destination_root,
            expected_size=expected_size,
            token=token,
            storage_manager=storage_manager,
            allow_symlinks=allow_symlinks,
        ),
        name="file-explorer-staged-upload-commit",
    )
    try:
        await asyncio.shield(commit_task)
    except asyncio.CancelledError as cancellation:
        token.cancel("Task cancelled.")
        try:
            await uncancel_and_wait(commit_task)
        except MoveFileCommittedAfterCancellationError:
            raise
        except TaskCancelledError as exception:
            raise cancellation from exception
        if not os.path.lexists(source_path) and os.path.lexists(destination_path):
            raise MoveFileCommittedAfterCancellationError(
                cancellation_id=token.cancellation_id,
                source_path=source_path,
                destination_path=destination_path,
                reason=token.cancellation_reason,
                cancellation_cause=cancellation,
            ) from cancellation
        raise


def _ensure_destination_within_root(destination_root: str, destination_parent: str) -> None:
    root = os.path.abspath(destination_root)
    parent = os.path.abspath(destination_parent)
    try:
        within_root = os.path.commonpath((root, parent)) == root
    except ValueError as exception:
        raise SecurityError("Upload destination is outside the workspace.") from exception
    if not within_root:
        raise SecurityError("Upload destination is outside the workspace.")
