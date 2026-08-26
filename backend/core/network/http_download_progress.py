"""SoAI - HTTP download progress and cancellation helpers [backend/core/network/http_download_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import time
from collections.abc import Awaitable, Callable

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.network.download_reservations import (
    DownloadReservationPlan,
    flush_download_buffer_with_reservation,
)

__all__ = (
    "emit_download_progress",
    "emit_final_download_progress",
    "raise_after_flushing_interrupted_download",
)


async def emit_download_progress(
    on_progress: Callable[[int, int | None, float, float], Awaitable[None] | None] | None,
    *,
    bytes_written: int,
    declared_content_length: int | None,
    started_at: float,
) -> None:
    if on_progress is None:
        return
    elapsed_seconds = max(time.monotonic() - started_at, 0.001)
    bytes_per_second = float(bytes_written) / elapsed_seconds
    eta_seconds = 0.0
    if declared_content_length is not None and bytes_per_second > 0:
        remaining_bytes = max(0, declared_content_length - bytes_written)
        eta_seconds = float(remaining_bytes) / bytes_per_second
    result = on_progress(
        bytes_written,
        declared_content_length,
        bytes_per_second,
        eta_seconds,
    )
    if result is not None:
        await result


async def emit_final_download_progress(
    on_progress: Callable[[int, int | None, float, float], Awaitable[None] | None] | None,
    *,
    bytes_written: int,
    declared_content_length: int | None,
    started_at: float,
) -> None:
    if declared_content_length is not None and bytes_written != declared_content_length:
        raise ValidationError(
            f"Download size ({bytes_written} bytes) does not match declared Content-Length ({declared_content_length} bytes).",
        )
    await emit_download_progress(
        on_progress,
        bytes_written=bytes_written,
        declared_content_length=declared_content_length,
        started_at=started_at,
    )


async def raise_after_flushing_interrupted_download(
    cancellation_token: CancellationTokenProtocol,
    write_buffer: list[bytes],
    *,
    file_handle: io.BufferedWriter,
    reservation_plan: DownloadReservationPlan,
) -> None:
    try:
        cancellation_token.raise_if_cancelled()
    except (asyncio.CancelledError, TaskCancelledError, ValidationError):
        await flush_download_buffer_with_reservation(
            write_buffer,
            file_handle=file_handle,
            reservation_plan=reservation_plan,
        )
        raise
