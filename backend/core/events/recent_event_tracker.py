"""SoAI - Recent processed event identifier tracking [backend/core/events/recent_event_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time

__all__ = ("RecentEventTracker",)


class RecentEventTracker:
    def __init__(
        self,
        *,
        ttl_seconds: float = 900.0,
        max_size: int = 8192,
        prune_interval_seconds: float = 60.0,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._prune_interval_seconds = prune_interval_seconds
        self._event_ids: dict[str, float] = {}
        self._next_prune_at = 0.0
        self._lock = asyncio.Lock()

    def _prune_unlocked(self, now_monotonic: float, *, force: bool = False) -> None:
        if (not force) and now_monotonic < self._next_prune_at:
            return
        min_allowed_timestamp = now_monotonic - self._ttl_seconds
        expired_event_ids = [
            event_id
            for event_id, processed_at in self._event_ids.items()
            if processed_at <= min_allowed_timestamp
        ]
        for event_id in expired_event_ids:
            self._event_ids.pop(event_id, None)
        overflow_count = len(self._event_ids) - self._max_size
        if overflow_count > 0:
            oldest_entries = sorted(self._event_ids.items(), key=lambda item: item[1])[
                :overflow_count
            ]
            for event_id, _ in oldest_entries:
                self._event_ids.pop(event_id, None)
        self._next_prune_at = now_monotonic + self._prune_interval_seconds

    async def has_recent(self, event_id: str) -> bool:
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            return False
        async with self._lock:
            now_monotonic = time.monotonic()
            self._prune_unlocked(now_monotonic)
            return normalized_event_id in self._event_ids

    async def mark_processed(self, event_id: str) -> None:
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            return
        async with self._lock:
            now_monotonic = time.monotonic()
            self._prune_unlocked(now_monotonic)
            self._event_ids[normalized_event_id] = now_monotonic
