"""SoAI - Directory listing session lifecycle registry [backend/features/file_explorer/directory_listing_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import ConflictError, NotFoundError, StateError
from features.file_explorer.directory_listing_dependencies import (
    DirectoryListingRegistryDependencies,
)
from features.file_explorer.directory_listing_state import DirectoryListingRecord

__all__ = ("DirectoryListingRegistry",)

ACTIVE_LISTING_LIMIT_PER_USER = 8
LISTING_IDLE_TTL_MS = 900_000
TOMBSTONE_TTL_MS = 60_000


class DirectoryListingRegistry:
    __slots__ = ("_lock", "_monotonic_clock", "_records", "_tombstones")

    def __init__(self, deps: DirectoryListingRegistryDependencies) -> None:
        self._lock = asyncio.Lock()
        self._monotonic_clock = deps.monotonic_clock
        self._records: dict[str, DirectoryListingRecord] = {}
        self._tombstones: dict[str, tuple[int, int]] = {}

    def _prune_tombstones(self) -> None:
        cutoff = self._monotonic_clock() - TOMBSTONE_TTL_MS
        expired = [
            listing_id
            for listing_id, (_user_id, created_at) in self._tombstones.items()
            if created_at < cutoff
        ]
        for listing_id in expired:
            self._tombstones.pop(listing_id, None)

    async def admit(
        self,
        *,
        listing_id: str,
        user_id: int,
        workspace_path: str,
        virtual_path: str,
    ) -> DirectoryListingRecord:
        async with self._lock:
            self._prune_tombstones()
            tombstone = self._tombstones.get(listing_id)
            if tombstone is not None:
                tombstone_owner = tombstone[0]
                if tombstone_owner != user_id:
                    raise NotFoundError("Directory listing was not found.")
                raise ConflictError("Directory listing was already released.")
            existing = self._records.get(listing_id)
            if existing is not None:
                if existing.user_id != user_id:
                    raise NotFoundError("Directory listing was not found.")
                if (
                    existing.workspace_path != workspace_path
                    or existing.virtual_path != virtual_path
                ):
                    raise ConflictError(
                        "Directory listing identifier is already used by another request.",
                    )
                existing.last_accessed_at_ms = self._monotonic_clock()
                return DirectoryListingRecord(
                    listing_id=existing.listing_id,
                    user_id=existing.user_id,
                    workspace_path=existing.workspace_path,
                    virtual_path=existing.virtual_path,
                    status=existing.status,
                    should_start=False,
                    last_accessed_at_ms=existing.last_accessed_at_ms,
                    task_id=existing.task_id,
                    snapshot_path=existing.snapshot_path,
                    task_event=existing.task_event,
                    cancellation_event=existing.cancellation_event,
                    io_lock=existing.io_lock,
                )
            active_for_user = sum(record.user_id == user_id for record in self._records.values())
            if active_for_user >= ACTIVE_LISTING_LIMIT_PER_USER:
                raise ConflictError(
                    "Too many active directory listings. Release an existing listing.",
                )
            now_ms = self._monotonic_clock()
            record = DirectoryListingRecord(
                listing_id=listing_id,
                user_id=user_id,
                workspace_path=workspace_path,
                virtual_path=virtual_path,
                status="building",
                should_start=True,
                last_accessed_at_ms=now_ms,
            )
            self._records[listing_id] = record
            return record

    async def attach_task(self, listing_id: str, *, task_id: str) -> None:
        async with self._lock:
            record = self._records.get(listing_id)
            if record is None or record.status == "released":
                raise StateError("Directory listing was released before task admission.")
            record.task_id = task_id
            record.last_accessed_at_ms = self._monotonic_clock()
            record.task_event.set()

    async def wait_for_task_id(self, listing_id: str, *, user_id: int) -> str:
        record = await self.get(listing_id, user_id=user_id)
        if record is None:
            raise StateError("Directory listing no longer exists.")
        await record.task_event.wait()
        refreshed = await self.get(listing_id, user_id=user_id)
        if refreshed is None or refreshed.task_id is None:
            raise StateError("Directory listing task admission failed.")
        return refreshed.task_id

    async def mark_ready(
        self,
        listing_id: str,
        *,
        snapshot_path: str,
    ) -> bool:
        async with self._lock:
            record = self._records.get(listing_id)
            if record is None or record.status == "released":
                return False
            record.status = "ready"
            record.snapshot_path = snapshot_path
            record.last_accessed_at_ms = self._monotonic_clock()
            return True

    async def mark_failed(self, listing_id: str) -> None:
        async with self._lock:
            record = self._records.get(listing_id)
            if record is not None and record.status != "released":
                record.status = "failed"
                record.last_accessed_at_ms = self._monotonic_clock()
                record.task_event.set()

    async def get(
        self,
        listing_id: str,
        *,
        user_id: int,
    ) -> DirectoryListingRecord | None:
        async with self._lock:
            record = self._records.get(listing_id)
            if record is None:
                return None
            if record.user_id != user_id:
                raise NotFoundError("Directory listing was not found.")
            record.last_accessed_at_ms = self._monotonic_clock()
            return record

    async def reap_expired(self) -> list[DirectoryListingRecord]:
        async with self._lock:
            self._prune_tombstones()
            cutoff = self._monotonic_clock() - LISTING_IDLE_TTL_MS
            expired = [
                record for record in self._records.values() if record.last_accessed_at_ms <= cutoff
            ]
            for record in expired:
                record.cancellation_event.set()
                record.task_event.set()
            return expired

    async def release(self, listing_id: str, *, user_id: int) -> bool:
        async with self._lock:
            self._prune_tombstones()
            record = self._records.get(listing_id)
            if record is None:
                tombstone = self._tombstones.get(listing_id)
                if tombstone is not None and tombstone[0] != user_id:
                    raise NotFoundError("Directory listing was not found.")
                self._tombstones[listing_id] = (user_id, self._monotonic_clock())
                return False
            if record.user_id != user_id:
                raise NotFoundError("Directory listing was not found.")
            record.cancellation_event.set()
            record.task_event.set()
            self._records.pop(listing_id)
            self._tombstones[listing_id] = (user_id, self._monotonic_clock())
            record.status = "released"
            return True
