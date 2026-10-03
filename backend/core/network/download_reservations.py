"""SoAI - HTTP download disk reservation flushing [backend/core/network/download_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.hardware.reserved_writes import write_reserved_bytes

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.types.json import JSONValue

__all__ = (
    "DownloadReservationPlan",
    "flush_download_buffer_with_reservation",
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
        await run_joined_thread_call(
            partial(
                write_reserved_bytes, file_handle, combined, reservation=reservation_plan.lease
            ),
            task_name="download-reserved-write",
            retain_resources_until_complete=True,
        )
        return

    def write_incremental() -> None:
        with reservation_plan.provider.reserve_disk_space(
            path=reservation_plan.path,
            required_bytes=byte_count,
            operation=reservation_plan.operation,
            details=reservation_plan.details,
        ) as reservation:
            write_reserved_bytes(file_handle, combined, reservation=reservation)

    await run_joined_thread_call(
        write_incremental,
        task_name="download-incremental-write",
        retain_resources_until_complete=True,
    )
