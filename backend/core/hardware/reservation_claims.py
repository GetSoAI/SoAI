"""SoAI - Disk reservation write claim helpers [backend/core/hardware/reservation_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from core.errors.exceptions import StateError
from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    preserve_primary_exception_cleanup_failure,
)

__all__ = ("claim_reserved_write",)


@contextmanager
def claim_reserved_write(
    reservation: DiskSpaceReservationLeaseProtocol | None,
    *,
    size_bytes: int,
) -> Generator[None]:
    if size_bytes <= 0:
        yield
        return
    if reservation is None:
        raise StateError("Disk reservation is required for positive writes.")
    with reservation.claim_write_bytes(size_bytes) as claim:
        try:
            yield
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as write_exception:
            try:
                claim.commit()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as commit_exception:
                preserve_primary_exception_cleanup_failure(
                    write_exception,
                    commit_exception,
                    cleanup_action="Disk reservation claim commit after write failure",
                )
            raise
        claim.commit()
