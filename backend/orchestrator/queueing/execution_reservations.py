"""SoAI - Queue execution member reservations [backend/orchestrator/queueing/execution_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Sequence

from core.errors.exceptions import StateError

__all__ = ("QueueExecutionReservations",)


class QueueExecutionReservations:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._universal_id_by_tracking_id: dict[str, str] = {}
        self._tracking_ids_by_universal_id: defaultdict[str, set[str]] = defaultdict(set)

    async def reserve(self, tracking_id: str, universal_id: str) -> None:
        if not tracking_id:
            raise StateError("Execution reservation requires tracking_id.")
        if not universal_id:
            raise StateError("Execution reservation requires universal_id.")
        async with self._lock:
            previous_universal_id = self._universal_id_by_tracking_id.get(tracking_id)
            if previous_universal_id == universal_id:
                return
            if previous_universal_id is not None:
                self._remove_locked(tracking_id, previous_universal_id)
            self._universal_id_by_tracking_id[tracking_id] = universal_id
            self._tracking_ids_by_universal_id[universal_id].add(tracking_id)

    async def release(self, tracking_id: str) -> None:
        if not tracking_id:
            return
        async with self._lock:
            universal_id = self._universal_id_by_tracking_id.get(tracking_id)
            if universal_id is None:
                return
            self._remove_locked(tracking_id, universal_id)

    async def snapshot(self, universal_ids: Sequence[str]) -> dict[str, int]:
        async with self._lock:
            return {
                universal_id: len(self._tracking_ids_by_universal_id.get(universal_id, set()))
                for universal_id in universal_ids
            }

    def _remove_locked(self, tracking_id: str, universal_id: str) -> None:
        self._universal_id_by_tracking_id.pop(tracking_id, None)
        tracking_ids = self._tracking_ids_by_universal_id.get(universal_id)
        if tracking_ids is None:
            return
        tracking_ids.discard(tracking_id)
        if not tracking_ids:
            self._tracking_ids_by_universal_id.pop(universal_id, None)
