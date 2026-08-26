"""SoAI - HTTP download disk reservation flushing [backend/core/network/download_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

__all__ = (
    "DownloadReservationPlan",
    "flush_download_buffer_with_reservation",
    "remove_partial_download_file",
)


@dataclass(frozen=True, slots=True)
class DownloadReservationPlan:
    lease: DiskSpaceReservationLeaseProtocol | None
    provider: StorageManagerProtocol
    path: str
    operation: str
    details: Mapping[str, JSONValue] | None = None


async def flush_download_buffer_with_reservation(
    write_buffer: list[bytes],
    *,
    file_handle: io.BufferedWriter,
    reservation_plan: DownloadReservationPlan,
) -> None:
    if not write_buffer:
        return
    combined = b"".join(write_buffer)
    write_buffer.clear()
    byte_count = len(combined)
    if reservation_plan.lease is not None:
        with reservation_plan.lease.claim_write_bytes(byte_count) as claim:
            await asyncio.to_thread(file_handle.write, combined)
            claim.commit()
        return
    with (
        reservation_plan.provider.reserve_disk_space(
            path=reservation_plan.path,
            required_bytes=byte_count,
            operation=reservation_plan.operation,
            details=reservation_plan.details,
        ) as reservation,
        reservation.claim_write_bytes(byte_count) as claim,
    ):
        await asyncio.to_thread(file_handle.write, combined)
        claim.commit()


async def remove_partial_download_file(
    path: str,
    *,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    try:
        if await asyncio.to_thread(os.path.exists, path):
            await asyncio.to_thread(os.remove, path)
    except OSError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to remove partial download file after failure.",
            operation=operation,
            details={"path": path},
            level="debug",
        )
