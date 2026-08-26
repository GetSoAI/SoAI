"""SoAI - Plugin log file history and live streaming [backend/core/logging/plugin_log_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import AsyncGenerator

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.logging.plugin_log_entries import build_plugin_log_entry
from core.types.json import JSONDict

__all__ = (
    "get_recent_plugin_log_entries",
    "stream_plugin_log_batches",
)

_TAIL_CHUNK_SIZE = 65536
_READ_CHUNK_SIZE = 65536
_LOG_NOT_FOUND_MESSAGE = "Plugin log source not found."
_LOG_OPEN_MESSAGE = "Plugin log source could not be opened."
_LOG_INSPECT_MESSAGE = "Plugin log source could not be inspected."
_LOG_REGULAR_FILE_MESSAGE = "Plugin log source must be a regular file."


def _decode_log_line(line_bytes: bytes) -> str:
    return line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")


def _build_entries(source: str, lines: list[str]) -> list[JSONDict]:
    return [build_plugin_log_entry(source, line) for line in lines if line.strip()]


def _read_recent_lines_from_handle(
    handle: io.BufferedReader,
    limit: int,
    end_offset: int,
) -> list[str]:
    if limit <= 0 or end_offset <= 0:
        return []
    chunks: list[bytes] = []
    remaining = end_offset
    newline_count = 0
    while remaining > 0 and newline_count <= limit:
        read_size = min(_TAIL_CHUNK_SIZE, remaining)
        remaining -= read_size
        handle.seek(remaining)
        chunk = handle.read(read_size)
        chunks.append(chunk)
        newline_count += chunk.count(b"\n")
    data = b"".join(reversed(chunks))
    if data and not data.endswith(b"\n"):
        last_newline = data.rfind(b"\n")
        data = b"" if last_newline < 0 else data[: last_newline + 1]
    lines = [_decode_log_line(line) for line in data.splitlines()]
    return [line for line in lines if line.strip()][-limit:]


def get_recent_plugin_log_entries(source: str, path: str, limit: int) -> list[JSONDict]:
    if limit <= 0:
        raise ValidationError("limit must be a positive integer")
    with open_regular_binary_no_symlink(
        path,
        not_found_message=_LOG_NOT_FOUND_MESSAGE,
        symlink_message=_LOG_OPEN_MESSAGE,
        open_message=_LOG_OPEN_MESSAGE,
        inspect_message=_LOG_INSPECT_MESSAGE,
        regular_file_message=_LOG_REGULAR_FILE_MESSAGE,
    ) as handle:
        handle.seek(0, os.SEEK_END)
        end_offset = handle.tell()
        lines = _read_recent_lines_from_handle(handle, limit, end_offset)
    return _build_entries(source, lines)


def _read_completed_lines(handle: io.BufferedReader, pending: bytes) -> tuple[list[str], bytes]:
    chunk = handle.read(_READ_CHUNK_SIZE)
    if not chunk:
        return [], pending
    data = pending + chunk
    if data.endswith(b"\n"):
        raw_lines = data.splitlines()
        remainder = b""
    else:
        last_newline = data.rfind(b"\n")
        if last_newline < 0:
            return [], data
        raw_lines = data[:last_newline].splitlines()
        remainder = data[last_newline + 1 :]
    return [_decode_log_line(line) for line in raw_lines if line.strip()], remainder


async def stream_plugin_log_batches(
    source: str,
    path: str,
    *,
    limit: int,
    batch_size: int,
    shutdown_event: asyncio.Event,
    idle_ping_interval: float,
) -> AsyncGenerator[JSONDict]:
    if limit <= 0:
        raise ValidationError("limit must be a positive integer")
    heartbeat_interval = max(float(idle_ping_interval or 0.0), 0.1)
    pending = b""
    if batch_size <= 0:
        raise ValidationError("batch_size must be a positive integer")
    handle = open_regular_binary_no_symlink(
        path,
        not_found_message=_LOG_NOT_FOUND_MESSAGE,
        symlink_message=_LOG_OPEN_MESSAGE,
        open_message=_LOG_OPEN_MESSAGE,
        inspect_message=_LOG_INSPECT_MESSAGE,
        regular_file_message=_LOG_REGULAR_FILE_MESSAGE,
    )
    try:
        file_identity = os.fstat(handle.fileno())
        device_id = file_identity.st_dev
        inode_id = file_identity.st_ino
        handle.seek(0, os.SEEK_END)
        offset = handle.tell()
        history_lines = _read_recent_lines_from_handle(handle, limit, offset)
        if history_lines:
            yield {
                "type": "batch",
                "mode": "history",
                "entries": _build_entries(source, history_lines),
            }
        handle.seek(offset)
        while not shutdown_event.is_set():
            try:
                current_identity = os.stat(path)
            except FileNotFoundError:
                await asyncio.sleep(heartbeat_interval)
                continue
            if (
                current_identity.st_dev != device_id
                or current_identity.st_ino != inode_id
                or current_identity.st_size < handle.tell()
            ):
                handle.close()
                handle = open_regular_binary_no_symlink(
                    path,
                    not_found_message=_LOG_NOT_FOUND_MESSAGE,
                    symlink_message=_LOG_OPEN_MESSAGE,
                    open_message=_LOG_OPEN_MESSAGE,
                    inspect_message=_LOG_INSPECT_MESSAGE,
                    regular_file_message=_LOG_REGULAR_FILE_MESSAGE,
                )
                file_identity = os.fstat(handle.fileno())
                device_id = file_identity.st_dev
                inode_id = file_identity.st_ino
                pending = b""
            lines, pending = await asyncio.to_thread(_read_completed_lines, handle, pending)
            if lines:
                for index in range(0, len(lines), batch_size):
                    batch_lines = lines[index : index + batch_size]
                    yield {
                        "type": "batch",
                        "mode": "live",
                        "entries": _build_entries(source, batch_lines),
                    }
                continue
            await asyncio.sleep(heartbeat_interval)
    finally:
        handle.close()
