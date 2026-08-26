"""SoAI - Disk reservation lease handles [backend/core/hardware/disk_reservation_leases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from collections.abc import Sequence
from types import TracebackType

from core.errors.exceptions import ValidationError
from core.hardware.protocols_storage import DiskReservationLedgerProtocol
from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    preserve_primary_exception_cleanup_failure,
)
from core.validation.strict_numbers import (
    require_positive_int_strict,
)

__all__ = ("DiskSpaceReservationLease", "DiskSpaceWriteClaim")


class DiskSpaceWriteClaim:
    def __init__(self, ledger: DiskReservationLedgerProtocol, claim_id: str) -> None:
        self._ledger = ledger
        self._claim_id = claim_id
        self._closed = False
        self._lock = threading.Lock()

    def commit(self) -> None:
        with self._lock:
            if self._closed:
                raise ValidationError("Disk write claim is already closed.")
            self._ledger.commit_reservation_claim(self._claim_id)
            self._closed = True

    def rollback(self) -> None:
        with self._lock:
            if self._closed:
                raise ValidationError("Disk write claim is already closed.")
            self._ledger.rollback_reservation_claim(self._claim_id)
            self._closed = True

    def __enter__(self) -> DiskSpaceWriteClaim:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc, traceback
        if not self._closed:
            if exc_type is not None:
                try:
                    self.commit()
                except DISK_RESERVATION_OPERATION_EXCEPTIONS as commit_exception:
                    preserve_primary_exception_cleanup_failure(
                        exc,
                        commit_exception,
                        cleanup_action="Disk reservation claim commit after failure",
                    )
                return
            try:
                self.rollback()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as rollback_exception:
                preserve_primary_exception_cleanup_failure(
                    exc,
                    rollback_exception,
                    cleanup_action="Disk reservation claim rollback",
                )


class DiskSpaceReservationLease:
    def __init__(
        self,
        ledger: DiskReservationLedgerProtocol,
        reservation_ids: Sequence[str],
    ) -> None:
        self._ledger = ledger
        self._reservation_ids = tuple(reservation_ids)
        self._released = False
        self._lock = threading.Lock()

    def claim_write_bytes(self, bytes_to_write: int) -> DiskSpaceWriteClaim:
        amount = require_positive_int_strict(
            bytes_to_write,
            error_message="bytes_to_write must be a positive integer",
        )
        with self._lock:
            if self._released:
                raise ValidationError("Cannot claim bytes from a released disk reservation.")
            claim_id = self._ledger.claim_reservation_bytes(self._reservation_ids, amount)
        return DiskSpaceWriteClaim(self._ledger, claim_id)

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._ledger.release_reservations(self._reservation_ids)
            self._released = True

    def __enter__(self) -> DiskSpaceReservationLease:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type, exc, traceback
        self.release()
