"""SoAI - Cancellation-aware file move primitives [backend/core/files/move_with_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import errno
import math
import os
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.protocols import CancellationTokenProtocol
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.move_errors import DestinationExistsError
from core.files.operations import async_remove, async_remove_if_exists
from core.filesystem.async_queries import async_makedirs
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.timing.constants import YIELD_CONTROL_SEC

if TYPE_CHECKING:
    from core.types.json import JSONValue

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
    ) -> None:
        super().__init__(cancellation_id, reason)
        self.source_path = source_path
        self.destination_path = destination_path
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
    file_size = os.path.getsize(src)
    if file_size > 0:
        min_chunks = 32
        target_chunk = max(1, math.ceil(file_size / min_chunks))
        chunk_size = min(chunk_size, target_chunk)
    chunk_size = max(1, int(chunk_size))
    dest_dir = os.path.dirname(dst)
    if dest_dir:
        await async_makedirs(dest_dir, exist_ok=True)
    temp_target = f"{dst}.partial.{uuid.uuid4().hex}"

    cancellation_probe_interval = 0.005

    def _raise_if_cancelled() -> None:
        if token.thread_event.is_set():
            raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)

    def _raise_if_committed_and_cancelled() -> None:
        if not target_committed:
            return
        if not token.thread_event.is_set():
            return
        raise MoveFileCommittedAfterCancellationError(
            cancellation_id=token.cancellation_id,
            source_path=src,
            destination_path=dst,
            reason=token.cancellation_reason,
        )

    target_committed = False

    def _blocking_copy() -> None:
        nonlocal target_committed
        _raise_if_cancelled()
        with (
            open_binary(src, mode="rb") as src_file,
            open_binary(temp_target, mode="wb") as dst_file,
        ):
            chunks_written = 0
            while True:
                if token.thread_event.is_set():
                    raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)
                chunk = src_file.read(chunk_size)
                if not chunk:
                    break
                dst_file.write(chunk)
                chunks_written += 1
                if flush_every_chunks and chunks_written % flush_every_chunks == 0:
                    flush_and_fsync_file(dst_file)
                if token.thread_event.wait(cancellation_probe_interval):
                    raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)
            flush_and_fsync_file(dst_file)
        if token.thread_event.wait(cancellation_probe_interval):
            raise TaskCancelledError(token.cancellation_id, token.cancellation_reason)
        if allow_overwrite:
            os.replace(temp_target, dst)
            target_committed = True
            return
        try:
            os.link(temp_target, dst)
        except FileExistsError as exception:
            raise DestinationExistsError(
                "A file or directory with this name already exists.",
            ) from exception
        except OSError as exception:
            if exception.errno in {errno.EEXIST, errno.EISDIR}:
                raise DestinationExistsError(
                    "A file or directory with this name already exists.",
                ) from exception
            raise
        target_committed = True
        os.remove(temp_target)

    try:
        await asyncio.to_thread(_blocking_copy)
        await asyncio.sleep(YIELD_CONTROL_SEC)
        if not target_committed:
            _raise_if_cancelled()
        await async_remove(src)
        _raise_if_committed_and_cancelled()
    except TaskCancelledError as exception:
        if target_committed:
            await async_remove_if_exists(src)
            raise MoveFileCommittedAfterCancellationError(
                cancellation_id=token.cancellation_id,
                source_path=src,
                destination_path=dst,
                reason=token.cancellation_reason,
                cancellation_cause=exception,
            ) from exception
        await async_remove_if_exists(temp_target)
        raise
    except asyncio.CancelledError as exception:
        if not token.thread_event.is_set():
            token.cancel("Task cancelled.")
        await async_remove_if_exists(temp_target)
        if target_committed:
            await async_remove_if_exists(src)
            raise MoveFileCommittedAfterCancellationError(
                cancellation_id=token.cancellation_id,
                source_path=src,
                destination_path=dst,
                reason=token.cancellation_reason,
                cancellation_cause=exception,
            ) from exception
        raise
    except DestinationExistsError:
        await async_remove_if_exists(temp_target)
        raise
    except RECOVERABLE_EXCEPTIONS:
        await async_remove_if_exists(temp_target)
        raise
