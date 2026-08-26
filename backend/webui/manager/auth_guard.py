"""SoAI - WebUI authentication rate limiting [backend/webui/manager/auth_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TypedDict

from core.timing.epoch import epoch_ms

__all__ = ("AuthFailureGuard",)


class _AuthFailureEntry(TypedDict):
    count: int
    window_start: int


class AuthFailureGuard:
    def __init__(self, window_seconds: int, max_failures: int, max_entries: int = 10000) -> None:
        self.window_ms = max(int(window_seconds) or 1, 1) * 1000
        self.max_failures = max(int(max_failures) or 1, 1)
        self._max_entries = max(int(max_entries) or 1000, 1000)
        self._lock = asyncio.Lock()
        self._entries: dict[str, _AuthFailureEntry] = {}

    def _count_is_throttled(self, count: int) -> bool:
        return int(count) >= int(self.max_failures)

    def _prune_expired_entries_unlocked(self, now: int) -> None:
        expired_keys = [
            key
            for key, entry in self._entries.items()
            if now >= entry["window_start"] + self.window_ms
        ]
        for key in expired_keys:
            del self._entries[key]
        if len(self._entries) > self._max_entries:
            sorted_entries = sorted(self._entries.items(), key=lambda item: item[1]["window_start"])
            for key, _ in sorted_entries[: len(self._entries) - self._max_entries]:
                del self._entries[key]

    async def is_throttled(self, identifier: str) -> tuple[bool, int | None]:
        identifier_value = identifier or "unknown"
        now = epoch_ms()
        async with self._lock:
            self._prune_expired_entries_unlocked(now)
            entry = self._entries.get(identifier_value)
            if not entry:
                return (False, None)
            if now >= entry["window_start"] + self.window_ms:
                del self._entries[identifier_value]
                return (False, None)
            if self._count_is_throttled(entry["count"]):
                return (True, entry["window_start"] + self.window_ms)
            return (False, None)

    async def register_failure(self, identifier: str) -> tuple[bool, int | None]:
        identifier_value = identifier or "unknown"
        now = epoch_ms()
        async with self._lock:
            self._prune_expired_entries_unlocked(now)
            current = self._entries.get(identifier_value)
            if current is None or now >= current["window_start"] + self.window_ms:
                updated: _AuthFailureEntry = {"count": 1, "window_start": now}
            else:
                updated = {
                    "count": current["count"] + 1,
                    "window_start": current["window_start"],
                }
            self._entries[identifier_value] = updated
            self._prune_expired_entries_unlocked(now)
            if self._count_is_throttled(updated["count"]):
                return (True, updated["window_start"] + self.window_ms)
            return (False, None)

    async def reset(self, identifier: str) -> None:
        identifier_value = identifier or "unknown"
        async with self._lock:
            self._entries.pop(identifier_value, None)
