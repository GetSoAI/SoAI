"""SoAI - Browser download file persistence [backend/mcp/tools/browser/download_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write

if TYPE_CHECKING:
    from playwright.async_api import Download

    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("save_browser_download_file",)

OPERATION_SAVE_BROWSER_DOWNLOAD = "mcp.browser.download.save_file"
_COPY_CHUNK_BYTES = MIB_BYTES


def _create_temp_path(downloads_dir: str) -> str:
    file_descriptor, temp_path = create_secure_temp_file_descriptor(
        directory=downloads_dir,
        prefix=".soai_browser_download_",
        suffix=".part",
    )
    os.close(file_descriptor)
    return temp_path


def _cleanup_temp_path(temp_path: str) -> None:
    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)


def _link_temp_to_target(temp_path: str, target_path: str) -> None:
    try:
        os.link(temp_path, target_path)
    except FileExistsError as exception:
        raise ValidationError("A browser download target file already exists.") from exception
    os.remove(temp_path)


def _copy_artifact_to_temp(source_path: str, temp_path: str) -> int:
    bytes_written = 0
    with (
        open_binary(source_path, mode="rb") as source_file,
        open_binary(temp_path, mode="wb") as target_file,
    ):
        while True:
            chunk = source_file.read(_COPY_CHUNK_BYTES)
            if not chunk:
                break
            target_file.write(chunk)
            bytes_written += len(chunk)
        flush_and_fsync_file(target_file)
    return bytes_written


async def _save_from_artifact_path(
    *,
    storage_manager: StorageManagerProtocol,
    source_path: str,
    target_path: str,
    temp_path: str,
    download_url: str,
    expected_size_bytes: int | None,
) -> int:
    source_size = await asyncio.to_thread(os.path.getsize, source_path)
    details = {
        "url": download_url,
        "target_path": target_path,
        "expected_size_bytes": expected_size_bytes,
        "source_size_bytes": source_size,
    }
    with (
        storage_manager.reserve_disk_space(
            path=target_path,
            required_bytes=source_size,
            operation=OPERATION_SAVE_BROWSER_DOWNLOAD,
            details=details,
        ) as reservation,
        claim_reserved_write(reservation, size_bytes=source_size),
    ):
        copied_bytes = await asyncio.to_thread(
            _copy_artifact_to_temp,
            source_path,
            temp_path,
        )
    if copied_bytes != source_size:
        raise ValidationError("Browser download artifact size changed while saving.")
    await asyncio.to_thread(_link_temp_to_target, temp_path, target_path)
    return copied_bytes


async def _save_via_playwright(
    *,
    storage_manager: StorageManagerProtocol,
    download: Download,
    target_path: str,
    temp_path: str,
    download_url: str,
    expected_size_bytes: int | None,
) -> int:
    reservation_size = max(0, int(expected_size_bytes or 0))
    details = {
        "url": download_url,
        "target_path": target_path,
        "expected_size_bytes": expected_size_bytes,
    }
    if reservation_size > 0:
        with storage_manager.reserve_disk_space(
            path=target_path,
            required_bytes=reservation_size,
            operation=OPERATION_SAVE_BROWSER_DOWNLOAD,
            details=details,
        ) as reservation:
            with claim_reserved_write(reservation, size_bytes=reservation_size):
                await download.save_as(temp_path)
    else:
        await download.save_as(temp_path)
    actual_size = await asyncio.to_thread(os.path.getsize, temp_path)
    if 0 < reservation_size < actual_size:
        raise ValidationError(
            "Browser download exceeded the reserved Content-Length size while saving.",
        )
    await asyncio.to_thread(_link_temp_to_target, temp_path, target_path)
    return actual_size


async def save_browser_download_file(
    *,
    storage_manager: StorageManagerProtocol,
    download: Download,
    downloads_dir: str,
    target_path: str,
    download_url: str,
    expected_size_bytes: int | None,
) -> int:
    temp_path = await asyncio.to_thread(_create_temp_path, downloads_dir)
    completed = False
    try:
        try:
            source_path = await download.path()
        except Error:
            source_path = None
        if isinstance(source_path, str) and source_path.strip():
            saved_bytes = await _save_from_artifact_path(
                storage_manager=storage_manager,
                source_path=source_path,
                target_path=target_path,
                temp_path=temp_path,
                download_url=download_url,
                expected_size_bytes=expected_size_bytes,
            )
            completed = True
            return saved_bytes
        saved_bytes = await _save_via_playwright(
            storage_manager=storage_manager,
            download=download,
            target_path=target_path,
            temp_path=temp_path,
            download_url=download_url,
            expected_size_bytes=expected_size_bytes,
        )
        completed = True
        return saved_bytes
    finally:
        if not completed:
            await asyncio.to_thread(_cleanup_temp_path, temp_path)
