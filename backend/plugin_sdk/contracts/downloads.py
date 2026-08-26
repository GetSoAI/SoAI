"""SoAI - Plugin SDK streaming download helpers [backend/plugin_sdk/contracts/downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
import io
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.network.download_reservations import remove_partial_download_file
from core.network.download_temp_files import create_download_temp_handle
from core.network.http_download_metadata import read_http_download_response_metadata
from core.network.http_download_progress import (
    emit_download_progress,
    emit_final_download_progress,
)
from core.network.outbound_http_profiles import build_outbound_request_headers
from core.types.protocols import HttpClientProtocol
from plugin_sdk.contracts.disk_claims import claim_plugin_reserved_write
from plugin_sdk.contracts.progress import DownloadProgressReporter
from plugin_sdk.contracts.resumable_downloads import (
    open_resumable_download,
    range_response_matches,
    resume_offset,
)
from plugin_sdk.filesystem.directory_creation import ensure_parent_dirs_exist

if TYPE_CHECKING:
    from core.plugins.protocols_runtime import (
        PluginStorageReservationLeaseProtocol,
        PluginStorageRuntimeProtocol,
    )
    from core.types.json import JSONValue

    type ChunkObserver = Callable[[int], Awaitable[None] | None]

__all__ = ("async_stream_download_to_file",)

LOGGER_NAME = "SoAI.plugin_sdk.contracts.downloads"
OPERATION_PLUGIN_SDK_DOWNLOADS_CLEANUP_PARTIAL = "plugin_sdk.downloads.cleanup_partial"
OPERATION_PLUGIN_SDK_DOWNLOADS_CLOSE_HANDLE = "plugin_sdk.downloads.close_handle"


async def async_stream_download_to_file(
    *,
    http_client: HttpClientProtocol,
    url: str,
    destination_path: str,
    reservation_provider: PluginStorageRuntimeProtocol,
    headers: Mapping[str, str] | None = None,
    timeout: float = 3600.0,
    follow_redirects: bool = True,
    shutdown_event: asyncio.Event | None = None,
    reporter: DownloadProgressReporter | None = None,
    chunk_observer: ChunkObserver | None = None,
    on_progress: Callable[[int, int | None, float, float], Awaitable[None] | None] | None = None,
    flush_threshold_bytes: int = MIB_BYTES,
    max_bytes: int | None = None,
    reservation_path: str | None = None,
    reservation_operation: str = "plugin_sdk.downloads.stream_download",
    reservation_details: Mapping[str, JSONValue] | None = None,
    resume_partial: bool = False,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not url.strip():
        raise ValidationError("url must be provided.")
    if not destination_path.strip():
        raise ValidationError("destination_path must be provided.")
    if shutdown_event is not None and shutdown_event.is_set():
        raise ValidationError("Shutdown requested before download start.")
    await ensure_parent_dirs_exist([destination_path])

    buffer = bytearray()
    handle: io.BufferedWriter | None = None
    temp_path = ""
    download_completed = False
    declared_reservation: PluginStorageReservationLeaseProtocol | None = None
    bytes_written = 0
    started_at = time.monotonic()
    request_headers = build_outbound_request_headers(
        profile_type="artifact_download",
        extra_headers=headers,
    )
    resume_path = f"{destination_path}.partial"
    resumed_bytes = 0
    if resume_partial:
        resumed_bytes = await asyncio.to_thread(resume_offset, resume_path, max_bytes)
        if max_bytes is not None and resumed_bytes == max_bytes:
            await asyncio.to_thread(os.replace, resume_path, destination_path)
            if reporter is not None:
                await reporter.report_async(resumed_bytes)
                await reporter.finalize_async()
            return
        if resumed_bytes > 0:
            request_headers = {**request_headers, "Range": f"bytes={resumed_bytes}-"}
    try:
        async with http_client.stream(
            "GET",
            url,
            headers=request_headers,
            follow_redirects=follow_redirects,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            append_resume = resumed_bytes > 0 and range_response_matches(
                status_code=response.status_code,
                headers=response.headers,
                offset=resumed_bytes,
            )
            if resumed_bytes > 0 and not append_resume:
                resumed_bytes = 0
            metadata = read_http_download_response_metadata(
                response.headers,
                max_bytes=max_bytes,
            )
            declared_content_length = metadata.declared_content_length
            declared_total_length = (
                declared_content_length + resumed_bytes
                if declared_content_length is not None
                else None
            )
            if max_bytes is not None and (
                resumed_bytes > max_bytes
                or (declared_total_length is not None and declared_total_length > max_bytes)
            ):
                raise ValidationError("Download size exceeds the configured maximum size.")
            if (
                reporter is not None
                and reporter.total_size <= 0
                and declared_total_length is not None
            ):
                reporter.total_size = declared_total_length
            if reporter is not None and resumed_bytes > 0:
                await reporter.report_async(resumed_bytes)
            if declared_content_length is not None and declared_content_length > 0:
                declared_reservation = await reservation_provider.reserve_disk_space(
                    path=reservation_path or destination_path,
                    required_bytes=declared_content_length,
                    operation=reservation_operation,
                    details={
                        "url": url,
                        "destination_path": destination_path,
                        "declared_content_length": declared_content_length,
                        "context": dict(reservation_details or {}),
                    },
                )
            if resume_partial:
                handle = await asyncio.to_thread(
                    open_resumable_download,
                    resume_path,
                    append=append_resume,
                )
                temp_path = resume_path
                bytes_written = resumed_bytes
            else:
                handle, temp_path = await asyncio.to_thread(
                    create_download_temp_handle,
                    destination_path,
                )
            if handle is None:
                raise ValidationError("Failed to open destination file for writing.")
            opened_handle = handle
            async for chunk in response.aiter_bytes():
                if shutdown_event is not None and shutdown_event.is_set():
                    raise ValidationError("Download cancelled.")
                if not chunk:
                    continue
                next_total = bytes_written + len(chunk)
                if max_bytes is not None and next_total > max_bytes:
                    raise ValidationError(
                        f"Download size ({next_total} bytes) exceeds maximum size ({max_bytes} bytes).",
                    )
                if declared_total_length is not None and next_total > declared_total_length:
                    raise ValidationError(
                        "Download size "
                        f"({next_total} bytes) exceeds declared "
                        f"total length ({declared_total_length} bytes).",
                    )
                buffer.extend(chunk)
                bytes_written = next_total
                if reporter is not None:
                    await reporter.report_async(len(chunk))
                if chunk_observer is not None:
                    observer_result = chunk_observer(len(chunk))
                    if inspect.isawaitable(observer_result):
                        await observer_result
                if len(buffer) >= flush_threshold_bytes:
                    await _flush_download_buffer(
                        buffer,
                        handle=opened_handle,
                        declared_reservation=declared_reservation,
                        reservation_provider=reservation_provider,
                        reservation_path=reservation_path or destination_path,
                        reservation_operation=reservation_operation,
                        reservation_details={
                            "url": url,
                            "destination_path": destination_path,
                            "declared_content_length": declared_content_length,
                            "context": dict(reservation_details or {}),
                        },
                    )
                    await emit_download_progress(
                        on_progress,
                        bytes_written=bytes_written,
                        declared_content_length=declared_total_length,
                        started_at=started_at,
                    )
        if buffer:
            await _flush_download_buffer(
                buffer,
                handle=opened_handle,
                declared_reservation=declared_reservation,
                reservation_provider=reservation_provider,
                reservation_path=reservation_path or destination_path,
                reservation_operation=reservation_operation,
                reservation_details={
                    "url": url,
                    "destination_path": destination_path,
                    "declared_content_length": declared_content_length,
                    "context": dict(reservation_details or {}),
                },
            )
        await emit_final_download_progress(
            on_progress,
            bytes_written=bytes_written,
            declared_content_length=declared_total_length,
            started_at=started_at,
        )
        if handle is None or not temp_path:
            raise ValidationError("Failed to finalize downloaded file.")
        await asyncio.to_thread(handle.close)
        handle = None
        await asyncio.to_thread(os.replace, temp_path, destination_path)
        temp_path = ""
        download_completed = True
    finally:
        if handle is not None:
            try:
                await asyncio.to_thread(handle.close)
            except OSError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to close download file handle (non-critical).",
                    operation=OPERATION_PLUGIN_SDK_DOWNLOADS_CLOSE_HANDLE,
                    details={"destination_path": destination_path},
                    level="debug",
                )
        if not download_completed and temp_path and not resume_partial:
            await remove_partial_download_file(
                temp_path,
                logger=logger,
                operation=OPERATION_PLUGIN_SDK_DOWNLOADS_CLEANUP_PARTIAL,
            )
        if declared_reservation is not None:
            await declared_reservation.release()
        if reporter is not None and download_completed:
            await reporter.finalize_async()


async def _flush_download_buffer(
    buffer: bytearray,
    *,
    handle: io.BufferedWriter,
    declared_reservation: PluginStorageReservationLeaseProtocol | None,
    reservation_provider: PluginStorageRuntimeProtocol,
    reservation_path: str,
    reservation_operation: str,
    reservation_details: Mapping[str, JSONValue] | None,
) -> None:
    if not buffer:
        return
    data = bytes(buffer)
    buffer.clear()
    byte_count = len(data)
    if declared_reservation is not None:
        async with claim_plugin_reserved_write(
            declared_reservation,
            size_bytes=byte_count,
            cleanup_action="Plugin SDK download declared claim commit after write failure",
        ):
            await asyncio.to_thread(handle.write, data)
        return
    reservation = await reservation_provider.reserve_disk_space(
        path=reservation_path,
        required_bytes=byte_count,
        operation=reservation_operation,
        details=reservation_details,
    )
    try:
        async with claim_plugin_reserved_write(
            reservation,
            size_bytes=byte_count,
            cleanup_action="Plugin SDK download chunk claim commit after write failure",
        ):
            await asyncio.to_thread(handle.write, data)
    finally:
        await reservation.release()
