"""SoAI - Update artifact download with reservation-aware staging [backend/app/updater/download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
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
from core.files.staged_transfer import (
    STAGED_TRANSFER_CHUNK_SIZE,
    StagedTransferResult,
    stage_chunks_to_temp_file,
)
from core.files.windows_readonly_deletion import remove_file_with_readonly_support
from core.hardware.protocols_storage import (
    DiskSpaceWriteClaimProtocol,
    StorageManagerProtocol,
)
from core.logging.protocols import LoggerProtocol
from core.network.http_download_metadata import HTTPDownloadResponseMetadata
from core.network.outbound_http_profiles import build_outbound_request_headers
from core.network.resumable_downloads import DownloadStreamState
from core.network.resumable_http_stream_sync import ResumableHTTPStreamSync
from core.network.transfer_retry import build_http_transfer_retry_policy

__all__ = ("download_update_file",)

OPERATION_APPLICATION_UPDATER_DOWNLOAD_RELEASE = "application_updater.download_release"


def _read_content_length(headers: Mapping[str, str]) -> int | None:
    raw_value = headers.get("Content-Length")
    if raw_value is None:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def download_update_file(
    logger: LoggerProtocol,
    *,
    url: str,
    timeout: float,
    temp_path: str,
    max_download_bytes: int,
    reservation_provider: StorageManagerProtocol,
    suffix: str = ".zip",
    on_progress: Callable[[int, int], None] | None = None,
) -> StagedTransferResult | None:
    validated_url = validate_updater_url(url)

    def open_response(
        headers: Mapping[str, str], io_timeout: float
    ) -> AbstractContextManager[httpx2.Response]:
        return open_url(
            request.Request(validated_url, headers=dict(headers)),
            timeout=io_timeout,
            offline_mode=False,
            artifact_download=True,
        )

    def read_metadata(headers: Mapping[str, str]) -> HTTPDownloadResponseMetadata:
        return HTTPDownloadResponseMetadata(
            _read_content_length(headers), headers.get("Content-Type")
        )

    state = DownloadStreamState(
        url=validated_url,
        headers=build_outbound_request_headers(profile_type="service_api"),
        policy=build_http_transfer_retry_policy("artifact"),
        timeout=timeout,
        max_bytes=max_download_bytes,
        metadata_reader=read_metadata,
    )
    recoverable_exceptions = HTTP_RECOVERABLE_EXCEPTIONS + (
        httpx2.HTTPError,
        InsufficientDiskSpaceError,
        PayloadTooLargeError,
        StateError,
        ValidationError,
    )
    try:
        with ExitStack() as staging_cleanup:
            with ResumableHTTPStreamSync(
                open_response,
                state=state,
                chunk_size=STAGED_TRANSFER_CHUNK_SIZE,
            ) as stream:
                content_length = state.total_length
                if content_length is not None and content_length > max_download_bytes:
                    raise PayloadTooLargeError(
                        f"Update download exceeds its limit of {max_download_bytes} bytes.",
                    )
                last_percent = -1
                last_published_percent = -2
                transfer_total = max_download_bytes

                def report_download_progress(downloaded_size: int) -> None:
                    nonlocal last_percent, last_published_percent
                    last_percent = report_progress(
                        logger,
                        "update.download",
                        downloaded_size,
                        state.total_length or 0,
                        last_percent,
                    )
                    if on_progress is not None and transfer_total > 0:
                        percent = min(100, int(downloaded_size * 100 / transfer_total))
                        if percent >= last_published_percent + 2 or percent == 100:
                            on_progress(min(downloaded_size, transfer_total), transfer_total)
                            last_published_percent = percent

                report_download_progress(0)

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
                                raise StateError(
                                    "Update download chunk reservation is unavailable."
                                )
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

                    staged_result = stage_chunks_to_temp_file(
                        stream,
                        temp_dir=temp_path,
                        suffix=suffix,
                        max_bytes=max_download_bytes,
                        expected_size=content_length,
                        on_progress=report_download_progress,
                        on_chunk_write_scope=reserve_chunk_before_write,
                        on_chunk_written=consume_written_chunk,
                    )
                    staging_cleanup.callback(
                        remove_file_with_readonly_support, staged_result.file_path
                    )
            staging_cleanup.pop_all()
            return staged_result
    except recoverable_exceptions as exception:
        log_exception(
            logger,
            exception,
            message="Download failed",
            operation=OPERATION_APPLICATION_UPDATER_DOWNLOAD_RELEASE,
        )
        return None
