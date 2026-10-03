"""SoAI - Plugin SDK streaming download helpers [backend/plugin_sdk/contracts/downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
import io
import os
import time
import unicodedata
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from functools import partial
from typing import TYPE_CHECKING

import httpx2

from core.bootstrap.runtime_directories import LOCKS_PATH_ENV
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.config.byte_sizes import MIB_BYTES
from core.config.locks import get_lock_path, resolve_lock_directory
from core.errors.exceptions import ValidationError
from core.files.locking import async_guarded_file_lock
from core.network.download_temp_files import DownloadFile, create_download_temp_handle
from core.network.http_download_progress import emit_download_progress, emit_final_download_progress
from core.network.outbound_http_profiles import build_outbound_request_headers
from core.network.resumable_downloads import DownloadStreamState
from core.network.resumable_http_stream import ResumableHTTPStream
from core.network.transfer_retry import build_http_transfer_retry_policy
from core.types.protocols import HttpClientProtocol
from core.validation.strict_numbers import require_non_negative_int_strict
from plugin_sdk.contracts.progress import DownloadProgressReporter
from plugin_sdk.contracts.resumable_downloads import (
    RetainedDownloadPrefix,
    flush_plugin_download_buffer,
    inspect_resumable_download,
    open_resumable_download,
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


class _DownloadInterruption:
    def __init__(self, shutdown_event: asyncio.Event | None) -> None:
        self.event = shutdown_event if shutdown_event is not None else asyncio.Event()

    async def wait(self) -> None:
        await self.event.wait()

    def raise_if_cancelled(self) -> None:
        if self.event.is_set():
            raise ValidationError("Download cancelled.")


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
    if not url.strip():
        raise ValidationError("url must be provided.")
    if not destination_path.strip():
        raise ValidationError("destination_path must be provided.")
    if shutdown_event is not None and shutdown_event.is_set():
        raise ValidationError("Shutdown requested before download start.")
    require_non_negative_int_strict(
        flush_threshold_bytes, error_message="Flush threshold must be nonnegative."
    )
    request_headers = build_outbound_request_headers(
        profile_type="artifact_download", extra_headers=headers
    )
    state = DownloadStreamState(
        url=url,
        headers=request_headers,
        policy=build_http_transfer_retry_policy("artifact"),
        timeout=timeout,
        max_bytes=max_bytes,
    )
    destination_path = os.path.abspath(destination_path)
    await ensure_parent_dirs_exist([destination_path])
    lock_directory = await run_joined_thread_call(
        resolve_lock_directory,
        os.environ.get(LOCKS_PATH_ENV, "") or os.path.dirname(destination_path),
        task_name="download-lock-directory",
        retain_resources_until_complete=True,
    )
    lock_path = get_lock_path(
        unicodedata.normalize("NFD", os.path.realpath(destination_path)).casefold(),
        lock_directory=lock_directory,
    )
    interruption = _DownloadInterruption(shutdown_event)
    resume_path = f"{destination_path}.partial"
    async with (
        async_guarded_file_lock(
            lock_path,
            timeout=0.0,
            on_timeout=ValidationError("A download already owns this destination."),
        ),
        AsyncExitStack() as reservations,
        DownloadFile(destination_path, retain_partial=resume_partial) as download_file,
    ):
        interruption.raise_if_cancelled()
        prefix = RetainedDownloadPrefix()
        if resume_partial:
            prefix = await run_joined_thread_call(
                inspect_resumable_download,
                resume_path,
                max_bytes,
                task_name="download-prefix-verification",
                retain_resources_until_complete=True,
            )
            state.retain_prefix(prefix.length, prefix.sha256)

        def open_response(
            effective_headers: Mapping[str, str], io_timeout: float
        ) -> AbstractAsyncContextManager[httpx2.Response]:
            return http_client.stream(
                "GET",
                url,
                headers=effective_headers,
                follow_redirects=follow_redirects,
                timeout=io_timeout,
            )

        started_at = time.monotonic()
        async with ResumableHTTPStream(
            open_response, state=state, interruption=interruption
        ) as stream:
            declared_reservation: PluginStorageReservationLeaseProtocol | None = None
            details: dict[str, JSONValue] = {
                "url": url,
                "destination_path": destination_path,
                "declared_content_length": state.total_length,
                "context": dict(reservation_details or {}),
            }
            if state.total_length is not None and state.total_length > state.resumed_bytes:
                declared_reservation = await reservation_provider.reserve_disk_space(
                    path=reservation_path or destination_path,
                    required_bytes=state.total_length - state.resumed_bytes,
                    operation=reservation_operation,
                    details=details,
                )
                reservations.push_async_callback(declared_reservation.release)
            interruption.raise_if_cancelled()
            if resume_partial:

                def open_partial() -> tuple[io.BufferedWriter, str]:
                    return (
                        open_resumable_download(
                            resume_path,
                            append=state.resumed_bytes > 0,
                            expected_status=prefix.status,
                        ),
                        resume_path,
                    )

                handle = await download_file.open(open_partial)
            else:
                handle = await download_file.open(
                    partial(create_download_temp_handle, destination_path)
                )
            if reporter is not None:
                if reporter.total_size <= 0 and state.total_length is not None:
                    reporter.total_size = state.total_length
                if state.resumed_bytes:
                    await reporter.report_async(
                        state.resumed_bytes, maximum_percent=max(0, reporter.progress_end - 1)
                    )
            bytes_written = state.resumed_bytes
            if bytes_written:
                await emit_download_progress(
                    on_progress,
                    bytes_written=bytes_written,
                    declared_content_length=state.total_length,
                    started_at=started_at,
                )
            buffer = bytearray()
            flush = partial(
                flush_plugin_download_buffer,
                buffer,
                handle=handle,
                declared_reservation=declared_reservation,
                reservation_provider=reservation_provider,
                reservation_path=reservation_path or destination_path,
                reservation_operation=reservation_operation,
                reservation_details=details,
            )
            async for chunk in stream:
                interruption.raise_if_cancelled()
                buffer.extend(chunk)
                bytes_written += len(chunk)
                if reporter is not None:
                    await reporter.report_async(
                        len(chunk), maximum_percent=max(0, reporter.progress_end - 1)
                    )
                if chunk_observer is not None:
                    observed = chunk_observer(len(chunk))
                    if inspect.isawaitable(observed):
                        await observed
                if len(buffer) >= flush_threshold_bytes:
                    await flush()
                    interruption.raise_if_cancelled()
                    await emit_download_progress(
                        on_progress,
                        bytes_written=bytes_written,
                        declared_content_length=state.total_length,
                        started_at=started_at,
                    )
            interruption.raise_if_cancelled()
            await flush()
        interruption.raise_if_cancelled()
        await download_file.publish(interruption)
    await emit_final_download_progress(
        on_progress,
        bytes_written=bytes_written,
        declared_content_length=state.total_length,
        started_at=started_at,
    )
    if reporter is not None:
        await reporter.finalize_async()
