"""SoAI - Staged upload commit outcome translation [backend/features/file_explorer/secure_ops/staged_upload_commit_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.files.move_errors import DestinationExistsError
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "destination_exists_error",
    "raise_if_cancelled",
    "raise_if_commit_cancelled",
)


def raise_if_cancelled(token: CancellationTokenProtocol) -> None:
    if token.thread_event.is_set():
        raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)


def raise_if_commit_cancelled(
    token: CancellationTokenProtocol,
    source_path: str,
    destination_path: str,
) -> None:
    if token.thread_event.is_set():
        raise MoveFileCommittedAfterCancellationError(
            cancellation_id=token.cancellation_id,
            source_path=source_path,
            destination_path=destination_path,
            reason=token.cancellation_reason,
        )


def destination_exists_error(exception: BaseException) -> DestinationExistsError:
    return DestinationExistsError(
        "A file or directory with this name already exists.",
        cause=exception,
    )
