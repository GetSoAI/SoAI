"""SoAI - Archive disk reservation contracts [backend/core/archives/reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.hardware.protocols_storage import (
    DiskSpaceReservationLeaseProtocol,
    DiskSpaceReservationProviderProtocol,
    DiskSpaceWriteClaimProtocol,
)
from core.hardware.reservation_exceptions import (
    close_write_claim_context,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "DiskReservationRequest",
    "open_disk_reservation",
    "open_write_claim",
)


@dataclass(frozen=True, slots=True)
class DiskReservationRequest:
    path: str
    required_bytes: int


class _ManagedDiskSpaceWriteClaim:
    def __init__(self, claim: DiskSpaceWriteClaimProtocol) -> None:
        self._claim = claim
        self._closed = False

    def commit(self) -> None:
        self._claim.commit()
        self._closed = True

    def rollback(self) -> None:
        self._claim.rollback()
        self._closed = True

    def __enter__(self) -> _ManagedDiskSpaceWriteClaim:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type, exc, traceback
        close_write_claim_context(
            closed=self._closed,
            primary_exception=exc,
            commit=self.commit,
            rollback=self.rollback,
            commit_cleanup_action="Archive disk reservation claim commit after failure",
            rollback_cleanup_action="Archive disk reservation claim rollback",
        )


def open_disk_reservation(
    reservation_provider: DiskSpaceReservationProviderProtocol,
    *,
    requests: Sequence[DiskReservationRequest],
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
) -> AbstractContextManager[DiskSpaceReservationLeaseProtocol | None]:
    if not requests or all(request.required_bytes <= 0 for request in requests):
        return nullcontext()
    if reservation_provider is None:
        raise StateError("Disk reservation provider is required for positive archive writes.")
    return reservation_provider.reserve_many_disk_spaces(
        requests=tuple(
            DiskSpaceReservationRequest(
                path=request.path,
                required_bytes=request.required_bytes,
                operation=operation,
                details=details,
            )
            for request in requests
        ),
    )


def open_write_claim(
    reservation: DiskSpaceReservationLeaseProtocol | None,
    *,
    size_bytes: int,
) -> AbstractContextManager[_ManagedDiskSpaceWriteClaim | None]:
    if size_bytes <= 0:
        return nullcontext()
    if reservation is None:
        raise StateError("Disk reservation is required for positive archive writes.")
    return _ManagedDiskSpaceWriteClaim(reservation.claim_write_bytes(size_bytes))
