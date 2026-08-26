"""SoAI - Thread-safe streaming upload reservation ownership [backend/features/api/routes/upload_streaming_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.reservation_claims import claim_reserved_write
from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )

__all__ = (
    "StreamingUploadReservationPurpose",
    "StreamingUploadReservationTracker",
)


@dataclass(frozen=True, slots=True)
class StreamingUploadReservationPurpose:
    declared_operation: str
    chunk_operation: str
    declared_details: Mapping[str, JSONValue]
    chunk_details: Mapping[str, JSONValue]


class StreamingUploadReservationTracker:
    def __init__(
        self,
        *,
        storage_manager: StorageManagerProtocol,
        temp_dir: str,
        initial_purpose: StreamingUploadReservationPurpose,
        initial_filename: str = "",
        purpose_for_filename: Callable[[str], StreamingUploadReservationPurpose] | None = None,
    ) -> None:
        self._storage_manager = storage_manager
        self._temp_dir = temp_dir
        self._purpose_for_filename = purpose_for_filename
        self._lock = threading.Lock()
        self._purpose = initial_purpose
        self._current_filename = initial_filename
        self._declared_size: int | None = None
        self._active_reservation: DiskSpaceReservationLeaseProtocol | None = None
        self._written_bytes = 0
        self._parser_active = False
        self._parser_completed = False
        self._release_requested = False

    @property
    def current_filename(self) -> str:
        with self._lock:
            return self._current_filename

    @property
    def declared_size(self) -> int | None:
        with self._lock:
            return self._declared_size

    @property
    def written_bytes(self) -> int:
        with self._lock:
            return self._written_bytes

    def parser_started(self) -> None:
        with self._lock:
            if self._parser_active or self._parser_completed:
                raise StateError("Streaming upload reservation parser lifecycle already started.")
            if self._release_requested:
                raise StateError("Streaming upload reservation is already releasing.")
            self._parser_active = True

    def parser_finished(self) -> None:
        reservation: DiskSpaceReservationLeaseProtocol | None = None
        with self._lock:
            if not self._parser_active or self._parser_completed:
                raise StateError("Streaming upload reservation parser lifecycle is not active.")
            self._parser_active = False
            self._parser_completed = True
            if self._release_requested:
                reservation = self._active_reservation
                self._active_reservation = None
        if reservation is not None:
            reservation.release()

    def file_started(self, filename: str) -> None:
        purpose_for_filename = self._purpose_for_filename
        purpose = purpose_for_filename(filename) if purpose_for_filename is not None else None
        with self._lock:
            self._require_active_parser()
            self._current_filename = filename
            if purpose is not None:
                self._purpose = purpose

    def open_write_scope(self, bytes_to_write: int) -> AbstractContextManager[None]:
        return self._open_write_scope(bytes_to_write=bytes_to_write)

    @contextmanager
    def _open_write_scope(self, *, bytes_to_write: int) -> Generator[None]:
        with self._lock:
            self._require_active_parser()
            reservation = self._active_reservation
            declared_size = self._declared_size
            written_bytes = self._written_bytes
            purpose = self._purpose
        within_declared_reservation = (
            declared_size is not None and written_bytes + bytes_to_write <= declared_size
        )
        if reservation is not None and within_declared_reservation:
            with claim_reserved_write(reservation, size_bytes=bytes_to_write):
                yield
            return
        details = dict(purpose.chunk_details)
        details["chunk_size"] = bytes_to_write
        with (
            self._storage_manager.reserve_disk_space(
                path=self._temp_dir,
                required_bytes=bytes_to_write,
                operation=purpose.chunk_operation,
                details=details,
            ) as chunk_reservation,
            claim_reserved_write(chunk_reservation, size_bytes=bytes_to_write),
        ):
            yield

    def record_written_bytes(self, bytes_written: int) -> None:
        with self._lock:
            self._require_active_parser()
            self._written_bytes += bytes_written

    def reserve_declared_remainder(
        self,
        *,
        declared_size: int,
        purpose: StreamingUploadReservationPurpose | None = None,
    ) -> None:
        with self._lock:
            written_bytes, resolved_purpose = self._begin_declared_reservation(
                declared_size=declared_size,
                purpose=purpose,
            )
        remaining_bytes = max(0, declared_size - written_bytes)
        if remaining_bytes <= 0:
            return
        details = dict(resolved_purpose.declared_details)
        details["declared_size_bytes"] = declared_size
        details["already_written_bytes"] = written_bytes
        details["required_bytes"] = remaining_bytes
        reservation = self._storage_manager.reserve_disk_space(
            path=self._temp_dir,
            required_bytes=remaining_bytes,
            operation=resolved_purpose.declared_operation,
            details=details,
        )
        self._publish_reservation(reservation)

    def release_active_reservation(self) -> None:
        reservation: DiskSpaceReservationLeaseProtocol | None = None
        with self._lock:
            if self._release_requested:
                return
            self._release_requested = True
            if not self._parser_active:
                reservation = self._active_reservation
                self._active_reservation = None
        if reservation is not None:
            reservation.release()

    def _begin_declared_reservation(
        self,
        *,
        declared_size: int,
        purpose: StreamingUploadReservationPurpose | None,
    ) -> tuple[int, StreamingUploadReservationPurpose]:
        if self._declared_size is not None:
            raise StateError("Streaming upload declared size was already reserved.")
        if self._release_requested:
            raise StateError("Streaming upload reservation is no longer active.")
        self._declared_size = declared_size
        if purpose is not None:
            self._purpose = purpose
        return self._written_bytes, self._purpose

    def _publish_reservation(self, reservation: DiskSpaceReservationLeaseProtocol) -> None:
        release_reservation = False
        with self._lock:
            if self._active_reservation is not None:
                release_reservation = True
            elif self._release_requested:
                release_reservation = True
            else:
                self._active_reservation = reservation
        if release_reservation:
            reservation.release()
            raise StateError("Streaming upload reservation could not be published.")

    def _require_active_parser(self) -> None:
        if not self._parser_active or self._parser_completed:
            raise StateError("Streaming upload reservation parser lifecycle is not active.")
