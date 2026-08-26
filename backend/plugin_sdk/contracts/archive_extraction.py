"""SoAI - Plugin SDK archive extraction helpers [backend/plugin_sdk/contracts/archive_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import TYPE_CHECKING

from core.archives.tar_extraction import safe_tar_extractall
from core.archives.zip_extraction import safe_zip_extractall
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    close_write_claim_context,
    preserve_primary_exception_cleanup_failure,
)
from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.plugins.protocols_runtime import (
        PluginStorageReservationLeaseProtocol,
        PluginStorageRuntimeProtocol,
        PluginStorageWriteClaimProtocol,
    )

__all__ = ("async_safe_tar_extractall", "async_safe_zip_extractall")


async def async_safe_tar_extractall(
    archive_path: str,
    destination: str,
    *,
    reservation_provider: PluginStorageRuntimeProtocol,
) -> None:
    sync_provider = _SyncPluginReservationProvider(reservation_provider, asyncio.get_running_loop())
    await asyncio.to_thread(
        safe_tar_extractall,
        archive_path,
        destination,
        reservation_provider=sync_provider,
    )


async def async_safe_zip_extractall(
    archive_path: str,
    destination: str,
    *,
    reservation_provider: PluginStorageRuntimeProtocol,
) -> list[str]:
    sync_provider = _SyncPluginReservationProvider(reservation_provider, asyncio.get_running_loop())
    return await asyncio.to_thread(
        safe_zip_extractall,
        archive_path,
        destination,
        reservation_provider=sync_provider,
    )


class _SyncPluginReservationLease:
    def __init__(
        self,
        leases: tuple[tuple[PluginStorageReservationLeaseProtocol, int], ...],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._leases = leases
        self._remaining_bytes = [max(0, remaining_bytes) for _, remaining_bytes in leases]
        self._loop = loop

    def claim_write_bytes(self, bytes_to_write: int) -> _SyncPluginWriteClaim:
        if bytes_to_write <= 0 or not self._leases:
            raise ValueError("bytes_to_write must be greater than zero.")
        remaining_to_claim = bytes_to_write
        claims: list[tuple[PluginStorageWriteClaimProtocol, int, int]] = []
        try:
            for index, (lease, _remaining_bytes) in enumerate(self._leases):
                if remaining_to_claim <= 0:
                    break
                claimed = min(self._remaining_bytes[index], remaining_to_claim)
                if claimed <= 0:
                    continue
                claim = asyncio.run_coroutine_threadsafe(
                    lease.claim_write_bytes(claimed),
                    self._loop,
                ).result()
                claims.append((claim, index, claimed))
                self._remaining_bytes[index] -= claimed
                remaining_to_claim -= claimed
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as claim_exception:
            try:
                _SyncPluginWriteClaim(tuple(claims), self._remaining_bytes, self._loop).rollback()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as rollback_exception:
                preserve_primary_exception_cleanup_failure(
                    claim_exception,
                    rollback_exception,
                    cleanup_action="Plugin archive claim rollback",
                )
            raise
        if remaining_to_claim > 0:
            claim_error = ValueError("Disk write claim exceeds remaining reservation bytes.")
            try:
                _SyncPluginWriteClaim(tuple(claims), self._remaining_bytes, self._loop).rollback()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as rollback_exception:
                preserve_primary_exception_cleanup_failure(
                    claim_error,
                    rollback_exception,
                    cleanup_action="Plugin archive claim rollback",
                )
            raise claim_error
        return _SyncPluginWriteClaim(tuple(claims), self._remaining_bytes, self._loop)

    def release(self) -> None:
        first_exception: Exception | None = None
        for lease, _remaining_bytes in reversed(self._leases):
            try:
                asyncio.run_coroutine_threadsafe(lease.release(), self._loop).result()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as exception:
                if first_exception is None:
                    first_exception = exception
                else:
                    first_exception.add_note(
                        f"Plugin archive reservation release failed: {exception}",
                    )
        if first_exception is not None:
            raise first_exception

    def __enter__(self) -> _SyncPluginReservationLease:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type, exc, traceback
        self.release()


class _SyncPluginWriteClaim:
    def __init__(
        self,
        claims: tuple[tuple[PluginStorageWriteClaimProtocol, int, int], ...],
        remaining_bytes: list[int],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._claims = claims
        self._remaining_bytes = remaining_bytes
        self._loop = loop
        self._closed = False

    def commit(self) -> None:
        if self._closed:
            raise ValueError("Disk write claim is already closed.")
        first_exception: Exception | None = None
        for claim, _index, _claimed in self._claims:
            try:
                asyncio.run_coroutine_threadsafe(claim.commit(), self._loop).result()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as exception:
                if first_exception is None:
                    first_exception = exception
                else:
                    first_exception.add_note(f"Plugin archive claim commit failed: {exception}")
        self._closed = True
        if first_exception is not None:
            raise first_exception

    def rollback(self) -> None:
        if self._closed:
            raise ValueError("Disk write claim is already closed.")
        first_exception: Exception | None = None
        for claim, index, claimed in reversed(self._claims):
            try:
                asyncio.run_coroutine_threadsafe(claim.rollback(), self._loop).result()
                self._remaining_bytes[index] += claimed
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as exception:
                if first_exception is None:
                    first_exception = exception
                else:
                    first_exception.add_note(f"Plugin archive claim rollback failed: {exception}")
        self._closed = True
        if first_exception is not None:
            raise first_exception

    def __enter__(self) -> _SyncPluginWriteClaim:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        primary_exception: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> None:
        _ = exception_type, exception_traceback
        close_write_claim_context(
            closed=self._closed,
            primary_exception=primary_exception,
            commit=self.commit,
            rollback=self.rollback,
            commit_cleanup_action="Plugin archive claim commit after failure",
            rollback_cleanup_action="Plugin archive claim rollback",
        )


class _SyncPluginReservationProvider:
    def __init__(
        self,
        reservation_provider: PluginStorageRuntimeProtocol,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._reservation_provider = reservation_provider
        self._loop = loop

    def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceReservationLeaseProtocol:
        lease = asyncio.run_coroutine_threadsafe(
            self._reservation_provider.reserve_disk_space(
                path=path,
                required_bytes=required_bytes,
                operation=operation,
                details=details,
            ),
            self._loop,
        ).result()
        return _SyncPluginReservationLease(((lease, required_bytes),), self._loop)

    def reserve_many_disk_spaces(
        self,
        *,
        requests: Sequence[DiskSpaceReservationRequest],
    ) -> DiskSpaceReservationLeaseProtocol:
        leases: list[tuple[PluginStorageReservationLeaseProtocol, int]] = []
        try:
            for request in requests:
                lease = asyncio.run_coroutine_threadsafe(
                    self._reservation_provider.reserve_disk_space(
                        path=request.path,
                        required_bytes=request.required_bytes,
                        operation=request.operation,
                        details=request.details,
                    ),
                    self._loop,
                ).result()
                leases.append((lease, request.required_bytes))
        except DISK_RESERVATION_OPERATION_EXCEPTIONS as reservation_exception:
            try:
                _SyncPluginReservationLease(tuple(leases), self._loop).release()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as release_exception:
                preserve_primary_exception_cleanup_failure(
                    reservation_exception,
                    release_exception,
                    cleanup_action="Plugin archive reservation release",
                )
            raise
        return _SyncPluginReservationLease(tuple(leases), self._loop)
