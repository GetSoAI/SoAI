"""SoAI - Staged upload commit orchestration [backend/features/file_explorer/secure_ops/staged_upload_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import BoundedBlockingPool, admit_bounded_blocking_call
from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import SecurityError, ValidationError
from core.files.commit_receipt import FileCommitReceipt
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.validation.strict_numbers import require_non_negative_int_strict
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
    expected_sha256: str,
    file_content_pool: BoundedBlockingPool,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
    allow_symlinks: bool,
) -> FileCommitReceipt:
    if not is_canonical_sha256_hexdigest(expected_sha256):
        raise ValidationError("Expected upload digest must be a canonical SHA-256.")
    token.raise_if_cancelled()
    require_non_negative_int_strict(
        expected_size, error_message="Expected staged upload size must be nonnegative."
    )
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
    commit_task = await admit_bounded_blocking_call(
        file_content_pool,
        partial(
            commit_function,
            source_path=source_path,
            destination_path=destination_path,
            destination_root=destination_root,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            token=token,
            storage_manager=storage_manager,
            allow_symlinks=allow_symlinks,
        ),
        deadline=deadline_after(30.0),
    )
    try:
        return await asyncio.shield(commit_task)
    except asyncio.CancelledError as cancellation:
        token.cancel("Task cancelled.")
        try:
            await wait_for_task_completion(commit_task, retain_resources_until_complete=True)
            receipt = commit_task.result()
        except MoveFileCommittedAfterCancellationError:
            raise
        except TaskCancelledError as exception:
            raise cancellation from exception
        raise MoveFileCommittedAfterCancellationError(
            cancellation_id=token.cancellation_id,
            source_path=source_path,
            destination_path=destination_path,
            reason=token.cancellation_reason,
            cancellation_cause=cancellation,
            receipt=receipt.to_dict(),
        ) from cancellation


def _ensure_destination_within_root(destination_root: str, destination_parent: str) -> None:
    root = os.path.abspath(destination_root)
    parent = os.path.abspath(destination_parent)
    try:
        within_root = os.path.commonpath((root, parent)) == root
    except ValueError as exception:
        raise SecurityError("Upload destination is outside the workspace.") from exception
    if not within_root:
        raise SecurityError("Upload destination is outside the workspace.")
