"""SoAI - Staged upload commit outcome translation [backend/features/file_explorer/secure_ops/staged_upload_commit_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation import TaskCancelledError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import FileCleanupIncompleteError, FilePublicationUncertainError
from core.files.move_errors import DestinationExistsError
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.files.windows_handle_operations import mark_windows_file_descriptor_for_deletion
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.files.commit_receipt import FileCommitReceipt
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "destination_exists_error",
    "raise_if_cancelled",
    "raise_if_commit_cancelled",
    "raise_publication_failure",
    "release_copy_reservation",
    "settle_upload_copy_resources",
)


def raise_if_cancelled(token: CancellationTokenProtocol) -> None:
    if token.thread_event.is_set():
        raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)


def raise_if_commit_cancelled(
    token: CancellationTokenProtocol,
    source_path: str,
    destination_path: str,
    receipt: FileCommitReceipt,
) -> None:
    if token.thread_event.is_set():
        raise MoveFileCommittedAfterCancellationError(
            cancellation_id=token.cancellation_id,
            source_path=source_path,
            destination_path=destination_path,
            reason=token.cancellation_reason,
            receipt=receipt.to_dict(),
        )


def destination_exists_error(exception: BaseException) -> DestinationExistsError:
    return DestinationExistsError(
        "A file or directory with this name already exists.",
        cause=exception,
    )


def raise_publication_failure(exception: BaseException, *, published: bool) -> NoReturn:
    if isinstance(exception, FilePublicationUncertainError):
        raise exception
    if published:
        raise FilePublicationUncertainError(
            "File publication could not be verified."
        ) from exception
    raise exception


def release_copy_reservation(
    reservation: DiskSpaceReservationLeaseProtocol, *, published: bool
) -> None:
    primary = sys.exception()
    try:
        reservation.release()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if primary is not None:
            primary.add_note(f"Upload reservation release failed: {exception}")
            if isinstance(primary, FilePublicationUncertainError):
                primary.details = {**(primary.details or {}), "cleanup_incomplete": True}
                return
        if published:
            raise_publication_failure(exception, published=True)
        raise FileCleanupIncompleteError(
            "Upload reservation release failed.", cause=exception
        ) from exception


def settle_upload_copy_resources(
    handle: io.BufferedRandom | None,
    reservation: DiskSpaceReservationLeaseProtocol,
    *,
    published: bool,
    temporary_path: str | None,
    delete_by_handle: bool = False,
) -> None:
    primary = sys.exception()
    cleanup_failure: BaseException | None = None
    if handle is not None:
        try:
            if temporary_path is not None and delete_by_handle:
                mark_windows_file_descriptor_for_deletion(handle.fileno())
                temporary_path = None
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            cleanup_failure = exception
        finally:
            try:
                handle.close()
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                if cleanup_failure is None:
                    cleanup_failure = exception
                else:
                    cleanup_failure.add_note(f"Upload temporary close failed: {exception}")
    try:
        reservation.release()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if cleanup_failure is None:
            cleanup_failure = exception
        else:
            cleanup_failure.add_note(f"Upload reservation release failed: {exception}")
    if cleanup_failure is None and temporary_path is None:
        return
    retained_paths = [temporary_path] if temporary_path is not None else []
    if primary is not None:
        primary.add_note(f"Upload copy cleanup incomplete: {cleanup_failure}")
    if isinstance(primary, FilePublicationUncertainError):
        primary.details = {
            **(primary.details or {}),
            "cleanup_incomplete": True,
            "retained_paths": retained_paths,
        }
        return
    failure = (
        FilePublicationUncertainError("Upload resources could not be settled after publication.")
        if published
        else FileCleanupIncompleteError("Upload copy cleanup is incomplete.")
    )
    failure_details: JSONDict = {"cleanup_incomplete": True, "retained_paths": retained_paths}
    failure.details = failure_details
    raise failure from (primary or cleanup_failure)
