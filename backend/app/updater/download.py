"""SoAI - Update archive download with reservation-aware staging [backend/app/updater/download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from urllib import request

import httpx2

from app.updater.networking import open_url, validate_updater_url
from app.updater.progress import report_progress
from core.archives.reservations import (
    DiskReservationRequest,
    open_disk_reservation,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    StateError,
    ValidationError,
)
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.files.staged_transfer import StagedTransferResult, stage_chunks_to_temp_file
from core.hardware.protocols_storage import (
    DiskSpaceWriteClaimProtocol,
    StorageManagerProtocol,
)
from core.logging.protocols import LoggerProtocol
from core.network.outbound_http_profiles import build_outbound_request_headers

__all__ = ("download_zip",)

OPERATION_APPLICATION_UPDATER_DOWNLOAD_RELEASE = "application_updater.download_release"


def _read_content_length(response: httpx2.Response) -> int | None:
    raw_value = response.headers.get("Content-Length")
    if raw_value is None:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def download_zip(
    logger: LoggerProtocol,
    *,
    url: str,
    timeout: float,
    temp_path: str,
    max_archive_bytes: int,
    reservation_provider: StorageManagerProtocol,
) -> StagedTransferResult | None:
    validated_url = validate_updater_url(url)
    download_request = request.Request(
        validated_url,
        headers=build_outbound_request_headers(profile_type="service_api"),
    )
    recoverable_exceptions = HTTP_RECOVERABLE_EXCEPTIONS + (
        httpx2.HTTPError,
        InsufficientDiskSpaceError,
        PayloadTooLargeError,
        StateError,
        ValidationError,
    )
    try:
        with open_url(
            download_request,
            timeout=timeout,
            offline_mode=False,
            artifact_download=True,
        ) as response:
            if response.status_code != 200:
                logger.warning(
                    "Failed to download update, server returned %s",
                    response.status_code,
                )
                return None
            content_length = _read_content_length(response)
            if content_length is not None and content_length > max_archive_bytes:
                raise PayloadTooLargeError(
                    f"Update archive exceeds the configured limit of {max_archive_bytes} bytes.",
                )
            last_percent = -1

            def report_download_progress(downloaded_size: int) -> None:
                nonlocal last_percent
                last_percent = report_progress(
                    logger,
                    "update.zip",
                    downloaded_size,
                    content_length or 0,
                    last_percent,
                )

            with open_disk_reservation(
                reservation_provider,
                requests=(
                    DiskReservationRequest(path=temp_path, required_bytes=content_length or 0),
                ),
                operation="application_updater.download_release.reserve_archive",
                details={"url": validated_url, "temp_path": temp_path},
            ) as reservation:
                pending_claim: list[DiskSpaceWriteClaimProtocol | None] = [None]

                @contextmanager
                def reserve_chunk_before_write(
                    chunk_size: int,
                ) -> Generator[None]:
                    active_reservation = reservation
                    if content_length is not None:
                        if active_reservation is None:
                            raise StateError("Update download reservation is unavailable.")
                        with active_reservation.claim_write_bytes(chunk_size) as claim:
                            pending_claim[0] = claim
                            try:
                                yield
                            finally:
                                pending_claim[0] = None
                        return
                    with open_disk_reservation(
                        reservation_provider,
                        requests=(
                            DiskReservationRequest(
                                path=temp_path,
                                required_bytes=chunk_size,
                            ),
                        ),
                        operation="application_updater.download_release.reserve_archive_chunk",
                        details={"url": validated_url, "temp_path": temp_path},
                    ) as chunk_reservation:
                        if chunk_reservation is None:
                            raise StateError("Update download chunk reservation is unavailable.")
                        with chunk_reservation.claim_write_bytes(chunk_size) as claim:
                            pending_claim[0] = claim
                            try:
                                yield
                            finally:
                                pending_claim[0] = None

                def consume_written_chunk(chunk_size: int) -> None:
                    _ = chunk_size
                    claim = pending_claim[0]
                    if claim is not None:
                        claim.commit()

                return stage_chunks_to_temp_file(
                    response.iter_bytes(),
                    temp_dir=temp_path,
                    suffix=".zip",
                    max_bytes=max_archive_bytes,
                    expected_size=content_length,
                    on_progress=report_download_progress,
                    on_chunk_write_scope=reserve_chunk_before_write,
                    on_chunk_written=consume_written_chunk,
                )
    except recoverable_exceptions as exception:
        log_exception(
            logger,
            exception,
            message="Download failed",
            operation=OPERATION_APPLICATION_UPDATER_DOWNLOAD_RELEASE,
        )
        return None
