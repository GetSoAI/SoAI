"""SoAI - Upload staging helpers [backend/core/files/upload_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager

from core.errors.exceptions import ValidationError
from core.files.operations import async_remove
from core.files.protocols import SeekableStreamProtocol
from core.files.staged_transfer import iter_reader_chunks, stage_chunks_to_temp_file

__all__ = (
    "cleanup_temp_file",
    "cleanup_temp_files",
    "resolve_stream_size",
    "stage_stream_to_file",
)


async def resolve_stream_size(stream: SeekableStreamProtocol) -> int:
    def _resolve_size_sync() -> int:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
        return size

    try:
        return await asyncio.to_thread(_resolve_size_sync)
    except (OSError, ValueError, TypeError) as exception:
        raise ValidationError(f"Upload stream is not seekable: {exception}") from exception


async def stage_stream_to_file(
    stream: SeekableStreamProtocol,
    *,
    temp_dir: str,
    suffix: str,
    on_chunk_write_scope: Callable[[int], AbstractContextManager[None]],
    on_chunk_written: Callable[[int], None] | None = None,
    max_bytes: int | None = None,
    expected_size: int | None = None,
) -> str:
    def _write_to_temp() -> str:
        stream.seek(0)
        staged = stage_chunks_to_temp_file(
            iter_reader_chunks(stream.read),
            temp_dir=temp_dir,
            suffix=suffix,
            max_bytes=max_bytes,
            expected_size=expected_size,
            on_chunk_write_scope=on_chunk_write_scope,
            on_chunk_written=on_chunk_written,
        )
        return staged.file_path

    return await asyncio.to_thread(_write_to_temp)


async def cleanup_temp_file(path: str | None) -> None:
    if not path:
        return
    try:
        await async_remove(path)
    except FileNotFoundError:
        return


async def cleanup_temp_files(paths: Iterable[str | None]) -> None:
    first_failure: Exception | asyncio.CancelledError | None = None
    for path in paths:
        try:
            await cleanup_temp_file(path)
        except (OSError, asyncio.CancelledError) as exception:
            if first_failure is None:
                first_failure = exception
            else:
                first_failure.add_note(f"Additional cleanup failure: {exception}")
    if first_failure is not None:
        raise first_failure
