"""SoAI - Bootstrap HTTP binary download helper [backend/core/bootstrap/download_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import tempfile

import httpx2

from core.archives.reservations import (
    DiskReservationRequest,
    open_disk_reservation,
    open_write_claim,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError
from core.filesystem.open_files import open_binary
from core.hardware.protocols_storage import (
    BinaryWriteHandleProtocol,
    DiskSpaceReservationLeaseProtocol,
    StorageManagerProtocol,
)

__all__ = ("download_http_binary_to_path",)

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
    target_dir = os.path.dirname(target_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    temp_path = ""
    with tempfile.NamedTemporaryFile(
        delete=False,
        prefix=".soai-bootstrap-download-",
        suffix=".tmp",
        dir=target_dir or None,
    ) as temp_handle:
        temp_path = temp_handle.name
    try:
        with httpx2.Client(
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            timeout=timeout_sec,
        ) as client:
            with client.stream("GET", url) as response:
                final_url = str(response.url)
                if require_https_final_url and final_url and not final_url.startswith("https://"):
                    raise StateError("Bootstrap binary download redirected to a non-HTTPS URL.")
                response.raise_for_status()
                content_length = _read_content_length(response)
                if (
                    max_bytes is not None
                    and content_length is not None
                    and content_length > max_bytes
                ):
                    raise StateError(
                        f"Bootstrap binary download exceeds the configured limit for {url}.",
                    )
                reservation_bytes = content_length or 0
                with open_disk_reservation(
                    reservation_provider,
                    requests=(
                        DiskReservationRequest(
                            path=temp_path,
                            required_bytes=reservation_bytes,
                        ),
                    ),
                    operation="core.bootstrap.download_stream.download",
                    details={"url": url, "target_path": target_path},
                ) as reservation:
                    downloaded_bytes = 0
                    write_buffer: list[bytes] = []
                    buffered_bytes = 0
                    with open_binary(temp_path, mode="wb") as target_handle:
                        for chunk in response.iter_bytes():
                            if not chunk:
                                continue
                            next_downloaded_bytes = downloaded_bytes + len(chunk)
                            if max_bytes is not None and next_downloaded_bytes > max_bytes:
                                raise StateError(
                                    f"Bootstrap binary download exceeds the configured limit for {url}.",
                                )
                            if (
                                content_length is not None
                                and next_downloaded_bytes > content_length
                            ):
                                raise StateError(
                                    f"Bootstrap binary download exceeded declared size for {url}.",
                                )
                            write_buffer.append(chunk)
                            buffered_bytes += len(chunk)
                            downloaded_bytes = next_downloaded_bytes
                            if buffered_bytes >= DOWNLOAD_FLUSH_THRESHOLD_BYTES:
                                _flush_download_buffer(
                                    write_buffer,
                                    reservation_provider=reservation_provider,
                                    reservation=reservation,
                                    target_handle=target_handle,
                                    temp_path=temp_path,
                                    url=url,
                                    target_path=target_path,
                                    content_length=content_length,
                                )
                                buffered_bytes = 0
                        _flush_download_buffer(
                            write_buffer,
                            reservation_provider=reservation_provider,
                            reservation=reservation,
                            target_handle=target_handle,
                            temp_path=temp_path,
                            url=url,
                            target_path=target_path,
                            content_length=content_length,
                        )
                    if content_length is not None and downloaded_bytes != content_length:
                        raise StateError(
                            f"Bootstrap binary download size did not match declared size for {url}.",
                        )
        os.replace(temp_path, target_path)
    except (OSError, httpx2.HTTPError, ValueError) as exception:
        raise StateError(f"Failed to download bootstrap binary from {url}.") from exception
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


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
            target_handle.write(payload)
            if claim is not None:
                claim.commit()


def _read_content_length(response: httpx2.Response) -> int | None:
    raw_value = response.headers.get("Content-Length")
    if raw_value is None:
        return None
    parsed: int | None = None
    try:
        parsed = int(raw_value)
    except ValueError:
        parsed = None
    if parsed is None:
        return None
    if parsed <= 0:
        return None
    return parsed
