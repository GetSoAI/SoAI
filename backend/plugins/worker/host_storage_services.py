"""SoAI - Plugin worker storage host service adapters [backend/plugins/worker/host_storage_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType

from core.errors.exceptions import ValidationError
from core.hardware.reservation_exceptions import (
    DISK_RESERVATION_OPERATION_EXCEPTIONS,
    preserve_primary_exception_cleanup_failure,
)
from core.types.json import JSONDict, JSONValue
from core.validation.strings import require_trimmed_json_text
from plugins.worker.storage_scope import WorkerStorageScopeState

__all__ = (
    "WorkerStorageAdapter",
    "WorkerStorageReservationLease",
    "WorkerStorageWriteClaim",
)


class WorkerStorageReservationLease:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        reservation_id: str,
        release_enabled: bool = True,
    ) -> None:
        self._request = request
        self._reservation_id = reservation_id
        self._release_enabled = release_enabled
        self._released = False
        self._lock = asyncio.Lock()

    async def claim_write_bytes(self, bytes_to_write: int) -> WorkerStorageWriteClaim:
        async with self._lock:
            if self._released:
                raise ValidationError("Cannot claim bytes from a released storage reservation.")
            result = await self._request(
                "storage.claim_reservation",
                {"reservation_id": self._reservation_id, "bytes_to_write": bytes_to_write},
            )
            claim_id = _require_storage_string_value(result.get("value"), "storage write claim id")
            return WorkerStorageWriteClaim(self._request, claim_id=claim_id)

    async def release(self) -> None:
        async with self._lock:
            if self._released:
                return
            if self._release_enabled:
                await self._request(
                    "storage.release_reservation",
                    {"reservation_id": self._reservation_id},
                )
            self._released = True

    async def __aenter__(self) -> WorkerStorageReservationLease:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type, exc, traceback
        await self.release()


class WorkerStorageWriteClaim:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        claim_id: str,
    ) -> None:
        self._request = request
        self._claim_id = claim_id
        self._closed = False
        self._lock = asyncio.Lock()

    async def commit(self) -> None:
        async with self._lock:
            if self._closed:
                raise ValidationError("Storage write claim is already closed.")
            await self._request("storage.commit_claim", {"claim_id": self._claim_id})
            self._closed = True

    async def rollback(self) -> None:
        async with self._lock:
            if self._closed:
                raise ValidationError("Storage write claim is already closed.")
            await self._request("storage.rollback_claim", {"claim_id": self._claim_id})
            self._closed = True

    async def __aenter__(self) -> WorkerStorageWriteClaim:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type, exc, traceback
        if not self._closed:
            if exc is not None:
                try:
                    await self.commit()
                except DISK_RESERVATION_OPERATION_EXCEPTIONS as commit_exception:
                    preserve_primary_exception_cleanup_failure(
                        exc,
                        commit_exception,
                        cleanup_action="Worker storage claim commit after failure",
                    )
                return
            try:
                await self.rollback()
            except DISK_RESERVATION_OPERATION_EXCEPTIONS as rollback_exception:
                preserve_primary_exception_cleanup_failure(
                    exc,
                    rollback_exception,
                    cleanup_action="Worker storage claim rollback",
                )


class WorkerStorageAdapter:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        storage_scope_state: WorkerStorageScopeState,
    ) -> None:
        self._request = request
        self._storage_scope_state = storage_scope_state

    async def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> WorkerStorageReservationLease:
        active_scope = self._storage_scope_state.get_active_scope()
        if (
            active_scope is not None
            and required_bytes > 0
            and operation == "plugin_sdk.downloads.stream_download"
            and _path_is_under_root(path, active_scope.reservation_root)
        ):
            return WorkerStorageReservationLease(
                self._request,
                reservation_id=active_scope.reservation_id,
                release_enabled=False,
            )
        result = await self._request(
            "storage.reserve_disk_space",
            {
                "path": path,
                "required_bytes": required_bytes,
                "operation": operation,
                "details": dict(details or {}),
            },
        )
        reservation_id = _require_storage_string_value(
            result.get("value"),
            "storage reservation id",
        )
        return WorkerStorageReservationLease(self._request, reservation_id=reservation_id)


def _require_storage_string_value(value: JSONValue | None, label: str) -> str:
    return require_trimmed_json_text(
        value,
        error_message=f"Host service {label} must be a non-empty string.",
    )


def _path_is_under_root(path: str, root: str) -> bool:
    try:
        normalized_path = os.path.abspath(path)
        normalized_root = os.path.abspath(root)
        return os.path.commonpath((normalized_path, normalized_root)) == normalized_root
    except ValueError:
        return False
