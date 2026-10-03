"""SoAI - Shared HTTP streaming download utility with redirect handling and cancellation [backend/core/network/http_download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx2

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.protocols import CancellationTokenProtocol
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.network.download_reservations import (
    DownloadReservationPlan,
    flush_download_buffer_with_reservation,
)
from core.network.download_temp_files import DownloadFile, create_download_temp_handle
from core.network.errors import (
    HTTPDownloadInsecureSchemeError,
    HTTPDownloadTooManyRedirectsError,
)
from core.network.http_download_progress import (
    emit_download_progress,
    emit_final_download_progress,
)
from core.network.http_transport import build_pinned_host_extensions
from core.network.redirect_headers import headers_for_redirect, resolve_redirect_url
from core.network.resumable_downloads import DownloadStreamState
from core.network.resumable_http_stream import ResumableHTTPStream
from core.network.transfer_retry import HTTPTransferRetryPolicy
from core.types.protocols import HttpClientProtocol
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.types.json import JSONValue

__all__ = ("HTTPDownloadResult", "download_http_stream_to_file")

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
    retry_policy: HTTPTransferRetryPolicy,
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
    require_non_negative_int_strict(
        flush_threshold, error_message="Flush threshold must be nonnegative."
    )
    state = DownloadStreamState(
        url=url,
        headers=request_headers,
        policy=retry_policy,
        timeout=timeout_seconds,
        max_bytes=max_bytes,
    )
    opener = partial(
        _open_download_response,
        http_client,
        url,
        cancellation_token=cancellation_token,
        max_redirects=max_redirects,
        allow_http_scheme=allow_http_scheme,
        url_validator=url_validator,
    )
    async with AsyncExitStack() as reservations, DownloadFile(destination_path) as download_file:
        async with ResumableHTTPStream(
            opener, state=state, interruption=cancellation_token
        ) as stream:
            owned_reservation_lease: DiskSpaceReservationLeaseProtocol | None = None
            details: dict[str, JSONValue] = {
                "url": state.final_url,
                "destination_path": destination_path,
                "max_bytes": max_bytes,
                "declared_content_length": state.total_length,
                "context": dict(reservation_details or {}),
            }
            if state.total_length is not None and state.total_length > 0:
                owned_reservation_lease = reservation_provider.reserve_disk_space(
                    path=reservation_path or destination_path,
                    required_bytes=state.total_length,
                    operation=reservation_operation,
                    details=details,
                )
                reservations.callback(owned_reservation_lease.release)
            plan = DownloadReservationPlan(
                lease=owned_reservation_lease,
                provider=reservation_provider,
                path=reservation_path or destination_path,
                operation=reservation_operation,
                details=details,
            )
            cancellation_token.raise_if_cancelled()
            handle = await download_file.open(
                partial(create_download_temp_handle, destination_path)
            )
            bytes_written = 0
            write_buffer: list[bytes] = []
            buffered_bytes = 0
            started_at = time.monotonic()
            last_progress_at = started_at
            flush = partial(
                flush_download_buffer_with_reservation,
                write_buffer,
                file_handle=handle,
                reservation_plan=plan,
            )
            try:
                async for chunk in stream:
                    cancellation_token.raise_if_cancelled()
                    write_buffer.append(chunk)
                    buffered_bytes += len(chunk)
                    bytes_written += len(chunk)
                    if buffered_bytes >= flush_threshold:
                        await flush()
                        buffered_bytes = 0
                    if not buffered_bytes or time.monotonic() - last_progress_at >= 1.0:
                        cancellation_token.raise_if_cancelled()
                        await emit_download_progress(
                            on_progress,
                            bytes_written=bytes_written,
                            declared_content_length=state.total_length,
                            started_at=started_at,
                        )
                        last_progress_at = time.monotonic()
                    cancellation_token.raise_if_cancelled()
                cancellation_token.raise_if_cancelled()
            except (asyncio.CancelledError, TaskCancelledError, ValidationError):
                await flush()
                raise
            await flush()
        cancellation_token.raise_if_cancelled()
        await download_file.publish(
            cancellation_token, cancellation_id=cancellation_token.cancellation_id
        )
    await emit_final_download_progress(
        on_progress,
        bytes_written=bytes_written,
        declared_content_length=state.total_length,
        started_at=started_at,
    )
    return HTTPDownloadResult(
        bytes_written=bytes_written,
        final_url=state.final_url,
        declared_content_length=state.total_length,
        content_type=state.content_type,
    )


@asynccontextmanager
async def _open_download_response(
    http_client: HttpClientProtocol,
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    *,
    cancellation_token: CancellationTokenProtocol,
    max_redirects: int,
    allow_http_scheme: bool,
    url_validator: Callable[[str], Awaitable[str | None]] | None,
) -> AsyncGenerator[httpx2.Response]:
    current_url = url
    active_headers: dict[str, str] | None = dict(headers)
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
            timeout=timeout,
            extensions=request_extensions,
        ) as response:
            next_url = resolve_redirect_url(response, current_url)
            if next_url is not None:
                active_headers = headers_for_redirect(
                    active_headers,
                    previous_url=current_url,
                    next_url=next_url,
                )
                current_url = next_url
                continue
            yield response
            return
    raise HTTPDownloadTooManyRedirectsError(
        f"Too many redirects (>{max_redirects}) while downloading from URL."
    )
