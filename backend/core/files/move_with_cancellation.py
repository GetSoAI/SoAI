"""SoAI - Cancellation-aware file move primitives [backend/core/files/move_with_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import errno
import math
import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.concurrency.protocols import CancellationTokenProtocol
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import FileCommitReceipt
from core.files.move_errors import DestinationExistsError, MoveFileCommittedError
from core.filesystem.atomic_write_primitives import allocate_atomic_temporary_file
from core.filesystem.exclusive_rename import rename_file_without_replacement
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.filesystem.path_coercion import normalize_filesystem_path

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MoveFileCommittedAfterCancellationError",
    "move_file_with_cancellation",
)


class MoveFileCommittedAfterCancellationError(TaskCancelledError):
    code: str | int = "cancelled"
    http_status = 499

    def __init__(
        self,
        *,
        cancellation_id: str,
        source_path: str,
        destination_path: str,
        reason: str | None = None,
        cancellation_cause: BaseException | None = None,
        receipt: JSONDict | None = None,
    ) -> None:
        super().__init__(cancellation_id, reason)
        self.source_path = source_path
        self.destination_path = destination_path
        self.receipt = FileCommitReceipt.from_dict(receipt) if receipt is not None else None
        if cancellation_cause is not None:
            self.cause = cancellation_cause
        details = dict(self.details or {})
        details["source_path"] = source_path
        details["destination_path"] = destination_path
        self.details = details

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (),
            {
                "cancellation_id": self.cancellation_id,
                "source_path": self.source_path,
                "destination_path": self.destination_path,
                "reason": self.reason,
                "cancellation_cause": self.cause,
                "receipt": self.receipt.to_dict() if self.receipt is not None else None,
            },
        )


async def move_file_with_cancellation(
    src: str,
    dst: str,
    token: CancellationTokenProtocol,
    *,
    chunk_size: int = 8 * MIB_BYTES,
    flush_every_chunks: int = 0,
    allow_overwrite: bool = True,
) -> None:
    if not src or not dst:
        raise ValidationError("Source and destination paths must be provided.")
    if chunk_size <= 0:
        raise ValidationError("Chunk size must be positive.")
    if flush_every_chunks < 0:
        raise ValidationError("flush_every_chunks must be non-negative.")
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if os.path.normcase(src) == os.path.normcase(dst):
        raise ValidationError("Source and destination must be different paths.")
    file_size = os.path.getsize(normalize_filesystem_path(src))
    if file_size > 0:
        min_chunks = 32
        target_chunk = max(1, math.ceil(file_size / min_chunks))
        chunk_size = min(chunk_size, target_chunk)
    chunk_size = max(1, int(chunk_size))
    cancellation_probe_interval = 0.005

    def _raise_if_cancelled() -> None:
        if token.thread_event.is_set():
            raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)

    target_committed = False

    def _blocking_copy() -> None:
        nonlocal target_committed
        temp_target: str | None = None
        try:
            _raise_if_cancelled()
            os.makedirs(normalize_filesystem_path(os.path.dirname(dst)), exist_ok=True)
            with open_binary(src, mode="rb") as src_file:
                _raise_if_cancelled()
                descriptor, temp_target = allocate_atomic_temporary_file(
                    dst, file_mode=None, partial=True
                )
                try:
                    dst_file = os.fdopen(descriptor, "wb")
                except (OSError, ValueError):
                    os.close(descriptor)
                    raise
                with dst_file:
                    chunks_written = 0
                    while True:
                        _raise_if_cancelled()
                        chunk = src_file.read(chunk_size)
                        if not chunk:
                            break
                        dst_file.write(chunk)
                        chunks_written += 1
                        if flush_every_chunks and chunks_written % flush_every_chunks == 0:
                            flush_and_fsync_file(dst_file)
                        if token.thread_event.wait(cancellation_probe_interval):
                            raise TaskCancelledError(
                                token.cancellation_id, token.cancellation_reason
                            )
                    flush_and_fsync_file(dst_file)
            if token.thread_event.wait(cancellation_probe_interval):
                raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)
            if allow_overwrite:
                os.replace(normalize_filesystem_path(temp_target), normalize_filesystem_path(dst))
                target_committed = True
                temp_target = None
            else:
                try:
                    rename_file_without_replacement(temp_target, dst)
                except OSError as exception:
                    if exception.errno in {errno.EEXIST, errno.EISDIR}:
                        raise DestinationExistsError(
                            "A file or directory with this name already exists."
                        ) from exception
                    raise
                target_committed = True
                temp_target = None
            os.remove(normalize_filesystem_path(src))
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if target_committed:
                raise MoveFileCommittedError(
                    source_path=src, destination_path=dst, cause=exception
                ) from exception
            raise
        finally:
            if temp_target is not None:
                try:
                    os.remove(normalize_filesystem_path(temp_target))
                except OSError as exception:
                    if target_committed:
                        raise MoveFileCommittedError(
                            source_path=src, destination_path=dst, cause=exception
                        ) from exception
                    raise

    def _cancel_copy() -> None:
        token.cancel("Task cancelled.")

    try:
        await run_joined_thread_call(
            _blocking_copy,
            task_name="core.files.move_with_cancellation.copy",
            retain_resources_until_complete=True,
            on_cancel=_cancel_copy,
        )
        _raise_if_cancelled()
    except TaskCancelledError as exception:
        if target_committed:
            raise MoveFileCommittedAfterCancellationError(
                cancellation_id=token.cancellation_id,
                source_path=src,
                destination_path=dst,
                reason=token.cancellation_reason,
                cancellation_cause=exception,
            ) from exception
        raise
    except asyncio.CancelledError as exception:
        if target_committed:
            raise MoveFileCommittedAfterCancellationError(
                cancellation_id=token.cancellation_id,
                source_path=src,
                destination_path=dst,
                reason=token.cancellation_reason,
                cancellation_cause=exception,
            ) from exception
        raise
