"""SoAI - Temp-file capture and replay for deduplicated binary streams [backend/orchestrator/execution/binary_dedup_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Awaitable
from dataclasses import dataclass

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.file_sync import flush_and_fsync_file
from core.logging.protocols import TraceLogger
from core.tasks.task import Task
from orchestrator.execution.stream_delivery import deliver_stream_chunk

__all__ = (
    "BinaryReplayRecorder",
    "replay_binary_replay_file",
)

BINARY_DEDUP_REPLAY_CHUNK_SIZE = 64 * 1024


def _create_binary_replay_file(temp_directory: str) -> tuple[io.BufferedIOBase, str]:
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=temp_directory,
        prefix="tts_dedup_",
        suffix=".bin",
    )
    try:
        return (os.fdopen(file_descriptor, "wb"), temp_path)
    except OSError:
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            _ = close_exception
        try:
            os.remove(temp_path)
        except FileNotFoundError as remove_exception:
            _ = remove_exception
        raise


def _flush_and_close(file_handle: io.BufferedIOBase) -> None:
    flush_exception: OSError | None = None
    try:
        flush_and_fsync_file(file_handle)
    except OSError as exception:
        flush_exception = exception
    file_handle.close()
    if flush_exception is not None:
        raise flush_exception


def _close_and_remove_binary_replay_file(
    file_handle: io.BufferedIOBase,
    temp_path: str,
) -> None:
    close_exception: OSError | None = None
    try:
        file_handle.close()
    except OSError as exception:
        close_exception = exception
    try:
        os.remove(temp_path)
    except FileNotFoundError as exception:
        _ = exception
    if close_exception is not None:
        raise close_exception


async def _await_blocking_file_io(
    awaitable: Awaitable[int | None],
    *,
    timeout_sec: float,
) -> None:
    async def await_io() -> None:
        _ = await awaitable

    io_task = asyncio.create_task(
        await_io(),
        name="orchestrator.execution.binary_dedup_replay.file_io",
    )
    try:
        return await asyncio.wait_for(asyncio.shield(io_task), timeout=timeout_sec)
    except TimeoutError:
        await uncancel_and_wait(io_task)
        raise
    except asyncio.CancelledError:
        await uncancel_and_wait(io_task)
        raise


@dataclass(slots=True)
class BinaryReplayRecorder:
    temp_path: str
    _file_handle: io.BufferedIOBase

    @classmethod
    async def create(cls, temp_directory: str) -> BinaryReplayRecorder:
        file_handle, temp_path = await uncancel_and_wait(
            asyncio.to_thread(_create_binary_replay_file, temp_directory),
        )
        return cls(temp_path=temp_path, _file_handle=file_handle)

    async def write_chunk(self, chunk_bytes: bytes, *, timeout_sec: float) -> None:
        await _await_blocking_file_io(
            asyncio.to_thread(self._file_handle.write, chunk_bytes),
            timeout_sec=timeout_sec,
        )

    async def finalize(self, *, timeout_sec: float) -> str:
        await _await_blocking_file_io(
            asyncio.to_thread(_flush_and_close, self._file_handle),
            timeout_sec=timeout_sec,
        )
        return self.temp_path

    async def discard(self) -> None:
        await uncancel_and_wait(
            asyncio.to_thread(
                _close_and_remove_binary_replay_file,
                self._file_handle,
                self.temp_path,
            ),
        )


async def replay_binary_replay_file(
    *,
    task: Task,
    temp_path: str,
    streaming_chunk_delivery_timeout: float,
    logger: TraceLogger,
) -> None:
    file_handle = await uncancel_and_wait(asyncio.to_thread(open, temp_path, "rb"))
    try:
        while True:
            chunk_bytes = await uncancel_and_wait(
                asyncio.to_thread(file_handle.read, BINARY_DEDUP_REPLAY_CHUNK_SIZE),
            )
            if not isinstance(chunk_bytes, bytes) or not chunk_bytes:
                break
            await deliver_stream_chunk(
                task=task,
                chunk_bytes=chunk_bytes,
                streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
                operation="orchestrator.propagate_dedup_result.binary_replay",
                logger=logger,
            )
    finally:
        await uncancel_and_wait(asyncio.to_thread(file_handle.close))
