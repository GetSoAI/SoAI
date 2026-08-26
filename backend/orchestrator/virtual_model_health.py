"""SoAI - Orchestrator virtual model health state [backend/orchestrator/virtual_model_health.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.timing.formatting import utc_now

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("VirtualModelHealth",)


class VirtualModelHealth:
    def __init__(self, cooldown_seconds: float) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._state: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def update_cooldown(self, cooldown_seconds: float) -> None:
        self._cooldown_seconds = cooldown_seconds

    def _entry_locked(self, virtual_model_name: str) -> dict[str, float] | None:
        if not virtual_model_name:
            return None
        entry = self._state.get(virtual_model_name)
        if entry is None:
            entry = {}
            self._state[virtual_model_name] = entry
        return entry

    async def record_success(self, virtual_model_name: str) -> None:
        await self._update(virtual_model_name, success=True)

    async def record_failure(self, virtual_model_name: str) -> None:
        await self._update(virtual_model_name, success=False)

    async def _update(self, virtual_model_name: str, *, success: bool) -> None:
        async with self._lock:
            entry = self._entry_locked(virtual_model_name)
            if entry is None:
                return
            now = utc_now().timestamp()
            now_monotonic = time.monotonic()
            if success:
                entry["last_success_ts"] = now
                entry["last_success_monotonic"] = now_monotonic
                entry.pop("stale_since_ts", None)
                entry.pop("stale_since_monotonic", None)
                return
            entry["stale_since_ts"] = now
            entry["stale_since_monotonic"] = now_monotonic

    def _in_stale_cooldown_locked(
        self,
        virtual_model_name: str,
        *,
        cleanup_expired: bool = True,
    ) -> bool:
        if not virtual_model_name:
            return False
        entry = self._state.get(virtual_model_name)
        if not entry:
            return False
        stale_since = entry.get("stale_since_monotonic")
        if stale_since is None or not isinstance(stale_since, int | float):
            return False
        elapsed = time.monotonic() - stale_since
        if elapsed < self._cooldown_seconds:
            return True
        if cleanup_expired:
            entry.pop("stale_since_monotonic", None)
            entry.pop("stale_since_ts", None)
            if not entry.get("last_success_ts") and (not entry.get("last_success_monotonic")):
                self._state.pop(virtual_model_name, None)
        return False

    async def in_stale_cooldown(
        self,
        virtual_model_name: str,
        *,
        cleanup_expired: bool = True,
    ) -> bool:
        async with self._lock:
            return self._in_stale_cooldown_locked(
                virtual_model_name,
                cleanup_expired=cleanup_expired,
            )

    async def snapshot(self) -> dict[str, JSONDict]:
        async with self._lock:
            snapshot: dict[str, JSONDict] = {}
            for name, data in list(self._state.items()):
                snapshot[name] = {
                    "last_success_ts": data.get("last_success_ts"),
                    "stale_since_ts": data.get("stale_since_ts"),
                    "is_stale": self._in_stale_cooldown_locked(name, cleanup_expired=False),
                }
            return snapshot

    async def prune(self, active_names: set[str]) -> None:
        async with self._lock:
            if self._state:
                self._state = {
                    name: state for name, state in self._state.items() if name in active_names
                }
