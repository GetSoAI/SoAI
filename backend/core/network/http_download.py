"""SoAI - Shared HTTP streaming download utility with redirect handling and cancellation [backend/core/network/http_download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from core.concurrency.protocols import CancellationTokenProtocol
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.network.download_reservations import (
    DownloadReservationPlan,
    flush_download_buffer_with_reservation,
    remove_partial_download_file,
)
from core.network.download_temp_files import create_download_temp_handle
from core.network.errors import (
    HTTPDownloadInsecureSchemeError,
    HTTPDownloadRedirectError,
    HTTPDownloadTooManyRedirectsError,
)
from core.network.http_download_metadata import read_http_download_response_metadata
from core.network.http_download_progress import (
    emit_download_progress,
    emit_final_download_progress,
    raise_after_flushing_interrupted_download,
)
from core.network.http_transport import build_pinned_host_extensions
from core.network.redirect_headers import headers_for_redirect
from core.network.urls import normalize_http_url
from core.types.protocols import HttpClientProtocol

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.types.json import JSONValue

__all__ = ("HTTPDownloadResult", "download_http_stream_to_file")

LOGGER_NAME = "SoAI.core.network.http_download"
OPERATION_CLEANUP_PARTIAL_DOWNLOAD = "core.network.http_download.cleanup_partial"
HTTP_DOWNLOAD_FLUSH_THRESHOLD_BYTES = MIB_BYTES


@dataclass(frozen=True, slots=True)
class HTTPDownloadResult:
    bytes_written: int
    final_url: str
    declared_content_length: int | None
    content_type: str | None


async def download_http_stream_to_file(
    http_client: HttpClientProtocol,
    url: str,
    destination_path: str,
    *,
    cancellation_token: CancellationTokenProtocol,
    max_bytes: int | None,
    reservation_provider: StorageManagerProtocol,
    max_redirects: int = 10,
    allow_http_scheme: bool = False,
    timeout_seconds: float = 300.0,
    flush_threshold: int = HTTP_DOWNLOAD_FLUSH_THRESHOLD_BYTES,
    request_headers: dict[str, str] | None = None,
    url_validator: Callable[[str], Awaitable[str | None]] | None = None,
    on_progress: Callable[[int, int | None, float, float], Awaitable[None] | None] | None = None,
    reservation_path: str | None = None,
    reservation_operation: str = "core.network.http_download",
    reservation_details: Mapping[str, JSONValue] | None = None,
) -> HTTPDownloadResult:
    current_url = url
    active_headers = dict(request_headers) if request_headers is not None else None
    for _ in range(max_redirects + 1):
        cancellation_token.raise_if_cancelled()
        parsed_url = urlparse(current_url)
        scheme = parsed_url.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValidationError(
                f"Invalid URL scheme: {scheme}. Only http and https are supported.",
            )
        if scheme == "http" and not allow_http_scheme:
            raise HTTPDownloadInsecureSchemeError(
                f"Insecure http scheme not allowed for URL: {current_url}"
            )
        request_extensions: dict[str, str] | None = None
        if url_validator is not None:
            pinned_host = await url_validator(current_url)
            if pinned_host:
                original_host = parsed_url.hostname
                if not original_host:
                    raise ValidationError("URL must include a hostname.")
                request_extensions = build_pinned_host_extensions(pinned_host, original_host)
        async with http_client.stream(
            "GET",
            current_url,
            headers=active_headers,
            follow_redirects=False,
            timeout=timeout_seconds,
            extensions=request_extensions,
        ) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_location = response.headers.get("Location")
                if not redirect_location:
                    raise HTTPDownloadRedirectError(
                        "Server sent a redirect response without a Location header.",
                    )
                next_url = normalize_http_url(urljoin(current_url, redirect_location))
                active_headers = headers_for_redirect(
                    active_headers,
                    previous_url=current_url,
                    next_url=next_url,
                )
                current_url = next_url
                continue
            response.raise_for_status()
            response_metadata = read_http_download_response_metadata(
                response.headers,
                max_bytes=max_bytes,
            )
            declared_content_length = response_metadata.declared_content_length
            owned_reservation_lease: DiskSpaceReservationLeaseProtocol | None = None
            reservation_plan_provider = reservation_provider
            reservation_plan_details: dict[str, JSONValue] = {
                "url": current_url,
                "destination_path": destination_path,
                "max_bytes": max_bytes,
                "declared_content_length": declared_content_length,
                "context": dict(reservation_details or {}),
            }
            if declared_content_length is not None and declared_content_length > 0:
                owned_reservation_lease = reservation_provider.reserve_disk_space(
                    path=reservation_path or destination_path,
                    required_bytes=declared_content_length,
                    operation=reservation_operation,
                    details=reservation_plan_details,
                )
            reservation_plan = DownloadReservationPlan(
                lease=owned_reservation_lease,
                provider=reservation_plan_provider,
                path=reservation_path or destination_path,
                operation=reservation_operation,
                details=reservation_plan_details,
            )
            bytes_written = 0
            write_buffer: list[bytes] = []
            buffered_bytes = 0
            started_at = time.monotonic()
            last_progress_at = started_at
            file_handle: io.BufferedWriter | None = None
            download_completed = False
            temp_file_path = ""
            try:
                opened_handle, temp_file_path = await asyncio.to_thread(
                    create_download_temp_handle,
                    destination_path,
                )
                file_handle = opened_handle
                opened_file_handle = opened_handle

                async for chunk in response.aiter_bytes():
                    await raise_after_flushing_interrupted_download(
                        cancellation_token,
                        write_buffer,
                        file_handle=opened_file_handle,
                        reservation_plan=reservation_plan,
                    )
                    if not chunk:
                        continue
                    next_total = bytes_written + len(chunk)
                    if max_bytes is not None and next_total > max_bytes:
                        await flush_download_buffer_with_reservation(
                            write_buffer,
                            file_handle=opened_file_handle,
                            reservation_plan=reservation_plan,
                        )
                        raise ValidationError(
                            f"Download size ({next_total} bytes) exceeds maximum size ({max_bytes} bytes).",
                        )
                    if declared_content_length is not None and next_total > declared_content_length:
                        await flush_download_buffer_with_reservation(
                            write_buffer,
                            file_handle=opened_file_handle,
                            reservation_plan=reservation_plan,
                        )
                        raise ValidationError(
                            f"Download size ({next_total} bytes) exceeds declared Content-Length ({declared_content_length} bytes).",
                        )
                    write_buffer.append(chunk)
                    buffered_bytes += len(chunk)
                    bytes_written = next_total
                    if buffered_bytes >= flush_threshold:
                        await flush_download_buffer_with_reservation(
                            write_buffer,
                            file_handle=opened_file_handle,
                            reservation_plan=reservation_plan,
                        )
                        buffered_bytes = 0
                        await emit_download_progress(
                            on_progress,
                            bytes_written=bytes_written,
                            declared_content_length=declared_content_length,
                            started_at=started_at,
                        )
                        last_progress_at = time.monotonic()
                    elif time.monotonic() - last_progress_at >= 1.0:
                        await emit_download_progress(
                            on_progress,
                            bytes_written=bytes_written,
                            declared_content_length=declared_content_length,
                            started_at=started_at,
                        )
                        last_progress_at = time.monotonic()
                    await raise_after_flushing_interrupted_download(
                        cancellation_token,
                        write_buffer,
                        file_handle=opened_file_handle,
                        reservation_plan=reservation_plan,
                    )
                await flush_download_buffer_with_reservation(
                    write_buffer,
                    file_handle=opened_file_handle,
                    reservation_plan=reservation_plan,
                )
                await emit_final_download_progress(
                    on_progress,
                    bytes_written=bytes_written,
                    declared_content_length=declared_content_length,
                    started_at=started_at,
                )
                await asyncio.to_thread(opened_file_handle.close)
                file_handle = None
                await asyncio.to_thread(os.replace, temp_file_path, destination_path)
                temp_file_path = ""
                download_completed = True
            finally:
                if file_handle is not None:
                    await asyncio.to_thread(file_handle.close)
                if not download_completed:
                    if temp_file_path:
                        await remove_partial_download_file(
                            temp_file_path,
                            logger=get_logger(LOGGER_NAME),
                            operation=OPERATION_CLEANUP_PARTIAL_DOWNLOAD,
                        )
                if owned_reservation_lease is not None:
                    owned_reservation_lease.release()
            return HTTPDownloadResult(
                bytes_written=bytes_written,
                final_url=current_url,
                declared_content_length=declared_content_length,
                content_type=response_metadata.content_type,
            )
    raise HTTPDownloadTooManyRedirectsError(
        f"Too many redirects (>{max_redirects}) while downloading from URL."
    )
