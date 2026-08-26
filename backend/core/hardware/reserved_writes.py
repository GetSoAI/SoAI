"""SoAI - Disk-reserved write primitives [backend/core/hardware/reserved_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.hardware.protocols_storage import (
    BinaryWriteHandleProtocol,
    DiskSpaceReservationLeaseProtocol,
)
from core.hardware.reservation_claims import claim_reserved_write
from core.validation.integers import is_positive_strict_int

__all__ = ("BinaryWriteHandleProtocol", "write_reserved_bytes")


def write_reserved_bytes(
    handle: BinaryWriteHandleProtocol,
    data: bytes,
    *,
    reservation: DiskSpaceReservationLeaseProtocol | None,
) -> int:
    byte_count = len(data)
    if byte_count <= 0:
        return 0
    if reservation is None:
        return _write_all(handle, data)
    with claim_reserved_write(reservation, size_bytes=byte_count):
        return _write_all(handle, data)


def _write_all(handle: BinaryWriteHandleProtocol, data: bytes) -> int:
    total_written = 0
    while total_written < len(data):
        written = handle.write(data[total_written:])
        if not is_positive_strict_int(written):
            raise StateError("Reserved write did not make progress.")
        total_written += written
    return total_written
