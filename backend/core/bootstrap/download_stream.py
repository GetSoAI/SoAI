"""SoAI - Bootstrap HTTP binary download helper [backend/core/bootstrap/download_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from functools import partial
from urllib.parse import urljoin, urlsplit

import httpx2

from core.archives.reservations import (
    DiskReservationRequest,
    open_disk_reservation,
    open_write_claim,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_binary
from core.hardware.protocols_storage import (
    BinaryWriteHandleProtocol,
    DiskSpaceReservationLeaseProtocol,
    StorageManagerProtocol,
)
from core.hardware.reserved_writes import write_reserved_bytes
from core.network.errors import HTTPDownloadInsecureSchemeError, HTTPDownloadSizeLimitError
from core.network.resumable_downloads import DownloadStreamState
from core.network.resumable_http_stream_sync import ResumableHTTPStreamSync
from core.network.transfer_retry import build_http_transfer_retry_policy

__all__ = ("download_http_binary_to_path", "download_http_text")

DOWNLOAD_FLUSH_THRESHOLD_BYTES = MIB_BYTES


def download_http_binary_to_path(
    url: str,
    *,
    target_path: str,
    user_agent: str,
    timeout_sec: float,
    reservation_provider: StorageManagerProtocol,
    max_bytes: int | None = None,
    require_https_final_url: bool = False,
) -> None:
    state = DownloadStreamState(
        url=url,
        headers={"User-Agent": user_agent},
        policy=build_http_transfer_retry_policy("artifact"),
        timeout=timeout_sec,
        max_bytes=max_bytes,
    )
    target_dir = os.path.dirname(os.path.abspath(target_path))
    os.makedirs(target_dir, exist_ok=True)
    temp_path = ""
    opener = partial(_open_bootstrap_response, url, require_https=require_https_final_url)
    try:
        with ResumableHTTPStreamSync(opener, state=state) as stream:
            content_length = state.total_length
            with tempfile.NamedTemporaryFile(
                delete=False,
                prefix=".soai-bootstrap-download-",
                suffix=".tmp",
                dir=target_dir,
            ) as temp_handle:
                temp_path = temp_handle.name
            with open_disk_reservation(
                reservation_provider,
                requests=(
                    DiskReservationRequest(path=temp_path, required_bytes=content_length or 0),
                ),
                operation="core.bootstrap.download_stream.download",
                details={"url": url, "target_path": target_path},
            ) as reservation:
                write_buffer: list[bytes] = []
                buffered_bytes = 0
                with open_binary(temp_path, mode="wb") as target_handle:
                    flush = partial(
                        _flush_download_buffer,
                        write_buffer,
                        reservation_provider=reservation_provider,
                        reservation=reservation,
                        target_handle=target_handle,
                        temp_path=temp_path,
                        url=url,
                        target_path=target_path,
                        content_length=content_length,
                    )
                    for chunk in stream:
                        write_buffer.append(chunk)
                        buffered_bytes += len(chunk)
                        if buffered_bytes >= DOWNLOAD_FLUSH_THRESHOLD_BYTES:
                            flush()
                            buffered_bytes = 0
                    flush()
        os.replace(temp_path, target_path)
    except HTTPDownloadInsecureSchemeError as exception:
        raise StateError("Bootstrap binary download redirected to a non-HTTPS URL.") from exception
    except HTTPDownloadSizeLimitError as exception:
        raise StateError(
            f"Bootstrap binary download exceeds the configured limit for {url}."
        ) from exception
    except ValidationError as exception:
        raise StateError(
            f"Bootstrap binary download validation failed: {exception.message}"
        ) from exception
    except (OSError, httpx2.HTTPError, ValueError) as exception:
        raise StateError(f"Failed to download bootstrap binary from {url}.") from exception
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def download_http_text(
    url: str,
    *,
    user_agent: str,
    timeout_sec: float,
    max_bytes: int,
) -> str:
    state = DownloadStreamState(
        url=url,
        headers={"User-Agent": user_agent},
        policy=build_http_transfer_retry_policy("artifact"),
        timeout=timeout_sec,
        max_bytes=max_bytes,
    )
    opener = partial(_open_bootstrap_response, url, require_https=True)
    with ResumableHTTPStreamSync(opener, state=state) as stream:
        payload = b"".join(stream)
    return payload.decode("utf-8", errors="strict")


@contextmanager
def _open_bootstrap_response(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    *,
    require_https: bool,
) -> Generator[httpx2.Response]:
    if require_https and urlsplit(url).scheme.lower() != "https":
        raise HTTPDownloadInsecureSchemeError("Bootstrap downloads require an HTTPS URL.")
    event_hooks = {"response": [_reject_https_redirect_downgrade]} if require_https else None
    with httpx2.Client(
        follow_redirects=True,
        timeout=timeout,
        event_hooks=event_hooks,
    ) as client:
        with client.stream("GET", url, headers=headers, timeout=timeout) as response:
            if require_https and urlsplit(str(response.url)).scheme.lower() != "https":
                raise HTTPDownloadInsecureSchemeError(
                    "Bootstrap download redirected to a non-HTTPS URL."
                )
            yield response


def _flush_download_buffer(
    write_buffer: list[bytes],
    *,
    reservation_provider: StorageManagerProtocol,
    reservation: DiskSpaceReservationLeaseProtocol | None,
    target_handle: BinaryWriteHandleProtocol,
    temp_path: str,
    url: str,
    target_path: str,
    content_length: int | None,
) -> None:
    if not write_buffer:
        return
    payload = b"".join(write_buffer)
    write_buffer.clear()
    with open_disk_reservation(
        reservation_provider,
        requests=(
            DiskReservationRequest(
                path=temp_path,
                required_bytes=len(payload) if content_length is None else 0,
            ),
        ),
        operation="core.bootstrap.download_stream.download_chunk",
        details={"url": url, "target_path": target_path},
    ) as chunk_reservation:
        active_reservation = reservation if reservation is not None else chunk_reservation
        with open_write_claim(
            active_reservation,
            size_bytes=len(payload),
        ) as claim:
            write_reserved_bytes(target_handle, payload, reservation=None)
            if claim is not None:
                claim.commit()


def _reject_https_redirect_downgrade(response: httpx2.Response) -> None:
    if not response.is_redirect:
        return
    current_url = str(response.url)
    redirect_location = response.headers.get("Location")
    if not redirect_location:
        return
    redirect_url = urljoin(current_url, redirect_location)
    if (
        urlsplit(current_url).scheme.lower() == "https"
        and urlsplit(redirect_url).scheme.lower() != "https"
    ):
        raise HTTPDownloadInsecureSchemeError(
            "Bootstrap binary download redirected to a non-HTTPS URL."
        )
